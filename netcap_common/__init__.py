"""
Network Packet Capture Utilities - Common Library

This package provides shared functionality for cross-platform network packet capture utilities.
Supports Windows (10/11, Server) and Linux (Debian/Ubuntu) with Python 3.8+ compatibility.
"""

__version__ = "1.0.0"
__author__ = "Network Security Team"

# Import core classes for easy access
from .platform_manager import PlatformManager
from .interface_manager import InterfaceManager
from .capture_manager import CaptureManager
from .file_manager import FileManager
from .folder_manager import FolderManager
from .logging_manager import LoggingManager
from .filter_handler import FilterHandler
from .concurrent_filter_manager import ConcurrentFilterManager
from .active_scanner import ActiveScanner
from .base_interfaces import CaptureConfig

# Import signal handling utilities
from .signal_handler import SignalHandler, IShutdownHandler, get_signal_handler, setup_global_signal_handling
from .shutdown_utils import setup_utility_shutdown, wait_for_shutdown, UtilityShutdownHandler


__all__ = [
    'PlatformManager',
    'InterfaceManager', 
    'CaptureManager',
    'FileManager',
    'FolderManager',
    'LoggingManager',
    'FilterHandler',
    'ConcurrentFilterManager',
    'ActiveScanner',
    'CaptureConfig',
    'SignalHandler',
    'IShutdownHandler',
    'get_signal_handler',
    'setup_global_signal_handling',
    'setup_utility_shutdown',
    'wait_for_shutdown',
    'UtilityShutdownHandler'
]