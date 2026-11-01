#!/bin/bash

echo "==================================================="
echo "  NetVisor - Live Network Packet Analysis Platform"
echo "==================================================="
echo

# Check if Python is available
if command -v python3 &> /dev/null; then
    PY_BIN=python3
elif command -v python &> /dev/null; then
    PY_BIN=python
else
    echo "[ERROR] Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Check if required files exist
if [ ! -f "server.py" ] && [ ! -f "Server1.py" ]; then
    echo "[ERROR] server.py not found"
    echo "Please run this script from the NetVisor directory"
    exit 1
fi

if [ ! -f "netcap_manager.py" ]; then
    echo "[ERROR] netcap_manager.py not found"
    echo "Please run this script from the NetVisor directory"
    exit 1
fi

echo "Available network interfaces:"
echo "---------------------------------------------------"
$PY_BIN netcap_manager.py interfaces
echo "---------------------------------------------------"
echo

# Get interface from user
read -p "Enter network interface name (or press Enter for eth0): " INTERFACE

if [ -z "$INTERFACE" ]; then
    INTERFACE="eth0"
fi

echo
echo "Starting NetVisor with interface: $INTERFACE"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[NOTE] Packet capture usually requires elevated permissions."
    echo "If capture fails, re-run with: sudo ./start_live_dashboard.sh"
    echo
fi

# Start live dashboard
$PY_BIN start_live_dashboard.py --interface "$INTERFACE"
