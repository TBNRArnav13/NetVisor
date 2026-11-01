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
Port-Specific Capture - Wrapper for netcap_manager.py with port filtering
"""

import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description='Capture packets by port')
    parser.add_argument('--interface', '-i', required=True, help='Network interface to capture from')
    parser.add_argument('--ports', '-p', required=True, help='Ports to capture (comma-separated or ranges)')
    parser.add_argument('--duration', '-d', type=int, help='Capture duration in seconds')
    parser.add_argument('--output-dir', help='Output directory (ignored - uses netcap_manager)')
    
    args = parser.parse_args()
    
    # Build command for netcap_manager
    cmd = [sys.executable, 'netcap_manager.py', 'capture', '--interface', args.interface]
    
    if args.duration:
        cmd.extend(['--duration', str(args.duration)])
    
    print(f"[INFO] Starting port-specific capture on interface: {args.interface}")
    print(f"[INFO] Ports: {args.ports}")
    if args.duration:
        print(f"[INFO] Duration: {args.duration} seconds")
    else:
        print("[INFO] Continuous capture (press Ctrl+C to stop)")
    
    # Note: Port filtering would need to be implemented in netcap_manager
    # For now, this captures all traffic and user can filter in dashboard
    print(f"[NOTE] Capturing all traffic - filter by ports {args.ports} in dashboard")
    
    # Execute netcap_manager
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[INFO] Capture stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Capture failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()