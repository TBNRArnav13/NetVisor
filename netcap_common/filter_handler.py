"""
Filter Handler - BPF and display filters for protocol-specific capture.

Manages BPF and display filters for protocol-specific capture with validation,
port range parsing, and filter optimization.
"""

import re
import logging
from typing import List, Dict, Set, Optional
from .base_interfaces import IFilterHandler


class FilterHandler(IFilterHandler):
    """Concrete implementation of packet filter operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Predefined protocol filters with optimized BPF expressions
        self.protocol_filters = {
            'http': 'tcp port 80 or tcp port 443 or tcp port 8080 or tcp port 8443',
            'https': 'tcp port 443 or tcp port 8443',
            'dns': 'udp port 53 or tcp port 53',
            'icmp': 'icmp',
            'tcp': 'tcp',
            'udp': 'udp',
            'ssh': 'tcp port 22',
            'ftp': 'tcp port 21 or tcp port 20',
            'smtp': 'tcp port 25 or tcp port 587 or tcp port 465',
            'pop3': 'tcp port 110 or tcp port 995',
            'imap': 'tcp port 143 or tcp port 993',
            'telnet': 'tcp port 23',
            'snmp': 'udp port 161 or udp port 162',
            'dhcp': 'udp port 67 or udp port 68',
            'ntp': 'udp port 123',
            'ldap': 'tcp port 389 or tcp port 636',
            'sip': 'udp port 5060 or tcp port 5060 or tcp port 5061',
            'rtp': 'udp portrange 16384-32767'
        }
        
        # Valid BPF filter keywords for validation
        self.valid_bpf_keywords = {
            'host', 'net', 'port', 'portrange', 'src', 'dst', 'tcp', 'udp', 'icmp',
            'ip', 'ip6', 'arp', 'rarp', 'ether', 'broadcast', 'multicast',
            'and', 'or', 'not', 'greater', 'less', 'len'
        }
    
    def validate_filter(self, filter_str: str) -> bool:
        """
        Validate filter syntax for BPF compatibility.
        
        Args:
            filter_str: The filter string to validate
            
        Returns:
            bool: True if filter is valid, False otherwise
        """
        if not filter_str or not isinstance(filter_str, str):
            return False
        
        # Remove extra whitespace and convert to lowercase for validation
        filter_clean = ' '.join(filter_str.strip().split()).lower()
        
        if not filter_clean:
            return False
        
        try:
            # Basic syntax validation
            if not self._validate_basic_syntax(filter_clean):
                return False
            
            # Check for balanced parentheses
            if not self._validate_parentheses(filter_clean):
                return False
            
            # Validate port numbers and ranges
            if not self._validate_port_numbers(filter_clean):
                return False
            
            # Validate IP addresses if present
            if not self._validate_ip_addresses(filter_clean):
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Filter validation error: {e}")
            return False
    
    def convert_to_bpf(self, protocol: str) -> str:
        """
        Convert protocol name to optimized BPF filter.
        
        Args:
            protocol: Protocol name (e.g., 'http', 'dns', 'tcp')
            
        Returns:
            str: BPF filter string
            
        Raises:
            ValueError: If protocol is not supported
        """
        if not protocol or not isinstance(protocol, str):
            raise ValueError("Protocol must be a non-empty string")
        
        protocol_lower = protocol.lower().strip()
        
        if protocol_lower in self.protocol_filters:
            bpf_filter = self.protocol_filters[protocol_lower]
            self.logger.debug(f"Converted protocol '{protocol}' to BPF: {bpf_filter}")
            return bpf_filter
        
        # Check if it's already a valid BPF filter
        if self.validate_filter(protocol):
            self.logger.debug(f"Using custom BPF filter: {protocol}")
            return protocol
        
        raise ValueError(f"Unsupported protocol: {protocol}. "
                        f"Supported protocols: {', '.join(sorted(self.protocol_filters.keys()))}")
    
    def parse_port_specification(self, port_spec: str) -> List[int]:
        """
        Parse port specification string into list of individual ports.
        
        Supports formats:
        - Individual ports: "80,443,8080"
        - Port ranges: "1-1024"
        - Mixed: "1-1024,443,8080"
        
        Args:
            port_spec: Port specification string
            
        Returns:
            List[int]: List of individual port numbers
            
        Raises:
            ValueError: If port specification is invalid
        """
        if not port_spec or not isinstance(port_spec, str):
            raise ValueError("Port specification must be a non-empty string")
        
        ports = set()  # Use set to avoid duplicates
        
        try:
            # Split by comma and process each part
            parts = [part.strip() for part in port_spec.split(',')]
            
            for part in parts:
                if not part:
                    continue
                
                if '-' in part:
                    # Handle port range
                    range_parts = part.split('-', 1)
                    if len(range_parts) != 2:
                        raise ValueError(f"Invalid port range format: {part}")
                    
                    start_str, end_str = range_parts
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    
                    if not self._validate_port_range(start, end):
                        raise ValueError(f"Invalid port range: {start}-{end}")
                    
                    # Add all ports in range
                    ports.update(range(start, end + 1))
                    
                else:
                    # Handle individual port
                    port = int(part)
                    if not self._validate_port_number(port):
                        raise ValueError(f"Invalid port number: {port}")
                    
                    ports.add(port)
            
            if not ports:
                raise ValueError("No valid ports found in specification")
            
            result = sorted(list(ports))
            self.logger.debug(f"Parsed port specification '{port_spec}' to {len(result)} ports")
            return result
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Error parsing port specification '{port_spec}': {e}")
    
    def create_port_filter(self, ports: List[int]) -> str:
        """
        Create optimized BPF filter for specified ports.
        
        Args:
            ports: List of port numbers
            
        Returns:
            str: Optimized BPF filter string
            
        Raises:
            ValueError: If ports list is invalid
        """
        if not ports or not isinstance(ports, list):
            raise ValueError("Ports must be a non-empty list")
        
        # Validate all ports
        for port in ports:
            if not isinstance(port, int) or not self._validate_port_number(port):
                raise ValueError(f"Invalid port number: {port}")
        
        # Remove duplicates and sort
        unique_ports = sorted(set(ports))
        
        # Optimize filter generation based on number of ports
        if len(unique_ports) == 1:
            # Single port
            filter_str = f"port {unique_ports[0]}"
        elif len(unique_ports) <= 10:
            # Small number of ports - use individual port specifications
            port_filters = [f"port {port}" for port in unique_ports]
            filter_str = " or ".join(port_filters)
        else:
            # Large number of ports - try to optimize with ranges
            filter_str = self._optimize_port_filter(unique_ports)
        
        self.logger.debug(f"Created port filter for {len(unique_ports)} ports: {filter_str}")
        return filter_str
    
    def get_supported_protocols(self) -> List[str]:
        """
        Get list of supported protocol names.
        
        Returns:
            List[str]: Sorted list of supported protocol names
        """
        return sorted(self.protocol_filters.keys())
    
    def combine_filters(self, filters: List[str], operator: str = "or") -> str:
        """
        Combine multiple filters with specified operator.
        
        Args:
            filters: List of filter strings
            operator: Logical operator ('and' or 'or')
            
        Returns:
            str: Combined filter string
            
        Raises:
            ValueError: If filters are invalid or operator is unsupported
        """
        if not filters or not isinstance(filters, list):
            raise ValueError("Filters must be a non-empty list")
        
        if operator.lower() not in ['and', 'or']:
            raise ValueError("Operator must be 'and' or 'or'")
        
        # Validate all filters
        valid_filters = []
        for filter_str in filters:
            if not isinstance(filter_str, str) or not filter_str.strip():
                continue
            
            if not self.validate_filter(filter_str):
                raise ValueError(f"Invalid filter: {filter_str}")
            
            valid_filters.append(f"({filter_str.strip()})")
        
        if not valid_filters:
            raise ValueError("No valid filters provided")
        
        if len(valid_filters) == 1:
            return valid_filters[0].strip("()")
        
        combined = f" {operator.lower()} ".join(valid_filters)
        self.logger.debug(f"Combined {len(valid_filters)} filters with '{operator}': {combined}")
        return combined
    
    def _validate_basic_syntax(self, filter_str: str) -> bool:
        """Validate basic BPF syntax."""
        # Check for invalid characters
        if re.search(r'[^\w\s\-\.\(\)\[\]\/\:&|!<>=]', filter_str):
            return False
        
        # Check for valid keywords
        tokens = re.findall(r'\b\w+\b', filter_str)
        for token in tokens:
            if token.isdigit():
                continue  # Numbers are valid
            if token in self.valid_bpf_keywords:
                continue  # Valid BPF keyword
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', token):
                continue  # IP address
            # Allow protocol names from our supported list
            if token in self.protocol_filters:
                continue
            
            # If we reach here, it might be an unknown keyword
            # For now, we'll be permissive and allow it
            pass
        
        return True
    
    def _validate_parentheses(self, filter_str: str) -> bool:
        """Validate balanced parentheses."""
        count = 0
        for char in filter_str:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0
    
    def _validate_port_numbers(self, filter_str: str) -> bool:
        """Validate port numbers in filter string."""
        # Find all port specifications
        port_patterns = [
            r'port\s+(\d+)',
            r'portrange\s+(\d+)-(\d+)',
            r'(\d+)-(\d+)'  # Generic range
        ]
        
        for pattern in port_patterns:
            matches = re.finditer(pattern, filter_str)
            for match in matches:
                if 'portrange' in pattern or '-' in pattern:
                    # Range validation
                    if len(match.groups()) >= 2:
                        start, end = int(match.group(1)), int(match.group(2))
                        if not self._validate_port_range(start, end):
                            return False
                else:
                    # Single port validation
                    port = int(match.group(1))
                    if not self._validate_port_number(port):
                        return False
        
        return True
    
    def _validate_ip_addresses(self, filter_str: str) -> bool:
        """Validate IP addresses in filter string."""
        # Find potential IP addresses
        ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        matches = re.finditer(ip_pattern, filter_str)
        
        for match in matches:
            ip = match.group(1)
            octets = ip.split('.')
            for octet in octets:
                if int(octet) > 255:
                    return False
        
        return True
    
    def _validate_port_number(self, port: int) -> bool:
        """Validate individual port number."""
        return isinstance(port, int) and 1 <= port <= 65535
    
    def _validate_port_range(self, start: int, end: int) -> bool:
        """Validate port range values."""
        if not (isinstance(start, int) and isinstance(end, int)):
            return False
        
        if not (1 <= start <= 65535 and 1 <= end <= 65535):
            return False
        
        if start > end:
            return False
        
        # Warn about very large ranges
        if end - start > 10000:
            self.logger.warning(f"Large port range detected: {start}-{end}")
        
        return True
    
    def _optimize_port_filter(self, ports: List[int]) -> str:
        """Optimize port filter by detecting ranges."""
        if not ports:
            return ""
        
        # Group consecutive ports into ranges
        ranges = []
        current_start = ports[0]
        current_end = ports[0]
        
        for i in range(1, len(ports)):
            if ports[i] == current_end + 1:
                # Consecutive port, extend current range
                current_end = ports[i]
            else:
                # Gap found, save current range and start new one
                if current_start == current_end:
                    ranges.append(f"port {current_start}")
                elif current_end - current_start == 1:
                    ranges.append(f"port {current_start} or port {current_end}")
                else:
                    ranges.append(f"portrange {current_start}-{current_end}")
                
                current_start = ports[i]
                current_end = ports[i]
        
        # Add the last range
        if current_start == current_end:
            ranges.append(f"port {current_start}")
        elif current_end - current_start == 1:
            ranges.append(f"port {current_start} or port {current_end}")
        else:
            ranges.append(f"portrange {current_start}-{current_end}")
        
        return " or ".join(ranges)