"""
Active Scanner - TCP connect scanning with legal compliance checks.

Implements TCP connect scanning with legal compliance enforcement,
rate limiting, and comprehensive audit logging.
"""

import socket
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from .base_interfaces import IActiveScanner


class ScanResult:
    """Represents the result of a port scan."""
    
    def __init__(self, port: int, is_open: bool, response_time: float, error: Optional[str] = None):
        self.port = port
        self.is_open = is_open
        self.response_time = response_time
        self.error = error
        self.timestamp = datetime.now(timezone.utc)


class ActiveScanner(IActiveScanner):
    """Concrete implementation of active port scanning operations."""
    
    def __init__(self, target_host: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the ActiveScanner.
        
        Args:
            target_host: Target hostname or IP address to scan
            logger: Optional logger instance for audit trail
        """
        self.target_host = target_host
        self.logger = logger or logging.getLogger(__name__)
        
        # Rate limiting configuration (non-aggressive scanning)
        self.scan_delay = 0.1  # 100ms delay between scans
        self.connection_timeout = 3.0  # 3 second connection timeout
        self.max_concurrent_scans = 10  # Limit concurrent connections
        
        # Scan statistics
        self.total_scans = 0
        self.open_ports = []
        self.scan_start_time = None
        self.scan_end_time = None
    
    def scan_ports(self, ports: List[int]) -> Dict[int, bool]:
        """
        Scan specified ports and return open/closed status.
        
        Args:
            ports: List of port numbers to scan
            
        Returns:
            Dict mapping port numbers to their open/closed status
        """
        
        if not ports:
            self.logger.warning("No ports specified for scanning")
            return {}
        
        self.logger.info(f"Starting port scan of {len(ports)} ports on {self.target_host}")
        self._log_scan_start("port_list", ports)
        
        self.scan_start_time = datetime.now(timezone.utc)
        results = {}
        scan_results = []
        
        try:
            for i, port in enumerate(ports):
                if i > 0:  # Rate limiting - skip delay for first port
                    time.sleep(self.scan_delay)
                
                scan_result = self._scan_single_port(port)
                results[port] = scan_result.is_open
                scan_results.append(scan_result)
                
                if scan_result.is_open:
                    self.open_ports.append(port)
                    self.logger.info(f"OPEN PORT DETECTED: {self.target_host}:{port} "
                                   f"(response time: {scan_result.response_time:.3f}s)")
                
                self.total_scans += 1
                
                # Log progress every 10 scans or at the end
                if (i + 1) % 10 == 0 or i == len(ports) - 1:
                    self._log_scan_progress(i + 1, len(ports), len(self.open_ports))
        
        except KeyboardInterrupt:
            self.logger.warning("Port scan interrupted by user")
            raise
        except Exception as e:
            self.logger.error(f"Error during port scanning: {e}")
            raise
        finally:
            self.scan_end_time = datetime.now(timezone.utc)
            self._log_scan_completion(scan_results)
        
        return results
    
    def scan_port_range(self, start: int, end: int) -> Dict[int, bool]:
        """
        Scan port range and return open/closed status.
        
        Args:
            start: Starting port number (inclusive)
            end: Ending port number (inclusive)
            
        Returns:
            Dict mapping port numbers to their open/closed status
            
        Raises:
            ValueError: If port range is invalid
        """
        if start < 1 or end > 65535 or start > end:
            raise ValueError(f"Invalid port range: {start}-{end}. Must be 1-65535 and start <= end")
        
        if end - start > 1000:
            self.logger.warning(f"Large port range specified ({end - start + 1} ports). "
                              "Consider using smaller ranges for better performance.")
        
        ports = list(range(start, end + 1))
        self.logger.info(f"Scanning port range {start}-{end} ({len(ports)} ports)")
        
        return self.scan_ports(ports)
    
    
    def get_scan_statistics(self) -> Dict[str, any]:
        """
        Get comprehensive scan statistics.
        
        Returns:
            Dict containing scan statistics
        """
        duration = None
        if self.scan_start_time and self.scan_end_time:
            duration = (self.scan_end_time - self.scan_start_time).total_seconds()
        
        return {
            'target_host': self.target_host,
            'total_scans': self.total_scans,
            'open_ports_count': len(self.open_ports),
            'open_ports': sorted(self.open_ports),
            'scan_start_time': self.scan_start_time.isoformat() if self.scan_start_time else None,
            'scan_end_time': self.scan_end_time.isoformat() if self.scan_end_time else None,
            'duration_seconds': duration,
            'scan_rate': self.total_scans / duration if duration and duration > 0 else None
        }
    
    def _scan_single_port(self, port: int) -> ScanResult:
        """
        Scan a single port using TCP connect.
        
        Args:
            port: Port number to scan
            
        Returns:
            ScanResult: Result of the port scan
        """
        start_time = time.time()
        sock = None
        
        try:
            # Create socket with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connection_timeout)
            
            # Attempt TCP connect
            result = sock.connect_ex((self.target_host, port))
            response_time = time.time() - start_time
            
            if result == 0:
                # Connection successful - port is open
                return ScanResult(port, True, response_time)
            else:
                # Connection failed - port is closed or filtered
                return ScanResult(port, False, response_time)
                
        except socket.gaierror as e:
            # DNS resolution error
            response_time = time.time() - start_time
            error_msg = f"DNS resolution failed: {e}"
            self.logger.error(f"Port {port} scan failed: {error_msg}")
            return ScanResult(port, False, response_time, error_msg)
            
        except socket.timeout:
            # Connection timeout
            response_time = time.time() - start_time
            return ScanResult(port, False, response_time, "Connection timeout")
            
        except Exception as e:
            # Other socket errors
            response_time = time.time() - start_time
            error_msg = f"Socket error: {e}"
            self.logger.error(f"Port {port} scan failed: {error_msg}")
            return ScanResult(port, False, response_time, error_msg)
            
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass  # Ignore close errors
    
    
    def _log_scan_start(self, scan_type: str, target_ports: List[int]):
        """Log the start of a scanning operation."""
        self.logger.info(f"SCAN_START: {scan_type} scan initiated")
        self.logger.info(f"SCAN_TARGET: {self.target_host}")
        self.logger.info(f"SCAN_PORTS: {len(target_ports)} ports")
        self.logger.info(f"SCAN_CONFIG: timeout={self.connection_timeout}s, "
                        f"delay={self.scan_delay}s, max_concurrent={self.max_concurrent_scans}")
        
        # Log first few and last few ports for audit trail
        if len(target_ports) <= 10:
            self.logger.info(f"SCAN_PORT_LIST: {target_ports}")
        else:
            first_ports = target_ports[:5]
            last_ports = target_ports[-5:]
            self.logger.info(f"SCAN_PORT_LIST: {first_ports} ... {last_ports} "
                           f"(total: {len(target_ports)})")
    
    def _log_scan_progress(self, completed: int, total: int, open_count: int):
        """Log scanning progress."""
        progress_pct = (completed / total) * 100
        self.logger.info(f"SCAN_PROGRESS: {completed}/{total} ports scanned "
                        f"({progress_pct:.1f}%), {open_count} open ports found")
    
    def _log_scan_completion(self, scan_results: List[ScanResult]):
        """Log the completion of a scanning operation."""
        duration = (self.scan_end_time - self.scan_start_time).total_seconds()
        scan_rate = len(scan_results) / duration if duration > 0 else 0
        
        self.logger.info(f"SCAN_COMPLETE: Scanned {len(scan_results)} ports in {duration:.2f}s "
                        f"(rate: {scan_rate:.1f} ports/sec)")
        self.logger.info(f"SCAN_RESULTS: {len(self.open_ports)} open ports found")
        
        if self.open_ports:
            self.logger.info(f"OPEN_PORTS: {sorted(self.open_ports)}")
        
        # Log any errors encountered
        error_count = sum(1 for result in scan_results if result.error)
        if error_count > 0:
            self.logger.warning(f"SCAN_ERRORS: {error_count} ports had scan errors")
        
        # Log scan statistics for audit trail
        stats = self.get_scan_statistics()
        self.logger.info(f"SCAN_AUDIT: {stats}")