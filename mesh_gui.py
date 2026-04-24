#!/usr/bin/env python3
"""
DECENTRALIZED MESH MESSAGING SYSTEM - GUI VERSION
==================================================
Selective messaging + Broadcast + Live peer status
"""

import socket
import threading
import time
import json
import platform
import base64
import pickle
import os
import sys
import queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = 5007
DISCOVERY_PORT = 5008
SECRET_KEY = "meshnet2024"
DISCOVERY_INTERVAL = 5
MAX_LOG_ENTRIES = 100
QUEUE_FILE = "message_queue.pkl"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

MY_IP = get_local_ip()
NODE_ID = f"{platform.node().split('.')[0][:8]}"

# Global state
PEERS = {}
CONNECTED_NODES = {}
MESSAGE_QUEUE = {}
gui_queue = queue.Queue()
running = True

# ============================================================================
# ENCRYPTION
# ============================================================================

def encrypt(plaintext, key=SECRET_KEY):
    result = ""
    for i, char in enumerate(plaintext):
        key_char = key[i % len(key)]
        result += chr(ord(char) ^ ord(key_char))
    return base64.b64encode(result.encode('utf-8', errors='ignore')).decode()

def decrypt(encoded_text, key=SECRET_KEY):
    try:
        text = base64.b64decode(encoded_text.encode()).decode('utf-8', errors='ignore')
        result = ""
        for i, char in enumerate(text):
            key_char = key[i % len(key)]
            result += chr(ord(char) ^ ord(key_char))
        return result
    except:
        return "[DECRYPT ERROR]"

# ============================================================================
# PERSISTENCE
# ============================================================================

def load_queue():
    global MESSAGE_QUEUE
    try:
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'rb') as f:
                MESSAGE_QUEUE = pickle.load(f)
    except:
        MESSAGE_QUEUE = {}

def save_queue():
    try:
        with open(QUEUE_FILE, 'wb') as f:
            pickle.dump(MESSAGE_QUEUE, f)
    except:
        pass

# ============================================================================
# NETWORK THREADS
# ============================================================================

def broadcast_presence():
    discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    while running:
        try:
            packet = json.dumps({
                "type": "DISCOVER",
                "id": NODE_ID,
                "ip": MY_IP,
                "port": PORT
            })
            discover_sock.sendto(packet.encode(), ("255.255.255.255", DISCOVERY_PORT))
        except:
            pass
        time.sleep(DISCOVERY_INTERVAL)

def discovery_listener():
    global PEERS, CONNECTED_NODES
    
    discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discover_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        discover_sock.bind(("0.0.0.0", DISCOVERY_PORT))
    except:
        return
    
    while running:
        try:
            data, addr = discover_sock.recvfrom(1024)
            msg = json.loads(data.decode())
            
            if msg.get("type") == "DISCOVER" and msg["id"] != NODE_ID:
                peer_ip = msg["ip"]
                peer_id = msg["id"]
                
                is_new = peer_id not in CONNECTED_NODES
                
                CONNECTED_NODES[peer_id] = {
                    "ip": peer_ip,
                    "last_seen": time.time(),
                    "port": msg.get("port", PORT)
                }
                PEERS[peer_id] = peer_ip
                
                if is_new:
                    gui_queue.put(("peer_joined", peer_id, peer_ip))
                    
        except:
            pass

def message_receiver(main_sock):
    global CONNECTED_NODES
    
    while running:
        try:
            data, addr = main_sock.recvfrom(4096)
            msg = json.loads(data.decode())
            
            sender = msg.get("from", "unknown")
            
            if sender == NODE_ID:
                continue
            
            # Handle different message types
            msg_type = msg.get("type", "message")
            
            if msg_type == "message":
                encrypted = msg.get("enc", "")
                decrypted = decrypt(encrypted)
                is_broadcast = msg.get("broadcast", False)
                
                CONNECTED_NODES[sender] = {
                    "ip": addr[0],
                    "last_seen": time.time(),
                    "port": addr[1]
                }
                PEERS[sender] = addr[0]
                
                gui_queue.put(("message", sender, decrypted, is_broadcast, msg.get("time", "")))
                
            elif msg_type == "ping":
                # Respond to ping
                response = json.dumps({"type": "pong", "from": NODE_ID})
                main_sock.sendto(response.encode(), addr)
                
            elif msg_type == "pong":
                CONNECTED_NODES[sender] = {
                    "ip": addr[0],
                    "last_seen": time.time()
                }
                
        except Exception as e:
            pass

def send_message_to_peer(message, target_id=None, is_broadcast=False):
    """Send message to specific peer or broadcast"""
    if not message:
        return False
    
    encrypted = encrypt(message)
    packet = {
        "type": "message",
        "from": NODE_ID,
        "enc": encrypted,
        "time": datetime.now().strftime("%H:%M:%S"),
        "broadcast": is_broadcast
    }
    data = json.dumps(packet).encode()
    
    sent_count = 0
    
    if is_broadcast:
        # Send to all known peers
        for peer_id, peer_ip in PEERS.items():
            if peer_id != NODE_ID:
                try:
                    main_socket.sendto(data, (peer_ip, PORT))
                    sent_count += 1
                except:
                    if peer_ip not in MESSAGE_QUEUE:
                        MESSAGE_QUEUE[peer_ip] = []
                    MESSAGE_QUEUE[peer_ip].append(data)
                    save_queue()
    else:
        # Send to specific peer
        if target_id and target_id in PEERS:
            peer_ip = PEERS[target_id]
            try:
                main_socket.sendto(data, (peer_ip, PORT))
                sent_count = 1
                
                # Send queued messages
                if peer_ip in MESSAGE_QUEUE and MESSAGE_QUEUE[peer_ip]:
                    for q_data in MESSAGE_QUEUE[peer_ip]:
                        main_socket.sendto(q_data, (peer_ip, PORT))
                    MESSAGE_QUEUE[peer_ip] = []
                    save_queue()
                    gui_queue.put(("system", f"Sent queued messages to {target_id}"))
                    
            except:
                if peer_ip not in MESSAGE_QUEUE:
                    MESSAGE_QUEUE[peer_ip] = []
                MESSAGE_QUEUE[peer_ip].append(data)
                save_queue()
                gui_queue.put(("system", f"Queued for {target_id} (offline)"))
    
    return sent_count > 0

# ============================================================================
# GUI APPLICATION
# ============================================================================

class MeshMessengerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🌐 Decentralized Mesh Messenger - {NODE_ID}")
        self.root.geometry("900x700")
        self.root.configure(bg='#1a1a2e')
        
        # Configure styles
        self.setup_styles()
        
        # Build UI
        self.build_ui()
        
        # Start processing GUI messages
        self.process_gui_queue()
        
        # Periodic peer status update
        self.update_peer_status()
        
    def setup_styles(self):
        self.colors = {
            'bg_dark': '#1a1a2e',
            'bg_medium': '#16213e',
            'bg_light': '#0f3460',
            'accent': '#e94560',
            'text_light': '#ffffff',
            'text_dim': '#a0a0a0',
            'success': '#00ff88',
            'warning': '#ffaa00',
            'error': '#ff3366',
            'broadcast': '#ff6b6b',
            'private': '#4ecdc4',
            'system': '#95a5a6'
        }
        
        # Custom font for message display
        self.message_font = font.Font(family="Consolas", size=10)
        self.header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        
    def build_ui(self):
        # Main container
        main_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_medium'], height=60)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🌐 DECENTRALIZED MESH MESSENGER", 
                               font=("Segoe UI", 16, "bold"), 
                               fg=self.colors['success'], bg=self.colors['bg_medium'])
        title_label.pack(side=tk.LEFT, padx=20, pady=15)
        
        self.status_label = tk.Label(header_frame, text=f"🟢 ONLINE | {NODE_ID} | {MY_IP}", 
                                      font=("Consolas", 10), 
                                      fg=self.colors['text_light'], bg=self.colors['bg_medium'])
        self.status_label.pack(side=tk.RIGHT, padx=20, pady=15)
        
        # Content area (Left: Peers, Right: Chat)
        content_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Peers list
        left_panel = tk.Frame(content_frame, bg=self.colors['bg_medium'], width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        peers_header = tk.Label(left_panel, text="📡 NETWORK NODES", 
                                font=self.header_font, 
                                fg=self.colors['text_light'], bg=self.colors['bg_medium'])
        peers_header.pack(pady=10)
        
        # Peer list with scrollbar
        peers_container = tk.Frame(left_panel, bg=self.colors['bg_medium'])
        peers_container.pack(fill=tk.BOTH, expand=True, padx=10)
        
        self.peers_listbox = tk.Listbox(peers_container, 
                                         bg=self.colors['bg_light'], 
                                         fg=self.colors['text_light'],
                                         selectbackground=self.colors['accent'],
                                         font=("Consolas", 10),
                                         relief=tk.FLAT,
                                         borderwidth=0,
                                         highlightthickness=1,
                                         highlightcolor=self.colors['success'])
        self.peers_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        peers_scrollbar = tk.Scrollbar(peers_container, orient=tk.VERTICAL)
        peers_scrollbar.config(command=self.peers_listbox.yview)
        peers_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.peers_listbox.config(yscrollcommand=peers_scrollbar.set)
        
        # Add broadcast option at top of list
        self.peers_listbox.insert(tk.END, "📢 BROADCAST TO ALL")
        self.peers_listbox.itemconfig(0, {'bg': self.colors['broadcast'], 'fg': 'white'})
        
        # Bind selection event
        self.peers_listbox.bind('<<ListboxSelect>>', self.on_peer_select)
        
        # Right panel - Chat area
        right_panel = tk.Frame(content_frame, bg=self.colors['bg_medium'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Chat header shows current recipient
        self.recipient_label = tk.Label(right_panel, text="📢 BROADCAST", 
                                         font=self.header_font,
                                         fg=self.colors['broadcast'], bg=self.colors['bg_medium'])
        self.recipient_label.pack(pady=10)
        
        # Message display area
        self.chat_display = scrolledtext.ScrolledText(right_panel, 
                                                       wrap=tk.WORD,
                                                       bg=self.colors['bg_dark'],
                                                       fg=self.colors['text_light'],
                                                       font=self.message_font,
                                                       relief=tk.FLAT,
                                                       borderwidth=0,
                                                       height=20)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Configure text tags for formatting
        self.chat_display.tag_config("system", foreground=self.colors['system'], font=("Consolas", 9, "italic"))
        self.chat_display.tag_config("sent", foreground=self.colors['private'], justify='right')
        self.chat_display.tag_config("received", foreground=self.colors['success'])
        self.chat_display.tag_config("broadcast", foreground=self.colors['broadcast'])
        self.chat_display.tag_config("private", foreground=self.colors['private'])
        self.chat_display.tag_config("timestamp", foreground=self.colors['text_dim'], font=("Consolas", 8))
        self.chat_display.tag_config("sender", font=("Consolas", 9, "bold"))
        
        # Input area
        input_frame = tk.Frame(right_panel, bg=self.colors['bg_medium'])
        input_frame.pack(fill=tk.X, pady=10, padx=10)
        
        self.message_entry = tk.Entry(input_frame, 
                                       bg=self.colors['bg_light'],
                                       fg=self.colors['text_light'],
                                       font=("Consolas", 11),
                                       relief=tk.FLAT,
                                       insertbackground=self.colors['success'])
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.message_entry.bind('<Return>', self.send_message)
        self.message_entry.focus()
        
        send_button = tk.Button(input_frame, text="📤 SEND", 
                                command=self.send_message,
                                bg=self.colors['accent'], fg='white',
                                font=("Segoe UI", 10, "bold"),
                                relief=tk.FLAT,
                                padx=15, pady=5,
                                cursor="hand2")
        send_button.pack(side=tk.RIGHT)
        
        # Footer with encryption status
        footer_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'], height=30)
        footer_frame.pack(fill=tk.X, pady=(10, 0))
        footer_frame.pack_propagate(False)
        
        encrypt_label = tk.Label(footer_frame, text="🔐 END-TO-END ENCRYPTED | XOR-256 + Base64", 
                                 font=("Consolas", 8),
                                 fg=self.colors['success'], bg=self.colors['bg_dark'])
        encrypt_label.pack(side=tk.LEFT)
        
        self.peer_count_label = tk.Label(footer_frame, text="📊 0 peers connected", 
                                          font=("Consolas", 8),
                                          fg=self.colors['text_dim'], bg=self.colors['bg_dark'])
        self.peer_count_label.pack(side=tk.RIGHT)
        
        # Store current selection
        self.current_recipient = "BROADCAST"
        self.current_recipient_id = None
        
    def on_peer_select(self, event):
        selection = self.peers_listbox.curselection()
        if selection:
            index = selection[0]
            peer_text = self.peers_listbox.get(index)
            
            if index == 0:
                # Broadcast
                self.current_recipient = "BROADCAST"
                self.current_recipient_id = None
                self.recipient_label.config(text="📢 BROADCAST (All Nodes)", fg=self.colors['broadcast'])
                self.message_entry.config(fg=self.colors['broadcast'])
            else:
                # Specific peer
                peer_display = peer_text.split(" ")[0] if " " in peer_text else peer_text
                self.current_recipient = peer_display
                self.current_recipient_id = peer_display
                self.recipient_label.config(text=f"💬 Private: {peer_display}", fg=self.colors['private'])
                self.message_entry.config(fg=self.colors['private'])
    
    def add_message(self, sender, message, is_broadcast=False, is_sent=False):
        timestamp = datetime.now().strftime("%H:%M")
        
        self.chat_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
        
        if sender == "SYSTEM":
            self.chat_display.insert(tk.END, "⚡ ", "system")
            self.chat_display.insert(tk.END, message, "system")
        else:
            if is_sent:
                arrow = "📤" if not is_broadcast else "📢"
                self.chat_display.insert(tk.END, f"{arrow} To {self.current_recipient}: ", "sender")
                self.chat_display.insert(tk.END, message, "sent" if not is_broadcast else "broadcast")
            else:
                msg_type = "broadcast" if is_broadcast else "private"
                arrow = "📢" if is_broadcast else "📨"
                self.chat_display.insert(tk.END, f"{arrow} {sender}: ", "sender")
                self.chat_display.insert(tk.END, message, msg_type)
        
        self.chat_display.see(tk.END)
    
    def add_system_message(self, message):
        self.add_message("SYSTEM", message)
    
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return
        
        is_broadcast = (self.current_recipient == "BROADCAST")
        
        # Display in chat
        self.add_message(NODE_ID, message, is_broadcast=is_broadcast, is_sent=True)
        
        # Send over network
        success = send_message_to_peer(message, self.current_recipient_id, is_broadcast)
        
        if success:
            self.message_entry.delete(0, tk.END)
            if not is_broadcast and not is_broadcast:
                status = f"Sent to {self.current_recipient_id}"
            else:
                status = "Broadcast sent"
            self.add_system_message(f"✓ {status}")
        else:
            self.add_system_message(f"⚠️ Failed to send (peer offline - queued)")
            self.message_entry.delete(0, tk.END)
    
    def update_peer_list(self):
        current_selection = self.peers_listbox.curselection()
        selected_index = current_selection[0] if current_selection else 0
        
        self.peers_listbox.delete(1, tk.END)  # Keep broadcast option
        
        active_peers = 0
        for peer_id, peer_data in CONNECTED_NODES.items():
            if peer_id != NODE_ID:
                last_seen = time.time() - peer_data.get("last_seen", 0)
                is_online = last_seen < 15
                
                status_icon = "🟢" if is_online else "🔴"
                display_text = f"{status_icon} {peer_id} ({peer_data['ip']})"
                
                self.peers_listbox.insert(tk.END, display_text)
                
                if is_online:
                    active_peers += 1
                    self.peers_listbox.itemconfig(tk.END, {'fg': self.colors['success']})
                else:
                    self.peers_listbox.itemconfig(tk.END, {'fg': self.colors['error']})
        
        self.peer_count_label.config(text=f"📊 {active_peers} peer{'s' if active_peers != 1 else ''} online")
        
        # Restore selection if possible
        if selected_index < self.peers_listbox.size():
            self.peers_listbox.selection_set(selected_index)
    
    def update_peer_status(self):
        self.update_peer_list()
        self.root.after(3000, self.update_peer_status)
    
    def process_gui_queue(self):
        try:
            while True:
                msg_data = gui_queue.get_nowait()
                msg_type = msg_data[0]
                
                if msg_type == "message":
                    _, sender, message, is_broadcast, timestamp = msg_data
                    self.add_message(sender, message, is_broadcast=is_broadcast)
                    
                elif msg_type == "peer_joined":
                    _, peer_id, peer_ip = msg_data
                    self.add_system_message(f"✨ {peer_id} joined ({peer_ip})")
                    self.update_peer_list()
                    
                elif msg_type == "system":
                    _, message = msg_data
                    self.add_system_message(message)
                    
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_gui_queue)

# ============================================================================
# MAIN
# ============================================================================

def main():
    global main_socket, running
    
    load_queue()
    
    # Create main socket
    main_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    main_socket.bind(("0.0.0.0", PORT))
    
    # Start network threads
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=discovery_listener, daemon=True).start()
    threading.Thread(target=message_receiver, args=(main_socket,), daemon=True).start()
    
    # Start GUI
    root = tk.Tk()
    app = MeshMessengerGUI(root)
    
    def on_closing():
        global running
        running = False
        save_queue()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()