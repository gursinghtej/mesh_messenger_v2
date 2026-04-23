"""
Reliable messaging with ACK, retry, and delivery confirmation
"""

import socket
import json
import threading
import time
import queue
import uuid
from datetime import datetime
from config import PORT, ACK_TIMEOUT, MAX_RETRIES, NODE_ID, profile
from storage.database import db

class ReliableTransport:
    def __init__(self, main_socket, gui_callback=None):
        self.socket = main_socket
        self.gui_callback = gui_callback
        self.pending_messages = {}  # msg_id -> {packet, retries, callback}
        self.message_queue = queue.Queue()
        self.running = True
        self.lock = threading.Lock()
        
        # Start retry thread
        self.retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.start()
        
        # Start queue processor
        self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.queue_thread.start()
    
    def send_message(self, peer_id, peer_ip, content, content_type='text', 
                     file_path=None, is_broadcast=False):
        """Send a message with guaranteed delivery via ACK"""
        msg_id = str(uuid.uuid4())[:8]
        
        packet = {
            "type": "message",
            "id": msg_id,
            "from": NODE_ID,
            "from_username": profile.username,
            "to": peer_id,
            "content": content,
            "content_type": content_type,
            "timestamp": datetime.now().timestamp(),
            "broadcast": is_broadcast,
            "requires_ack": True,
            "file_path": file_path
        }
        
        # Save to database
        db.save_message(msg_id, peer_id, NODE_ID, content, content_type, file_path)
        
        if is_broadcast:
            # Broadcast doesn't wait for ACK from all
            self._send_packet(packet, peer_ip, is_broadcast=True)
        else:
            # Store for ACK tracking
            with self.lock:
                self.pending_messages[msg_id] = {
                    "packet": packet,
                    "peer_ip": peer_ip,
                    "retries": 0,
                    "sent_time": time.time()
                }
            self._send_packet(packet, peer_ip)
        
        return msg_id
    
    def _send_packet(self, packet, peer_ip, is_broadcast=False):
        """Send a single packet"""
        try:
            data = json.dumps(packet).encode()
            if is_broadcast:
                # In broadcast mode, we'd send to all peers
                # For now, just to the specified IP
                pass
            self.socket.sendto(data, (peer_ip, PORT))
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def handle_ack(self, msg_id):
        """Handle incoming ACK"""
        with self.lock:
            if msg_id in self.pending_messages:
                packet = self.pending_messages[msg_id]["packet"]
                peer_id = packet["to"]
                
                # Update database - delivered
                db.update_message_status(msg_id, is_delivered=True)
                
                # Notify GUI
                if self.gui_callback:
                    self.gui_callback("delivered", {"msg_id": msg_id, "peer_id": peer_id})
                
                del self.pending_messages[msg_id]
                print(f"✓ Message {msg_id} delivered to {peer_id}")
    
    def handle_read_receipt(self, msg_id, peer_id):
        """Handle read receipt"""
        db.update_message_status(msg_id, is_read=True)
        if self.gui_callback:
            self.gui_callback("read", {"msg_id": msg_id, "peer_id": peer_id})
    
    def _retry_loop(self):
        """Retry unacked messages"""
        while self.running:
            time.sleep(1)
            with self.lock:
                to_remove = []
                for msg_id, info in self.pending_messages.items():
                    if time.time() - info["sent_time"] > ACK_TIMEOUT:
                        if info["retries"] < MAX_RETRIES:
                            info["retries"] += 1
                            info["sent_time"] = time.time()
                            self._send_packet(info["packet"], info["peer_ip"])
                            print(f"↻ Retry {info['retries']} for {msg_id}")
                        else:
                            # Max retries exceeded
                            to_remove.append(msg_id)
                            if self.gui_callback:
                                self.gui_callback("failed", {"msg_id": msg_id})
                
                for msg_id in to_remove:
                    del self.pending_messages[msg_id]
    
    def _process_queue(self):
        """Process queued messages"""
        while self.running:
            try:
                msg_data = self.message_queue.get(timeout=1)
                peer_id, peer_ip, content, content_type, file_path = msg_data
                self.send_message(peer_id, peer_ip, content, content_type, file_path)
            except queue.Empty:
                pass
    
    def queue_message(self, peer_id, peer_ip, content, content_type='text', file_path=None):
        """Queue message for later sending (when peer comes online)"""
        self.message_queue.put((peer_id, peer_ip, content, content_type, file_path))
    
    def send_ack(self, msg_id, peer_ip, from_id):
        """Send acknowledgment for received message"""
        ack_packet = {
            "type": "ack",
            "id": msg_id,
            "from": NODE_ID,
            "to": from_id
        }
        self._send_packet(ack_packet, peer_ip)
    
    def send_read_receipt(self, msg_id, peer_ip, from_id):
        """Send read receipt"""
        read_packet = {
            "type": "read",
            "id": msg_id,
            "from": NODE_ID,
            "to": from_id
        }
        self._send_packet(read_packet, peer_ip)
    
    def stop(self):
        self.running = False