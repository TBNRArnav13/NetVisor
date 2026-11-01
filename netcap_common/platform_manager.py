"""
Platform Manager for cross-platform network capture utilities.

Handles platform detection, privilege validation, and platform-specific configurations.
"""

import platform
import os
import sys
import subprocess
from typing import Dict, Optional, Tuple


class PlatformManager:
    """Manages platform detection and privilege validation across Windows and Linux."""
    
    SUPPORTED_PLATFORMS = {
        'Windows': ['10', '11', 'Server'],
        'Linux': ['Ubuntu', 'Debian']
    }
    
    def __init__(self):
        self.platform = self.detect_platform()
        self.is_windows = self.platform == 'Windows'
        self.is_linux = self.platform == 'Linux'
    
    def detect_platform(self) -> str:
        """
        Detect the current platform and validate compatibility.
        
        Returns:
            str: Platform name ('Windows' or 'Linux')
            
        Raises:
            RuntimeError: If platform is not supported
        """
        system = platform.system()
        
        if system == 'Windows':
            # Validate Windows version
            version = platform.version()
            release = platform.release()
            
            # Check for Windows 10/11/Server
            if release in ['10', '11'] or 'Server' in platform.platform():
                return 'Windows'
            else:
                raise RuntimeError(
                    f"Unsupported Windows version: {release}. "
                    f"Supported versions: Windows 10, 11, Server"
                )
                
        elif system == 'Linux':
            # Check for supported Linux distributions
            try:
                # Try to read /etc/os-release for distribution info
                with open('/etc/os-release', 'r') as f:
                    os_release = f.read().lower()
                    
                if 'ubuntu' in os_release or 'debian' in os_release:
                    return 'Linux'
                else:
                    # Still allow other Linux distributions but warn
                    print("Warning: Untested Linux distribution detected. "
                          "Officially supported: Ubuntu, Debian")
                    return 'Linux'
                    
            except FileNotFoundError:
                # Fallback for systems without /etc/os-release
                print("Warning: Could not determine Linux distribution. "
                      "Officially supported: Ubuntu, Debian")
                return 'Linux'
                
        else:
            raise RuntimeError(
                f"Unsupported platform: {system}. "
                f"Supported platforms: Windows (10/11/Server), Linux (Ubuntu/Debian)"
            )
    
    def check_privileges(self) -> bool:
        """
        Check if the current process has sufficient privileges for packet capture.
        
        Returns:
            bool: True if privileges are sufficient, False otherwise
        """
        if self.is_windows:
            return self._check_windows_admin()
        elif self.is_linux:
            return self._check_linux_root()
        else:
            return False
    
    def _check_windows_admin(self) -> bool:
        """Check for Windows Administrator privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            # Fallback method or if ctypes is not available
            return False
    
    def _check_linux_root(self) -> bool:
        """Check for Linux root privileges."""
        return os.geteuid() == 0
    
    def get_privilege_error_message(self) -> str:
        """
        Get platform-specific error message for insufficient privileges.
        
        Returns:
            str: Detailed error message with instructions
        """
        if self.is_windows:
            return (
                "Administrator privileges required for packet capture on Windows.\n\n"
                "To run with Administrator privileges:\n"
                "1. Right-click on Command Prompt or PowerShell\n"
                "2. Select 'Run as administrator'\n"
                "3. Navigate to the script directory and run again\n\n"
                "Alternatively, you can:\n"
                "- Right-click on the Python script and select 'Run as administrator'\n"
                "- Use 'runas' command: runas /user:Administrator python script.py\n\n"
                "Note: Administrator privileges are required to access network interfaces "
                "and perform packet capture operations."
            )
        elif self.is_linux:
            return (
                "Root privileges required for packet capture on Linux.\n\n"
                "To run with root privileges:\n"
                "1. Use sudo: sudo python3 script.py\n"
                "2. Or switch to root user: su - root\n\n"
                "Alternative approaches:\n"
                "- Add user to wireshark group (if available): sudo usermod -a -G wireshark $USER\n"
                "- Set capabilities on Python binary (advanced): sudo setcap cap_net_raw+ep /usr/bin/python3\n\n"
                "Note: Root privileges are required to access raw network sockets "
                "and perform packet capture operations."
            )
        else:
            return "Insufficient privileges for packet capture operations."
    
    def get_installation_instructions(self) -> str:
        """
        Get platform-specific installation instructions for dependencies.
        
        Returns:
            str: Detailed installation instructions
        """
        if self.is_windows:
            return self._get_windows_installation_instructions()
        elif self.is_linux:
            return self._get_linux_installation_instructions()
        else:
            return "Platform-specific installation instructions not available."
    
    def _get_windows_installation_instructions(self) -> str:
        """Get Windows-specific installation instructions."""
        return (
            "Windows Installation Instructions:\n"
            "================================\n\n"
            "1. Install Python 3.8+ (if not already installed):\n"
            "   - Download from https://www.python.org/downloads/\n"
            "   - Ensure 'Add Python to PATH' is checked during installation\n\n"
            "2. Install Wireshark with TShark:\n"
            "   - Download from https://www.wireshark.org/download.html\n"
            "   - During installation, ensure 'TShark' component is selected\n"
            "   - This will also install Npcap (required for packet capture)\n\n"
            "3. Alternative - Install TShark separately:\n"
            "   - Download TShark from https://www.wireshark.org/download.html\n"
            "   - Install Npcap from https://nmap.org/npcap/\n\n"
            "4. Install Python dependencies:\n"
            "   pip install pyshark\n\n"
            "5. Verify installation:\n"
            "   - Open Command Prompt as Administrator\n"
            "   - Run: tshark --version\n"
            "   - Should display TShark version information\n\n"
            "Troubleshooting:\n"
            "- If 'tshark' is not recognized, add Wireshark installation directory to PATH\n"
            "- Default path: C:\\Program Files\\Wireshark\n"
            "- Ensure Npcap is installed and WinPcap is uninstalled (conflicts possible)"
        )
    
    def _get_linux_installation_instructions(self) -> str:
        """Get Linux-specific installation instructions."""
        return (
            "Linux Installation Instructions:\n"
            "===============================\n\n"
            "Ubuntu/Debian:\n"
            "1. Update package list:\n"
            "   sudo apt update\n\n"
            "2. Install TShark and dependencies:\n"
            "   sudo apt install tshark\n"
            "   sudo apt install libpcap-dev\n\n"
            "3. Install Python 3.8+ (if not available):\n"
            "   sudo apt install python3 python3-pip\n\n"
            "4. Install Python dependencies:\n"
            "   pip3 install pyshark\n\n"
            "5. Configure TShark permissions (optional):\n"
            "   sudo dpkg-reconfigure wireshark-common\n"
            "   # Select 'Yes' to allow non-superusers to capture packets\n"
            "   sudo usermod -a -G wireshark $USER\n"
            "   # Log out and back in for group changes to take effect\n\n"
            "CentOS/RHEL/Fedora:\n"
            "1. Install TShark:\n"
            "   sudo yum install wireshark-cli  # CentOS/RHEL\n"
            "   sudo dnf install wireshark-cli  # Fedora\n\n"
            "2. Install development tools:\n"
            "   sudo yum groupinstall 'Development Tools'\n"
            "   sudo yum install libpcap-devel\n\n"
            "3. Install Python dependencies:\n"
            "   pip3 install pyshark\n\n"
            "Verification:\n"
            "- Run: tshark --version\n"
            "- Should display TShark version information\n"
            "- Test packet capture: sudo tshark -i any -c 5"
        )
    
    def normalize_interface_name(self, interface: str) -> str:
        """
        Normalize interface name for cross-platform compatibility.
        
        Args:
            interface: Raw interface name
            
        Returns:
            str: Normalized interface name safe for filenames
        """
        if not interface:
            return "unknown"
        
        # Remove or replace characters that are problematic in filenames
        normalized = interface.replace('\\', '_')
        normalized = normalized.replace('/', '_')
        normalized = normalized.replace(':', '_')
        normalized = normalized.replace('*', '_')
        normalized = normalized.replace('?', '_')
        normalized = normalized.replace('"', '_')
        normalized = normalized.replace('<', '_')
        normalized = normalized.replace('>', '_')
        normalized = normalized.replace('|', '_')
        normalized = normalized.replace(' ', '_')
        
        # Handle Windows-specific interface naming
        if self.is_windows:
            # Windows interfaces often have long GUIDs, shorten them
            if len(normalized) > 50:
                # Keep first part and add hash of full name
                import hashlib
                hash_suffix = hashlib.md5(interface.encode()).hexdigest()[:8]
                normalized = f"{normalized[:30]}_{hash_suffix}"
        
        return normalized.lower()
    
    def validate_tshark_installation(self) -> Tuple[bool, str, Optional[str]]:
        """
        Validate TShark installation and get version information.
        
        Returns:
            Tuple of (is_installed, error_message, version_string)
        """
        try:
            # Try to run tshark --version
            result = subprocess.run(
                ['tshark', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # TShark is installed and working
                version_output = result.stdout.strip()
                version_line = version_output.split('\n')[0] if version_output else "Unknown version"
                return True, "", version_line
            else:
                # TShark command failed
                error_msg = result.stderr.strip() if result.stderr else "TShark command failed"
                return False, f"TShark execution failed: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, "TShark command timed out", None
            
        except FileNotFoundError:
            # TShark not found in PATH
            return False, "TShark not found in system PATH", None
            
        except Exception as e:
            return False, f"Error checking TShark installation: {str(e)}", None
    
    def get_tshark_installation_error_message(self) -> str:
        """
        Get detailed error message and installation instructions for TShark.
        
        Returns:
            str: Comprehensive error message with installation guidance
        """
        is_installed, error, version = self.validate_tshark_installation()
        
        if is_installed:
            return f"TShark is properly installed: {version}"
        
        base_error = f"TShark Installation Error: {error}\n\n"
        
        if self.is_windows:
            return base_error + self._get_windows_tshark_instructions()
        elif self.is_linux:
            return base_error + self._get_linux_tshark_instructions()
        else:
            return base_error + "Please install TShark for your platform."
    
    def _get_windows_tshark_instructions(self) -> str:
        """Get Windows-specific TShark installation instructions."""
        return (
            "Windows TShark Installation:\n"
            "===========================\n\n"
            "Method 1 - Install Wireshark (Recommended):\n"
            "1. Download Wireshark from: https://www.wireshark.org/download.html\n"
            "2. Run the installer as Administrator\n"
            "3. During installation, ensure these components are selected:\n"
            "   ✓ TShark (command-line network analyzer)\n"
            "   ✓ Npcap (packet capture library)\n"
            "4. Complete the installation\n"
            "5. Add Wireshark to PATH (if not automatic):\n"
            "   - Default location: C:\\Program Files\\Wireshark\n"
            "   - Add to System Environment Variables > PATH\n\n"
            "Method 2 - Standalone TShark:\n"
            "1. Download TShark from: https://www.wireshark.org/download.html\n"
            "2. Install Npcap separately from: https://nmap.org/npcap/\n"
            "3. Ensure TShark is in your PATH\n\n"
            "Verification Steps:\n"
            "1. Open Command Prompt as Administrator\n"
            "2. Run: tshark --version\n"
            "3. Should display version information without errors\n\n"
            "Common Issues:\n"
            "- 'tshark' is not recognized: Add Wireshark directory to PATH\n"
            "- Permission denied: Run Command Prompt as Administrator\n"
            "- Npcap errors: Uninstall WinPcap if present (conflicts with Npcap)\n"
            "- Firewall/Antivirus: Add TShark to exceptions if blocked"
        )
    
    def _get_linux_tshark_instructions(self) -> str:
        """Get Linux-specific TShark installation instructions."""
        return (
            "Linux TShark Installation:\n"
            "=========================\n\n"
            "Ubuntu/Debian:\n"
            "1. Update package repositories:\n"
            "   sudo apt update\n\n"
            "2. Install TShark:\n"
            "   sudo apt install tshark\n\n"
            "3. Install additional dependencies:\n"
            "   sudo apt install libpcap-dev\n\n"
            "4. Configure non-root capture (optional but recommended):\n"
            "   sudo dpkg-reconfigure wireshark-common\n"
            "   # Select 'Yes' when asked about non-superuser packet capture\n"
            "   sudo usermod -a -G wireshark $USER\n"
            "   # Log out and back in for group changes to take effect\n\n"
            "CentOS/RHEL:\n"
            "1. Install TShark:\n"
            "   sudo yum install wireshark-cli\n"
            "   # OR for newer versions:\n"
            "   sudo dnf install wireshark-cli\n\n"
            "2. Install development packages:\n"
            "   sudo yum install libpcap-devel\n\n"
            "Fedora:\n"
            "1. Install TShark:\n"
            "   sudo dnf install wireshark-cli\n\n"
            "2. Install development packages:\n"
            "   sudo dnf install libpcap-devel\n\n"
            "Verification Steps:\n"
            "1. Check installation: tshark --version\n"
            "2. Test capture (as root): sudo tshark -i any -c 5\n"
            "3. List interfaces: tshark -D\n\n"
            "Common Issues:\n"
            "- Permission denied: Use sudo or configure wireshark group\n"
            "- No interfaces found: Check network interface status\n"
            "- Package not found: Enable EPEL repository on CentOS/RHEL\n"
            "- Capture fails: Verify libpcap installation and permissions"
        )
    
    def check_dependencies(self) -> Dict[str, Dict[str, str]]:
        """
        Check all required dependencies and their status.
        
        Returns:
            Dict containing dependency check results
        """
        results = {
            'platform': {
                'status': 'ok' if self.platform in ['Windows', 'Linux'] else 'error',
                'details': f"Platform: {self.platform}",
                'message': 'Supported platform detected' if self.platform in ['Windows', 'Linux'] 
                          else 'Unsupported platform'
            },
            'privileges': {
                'status': 'ok' if self.check_privileges() else 'error',
                'details': f"Has privileges: {self.check_privileges()}",
                'message': 'Sufficient privileges' if self.check_privileges() 
                          else 'Insufficient privileges for packet capture'
            }
        }
        
        # Check TShark
        tshark_installed, tshark_error, tshark_version = self.validate_tshark_installation()
        results['tshark'] = {
            'status': 'ok' if tshark_installed else 'error',
            'details': tshark_version if tshark_installed else tshark_error,
            'message': 'TShark is available' if tshark_installed else 'TShark not found or not working'
        }
        
        # Check Python version
        python_version = sys.version_info
        python_ok = python_version >= (3, 8)
        major = getattr(python_version, 'major', python_version[0])
        minor = getattr(python_version, 'minor', python_version[1])
        micro = getattr(python_version, 'micro', python_version[2])
        results['python'] = {
            'status': 'ok' if python_ok else 'error',
            'details': f"Python {major}.{minor}.{micro}",
            'message': 'Python version is compatible' if python_ok 
                      else 'Python 3.8+ required'
        }
        
        return results
    
    def get_dependency_report(self) -> str:
        """
        Generate a comprehensive dependency status report.
        
        Returns:
            str: Formatted dependency report
        """
        results = self.check_dependencies()
        
        report = "Dependency Status Report\n"
        report += "=" * 50 + "\n\n"
        
        all_ok = True
        for dep_name, dep_info in results.items():
            status_symbol = "✓" if dep_info['status'] == 'ok' else "✗"
            report += f"{status_symbol} {dep_name.upper()}: {dep_info['message']}\n"
            report += f"   Details: {dep_info['details']}\n\n"
            
            if dep_info['status'] != 'ok':
                all_ok = False
        
        if all_ok:
            report += "🎉 All dependencies are satisfied! Ready for packet capture.\n"
        else:
            report += "⚠️  Some dependencies need attention. See installation instructions above.\n"
        
        return report
    
    def get_platform_info(self) -> Dict[str, str]:
        """
        Get detailed platform information for logging and debugging.
        
        Returns:
            Dict containing platform details
        """
        info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'platform_detected': self.platform,
            'has_privileges': str(self.check_privileges())
        }
        
        # Add TShark information
        tshark_installed, tshark_error, tshark_version = self.validate_tshark_installation()
        info['tshark_installed'] = str(tshark_installed)
        info['tshark_version'] = tshark_version if tshark_installed else tshark_error
        
        if self.is_linux:
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            info['distribution'] = line.split('=')[1].strip().strip('"')
                            break
            except FileNotFoundError:
                info['distribution'] = 'Unknown Linux'
        
        return info


# Convenience function for quick platform checks
def get_platform_manager() -> PlatformManager:
    """Get a configured PlatformManager instance."""
    return PlatformManager()


# Module-level convenience functions
def is_windows() -> bool:
    """Check if running on Windows."""
    return PlatformManager().is_windows


def is_linux() -> bool:
    """Check if running on Linux."""
    return PlatformManager().is_linux


def has_privileges() -> bool:
    """Check if current process has packet capture privileges."""
    return PlatformManager().check_privileges()


def is_tshark_available() -> bool:
    """Check if TShark is installed and available."""
    pm = PlatformManager()
    installed, _, _ = pm.validate_tshark_installation()
    return installed


def validate_environment() -> Tuple[bool, str]:
    """
    Validate the complete environment for packet capture.
    
    Returns:
        Tuple of (is_ready, status_message)
    """
    pm = PlatformManager()
    
    # Check all dependencies
    results = pm.check_dependencies()
    
    # Check if all are OK
    all_ok = all(result['status'] == 'ok' for result in results.values())
    
    if all_ok:
        return True, "Environment is ready for packet capture operations."
    else:
        failed_deps = [name for name, result in results.items() if result['status'] != 'ok']
        return False, f"Environment validation failed. Issues with: {', '.join(failed_deps)}"