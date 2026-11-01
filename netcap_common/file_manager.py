"""
File Manager - Secure file operations, rotation, and naming conventions.

Handles secure file operations with rotation, safe naming conventions,
and configurable retention policies for network packet capture utilities.

Key Features:
- Automatic file rotation based on size and age thresholds
- Configurable retention policies for rotated files
- Disk space monitoring and warnings
- Safe filename generation preventing path traversal
- Cross-platform compatibility

Usage Example:
    # Basic file management
    file_manager = FileManager("/path/to/output")
    pcap_path, log_path = file_manager.setup_output_files("capture_session")
    
    # Configure rotation and cleanup
    rotation_manager = FileRotationManager(file_manager)
    config = FileRotationConfig(max_file_size_mb=100, keep_rotations=5)
    rotation_manager.configure_capture_rotation(pcap_path, log_path, config)
    
    # Perform maintenance
    results = rotation_manager.perform_maintenance()
"""

import os
import re
import shutil
import glob
from datetime import datetime, timezone
from typing import Tuple, List, Dict
from pathlib import Path
from .base_interfaces import IFileManager


class FileManager(IFileManager):
    """Concrete implementation of file management operations."""
    
    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        self._ensure_output_directory()
    
    def create_safe_filename(self, base: str, extension: str) -> str:
        """
        Create a safe filename preventing path traversal.
        
        Args:
            base: Base filename (will be sanitized)
            extension: File extension (without dot)
            
        Returns:
            Safe filename with UTC timestamp
            
        Raises:
            ValueError: If base name is empty or contains only invalid characters
        """
        if not base or not base.strip():
            raise ValueError("Base filename cannot be empty")
        
        # Remove path separators and dangerous characters
        safe_base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', base.strip())
        safe_base = re.sub(r'\.+', '_', safe_base)
        
        # Remove leading/trailing dots and spaces
        safe_base = safe_base.strip('. ')
        
        # Ensure we still have a valid name after sanitization
        if not safe_base:
            safe_base = "capture"
        
        # Limit length to prevent filesystem issues
        if len(safe_base) > 100:
            safe_base = safe_base[:100]
        
        # Add UTC timestamp
        timestamp = self._get_utc_timestamp()
        
        # Ensure extension doesn't have leading dot
        clean_extension = extension.lstrip('.')
        
        return f"{safe_base}_{timestamp}.{clean_extension}"
    
    def setup_output_files(self, base_name: str) -> Tuple[str, str]:
        """
        Setup output files and return PCAP and log file paths.
        
        Args:
            base_name: Base name for the files
            
        Returns:
            Tuple of (pcap_filepath, log_filepath)
            
        Raises:
            OSError: If unable to create output files
        """
        # Create safe filenames
        pcap_filename = self.create_safe_filename(base_name, "pcap")
        log_filename = self.create_safe_filename(base_name, "log")
        
        # Create full paths
        pcap_path = os.path.join(self.output_directory, pcap_filename)
        log_path = os.path.join(self.output_directory, log_filename)
        
        # Handle file conflicts
        pcap_path = self._resolve_file_conflict(pcap_path)
        log_path = self._resolve_file_conflict(log_path)
        
        # Create empty files to reserve them
        try:
            # Create PCAP file
            with open(pcap_path, 'wb') as f:
                pass  # Create empty file
            
            # Create log file
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"# Capture log started at {datetime.now(timezone.utc).isoformat()}\n")
            
        except (OSError, IOError) as e:
            raise OSError(f"Failed to create output files: {e}")
        
        return pcap_path, log_path
    
    def rotate_file_if_needed(self, filepath: str, max_size_mb: int) -> bool:
        """
        Rotate file if it exceeds maximum size.
        
        Args:
            filepath: Path to file to check
            max_size_mb: Maximum file size in MB
            
        Returns:
            True if file was rotated, False otherwise
            
        Raises:
            OSError: If rotation fails
        """
        if not os.path.exists(filepath):
            return False
        
        # Check file size
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        if file_size_mb >= max_size_mb:
            return self._perform_rotation(filepath)
        
        return False
    
    def force_rotate_file(self, filepath: str) -> bool:
        """
        Force rotation of a file regardless of size.
        
        Args:
            filepath: Path to file to rotate
            
        Returns:
            True if file was rotated, False if file doesn't exist
            
        Raises:
            OSError: If rotation fails
        """
        if not os.path.exists(filepath):
            return False
        
        return self._perform_rotation(filepath)
    
    def _perform_rotation(self, filepath: str) -> bool:
        """
        Perform the actual file rotation.
        
        Args:
            filepath: Path to file to rotate
            
        Returns:
            True if rotation was successful
            
        Raises:
            OSError: If rotation fails
        """
        # Generate rotation filename
        base_path = os.path.splitext(filepath)[0]
        extension = os.path.splitext(filepath)[1]
        timestamp = self._get_utc_timestamp()
        
        # Find next available rotation number
        rotation_counter = 1
        while True:
            rotated_path = f"{base_path}_rotated_{timestamp}_{rotation_counter:03d}{extension}"
            if not os.path.exists(rotated_path):
                break
            rotation_counter += 1
            if rotation_counter > 999:
                raise OSError(f"Too many rotation files for {filepath}")
        
        try:
            # Move current file to rotated name
            shutil.move(filepath, rotated_path)
            
            # Create new empty file
            if extension.lower() == '.pcap':
                with open(filepath, 'wb') as f:
                    pass
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Capture log rotated at {datetime.now(timezone.utc).isoformat()}\n")
            
            return True
            
        except (OSError, IOError) as e:
            raise OSError(f"Failed to rotate file {filepath}: {e}")
    
    def cleanup_old_rotations(self, base_path: str, keep_count: int) -> List[str]:
        """
        Clean up old rotated files keeping only specified count.
        
        Args:
            base_path: Base path pattern for rotated files (without extension)
            keep_count: Number of rotated files to keep (0 = keep all)
            
        Returns:
            List of files that were removed
        """
        removed_files = []
        
        if keep_count <= 0:
            return removed_files
        
        # Find all rotated files for both .pcap and .log extensions
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else self.output_directory
        base_name = os.path.basename(base_path)
        
        for extension in ['.pcap', '.log']:
            # Pattern to match rotated files
            pattern = os.path.join(base_dir, f"{base_name}_rotated_*{extension}")
            rotated_files = glob.glob(pattern)
            
            if len(rotated_files) <= keep_count:
                continue
            
            # Sort by modification time (oldest first)
            rotated_files.sort(key=lambda x: os.path.getmtime(x))
            
            # Remove oldest files
            files_to_remove = rotated_files[:-keep_count]
            
            for file_path in files_to_remove:
                try:
                    os.remove(file_path)
                    removed_files.append(file_path)
                except OSError:
                    # Continue cleanup even if some files fail to delete
                    pass
        
        return removed_files
    
    def get_disk_space_info(self) -> Tuple[int, int, int]:
        """
        Get disk space information for output directory.
        
        Returns:
            Tuple of (total_bytes, used_bytes, free_bytes)
        """
        try:
            statvfs = os.statvfs(self.output_directory)
            total = statvfs.f_frsize * statvfs.f_blocks
            free = statvfs.f_frsize * statvfs.f_available
            used = total - free
            return total, used, free
        except (OSError, AttributeError):
            # Fallback for Windows or other systems
            try:
                total, used, free = shutil.disk_usage(self.output_directory)
                return total, used, free
            except OSError:
                return 0, 0, 0
    
    def check_disk_space_warning(self, min_free_mb: int = 100) -> bool:
        """
        Check if available disk space is below warning threshold.
        
        Args:
            min_free_mb: Minimum free space in MB before warning
            
        Returns:
            True if disk space is low
        """
        _, _, free_bytes = self.get_disk_space_info()
        free_mb = free_bytes / (1024 * 1024)
        return free_mb < min_free_mb
    
    def check_disk_space_critical(self, min_free_mb: int = 50) -> bool:
        """
        Check if available disk space is critically low.
        
        Args:
            min_free_mb: Critical minimum free space in MB
            
        Returns:
            True if disk space is critically low
        """
        _, _, free_bytes = self.get_disk_space_info()
        free_mb = free_bytes / (1024 * 1024)
        return free_mb < min_free_mb
    
    def get_disk_space_warning_message(self) -> str:
        """
        Get formatted disk space warning message.
        
        Returns:
            Warning message with current disk space information
        """
        total, used, free = self.get_disk_space_info()
        
        if total == 0:
            return "Warning: Unable to determine disk space information"
        
        total_gb = total / (1024 * 1024 * 1024)
        used_gb = used / (1024 * 1024 * 1024)
        free_gb = free / (1024 * 1024 * 1024)
        used_percent = (used / total) * 100 if total > 0 else 0
        
        return (f"Disk space warning for {self.output_directory}:\n"
                f"  Total: {total_gb:.2f} GB\n"
                f"  Used: {used_gb:.2f} GB ({used_percent:.1f}%)\n"
                f"  Free: {free_gb:.2f} GB\n"
                f"  Consider cleaning up old files or increasing storage capacity.")
    
    def auto_cleanup_by_age(self, max_age_days: int) -> List[str]:
        """
        Automatically clean up files older than specified age.
        
        Args:
            max_age_days: Maximum age in days for files to keep
            
        Returns:
            List of files that were removed
        """
        if max_age_days <= 0:
            return []
        
        removed_files = []
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        
        try:
            for filename in os.listdir(self.output_directory):
                filepath = os.path.join(self.output_directory, filename)
                
                # Only process capture files (pcap and log)
                if not (filename.endswith('.pcap') or filename.endswith('.log')):
                    continue
                
                # Skip if it's not a regular file
                if not os.path.isfile(filepath):
                    continue
                
                # Check file age
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_time:
                    try:
                        os.remove(filepath)
                        removed_files.append(filepath)
                    except OSError:
                        # Continue cleanup even if some files fail
                        pass
                        
        except OSError:
            # Directory access issues
            pass
        
        return removed_files
    
    def auto_cleanup_by_size(self, max_total_mb: int) -> List[str]:
        """
        Automatically clean up oldest files to stay under size limit.
        
        Args:
            max_total_mb: Maximum total size in MB for all capture files
            
        Returns:
            List of files that were removed
        """
        if max_total_mb <= 0:
            return []
        
        removed_files = []
        max_bytes = max_total_mb * 1024 * 1024
        
        try:
            # Get all capture files with their sizes and modification times
            files_info = []
            total_size = 0
            
            for filename in os.listdir(self.output_directory):
                filepath = os.path.join(self.output_directory, filename)
                
                # Only process capture files
                if not (filename.endswith('.pcap') or filename.endswith('.log')):
                    continue
                
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    mtime = os.path.getmtime(filepath)
                    files_info.append((filepath, size, mtime))
                    total_size += size
            
            # If we're under the limit, nothing to do
            if total_size <= max_bytes:
                return []
            
            # Sort by modification time (oldest first)
            files_info.sort(key=lambda x: x[2])
            
            # Remove oldest files until we're under the limit
            for filepath, size, _ in files_info:
                if total_size <= max_bytes:
                    break
                
                try:
                    os.remove(filepath)
                    removed_files.append(filepath)
                    total_size -= size
                except OSError:
                    # Continue cleanup even if some files fail
                    pass
                    
        except OSError:
            # Directory access issues
            pass
        
        return removed_files
    
    def _ensure_output_directory(self):
        """
        Ensure output directory exists and is writable.
        
        Raises:
            OSError: If directory cannot be created or is not writable
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.output_directory, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(self.output_directory, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except (OSError, IOError):
                raise OSError(f"Output directory is not writable: {self.output_directory}")
                
        except OSError as e:
            raise OSError(f"Cannot create or access output directory {self.output_directory}: {e}")
    
    def _get_utc_timestamp(self) -> str:
        """
        Get UTC timestamp in ISO8601 format for filename use.
        
        Returns:
            UTC timestamp string in format: YYYYMMDD_HHMMSS
        """
        utc_now = datetime.now(timezone.utc)
        return utc_now.strftime("%Y%m%d_%H%M%S")
    
    def _resolve_file_conflict(self, filepath: str) -> str:
        """
        Resolve file naming conflicts by adding a counter.
        
        Args:
            filepath: Original file path
            
        Returns:
            Non-conflicting file path
        """
        if not os.path.exists(filepath):
            return filepath
        
        base_path = os.path.splitext(filepath)[0]
        extension = os.path.splitext(filepath)[1]
        
        counter = 1
        while True:
            new_path = f"{base_path}_{counter:03d}{extension}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
            
            # Prevent infinite loop
            if counter > 999:
                raise OSError(f"Too many file conflicts for {filepath}")


class FileRotationConfig:
    """
    Configuration class for file rotation and cleanup policies.
    """
    
    def __init__(self, max_file_size_mb: int = 100, keep_rotations: int = 5,
                 max_age_days: int = None, max_total_mb: int = None,
                 max_age_hours: int = None):
        """
        Initialize rotation configuration.
        
        Args:
            max_file_size_mb: Maximum file size in MB before rotation
            keep_rotations: Number of rotated files to keep
            max_age_days: Maximum age in days for rotated files
            max_total_mb: Maximum total size in MB for all rotated files
            max_age_hours: Maximum age in hours before rotation
        """
        self.max_file_size_mb = max_file_size_mb
        self.keep_rotations = keep_rotations
        self.max_age_days = max_age_days
        self.max_total_mb = max_total_mb
        self.max_age_hours = max_age_hours
    
    def to_dict(self) -> Dict:
        """Convert configuration to dictionary."""
        return {
            'max_file_size_mb': self.max_file_size_mb,
            'keep_rotations': self.keep_rotations,
            'max_age_days': self.max_age_days,
            'max_total_mb': self.max_total_mb,
            'max_age_hours': self.max_age_hours
        }


class FileRotationManager:
    """
    Manages automatic file rotation based on configurable policies.
    """
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.rotation_policies = {}
        self.cleanup_policies = {}
    
    def add_rotation_policy(self, filepath: str, max_size_mb: int, 
                          max_age_hours: int = None) -> None:
        """
        Add rotation policy for a specific file.
        
        Args:
            filepath: Path to file to monitor
            max_size_mb: Maximum size in MB before rotation
            max_age_hours: Maximum age in hours before rotation (optional)
        """
        self.rotation_policies[filepath] = {
            'max_size_mb': max_size_mb,
            'max_age_hours': max_age_hours,
            'last_check': datetime.now()
        }
    
    def add_cleanup_policy(self, base_path: str, keep_rotations: int = 5,
                          max_age_days: int = None, max_total_mb: int = None) -> None:
        """
        Add cleanup policy for rotated files.
        
        Args:
            base_path: Base path for rotated files
            keep_rotations: Number of rotated files to keep
            max_age_days: Maximum age in days for rotated files
            max_total_mb: Maximum total size in MB for all rotated files
        """
        self.cleanup_policies[base_path] = {
            'keep_rotations': keep_rotations,
            'max_age_days': max_age_days,
            'max_total_mb': max_total_mb,
            'last_cleanup': datetime.now()
        }
    
    def configure_capture_rotation(self, pcap_filepath: str, log_filepath: str, 
                                 config: FileRotationConfig) -> None:
        """
        Configure rotation and cleanup for a capture session's files.
        
        Args:
            pcap_filepath: Path to PCAP file
            log_filepath: Path to log file
            config: Rotation configuration
        """
        # Add rotation policies for both files
        self.add_rotation_policy(pcap_filepath, config.max_file_size_mb, config.max_age_hours)
        self.add_rotation_policy(log_filepath, config.max_file_size_mb, config.max_age_hours)
        
        # Add cleanup policies (use base path without extension)
        pcap_base = os.path.splitext(pcap_filepath)[0]
        log_base = os.path.splitext(log_filepath)[0]
        
        self.add_cleanup_policy(pcap_base, config.keep_rotations, 
                              config.max_age_days, config.max_total_mb)
        self.add_cleanup_policy(log_base, config.keep_rotations, 
                              config.max_age_days, config.max_total_mb)
    
    def check_and_rotate_files(self) -> List[str]:
        """
        Check all monitored files and rotate if needed.
        
        Returns:
            List of files that were rotated
        """
        rotated_files = []
        
        for filepath, policy in self.rotation_policies.items():
            if not os.path.exists(filepath):
                continue
            
            should_rotate = False
            rotation_reason = ""
            
            # Check size-based rotation
            if policy['max_size_mb']:
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                if file_size_mb >= policy['max_size_mb']:
                    should_rotate = True
                    rotation_reason = f"size ({file_size_mb:.2f}MB >= {policy['max_size_mb']}MB)"
            
            # Check age-based rotation
            if policy['max_age_hours']:
                file_age_hours = (datetime.now().timestamp() - 
                                os.path.getmtime(filepath)) / 3600
                if file_age_hours >= policy['max_age_hours']:
                    should_rotate = True
                    if rotation_reason:
                        rotation_reason += f" and age ({file_age_hours:.1f}h >= {policy['max_age_hours']}h)"
                    else:
                        rotation_reason = f"age ({file_age_hours:.1f}h >= {policy['max_age_hours']}h)"
            
            if should_rotate:
                try:
                    if self.file_manager.force_rotate_file(filepath):
                        rotated_files.append(filepath)
                        policy['last_rotation'] = datetime.now()
                        policy['rotation_reason'] = rotation_reason
                except OSError:
                    # Continue with other files even if one fails
                    pass
        
        return rotated_files
    
    def cleanup_rotated_files(self) -> Dict[str, List[str]]:
        """
        Clean up rotated files according to policies.
        
        Returns:
            Dictionary mapping base paths to lists of removed files
        """
        cleanup_results = {}
        
        for base_path, policy in self.cleanup_policies.items():
            removed_files = []
            
            # Apply rotation count limit
            if policy['keep_rotations'] > 0:
                count_removed = self.file_manager.cleanup_old_rotations(
                    base_path, policy['keep_rotations']
                )
                removed_files.extend(count_removed)
            
            # Apply age-based cleanup
            if policy['max_age_days']:
                age_removed = self._cleanup_by_age(base_path, policy['max_age_days'])
                removed_files.extend(age_removed)
            
            # Apply size-based cleanup
            if policy['max_total_mb']:
                size_removed = self._cleanup_by_total_size(base_path, policy['max_total_mb'])
                removed_files.extend(size_removed)
            
            cleanup_results[base_path] = removed_files
            self.cleanup_policies[base_path]['last_cleanup'] = datetime.now()
        
        return cleanup_results
    
    def _cleanup_by_age(self, base_path: str, max_age_days: int) -> List[str]:
        """
        Clean up rotated files older than specified age.
        
        Args:
            base_path: Base path for rotated files
            max_age_days: Maximum age in days
            
        Returns:
            List of files that were removed
        """
        removed_files = []
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else self.file_manager.output_directory
        base_name = os.path.basename(base_path)
        
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        
        for extension in ['.pcap', '.log']:
            pattern = os.path.join(base_dir, f"{base_name}_rotated_*{extension}")
            
            for rotated_file in glob.glob(pattern):
                if os.path.getmtime(rotated_file) < cutoff_time:
                    try:
                        os.remove(rotated_file)
                        removed_files.append(rotated_file)
                    except OSError:
                        pass
        
        return removed_files
    
    def _cleanup_by_total_size(self, base_path: str, max_total_mb: int) -> List[str]:
        """
        Clean up rotated files to stay under total size limit.
        
        Args:
            base_path: Base path for rotated files
            max_total_mb: Maximum total size in MB
            
        Returns:
            List of files that were removed
        """
        removed_files = []
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else self.file_manager.output_directory
        base_name = os.path.basename(base_path)
        max_bytes = max_total_mb * 1024 * 1024
        
        # Collect all rotated files with their sizes
        files_info = []
        total_size = 0
        
        for extension in ['.pcap', '.log']:
            pattern = os.path.join(base_dir, f"{base_name}_rotated_*{extension}")
            
            for rotated_file in glob.glob(pattern):
                if os.path.isfile(rotated_file):
                    size = os.path.getsize(rotated_file)
                    mtime = os.path.getmtime(rotated_file)
                    files_info.append((rotated_file, size, mtime))
                    total_size += size
        
        # If we're under the limit, nothing to do
        if total_size <= max_bytes:
            return removed_files
        
        # Sort by modification time (oldest first)
        files_info.sort(key=lambda x: x[2])
        
        # Remove oldest files until we're under the limit
        for filepath, size, _ in files_info:
            if total_size <= max_bytes:
                break
            
            try:
                os.remove(filepath)
                removed_files.append(filepath)
                total_size -= size
            except OSError:
                pass
        
        return removed_files
    
    def get_rotation_status(self) -> Dict[str, Dict]:
        """
        Get status information for all monitored files.
        
        Returns:
            Dictionary with file status information
        """
        status = {}
        
        for filepath, policy in self.rotation_policies.items():
            if os.path.exists(filepath):
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                file_age_hours = (datetime.now().timestamp() - 
                                os.path.getmtime(filepath)) / 3600
                
                needs_rotation = False
                rotation_reasons = []
                
                if policy['max_size_mb'] and file_size_mb >= policy['max_size_mb']:
                    needs_rotation = True
                    rotation_reasons.append(f"size ({file_size_mb:.2f}MB >= {policy['max_size_mb']}MB)")
                
                if policy['max_age_hours'] and file_age_hours >= policy['max_age_hours']:
                    needs_rotation = True
                    rotation_reasons.append(f"age ({file_age_hours:.1f}h >= {policy['max_age_hours']}h)")
                
                status[filepath] = {
                    'exists': True,
                    'size_mb': file_size_mb,
                    'age_hours': file_age_hours,
                    'max_size_mb': policy['max_size_mb'],
                    'max_age_hours': policy['max_age_hours'],
                    'needs_rotation': needs_rotation,
                    'rotation_reasons': rotation_reasons,
                    'last_rotation': policy.get('last_rotation'),
                    'last_rotation_reason': policy.get('rotation_reason')
                }
            else:
                status[filepath] = {'exists': False}
        
        return status
    
    def get_cleanup_status(self) -> Dict[str, Dict]:
        """
        Get status information for all cleanup policies.
        
        Returns:
            Dictionary with cleanup policy status information
        """
        status = {}
        
        for base_path, policy in self.cleanup_policies.items():
            base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else self.file_manager.output_directory
            base_name = os.path.basename(base_path)
            
            # Count rotated files
            rotated_count = 0
            total_size_mb = 0
            oldest_file_age_days = 0
            
            for extension in ['.pcap', '.log']:
                pattern = os.path.join(base_dir, f"{base_name}_rotated_*{extension}")
                rotated_files = glob.glob(pattern)
                rotated_count += len(rotated_files)
                
                for rotated_file in rotated_files:
                    if os.path.isfile(rotated_file):
                        total_size_mb += os.path.getsize(rotated_file) / (1024 * 1024)
                        file_age_days = (datetime.now().timestamp() - os.path.getmtime(rotated_file)) / (24 * 3600)
                        oldest_file_age_days = max(oldest_file_age_days, file_age_days)
            
            needs_cleanup = []
            if policy['keep_rotations'] > 0 and rotated_count > policy['keep_rotations']:
                needs_cleanup.append(f"count ({rotated_count} > {policy['keep_rotations']})")
            
            if policy['max_age_days'] and oldest_file_age_days > policy['max_age_days']:
                needs_cleanup.append(f"age ({oldest_file_age_days:.1f}d > {policy['max_age_days']}d)")
            
            if policy['max_total_mb'] and total_size_mb > policy['max_total_mb']:
                needs_cleanup.append(f"size ({total_size_mb:.2f}MB > {policy['max_total_mb']}MB)")
            
            status[base_path] = {
                'rotated_file_count': rotated_count,
                'total_size_mb': total_size_mb,
                'oldest_file_age_days': oldest_file_age_days,
                'keep_rotations': policy['keep_rotations'],
                'max_age_days': policy['max_age_days'],
                'max_total_mb': policy['max_total_mb'],
                'needs_cleanup': len(needs_cleanup) > 0,
                'cleanup_reasons': needs_cleanup,
                'last_cleanup': policy.get('last_cleanup')
            }
        
        return status
    
    def perform_maintenance(self) -> Dict[str, any]:
        """
        Perform complete maintenance cycle: rotation and cleanup.
        
        Returns:
            Dictionary with maintenance results
        """
        results = {
            'rotated_files': [],
            'cleanup_results': {},
            'disk_space_warning': False,
            'disk_space_critical': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Check disk space
        results['disk_space_warning'] = self.file_manager.check_disk_space_warning()
        results['disk_space_critical'] = self.file_manager.check_disk_space_critical()
        
        # Perform rotations
        results['rotated_files'] = self.check_and_rotate_files()
        
        # Perform cleanup
        results['cleanup_results'] = self.cleanup_rotated_files()
        
        return results