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
Test Dashboard - Generate sample packet data for testing the enhanced dashboard
"""

import json
import time
import random
import os
from datetime import datetime, timezone

def generate_sample_packet(packet_id):
    """Generate a realistic sample packet for testing."""
    
    protocols = ['TCP', 'UDP', 'HTTP', 'HTTPS', 'DNS', 'ICMP', 'TLS', 'QUIC']
    
    # Sample IP addresses (mix of internal and external)
    internal_ips = ['192.168.1.100', '192.168.1.101', '192.168.1.102', '10.0.0.50', '172.16.0.10']
    external_ips = ['8.8.8.8', '1.1.1.1', '142.250.191.14', '157.240.12.35', '52.84.223.104']
    
    # Common ports
    common_ports = {
        'HTTP': [80, 8080, 8000],
        'HTTPS': [443, 8443],
        'DNS': [53],
        'TCP': [22, 23, 25, 80, 110, 143, 443, 993, 995],
        'UDP': [53, 67, 68, 123, 161, 514],
        'ICMP': [None],
        'TLS': [443, 993, 995],
        'QUIC': [443, 80]
    }
    
    protocol = random.choice(protocols)
    src_ip = random.choice(internal_ips + external_ips)
    dest_ip = random.choice(internal_ips + external_ips)
    
    # Ensure src and dest are different
    while dest_ip == src_ip:
        dest_ip = random.choice(internal_ips + external_ips)
    
    # Generate ports based on protocol
    ports = common_ports.get(protocol, [80, 443, 22, 53])
    src_port = random.randint(1024, 65535) if protocol not in ['ICMP'] else None
    dest_port = random.choice([p for p in ports if p is not None]) if ports[0] is not None else None
    
    # Generate realistic packet lengths
    length = random.randint(64, 1500)
    
    # Generate protocol-specific info
    info_templates = {
        'HTTP': [
            'GET /index.html HTTP/1.1',
            'POST /api/data HTTP/1.1',
            'HTTP/1.1 200 OK',
            'HTTP/1.1 404 Not Found'
        ],
        'HTTPS': [
            'TLS Application Data',
            'Client Hello',
            'Server Hello',
            'Certificate'
        ],
        'DNS': [
            'Standard query A google.com',
            'Standard query response A 142.250.191.14',
            'Standard query AAAA facebook.com',
            'Standard query PTR 8.8.8.8'
        ],
        'TCP': [
            f'[SYN] Seq=0 Win=65535',
            f'[ACK] Seq=1 Ack=1 Win=65535',
            f'[FIN, ACK] Seq=100 Ack=1 Win=65535',
            f'[RST] Seq=0 Win=0'
        ],
        'UDP': [
            f'Source port: {src_port}',
            f'Length: {length}',
            'UDP Payload',
            'Broadcast packet'
        ],
        'ICMP': [
            'Echo (ping) request',
            'Echo (ping) reply',
            'Destination unreachable',
            'Time exceeded'
        ]
    }
    
    info = random.choice(info_templates.get(protocol, [f'{protocol} packet']))
    
    packet = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'packet_number': packet_id,
        'length': length,
        'protocols': [protocol],
        'source': src_ip,
        'destination': dest_ip,
        'protocol': protocol,
        'src_ip': src_ip,
        'dest_ip': dest_ip,
        'info': info
    }
    
    # Add port information if applicable
    if src_port:
        packet['source_port'] = src_port
    if dest_port:
        packet['destination_port'] = dest_port
        packet['info'] = f"{info} Port: {dest_port}"
    
    return packet

def create_test_json_file():
    """Create a test JSON file with sample packets."""
    
    # Ensure captures directory exists
    os.makedirs('captures', exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'captures/test_capture_{timestamp}.json'
    
    print(f"Creating test file: {filename}")
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Write file header
        header = {
            'file_info': {
                'format': 'NetCap JSON Packet Log',
                'version': '1.0',
                'created': datetime.now(timezone.utc).isoformat(),
                'interface': 'test_interface',
                'session_id': 'test_session_123',
                'frontend_compatible': True
            }
        }
        f.write(json.dumps(header, indent=2) + '\n')
        
        # Generate and write packet batches
        batch_number = 1
        total_packets = 0
        
        for batch in range(5):  # 5 batches
            packets_in_batch = random.randint(5, 15)
            batch_packets = []
            
            for i in range(packets_in_batch):
                packet = generate_sample_packet(total_packets + i + 1)
                batch_packets.append(packet)
            
            batch_data = {
                'batch_timestamp': datetime.now(timezone.utc).isoformat(),
                'batch_number': batch_number,
                'interface': 'test_interface',
                'packet_count': len(batch_packets),
                'total_packets': total_packets + len(batch_packets),
                'packets': batch_packets
            }
            
            f.write(json.dumps(batch_data, indent=2) + '\n')
            
            total_packets += len(batch_packets)
            batch_number += 1
            
            print(f"  Batch {batch_number-1}: {len(batch_packets)} packets")
            
            # Small delay between batches for realistic timing
            time.sleep(0.5)
    
    print(f"Test file created with {total_packets} total packets")
    return filename

def simulate_live_capture():
    """Simulate live packet capture by continuously adding to JSON file."""
    
    filename = create_test_json_file()
    
    print("Starting live simulation... (Press Ctrl+C to stop)")
    
    try:
        batch_number = 6
        total_packets = 50  # Starting from where we left off
        
        while True:
            # Generate a new batch every 2-5 seconds
            time.sleep(random.uniform(2, 5))
            
            packets_in_batch = random.randint(3, 12)
            batch_packets = []
            
            for i in range(packets_in_batch):
                packet = generate_sample_packet(total_packets + i + 1)
                batch_packets.append(packet)
            
            batch_data = {
                'batch_timestamp': datetime.now(timezone.utc).isoformat(),
                'batch_number': batch_number,
                'interface': 'test_interface',
                'packet_count': len(batch_packets),
                'total_packets': total_packets + len(batch_packets),
                'packets': batch_packets
            }
            
            # Append to existing file
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(batch_data, indent=2) + '\n')
            
            total_packets += len(batch_packets)
            batch_number += 1
            
            print(f"Added batch {batch_number-1}: {len(batch_packets)} packets (Total: {total_packets})")
            
    except KeyboardInterrupt:
        print(f"\nSimulation stopped. Total packets generated: {total_packets}")

def main():
    """Main function supporting CLI arguments and interactive mode."""
    import argparse
    parser = argparse.ArgumentParser(description="NetVisor Dashboard Test Traffic Generator")
    parser.add_argument("--simulate", "-s", action="store_true", help="Simulate continuous live packet stream")
    parser.add_argument("--file-only", "-f", action="store_true", help="Generate single test batch file and exit")
    args = parser.parse_args()

    print("NetVisor Dashboard Test Data Generator")
    print("=" * 40)

    if args.simulate:
        simulate_live_capture()
    elif args.file_only:
        create_test_json_file()
        print("\nTest file created. You can now view it in the dashboard.")
    else:
        try:
            choice = input("Choose option:\n1. Create test file only\n2. Simulate live capture\nEnter choice (1 or 2, default 1): ").strip()
        except EOFError:
            choice = '1'

        if choice == '2':
            simulate_live_capture()
        else:
            create_test_json_file()
            print("\nTest file created. You can now view it in the dashboard.")

if __name__ == "__main__":
    main()