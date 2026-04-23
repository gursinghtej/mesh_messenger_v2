"""
Smart peer discovery with multicast
"""

import socket
import json
import threading
import time
from config import DISCOVERY_PORT, DISCOVERY_INTERVAL, MULTICAST_GROUP, USE_MULTICAST, MY_IP, NODE_ID, PORT, profile
from storage.database import db

def start_discovery(transport, gui_app=None):
    """Start discovery threads"""
    
    def broadcast_presence():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while True:
            try:
                packet = json.dumps({
                    "type": "DISCOVER",
                    "id": NODE_ID,
                    "username": profile.username,
                    "ip": MY_IP,
                    "port": PORT,
                    "status": profile.status
                })
                
                if USE_MULTICAST:
                    sock.sendto(packet.encode(), (MULTICAST_GROUP, DISCOVERY_PORT))
                else:
                    sock.sendto(packet.encode(), ("255.255.255.255", DISCOVERY_PORT))
            except:
                pass
            time.sleep(DISCOVERY_INTERVAL)
    
    def discovery_listener():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
        except:
            return
        
        if USE_MULTICAST:
            import struct
            mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if msg.get("type") == "DISCOVER" and msg["id"] != NODE_ID:
                    peer_id = msg["id"]
                    username = msg.get("username", peer_id)
                    peer_ip = msg["ip"]
                    status = msg.get("status", "Unknown")
                    
                    # Add/update in database
                    db.add_or_update_peer(peer_id, username, peer_ip, status)
                    
                    # Notify GUI
                    if gui_app:
                        gui_app.gui_queue.put(("network", "peer_discovered", {
                            "peer_id": peer_id,
                            "username": username,
                            "ip": peer_ip
                        }))
            except:
                pass
    
    threading.Thread(target=discovery_listener, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()