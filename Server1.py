from collections import deque
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import socket
import threading
import asyncio
import websockets
import json
import time
import http.server
import socketserver
import os
import glob
from datetime import datetime

# --- CONFIGURATION ---
PORT = 8081
# Change SERVER to '0.0.0.0' to listen on all available network interfaces
SERVER = '0.0.0.0' 
ADDR = (SERVER, PORT)
WEBSOCKET_PORT = 8765 # Port for WebSocket connections
HTTP_PORT = 8000 # Port for the web server

# For Windows compatibility
try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except AttributeError:
    pass

# --- GLOBAL VARIABLES ---
clients = set()
ws_loop = None
capture_folder = "captures"
file_batch_tracking = {}  # Track processed batches per file
recent_packets = deque(maxlen=200)  # In-memory buffer for newly connected clients
recent_packets = deque(maxlen=200)  # In-memory buffer for newly connected clients

def get_local_ip():
    """Finds the local IP address of the machine more reliably."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # Fallback to loopback
    finally:
        s.close()
    return IP

# --- WEBSOCKET SERVER LOGIC ---
async def websocket_handler(websocket):
    clients.add(websocket)
    print(f"[WebSocket] Client connected from {websocket.remote_address}. Total clients: {len(clients)}")
    try:
        # Replay recent packets to newly connected client
        if recent_packets:
            print(f"[WebSocket] Replaying {len(recent_packets)} recent packets to new client...")
            for packet in list(recent_packets):
                await websocket.send(json.dumps(packet))
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)
        print(f"[WebSocket] Client disconnected. Total clients: {len(clients)}")

async def start_websocket_main():
    global ws_loop
    ws_loop = asyncio.get_running_loop()
    
    async with websockets.serve(websocket_handler, SERVER, WEBSOCKET_PORT):
        print(f"[WebSocket] Server started and listening on all interfaces on port {WEBSOCKET_PORT}")
        
        # Start JSON file monitoring
        asyncio.create_task(stream_json_data())
        
        await asyncio.Future()

def run_websocket_server():
    asyncio.run(start_websocket_main())

# --- TCP SERVER LOGIC (Corrected with Buffering) ---
def handle_tcp_client(conn):
    """Handles data from a client, buffering to ensure complete JSON messages."""
    buffer = ""
    with conn:
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    
                    if ws_loop and clients and message:
                        print(f"[TCP] Relaying complete packet ({len(message)} bytes) to WebSocket...")
                        asyncio.run_coroutine_threadsafe(broadcast_to_websockets(message), ws_loop)

            except ConnectionResetError:
                break
            except Exception as e:
                print(f"[TCP ERROR] An error occurred: {e}")
                break
    print(f"[TCP] Connection closed.")

async def broadcast_to_websockets(message):
    if clients:
        await asyncio.gather(*(client.send(message) for client in clients))

def find_json_files():
    """Find all JSON files in the captures folder."""
    if not os.path.exists(capture_folder):
        return []
    
    json_files = []
    for file_path in glob.glob(os.path.join(capture_folder, "*.json")):
        if os.path.basename(file_path) != ".gitkeep":
            json_files.append(file_path)
    
    # Sort by modification time (newest first)
    json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return json_files

def parse_json_file_new_batches_only(file_path):
    """Parse a JSON file and extract only NEW packets from unprocessed batches."""
    packets = []
    
    # Initialize tracking for this file if not exists
    if file_path not in file_batch_tracking:
        file_batch_tracking[file_path] = set()
    
    processed_batches = file_batch_tracking[file_path]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            
            if not content:
                return packets
            
            # Handle multi-line JSON objects (pretty printed)
            json_objects = []
            current_obj = ""
            brace_count = 0
            
            for char in content:
                current_obj += char
                
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # Complete JSON object found
                    if brace_count == 0:
                        json_objects.append(current_obj.strip())
                        current_obj = ""
            
            new_batches_found = 0
            
            for i, json_str in enumerate(json_objects):
                if not json_str:
                    continue
                
                try:
                    data = json.loads(json_str)
                    
                    # Skip file info headers
                    if 'file_info' in data:
                        continue
                    
                    # Handle batch format
                    if 'packets' in data and isinstance(data['packets'], list):
                        batch_number = data.get('batch_number', i)
                        batch_id = f"{file_path}_{batch_number}"
                        
                        # Only process if this batch hasn't been processed before
                        if batch_id not in processed_batches:
                            print(f"[JSON Parser] Processing NEW batch {batch_number} with {len(data['packets'])} packets")
                            new_batches_found += 1
                            
                            for packet in data['packets']:
                                # Transform packet to frontend format
                                transformed_packet = transform_packet_for_frontend(packet)
                                if transformed_packet:
                                    packets.append(transformed_packet)
                            
                            # Mark this batch as processed
                            processed_batches.add(batch_id)
                    
                    # Handle direct packet format
                    elif 'timestamp' in data and 'protocols' in data:
                        packet_id = f"{file_path}_direct_{i}"
                        if packet_id not in processed_batches:
                            print(f"[JSON Parser] Processing NEW direct packet")
                            transformed_packet = transform_packet_for_frontend(data)
                            if transformed_packet:
                                packets.append(transformed_packet)
                            processed_batches.add(packet_id)
                            
                except json.JSONDecodeError as e:
                    print(f"[JSON Parser] JSON decode error for object {i}: {e}")
                    continue
            
            if new_batches_found > 0:
                print(f"[JSON Parser] Found {new_batches_found} NEW batches with {len(packets)} total packets from {os.path.basename(file_path)}")
            
    except Exception as e:
        print(f"[ERROR] Error parsing JSON file {file_path}: {e}")
    
    return packets

def transform_packet_for_frontend(packet):
    """Transform packet data to frontend format."""
    try:
        # Get main protocol
        protocols = packet.get('protocols', [])
        main_protocol = 'UNKNOWN'
        
        priority = ['HTTP', 'HTTPS', 'DNS', 'TCP', 'UDP', 'ICMP', 'TLS']
        for p in priority:
            if any(p.lower() in proto.lower() for proto in protocols):
                main_protocol = p
                break
        
        if main_protocol == 'UNKNOWN' and protocols:
            main_protocol = protocols[0].upper()
        
        src = packet.get('source') or packet.get('src_ip', 'N/A')
        dst = packet.get('destination') or packet.get('dest_ip', 'N/A')
        sp = packet.get('source_port') or packet.get('src_port')
        dp = packet.get('destination_port') or packet.get('dest_port')
        return {
            "timestamp": packet.get('timestamp', ''),
            "protocol": main_protocol,
            "src_ip": src,
            "dest_ip": dst,
            "source": src,
            "destination": dst,
            "src_port": str(sp) if sp is not None else None,
            "dest_port": str(dp) if dp is not None else None,
            "source_port": str(sp) if sp is not None else None,
            "destination_port": str(dp) if dp is not None else None,
            "length": packet.get('length', 0),
            "info": packet.get('info', f"{main_protocol} packet")
        }
        
    except Exception as e:
        print(f"[ERROR] Error transforming packet: {e}")
        return None

async def stream_json_data():
    """Continuously monitor and stream JSON file data."""
    print(f"[JSON Monitor] Starting CONTINUOUS JSON file monitoring in {capture_folder}/")
    
    file_last_modified = {}  # Track file modification times
    
    while True:
        try:
            # Find JSON files
            json_files = find_json_files()
            
            if not json_files:
                print(f"[JSON Monitor] No JSON files found, waiting...")
                await asyncio.sleep(2)
                continue
            
            # Check each file for new data
            for file_path in json_files:
                try:
                    # Get current modification time
                    current_mtime = os.path.getmtime(file_path)
                    
                    # Check if file is new or has been modified
                    if file_path not in file_last_modified or current_mtime > file_last_modified[file_path]:
                        print(f"[JSON Monitor] Processing {'new' if file_path not in file_last_modified else 'updated'} file: {os.path.basename(file_path)}")
                        
                        # Parse and stream only NEW packets
                        packets = parse_json_file_new_batches_only(file_path)
                        
                        if packets:
                            recent_packets.extend(packets)
                        
                        if packets and clients:  # Only stream if there are connected clients
                            print(f"[JSON Monitor] Streaming {len(packets)} packets from {os.path.basename(file_path)}")
                            
                            # Stream packets with small delays for real-time effect
                            for i, packet in enumerate(packets):
                                packet_json = json.dumps(packet)
                                await broadcast_to_websockets(packet_json)
                                
                                # Small delay between packets for visual effect
                                if i % 5 == 0:  # Every 5 packets
                                    await asyncio.sleep(0.05)
                        
                        # Update last modified time
                        file_last_modified[file_path] = current_mtime
                        
                except Exception as e:
                    print(f"[JSON Monitor] Error processing file {file_path}: {e}")
                    continue
            
            # Wait before checking again (shorter interval for more responsiveness)
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"[JSON Monitor] Error: {e}")
            await asyncio.sleep(2)

def tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    try:
        server.bind(ADDR)
        server.listen()
        print(f"[TCP] Listening for data on all interfaces on port {PORT}")
        while True:
            try:
                conn, addr = server.accept()
                print(f"[TCP] Data connection from {addr}")
                threading.Thread(target=handle_tcp_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
    except Exception:
        pass
    finally:
        try:
            server.close()
        except Exception:
            pass

# --- HTTP SERVER LOGIC ---
def start_http_server():
    """Serves the index.html file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", HTTP_PORT), handler) as httpd:
        server_ip = get_local_ip()
        print("-" * 50)
        print(f"[HTTP] Web server running. Access the dashboard at: http://{server_ip}:{HTTP_PORT}")
        print("-" * 50)
        httpd.serve_forever()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    threading.Thread(target=run_websocket_server, daemon=True).start()
    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=tcp_server, daemon=True).start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        sys.exit(0)

