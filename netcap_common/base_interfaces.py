"""
Base interfaces and abstract classes for platform management and capture operations.

This module defines the core interfaces that all platform-specific implementations
must follow to ensure consistent behavior across Windows and Linux environments.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class InterfaceInfo:
    """Information about a network interface."""
    name: str
    display_name: str
    description: str
    is_active: bool
    ip_addresses: List[str]
    mac_address: str
    platform_specific: Dict[str, Any]


@dataclass
class CaptureSession:
    """Information about a packet capture session."""
    session_id: str
    interface: str
    start_time: datetime
    end_time: Optional[datetime]
    filters: List[str]
    output_files: Dict[str, str]  # type -> filepath
    packet_count: int
    total_bytes: int
    platform: str


@dataclass
class CaptureConfig:
    """Configuration for packet capture operations."""
    interface: str
    output_directory: str
    batch_interval: int = 5
    max_file_size_mb: int = 100
    keep_rotations: int = 5
    json_logging: bool = False
    duration: Optional[int] = None


@dataclass
class LogEntry:
    """Structured log entry for capture operations."""
    timestamp: datetime
    level: str
    message: str
    context: Dict[str, Any]
    session_id: str


class IPlatformManager(ABC):
    """Abstract interface for platform-specific operations."""
    
    @abstractmethod
    def detect_platform(self) -> str:
        """Detect the current platform (Windows/Linux)."""
        pass
    
    @abstractmethod
    def check_privileges(self) -> bool:
        """Check if current user has sufficient privileges for packet capture."""
        pass
    
    @abstractmethod
    def get_privilege_error_message(self) -> str:
        """Get platform-specific error message for insufficient privileges."""
        pass
    
    @abstractmethod
    def get_installation_instructions(self) -> str:
        """Get platform-specific installation instructions for dependencies."""
        pass
    
    @abstractmethod
    def normalize_interface_name(self, interface: str) -> str:
        """Normalize interface name for platform-specific conventions."""
        pass


class IInterfaceManager(ABC):
    """Abstract interface for network interface management."""
    
    @abstractmethod
    def list_interfaces(self) -> List[InterfaceInfo]:
        """List all available network interfaces."""
        pass
    
    @abstractmethod
    def validate_interface(self, interface: str) -> bool:
        """Validate if an interface exists and is accessible."""
        pass
    
    @abstractmethod
    def get_default_interface(self) -> str:
        """Get the default network interface for the platform."""
        pass
    
    @abstractmethod
    def sanitize_interface_name(self, interface: str) -> str:
        """Sanitize interface name for safe filename generation."""
        pass


class ICaptureManager(ABC):
    """Abstract interface for packet capture operations."""
    
    @abstractmethod
    def start_capture(self, filters: Optional[List[str]] = None) -> None:
        """Start packet capture with optional filters."""
        pass
    
    @abstractmethod
    def stop_capture(self) -> None:
        """Stop packet capture gracefully."""
        pass
    
    @abstractmethod
    def set_batch_interval(self, seconds: int = 5) -> None:
        """Set the batch interval for capture cycles."""
        pass
    
    @abstractmethod
    def register_shutdown_handler(self) -> None:
        """Register signal handlers for graceful shutdown."""
        pass


class IFileManager(ABC):
    """Abstract interface for file operations."""
    
    @abstractmethod
    def create_safe_filename(self, base: str, extension: str) -> str:
        """Create a safe filename preventing path traversal."""
        pass
    
    @abstractmethod
    def setup_output_files(self, base_name: str) -> Tuple[str, str]:
        """Setup output files and return PCAP and log file paths."""
        pass
    
    @abstractmethod
    def rotate_file_if_needed(self, filepath: str, max_size_mb: int) -> None:
        """Rotate file if it exceeds maximum size."""
        pass
    
    @abstractmethod
    def cleanup_old_rotations(self, base_path: str, keep_count: int) -> None:
        """Clean up old rotated files keeping only specified count."""
        pass


class ILoggingManager(ABC):
    """Abstract interface for logging operations."""
    
    @abstractmethod
    def setup_logging(self, log_file: str, json_mode: bool = False) -> None:
        """Setup logging configuration."""
        pass
    
    @abstractmethod
    def log_capture_start(self, interface: str, filters: List[str]) -> None:
        """Log capture session start."""
        pass
    
    @abstractmethod
    def log_packet_batch(self, count: int, timestamp: str, filename: str) -> None:
        """Log packet batch processing."""
        pass
    
    @abstractmethod
    def log_error(self, error: Exception, context: str) -> None:
        """Log error with context information."""
        pass
    
    @abstractmethod
    def log_shutdown(self, total_packets: int, duration: float) -> None:
        """Log capture session shutdown."""
        pass


class IFilterHandler(ABC):
    """Abstract interface for packet filter operations."""
    
    @abstractmethod
    def validate_filter(self, filter_str: str) -> bool:
        """Validate filter syntax."""
        pass
    
    @abstractmethod
    def convert_to_bpf(self, protocol: str) -> str:
        """Convert protocol name to BPF filter."""
        pass
    
    @abstractmethod
    def parse_port_specification(self, port_spec: str) -> List[int]:
        """Parse port specification string into list of ports."""
        pass
    
    @abstractmethod
    def create_port_filter(self, ports: List[int]) -> str:
        """Create BPF filter for specified ports."""
        pass


class IActiveScanner(ABC):
    """Abstract interface for active port scanning operations."""
    
    @abstractmethod
    def scan_ports(self, ports: List[int]) -> Dict[int, bool]:
        """Scan specified ports and return open/closed status."""
        pass
    
    @abstractmethod
    def scan_port_range(self, start: int, end: int) -> Dict[int, bool]:
        """Scan port range and return open/closed status."""
        pass
    