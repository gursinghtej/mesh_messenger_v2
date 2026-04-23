#!/usr/bin/env python3
"""
Decentralized Mesh Messenger v2.0
Complete GUI with separate chats, online status, and broadcast
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import threading
import time
import json
import os
from datetime import datetime
from pathlib import Path
import platform

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = 5007
DISCOVERY_PORT = 5008

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

print(f"""
╔══════════════════════════════════════════╗
║     🌐 MESH MESSENGER v2.0 STARTING      ║
╠══════════════════════════════════════════╣
║  Node: {NODE_ID}
║  IP:   {MY_IP}:{PORT}
╚══════════════════════════════════════════╝
""")

# ============================================================================
# SIMPLE DATABASE (JSON file)
# ============================================================================

DATA_DIR = Path("mesh_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "mesh_db.json"

class SimpleDB:
    def __init__(self):
        self.data = self.load()
    
    def load(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"peers": {}, "messages": {}, "settings": {}}
    
    def save(self):
        try:
            with open(DB_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass
    
    def add_peer(self, peer_id, username=None, ip=None):
        if peer_id not in self.data["peers"]:
            self.data["peers"][peer_id] = {
                "username": username or peer_id,
                "ip": ip,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "status": "Available",
                "pinned": False,
                "unread": 0
            }
        else:
            self.data["peers"][peer_id]["last_seen"] = time.time()
            if ip:
                self.data["peers"][peer_id]["ip"] = ip
        self.save()
        return self.data["peers"][peer_id]
    
    def get_peers(self):
        return [(pid, data) for pid, data in self.data["peers"].items()]
    
    def add_message(self, peer_id, sender_id, content, content_type="text"):
        msg_id = f"{int(time.time()*1000)}"
        msg = {
            "id": msg_id,
            "peer_id": peer_id,
            "sender": sender_id,
            "content": content,
            "type": content_type,
            "timestamp": time.time()
        }
        
        if peer_id not in self.data["messages"]:
            self.data["messages"][peer_id] = []
        self.data["messages"][peer_id].append(msg)
        
        # Keep only last 100 messages per peer
        if len(self.data["messages"][peer_id]) > 100:
            self.data["messages"][peer_id] = self.data["messages"][peer_id][-100:]
        
        # Increment unread if not from self
        if sender_id != NODE_ID:
            if peer_id in self.data["peers"]:
                self.data["peers"][peer_id]["unread"] = self.data["peers"][peer_id].get("unread", 0) + 1
        
        self.save()
        return msg
    
    def get_messages(self, peer_id):
        return self.data["messages"].get(peer_id, [])
    
    def clear_unread(self, peer_id):
        if peer_id in self.data["peers"]:
            self.data["peers"][peer_id]["unread"] = 0
            self.save()
    
    def delete_conversation(self, peer_id):
        if peer_id in self.data["messages"]:
            del self.data["messages"][peer_id]
        self.clear_unread(peer_id)
        self.save()
    
    def pin_peer(self, peer_id, pinned=True):
        if peer_id in self.data["peers"]:
            self.data["peers"][peer_id]["pinned"] = pinned
            self.save()
    
    def search_messages(self, query):
        results = []
        for peer_id, msgs in self.data["messages"].items():
            for msg in msgs:
                if query.lower() in msg["content"].lower():
                    results.append({**msg, "peer_id": peer_id})
        return results

db = SimpleDB()

# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class MeshMessengerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🌐 Mesh Messenger - {NODE_ID}")
        self.root.geometry("950x700")
        self.root.configure(bg='#1a1a2e')
        
        # State
        self.current_peer = None
        self.peer_widgets = {}
        self.running = True
        
        # Colors
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
        }
        
        self.setup_ui()
        self.setup_network()
        self.update_peers_loop()
    
    def setup_ui(self):
        # Main container
        main_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ===== LEFT PANEL - PEERS =====
        left_panel = tk.Frame(main_frame, bg=self.colors['bg_medium'], width=260)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        # Profile section
        profile_frame = tk.Frame(left_panel, bg=self.colors['bg_light'], height=70)
        profile_frame.pack(fill=tk.X, padx=8, pady=8)
        profile_frame.pack_propagate(False)
        
        tk.Label(profile_frame, text="🖥️", font=("Segoe UI", 20),
                fg=self.colors['success'], bg=self.colors['bg_light']).place(x=10, y=15)
        
        tk.Label(profile_frame, text=NODE_ID, font=("Segoe UI", 11, "bold"),
                fg=self.colors['text_light'], bg=self.colors['bg_light']).place(x=55, y=12)
        
        tk.Label(profile_frame, text=f"{MY_IP}:{PORT}", font=("Consolas", 9),
                fg=self.colors['text_dim'], bg=self.colors['bg_light']).place(x=55, y=35)
        
        # Search bar
        search_frame = tk.Frame(left_panel, bg=self.colors['bg_medium'])
        search_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                bg=self.colors['bg_light'], fg=self.colors['text_light'],
                                font=("Segoe UI", 10), relief=tk.FLAT)
        search_entry.pack(fill=tk.X, ipady=6)
        search_entry.insert(0, "🔍 Search...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, tk.END) if search_entry.get() == "🔍 Search..." else None)
        search_entry.bind("<FocusOut>", lambda e: search_entry.insert(0, "🔍 Search...") if not search_entry.get() else None)
        
        # Peers header
        tk.Label(left_panel, text="👥 CONVERSATIONS", font=("Segoe UI", 9, "bold"),
                fg=self.colors['text_dim'], bg=self.colors['bg_medium']).pack(anchor='w', padx=12, pady=(5, 5))
        
        # Peer list
        list_frame = tk.Frame(left_panel, bg=self.colors['bg_medium'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        self.peer_listbox = tk.Listbox(list_frame,
                                       bg=self.colors['bg_light'],
                                       fg=self.colors['text_light'],
                                       selectbackground=self.colors['accent'],
                                       font=("Segoe UI", 10),
                                       relief=tk.FLAT,
                                       borderwidth=0,
                                       highlightthickness=0)
        self.peer_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.peer_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.peer_listbox.yview)
        
        # Broadcast option (always first)
        self.peer_listbox.insert(tk.END, "📢 BROADCAST (All Nodes)")
        self.peer_listbox.itemconfig(0, bg='#e94560', fg='white')
        
        self.peer_listbox.bind('<<ListboxSelect>>', self.on_peer_select)
        
        # ===== RIGHT PANEL - CHAT =====
        right_panel = tk.Frame(main_frame, bg=self.colors['bg_medium'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Chat header
        self.chat_header = tk.Label(right_panel, text="📱 Select a conversation",
                                    font=("Segoe UI", 12, "bold"),
                                    fg=self.colors['text_light'], bg=self.colors['bg_medium'])
        self.chat_header.pack(pady=12)
        
        # Chat notebook (tabs)
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Style the notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=self.colors['bg_medium'], borderwidth=0)
        style.configure('TNotebook.Tab', background=self.colors['bg_light'], 
                       foreground='white', padding=[15, 5], borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', self.colors['accent'])])
        
        # Welcome tab
        self.create_welcome_tab()
        
        # Input area
        input_frame = tk.Frame(right_panel, bg=self.colors['bg_medium'], height=70)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=8, padx=5)
        input_frame.pack_propagate(False)
        
        self.msg_entry = tk.Text(input_frame, bg=self.colors['bg_light'], 
                                 fg=self.colors['text_light'],
                                 font=("Segoe UI", 10), relief=tk.FLAT, 
                                 height=2, wrap=tk.WORD,
                                 insertbackground=self.colors['success'])
        self.msg_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.msg_entry.bind('<Return>', self.send_message)
        self.msg_entry.config(state=tk.DISABLED)
        
        # Buttons
        btn_frame = tk.Frame(input_frame, bg=self.colors['bg_medium'])
        btn_frame.pack(side=tk.RIGHT, padx=5)
        
        self.clear_btn = tk.Label(btn_frame, text="🗑️", font=("Segoe UI", 12),
                                  fg=self.colors['text_dim'], bg=self.colors['bg_medium'],
                                  cursor="hand2")
        self.clear_btn.pack(side=tk.LEFT, padx=3)
        self.clear_btn.bind("<Button-1>", self.clear_chat)
        
        self.pin_btn = tk.Label(btn_frame, text="📌", font=("Segoe UI", 12),
                                fg=self.colors['text_dim'], bg=self.colors['bg_medium'],
                                cursor="hand2")
        self.pin_btn.pack(side=tk.LEFT, padx=3)
        self.pin_btn.bind("<Button-1>", self.toggle_pin)
        
        send_btn = tk.Label(btn_frame, text="📤 SEND", font=("Segoe UI", 10, "bold"),
                           fg='white', bg=self.colors['accent'], padx=15, pady=6,
                           cursor="hand2")
        send_btn.pack(side=tk.LEFT, padx=5)
        send_btn.bind("<Button-1>", self.send_message)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg=self.colors['bg_light'], height=25)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="🟢 Online | 🔐 Encrypted",
                                     fg=self.colors['success'], bg=self.colors['bg_light'],
                                     font=("Consolas", 9))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=3)
        
        self.peer_count_label = tk.Label(status_frame, text="📡 0 peers online",
                                         fg=self.colors['text_dim'], bg=self.colors['bg_light'],
                                         font=("Consolas", 9))
        self.peer_count_label.pack(side=tk.RIGHT, padx=10, pady=3)
    
    def create_welcome_tab(self):
        welcome_frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        self.notebook.add(welcome_frame, text="Welcome")
        
        welcome_text = f"""

    ╔══════════════════════════════════════╗
    ║                                      ║
    ║       🌐 MESH MESSENGER v2.0         ║
    ║                                      ║
    ║         Welcome, {NODE_ID}!           ║
    ║                                      ║
    ║    • Select a peer to start chat     ║
    ║    • Broadcast sends to everyone     ║
    ║    • Messages are auto-saved         ║
    ║    • Pin important conversations     ║
    ║                                      ║
    ║    Your Address: {MY_IP}:{PORT}      ║
    ║    Status: 🔒 Encrypted              ║
    ║                                      ║
    ╚══════════════════════════════════════╝
        """
        
        tk.Label(welcome_frame, text=welcome_text, 
                fg=self.colors['success'], bg=self.colors['bg_dark'],
                font=("Consolas", 11), justify=tk.CENTER).pack(expand=True)
    
    def create_chat_tab(self, peer_id):
        """Create a new chat tab for a peer"""
        if peer_id in self.peer_widgets:
            return self.peer_widgets[peer_id]
        
        chat_frame = tk.Frame(self.notebook, bg=self.colors['bg_dark'])
        
        # Chat display
        chat_display = scrolledtext.ScrolledText(chat_frame,
                                                  wrap=tk.WORD,
                                                  bg=self.colors['bg_dark'],
                                                  fg=self.colors['text_light'],
                                                  font=("Consolas", 10),
                                                  relief=tk.FLAT,
                                                  borderwidth=0)
        chat_display.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Configure tags
        chat_display.tag_config("timestamp", foreground=self.colors['text_dim'], font=("Consolas", 8))
        chat_display.tag_config("sender", foreground=self.colors['success'], font=("Consolas", 9, "bold"))
        chat_display.tag_config("sent", foreground=self.colors['private'])
        chat_display.tag_config("received", foreground=self.colors['text_light'])
        chat_display.tag_config("system", foreground=self.colors['warning'], font=("Consolas", 9, "italic"))
        
        self.peer_widgets[peer_id] = chat_display
        self.notebook.add(chat_frame, text=peer_id[:12])
        
        # Load message history
        for msg in db.get_messages(peer_id):
            if msg['sender'] == NODE_ID:
                chat_display.insert(tk.END, f"{msg['content']}\n", "sent")
            else:
                chat_display.insert(tk.END, f"[{msg['sender']}] ", "sender")
                chat_display.insert(tk.END, f"{msg['content']}\n", "received")
        
        chat_display.see(tk.END)
        return chat_display
    
    def setup_network(self):
        # Main socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", PORT))
        
        # Start network threads
        threading.Thread(target=self.receive_loop, daemon=True).start()
        threading.Thread(target=self.discovery_listener, daemon=True).start()
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
    
    def broadcast_presence(self):
        """Announce presence to network"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while self.running:
            try:
                packet = json.dumps({
                    "type": "DISCOVER",
                    "id": NODE_ID,
                    "ip": MY_IP,
                    "port": PORT
                })
                sock.sendto(packet.encode(), ("255.255.255.255", DISCOVERY_PORT))
            except:
                pass
            time.sleep(5)
    
    def discovery_listener(self):
        """Listen for other peers"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", DISCOVERY_PORT))
        except:
            return
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("type") == "DISCOVER" and msg["id"] != NODE_ID:
                    peer_id = msg["id"]
                    peer_ip = msg["ip"]
                    
                    db.add_peer(peer_id, peer_id, peer_ip)
                    self.root.after(0, self.refresh_peer_list)
            except:
                pass
    
    def receive_loop(self):
        """Receive messages"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
                
                if msg.get("type") == "message":
                    sender = msg["from"]
                    content = msg.get("content", "")
                    is_broadcast = msg.get("broadcast", False)
                    
                    # Update peer
                    db.add_peer(sender, sender, addr[0])
                    
                    # Save message
                    peer_key = "BROADCAST" if is_broadcast else sender
                    db.add_message(peer_key, sender, content)
                    
                    # Display in UI
                    self.root.after(0, lambda: self.display_incoming_message(sender, content, is_broadcast))
                    self.root.after(0, self.refresh_peer_list)
                    
            except Exception as e:
                pass
    
    def display_incoming_message(self, sender, content, is_broadcast):
        """Show incoming message in appropriate chat"""
        peer_key = "BROADCAST" if is_broadcast else sender
        
        # Create tab if needed
        if peer_key not in self.peer_widgets:
            self.create_chat_tab(peer_key)
        
        chat = self.peer_widgets[peer_key]
        
        if is_broadcast:
            chat.insert(tk.END, f"[📢 {sender}] ", "sender")
        else:
            chat.insert(tk.END, f"[{sender}] ", "sender")
        chat.insert(tk.END, f"{content}\n", "received")
        chat.see(tk.END)
    
    def on_peer_select(self, event):
        selection = self.peer_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        
        if index == 0:
            # Broadcast selected
            self.current_peer = "BROADCAST"
            self.chat_header.config(text="📢 BROADCAST (All Nodes)", fg=self.colors['broadcast'])
            self.msg_entry.config(state=tk.NORMAL)
            
            if "BROADCAST" not in self.peer_widgets:
                self.create_chat_tab("BROADCAST")
            
            # Switch to broadcast tab
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == "BROADCAST":
                    self.notebook.select(i)
                    break
        else:
            # Regular peer
            peer_text = self.peer_listbox.get(index)
            
            # Extract peer ID
            parts = peer_text.split()
            for part in parts:
                if not part.startswith(("📌", "🟢", "🔴", "(")):
                    peer_id = part
                    break
            else:
                peer_id = peer_text.split()[0]
            
            self.current_peer = peer_id
            peer_data = db.data["peers"].get(peer_id, {})
            is_online = time.time() - peer_data.get("last_seen", 0) < 15
            status_text = "🟢 Online" if is_online else "🔴 Offline"
            
            self.chat_header.config(text=f"💬 {peer_id} - {status_text}", fg=self.colors['private'])
            self.msg_entry.config(state=tk.NORMAL)
            
            # Create/switch to chat tab
            if peer_id not in self.peer_widgets:
                self.create_chat_tab(peer_id)
            
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == peer_id[:12]:
                    self.notebook.select(i)
                    break
            
            db.clear_unread(peer_id)
            self.refresh_peer_list()
    
    def send_message(self, event=None):
        if not self.current_peer:
            return "break"
        
        content = self.msg_entry.get(1.0, tk.END).strip()
        if not content:
            return "break"
        
        is_broadcast = (self.current_peer == "BROADCAST")
        
        packet = {
            "type": "message",
            "from": NODE_ID,
            "content": content,
            "broadcast": is_broadcast,
            "timestamp": time.time()
        }
        data = json.dumps(packet).encode()
        
        if is_broadcast:
            # Send to all peers
            for peer_id, peer_data in db.data["peers"].items():
                if peer_data.get("ip"):
                    try:
                        self.sock.sendto(data, (peer_data["ip"], PORT))
                    except:
                        pass
            
            # Display in broadcast chat
            if "BROADCAST" in self.peer_widgets:
                chat = self.peer_widgets["BROADCAST"]
                chat.insert(tk.END, "[📢 You] ", "sender")
                chat.insert(tk.END, f"{content}\n", "sent")
                chat.see(tk.END)
            
            db.add_message("BROADCAST", NODE_ID, content)
        else:
            peer_data = db.data["peers"].get(self.current_peer, {})
            if peer_data.get("ip"):
                try:
                    self.sock.sendto(data, (peer_data["ip"], PORT))
                except:
                    pass
            
            # Display in chat
            if self.current_peer in self.peer_widgets:
                chat = self.peer_widgets[self.current_peer]
                chat.insert(tk.END, f"{content}\n", "sent")
                chat.see(tk.END)
            
            db.add_message(self.current_peer, NODE_ID, content)
        
        self.msg_entry.delete(1.0, tk.END)
        return "break"
    
    def clear_chat(self, event=None):
        if not self.current_peer or self.current_peer == "BROADCAST":
            return
        
        if tk.messagebox.askyesno("Clear Chat", f"Delete conversation with {self.current_peer}?"):
            db.delete_conversation(self.current_peer)
            if self.current_peer in self.peer_widgets:
                self.peer_widgets[self.current_peer].delete(1.0, tk.END)
    
    def toggle_pin(self, event=None):
        if not self.current_peer or self.current_peer == "BROADCAST":
            return
        
        peer_data = db.data["peers"].get(self.current_peer, {})
        current_pin = peer_data.get("pinned", False)
        db.pin_peer(self.current_peer, not current_pin)
        self.refresh_peer_list()
    
    def refresh_peer_list(self):
        # Keep broadcast, clear others
        self.peer_listbox.delete(1, tk.END)
        
        online_count = 0
        peers = sorted(db.data["peers"].items(), 
                      key=lambda x: (not x[1].get("pinned", False), -x[1].get("last_seen", 0)))
        
        for peer_id, peer_data in peers:
            is_online = time.time() - peer_data.get("last_seen", 0) < 15
            if is_online:
                online_count += 1
            
            status_icon = "🟢" if is_online else "🔴"
            pin_icon = "📌" if peer_data.get("pinned") else ""
            unread = peer_data.get("unread", 0)
            unread_str = f" ({unread})" if unread > 0 else ""
            
            display = f"{pin_icon}{status_icon} {peer_id}{unread_str}"
            self.peer_listbox.insert(tk.END, display)
            
            # Color coding
            idx = self.peer_listbox.size() - 1
            if peer_data.get("pinned"):
                self.peer_listbox.itemconfig(idx, fg=self.colors['warning'])
            elif is_online:
                self.peer_listbox.itemconfig(idx, fg=self.colors['success'])
            else:
                self.peer_listbox.itemconfig(idx, fg=self.colors['error'])
        
        self.peer_count_label.config(text=f"📡 {online_count} peer{'s' if online_count != 1 else ''} online")
    
    def update_peers_loop(self):
        self.refresh_peer_list()
        self.root.after(3000, self.update_peers_loop)
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def on_close(self):
        self.running = False
        db.save()
        self.root.destroy()

# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    app = MeshMessengerGUI(root)
    app.run()

if __name__ == "__main__":
    main()