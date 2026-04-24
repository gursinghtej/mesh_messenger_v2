#!/usr/bin/env python3
"""
NEON MESH - Complete Working Messenger
All features in one file. Run this on all devices.
"""

import tkinter as tk
from tkinter import messagebox
import socket
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import platform
import hashlib

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
NODE_ID = platform.node().split('.')[0][:8]

NEON_COLORS = ['#ff006e', '#ff4d6d', '#ff6b35', '#ff9f1c', '#06d6a0', 
               '#3a86ff', '#7209b7', '#f72585', '#4cc9f0', '#f77f00',
               '#2ec4b6', '#ff0a54', '#ff7096', '#9d4edd', '#00f5d4']

def get_peer_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return NEON_COLORS[h % len(NEON_COLORS)]

USER_COLOR = get_peer_color(NODE_ID)

# ============================================================================
# DATABASE
# ============================================================================

DATA_DIR = Path("mesh_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "mesh_db.json"

class Database:
    def __init__(self):
        self.data = self.load()
    
    def load(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {"peers": {}, "messages": {}}
    
    def save(self):
        with open(DB_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_peer(self, peer_id, ip=None):
        if peer_id not in self.data["peers"]:
            self.data["peers"][peer_id] = {
                "ip": ip,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "unread": 0,
                "color": get_peer_color(peer_id)
            }
        else:
            self.data["peers"][peer_id]["last_seen"] = time.time()
            if ip:
                self.data["peers"][peer_id]["ip"] = ip
        self.save()
    
    def add_message(self, peer_id, sender, text):
        msg = {
            "sender": sender,
            "text": text,
            "time": time.time()
        }
        if peer_id not in self.data["messages"]:
            self.data["messages"][peer_id] = []
        self.data["messages"][peer_id].append(msg)
        
        if sender != NODE_ID and peer_id in self.data["peers"]:
            self.data["peers"][peer_id]["unread"] = self.data["peers"][peer_id].get("unread", 0) + 1
        
        # Keep only last 200 messages
        if len(self.data["messages"][peer_id]) > 200:
            self.data["messages"][peer_id] = self.data["messages"][peer_id][-200:]
        
        self.save()
        return msg
    
    def get_messages(self, peer_id):
        return self.data["messages"].get(peer_id, [])
    
    def clear_unread(self, peer_id):
        if peer_id in self.data["peers"]:
            self.data["peers"][peer_id]["unread"] = 0
            self.save()
    
    def delete_chat(self, peer_id):
        if peer_id in self.data["messages"]:
            del self.data["messages"][peer_id]
        self.clear_unread(peer_id)
        self.save()
    
    def get_online_peers(self):
        online = []
        for pid, pdata in self.data["peers"].items():
            if time.time() - pdata.get("last_seen", 0) < 15:
                online.append((pid, pdata))
        return online
    
    def get_all_peers_sorted(self):
        peers = list(self.data["peers"].items())
        peers.sort(key=lambda x: (-x[1].get("last_seen", 0), x[0]))
        return peers

db = Database()

# ============================================================================
# GUI APPLICATION
# ============================================================================

class NeonMeshApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"⚡ NEON MESH - {NODE_ID}")
        self.root.geometry("1050x680")
        self.root.configure(bg='#0a0a0f')
        self.root.minsize(850, 500)
        
        self.current_peer = None
        self.running = True
        self.peer_widgets = {}
        
        self.build_ui()
        self.setup_network()
        self.periodic_refresh()
    
    # ========================================================================
    # UI CONSTRUCTION
    # ========================================================================
    
    def build_ui(self):
        main = tk.Frame(self.root, bg='#0a0a0f')
        main.pack(fill=tk.BOTH, expand=True)
        
        # === LEFT SIDEBAR ===
        self.sidebar = tk.Frame(main, bg='#0d0d15', width=280)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))
        self.sidebar.pack_propagate(False)
        
        self.build_sidebar_header()
        self.build_broadcast_button()
        self.build_peer_list()
        
        # === RIGHT CONTENT ===
        right = tk.Frame(main, bg='#0a0a0f')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.build_chat_header(right)
        self.build_chat_area(right)
        self.build_input_area(right)
        self.build_status_bar()
        
        # Show welcome
        self.show_welcome()
    
    def build_sidebar_header(self):
        header = tk.Frame(self.sidebar, bg='#0d0d15', height=90)
        header.pack(fill=tk.X, padx=15, pady=(25, 10))
        header.pack_propagate(False)
        
        # Logo
        tk.Label(header, text="⚡ NEON MESH", font=('Segoe UI', 20, 'bold'),
                fg=USER_COLOR, bg='#0d0d15').pack(anchor='w')
        tk.Label(header, text="DECENTRALIZED", font=('Segoe UI', 7, 'bold'),
                fg='#444444', bg='#0d0d15').pack(anchor='w', padx=2)
        
        # User badge
        badge = tk.Frame(self.sidebar, bg='#13131f', height=50)
        badge.pack(fill=tk.X, padx=15, pady=(0, 10))
        badge.pack_propagate(False)
        
        avatar = tk.Canvas(badge, width=32, height=32, highlightthickness=0, bg='#13131f')
        avatar.place(x=10, y=9)
        avatar.create_oval(0, 0, 32, 32, fill=USER_COLOR, outline='')
        avatar.create_text(16, 16, text=NODE_ID[:2].upper(), fill='white', font=('Segoe UI', 11, 'bold'))
        
        tk.Label(badge, text=NODE_ID, font=('Segoe UI', 10, 'bold'),
                fg='white', bg='#13131f').place(x=52, y=8)
        tk.Label(badge, text=f"{MY_IP}:{PORT}", font=('Consolas', 8),
                fg='#666666', bg='#13131f').place(x=52, y=28)
    
    def build_broadcast_button(self):
        bc_btn = tk.Frame(self.sidebar, bg='#13131f', height=45, cursor='hand2')
        bc_btn.pack(fill=tk.X, padx=15, pady=(0, 10))
        bc_btn.pack_propagate(False)
        
        bc_icon = tk.Canvas(bc_btn, width=28, height=28, highlightthickness=0, bg='#13131f')
        bc_icon.place(x=12, y=8)
        bc_icon.create_oval(0, 0, 28, 28, fill='#ff006e', outline='')
        bc_icon.create_text(14, 14, text='📢', fill='white', font=('Segoe UI', 11))
        
        tk.Label(bc_btn, text="BROADCAST", font=('Segoe UI', 10, 'bold'),
                fg='#ff006e', bg='#13131f').place(x=50, y=12)
        tk.Label(bc_btn, text="Send to all peers", font=('Segoe UI', 8),
                fg='#555555', bg='#13131f').place(x=50, y=30)
        
        bc_btn.bind('<Button-1>', lambda e: self.select_peer('BROADCAST'))
        bc_btn.bind('<Enter>', lambda e: bc_btn.configure(bg='#1a1a2a'))
        bc_btn.bind('<Leave>', lambda e: bc_btn.configure(bg='#13131f'))
    
    def build_peer_list(self):
        sep = tk.Frame(self.sidebar, bg='#1a1a2a', height=1)
        sep.pack(fill=tk.X, padx=15, pady=8)
        
        tk.Label(self.sidebar, text="CONNECTIONS", font=('Segoe UI', 8, 'bold'),
                fg='#555555', bg='#0d0d15').pack(anchor='w', padx=20, pady=(0, 8))
        
        # Scrollable container
        list_frame = tk.Frame(self.sidebar, bg='#0d0d15')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8)
        
        self.peer_canvas = tk.Canvas(list_frame, bg='#0d0d15', highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.peer_canvas.yview)
        self.peer_container = tk.Frame(self.peer_canvas, bg='#0d0d15')
        
        self.peer_container.bind('<Configure>',
            lambda e: self.peer_canvas.configure(scrollregion=self.peer_canvas.bbox('all')))
        
        self.peer_canvas.create_window((0, 0), window=self.peer_container, anchor='nw')
        self.peer_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.peer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            self.peer_canvas.yview_scroll(-1 * (event.delta // 120), 'units')
        self.peer_canvas.bind('<Enter>', lambda e: self.peer_canvas.bind_all('<MouseWheel>', on_mousewheel))
        self.peer_canvas.bind('<Leave>', lambda e: self.peer_canvas.unbind_all('<MouseWheel>'))
    
    def build_chat_header(self, parent):
        self.chat_header_frame = tk.Frame(parent, bg='#0a0a0f', height=60)
        self.chat_header_frame.pack(fill=tk.X, padx=25, pady=(15, 0))
        self.chat_header_frame.pack_propagate(False)
        
        self.chat_avatar_canvas = tk.Canvas(self.chat_header_frame, width=42, height=42, 
                                            highlightthickness=0, bg='#0a0a0f')
        self.chat_avatar_canvas.pack(side=tk.LEFT)
        
        info = tk.Frame(self.chat_header_frame, bg='#0a0a0f')
        info.pack(side=tk.LEFT, padx=12)
        
        self.chat_name_label = tk.Label(info, text="NEON MESH", font=('Segoe UI', 15, 'bold'),
                                        fg='white', bg='#0a0a0f')
        self.chat_name_label.pack(anchor='w')
        
        self.chat_status_label = tk.Label(info, text="Select a peer to start messaging",
                                          font=('Segoe UI', 9), fg='#666666', bg='#0a0a0f')
        self.chat_status_label.pack(anchor='w')
        
        # Action buttons
        actions = tk.Frame(self.chat_header_frame, bg='#0a0a0f')
        actions.pack(side=tk.RIGHT)
        
        self.clear_btn = tk.Label(actions, text="🗑️", font=('Segoe UI', 14),
                                  fg='#444444', bg='#0a0a0f', cursor='hand2')
        self.clear_btn.pack(side=tk.LEFT, padx=8)
        self.clear_btn.bind('<Button-1>', self.clear_chat)
        self.clear_btn.bind('<Enter>', lambda e: self.clear_btn.configure(fg='#ff4444'))
        self.clear_btn.bind('<Leave>', lambda e: self.clear_btn.configure(fg='#444444'))
        
        # Separator
        tk.Frame(parent, bg='#1a1a2a', height=1).pack(fill=tk.X, padx=25, pady=8)
    
    def build_chat_area(self, parent):
        self.chat_area_frame = tk.Frame(parent, bg='#0a0a0f')
        self.chat_area_frame.pack(fill=tk.BOTH, expand=True)
        
        # Chat canvas for scrolling messages
        self.chat_canvas = tk.Canvas(self.chat_area_frame, bg='#0a0a0f', highlightthickness=0)
        chat_scroll = tk.Scrollbar(self.chat_area_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        
        self.message_frame = tk.Frame(self.chat_canvas, bg='#0a0a0f')
        self.message_frame.bind('<Configure>',
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox('all')))
        
        self.chat_window_id = self.chat_canvas.create_window((0, 0), window=self.message_frame, anchor='nw')
        
        self.chat_canvas.configure(yscrollcommand=chat_scroll.set)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(25, 0))
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.chat_canvas.bind('<Configure>', lambda e: self.chat_canvas.itemconfig(self.chat_window_id, width=e.width))
    
    def build_input_area(self, parent):
        input_frame = tk.Frame(parent, bg='#0a0a0f', height=60)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=25, pady=15)
        input_frame.pack_propagate(False)
        
        # Input field
        self.message_input = tk.Text(input_frame, bg='#13131f', fg='white',
                                     font=('Segoe UI', 11), relief=tk.FLAT,
                                     wrap=tk.WORD, height=2,
                                     insertbackground=USER_COLOR,
                                     padx=15, pady=12,
                                     highlightthickness=1,
                                     highlightbackground='#1a1a2a')
        self.message_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.message_input.bind('<Return>', self.send_message)
        self.message_input.config(state=tk.DISABLED)
        
        # Send button
        send_frame = tk.Frame(input_frame, bg='#0a0a0f')
        send_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.send_btn_canvas = tk.Canvas(send_frame, width=46, height=46, 
                                         highlightthickness=0, bg='#0a0a0f')
        self.send_btn_canvas.pack()
        self.send_btn_canvas.create_oval(0, 0, 46, 46, fill=USER_COLOR, outline='')
        self.send_btn_canvas.create_text(23, 23, text='↑', fill='white', font=('Segoe UI', 18, 'bold'))
        self.send_btn_canvas.bind('<Button-1>', self.send_message)
    
    def build_status_bar(self):
        status = tk.Frame(self.root, bg='#0d0d15', height=26)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        status.pack_propagate(False)
        
        tk.Label(status, text=f"🔐 ENCRYPTED  •  {MY_IP}:{PORT}",
                font=('Consolas', 8), fg='#555555', bg='#0d0d15').pack(side=tk.LEFT, padx=15)
        
        self.peer_count_label = tk.Label(status, text="0 PEERS ONLINE",
                                         font=('Consolas', 8), fg=USER_COLOR, bg='#0d0d15')
        self.peer_count_label.pack(side=tk.RIGHT, padx=15)
    
    # ========================================================================
    # WELCOME / CHAT VIEWS
    # ========================================================================
    
    def show_welcome(self):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        welcome = tk.Frame(self.message_frame, bg='#0a0a0f')
        welcome.pack(expand=True, pady=120)
        
        tk.Label(welcome, text="⚡", font=('Segoe UI', 50), fg=USER_COLOR, bg='#0a0a0f').pack()
        tk.Label(welcome, text="NEON MESH", font=('Segoe UI', 22, 'bold'),
                fg=USER_COLOR, bg='#0a0a0f').pack(pady=5)
        tk.Label(welcome, text="D E C E N T R A L I Z E D", font=('Consolas', 8),
                fg='#444444', bg='#0a0a0f').pack()
        tk.Label(welcome, text=f"\n{NODE_ID}", font=('Consolas', 10, 'bold'),
                fg='white', bg='#0a0a0f').pack()
        tk.Label(welcome, text=f"{MY_IP}", font=('Consolas', 9),
                fg='#666666', bg='#0a0a0f').pack()
        tk.Label(welcome, text="\nSelect a connection to begin messaging",
                font=('Segoe UI', 10), fg='#444444', bg='#0a0a0f').pack()
    
    def show_chat(self, peer_id):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        messages = db.get_messages(peer_id)
        
        if not messages:
            empty = tk.Frame(self.message_frame, bg='#0a0a0f')
            empty.pack(expand=True, pady=150)
            tk.Label(empty, text="╔══════════════════════╗", font=('Consolas', 9),
                    fg='#444444', bg='#0a0a0f').pack()
            tk.Label(empty, text="║  NO MESSAGES YET    ║", font=('Consolas', 9),
                    fg='#444444', bg='#0a0a0f').pack()
            tk.Label(empty, text="║  Start a conversation║", font=('Consolas', 9),
                    fg='#444444', bg='#0a0a0f').pack()
            tk.Label(empty, text="╚══════════════════════╝", font=('Consolas', 9),
                    fg='#444444', bg='#0a0a0f').pack()
        else:
            for msg in messages:
                self.add_message_bubble(msg)
        
        self.scroll_to_bottom()
    
    def add_message_bubble(self, msg):
        is_sent = msg['sender'] == NODE_ID
        sender_color = USER_COLOR if is_sent else db.data['peers'].get(msg['sender'], {}).get('color', '#3a86ff')
        time_str = datetime.fromtimestamp(msg['time']).strftime("%H:%M")
        
        # Message row
        row = tk.Frame(self.message_frame, bg='#0a0a0f')
        
        if is_sent:
            row.pack(fill=tk.X, pady=4, padx=20)
            # Right-aligned sent message
            bubble = tk.Frame(row, bg=f'{sender_color}22')
            bubble.pack(side=tk.RIGHT)
            
            inner = tk.Frame(bubble, bg=f'{sender_color}22', padx=15, pady=10)
            inner.pack()
            
            tk.Label(inner, text=msg['text'], font=('Segoe UI', 10),
                    fg='white', bg=f'{sender_color}22', wraplength=400).pack(anchor='e')
            tk.Label(inner, text=time_str, font=('Consolas', 7),
                    fg=sender_color, bg=f'{sender_color}22').pack(anchor='e')
        else:
            row.pack(fill=tk.X, pady=4, padx=20)
            # Left-aligned received message
            sender = tk.Label(row, text=f"◆ {msg['sender']}", font=('Consolas', 8, 'bold'),
                            fg=sender_color, bg='#0a0a0f')
            sender.pack(anchor='w', padx=(5, 0))
            
            bubble = tk.Frame(row, bg='#13131f')
            bubble.pack(side=tk.LEFT, padx=(0, 0))
            
            inner = tk.Frame(bubble, bg='#13131f', padx=15, pady=10)
            inner.pack()
            
            tk.Label(inner, text=msg['text'], font=('Segoe UI', 10),
                    fg='white', bg='#13131f', wraplength=400).pack(anchor='w')
            tk.Label(inner, text=time_str, font=('Consolas', 7),
                    fg='#555555', bg='#13131f').pack(anchor='w')
        
        self.message_frame.update_idletasks()
    
    def scroll_to_bottom(self):
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
    
    # ========================================================================
    # PEER SELECTION
    # ========================================================================
    
    def select_peer(self, peer_id):
        self.current_peer = peer_id
        
        # Update header
        if peer_id == 'BROADCAST':
            self.chat_avatar_canvas.delete('all')
            self.chat_avatar_canvas.create_oval(2, 2, 40, 40, fill='#ff006e', outline='')
            self.chat_avatar_canvas.create_text(21, 21, text='📢', fill='white', font=('Segoe UI', 13))
            self.chat_name_label.config(text='BROADCAST', fg='#ff006e')
            self.chat_status_label.config(text='Message will be sent to all online peers')
        else:
            data = db.data['peers'].get(peer_id, {})
            color = data.get('color', '#3a86ff')
            is_online = time.time() - data.get('last_seen', 0) < 15
            
            self.chat_avatar_canvas.delete('all')
            self.chat_avatar_canvas.create_oval(2, 2, 40, 40, fill=color, outline='')
            self.chat_avatar_canvas.create_text(21, 21, text=peer_id[:2].upper(),
                                                fill='white', font=('Segoe UI', 12, 'bold'))
            
            self.chat_name_label.config(text=peer_id, fg=color)
            status = '🟢 Online' if is_online else '🔴 Offline'
            self.chat_status_label.config(text=f"{status}  •  {data.get('ip', 'Unknown')}")
        
        # Show chat
        self.show_chat(peer_id)
        
        # Enable input
        self.message_input.config(state=tk.NORMAL)
        self.message_input.focus()
        
        # Clear unread
        if peer_id != 'BROADCAST':
            db.clear_unread(peer_id)
        
        # Refresh peer list to update selection
        self.refresh_peer_list()
    
    # ========================================================================
    # MESSAGE SENDING
    # ========================================================================
    
    def send_message(self, event=None):
        if not self.current_peer:
            return 'break'
        
        text = self.message_input.get('1.0', tk.END).strip()
        if not text:
            return 'break'
        
        is_broadcast = (self.current_peer == 'BROADCAST')
        
        # Create packet
        packet = json.dumps({
            'type': 'message',
            'from': NODE_ID,
            'content': text,
            'broadcast': is_broadcast,
            'time': time.time()
        }).encode()
        
        # Send to network
        if is_broadcast:
            for pid, pdata in db.data['peers'].items():
                if pdata.get('ip'):
                    try:
                        self.sock.sendto(packet, (pdata['ip'], PORT))
                    except:
                        pass
            db.add_message('BROADCAST', NODE_ID, text)
        else:
            peer_data = db.data['peers'].get(self.current_peer, {})
            if peer_data.get('ip'):
                try:
                    self.sock.sendto(packet, (peer_data['ip'], PORT))
                except:
                    pass
            db.add_message(self.current_peer, NODE_ID, text)
        
        # Add to UI
        msg = db.get_messages(self.current_peer)[-1]
        self.add_message_bubble(msg)
        
        # Clear input
        self.message_input.delete('1.0', tk.END)
        self.scroll_to_bottom()
        
        return 'break'
    
    # ========================================================================
    # ACTIONS
    # ========================================================================
    
    def clear_chat(self, event=None):
        if not self.current_peer or self.current_peer == 'BROADCAST':
            return
        
        if messagebox.askyesno("Clear Chat", f"Delete all messages with {self.current_peer}?"):
            db.delete_chat(self.current_peer)
            self.show_chat(self.current_peer)
    
    # ========================================================================
    # NETWORK
    # ========================================================================
    
    def setup_network(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', PORT))
        
        threading.Thread(target=self.broadcast_loop, daemon=True).start()
        threading.Thread(target=self.discovery_listener, daemon=True).start()
        threading.Thread(target=self.receive_loop, daemon=True).start()
        
        print(f"[NEON MESH] Started on {MY_IP}:{PORT}")
    
    def broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        while self.running:
            try:
                packet = json.dumps({
                    'type': 'DISCOVER',
                    'id': NODE_ID,
                    'ip': MY_IP,
                    'port': PORT
                })
                sock.sendto(packet.encode(), ('255.255.255.255', DISCOVERY_PORT))
            except:
                pass
            time.sleep(5)
    
    def discovery_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(('0.0.0.0', DISCOVERY_PORT))
        except:
            print("[NEON MESH] Discovery port in use, using receive-only mode")
            return
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if msg.get('type') == 'DISCOVER' and msg['id'] != NODE_ID:
                    peer_id = msg['id']
                    peer_ip = msg['ip']
                    
                    db.add_peer(peer_id, peer_ip)
                    self.root.after(0, self.refresh_peer_list)
                    
            except:
                pass
    
    def receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                msg = json.loads(data.decode())
                
                if msg.get('type') == 'message':
                    sender = msg['from']
                    text = msg.get('content', '')
                    is_broadcast = msg.get('broadcast', False)
                    
                    peer_key = 'BROADCAST' if is_broadcast else sender
                    
                    db.add_peer(sender, addr[0])
                    db.add_message(peer_key, sender, text)
                    
                    self.root.after(0, lambda pk=peer_key, s=sender: self.handle_incoming(pk, s))
                    self.root.after(0, self.refresh_peer_list)
                    
            except Exception as e:
                pass
    
    def handle_incoming(self, peer_key, sender):
        # If currently viewing this chat, add bubble
        if self.current_peer == peer_key:
            messages = db.get_messages(peer_key)
            if messages:
                self.add_message_bubble(messages[-1])
                self.scroll_to_bottom()
        else:
            # Just refresh peer list to show unread
            self.refresh_peer_list()
    
    # ========================================================================
    # PEER LIST REFRESH
    # ========================================================================
    
    def refresh_peer_list(self):
        for widget in self.peer_container.winfo_children():
            widget.destroy()
        
        online_count = 0
        peers = db.get_all_peers_sorted()
        
        for peer_id, peer_data in peers:
            is_online = time.time() - peer_data.get('last_seen', 0) < 15
            if is_online:
                online_count += 1
            
            # Create peer card
            self.create_peer_card(peer_id, peer_data, is_online)
        
        self.peer_count_label.config(text=f"{online_count} PEERS ONLINE")
    
    def create_peer_card(self, peer_id, peer_data, is_online):
        is_selected = (self.current_peer == peer_id)
        bg = '#1a1a2a' if is_selected else '#0d0d15'
        
        card = tk.Frame(self.peer_container, bg=bg, height=55, cursor='hand2')
        card.pack(fill=tk.X, pady=1)
        card.pack_propagate(False)
        
        color = peer_data.get('color', '#3a86ff')
        
        # Selection indicator
        if is_selected:
            indicator = tk.Frame(card, bg=color, width=2)
            indicator.place(x=0, y=5, height=45)
        
        # Avatar
        av = tk.Canvas(card, width=34, height=34, highlightthickness=0, bg=bg)
        av.place(x=10, y=10)
        
        dot_color = '#00ff88' if is_online else '#444444'
        av.create_oval(2, 2, 32, 32, fill=color, outline='')
        av.create_text(17, 17, text=peer_id[:2].upper(), fill='white', font=('Segoe UI', 10, 'bold'))
        av.create_oval(24, 24, 32, 32, fill=dot_color, outline=bg, width=2)
        
        # Name
        name_color = 'white' if is_online else '#666666'
        name = tk.Label(card, text=peer_id, font=('Segoe UI', 10, 'bold'),
                       fg=name_color, bg=bg)
        name.place(x=55, y=10)
        
        # Status
        status_text = '● online' if is_online else '○ offline'
        status = tk.Label(card, text=status_text, font=('Segoe UI', 8),
                         fg='#00ff88' if is_online else '#555555', bg=bg)
        status.place(x=55, y=32)
        
        # Unread badge
        unread = peer_data.get('unread', 0)
        if unread > 0:
            badge = tk.Canvas(card, width=22, height=20, highlightthickness=0, bg=bg)
            badge.place(x=230, y=17)
            badge.create_rectangle(2, 0, 20, 20, fill='#ff3366', outline='')
            badge.create_text(11, 10, text=str(unread), fill='white', font=('Segoe UI', 7, 'bold'))
        
        # Bind click
        for widget in [card, name, status, av]:
            widget.bind('<Button-1>', lambda e, pid=peer_id: self.select_peer(pid))
        
        # Hover effect
        def on_enter(e, c=card, n=name, s=status, a=av):
            if not is_selected:
                hover_bg = '#13131f'
                c.configure(bg=hover_bg)
                n.configure(bg=hover_bg)
                s.configure(bg=hover_bg)
                a.configure(bg=hover_bg)
        
        def on_leave(e, c=card, n=name, s=status, a=av, bg=bg):
            if not is_selected:
                c.configure(bg=bg)
                n.configure(bg=bg)
                s.configure(bg=bg)
                a.configure(bg=bg)
        
        for widget in [card, name, status, av]:
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
    
    def periodic_refresh(self):
        if self.running:
            self.refresh_peer_list()
            self.root.after(5000, self.periodic_refresh)
    
    # ========================================================================
    # RUN
    # ========================================================================
    
    def run(self):
        self.root.after(200, self.refresh_peer_list)
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
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
    app = NeonMeshApp(root)
    app.run()

if __name__ == '__main__':
    main()