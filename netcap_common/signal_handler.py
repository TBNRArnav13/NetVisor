"""
Signal Handler - Cross-platform signal handling for graceful shutdown.

Provides comprehensive signal handling for SIGINT/SIGTERM on Linux and 
CTRL+C/CTRL+BREAK on Windows with graceful capture stopping, data preservation,
and resource cleanup.
"""

import signal
import sys
import threading
import logging
import time
from typing import Callable, List, Optional, Dict, Any
from abc import ABC, abstractmethod


class IShutdownHandler(ABC):
    """Interface for objects that need graceful shutdown handling."""
    
    @abstractmethod
    def shutdown(self) -> None:
        """Perform graceful shutdown operations."""
        pass
    
    @abstractmethod
    def emergency_save(self) -> None:
        """Perform emergency data saving for partial capture buffers."""
        pass


class SignalHandler:
    """Cross-platform signal handler for graceful shutdown."""
    
    def __init__(self):
        """Initialize signal handler."""
        self.shutdown_handlers: List[IShutdownHandler] = []
        self.shutdown_callbacks: List[Callable[[], None]] = []
        self.shutdown_initiated = False
        self.shutdown_lock = threading.Lock()
        self.emergency_timeout = 10  # seconds
        self.platform = sys.platform
        
        # Track registered signals for cleanup
        self.registered_signals: List[int] = []
        self.original_handlers: Dict[int, Any] = {}
        
        # Windows-specific handler reference
        self.win_handler_ref = None
        
        logging.info(f"Initialized SignalHandler for platform: {self.platform}")
    
    def register_handler(self, handler: IShutdownHandler) -> None:
        """Register a shutdown handler object.
        
        Args:
            handler: Object implementing IShutdownHandler interface
        """
        if handler not in self.shutdown_handlers:
            self.shutdown_handlers.append(handler)
            logging.debug(f"Registered shutdown handler: {type(handler).__name__}")
    
    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a shutdown callback function.
        
        Args:
            callback: Function to call during shutdown
        """
        if callback not in self.shutdown_callbacks:
            self.shutdown_callbacks.append(callback)
            logging.debug("Registered shutdown callback")
    
    def unregister_handler(self, handler: IShutdownHandler) -> None:
        """Unregister a shutdown handler.
        
        Args:
            handler: Handler to remove
        """
        if handler in self.shutdown_handlers:
            self.shutdown_handlers.remove(handler)
            logging.debug(f"Unregistered shutdown handler: {type(handler).__name__}")
    
    def setup_signal_handlers(self) -> None:
        """Setup cross-platform signal handlers."""
        if self.platform.startswith('win'):
            self._setup_windows_handlers()
        else:
            self._setup_unix_handlers()
        
        logging.info("Signal handlers registered successfully")
    
    def _setup_unix_handlers(self) -> None:
        """Setup signal handlers for Unix-like systems (Linux, macOS)."""
        signals_to_handle = []
        
        # SIGINT (Ctrl+C)
        if hasattr(signal, 'SIGINT'):
            signals_to_handle.append(signal.SIGINT)
        
        # SIGTERM (termination request)
        if hasattr(signal, 'SIGTERM'):
            signals_to_handle.append(signal.SIGTERM)
        
        # SIGHUP (hangup) - optional, for daemon processes
        if hasattr(signal, 'SIGHUP'):
            signals_to_handle.append(signal.SIGHUP)
        
        for sig in signals_to_handle:
            try:
                # Store original handler
                self.original_handlers[sig] = signal.signal(sig, self._unix_signal_handler)
                self.registered_signals.append(sig)
                logging.debug(f"Registered Unix signal handler for signal {sig}")
            except (OSError, ValueError) as e:
                logging.warning(f"Could not register handler for signal {sig}: {e}")
    
    def _setup_windows_handlers(self) -> None:
        """Setup signal handlers for Windows systems."""
        # Standard signal handlers that work on Windows
        signals_to_handle = []
        
        if hasattr(signal, 'SIGINT'):
            signals_to_handle.append(signal.SIGINT)
        if hasattr(signal, 'SIGTERM'):
            signals_to_handle.append(signal.SIGTERM)
        if hasattr(signal, 'SIGBREAK'):
            signals_to_handle.append(signal.SIGBREAK)
        
        for sig in signals_to_handle:
            try:
                self.original_handlers[sig] = signal.signal(sig, self._unix_signal_handler)
                self.registered_signals.append(sig)
                logging.debug(f"Registered Windows signal handler for signal {sig}")
            except (OSError, ValueError) as e:
                logging.warning(f"Could not register handler for signal {sig}: {e}")
        
        # Windows-specific console control handler
        self._setup_windows_console_handler()
    
    def _setup_windows_console_handler(self) -> None:
        """Setup Windows console control handler for CTRL+C, CTRL+BREAK, etc."""
        try:
            import win32api
            import win32con
            
            def windows_console_handler(ctrl_type):
                """Handle Windows console control events."""
                event_names = {
                    win32con.CTRL_C_EVENT: "CTRL+C",
                    win32con.CTRL_BREAK_EVENT: "CTRL+BREAK", 
                    win32con.CTRL_CLOSE_EVENT: "Console Close",
                    win32con.CTRL_LOGOFF_EVENT: "User Logoff",
                    win32con.CTRL_SHUTDOWN_EVENT: "System Shutdown"
                }
                
                event_name = event_names.get(ctrl_type, f"Unknown({ctrl_type})")
                logging.info(f"Received Windows console event: {event_name}")
                
                # Handle shutdown events
                if ctrl_type in (win32con.CTRL_C_EVENT, win32con.CTRL_BREAK_EVENT, 
                               win32con.CTRL_CLOSE_EVENT):
                    self._initiate_shutdown(f"Windows console event: {event_name}")
                    return True  # Indicate we handled the event
                elif ctrl_type in (win32con.CTRL_LOGOFF_EVENT, win32con.CTRL_SHUTDOWN_EVENT):
                    # For system events, do emergency shutdown
                    self._initiate_emergency_shutdown(f"Windows system event: {event_name}")
                    return True
                
                return False  # Let default handler process
            
            # Store reference to prevent garbage collection
            self.win_handler_ref = windows_console_handler
            win32api.SetConsoleCtrlHandler(windows_console_handler, True)
            logging.info("Registered Windows console control handler")
            
        except ImportError:
            logging.warning("win32api not available, Windows-specific console handling disabled")
        except Exception as e:
            logging.error(f"Failed to setup Windows console handler: {e}")
    
    def _unix_signal_handler(self, signum: int, frame) -> None:
        """Handle Unix signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_names = {
            getattr(signal, 'SIGINT', None): 'SIGINT',
            getattr(signal, 'SIGTERM', None): 'SIGTERM', 
            getattr(signal, 'SIGHUP', None): 'SIGHUP',
            getattr(signal, 'SIGBREAK', None): 'SIGBREAK'
        }
        
        signal_name = signal_names.get(signum, f'Signal {signum}')
        logging.info(f"Received signal: {signal_name}")
        
        # Determine shutdown type based on signal
        if signum == getattr(signal, 'SIGINT', None):
            # SIGINT (Ctrl+C) - graceful shutdown
            self._initiate_shutdown(f"Received {signal_name}")
        elif signum == getattr(signal, 'SIGTERM', None):
            # SIGTERM - graceful shutdown
            self._initiate_shutdown(f"Received {signal_name}")
        elif signum == getattr(signal, 'SIGHUP', None):
            # SIGHUP - could be graceful or emergency depending on context
            self._initiate_shutdown(f"Received {signal_name}")
        else:
            # Other signals - emergency shutdown
            self._initiate_emergency_shutdown(f"Received {signal_name}")
    
    def _initiate_shutdown(self, reason: str) -> None:
        """Initiate graceful shutdown process.
        
        Args:
            reason: Reason for shutdown
        """
        with self.shutdown_lock:
            if self.shutdown_initiated:
                logging.warning("Shutdown already in progress, ignoring additional signal")
                return
            
            self.shutdown_initiated = True
        
        logging.info(f"Initiating graceful shutdown: {reason}")
        
        # Start shutdown in separate thread to avoid blocking signal handler
        shutdown_thread = threading.Thread(
            target=self._execute_graceful_shutdown,
            args=(reason,),
            name="GracefulShutdown",
            daemon=False
        )
        shutdown_thread.start()
    
    def _initiate_emergency_shutdown(self, reason: str) -> None:
        """Initiate emergency shutdown with timeout.
        
        Args:
            reason: Reason for emergency shutdown
        """
        with self.shutdown_lock:
            if self.shutdown_initiated:
                logging.warning("Shutdown already in progress, forcing emergency procedures")
                self._force_emergency_save()
                return
            
            self.shutdown_initiated = True
        
        logging.warning(f"Initiating emergency shutdown: {reason}")
        
        # Start emergency shutdown with timeout
        emergency_thread = threading.Thread(
            target=self._execute_emergency_shutdown,
            args=(reason,),
            name="EmergencyShutdown", 
            daemon=False
        )
        emergency_thread.start()
    
    def _execute_graceful_shutdown(self, reason: str) -> None:
        """Execute graceful shutdown procedures.
        
        Args:
            reason: Reason for shutdown
        """
        try:
            logging.info("Starting graceful shutdown procedures")
            
            # Call shutdown callbacks first
            for callback in self.shutdown_callbacks:
                try:
                    logging.debug("Executing shutdown callback")
                    callback()
                except Exception as e:
                    logging.error(f"Error in shutdown callback: {e}")
            
            # Call shutdown handlers
            for handler in self.shutdown_handlers:
                try:
                    logging.debug(f"Shutting down handler: {type(handler).__name__}")
                    handler.shutdown()
                except Exception as e:
                    logging.error(f"Error shutting down handler {type(handler).__name__}: {e}")
            
            logging.info("Graceful shutdown completed successfully")
            
        except Exception as e:
            logging.error(f"Error during graceful shutdown: {e}")
            logging.info("Falling back to emergency procedures")
            self._force_emergency_save()
        
        finally:
            # Clean up signal handlers
            self._cleanup_signal_handlers()
            
            # Exit the process
            logging.info("Exiting process")
            sys.exit(0)
    
    def _execute_emergency_shutdown(self, reason: str) -> None:
        """Execute emergency shutdown with timeout.
        
        Args:
            reason: Reason for emergency shutdown
        """
        try:
            logging.warning("Starting emergency shutdown procedures")
            
            # Set a timeout for emergency operations
            start_time = time.time()
            
            # Try graceful shutdown first, but with timeout
            for handler in self.shutdown_handlers:
                if time.time() - start_time > self.emergency_timeout:
                    logging.warning("Emergency shutdown timeout reached, forcing exit")
                    break
                
                try:
                    logging.debug(f"Emergency shutdown of handler: {type(handler).__name__}")
                    handler.emergency_save()
                except Exception as e:
                    logging.error(f"Error in emergency save for {type(handler).__name__}: {e}")
            
            # Execute callbacks with timeout
            for callback in self.shutdown_callbacks:
                if time.time() - start_time > self.emergency_timeout:
                    break
                
                try:
                    callback()
                except Exception as e:
                    logging.error(f"Error in emergency callback: {e}")
            
            logging.warning("Emergency shutdown completed")
            
        except Exception as e:
            logging.error(f"Error during emergency shutdown: {e}")
        
        finally:
            self._cleanup_signal_handlers()
            logging.warning("Force exiting process")
            sys.exit(1)
    
    def _force_emergency_save(self) -> None:
        """Force emergency save operations without timeout."""
        logging.critical("Forcing emergency save operations")
        
        for handler in self.shutdown_handlers:
            try:
                handler.emergency_save()
            except Exception as e:
                logging.error(f"Error in forced emergency save: {e}")
    
    def _cleanup_signal_handlers(self) -> None:
        """Clean up registered signal handlers."""
        try:
            # Restore original signal handlers
            for sig in self.registered_signals:
                if sig in self.original_handlers:
                    try:
                        signal.signal(sig, self.original_handlers[sig])
                        logging.debug(f"Restored original handler for signal {sig}")
                    except (OSError, ValueError) as e:
                        logging.warning(f"Could not restore handler for signal {sig}: {e}")
            
            # Clean up Windows console handler
            if self.platform.startswith('win') and self.win_handler_ref:
                try:
                    import win32api
                    win32api.SetConsoleCtrlHandler(self.win_handler_ref, False)
                    logging.debug("Removed Windows console control handler")
                except ImportError:
                    pass
                except Exception as e:
                    logging.warning(f"Error removing Windows console handler: {e}")
            
            self.registered_signals.clear()
            self.original_handlers.clear()
            
        except Exception as e:
            logging.error(f"Error cleaning up signal handlers: {e}")
    
    def is_shutdown_initiated(self) -> bool:
        """Check if shutdown has been initiated.
        
        Returns:
            True if shutdown is in progress
        """
        with self.shutdown_lock:
            return self.shutdown_initiated
    
    def set_emergency_timeout(self, timeout_seconds: int) -> None:
        """Set timeout for emergency shutdown operations.
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        if timeout_seconds < 1:
            raise ValueError("Emergency timeout must be at least 1 second")
        
        self.emergency_timeout = timeout_seconds
        logging.info(f"Set emergency shutdown timeout to {timeout_seconds} seconds")
    
    def manual_shutdown(self, reason: str = "Manual shutdown requested") -> None:
        """Manually trigger graceful shutdown.
        
        Args:
            reason: Reason for manual shutdown
        """
        logging.info(f"Manual shutdown triggered: {reason}")
        self._initiate_shutdown(reason)


# Global signal handler instance
_global_signal_handler: Optional[SignalHandler] = None


def get_signal_handler() -> SignalHandler:
    """Get the global signal handler instance.
    
    Returns:
        Global SignalHandler instance
    """
    global _global_signal_handler
    
    if _global_signal_handler is None:
        _global_signal_handler = SignalHandler()
    
    return _global_signal_handler


def setup_global_signal_handling() -> SignalHandler:
    """Setup global signal handling for the application.
    
    Returns:
        Configured SignalHandler instance
    """
    handler = get_signal_handler()
    handler.setup_signal_handlers()
    return handler


def register_shutdown_handler(handler: IShutdownHandler) -> None:
    """Register a shutdown handler with the global signal handler.
    
    Args:
        handler: Object implementing IShutdownHandler interface
    """
    get_signal_handler().register_handler(handler)


def register_shutdown_callback(callback: Callable[[], None]) -> None:
    """Register a shutdown callback with the global signal handler.
    
    Args:
        callback: Function to call during shutdown
    """
    get_signal_handler().register_callback(callback)