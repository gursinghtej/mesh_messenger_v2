"""
File and image sharing for mesh messenger
"""

import socket
import json
import threading
import base64
import os
import hashlib
from pathlib import Path
from datetime import datetime
from config import FILES_DIR, AVATAR_DIR, FILE_PORT, NODE_ID

class FileHandler:
    def __init__(self, gui_callback=None):
        self.gui_callback = gui_callback
        self.transfers = {}  # transfer_id -> transfer info
        self.running = True
        self.file_socket = None
        self.setup_file_socket()
    
    def setup_file_socket(self):
        """Setup separate socket for file transfers"""
        self.file_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.file_socket.bind(("0.0.0.0", FILE_PORT))
            self.file_socket.listen(5)
            threading.Thread(target=self._accept_connections, daemon=True).start()
        except Exception as e:
            print(f"File socket error: {e}")
    
    def _accept_connections(self):
        """Accept incoming file transfer connections"""
        while self.running:
            try:
                client_socket, addr = self.file_socket.accept()
                threading.Thread(target=self._receive_file, args=(client_socket, addr), daemon=True).start()
            except:
                pass
    
    def send_file(self, peer_ip, file_path, peer_id):
        """Send a file to a peer"""
        if not os.path.exists(file_path):
            return None
        
        transfer_id = hashlib.md5(f"{file_path}{datetime.now()}".encode()).hexdigest()[:8]
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # Determine content type
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            content_type = 'image'
        elif ext in ['.mp3', '.wav', '.ogg']:
            content_type = 'audio'
        else:
            content_type = 'file'
        
        # Start transfer in background
        threading.Thread(target=self._send_file_thread, 
                        args=(peer_ip, file_path, file_name, file_size, content_type, transfer_id, peer_id), 
                        daemon=True).start()
        
        return transfer_id
    
    def _send_file_thread(self, peer_ip, file_path, file_name, file_size, content_type, transfer_id, peer_id):
        """Background thread for sending file"""
        try:
            # Connect to peer's file socket
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(30)
            client.connect((peer_ip, FILE_PORT))
            
            # Send header
            header = {
                "type": "file_transfer",
                "transfer_id": transfer_id,
                "from": NODE_ID,
                "filename": file_name,
                "size": file_size,
                "content_type": content_type
            }
            header_json = json.dumps(header).encode()
            client.send(len(header_json).to_bytes(4, 'big'))
            client.send(header_json)
            
            # Send file data with progress
            sent = 0
            chunk_size = 8192
            
            with open(file_path, 'rb') as f:
                while sent < file_size:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    client.send(chunk)
                    sent += len(chunk)
                    
                    # Progress callback
                    if self.gui_callback:
                        progress = (sent / file_size) * 100
                        self.gui_callback("file_progress", {
                            "transfer_id": transfer_id,
                            "progress": progress,
                            "peer_id": peer_id
                        })
            
            client.close()
            
            if self.gui_callback:
                self.gui_callback("file_sent", {
                    "transfer_id": transfer_id,
                    "filename": file_name,
                    "peer_id": peer_id
                })
                
        except Exception as e:
            if self.gui_callback:
                self.gui_callback("file_error", {
                    "transfer_id": transfer_id,
                    "error": str(e)
                })
    
    def _receive_file(self, client_socket, addr):
        """Receive an incoming file"""
        try:
            # Receive header length
            header_len_bytes = client_socket.recv(4)
            if not header_len_bytes:
                return
            header_len = int.from_bytes(header_len_bytes, 'big')
            
            # Receive header
            header_json = b''
            while len(header_json) < header_len:
                chunk = client_socket.recv(header_len - len(header_json))
                if not chunk:
                    return
                header_json += chunk
            
            header = json.loads(header_json.decode())
            
            transfer_id = header["transfer_id"]
            filename = header["filename"]
            file_size = header["size"]
            content_type = header["content_type"]
            from_id = header["from"]
            
            # Determine save directory
            if content_type == 'image':
                save_dir = FILES_DIR / "images"
            elif content_type == 'audio':
                save_dir = FILES_DIR / "audio"
            else:
                save_dir = FILES_DIR / "documents"
            
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            name, ext = os.path.splitext(filename)
            save_path = save_dir / f"{name}_{transfer_id}{ext}"
            
            # Receive file data
            received = 0
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk = client_socket.recv(min(8192, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    
                    # Progress callback
                    if self.gui_callback:
                        progress = (received / file_size) * 100
                        self.gui_callback("file_progress", {
                            "transfer_id": transfer_id,
                            "progress": progress,
                            "from_id": from_id
                        })
            
            client_socket.close()
            
            if self.gui_callback:
                self.gui_callback("file_received", {
                    "transfer_id": transfer_id,
                    "filename": filename,
                    "path": str(save_path),
                    "from_id": from_id,
                    "content_type": content_type
                })
                
        except Exception as e:
            print(f"File receive error: {e}")
    
    def send_image(self, peer_ip, image_path, peer_id):
        """Send an image (uses same file transfer with type detection)"""
        return self.send_file(peer_ip, image_path, peer_id)
    
    def stop(self):
        self.running = False
        if self.file_socket:
            self.file_socket.close()