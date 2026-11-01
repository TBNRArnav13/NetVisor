"""
Interface Manager - Network interface discovery and management.

Discovers, validates, and manages network interfaces across platforms with
cross-platform compatibility and safe filename generation.
"""

import re
import logging
import subprocess
from typing import List, Optional, Dict, Any
import pyshark
import psutil

from .base_interfaces import IInterfaceManager, InterfaceInfo

# Optional import for netifaces (may not be available on all systems)
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False
    netifaces = None


class InterfaceManager(IInterfaceManager):
    """Concrete implementation of network interface management."""
    
    def __init__(self, platform_manager=None):
        self.platform_manager = platform_manager
        self.logger = logging.getLogger(__name__)
        self._interface_cache = {}
        self._cache_valid = False
    
    def list_interfaces(self) -> List[InterfaceInfo]:
        """
        List all available network interfaces using multiple discovery methods.
        
        Uses pyshark, netifaces, and psutil for comprehensive interface discovery
        with cross-platform compatibility.
        
        Returns:
            List[InterfaceInfo]: List of discovered network interfaces
        """
        interfaces = []
        
        try:
            # Primary method: Use pyshark for interface discovery
            interfaces.extend(self._discover_pyshark_interfaces())
        except Exception as e:
            self.logger.warning(f"PyShark interface discovery failed: {e}")
        
        if NETIFACES_AVAILABLE:
            try:
                # Fallback method: Use netifaces for additional interface info
                interfaces.extend(self._discover_netifaces_interfaces())
            except Exception as e:
                self.logger.warning(f"Netifaces interface discovery failed: {e}")
        else:
            self.logger.debug("Netifaces not available, skipping netifaces-based discovery")
        
        try:
            # Additional method: Use psutil for system interface info
            interfaces.extend(self._discover_psutil_interfaces())
        except Exception as e:
            self.logger.warning(f"PSUtil interface discovery failed: {e}")
        
        # Remove duplicates and merge information
        unique_interfaces = self._merge_interface_info(interfaces)
        
        # Cache the results
        self._interface_cache = {iface.name: iface for iface in unique_interfaces}
        self._cache_valid = True
        
        return unique_interfaces
    
    def validate_interface(self, interface: str) -> bool:
        """
        Validate if an interface exists and is accessible for packet capture.
        
        Args:
            interface: Interface name to validate
            
        Returns:
            bool: True if interface is valid and accessible
        """
        if not interface:
            return False
        
        # Refresh interface list if cache is invalid
        if not self._cache_valid:
            self.list_interfaces()
        
        # Check if interface exists in our cache
        if interface in self._interface_cache:
            iface_info = self._interface_cache[interface]
            return iface_info.is_active
        
        # Try to validate using pyshark directly
        try:
            # Attempt to create a capture object to test accessibility
            capture = pyshark.LiveCapture(interface=interface)
            # Don't actually start capture, just test if interface is accessible
            capture.close()
            return True
        except Exception as e:
            self.logger.debug(f"Interface validation failed for {interface}: {e}")
            return False
    
    def get_default_interface(self) -> str:
        """
        Get the default network interface for the platform.
        
        Selects the best available interface based on:
        1. Active status
        2. Has IP address assigned
        3. Not loopback
        4. Platform-specific preferences
        
        Returns:
            str: Name of the default interface
            
        Raises:
            RuntimeError: If no suitable interface is found
        """
        interfaces = self.list_interfaces()
        
        if not interfaces:
            raise RuntimeError("No network interfaces found")
        
        # Filter for active interfaces with IP addresses
        active_interfaces = [
            iface for iface in interfaces 
            if iface.is_active and iface.ip_addresses and not self._is_loopback(iface)
        ]
        
        if not active_interfaces:
            # Fallback to any active interface
            active_interfaces = [iface for iface in interfaces if iface.is_active]
        
        if not active_interfaces:
            raise RuntimeError("No active network interfaces found")
        
        # Platform-specific default selection
        if self.platform_manager:
            platform = self.platform_manager.detect_platform()
            if platform == "Windows":
                # Prefer Ethernet over WiFi on Windows
                for iface in active_interfaces:
                    if "ethernet" in iface.description.lower() or "eth" in iface.name.lower():
                        return iface.name
            elif platform == "Linux":
                # Prefer eth0, ens, or enp interfaces on Linux
                for iface in active_interfaces:
                    if iface.name.startswith(("eth", "ens", "enp")):
                        return iface.name
        
        # Return the first active interface as default
        return active_interfaces[0].name
    
    def sanitize_interface_name(self, interface: str) -> str:
        """
        Sanitize interface name for safe filename generation.
        
        Removes or replaces characters that could cause issues in filenames
        across different operating systems.
        
        Args:
            interface: Raw interface name
            
        Returns:
            str: Sanitized interface name safe for use in filenames
        """
        if not interface:
            return "unknown"
        
        # Remove leading/trailing dots and spaces first
        sanitized = interface.strip('. ')
        
        # Replace problematic characters with underscores
        # Remove: < > : " | ? * \ / and control characters
        sanitized = re.sub(r'[<>:"|?*\\/\x00-\x1f\x7f]', '_', sanitized)
        
        # Replace spaces with underscores
        sanitized = re.sub(r'\s+', '_', sanitized)
        
        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "unknown"
        
        # Limit length to prevent filesystem issues
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        
        # Ensure it doesn't end with a dot (Windows issues)
        sanitized = sanitized.rstrip('.')
        
        return sanitized
    
    def _discover_pyshark_interfaces(self) -> List[InterfaceInfo]:
        """Discover interfaces using pyshark."""
        interfaces = []
        
        try:
            # PyShark doesn't have a direct get_interfaces() method
            # We'll use a different approach - try to get interfaces from tshark directly
            
            # Try to get interfaces using tshark -D command
            result = subprocess.run(['tshark', '-D'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        # Parse tshark -D output format: "1. interface_name (description)"
                        parts = line.split('.', 1)
                        if len(parts) > 1:
                            iface_info = parts[1].strip()
                            # Extract interface name (before parentheses if present)
                            if '(' in iface_info:
                                iface_name = iface_info.split('(')[0].strip()
                                description = iface_info
                            else:
                                iface_name = iface_info
                                description = f"Network interface {iface_name}"
                            
                            # Get additional info from other sources if available
                            ip_addresses = []
                            mac_address = ""
                            
                            if NETIFACES_AVAILABLE and iface_name in netifaces.interfaces():
                                addrs = netifaces.ifaddresses(iface_name)
                                if netifaces.AF_INET in addrs:
                                    ip_addresses = [addr['addr'] for addr in addrs[netifaces.AF_INET]]
                                if netifaces.AF_LINK in addrs and addrs[netifaces.AF_LINK]:
                                    mac_address = addrs[netifaces.AF_LINK][0].get('addr', '')
                            
                            interface_info = InterfaceInfo(
                                name=iface_name,
                                display_name=iface_name,
                                description=description,
                                is_active=True,  # Assume active if tshark can see it
                                ip_addresses=ip_addresses,
                                mac_address=mac_address,
                                platform_specific={'source': 'pyshark_tshark'}
                            )
                            interfaces.append(interface_info)
                            
        except subprocess.TimeoutExpired:
            self.logger.warning("TShark interface discovery timed out")
        except FileNotFoundError:
            self.logger.debug("TShark not found, skipping pyshark-based interface discovery")
        except Exception as e:
            self.logger.warning(f"PyShark interface discovery failed: {e}")
            
        return interfaces
    
    def _discover_netifaces_interfaces(self) -> List[InterfaceInfo]:
        """Discover interfaces using netifaces."""
        interfaces = []
        
        if not NETIFACES_AVAILABLE:
            return interfaces
        
        try:
            for iface_name in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(iface_name)
                    
                    # Get IP addresses
                    ip_addresses = []
                    if netifaces.AF_INET in addrs:
                        ip_addresses = [addr['addr'] for addr in addrs[netifaces.AF_INET]]
                    
                    # Get MAC address
                    mac_address = ""
                    if netifaces.AF_LINK in addrs and addrs[netifaces.AF_LINK]:
                        mac_address = addrs[netifaces.AF_LINK][0].get('addr', '')
                    
                    # Determine if interface is active (has IP or is up)
                    is_active = bool(ip_addresses) or self._is_interface_up(iface_name)
                    
                    interface_info = InterfaceInfo(
                        name=iface_name,
                        display_name=iface_name,
                        description=f"Network interface {iface_name}",
                        is_active=is_active,
                        ip_addresses=ip_addresses,
                        mac_address=mac_address,
                        platform_specific={'source': 'netifaces'}
                    )
                    interfaces.append(interface_info)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing netifaces interface {iface_name}: {e}")
                    
        except Exception as e:
            self.logger.warning(f"Netifaces interface discovery failed: {e}")
            
        return interfaces
    
    def _discover_psutil_interfaces(self) -> List[InterfaceInfo]:
        """Discover interfaces using psutil."""
        interfaces = []
        
        try:
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for iface_name, addresses in net_if_addrs.items():
                try:
                    # Get IP addresses and MAC address
                    ip_addresses = []
                    mac_address = ""
                    
                    for addr in addresses:
                        if addr.family == 2:  # AF_INET (IPv4)
                            ip_addresses.append(addr.address)
                        elif addr.family == 17:  # AF_LINK (MAC)
                            mac_address = addr.address
                    
                    # Get interface statistics
                    is_active = False
                    if iface_name in net_if_stats:
                        stats = net_if_stats[iface_name]
                        is_active = stats.isup
                    
                    interface_info = InterfaceInfo(
                        name=iface_name,
                        display_name=iface_name,
                        description=f"Network interface {iface_name}",
                        is_active=is_active,
                        ip_addresses=ip_addresses,
                        mac_address=mac_address,
                        platform_specific={'source': 'psutil'}
                    )
                    interfaces.append(interface_info)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing psutil interface {iface_name}: {e}")
                    
        except Exception as e:
            self.logger.warning(f"PSUtil interface discovery failed: {e}")
            
        return interfaces
    
    def _merge_interface_info(self, interfaces: List[InterfaceInfo]) -> List[InterfaceInfo]:
        """Merge interface information from multiple sources."""
        merged = {}
        
        for iface in interfaces:
            name = iface.name
            if name in merged:
                # Merge information, preferring more complete data
                existing = merged[name]
                
                # Prefer non-empty IP addresses
                if not existing.ip_addresses and iface.ip_addresses:
                    existing.ip_addresses = iface.ip_addresses
                
                # Prefer non-empty MAC addresses
                if not existing.mac_address and iface.mac_address:
                    existing.mac_address = iface.mac_address
                
                # Prefer active status if any source reports it as active
                if not existing.is_active and iface.is_active:
                    existing.is_active = iface.is_active
                
                # Merge platform-specific data
                existing.platform_specific.update(iface.platform_specific)
            else:
                merged[name] = iface
        
        return list(merged.values())
    
    def _is_loopback(self, interface: InterfaceInfo) -> bool:
        """Check if interface is a loopback interface."""
        loopback_names = ['lo', 'loopback', 'localhost']
        loopback_ips = ['127.0.0.1', '::1']
        
        # Check by name
        if interface.name.lower() in loopback_names:
            return True
        
        # Check by IP address
        for ip in interface.ip_addresses:
            if ip in loopback_ips or ip.startswith('127.'):
                return True
        
        return False
    
    def _is_interface_up(self, interface_name: str) -> bool:
        """Check if interface is up using psutil."""
        try:
            net_if_stats = psutil.net_if_stats()
            if interface_name in net_if_stats:
                return net_if_stats[interface_name].isup
        except Exception:
            pass
        return False
    
    def monitor_interface_availability(self, interface: str) -> Dict[str, Any]:
        """
        Monitor interface availability and return detailed status.
        
        Args:
            interface: Interface name to monitor
            
        Returns:
            Dict containing interface status, error messages, and suggestions
        """
        status = {
            'available': False,
            'active': False,
            'has_ip': False,
            'error_message': None,
            'suggestions': []
        }
        
        try:
            # Check if interface exists
            interfaces = self.list_interfaces()
            interface_info = None
            
            for iface in interfaces:
                if iface.name == interface:
                    interface_info = iface
                    break
            
            if not interface_info:
                status['error_message'] = f"Interface '{interface}' not found"
                status['suggestions'] = self._get_interface_suggestions(interface, interfaces)
                return status
            
            status['available'] = True
            status['active'] = interface_info.is_active
            status['has_ip'] = bool(interface_info.ip_addresses)
            
            # Additional validation for packet capture capability
            if not self._test_capture_capability(interface):
                status['error_message'] = f"Interface '{interface}' exists but cannot be used for packet capture"
                status['suggestions'].append("Check if you have sufficient privileges for packet capture")
                if self.platform_manager:
                    if not self.platform_manager.check_privileges():
                        status['suggestions'].append(self.platform_manager.get_privilege_error_message())
            
            return status
            
        except Exception as e:
            status['error_message'] = f"Error monitoring interface '{interface}': {str(e)}"
            status['suggestions'].append("Try refreshing the interface list or check system configuration")
            return status
    
    def get_interface_fallbacks(self, preferred_interface: str) -> List[str]:
        """
        Get fallback interfaces when the preferred interface is unavailable.
        
        Args:
            preferred_interface: The originally requested interface
            
        Returns:
            List of alternative interface names, ordered by preference
        """
        fallbacks = []
        
        try:
            interfaces = self.list_interfaces()
            active_interfaces = [iface for iface in interfaces if iface.is_active]
            
            # Remove the preferred interface from consideration
            active_interfaces = [iface for iface in active_interfaces if iface.name != preferred_interface]
            
            if not active_interfaces:
                return fallbacks
            
            # Sort by preference criteria
            def interface_score(iface):
                score = 0
                # Prefer interfaces with IP addresses
                if iface.ip_addresses:
                    score += 10
                # Prefer non-loopback interfaces
                if not self._is_loopback(iface):
                    score += 5
                # Platform-specific preferences
                if self.platform_manager:
                    platform = self.platform_manager.detect_platform()
                    if platform == "Windows":
                        if "ethernet" in iface.description.lower():
                            score += 3
                    elif platform == "Linux":
                        if iface.name.startswith(("eth", "ens", "enp")):
                            score += 3
                return score
            
            # Sort by score (highest first)
            active_interfaces.sort(key=interface_score, reverse=True)
            fallbacks = [iface.name for iface in active_interfaces[:5]]  # Limit to top 5
            
        except Exception as e:
            self.logger.error(f"Error getting interface fallbacks: {e}")
        
        return fallbacks
    
    def get_interface_error_message(self, interface: str, error: Exception = None) -> str:
        """
        Generate clear error message for interface-related issues.
        
        Args:
            interface: Interface name that caused the error
            error: Optional exception that occurred
            
        Returns:
            str: Human-readable error message with suggestions
        """
        base_message = f"Interface '{interface}' is not available for packet capture."
        
        # Get interface status for detailed error information
        status = self.monitor_interface_availability(interface)
        
        if status['error_message']:
            base_message = status['error_message']
        
        # Build comprehensive error message
        error_parts = [base_message]
        
        if error:
            error_parts.append(f"Error details: {str(error)}")
        
        # Add suggestions
        if status['suggestions']:
            error_parts.append("Suggestions:")
            for suggestion in status['suggestions']:
                error_parts.append(f"  - {suggestion}")
        
        # Add available interfaces
        try:
            interfaces = self.list_interfaces()
            active_interfaces = [iface.name for iface in interfaces if iface.is_active]
            if active_interfaces:
                error_parts.append(f"Available interfaces: {', '.join(active_interfaces)}")
        except Exception:
            pass
        
        return "\n".join(error_parts)
    
    def validate_interface_for_capture(self, interface: str) -> tuple[bool, str]:
        """
        Comprehensive validation of interface for packet capture operations.
        
        Args:
            interface: Interface name to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic existence check
            if not self.validate_interface(interface):
                return False, self.get_interface_error_message(interface)
            
            # Test actual capture capability
            if not self._test_capture_capability(interface):
                error_msg = f"Interface '{interface}' exists but cannot be used for packet capture. "
                if self.platform_manager and not self.platform_manager.check_privileges():
                    error_msg += self.platform_manager.get_privilege_error_message()
                else:
                    error_msg += "Check if the interface supports packet capture and is not in use by another application."
                return False, error_msg
            
            return True, ""
            
        except Exception as e:
            return False, self.get_interface_error_message(interface, e)
    
    def _test_capture_capability(self, interface: str) -> bool:
        """
        Test if interface can actually be used for packet capture.
        
        Args:
            interface: Interface name to test
            
        Returns:
            bool: True if interface supports packet capture
        """
        try:
            # Create a test capture object without starting capture
            capture = pyshark.LiveCapture(interface=interface)
            
            # Try to access the interface (this will fail if not accessible)
            # We don't actually start capture, just test if pyshark can access it
            capture.close()
            return True
            
        except Exception as e:
            self.logger.debug(f"Capture capability test failed for {interface}: {e}")
            return False
    
    def _get_interface_suggestions(self, requested_interface: str, available_interfaces: List[InterfaceInfo]) -> List[str]:
        """
        Generate suggestions for interface name corrections.
        
        Args:
            requested_interface: The interface name that was requested
            available_interfaces: List of available interfaces
            
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        if not available_interfaces:
            suggestions.append("No network interfaces found. Check if network drivers are installed.")
            return suggestions
        
        # Look for similar names (fuzzy matching)
        similar_interfaces = []
        requested_lower = requested_interface.lower()
        
        for iface in available_interfaces:
            iface_lower = iface.name.lower()
            # Simple similarity check
            if (requested_lower in iface_lower or 
                iface_lower in requested_lower or
                self._calculate_similarity(requested_lower, iface_lower) > 0.6):
                similar_interfaces.append(iface.name)
        
        if similar_interfaces:
            suggestions.append(f"Did you mean one of: {', '.join(similar_interfaces)}?")
        
        # List active interfaces
        active_interfaces = [iface.name for iface in available_interfaces if iface.is_active]
        if active_interfaces:
            suggestions.append(f"Active interfaces: {', '.join(active_interfaces)}")
        
        # Platform-specific suggestions
        if self.platform_manager:
            platform = self.platform_manager.detect_platform()
            if platform == "Windows":
                suggestions.append("On Windows, try using interface names like 'Ethernet', 'Wi-Fi', or check 'ipconfig /all' for exact names")
            elif platform == "Linux":
                suggestions.append("On Linux, try using interface names like 'eth0', 'ens33', or check 'ip link show' for exact names")
        
        return suggestions
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate simple similarity score between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            float: Similarity score between 0 and 1
        """
        if str1 == str2:
            return 1.0
        if str1 == str2:
            return 1.0
        if not str1 or not str2:
            return 0.0
        
        # Simple Jaccard similarity using character bigrams
        def get_bigrams(s):
            return set(s[i:i+2] for i in range(len(s)-1))
        
        bigrams1 = get_bigrams(str1)
        bigrams2 = get_bigrams(str2)
        
        if not bigrams1 and not bigrams2:
            return 1.0
        if not bigrams1 or not bigrams2:
            return 0.0
        
        intersection = len(bigrams1.intersection(bigrams2))
        union = len(bigrams1.union(bigrams2))
        
        return intersection / union if union > 0 else 0.0