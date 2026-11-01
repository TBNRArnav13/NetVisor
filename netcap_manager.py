#!/usr/bin/env python3
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
"""
NetCap Manager - Integrated management for network capture with frontend support.

This script manages the folder structure and provides utilities for:
- Starting captures with proper folder separation
- Cleaning up JSON files after capture stops
- Managing log files and disk space
- Integration with the test2 frontend
"""

import sys
import os
import argparse
import logging
import signal
import time
from datetime import datetime
from typing import Optional

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from netcap_common.folder_manager import FolderManager
    from netcap_common.capture_manager import CaptureManager
    from netcap_common.interface_manager import InterfaceManager
    from netcap_common.platform_manager import PlatformManager
    from netcap_common import CaptureConfig
except ImportError as e:
    print(f"Error importing netcap_common: {e}")
    print("Please ensure the netcap_common package is properly installed.")
    sys.exit(1)


class NetCapManager:
    """Main manager for integrated network capture operations."""
    
    def __init__(self):
        """Initialize the NetCap manager."""
        self.folder_manager = FolderManager(".")
        self.platform_manager = PlatformManager()
        self.interface_manager = InterfaceManager(self.platform_manager)
        self.capture_manager = None
        self.logger = None
        
        # Setup signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n[INFO] Shutdown signal received, stopping capture...")
        if self.capture_manager and self.capture_manager.is_running():
            self.capture_manager.stop_capture()
        sys.exit(0)
    
    def setup_logging(self, level: str = "INFO") -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
    
    def start_capture(self, interface: str, duration: Optional[int] = None) -> None:
        """Start a network capture with integrated folder management.
        
        Args:
            interface: Network interface to capture from
            duration: Optional duration in seconds
        """
        try:
            # Validate interface
            is_valid, error_msg = self.interface_manager.validate_interface_for_capture(interface)
            if not is_valid:
                print(f"Error: {error_msg}")
                return
            
            # Create capture configuration
            config = CaptureConfig(
                interface=interface,
                output_directory=".",
                duration=duration,
                json_logging=True,
                batch_interval=5
            )
            
            # Initialize capture manager
            self.capture_manager = CaptureManager(interface, ".", config)
            
            print(f"[INFO] Starting capture on interface: {interface}")
            if duration:
                print(f"[INFO] Capture duration: {duration} seconds")
            else:
                print("[INFO] Continuous capture (press Ctrl+C to stop)")
            
            print(f"[INFO] JSON files (frontend): {self.folder_manager.captures_dir}")
            print(f"[INFO] PCAP/Log files (storage): {self.folder_manager.logs_dir}")
            
            # Start capture
            self.capture_manager.start_capture()
            
            # Wait for duration or until interrupted
            if duration:
                time.sleep(duration)
                self.capture_manager.stop_capture()
                print("[INFO] Capture completed")
            else:
                print("[INFO] Capture running... Press Ctrl+C to stop")
                try:
                    while self.capture_manager.is_running():
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n[INFO] Stopping capture...")
                    self.capture_manager.stop_capture()
            
        except Exception as e:
            print(f"Error during capture: {e}")
            if self.capture_manager:
                self.capture_manager.stop_capture()
    
    def cleanup_json_files(self) -> None:
        """Clean up JSON files from captures directory."""
        try:
            removed_files = self.folder_manager.cleanup_json_files()
            if removed_files:
                print(f"[INFO] Cleaned up {len(removed_files)} JSON files")
                for file_path in removed_files:
                    print(f"  Removed: {os.path.basename(file_path)}")
            else:
                print("[INFO] No JSON files to clean up")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def cleanup_old_logs(self, max_age_days: int = 30) -> None:
        """Clean up old log files."""
        try:
            removed_files = self.folder_manager.cleanup_old_logs(max_age_days)
            if removed_files:
                print(f"[INFO] Cleaned up {len(removed_files)} old log files")
                for file_path in removed_files:
                    print(f"  Removed: {os.path.basename(file_path)}")
            else:
                print(f"[INFO] No log files older than {max_age_days} days found")
        except Exception as e:
            print(f"Error during log cleanup: {e}")
    
    def show_status(self) -> None:
        """Show current status and disk usage."""
        try:
            # Get disk usage
            usage = self.folder_manager.get_disk_usage()
            
            print("NetCap Status")
            print("=" * 50)
            print(f"Captures directory: {usage['captures_dir']['path']}")
            print(f"  Files: {usage['captures_dir']['file_count']}")
            print(f"  Size: {usage['captures_dir']['size_mb']} MB")
            print()
            print(f"Logs directory: {usage['logs_dir']['path']}")
            print(f"  Files: {usage['logs_dir']['file_count']}")
            print(f"  Size: {usage['logs_dir']['size_mb']} MB")
            print()
            print(f"Total size: {usage['total_size_mb']} MB")
            
            # Show available JSON files for frontend
            json_files = self.folder_manager.get_json_files_for_frontend()
            if json_files:
                print(f"\nAvailable JSON files for frontend ({len(json_files)}):")
                for file_info in json_files[:5]:  # Show first 5
                    print(f"  {file_info['name']} ({file_info['size_mb']} MB)")
                if len(json_files) > 5:
                    print(f"  ... and {len(json_files) - 5} more")
            else:
                print("\nNo JSON files available for frontend")
                
        except Exception as e:
            print(f"Error getting status: {e}")
    
    def list_interfaces(self) -> None:
        """List available network interfaces."""
        try:
            interfaces = self.interface_manager.list_interfaces()
            
            print("Available Network Interfaces:")
            print("=" * 50)
            
            for i, iface in enumerate(interfaces, 1):
                status = "ACTIVE" if iface.is_active else "INACTIVE"
                ip_info = f" ({', '.join(iface.ip_addresses)})" if iface.ip_addresses else ""
                
                print(f"{i:2d}. {iface.name:<20} [{status}]{ip_info}")
                if iface.description and iface.description != iface.name:
                    print(f"    Description: {iface.description}")
                print()
                
        except Exception as e:
            print(f"Error listing interfaces: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NetCap Manager - Integrated network capture with frontend support",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Capture command
    capture_parser = subparsers.add_parser('capture', help='Start network capture')
    capture_parser.add_argument('--interface', '-i', required=True, help='Network interface to capture from')
    capture_parser.add_argument('--duration', '-d', type=int, help='Capture duration in seconds')
    
    # Cleanup commands
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup files')
    cleanup_parser.add_argument('--json', action='store_true', help='Clean up JSON files')
    cleanup_parser.add_argument('--logs', type=int, metavar='DAYS', help='Clean up log files older than DAYS')
    
    # Status command
    subparsers.add_parser('status', help='Show current status')
    
    # List interfaces command
    subparsers.add_parser('interfaces', help='List available network interfaces')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize manager
    manager = NetCapManager()
    manager.setup_logging()
    
    # Execute command
    if args.command == 'capture':
        manager.start_capture(args.interface, args.duration)
    elif args.command == 'cleanup':
        if args.json:
            manager.cleanup_json_files()
        if args.logs:
            manager.cleanup_old_logs(args.logs)
        if not args.json and not args.logs:
            print("Specify --json or --logs <days> for cleanup")
    elif args.command == 'status':
        manager.show_status()
    elif args.command == 'interfaces':
        manager.list_interfaces()


if __name__ == "__main__":
    main()