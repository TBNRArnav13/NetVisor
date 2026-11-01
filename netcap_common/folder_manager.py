"""
Folder Manager - Manages separate folders for JSON (frontend) and logs (storage).

This module handles the separation of capture files:
- captures/ folder: Contains JSON files for frontend consumption
- logs/ folder: Contains PCAP and log files for storage
- Automatic cleanup of JSON files when capture stops
"""

import os
import shutil
import glob
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class FolderManager:
    """Manages folder structure for netcap with frontend integration."""
    
    def __init__(self, base_output_dir: str = "."):
        """Initialize folder manager.
        
        Args:
            base_output_dir: Base directory for all outputs
        """
        self.base_output_dir = Path(base_output_dir)
        self.captures_dir = self.base_output_dir / "captures"
        self.logs_dir = self.base_output_dir / "logs"
        
        # Ensure directories exist
        self._ensure_directories()
        
        self.logger = logging.getLogger(__name__)
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        try:
            self.captures_dir.mkdir(parents=True, exist_ok=True)
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Create .gitkeep files to ensure directories are tracked
            (self.captures_dir / ".gitkeep").touch(exist_ok=True)
            (self.logs_dir / ".gitkeep").touch(exist_ok=True)
            
        except Exception as e:
            raise OSError(f"Failed to create directories: {e}")
    
    def get_capture_paths(self, session_name: str) -> Dict[str, str]:
        """Get file paths for a capture session.
        
        Args:
            session_name: Name for the capture session
            
        Returns:
            Dictionary with paths for different file types
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_filename(session_name)
        
        return {
            'json_file': str(self.captures_dir / f"{safe_name}_{timestamp}.json"),
            'pcap_file': str(self.logs_dir / f"{safe_name}_{timestamp}.pcap"),
            'log_file': str(self.logs_dir / f"{safe_name}_{timestamp}.log")
        }
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for cross-platform compatibility.
        
        Args:
            name: Original filename
            
        Returns:
            Sanitized filename
        """
        import re
        # Remove dangerous characters
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name.strip())
        # Remove leading/trailing dots and spaces
        safe_name = safe_name.strip('. ')
        # Ensure we have a valid name
        if not safe_name:
            safe_name = "capture"
        # Limit length
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        return safe_name
    
    def cleanup_json_files(self, session_id: Optional[str] = None) -> List[str]:
        """Clean up JSON files from captures directory.
        
        Args:
            session_id: Optional session ID to clean specific files
            
        Returns:
            List of files that were removed
        """
        removed_files = []
        
        try:
            if session_id:
                # Clean specific session files
                pattern = f"*{session_id}*.json"
            else:
                # Clean all JSON files
                pattern = "*.json"
            
            json_files = list(self.captures_dir.glob(pattern))
            
            for json_file in json_files:
                try:
                    json_file.unlink()
                    removed_files.append(str(json_file))
                    self.logger.info(f"Removed JSON file: {json_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {json_file}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error during JSON cleanup: {e}")
        
        return removed_files
    
    def move_file_to_logs(self, source_path: str, target_name: Optional[str] = None) -> str:
        """Move a file to the logs directory.
        
        Args:
            source_path: Path to source file
            target_name: Optional target filename
            
        Returns:
            Path to moved file
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if target_name:
            target = self.logs_dir / target_name
        else:
            target = self.logs_dir / source.name
        
        # Handle name conflicts
        counter = 1
        original_target = target
        while target.exists():
            stem = original_target.stem
            suffix = original_target.suffix
            target = self.logs_dir / f"{stem}_{counter:03d}{suffix}"
            counter += 1
        
        shutil.move(str(source), str(target))
        self.logger.info(f"Moved file from {source} to {target}")
        return str(target)
    
    def get_json_files_for_frontend(self) -> List[Dict[str, any]]:
        """Get list of JSON files available for frontend.
        
        Returns:
            List of dictionaries with file information
        """
        json_files = []
        
        try:
            for json_file in self.captures_dir.glob("*.json"):
                if json_file.name == ".gitkeep":
                    continue
                
                try:
                    stat = json_file.stat()
                    json_files.append({
                        'name': json_file.name,
                        'path': str(json_file),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'size_mb': round(stat.st_size / (1024 * 1024), 2)
                    })
                except Exception as e:
                    self.logger.warning(f"Error reading file info for {json_file}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error listing JSON files: {e}")
        
        # Sort by modification time (newest first)
        json_files.sort(key=lambda x: x['modified'], reverse=True)
        return json_files
    
    def cleanup_old_logs(self, max_age_days: int = 30) -> List[str]:
        """Clean up old log files.
        
        Args:
            max_age_days: Maximum age in days for log files
            
        Returns:
            List of files that were removed
        """
        removed_files = []
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        
        try:
            for log_file in self.logs_dir.glob("*"):
                if log_file.name == ".gitkeep":
                    continue
                
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        removed_files.append(str(log_file))
                        self.logger.info(f"Removed old log file: {log_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {log_file}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error during log cleanup: {e}")
        
        return removed_files
    
    def get_disk_usage(self) -> Dict[str, any]:
        """Get disk usage information for both directories.
        
        Returns:
            Dictionary with disk usage information
        """
        def get_dir_size(directory: Path) -> int:
            """Get total size of directory."""
            total = 0
            try:
                for file_path in directory.rglob("*"):
                    if file_path.is_file():
                        total += file_path.stat().st_size
            except Exception:
                pass
            return total
        
        captures_size = get_dir_size(self.captures_dir)
        logs_size = get_dir_size(self.logs_dir)
        
        return {
            'captures_dir': {
                'path': str(self.captures_dir),
                'size_bytes': captures_size,
                'size_mb': round(captures_size / (1024 * 1024), 2),
                'file_count': len(list(self.captures_dir.glob("*"))) - 1  # Exclude .gitkeep
            },
            'logs_dir': {
                'path': str(self.logs_dir),
                'size_bytes': logs_size,
                'size_mb': round(logs_size / (1024 * 1024), 2),
                'file_count': len(list(self.logs_dir.glob("*"))) - 1  # Exclude .gitkeep
            },
            'total_size_mb': round((captures_size + logs_size) / (1024 * 1024), 2)
        }