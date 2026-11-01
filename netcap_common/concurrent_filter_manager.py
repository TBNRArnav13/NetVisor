"""
Concurrent Filter Manager - Thread-safe filter management for concurrent captures.

Manages multiple capture instances with different filters, providing isolated file outputs
and thread-safe operations across platforms.
"""

import threading
import logging
import time
import os
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, Future
import uuid

from .base_interfaces import CaptureConfig
from .capture_manager import CaptureManager
from .filter_handler import FilterHandler
from .file_manager import FileManager
from .interface_manager import InterfaceManager
from .signal_handler import IShutdownHandler


class FilteredCaptureSession:
    """Represents a single filtered capture session."""
    
    def __init__(self, filter_name: str, filter_str: str, capture_manager: CaptureManager):
        """Initialize filtered capture session.
        
        Args:
            filter_name: Human-readable name for the filter
            filter_str: BPF filter string
            capture_manager: CaptureManager instance for this filter
        """
        self.filter_name = filter_name
        self.filter_str = filter_str
        self.capture_manager = capture_manager
        self.session_id = str(uuid.uuid4())
        self.start_time = None
        self.end_time = None
        self.is_running = False
        self.thread = None
        self.error = None
        
        # Statistics
        self.packet_count = 0
        self.total_bytes = 0
        
        # Thread safety
        self.lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the filtered capture session.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        with self.lock:
            if self.is_running:
                return False
            
            try:
                self.capture_manager.start_capture([self.filter_str])
                self.start_time = datetime.now(timezone.utc)
                self.is_running = True
                
                logging.info(f"Started filtered capture session '{self.filter_name}' "
                           f"with filter: {self.filter_str}")
                return True
                
            except Exception as e:
                self.error = str(e)
                logging.error(f"Failed to start filtered capture '{self.filter_name}': {e}")
                return False
    
    def stop(self) -> bool:
        """Stop the filtered capture session.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        with self.lock:
            if not self.is_running:
                return True
            
            try:
                self.capture_manager.stop_capture()
                self.end_time = datetime.now(timezone.utc)
                self.is_running = False
                
                # Update statistics
                self.packet_count = self.capture_manager.total_packets
                self.total_bytes = self.capture_manager.total_bytes
                
                logging.info(f"Stopped filtered capture session '{self.filter_name}' "
                           f"- {self.packet_count} packets, {self.total_bytes} bytes")
                return True
                
            except Exception as e:
                self.error = str(e)
                logging.error(f"Failed to stop filtered capture '{self.filter_name}': {e}")
                return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the capture session.
        
        Returns:
            Dict containing session status information
        """
        with self.lock:
            return {
                'session_id': self.session_id,
                'filter_name': self.filter_name,
                'filter_str': self.filter_str,
                'is_running': self.is_running,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'packet_count': self.packet_count,
                'total_bytes': self.total_bytes,
                'error': self.error,
                'output_files': getattr(getattr(self.capture_manager, 'session', None), 'output_files', {})
            }


class ConcurrentFilterManager(IShutdownHandler):
    """Manages multiple concurrent capture sessions with different filters."""
    
    def __init__(self, interface: str, output_dir: str, base_config: Optional[CaptureConfig] = None):
        """Initialize concurrent filter manager.
        
        Args:
            interface: Network interface to capture from
            output_dir: Base output directory for all captures
            base_config: Base configuration for all capture sessions
        """
        self.interface = interface
        self.output_dir = output_dir
        self.base_config = base_config or CaptureConfig(
            interface=interface,
            output_directory=output_dir
        )
        
        # Components
        self.filter_handler = FilterHandler()
        self.file_manager = FileManager(output_dir)
        self.interface_manager = InterfaceManager()
        
        # Session management
        self.sessions: Dict[str, FilteredCaptureSession] = {}
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="FilterCapture")
        self.futures: Dict[str, Future] = {}
        
        # Thread safety
        self.manager_lock = threading.RLock()
        self.is_running = False
        self.shutdown_requested = False
        
        # Statistics
        self.total_sessions = 0
        self.active_sessions = 0
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Validate interface
        if not self.interface_manager.validate_interface(interface):
            raise ValueError(f"Invalid or inaccessible interface: {interface}")
    
    def add_protocol_filters(self, protocols: List[str]) -> List[str]:
        """Add multiple protocol filters for concurrent capture.
        
        Args:
            protocols: List of protocol names to capture
            
        Returns:
            List of session IDs for the created capture sessions
            
        Raises:
            ValueError: If any protocol is invalid
        """
        session_ids = []
        
        with self.manager_lock:
            for protocol in protocols:
                try:
                    # Convert protocol to BPF filter
                    bpf_filter = self.filter_handler.convert_to_bpf(protocol)
                    
                    # Create session ID
                    session_id = self._add_filter_session(protocol, bpf_filter)
                    session_ids.append(session_id)
                    
                except Exception as e:
                    self.logger.error(f"Failed to add protocol filter '{protocol}': {e}")
                    # Clean up any successfully created sessions if one fails
                    for sid in session_ids:
                        self._remove_session(sid)
                    raise ValueError(f"Failed to add protocol filter '{protocol}': {e}")
        
        self.logger.info(f"Added {len(session_ids)} protocol filters: {protocols}")
        return session_ids
    
    def add_port_filters(self, port_specs: List[str]) -> List[str]:
        """Add multiple port-based filters for concurrent capture.
        
        Args:
            port_specs: List of port specifications (e.g., ["80,443", "1-1024"])
            
        Returns:
            List of session IDs for the created capture sessions
            
        Raises:
            ValueError: If any port specification is invalid
        """
        session_ids = []
        
        with self.manager_lock:
            for port_spec in port_specs:
                try:
                    # Parse port specification
                    ports = self.filter_handler.parse_port_specification(port_spec)
                    
                    # Create port filter
                    bpf_filter = self.filter_handler.create_port_filter(ports)
                    
                    # Create session ID with descriptive name
                    filter_name = f"ports_{port_spec.replace(',', '_').replace('-', 'to')}"
                    session_id = self._add_filter_session(filter_name, bpf_filter)
                    session_ids.append(session_id)
                    
                except Exception as e:
                    self.logger.error(f"Failed to add port filter '{port_spec}': {e}")
                    # Clean up any successfully created sessions if one fails
                    for sid in session_ids:
                        self._remove_session(sid)
                    raise ValueError(f"Failed to add port filter '{port_spec}': {e}")
        
        self.logger.info(f"Added {len(session_ids)} port filters: {port_specs}")
        return session_ids
    
    def add_custom_filters(self, custom_filters: Dict[str, str]) -> List[str]:
        """Add custom BPF filters for concurrent capture.
        
        Args:
            custom_filters: Dictionary mapping filter names to BPF filter strings
            
        Returns:
            List of session IDs for the created capture sessions
            
        Raises:
            ValueError: If any filter is invalid
        """
        session_ids = []
        
        with self.manager_lock:
            for filter_name, bpf_filter in custom_filters.items():
                try:
                    # Validate filter
                    if not self.filter_handler.validate_filter(bpf_filter):
                        raise ValueError(f"Invalid BPF filter: {bpf_filter}")
                    
                    # Create session
                    session_id = self._add_filter_session(filter_name, bpf_filter)
                    session_ids.append(session_id)
                    
                except Exception as e:
                    self.logger.error(f"Failed to add custom filter '{filter_name}': {e}")
                    # Clean up any successfully created sessions if one fails
                    for sid in session_ids:
                        self._remove_session(sid)
                    raise ValueError(f"Failed to add custom filter '{filter_name}': {e}")
        
        self.logger.info(f"Added {len(session_ids)} custom filters")
        return session_ids
    
    def start_all_captures(self) -> Dict[str, bool]:
        """Start all configured capture sessions concurrently.
        
        Returns:
            Dictionary mapping session IDs to success status
        """
        results = {}
        
        with self.manager_lock:
            if self.is_running:
                raise RuntimeError("Concurrent captures are already running")
            
            if not self.sessions:
                raise RuntimeError("No capture sessions configured")
            
            self.is_running = True
            self.shutdown_requested = False
            
            # Start all sessions concurrently
            for session_id, session in self.sessions.items():
                try:
                    # Submit capture start to thread pool
                    future = self.executor.submit(self._start_session_async, session)
                    self.futures[session_id] = future
                    results[session_id] = True
                    
                except Exception as e:
                    self.logger.error(f"Failed to submit session {session_id}: {e}")
                    results[session_id] = False
            
            # Wait for all sessions to start (with timeout)
            self._wait_for_session_starts(timeout=30)
            
            # Update active session count
            self.active_sessions = sum(1 for session in self.sessions.values() if session.is_running)
            
            self.logger.info(f"Started {self.active_sessions}/{len(self.sessions)} capture sessions")
        
        return results
    
    def stop_all_captures(self) -> Dict[str, bool]:
        """Stop all running capture sessions.
        
        Returns:
            Dictionary mapping session IDs to success status
        """
        results = {}
        
        with self.manager_lock:
            if not self.is_running:
                return {}
            
            self.shutdown_requested = True
            
            # Stop all sessions
            for session_id, session in self.sessions.items():
                try:
                    success = session.stop()
                    results[session_id] = success
                    
                except Exception as e:
                    self.logger.error(f"Failed to stop session {session_id}: {e}")
                    results[session_id] = False
            
            # Cancel any pending futures
            for session_id, future in self.futures.items():
                if not future.done():
                    future.cancel()
            
            self.futures.clear()
            self.is_running = False
            self.active_sessions = 0
            
            self.logger.info(f"Stopped all capture sessions")
        
        return results
    
    def get_session_status(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of capture sessions.
        
        Args:
            session_id: Specific session ID, or None for all sessions
            
        Returns:
            Dictionary containing session status information
        """
        with self.manager_lock:
            if session_id:
                if session_id not in self.sessions:
                    raise ValueError(f"Session not found: {session_id}")
                return self.sessions[session_id].get_status()
            else:
                return {
                    'manager_status': {
                        'is_running': self.is_running,
                        'total_sessions': len(self.sessions),
                        'active_sessions': self.active_sessions,
                        'interface': self.interface,
                        'output_dir': self.output_dir
                    },
                    'sessions': {sid: session.get_status() 
                               for sid, session in self.sessions.items()}
                }
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a capture session.
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            bool: True if removed successfully
        """
        with self.manager_lock:
            return self._remove_session(session_id)
    
    def cleanup(self) -> None:
        """Clean up all resources and stop all captures."""
        self.logger.info("Cleaning up concurrent filter manager")
        
        try:
            # Stop all captures
            self.stop_all_captures()
            
            # Shutdown thread pool
            self.executor.shutdown(wait=True)
            
            # Clear sessions
            with self.manager_lock:
                self.sessions.clear()
                self.futures.clear()
            
            self.logger.info("Concurrent filter manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def shutdown(self) -> None:
        """Implement IShutdownHandler.shutdown() for graceful shutdown."""
        self.logger.info("Graceful shutdown requested for concurrent filter manager")
        self.cleanup()
    
    def emergency_save(self) -> None:
        """Implement IShutdownHandler.emergency_save() for emergency data preservation."""
        self.logger.warning("Emergency save requested for concurrent filter manager")
        
        try:
            # Emergency save for all active sessions
            with self.manager_lock:
                for session_id, session in self.sessions.items():
                    if session.is_running:
                        try:
                            session.capture_manager.emergency_save()
                        except Exception as e:
                            self.logger.error(f"Emergency save failed for session {session_id}: {e}")
            
            self.logger.warning("Emergency save completed for all sessions")
            
        except Exception as e:
            self.logger.error(f"Error during emergency save: {e}")
    
    def _add_filter_session(self, filter_name: str, bpf_filter: str) -> str:
        """Add a new filter session (internal method).
        
        Args:
            filter_name: Human-readable name for the filter
            bpf_filter: BPF filter string
            
        Returns:
            Session ID for the created session
        """
        # Create unique session directory
        safe_interface = self.interface_manager.sanitize_interface_name(self.interface)
        safe_filter_name = self._sanitize_filter_name(filter_name)
        
        session_dir = os.path.join(
            self.output_dir,
            f"protocol_{safe_filter_name}_{safe_interface}"
        )
        
        # Ensure directory exists
        os.makedirs(session_dir, exist_ok=True)
        
        # Create capture configuration for this session
        session_config = CaptureConfig(
          interface=self.interface,
          output_directory=session_dir,
          batch_interval=self.base_config.batch_interval,
          max_file_size_mb=self.base_config.max_file_size_mb,
          keep_rotations=self.base_config.keep_rotations,
          json_logging=self.base_config.json_logging,
          duration=self.base_config.duration
        )
        
        # Create capture manager for this session
        capture_manager = CaptureManager(
            interface=self.interface,
            output_dir=session_dir,
            config=session_config
        )
        
        # Create filtered capture session
        session = FilteredCaptureSession(filter_name, bpf_filter, capture_manager)
        session_id = session.session_id
        
        # Store session
        self.sessions[session_id] = session
        self.total_sessions += 1
        
        self.logger.debug(f"Added filter session '{filter_name}' with ID {session_id}")
        return session_id
    
    def _remove_session(self, session_id: str) -> bool:
        """Remove a session (internal method).
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            bool: True if removed successfully
        """
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        # Stop session if running
        if session.is_running:
            session.stop()
        
        # Cancel future if pending
        if session_id in self.futures:
            future = self.futures[session_id]
            if not future.done():
                future.cancel()
            del self.futures[session_id]
        
        # Remove session
        del self.sessions[session_id]
        
        if self.active_sessions > 0:
            self.active_sessions -= 1
        
        self.logger.debug(f"Removed session {session_id}")
        return True
    
    def _start_session_async(self, session: FilteredCaptureSession) -> bool:
        """Start a session asynchronously (internal method).
        
        Args:
            session: Session to start
            
        Returns:
            bool: True if started successfully
        """
        try:
            return session.start()
        except Exception as e:
            self.logger.error(f"Async session start failed: {e}")
            return False
    
    def _wait_for_session_starts(self, timeout: int = 30) -> None:
        """Wait for all sessions to start (internal method).
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.shutdown_requested:
                break
            
            # Check if all futures are done
            all_done = all(future.done() for future in self.futures.values())
            if all_done:
                break
            
            time.sleep(0.1)
        
        # Log any sessions that didn't start
        for session_id, future in self.futures.items():
            if not future.done():
                self.logger.warning(f"Session {session_id} did not start within timeout")
            elif future.exception():
                self.logger.error(f"Session {session_id} failed to start: {future.exception()}")
    
    def _sanitize_filter_name(self, filter_name: str) -> str:
        """Sanitize filter name for safe filename generation.
        
        Args:
            filter_name: Original filter name
            
        Returns:
            Sanitized filter name safe for filenames
        """
        # Replace unsafe characters with underscores
        import re
        safe_name = re.sub(r'[^\w\-_.]', '_', filter_name)
        
        # Remove multiple consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        
        # Ensure it's not empty
        if not safe_name:
            safe_name = "filter"
        
        # Limit length
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        
        return safe_name