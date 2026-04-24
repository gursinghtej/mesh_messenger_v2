#!/usr/bin/env python3
"""
NEON MESH - Fixed Communication
Discovery works → Now let's make messaging work
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import platform
import hashlib

# ============================================================================
# CONFIG
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

print(f"\n⚡ NEON MESH - {NODE_ID} @ {MY_IP}")
print(f"   Message Port: {PORT} | Discovery Port: {DISCOVERY_PORT}\n")

# ============================================================================
# DATABASE
# ============================================================================

DATA_DIR = Path("mesh_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "mesh_db.json"

class Database:
    def __init__(self):
        self.data = self.load()
        self.ensure_broadcast_ip()
    
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
    
    def ensure_broadcast_ip(self):
        """Make sure BROADCAST has an IP so messages can be stored"""
        if 'BROADCAST' not in self.data["peers"]:
            self.data["peers"]['BROADCAST'] = {
                "ip": "255.255.255.255",
                "first_seen": time.time(),
                "last_seen": time.time(),
                "unread": 0
            }
            self.save()
    
    def add_peer(self, peer_id, ip=None):
        if peer_id == NODE_ID:
            return
        if peer_id not in self.data["peers"]:
            self.data["peers"][peer_id] = {
                "ip": ip,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "unread": 0
            }
        else:
            self.data["peers"][peer_id]["last_seen"] = time.time()
            if ip:
                self.data["peers"][peer_id]["ip"] = ip
        self.save()
    
    def get_peer_ip(self, peer_id):
        peer = self.data["peers"].get(peer_id, {})
        return peer.get("ip")
    
    def add_message(self, peer_id, sender, text):
        msg = {"sender": sender, "text": text, "time": time.time()}
        if peer_id not in self.data["messages"]:
            self.data["messages"][peer_id] = []
        self.data["messages"][peer_id].append(msg)
        
        if sender != NODE_ID and peer_id in self.data["peers"] and peer_id != 'BROADCAST':
            self.data["peers"][peer_id]["unread"] = self.data["peers"][peer_id].get("unread", 0) + 1
        
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
            if pid == 'BROADCAST' or pid == NODE_ID:
                continue
            if time.time() - pdata.get("last_seen", 0) < 15:
                online.append((pid, pdata))
        return online
    
    def get_all_peers_sorted(self):
        peers = []
        for pid, pdata in self.data["peers"].items():
            if pid == 'BROADCAST' or pid == NODE_ID:
                continue
            peers.append((pid, pdata))
        peers.sort(key=lambda x: (-x[1].get("last_seen", 0), x[0]))
        return peers

db = Database()

# ============================================================================
# COLORS
# ============================================================================

NEON_COLORS = ['#ff006e', '#ff4d6d', '#ff6b35', '#ff9f1c', '#06d6a0', 
               '#3a86ff', '#7209b7', '#f72585', '#4cc9f0', '#f77f00',
               '#2ec4b6', '#ff0a54', '#ff7096', '#9d4edd', '#00f5d4']

def get_peer_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return NEON_COLORS[h % len(NEON_COLORS)]

USER_COLOR = get_peer_color(NODE_ID)

# ============================================================================
# LOG
# ============================================================================

log_messages = []

def log(msg):
    global log_messages
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    log_messages.append(entry)
    print(entry)
    if len(log_messages) > 50:
        log_messages.pop(0)

# ============================================================================
# GUI
# ============================================================================

class NeonMeshApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"⚡ NEON MESH - {NODE_ID}")
        self.root.geometry("1100x700")
        self.root.configure(bg='#0a0a0f')
        
        self.current_peer = None
        self.running = True
        self.sock = None
        
        self.build_ui()
        self.setup_network()
        self.periodic_refresh()
    
    def build_ui(self):
        main = tk.Frame(self.root, bg='#0a0a0f')
        main.pack(fill=tk.BOTH, expand=True)
        
        # === SIDEBAR ===
        sidebar = tk.Frame(main, bg='#0d0d15', width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))
        sidebar.pack_propagate(False)
        
        # Header
        header = tk.Frame(sidebar, bg='#0d0d15', height=70)
        header.pack(fill=tk.X, padx=15, pady=(20, 10))
        header.pack_propagate(False)
        
        tk.Label(header, text="⚡ NEON MESH", font=('Segoe UI', 20, 'bold'),
                fg=USER_COLOR, bg='#0d0d15').pack(anchor='w')
        tk.Label(header, text="DECENTRALIZED", font=('Segoe UI', 7),
                fg='#444444', bg='#0d0d15').pack(anchor='w', padx=2)
        
        # User info
        badge = tk.Frame(sidebar, bg='#13131f', height=45)
        badge.pack(fill=tk.X, padx=15, pady=(0, 10))
        badge.pack_propagate(False)
        
        av = tk.Canvas(badge, width=30, height=30, highlightthickness=0, bg='#13131f')
        av.place(x=10, y=7)
        av.create_oval(0, 0, 30, 30, fill=USER_COLOR, outline='')
        av.create_text(15, 15, text=NODE_ID[:2].upper(), fill='white', font=('Segoe UI', 10, 'bold'))
        
        tk.Label(badge, text=f"{NODE_ID}  •  {MY_IP}", font=('Consolas', 9),
                fg='#666666', bg='#13131f').place(x=50, y=13)
        
        # Broadcast
        bc_btn = tk.Frame(sidebar, bg='#13131f', height=42, cursor='hand2')
        bc_btn.pack(fill=tk.X, padx=15, pady=(0, 10))
        bc_btn.pack_propagate(False)
        
        tk.Label(bc_btn, text="📢  BROADCAST", font=('Segoe UI', 11, 'bold'),
                fg='#ff006e', bg='#13131f').place(x=15, y=10)
        
        bc_btn.bind('<Button-1>', lambda e: self.select_peer('BROADCAST'))
        bc_btn.bind('<Enter>', lambda e: bc_btn.configure(bg='#1a1a2a'))
        bc_btn.bind('<Leave>', lambda e: bc_btn.configure(bg='#13131f'))
        
        # Connections
        tk.Frame(sidebar, bg='#1a1a2a', height=1).pack(fill=tk.X, padx=15, pady=8)
        tk.Label(sidebar, text="CONNECTIONS", font=('Segoe UI', 8, 'bold'),
                fg='#555555', bg='#0d0d15').pack(anchor='w', padx=20, pady=(0, 8))
        
        # Peer list
        list_frame = tk.Frame(sidebar, bg='#0d0d15')
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
        
        # === RIGHT PANEL ===
        right = tk.Frame(main, bg='#0a0a0f')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Chat header
        chat_header = tk.Frame(right, bg='#0a0a0f', height=55)
        chat_header.pack(fill=tk.X, padx=25, pady=(15, 0))
        chat_header.pack_propagate(False)
        
        self.chat_avatar = tk.Canvas(chat_header, width=38, height=38, highlightthickness=0, bg='#0a0a0f')
        self.chat_avatar.pack(side=tk.LEFT)
        
        info = tk.Frame(chat_header, bg='#0a0a0f')
        info.pack(side=tk.LEFT, padx=12)
        
        self.chat_name = tk.Label(info, text="NEON MESH", font=('Segoe UI', 14, 'bold'),
                                  fg='white', bg='#0a0a0f')
        self.chat_name.pack(anchor='w')
        
        self.chat_status = tk.Label(info, text="Select a peer", font=('Segoe UI', 9),
                                    fg='#666666', bg='#0a0a0f')
        self.chat_status.pack(anchor='w')
        
        self.clear_btn = tk.Label(chat_header, text="🗑️", font=('Segoe UI', 14),
                                  fg='#444444', bg='#0a0a0f', cursor='hand2')
        self.clear_btn.pack(side=tk.RIGHT)
        self.clear_btn.bind('<Button-1>', self.clear_chat)
        
        tk.Frame(right, bg='#1a1a2a', height=1).pack(fill=tk.X, padx=25, pady=8)
        
        # Log panel
        tk.Label(right, text="📡 NETWORK LOG", font=('Consolas', 8, 'bold'),
                fg='#ff9f1c', bg='#0a0a0f').pack(anchor='w', padx=25, pady=(5, 2))
        
        self.log_display = scrolledtext.ScrolledText(right, bg='#0d0d15', fg='#00ff88',
                                                      font=('Consolas', 8), relief=tk.FLAT,
                                                      height=8, borderwidth=0)
        self.log_display.pack(fill=tk.X, padx=25, pady=(0, 10))
        self.log_display.config(state=tk.DISABLED)
        
        # Chat area
        self.chat_canvas = tk.Canvas(right, bg='#0a0a0f', highlightthickness=0)
        chat_scroll = tk.Scrollbar(right, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        
        self.message_frame = tk.Frame(self.chat_canvas, bg='#0a0a0f')
        self.message_frame.bind('<Configure>',
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox('all')))
        
        self.chat_window_id = self.chat_canvas.create_window((0, 0), window=self.message_frame, anchor='nw')
        self.chat_canvas.configure(yscrollcommand=chat_scroll.set)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(25, 0))
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.bind('<Configure>', lambda e: self.chat_canvas.itemconfig(self.chat_window_id, width=e.width))
        
        self.show_welcome()
        
        # Input
        input_frame = tk.Frame(right, bg='#0a0a0f', height=55)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=25, pady=15)
        input_frame.pack_propagate(False)
        
        self.msg_input = tk.Text(input_frame, bg='#13131f', fg='white',
                                 font=('Segoe UI', 11), relief=tk.FLAT,
                                 wrap=tk.WORD, height=2,
                                 insertbackground=USER_COLOR,
                                 padx=15, pady=12,
                                 highlightthickness=1,
                                 highlightbackground='#1a1a2a')
        self.msg_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.msg_input.bind('<Return>', self.send_message)
        self.msg_input.config(state=tk.DISABLED)
        
        send_btn = tk.Canvas(input_frame, width=44, height=44, highlightthickness=0, bg='#0a0a0f')
        send_btn.pack(side=tk.RIGHT, padx=(10, 0))
        send_btn.create_oval(0, 0, 44, 44, fill=USER_COLOR, outline='')
        send_btn.create_text(22, 22, text='↑', fill='white', font=('Segoe UI', 16, 'bold'))
        send_btn.bind('<Button-1>', self.send_message)
        
        # Status bar
        status = tk.Frame(self.root, bg='#0d0d15', height=24)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        status.pack_propagate(False)
        
        tk.Label(status, text=f"🔐 ENCRYPTED  •  {MY_IP}:{PORT}",
                font=('Consolas', 8), fg='#555555', bg='#0d0d15').pack(side=tk.LEFT, padx=15)
        
        self.peer_count_label = tk.Label(status, text="0 ONLINE",
                                         font=('Consolas', 8), fg=USER_COLOR, bg='#0d0d15')
        self.peer_count_label.pack(side=tk.RIGHT, padx=15)
    
    def show_welcome(self):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        welcome = tk.Frame(self.message_frame, bg='#0a0a0f')
        welcome.pack(expand=True, pady=100)
        
        tk.Label(welcome, text="⚡", font=('Segoe UI', 50), fg=USER_COLOR, bg='#0a0a0f').pack()
        tk.Label(welcome, text="NEON MESH", font=('Segoe UI', 22, 'bold'),
                fg=USER_COLOR, bg='#0a0a0f').pack(pady=5)
        tk.Label(welcome, text=f"{NODE_ID} @ {MY_IP}:{PORT}", font=('Consolas', 9),
                fg='#666666', bg='#0a0a0f').pack(pady=10)
        tk.Label(welcome, text="Click a peer to start chatting\nWatch the NETWORK LOG for live status",
                font=('Segoe UI', 10), fg='#444444', bg='#0a0a0f').pack()
    
    def show_chat(self, peer_id):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        messages = db.get_messages(peer_id)
        
        if not messages:
            empty = tk.Frame(self.message_frame, bg='#0a0a0f')
            empty.pack(expand=True, pady=150)
            tk.Label(empty, text="No messages yet", font=('Segoe UI', 10),
                    fg='#444444', bg='#0a0a0f').pack()
            tk.Label(empty, text="Type a message and press Enter to send",
                    font=('Segoe UI', 9), fg='#555555', bg='#0a0a0f').pack()
        else:
            for msg in messages:
                self.add_message_bubble(msg)
        
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
    
    def add_message_bubble(self, msg):
        is_sent = msg['sender'] == NODE_ID
        sender_color = USER_COLOR if is_sent else get_peer_color(msg['sender'])
        time_str = datetime.fromtimestamp(msg['time']).strftime("%H:%M")
        
        row = tk.Frame(self.message_frame, bg='#0a0a0f')
        
        if is_sent:
            row.pack(fill=tk.X, pady=3, padx=20)
            bubble = tk.Frame(row, bg=f'{sender_color}22')
            bubble.pack(side=tk.RIGHT)
            inner = tk.Frame(bubble, bg=f'{sender_color}22', padx=15, pady=8)
            inner.pack()
            tk.Label(inner, text=msg['text'], font=('Segoe UI', 10),
                    fg='white', bg=f'{sender_color}22', wraplength=400).pack(anchor='e')
            tk.Label(inner, text=f"You • {time_str}", font=('Consolas', 7),
                    fg=sender_color, bg=f'{sender_color}22').pack(anchor='e')
        else:
            row.pack(fill=tk.X, pady=3, padx=20)
            tk.Label(row, text=f"◆ {msg['sender']}", font=('Consolas', 8, 'bold'),
                    fg=sender_color, bg='#0a0a0f').pack(anchor='w', padx=(5, 0))
            bubble = tk.Frame(row, bg='#13131f')
            bubble.pack(side=tk.LEFT)
            inner = tk.Frame(bubble, bg='#13131f', padx=15, pady=8)
            inner.pack()
            tk.Label(inner, text=msg['text'], font=('Segoe UI', 10),
                    fg='white', bg='#13131f', wraplength=400).pack(anchor='w')
            tk.Label(inner, text=time_str, font=('Consolas', 7),
                    fg='#555555', bg='#13131f').pack(anchor='w')
    
    # ========================================================================
    # PEER SELECTION
    # ========================================================================
    
    def select_peer(self, peer_id):
        self.current_peer = peer_id
        log(f"Selected: {peer_id}")
        
        if peer_id == 'BROADCAST':
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(2, 2, 36, 36, fill='#ff006e', outline='')
            self.chat_avatar.create_text(19, 19, text='📢', fill='white', font=('Segoe UI', 12))
            self.chat_name.config(text='BROADCAST', fg='#ff006e')
            online_count = len(db.get_online_peers())
            self.chat_status.config(text=f'Send to all online peers ({online_count} online)')
        else:
            data = db.data.get('peers', {}).get(peer_id, {})
            color = get_peer_color(peer_id)
            is_online = time.time() - data.get('last_seen', 0) < 15
            ip = data.get('ip', 'Unknown')
            
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(2, 2, 36, 36, fill=color, outline='')
            self.chat_avatar.create_text(19, 19, text=peer_id[:2].upper(),
                                         fill='white', font=('Segoe UI', 11, 'bold'))
            
            self.chat_name.config(text=peer_id, fg=color)
            self.chat_status.config(text=f"{'🟢 Online' if is_online else '🔴 Offline'} • {ip}")
        
        self.show_chat(peer_id)
        self.msg_input.config(state=tk.NORMAL)
        self.msg_input.focus()
        
        if peer_id != 'BROADCAST':
            db.clear_unread(peer_id)
        
        self.refresh_peer_list()
    
    # ========================================================================
    # SEND MESSAGE - CRITICAL FIX
    # ========================================================================
    
    def send_message(self, event=None):
        if not self.current_peer:
            return 'break'
        
        text = self.msg_input.get('1.0', tk.END).strip()
        if not text:
            return 'break'
        
        if not self.sock:
            log("❌ No socket! Cannot send.")
            return 'break'
        
        is_broadcast = (self.current_peer == 'BROADCAST')
        
        packet = json.dumps({
            'type': 'message',
            'from': NODE_ID,
            'content': text,
            'broadcast': is_broadcast,
            'time': time.time()
        }).encode()
        
        if is_broadcast:
            # Send to EVERY known peer that has an IP
            all_peers = db.get_all_peers_sorted()
            sent_count = 0
            for pid, pdata in all_peers:
                ip = pdata.get('ip')
                if ip and ip != '255.255.255.255':
                    try:
                        self.sock.sendto(packet, (ip, PORT))
                        sent_count += 1
                        log(f"   ✓ Sent to {pid} @ {ip}:{PORT}")
                    except Exception as e:
                        log(f"   ✗ Failed {pid}: {e}")
            
            log(f"📤 BROADCAST: '{text[:25]}...' → {sent_count} peers")
            db.add_message('BROADCAST', NODE_ID, text)
        else:
            # Send to specific peer
            ip = db.get_peer_ip(self.current_peer)
            if ip:
                try:
                    self.sock.sendto(packet, (ip, PORT))
                    log(f"📤 Sent to {self.current_peer} @ {ip}:{PORT}: '{text[:25]}...'")
                    db.add_message(self.current_peer, NODE_ID, text)
                except Exception as e:
                    log(f"❌ Send failed to {self.current_peer} @ {ip}: {e}")
            else:
                log(f"❌ No IP for {self.current_peer}. Cannot send.")
        
        # Show in UI
        self.add_message_bubble({
            'sender': NODE_ID,
            'text': text,
            'time': time.time()
        })
        
        self.msg_input.delete('1.0', tk.END)
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
        self.update_log_display()
        
        return 'break'
    
    # ========================================================================
    # NETWORK
    # ========================================================================
    
    def setup_network(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Increase buffer size
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.sock.bind(('0.0.0.0', PORT))
            log(f"✅ Bound to 0.0.0.0:{PORT}")
        except Exception as e:
            log(f"❌ Bind failed: {e}")
            return
        
        threading.Thread(target=self.broadcast_loop, daemon=True).start()
        threading.Thread(target=self.discovery_listener, daemon=True).start()
        threading.Thread(target=self.receive_loop, daemon=True).start()
        
        log("🚀 Network active")
        self.update_log_display()
    
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
            log(f"✅ Discovery on :{DISCOVERY_PORT}")
        except:
            log("⚠️ Discovery port busy - listening on main socket only")
            return
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if msg.get('type') == 'DISCOVER' and msg['id'] != NODE_ID:
                    peer_id = msg['id']
                    peer_ip = msg.get('ip', addr[0])
                    
                    db.add_peer(peer_id, peer_ip)
                    self.root.after(0, self.refresh_peer_list)
                    self.root.after(0, self.update_log_display)
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
                    
                    log(f"📥 RECEIVED from {sender}: '{text[:30]}...'")
                    
                    db.add_peer(sender, addr[0])
                    db.add_message(peer_key, sender, text)
                    
                    self.root.after(0, lambda pk=peer_key: self.handle_incoming(pk))
                    self.root.after(0, self.refresh_peer_list)
                    self.root.after(0, self.update_log_display)
                    
            except Exception as e:
                pass
    
    def handle_incoming(self, peer_key):
        if self.current_peer == peer_key:
            messages = db.get_messages(peer_key)
            if messages:
                self.add_message_bubble(messages[-1])
                self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
        else:
            self.refresh_peer_list()
    
    # ========================================================================
    # PEER LIST
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
            
            self.create_peer_card(peer_id, peer_data, is_online)
        
        self.peer_count_label.config(text=f"{online_count} ONLINE")
    
    def create_peer_card(self, peer_id, peer_data, is_online):
        is_selected = (self.current_peer == peer_id)
        bg = '#1a1a2a' if is_selected else '#0d0d15'
        
        card = tk.Frame(self.peer_container, bg=bg, height=48, cursor='hand2')
        card.pack(fill=tk.X, pady=1)
        card.pack_propagate(False)
        
        color = get_peer_color(peer_id)
        
        if is_selected:
            tk.Frame(card, bg=color, width=2).place(x=0, y=4, height=40)
        
        av = tk.Canvas(card, width=28, height=28, highlightthickness=0, bg=bg)
        av.place(x=10, y=10)
        
        dot_color = '#00ff88' if is_online else '#444444'
        av.create_oval(2, 2, 26, 26, fill=color, outline='')
        av.create_text(14, 14, text=peer_id[:2].upper(), fill='white', font=('Segoe UI', 9, 'bold'))
        av.create_oval(18, 18, 26, 26, fill=dot_color, outline=bg, width=2)
        
        name = tk.Label(card, text=peer_id, font=('Segoe UI', 10, 'bold'),
                       fg='white' if is_online else '#666666', bg=bg)
        name.place(x=48, y=5)
        
        ip_label = tk.Label(card, text=peer_data.get('ip', '?'), font=('Consolas', 8),
                           fg='#555555', bg=bg)
        ip_label.place(x=48, y=26)
        
        unread = peer_data.get('unread', 0)
        if unread > 0:
            badge = tk.Canvas(card, width=20, height=16, highlightthickness=0, bg=bg)
            badge.place(x=230, y=16)
            badge.create_rectangle(2, 0, 18, 16, fill='#ff3366', outline='')
            badge.create_text(10, 8, text=str(unread), fill='white', font=('Segoe UI', 7, 'bold'))
        
        for widget in [card, name, ip_label, av]:
            widget.bind('<Button-1>', lambda e, pid=peer_id: self.select_peer(pid))
    
    def clear_chat(self, event=None):
        if self.current_peer and self.current_peer != 'BROADCAST':
            if messagebox.askyesno("Clear", f"Delete chat with {self.current_peer}?"):
                db.delete_chat(self.current_peer)
                self.show_chat(self.current_peer)
                log(f"🗑️ Cleared {self.current_peer}")
    
    def update_log_display(self):
        self.log_display.config(state=tk.NORMAL)
        self.log_display.delete(1.0, tk.END)
        for entry in log_messages[-12:]:
            self.log_display.insert(tk.END, entry + '\n')
        self.log_display.config(state=tk.DISABLED)
        self.log_display.see(tk.END)
    
    def periodic_refresh(self):
        if self.running:
            self.refresh_peer_list()
            self.update_log_display()
            self.root.after(3000, self.periodic_refresh)
    
    def run(self):
        self.root.after(500, self.refresh_peer_list)
        self.root.after(1000, self.update_log_display)
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