"""
Capture Manager - Core packet capture orchestration using pyshark.

Manages packet capture operations with 5-second batching cycles, PyShark integration,
and graceful shutdown handling.
"""

import threading
import time
import signal
import sys
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

try:
    import pyshark
except ImportError:
    pyshark = None

from .base_interfaces import ICaptureManager, CaptureConfig, CaptureSession
from .signal_handler import IShutdownHandler
from .folder_manager import FolderManager


class PcapFileWriter:
    """PCAP file writer using pyshark capabilities."""
    
    def __init__(self, filepath: str):
        """Initialize PCAP writer.
        
        Args:
            filepath: Path to PCAP file to write
        """
        self.filepath = filepath
        self.file_handle = None
        self.packets_written = 0
        self._initialize_file()
    
    def _initialize_file(self) -> None:
        """Initialize PCAP file with proper headers."""
        try:
            # Open file in binary append mode
            self.file_handle = open(self.filepath, 'ab')
            
            # Write PCAP global header if file is empty
            if os.path.getsize(self.filepath) == 0:
                self._write_pcap_header()
                
        except Exception as e:
            logging.error(f"Failed to initialize PCAP file {self.filepath}: {e}")
            raise
    
    def _write_pcap_header(self) -> None:
        """Write PCAP global header."""
        # PCAP global header (24 bytes)
        # Magic number, version, timezone, timestamp accuracy, max packet length, data link type
        header = bytearray([
            0xD4, 0xC3, 0xB2, 0xA1,  # Magic number (little endian)
            0x02, 0x00,              # Version major (2)
            0x04, 0x00,              # Version minor (4)
            0x00, 0x00, 0x00, 0x00,  # Timezone offset
            0x00, 0x00, 0x00, 0x00,  # Timestamp accuracy
            0xFF, 0xFF, 0x00, 0x00,  # Max packet length (65535)
            0x01, 0x00, 0x00, 0x00   # Data link type (Ethernet)
        ])
        
        if self.file_handle:
            self.file_handle.write(header)
            self.file_handle.flush()
    
    def write_packet(self, packet) -> bool:
        """Write a packet to the PCAP file.
        
        Args:
            packet: PyShark packet object
            
        Returns:
            True if packet was written successfully
        """
        if not self.file_handle:
            return False
        
        try:
            # Get raw packet data
            raw_data = self._extract_raw_data(packet)
            if not raw_data:
                return False
            
            # Write packet record header
            timestamp = time.time()
            ts_sec = int(timestamp)
            ts_usec = int((timestamp - ts_sec) * 1000000)
            
            # Packet record header (16 bytes)
            record_header = bytearray([
                # Timestamp seconds (4 bytes, little endian)
                ts_sec & 0xFF, (ts_sec >> 8) & 0xFF, (ts_sec >> 16) & 0xFF, (ts_sec >> 24) & 0xFF,
                # Timestamp microseconds (4 bytes, little endian)
                ts_usec & 0xFF, (ts_usec >> 8) & 0xFF, (ts_usec >> 16) & 0xFF, (ts_usec >> 24) & 0xFF,
                # Captured packet length (4 bytes, little endian)
                len(raw_data) & 0xFF, (len(raw_data) >> 8) & 0xFF, 
                (len(raw_data) >> 16) & 0xFF, (len(raw_data) >> 24) & 0xFF,
                # Original packet length (4 bytes, little endian)
                len(raw_data) & 0xFF, (len(raw_data) >> 8) & 0xFF, 
                (len(raw_data) >> 16) & 0xFF, (len(raw_data) >> 24) & 0xFF
            ])
            
            # Write record header and packet data
            self.file_handle.write(record_header)
            self.file_handle.write(raw_data)
            
            self.packets_written += 1
            return True
            
        except Exception as e:
            logging.error(f"Error writing packet to PCAP: {e}")
            return False
    
    def _extract_raw_data(self, packet) -> bytes:
        """Extract raw packet data from PyShark packet.
        
        Args:
            packet: PyShark packet object
            
        Returns:
            Raw packet data as bytes
        """
        try:
            # Try different methods to get raw data
            if hasattr(packet, 'get_raw_packet'):
                return packet.get_raw_packet()
            elif hasattr(packet, 'frame_raw'):
                # Convert hex string to bytes
                hex_data = packet.frame_raw.value.replace(':', '')
                return bytes.fromhex(hex_data)
            elif hasattr(packet, 'raw_mode') and packet.raw_mode:
                return packet.raw_mode
            else:
                # Fallback: try to reconstruct from layers
                return self._reconstruct_packet_data(packet)
                
        except Exception as e:
            logging.debug(f"Could not extract raw data from packet: {e}")
            return b''
    
    def _reconstruct_packet_data(self, packet) -> bytes:
        """Attempt to reconstruct packet data from layers.
        
        Args:
            packet: PyShark packet object
            
        Returns:
            Reconstructed packet data as bytes
        """
        try:
            # This is a simplified reconstruction - in practice, this is complex
            # For now, return empty bytes as fallback
            logging.debug("Packet reconstruction not implemented, skipping packet")
            return b''
            
        except Exception:
            return b''
    
    def flush(self) -> None:
        """Flush data to disk."""
        if self.file_handle:
            self.file_handle.flush()
            os.fsync(self.file_handle.fileno())
    
    def close(self) -> None:
        """Close the PCAP file."""
        if self.file_handle:
            self.flush()
            self.file_handle.close()
            self.file_handle = None
        
        logging.info(f"Closed PCAP file {self.filepath}, wrote {self.packets_written} packets")


class RawPcapWriter:
    """Fallback PCAP writer for when pyshark methods are not available."""
    
    def __init__(self, filepath: str):
        """Initialize raw PCAP writer.
        
        Args:
            filepath: Path to PCAP file to write
        """
        self.filepath = filepath
        self.file_handle = None
        self.packets_written = 0
        self._initialize_file()
    
    def _initialize_file(self) -> None:
        """Initialize PCAP file."""
        try:
            # Create empty file or append to existing
            self.file_handle = open(self.filepath, 'ab')
            
            # Write header if file is empty
            if os.path.getsize(self.filepath) == 0:
                self._write_pcap_header()
                
        except Exception as e:
            logging.error(f"Failed to initialize raw PCAP file {self.filepath}: {e}")
            raise
    
    def _write_pcap_header(self) -> None:
        """Write PCAP global header."""
        # Same header as PcapFileWriter
        header = bytearray([
            0xD4, 0xC3, 0xB2, 0xA1,  # Magic number
            0x02, 0x00, 0x04, 0x00,  # Version
            0x00, 0x00, 0x00, 0x00,  # Timezone
            0x00, 0x00, 0x00, 0x00,  # Timestamp accuracy
            0xFF, 0xFF, 0x00, 0x00,  # Max packet length
            0x01, 0x00, 0x00, 0x00   # Data link type
        ])
        
        if self.file_handle:
            self.file_handle.write(header)
            self.file_handle.flush()
    
    def write_packet(self, packet) -> bool:
        """Write packet using fallback method.
        
        Args:
            packet: PyShark packet object
            
        Returns:
            True if packet was processed (may not be written if no raw data)
        """
        if not self.file_handle:
            return False
        
        # For fallback writer, we log the packet but may not be able to write raw data
        # This ensures the capture continues even if we can't extract raw packet data
        logging.debug(f"Processed packet (fallback mode): {getattr(packet, 'summary', 'Unknown')}")
        self.packets_written += 1
        return True
    
    def flush(self) -> None:
        """Flush data to disk."""
        if self.file_handle:
            self.file_handle.flush()
    
    def close(self) -> None:
        """Close the file."""
        if self.file_handle:
            self.flush()
            self.file_handle.close()
            self.file_handle = None
        
        logging.info(f"Closed raw PCAP file {self.filepath}, processed {self.packets_written} packets")


class PySharkError(Exception):
    """Custom exception for PyShark-related errors."""
    pass


class CaptureManager(ICaptureManager, IShutdownHandler):
    """Concrete implementation of packet capture operations using PyShark."""
    
    def __init__(self, interface: str, output_dir: str, config: Optional[CaptureConfig] = None):
        """Initialize CaptureManager with interface and output directory.
        
        Args:
            interface: Network interface name to capture from
            output_dir: Directory to save capture files
            config: Optional capture configuration
        """
        self.interface = interface
        self.output_dir = output_dir
        self.config = config or CaptureConfig(interface=interface, output_directory=output_dir)
        
        # Initialize folder manager for organized file structure
        self.folder_manager = FolderManager(output_dir)
        
        # Capture state
        self.running = False
        self.capture_thread = None
        self.capture = None
        self.session_id = str(uuid.uuid4())
        
        # Packet buffering
        self.packet_buffer = []
        self.buffer_lock = threading.Lock()
        self.total_packets = 0
        self.total_bytes = 0
        
        # Session tracking
        self.session = CaptureSession(
            session_id=self.session_id,
            interface=interface,
            start_time=None,
            end_time=None,
            filters=[],
            output_files={},
            packet_count=0,
            total_bytes=0,
            platform=sys.platform
        )
        
        # Shutdown handling
        self.shutdown_handlers_registered = False
        
        # Validate PyShark availability
        self._validate_pyshark()
    
    def _validate_pyshark(self) -> None:
        """Validate that PyShark is available and properly configured."""
        if pyshark is None:
            raise PySharkError(
                "PyShark is not installed. Please install it using: pip install pyshark"
            )
        
        # Test TShark availability
        try:
            # Try to get TShark version to verify installation
            import subprocess
            result = subprocess.run(['tshark', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise PySharkError("TShark is not properly installed or not in PATH")
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            raise PySharkError(f"TShark validation failed: {e}")
    
    def start_capture(self, filters: Optional[List[str]] = None) -> None:
        """Start packet capture with optional filters.
        
        Args:
            filters: Optional list of BPF filters to apply
            
        Raises:
            PySharkError: If capture cannot be started
            RuntimeError: If capture is already running
        """
        if self.running:
            raise RuntimeError("Capture is already running")
        
        try:
            # Setup capture filters
            capture_filter = None
            if filters:
                # Combine multiple filters with 'or' logic
                capture_filter = ' or '.join(f'({f})' for f in filters)
                self.session.filters = filters
            
            # Initialize PyShark LiveCapture
            self.capture = pyshark.LiveCapture(
                interface=self.interface,
                bpf_filter=capture_filter,
                use_json=True,   # Required for include_raw in newer PyShark versions
                include_raw=True  # Include raw packet data for PCAP writing
            )
            
            # Start capture session
            self.running = True
            self.session.start_time = datetime.now(timezone.utc)
            
            # Start capture thread
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                name=f"CaptureThread-{self.interface}",
                daemon=False
            )
            self.capture_thread.start()
            
            logging.info(f"Started packet capture on interface {self.interface} "
                        f"with session ID {self.session_id}")
            if filters:
                logging.info(f"Applied filters: {filters}")
                
        except Exception as e:
            self.running = False
            self.capture = None
            raise PySharkError(f"Failed to start capture: {e}")
    
    def _kill_pyshark_subprocesses(self) -> None:
        """Terminate any tshark or dumpcap subprocesses to release packet files immediately."""
        try:
            import psutil
            current_process = psutil.Process(os.getpid())
            for child in current_process.children(recursive=True):
                try:
                    pname = child.name().lower()
                    if "tshark" in pname or "dumpcap" in pname:
                        child.kill()
                except Exception:
                    pass
        except Exception as e:
            logging.debug(f"Subprocess cleanup notice: {e}")

    def stop_capture(self) -> None:
        """Stop packet capture gracefully."""
        if not self.running:
            return
        
        logging.info(f"Stopping capture session {self.session_id}")
        
        # Signal capture thread to stop
        self.running = False
        
        # Close PyShark capture gracefully first
        if self.capture:
            try:
                self.capture.close()
            except Exception as e:
                logging.debug(f"PyShark close note: {e}")
            finally:
                self.capture = None
        
        # Ensure any remaining dumpcap/tshark child processes are terminated immediately
        self._kill_pyshark_subprocesses()
        
        # Wait for capture thread to finish (now unblocked immediately)
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2)
        
        # Process any remaining packets in buffer
        self._save_remaining_packets()
        
        # Clean up file resources
        self._cleanup_resources()
        
        # Automatically clean up JSON files for frontend
        self._cleanup_json_files()
        
        # Update session end time
        self.session.end_time = datetime.now(timezone.utc)
        self.session.packet_count = self.total_packets
        self.session.total_bytes = self.total_bytes
        
        logging.info(f"Capture session {self.session_id} stopped. "
                    f"Total packets: {self.total_packets}, "
                    f"Total bytes: {self.total_bytes}")
    
    def _save_remaining_packets(self) -> None:
        """Save any remaining packets in the buffer."""
        try:
            with self.buffer_lock:
                if self.packet_buffer:
                    logging.info(f"Saving {len(self.packet_buffer)} remaining packets")
                    self._write_packet_batch(self.packet_buffer)
                    self.packet_buffer.clear()
        except Exception as e:
            logging.error(f"Error saving remaining packets: {e}")
            # Continue with cleanup even if packet saving fails
    
    def set_batch_interval(self, seconds: int = 5) -> None:
        """Set the batch interval for capture cycles.
        
        Args:
            seconds: Batch interval in seconds (default: 5)
        """
        if seconds < 1:
            raise ValueError("Batch interval must be at least 1 second")
        
        self.config.batch_interval = seconds
        logging.info(f"Set batch interval to {seconds} seconds")
    
    def register_shutdown_handler(self) -> None:
        """Register signal handlers for graceful shutdown."""
        if self.shutdown_handlers_registered:
            return
        
        # Import here to avoid circular imports
        from .signal_handler import register_shutdown_handler
        
        # Register this capture manager with the global signal handler
        register_shutdown_handler(self)
        
        self.shutdown_handlers_registered = True
        logging.info("Registered CaptureManager with global shutdown handler")
    
    def shutdown(self) -> None:
        """Implement IShutdownHandler.shutdown() for graceful shutdown."""
        logging.info(f"Graceful shutdown requested for capture session {self.session_id}")
        self.stop_capture()
    
    def emergency_save(self) -> None:
        """Implement IShutdownHandler.emergency_save() for emergency data preservation."""
        logging.warning(f"Emergency save requested for capture session {self.session_id}")
        
        try:
            # Stop capture immediately without waiting for threads
            self.running = False
            
            # Save any buffered packets immediately
            with self.buffer_lock:
                if self.packet_buffer:
                    logging.info(f"Emergency saving {len(self.packet_buffer)} buffered packets")
                    self._write_packet_batch(self.packet_buffer)
                    self.packet_buffer.clear()
            
            # Force close all file handles
            self._cleanup_resources()
            
            # Log emergency save completion
            logging.warning(f"Emergency save completed for session {self.session_id}")
            
        except Exception as e:
            logging.error(f"Error during emergency save: {e}")
            # Continue anyway to ensure resources are released
    
    def _flush_batch(self, batch_packets: List[Any]) -> None:
        """Flush a completed batch to buffer and files."""
        if not batch_packets:
            return
            
        with self.buffer_lock:
            self.packet_buffer.extend(batch_packets)
            self.total_packets += len(batch_packets)
            
            for packet in batch_packets:
                try:
                    if hasattr(packet, 'length'):
                        self.total_bytes += int(packet.length)
                    elif hasattr(packet, 'captured_length'):
                        self.total_bytes += int(packet.captured_length)
                except (ValueError, AttributeError):
                    pass
        
        self._write_packet_batch(batch_packets)
        logging.debug(f"Processed batch of {len(batch_packets)} packets")

    def _capture_loop(self) -> None:
        """Internal capture loop with continuous single-process stream and 5s batching."""
        logging.info(f"Starting capture loop with {self.config.batch_interval}s batch interval")
        
        try:
            batch_start_time = time.time()
            batch_packets = []
            
            for packet in self.capture.sniff_continuously():
                if not self.running:
                    break
                
                batch_packets.append(packet)
                
                if time.time() - batch_start_time >= self.config.batch_interval:
                    self._flush_batch(batch_packets)
                    batch_packets = []
                    batch_start_time = time.time()
            
            if batch_packets:
                self._flush_batch(batch_packets)
                
        except Exception as e:
            if self.running:
                logging.error(f"Error during packet capture: {e}")
        finally:
            logging.info("Capture loop terminated")
    
    def _write_packet_batch(self, packets: List[Any]) -> None:
        """Write packet batch to PCAP file and log.
        
        Args:
            packets: List of captured packets to write
        """
        if not packets:
            return
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            # Initialize output files if not already done
            if not hasattr(self, 'pcap_writer') or not hasattr(self, 'log_file'):
                self._initialize_output_files()
            
            # Write packets to PCAP file
            packets_written = self._write_packets_to_pcap(packets)
            
            # Write packets to JSON file
            self._write_packets_to_json(packets, timestamp)
            
            # Write log entry
            self._write_log_entry(packets_written, timestamp)
            
            # Check if file rotation is needed
            self._check_file_rotation()
            
        except Exception as e:
            logging.error(f"Error writing packet batch: {e}")
            # Continue operation even if writing fails
        
        # Clear the buffer after processing
        with self.buffer_lock:
            # Remove processed packets from buffer
            for _ in range(len(packets)):
                if self.packet_buffer:
                    self.packet_buffer.pop(0)
    
    def _initialize_output_files(self) -> None:
        """Initialize PCAP, log, and JSON output files using folder manager."""
        from .interface_manager import InterfaceManager
        
        # Create interface manager for name sanitization
        if not hasattr(self, 'interface_manager'):
            self.interface_manager = InterfaceManager()
        
        # Generate session name
        safe_interface = self.interface_manager.sanitize_interface_name(self.interface)
        session_name = f"capture_{safe_interface}"
        
        # Get file paths from folder manager
        file_paths = self.folder_manager.get_capture_paths(session_name)
        
        self.pcap_filepath = file_paths['pcap_file']
        self.log_filepath = file_paths['log_file']
        self.json_filepath = file_paths['json_file']
        
        # Update session info
        self.session.output_files = {
            'pcap': self.pcap_filepath,
            'log': self.log_filepath,
            'json': self.json_filepath
        }
        
        # Initialize writers
        self._initialize_pcap_writer()
        self._initialize_log_file()
        self._initialize_json_file()
        
        logging.info(f"Initialized output files:")
        logging.info(f"  PCAP: {self.pcap_filepath}")
        logging.info(f"  LOG: {self.log_filepath}")
        logging.info(f"  JSON: {self.json_filepath}")
    
    def _initialize_pcap_writer(self) -> None:
        """Initialize PCAP writer for packet storage."""
        try:
            # Try to use pyshark's PcapWriter if available
            if hasattr(pyshark, 'FileCapture'):
                # Use a custom PCAP writer implementation
                self.pcap_writer = PcapFileWriter(self.pcap_filepath)
            else:
                # Fallback to raw file writing
                self.pcap_writer = RawPcapWriter(self.pcap_filepath)
                
        except Exception as e:
            logging.error(f"Failed to initialize PCAP writer: {e}")
            # Use fallback writer
            self.pcap_writer = RawPcapWriter(self.pcap_filepath)
    
    def _initialize_log_file(self) -> None:
        """Initialize log file for capture session."""
        try:
            self.log_file = open(self.log_filepath, 'a', encoding='utf-8')
            
            # Write session header
            header = (
                f"# Packet Capture Session Log\n"
                f"# Session ID: {self.session_id}\n"
                f"# Interface: {self.interface}\n"
                f"# Started: {self.session.start_time.isoformat() if self.session.start_time else 'Unknown'}\n"
                f"# Platform: {self.session.platform}\n"
                f"# Filters: {', '.join(self.session.filters) if self.session.filters else 'None'}\n"
                f"#\n"
                f"# Format: timestamp,packet_count,total_packets,total_bytes,batch_duration_ms\n"
                f"\n"
            )
            self.log_file.write(header)
            self.log_file.flush()
            
        except Exception as e:
            logging.error(f"Failed to initialize log file: {e}")
            self.log_file = None
    
    def _write_packets_to_pcap(self, packets: List[Any]) -> int:
        """Write packets to PCAP file.
        
        Args:
            packets: List of packets to write
            
        Returns:
            Number of packets successfully written
        """
        if not self.pcap_writer:
            return 0
        
        packets_written = 0
        
        try:
            for packet in packets:
                if self.pcap_writer.write_packet(packet):
                    packets_written += 1
            
            # Flush data to ensure persistence
            self.pcap_writer.flush()
            
        except Exception as e:
            logging.error(f"Error writing packets to PCAP: {e}")
        
        return packets_written
    
    def _write_log_entry(self, packet_count: int, timestamp: str) -> None:
        """Write log entry for packet batch.
        
        Args:
            packet_count: Number of packets in this batch
            timestamp: Timestamp of the batch
        """
        if not self.log_file:
            return
        
        try:
            # Calculate batch duration (approximate)
            batch_duration_ms = self.config.batch_interval * 1000
            
            log_entry = (
                f"{timestamp},{packet_count},{self.total_packets},"
                f"{self.total_bytes},{batch_duration_ms}\n"
            )
            
            self.log_file.write(log_entry)
            self.log_file.flush()
            
        except Exception as e:
            logging.error(f"Error writing log entry: {e}")
    
    def _write_packets_to_json(self, packets: List[Any], timestamp: str) -> None:
        """Write packet batch to JSON file for frontend integration.
        
        Args:
            packets: List of captured packets
            timestamp: Timestamp of the batch
        """
        if not packets:
            return
        
        try:
            # Initialize JSON file if not exists
            if not hasattr(self, 'json_file') or not self.json_file:
                self._initialize_json_file()
            
            # Convert packets to JSON format
            json_packets = []
            for i, packet in enumerate(packets):
                try:
                    packet_data = {
                        'timestamp': timestamp,
                        'packet_number': self.total_packets - len(packets) + i + 1,
                        'length': len(packet) if hasattr(packet, '__len__') else 0,
                        'protocols': [],
                        'source': '',
                        'destination': '',
                        'info': ''
                    }
                    
                    # Extract packet information
                    if hasattr(packet, 'layers'):
                        packet_data['protocols'] = [layer.layer_name for layer in packet.layers]
                    
                    # Extract source and destination
                    if hasattr(packet, 'ip'):
                        packet_data['source'] = getattr(packet.ip, 'src', '')
                        packet_data['destination'] = getattr(packet.ip, 'dst', '')
                    elif hasattr(packet, 'ipv6'):
                        packet_data['source'] = getattr(packet.ipv6, 'src', '')
                        packet_data['destination'] = getattr(packet.ipv6, 'dst', '')
                    elif hasattr(packet, 'eth'):
                        packet_data['source'] = getattr(packet.eth, 'src', '')
                        packet_data['destination'] = getattr(packet.eth, 'dst', '')
                    
                    # Extract protocol-specific information
                    if hasattr(packet, 'tcp'):
                        packet_data['source_port'] = getattr(packet.tcp, 'srcport', '')
                        packet_data['destination_port'] = getattr(packet.tcp, 'dstport', '')
                        packet_data['info'] = f"TCP {packet_data['source_port']} → {packet_data['destination_port']}"
                    elif hasattr(packet, 'udp'):
                        packet_data['source_port'] = getattr(packet.udp, 'srcport', '')
                        packet_data['destination_port'] = getattr(packet.udp, 'dstport', '')
                        packet_data['info'] = f"UDP {packet_data['source_port']} → {packet_data['destination_port']}"
                    elif hasattr(packet, 'http'):
                        packet_data['info'] = f"HTTP {getattr(packet.http, 'request_method', 'Response')}"
                        if hasattr(packet.http, 'host'):
                            packet_data['http_host'] = packet.http.host
                        if hasattr(packet.http, 'request_uri'):
                            packet_data['http_uri'] = packet.http.request_uri
                    elif hasattr(packet, 'dns'):
                        packet_data['info'] = f"DNS Query"
                        if hasattr(packet.dns, 'qry_name'):
                            packet_data['dns_query'] = packet.dns.qry_name
                    
                    json_packets.append(packet_data)
                    
                except Exception as e:
                    # If packet parsing fails, create minimal entry
                    json_packets.append({
                        'timestamp': timestamp,
                        'packet_number': self.total_packets - len(packets) + i + 1,
                        'length': 0,
                        'protocols': ['Unknown'],
                        'source': '',
                        'destination': '',
                        'info': f'Packet parsing error: {str(e)[:100]}',
                        'error': True
                    })
            
            # Write batch to JSON file
            batch_data = {
                'batch_timestamp': timestamp,
                'batch_number': getattr(self, 'batch_counter', 0) + 1,
                'interface': self.interface,
                'packet_count': len(json_packets),
                'total_packets': self.total_packets,
                'packets': json_packets
            }
            
            # Increment batch counter
            if not hasattr(self, 'batch_counter'):
                self.batch_counter = 0
            self.batch_counter += 1
            
            # Write to JSON file with beautiful formatting
            import json
            json_line = json.dumps(batch_data, indent=2, ensure_ascii=False) + '\n'
            self.json_file.write(json_line)
            self.json_file.flush()
            
        except Exception as e:
            logging.error(f"Error writing packets to JSON: {e}")
    
    def _initialize_json_file(self) -> None:
        """Initialize JSON output file in captures directory."""
        try:
            # JSON filepath is already set by folder manager
            self.json_file = open(self.json_filepath, 'w', encoding='utf-8')
            
            # Write JSON file header
            header = {
                'file_info': {
                    'format': 'NetCap JSON Packet Log',
                    'version': '1.0',
                    'created': datetime.now(timezone.utc).isoformat(),
                    'interface': self.interface,
                    'session_id': str(self.session_id),
                    'frontend_compatible': True
                }
            }
            
            import json
            header_line = json.dumps(header, indent=2, ensure_ascii=False) + '\n'
            self.json_file.write(header_line)
            self.json_file.flush()
            
            logging.info(f"Initialized JSON output file: {self.json_filepath}")
            
        except Exception as e:
            logging.error(f"Error initializing JSON file: {e}")
            self.json_file = None
    
    def _check_file_rotation(self) -> None:
        """Check if files need rotation based on size limits."""
        if not hasattr(self, 'file_manager'):
            return
        
        try:
            # Check PCAP file rotation
            if (hasattr(self, 'pcap_filepath') and 
                self.file_manager.rotate_file_if_needed(self.pcap_filepath, self.config.max_file_size_mb)):
                
                logging.info(f"Rotated PCAP file: {self.pcap_filepath}")
                # Reinitialize PCAP writer for new file
                self._initialize_pcap_writer()
            
            # Check log file rotation
            if (hasattr(self, 'log_filepath') and 
                self.file_manager.rotate_file_if_needed(self.log_filepath, self.config.max_file_size_mb)):
                
                logging.info(f"Rotated log file: {self.log_filepath}")
                # Reinitialize log file
                if hasattr(self, 'log_file') and self.log_file:
                    self.log_file.close()
                self._initialize_log_file()
                
        except Exception as e:
            logging.error(f"Error during file rotation check: {e}")
    
    def _cleanup_resources(self) -> None:
        """Clean up file resources and network handles."""
        logging.debug("Cleaning up capture resources")
        
        # Close PCAP writer
        try:
            if hasattr(self, 'pcap_writer') and self.pcap_writer:
                logging.debug("Closing PCAP writer")
                self.pcap_writer.close()
                self.pcap_writer = None
        except Exception as e:
            logging.error(f"Error closing PCAP writer: {e}")
        
        # Close log file
        try:
            if hasattr(self, 'log_file') and self.log_file:
                logging.debug("Closing log file")
                # Write final log entry
                try:
                    final_entry = (
                        f"# Capture session ended at {datetime.now(timezone.utc).isoformat()}\n"
                        f"# Final stats: {self.total_packets} packets, {self.total_bytes} bytes\n"
                    )
                    self.log_file.write(final_entry)
                    self.log_file.flush()
                except Exception:
                    pass  # Don't fail cleanup if final log write fails
                
                self.log_file.close()
                self.log_file = None
        except Exception as e:
            logging.error(f"Error closing log file: {e}")
        
        # Close JSON file
        try:
            if hasattr(self, 'json_file') and self.json_file:
                logging.debug("Closing JSON file")
                # Write final JSON entry
                try:
                    final_entry = {
                        'file_info': {
                            'session_ended': datetime.now(timezone.utc).isoformat(),
                            'final_packet_count': self.total_packets,
                            'final_byte_count': self.total_bytes,
                            'total_batches': getattr(self, 'batch_counter', 0)
                        }
                    }
                    import json
                    final_line = json.dumps(final_entry, indent=2, ensure_ascii=False) + '\n'
                    self.json_file.write(final_line)
                    self.json_file.flush()
                except Exception:
                    pass  # Don't fail cleanup if final JSON write fails
                
                self.json_file.close()
                self.json_file = None
        except Exception as e:
            logging.error(f"Error closing JSON file: {e}")
        
        # Clean up PyShark capture if still open
        try:
            if self.capture:
                logging.debug("Force closing PyShark capture")
                self.capture.close()
                self.capture = None
        except Exception as e:
            logging.debug(f"Error force closing PyShark capture: {e}")
        
        # Clear packet buffer
        try:
            with self.buffer_lock:
                if self.packet_buffer:
                    logging.debug(f"Clearing {len(self.packet_buffer)} packets from buffer")
                    self.packet_buffer.clear()
        except Exception as e:
            logging.error(f"Error clearing packet buffer: {e}")
        
        logging.debug("Resource cleanup completed")
    
    def _cleanup_json_files(self) -> None:
        """Clean up JSON files from captures directory after capture stops."""
        try:
            removed_files = self.folder_manager.cleanup_json_files(self.session_id[:8])
            if removed_files:
                logging.info(f"Cleaned up {len(removed_files)} JSON files from captures directory")
                for file_path in removed_files:
                    logging.debug(f"Removed: {file_path}")
            else:
                logging.debug("No JSON files to clean up")
        except Exception as e:
            logging.error(f"Error during JSON cleanup: {e}")
    
    def get_session_info(self) -> CaptureSession:
        """Get current capture session information.
        
        Returns:
            CaptureSession object with current session details
        """
        # Update current packet count
        self.session.packet_count = self.total_packets
        self.session.total_bytes = self.total_bytes
        return self.session
    
    def is_running(self) -> bool:
        """Check if capture is currently running.
        
        Returns:
            True if capture is active, False otherwise
        """
        return self.running