#!/usr/bin/env python3
"""
NetVisor - Live Dashboard & Capture Orchestrator
Starts the WebSocket/HTTP streaming server and initiates live packet capture.
Cleanly shuts down all child processes (server, capture, tshark, dumpcap) on Ctrl+C.
"""

import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import os
import subprocess
import threading
import time
import argparse
import socket
import signal
from pathlib import Path

# Track child processes globally for reliable Ctrl+C cleanup
server_process = None
capture_process = None
is_shutting_down = False


def get_local_ip():
    """Get the local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def get_default_interface_name():
    """Attempt to detect a reasonable default interface name."""
    if sys.platform.startswith('win'):
        return 'Wi-Fi'
    return 'eth0'


def check_interface_exists(interface):
    """Check if the network interface exists."""
    try:
        result = subprocess.run(
            [sys.executable, 'netcap_manager.py', 'interfaces'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return interface.lower() in result.stdout.lower()
        return False
    except Exception:
        return False


def kill_process_tree(proc):
    """Recursively kill a process and all of its spawned children (e.g. tshark, dumpcap)."""
    if not proc or proc.poll() is not None:
        return
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
    except Exception:
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
            else:
                proc.kill()
        except Exception:
            pass


def cleanup_all():
    """Clean up all running processes and temporary files."""
    global is_shutting_down, server_process, capture_process
    if is_shutting_down:
        return
    is_shutting_down = True
    print("\n[*] Stopping NetVisor services and releasing network adapters...")

    if capture_process:
        kill_process_tree(capture_process)
    if server_process:
        kill_process_tree(server_process)

    # Extra safety for any orphaned dumpcap or tshark on Windows
    if sys.platform == 'win32':
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    pname = proc.info['name']
                    if pname and ('dumpcap' in pname.lower() or 'tshark' in pname.lower()):
                        proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

    # Clean up temporary JSON batches
    try:
        subprocess.run(
            [sys.executable, 'netcap_manager.py', 'cleanup', '--json'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass

    print("[+] All NetVisor services stopped cleanly.")


def signal_handler(signum, frame):
    """Handle Ctrl+C and termination signals immediately."""
    cleanup_all()
    sys.exit(0)


def start_server_process():
    """Start the WebSocket and HTTP server as a tracked subprocess."""
    global server_process
    server_script = 'server.py' if os.path.exists('server.py') else 'Server1.py'
    print("[+] Starting NetVisor Web & WebSocket Server...")
    server_process = subprocess.Popen([sys.executable, server_script])
    return server_process


def start_packet_capture(interface, duration=None):
    """Start packet capture using netcap_manager."""
    global capture_process
    print(f"[+] Starting packet capture on interface: {interface}")
    cmd = [sys.executable, 'netcap_manager.py', 'capture', '--interface', interface]
    if duration:
        cmd.extend(['--duration', str(duration)])
    capture_process = subprocess.Popen(cmd)
    return capture_process


def start_simulation():
    """Start mock traffic simulator."""
    global capture_process
    print("[+] Starting background mock traffic simulator...")
    cmd = [sys.executable, 'test_dashboard.py', '--simulate']
    capture_process = subprocess.Popen(cmd)
    return capture_process


def main():
    global server_process, capture_process

    # Register signal handlers for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(description='Start NetVisor Live Dashboard & Packet Engine')
    parser.add_argument('--interface', '-i', type=str, default=None,
                        help='Network interface to capture from (e.g., Wi-Fi, Ethernet, eth0)')
    parser.add_argument('--duration', '-d', type=int,
                        help='Capture duration in seconds (default: continuous)')
    parser.add_argument('--no-capture', action='store_true',
                        help='Start only the web and WebSocket server without packet capture')
    parser.add_argument('--demo', '--simulate', action='store_true',
                        help='Simulate live network traffic without requiring real capture permissions')

    args = parser.parse_args()

    print("==================================================")
    print("  NetVisor - Real-Time Packet Capture Platform    ")
    print("==================================================")

    # Determine interface
    interface = args.interface
    if not args.no_capture and not args.demo and not interface:
        interface = get_default_interface_name()
        print(f"[*] No interface specified. Defaulting to: {interface}")

    # Check interface validity if capturing live
    if not args.no_capture and not args.demo:
        print(f"[*] Validating interface: {interface}")
        if not check_interface_exists(interface):
            print(f"[!] Warning: Interface '{interface}' may not match system adapters.")
            print("[*] Available interfaces:")
            try:
                subprocess.run([sys.executable, 'netcap_manager.py', 'interfaces'])
            except Exception:
                pass

    # Start Server Subprocess
    start_server_process()
    time.sleep(1.5)

    # Open browser automatically
    try:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8000")).start()
    except Exception:
        pass

    # Start capture or simulation
    if args.demo:
        start_simulation()
    elif not args.no_capture:
        start_packet_capture(interface, args.duration)

    local_ip = get_local_ip()

    print("\n[+] NetVisor Dashboard is running!")
    print("--------------------------------------------------")
    print(f"  Web Dashboard:     http://localhost:8000 (or http://{local_ip}:8000)")
    print(f"  WebSocket Stream:  ws://localhost:8765")
    if args.demo:
        print("  Mode:              Traffic Simulation (Demo Mode)")
    elif args.no_capture:
        print("  Mode:              Server Only (No capture)")
    else:
        print(f"  Capture Interface: {interface}")
        print(f"  Duration:          {f'{args.duration}s' if args.duration else 'Continuous (Ctrl+C to stop)'}")
    print("--------------------------------------------------")
    print("Press Ctrl+C to stop all services.\n")

    try:
        while True:
            time.sleep(0.5)
            # If a duration was set and the capture process completed
            if capture_process and capture_process.poll() is not None:
                if args.duration:
                    print("[+] Capture duration elapsed.")
                    break
                elif not is_shutting_down:
                    print(f"[!] Capture process exited (code: {capture_process.returncode})")
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_all()


if __name__ == '__main__':
    main()
