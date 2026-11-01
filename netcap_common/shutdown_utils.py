"""
Shutdown Utilities - Helper functions for setting up graceful shutdown in utilities.

Provides convenience functions for setting up signal handling and shutdown procedures
in the main capture utilities (capture_all.py, capture_protocols.py, etc.).
"""

import logging
import sys
import atexit
from typing import List, Optional, Callable
from .signal_handler import setup_global_signal_handling, get_signal_handler, IShutdownHandler


def setup_utility_shutdown(utility_name: str, 
                          handlers: Optional[List[IShutdownHandler]] = None,
                          callbacks: Optional[List[Callable[[], None]]] = None,
                          emergency_timeout: int = 10) -> None:
    """Setup comprehensive shutdown handling for a utility.
    
    Args:
        utility_name: Name of the utility for logging
        handlers: List of shutdown handlers to register
        callbacks: List of shutdown callbacks to register  
        emergency_timeout: Timeout for emergency shutdown operations
    """
    logging.info(f"Setting up shutdown handling for {utility_name}")
    
    try:
        # Setup global signal handling
        signal_handler = setup_global_signal_handling()
        signal_handler.set_emergency_timeout(emergency_timeout)
        
        # Register handlers
        if handlers:
            for handler in handlers:
                signal_handler.register_handler(handler)
                logging.debug(f"Registered shutdown handler: {type(handler).__name__}")
        
        # Register callbacks
        if callbacks:
            for callback in callbacks:
                signal_handler.register_callback(callback)
                logging.debug("Registered shutdown callback")
        
        # Register atexit handler for normal program termination
        def atexit_handler():
            if not signal_handler.is_shutdown_initiated():
                logging.info(f"{utility_name} exiting normally")
                # Trigger graceful shutdown for normal exit
                signal_handler.manual_shutdown(f"{utility_name} normal exit")
        
        atexit.register(atexit_handler)
        
        logging.info(f"Shutdown handling configured for {utility_name}")
        
    except Exception as e:
        logging.error(f"Failed to setup shutdown handling for {utility_name}: {e}")
        raise


def create_shutdown_callback(name: str, cleanup_func: Callable[[], None]) -> Callable[[], None]:
    """Create a named shutdown callback with error handling.
    
    Args:
        name: Name of the callback for logging
        cleanup_func: Function to call during shutdown
        
    Returns:
        Wrapped callback function with error handling
    """
    def callback():
        try:
            logging.info(f"Executing shutdown callback: {name}")
            cleanup_func()
            logging.debug(f"Shutdown callback completed: {name}")
        except Exception as e:
            logging.error(f"Error in shutdown callback {name}: {e}")
    
    return callback


def wait_for_shutdown() -> None:
    """Wait for shutdown signal in main thread.
    
    This function blocks the main thread and waits for shutdown signals.
    Useful for utilities that need to keep running until interrupted.
    """
    signal_handler = get_signal_handler()
    
    try:
        logging.info("Waiting for shutdown signal (Ctrl+C to stop)")
        
        # Keep main thread alive while waiting for signals
        while not signal_handler.is_shutdown_initiated():
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        # This shouldn't happen if signal handling is working correctly,
        # but provide fallback just in case
        logging.info("KeyboardInterrupt received in main thread")
        signal_handler.manual_shutdown("KeyboardInterrupt fallback")
    
    except Exception as e:
        logging.error(f"Error in main wait loop: {e}")
        signal_handler.manual_shutdown(f"Error in main loop: {e}")


def force_shutdown(reason: str = "Force shutdown requested") -> None:
    """Force immediate shutdown of the application.
    
    Args:
        reason: Reason for forced shutdown
    """
    logging.warning(f"Force shutdown requested: {reason}")
    
    signal_handler = get_signal_handler()
    signal_handler.manual_shutdown(reason)


class UtilityShutdownHandler(IShutdownHandler):
    """Generic shutdown handler for utilities with custom cleanup logic."""
    
    def __init__(self, name: str, 
                 shutdown_func: Optional[Callable[[], None]] = None,
                 emergency_func: Optional[Callable[[], None]] = None):
        """Initialize utility shutdown handler.
        
        Args:
            name: Name of the utility/component
            shutdown_func: Function to call for graceful shutdown
            emergency_func: Function to call for emergency shutdown
        """
        self.name = name
        self.shutdown_func = shutdown_func
        self.emergency_func = emergency_func
    
    def shutdown(self) -> None:
        """Perform graceful shutdown."""
        logging.info(f"Graceful shutdown for {self.name}")
        
        if self.shutdown_func:
            try:
                self.shutdown_func()
            except Exception as e:
                logging.error(f"Error in graceful shutdown for {self.name}: {e}")
                # Fall back to emergency procedures
                self.emergency_save()
    
    def emergency_save(self) -> None:
        """Perform emergency data saving."""
        logging.warning(f"Emergency save for {self.name}")
        
        if self.emergency_func:
            try:
                self.emergency_func()
            except Exception as e:
                logging.error(f"Error in emergency save for {self.name}: {e}")
        elif self.shutdown_func:
            # If no specific emergency function, try regular shutdown
            try:
                self.shutdown_func()
            except Exception as e:
                logging.error(f"Error in fallback emergency save for {self.name}: {e}")


def log_platform_signal_info() -> None:
    """Log information about signal handling capabilities on current platform."""
    import signal
    
    platform = sys.platform
    logging.info(f"Signal handling capabilities for platform: {platform}")
    
    # Check available signals
    available_signals = []
    for sig_name in ['SIGINT', 'SIGTERM', 'SIGHUP', 'SIGBREAK']:
        if hasattr(signal, sig_name):
            available_signals.append(sig_name)
    
    logging.info(f"Available signals: {', '.join(available_signals)}")
    
    # Platform-specific information
    if platform.startswith('win'):
        logging.info("Windows platform detected - console control handlers will be used")
        try:
            import win32api
            logging.info("win32api available - enhanced Windows signal handling enabled")
        except ImportError:
            logging.warning("win32api not available - limited Windows signal handling")
    else:
        logging.info("Unix-like platform detected - standard signal handlers will be used")
    
    # Check if running in interactive mode
    if hasattr(sys, 'ps1'):
        logging.warning("Running in interactive mode - signal handling may behave differently")