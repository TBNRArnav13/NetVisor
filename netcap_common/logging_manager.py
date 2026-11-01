"""
Logging Manager for Network Packet Capture Utilities

Provides structured logging with multiple output formats including human-readable text
and JSON structured logs for automated processing. Supports UTC timestamps and 
configurable log levels.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict


@dataclass
class LogEntry:
    """Structured log entry with timestamp and context information."""
    timestamp: str
    level: str
    message: str
    context: Dict[str, Any]
    session_id: Optional[str] = None


class UTCFormatter(logging.Formatter):
    """Custom formatter that uses UTC timestamps in ISO8601 format."""
    
    def formatTime(self, record, datefmt=None):
        """Format time as UTC ISO8601 timestamp."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging output."""
    
    def __init__(self, session_id: Optional[str] = None):
        super().__init__()
        self.session_id = session_id
    
    def format(self, record):
        """Format log record as JSON structure."""
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            level=record.levelname,
            message=record.getMessage(),
            context=getattr(record, 'context', {}),
            session_id=self.session_id
        )
        
        # Add exception info if present
        if record.exc_info:
            log_entry.context['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(asdict(log_entry), ensure_ascii=False)


class LoggingManager:
    """
    Manages logging infrastructure with support for multiple output formats.
    
    Provides structured logging with UTC timestamps, configurable log levels,
    and both human-readable text and JSON output formats.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize logging manager.
        
        Args:
            session_id: Optional session identifier for log correlation
        """
        self.session_id = session_id
        self.logger = None
        self.log_file_path = None
        self.json_mode = False
        self._handlers = []
    
    def setup_logging(self, log_file: Union[str, Path], json_mode: bool = False, 
                     log_level: str = "INFO", console_output: bool = True) -> None:
        """
        Set up logging configuration with specified output format.
        
        Args:
            log_file: Path to log file
            json_mode: If True, output JSON structured logs
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: If True, also log to console
        """
        self.log_file_path = Path(log_file)
        self.json_mode = json_mode
        
        # Create logger
        self.logger = logging.getLogger(f"netcap_{self.session_id or 'default'}")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear any existing handlers
        for handler in self._handlers:
            self.logger.removeHandler(handler)
        self._handlers.clear()
        
        # Create file handler
        file_handler = logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8')
        
        if json_mode:
            file_formatter = JSONFormatter(self.session_id)
        else:
            file_formatter = UTCFormatter(
                fmt='%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
            )
        
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        self._handlers.append(file_handler)
        
        # Add console handler if requested
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = UTCFormatter(
                fmt='%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            self._handlers.append(console_handler)
    
    def _log_with_context(self, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log message with optional context information.
        
        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message
            context: Optional context dictionary
        """
        if not self.logger:
            raise RuntimeError("Logging not initialized. Call setup_logging() first.")
        
        # Create log record with context
        log_method = getattr(self.logger, level.lower())
        
        if context:
            # Add context as extra data for JSON formatter
            extra = {'context': context}
            log_method(message, extra=extra)
        else:
            log_method(message)
    
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message with optional context."""
        self._log_with_context('debug', message, context)
    
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message with optional context."""
        self._log_with_context('info', message, context)
    
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message with optional context."""
        self._log_with_context('warning', message, context)
    
    def error(self, message: str, context: Optional[Dict[str, Any]] = None, 
              exception: Optional[Exception] = None) -> None:
        """
        Log error message with optional context and exception.
        
        Args:
            message: Error message
            context: Optional context dictionary
            exception: Optional exception to include in log
        """
        if exception:
            if context is None:
                context = {}
            context['exception_type'] = type(exception).__name__
            context['exception_message'] = str(exception)
            
            # Log with exception info for stack trace
            if not self.logger:
                raise RuntimeError("Logging not initialized. Call setup_logging() first.")
            
            extra = {'context': context} if context else {}
            self.logger.error(message, exc_info=exception, extra=extra)
        else:
            self._log_with_context('error', message, context)
    
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message with optional context."""
        self._log_with_context('critical', message, context)
    
    def log_capture_start(self, interface: str, filters: Optional[list] = None, 
                         output_files: Optional[Dict[str, str]] = None) -> None:
        """
        Log capture session start with configuration details.
        
        Args:
            interface: Network interface being captured
            filters: List of applied filters
            output_files: Dictionary of output file paths
        """
        context = {
            'interface': interface,
            'filters': filters or [],
            'output_files': output_files or {},
            'session_id': self.session_id
        }
        self.info(f"Starting packet capture on interface '{interface}'", context)
    
    def log_capture_stop(self, total_packets: int, duration: float, 
                        total_bytes: Optional[int] = None) -> None:
        """
        Log capture session stop with summary statistics.
        
        Args:
            total_packets: Total number of packets captured
            duration: Capture duration in seconds
            total_bytes: Total bytes captured (optional)
        """
        context = {
            'total_packets': total_packets,
            'duration_seconds': duration,
            'session_id': self.session_id
        }
        
        if total_bytes is not None:
            context['total_bytes'] = total_bytes
            context['average_packet_size'] = total_bytes / total_packets if total_packets > 0 else 0
        
        if duration > 0:
            context['packets_per_second'] = total_packets / duration
        
        self.info(f"Capture session completed: {total_packets} packets in {duration:.2f} seconds", context)
    
    def log_packet_batch(self, count: int, timestamp: Optional[str] = None, 
                        filename: Optional[str] = None, batch_size_bytes: Optional[int] = None) -> None:
        """
        Log packet batch processing with counts and timestamps.
        
        Args:
            count: Number of packets in batch
            timestamp: Batch timestamp (defaults to current UTC time)
            filename: Output filename for batch
            batch_size_bytes: Size of batch in bytes
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        context = {
            'packet_count': count,
            'batch_timestamp': timestamp,
            'session_id': self.session_id
        }
        
        if filename:
            context['output_file'] = filename
        
        if batch_size_bytes is not None:
            context['batch_size_bytes'] = batch_size_bytes
            context['average_packet_size'] = batch_size_bytes / count if count > 0 else 0
        
        self.debug(f"Processed packet batch: {count} packets", context)
    
    def log_file_rotation(self, old_file: str, new_file: str, file_size_mb: float) -> None:
        """
        Log file rotation event.
        
        Args:
            old_file: Path to rotated file
            new_file: Path to new active file
            file_size_mb: Size of rotated file in MB
        """
        context = {
            'old_file': old_file,
            'new_file': new_file,
            'file_size_mb': file_size_mb,
            'session_id': self.session_id
        }
        self.info(f"File rotated: {old_file} ({file_size_mb:.2f} MB) -> {new_file}", context)
    
    def log_performance_metrics(self, packets_per_second: float, bytes_per_second: float,
                               memory_usage_mb: Optional[float] = None, 
                               cpu_usage_percent: Optional[float] = None) -> None:
        """
        Log performance metrics for monitoring.
        
        Args:
            packets_per_second: Current packet capture rate
            bytes_per_second: Current byte capture rate
            memory_usage_mb: Current memory usage in MB
            cpu_usage_percent: Current CPU usage percentage
        """
        context = {
            'packets_per_second': packets_per_second,
            'bytes_per_second': bytes_per_second,
            'session_id': self.session_id
        }
        
        if memory_usage_mb is not None:
            context['memory_usage_mb'] = memory_usage_mb
        
        if cpu_usage_percent is not None:
            context['cpu_usage_percent'] = cpu_usage_percent
        
        self.debug(f"Performance: {packets_per_second:.1f} pps, {bytes_per_second:.1f} Bps", context)
    
    def log_interface_event(self, interface: str, event_type: str, details: Optional[str] = None) -> None:
        """
        Log interface-related events (up/down, errors, etc.).
        
        Args:
            interface: Network interface name
            event_type: Type of event (up, down, error, etc.)
            details: Optional additional details
        """
        context = {
            'interface': interface,
            'event_type': event_type,
            'session_id': self.session_id
        }
        
        if details:
            context['details'] = details
        
        level = 'warning' if event_type in ['down', 'error'] else 'info'
        message = f"Interface {interface}: {event_type}"
        if details:
            message += f" - {details}"
        
        self._log_with_context(level, message, context)
    
    def log_filter_applied(self, filter_expression: str, filter_type: str = "bpf") -> None:
        """
        Log filter application.
        
        Args:
            filter_expression: The filter expression applied
            filter_type: Type of filter (bpf, display, etc.)
        """
        context = {
            'filter_expression': filter_expression,
            'filter_type': filter_type,
            'session_id': self.session_id
        }
        self.info(f"Applied {filter_type} filter: {filter_expression}", context)
    
    def close(self) -> None:
        """Close logging handlers and cleanup resources."""
        if self.logger:
            for handler in self._handlers:
                handler.close()
                self.logger.removeHandler(handler)
            self._handlers.clear()