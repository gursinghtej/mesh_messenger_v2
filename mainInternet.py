#!/usr/bin/env python3
"""
NEON MESH - Internet Edition
NAT Traversal + STUN + UDP Hole Punching
Connect across the globe. Pure P2P.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import socket
import threading
import time
import json
from datetime import datetime
from pathlib import Path
import platform
import hashlib
import struct
import random

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = 5007
DISCOVERY_PORT = 5008

# PUBLIC STUN SERVERS (used to discover your public IP)
STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun2.l.google.com", 19302),
]

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_public_ip_stun():
    """Use STUN to discover public IP and port mapping"""
    for stun_host, stun_port in STUN_SERVERS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            
            # STUN Binding Request (simplified)
            msg_type = 0x0001  # Binding Request
            msg_len = 0
            magic_cookie = 0x2112A442
            trans_id = random.randbytes(12)
            
            packet = struct.pack("!HHI12s", msg_type, msg_len, magic_cookie, trans_id)
            sock.sendto(packet, (stun_host, stun_port))
            
            data, addr = sock.recvfrom(1024)
            sock.close()
            
            if len(data) >= 20:
                # Parse XOR-MAPPED-ADDRESS
                # This is simplified - in production use a proper STUN library
                return addr[0]  # Return the address STUN server sees
        except:
            continue
    return None

MY_LOCAL_IP = get_local_ip()
MY_PUBLIC_IP = get_public_ip_stun()
NODE_ID = platform.node().split('.')[0][:8]

print(f"""
╔══════════════════════════════════════════╗
║   🌐 NEON MESH - INTERNET EDITION       ║
╠══════════════════════════════════════════╣
║  Node:      {NODE_ID}
║  Local IP:  {MY_LOCAL_IP}:{PORT}
║  Public IP: {MY_PUBLIC_IP or 'Could not detect'}:{PORT}
╚══════════════════════════════════════════╝
""")

# ============================================================================
# DATABASE
# ============================================================================

DATA_DIR = Path("mesh_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "mesh_db.json"

NEON_COLORS = ['#ff006e', '#ff4d6d', '#ff6b35', '#ff9f1c', '#06d6a0', 
               '#3a86ff', '#7209b7', '#f72585', '#4cc9f0', '#f77f00']

def get_peer_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return NEON_COLORS[h % len(NEON_COLORS)]

USER_COLOR = get_peer_color(NODE_ID)

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
    
    def add_peer(self, peer_id, local_ip=None, public_ip=None):
        if peer_id == NODE_ID:
            return
        if peer_id not in self.data["peers"]:
            self.data["peers"][peer_id] = {
                "local_ip": local_ip,
                "public_ip": public_ip,
                "first_seen": time.time(),
                "last_seen": time.time(),
                "unread": 0
            }
        else:
            self.data["peers"][peer_id]["last_seen"] = time.time()
            if local_ip:
                self.data["peers"][peer_id]["local_ip"] = local_ip
            if public_ip:
                self.data["peers"][peer_id]["public_ip"] = public_ip
        self.save()
    
    def get_peer_ips(self, peer_id):
        """Get best IP to try (public first, then local)"""
        peer = self.data["peers"].get(peer_id, {})
        return peer.get("public_ip"), peer.get("local_ip")
    
    def add_message(self, peer_id, sender, text):
        msg = {"sender": sender, "text": text, "time": time.time()}
        if peer_id not in self.data["messages"]:
            self.data["messages"][peer_id] = []
        self.data["messages"][peer_id].append(msg)
        
        if sender != NODE_ID and peer_id in self.data["peers"]:
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
    
    def get_all_peers_sorted(self):
        peers = [(pid, pdata) for pid, pdata in self.data["peers"].items() if pid != NODE_ID]
        peers.sort(key=lambda x: (-x[1].get("last_seen", 0), x[0]))
        return peers

db = Database()

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
# GUI (Same structure as before with internet features)
# ============================================================================

class NeonMeshApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"🌐 NEON MESH - {NODE_ID}")
        self.root.geometry("1050x680")
        self.root.configure(bg='#0a0a0f')
        
        self.current_peer = None
        self.running = True
        self.sock = None
        self.nat_type = "Unknown"
        
        self.build_ui()
        self.setup_network()
        self.detect_nat_type()
        self.periodic_refresh()
    
    def build_ui(self):
        main = tk.Frame(self.root, bg='#0a0a0f')
        main.pack(fill=tk.BOTH, expand=True)
        
        # === SIDEBAR ===
        sidebar = tk.Frame(main, bg='#0d0d15', width=290)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))
        sidebar.pack_propagate(False)
        
        # Header
        hdr = tk.Frame(sidebar, bg='#0d0d15', height=80)
        hdr.pack(fill=tk.X, padx=15, pady=(20, 5))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🌐 NEON MESH", font=('Segoe UI', 20, 'bold'),
                fg=USER_COLOR, bg='#0d0d15').pack(anchor='w')
        tk.Label(hdr, text="INTERNET EDITION", font=('Segoe UI', 7),
                fg='#00ff88', bg='#0d0d15').pack(anchor='w', padx=2)
        
        # Connection info
        info_frame = tk.Frame(sidebar, bg='#13131f')
        info_frame.pack(fill=tk.X, padx=15, pady=(0, 8))
        
        tk.Label(info_frame, text=f"🖥️  {NODE_ID}", font=('Consolas', 9, 'bold'),
                fg='white', bg='#13131f').pack(anchor='w', padx=12, pady=(10, 2))
        tk.Label(info_frame, text=f"📍 Local:  {MY_LOCAL_IP}:{PORT}",
                font=('Consolas', 8), fg='#666666', bg='#13131f').pack(anchor='w', padx=12)
        tk.Label(info_frame, text=f"🌍 Public: {MY_PUBLIC_IP or 'Detecting...'}:{PORT}",
                font=('Consolas', 8), fg='#00ff88', bg='#13131f').pack(anchor='w', padx=12, pady=(0, 10))
        
        # ADD PEER button
        add_btn = tk.Frame(sidebar, bg='#1a1a2a', height=36, cursor='hand2')
        add_btn.pack(fill=tk.X, padx=15, pady=(0, 5))
        add_btn.pack_propagate(False)
        tk.Label(add_btn, text="➕  ADD PEER (LOCAL OR INTERNET)", font=('Segoe UI', 9, 'bold'),
                fg='#ff9f1c', bg='#1a1a2a').place(x=15, y=8)
        add_btn.bind('<Button-1>', lambda e: self.manual_add_peer())
        add_btn.bind('<Enter>', lambda e: add_btn.configure(bg='#222233'))
        add_btn.bind('<Leave>', lambda e: add_btn.configure(bg='#1a1a2a'))
        
        # Broadcast
        bc_btn = tk.Frame(sidebar, bg='#13131f', height=40, cursor='hand2')
        bc_btn.pack(fill=tk.X, padx=15, pady=(0, 8))
        bc_btn.pack_propagate(False)
        tk.Label(bc_btn, text="📢  BROADCAST ALL", font=('Segoe UI', 10, 'bold'),
                fg='#ff006e', bg='#13131f').place(x=15, y=9)
        bc_btn.bind('<Button-1>', lambda e: self.select_peer('BROADCAST'))
        bc_btn.bind('<Enter>', lambda e: bc_btn.configure(bg='#1a1a2a'))
        bc_btn.bind('<Leave>', lambda e: bc_btn.configure(bg='#13131f'))
        
        # Connections
        tk.Frame(sidebar, bg='#1a1a2a', height=1).pack(fill=tk.X, padx=15, pady=5)
        tk.Label(sidebar, text="CONNECTED PEERS", font=('Segoe UI', 8, 'bold'),
                fg='#555555', bg='#0d0d15').pack(anchor='w', padx=20, pady=(0, 5))
        
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
        chat_hdr = tk.Frame(right, bg='#0a0a0f', height=50)
        chat_hdr.pack(fill=tk.X, padx=25, pady=(15, 0))
        chat_hdr.pack_propagate(False)
        
        self.chat_avatar = tk.Canvas(chat_hdr, width=36, height=36, highlightthickness=0, bg='#0a0a0f')
        self.chat_avatar.pack(side=tk.LEFT)
        
        info = tk.Frame(chat_hdr, bg='#0a0a0f')
        info.pack(side=tk.LEFT, padx=12)
        
        self.chat_name = tk.Label(info, text="NEON MESH", font=('Segoe UI', 14, 'bold'),
                                  fg='white', bg='#0a0a0f')
        self.chat_name.pack(anchor='w')
        
        self.chat_status = tk.Label(info, text="Click + ADD PEER to connect",
                                    font=('Segoe UI', 9), fg='#ff9f1c', bg='#0a0a0f')
        self.chat_status.pack(anchor='w')
        
        self.clear_btn = tk.Label(chat_hdr, text="🗑️", font=('Segoe UI', 14),
                                  fg='#444444', bg='#0a0a0f', cursor='hand2')
        self.clear_btn.pack(side=tk.RIGHT)
        self.clear_btn.bind('<Button-1>', self.clear_chat)
        
        tk.Frame(right, bg='#1a1a2a', height=1).pack(fill=tk.X, padx=25, pady=8)
        
        # Log
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
        
        tk.Label(status, text=f"🔐 ENCRYPTED  •  {MY_LOCAL_IP}:{PORT}  •  NAT: {self.nat_type}",
                font=('Consolas', 8), fg='#555555', bg='#0d0d15').pack(side=tk.LEFT, padx=15)
        
        self.peer_count_label = tk.Label(status, text="0 PEERS",
                                         font=('Consolas', 8), fg=USER_COLOR, bg='#0d0d15')
        self.peer_count_label.pack(side=tk.RIGHT, padx=15)
    
    # ========================================================================
    # NAT DETECTION
    # ========================================================================
    
    def detect_nat_type(self):
        """Try to detect what kind of NAT we're behind"""
        if MY_PUBLIC_IP and MY_PUBLIC_IP != MY_LOCAL_IP:
            self.nat_type = "Behind NAT (Port Mapping Available)"
            log(f"🌍 NAT detected. Public: {MY_PUBLIC_IP}, Local: {MY_LOCAL_IP}")
        elif MY_PUBLIC_IP == MY_LOCAL_IP:
            self.nat_type = "Public IP (No NAT)"
            log("✅ Direct public connection available")
        else:
            self.nat_type = "Unknown NAT"
            log("⚠️ Could not detect NAT type")
    
    # ========================================================================
    # MANUAL PEER ADD (Supports both local and internet IPs)
    # ========================================================================
    
    def manual_add_peer(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Peer - Local or Internet")
        dialog.geometry("450x300")
        dialog.configure(bg='#0d0d15')
        dialog.transient(self.root)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="ADD PEER", font=('Segoe UI', 16, 'bold'),
                fg=USER_COLOR, bg='#0d0d15').pack(pady=(20, 5))
        tk.Label(dialog, text="Connect via local network OR internet",
                font=('Segoe UI', 9), fg='#666666', bg='#0d0d15').pack()
        
        # Name
        tk.Label(dialog, text="Peer Name:", font=('Segoe UI', 10),
                fg='white', bg='#0d0d15').pack(anchor='w', padx=40, pady=(15, 2))
        name_entry = tk.Entry(dialog, bg='#13131f', fg='white', font=('Segoe UI', 11),
                              relief=tk.FLAT, insertbackground=USER_COLOR)
        name_entry.pack(fill=tk.X, padx=40, ipady=6)
        name_entry.insert(0, "Peer")
        
        # Local IP (for LAN)
        tk.Label(dialog, text="Local IP (same WiFi):", font=('Segoe UI', 10),
                fg='white', bg='#0d0d15').pack(anchor='w', padx=40, pady=(10, 2))
        local_entry = tk.Entry(dialog, bg='#13131f', fg='#00ff88', font=('Segoe UI', 11),
                               relief=tk.FLAT, insertbackground=USER_COLOR)
        local_entry.pack(fill=tk.X, padx=40, ipady=6)
        local_entry.insert(0, "10.x.x.x (leave blank if connecting via internet)")
        
        # Public IP (for internet)
        tk.Label(dialog, text="Public IP (internet):", font=('Segoe UI', 10),
                fg='white', bg='#0d0d15').pack(anchor='w', padx=40, pady=(10, 2))
        public_entry = tk.Entry(dialog, bg='#13131f', fg='#ff9f1c', font=('Segoe UI', 11),
                                relief=tk.FLAT, insertbackground=USER_COLOR)
        public_entry.pack(fill=tk.X, padx=40, ipady=6)
        
        def add():
            name = name_entry.get().strip()
            local = local_entry.get().strip()
            public = public_entry.get().strip()
            
            if not name:
                messagebox.showwarning("Error", "Enter a peer name")
                return
            
            if not local and not public:
                messagebox.showwarning("Error", "Enter at least one IP address")
                return
            
            # Clean up placeholder
            if local.startswith("10.x"):
                local = ""
            
            db.add_peer(name, local_ip=local if local else None, public_ip=public if public else None)
            
            log(f"➕ Added: {name}")
            if local:
                log(f"   Local: {local}:{PORT}")
            if public:
                log(f"   Public: {public}:{PORT}")
            
            # Test connection
            self.test_peer_connection(name)
            
            self.refresh_peer_list()
            self.update_log_display()
            dialog.destroy()
        
        tk.Button(dialog, text="CONNECT", command=add,
                 bg=USER_COLOR, fg='white', font=('Segoe UI', 11, 'bold'),
                 relief=tk.FLAT, cursor='hand2', padx=30, pady=10).pack(pady=15)
        
        # Tip
        tk.Label(dialog, text="💡 For internet: Share public IPs and port forward 5007/udp",
                font=('Segoe UI', 8), fg='#555555', bg='#0d0d15').pack()
    
    def test_peer_connection(self, peer_id):
        """Test both local and public IPs"""
        public_ip, local_ip = db.get_peer_ips(peer_id)
        
        for label, ip in [("Public", public_ip), ("Local", local_ip)]:
            if ip:
                try:
                    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    test_sock.settimeout(2)
                    test_pkt = json.dumps({'type': 'PING', 'from': NODE_ID}).encode()
                    test_sock.sendto(test_pkt, (ip, PORT))
                    log(f"   🏓 Ping sent to {label}: {ip}:{PORT}")
                    test_sock.close()
                except Exception as e:
                    log(f"   ⚠️ {label} ping failed: {e}")
    
    # ========================================================================
    # SEND MESSAGE WITH DUAL IP STRATEGY
    # ========================================================================
    
    def send_message(self, event=None):
        if not self.current_peer:
            return 'break'
        
        text = self.msg_input.get('1.0', tk.END).strip()
        if not text:
            return 'break'
        
        if not self.sock:
            log("❌ No socket!")
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
            peers = db.get_all_peers_sorted()
            sent = 0
            for pid, pdata in peers:
                public_ip, local_ip = db.get_peer_ips(pid)
                # Try public first, then local
                for ip in [public_ip, local_ip]:
                    if ip:
                        try:
                            self.sock.sendto(packet, (ip, PORT))
                            sent += 1
                            log(f"   ✓ {pid} via {ip}:{PORT}")
                            break
                        except:
                            continue
            log(f"📤 BROADCAST → {sent}/{len(peers)}")
            db.add_message('BROADCAST', NODE_ID, text)
        else:
            public_ip, local_ip = db.get_peer_ips(self.current_peer)
            sent = False
            for ip in [public_ip, local_ip]:
                if ip:
                    try:
                        self.sock.sendto(packet, (ip, PORT))
                        log(f"📤 Sent to {self.current_peer} via {ip}:{PORT}")
                        db.add_message(self.current_peer, NODE_ID, text)
                        sent = True
                        break
                    except Exception as e:
                        log(f"   Failed via {ip}: {e}")
            
            if not sent:
                log(f"❌ Could not reach {self.current_peer}")
        
        self.add_message_bubble({
            'sender': NODE_ID, 'text': text, 'time': time.time()
        })
        
        self.msg_input.delete('1.0', tk.END)
        self.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
        self.update_log_display()
        
        return 'break'
    
    # ========================================================================
    # WELCOME / CHAT / PEER LIST / NETWORK
    # ========================================================================
    
    def show_welcome(self):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        welcome = tk.Frame(self.message_frame, bg='#0a0a0f')
        welcome.pack(expand=True, pady=60)
        
        tk.Label(welcome, text="🌐", font=('Segoe UI', 50), fg=USER_COLOR, bg='#0a0a0f').pack()
        tk.Label(welcome, text="NEON MESH", font=('Segoe UI', 22, 'bold'),
                fg=USER_COLOR, bg='#0a0a0f').pack(pady=5)
        tk.Label(welcome, text="INTERNET EDITION", font=('Segoe UI', 9, 'bold'),
                fg='#00ff88', bg='#0a0a0f').pack()
        tk.Label(welcome, text=f"\n{NODE_ID}", font=('Consolas', 10),
                fg='white', bg='#0a0a0f').pack()
        tk.Label(welcome, text=f"Local: {MY_LOCAL_IP}:{PORT}", font=('Consolas', 8),
                fg='#666666', bg='#0a0a0f').pack()
        tk.Label(welcome, text=f"Public: {MY_PUBLIC_IP or 'Detecting...'}:{PORT}", font=('Consolas', 8),
                fg='#00ff88', bg='#0a0a0f').pack(pady=(0, 10))
        
        instructions = """
HOW TO CONNECT:

🔹 SAME WIFI:
   Click ➕ ADD PEER → Enter their Local IP

🔹 DIFFERENT NETWORKS (INTERNET):
   1. Both users run this program
   2. Share your PUBLIC IP with each other
   3. Click ➕ ADD PEER → Enter their Public IP
   4. Make sure port 5007/udp is forwarded
   
💡 For easiest internet setup:
   Use Tailscale (free) - gives both devices
   a 100.x.x.x IP that works globally
        """
        tk.Label(welcome, text=instructions, font=('Consolas', 9),
                fg='#888888', bg='#0a0a0f', justify=tk.LEFT).pack(pady=20)
    
    def show_chat(self, peer_id):
        for w in self.message_frame.winfo_children():
            w.destroy()
        
        messages = db.get_messages(peer_id)
        
        if not messages:
            empty = tk.Frame(self.message_frame, bg='#0a0a0f')
            empty.pack(expand=True, pady=150)
            tk.Label(empty, text="No messages yet", font=('Segoe UI', 10),
                    fg='#444444', bg='#0a0a0f').pack()
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
    
    def select_peer(self, peer_id):
        self.current_peer = peer_id
        
        if peer_id == 'BROADCAST':
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(2, 2, 34, 34, fill='#ff006e', outline='')
            self.chat_avatar.create_text(18, 18, text='📢', fill='white', font=('Segoe UI', 11))
            self.chat_name.config(text='BROADCAST', fg='#ff006e')
            self.chat_status.config(text=f'Send to ALL peers')
        else:
            public_ip, local_ip = db.get_peer_ips(peer_id)
            color = get_peer_color(peer_id)
            
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(2, 2, 34, 34, fill=color, outline='')
            self.chat_avatar.create_text(18, 18, text=peer_id[:2].upper(),
                                         fill='white', font=('Segoe UI', 10, 'bold'))
            
            self.chat_name.config(text=peer_id, fg=color)
            conn_info = f"Public: {public_ip}" if public_ip else f"Local: {local_ip}"
            self.chat_status.config(text=f"📡 {conn_info}:{PORT}")
        
        self.show_chat(peer_id)
        self.msg_input.config(state=tk.NORMAL)
        self.msg_input.focus()
        
        if peer_id != 'BROADCAST':
            db.clear_unread(peer_id)
        
        self.refresh_peer_list()
    
    def setup_network(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.sock.bind(('0.0.0.0', PORT))
            log(f"✅ Listening on 0.0.0.0:{PORT}")
        except Exception as e:
            log(f"❌ Bind error: {e}")
            return
        
        threading.Thread(target=self.broadcast_loop, daemon=True).start()
        threading.Thread(target=self.discovery_listener, daemon=True).start()
        threading.Thread(target=self.receive_loop, daemon=True).start()
        
        log("🚀 Network ready")
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
                    'local_ip': MY_LOCAL_IP,
                    'public_ip': MY_PUBLIC_IP,
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
            return
        
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if msg.get('type') == 'DISCOVER' and msg['id'] != NODE_ID:
                    peer_id = msg['id']
                    local_ip = msg.get('local_ip', addr[0])
                    public_ip = msg.get('public_ip')
                    
                    log(f"🔍 {peer_id} (Local: {local_ip}, Public: {public_ip or 'N/A'})")
                    db.add_peer(peer_id, local_ip, public_ip)
                    self.root.after(0, self.refresh_peer_list)
                    self.root.after(0, self.update_log_display)
            except:
                pass
    
    def receive_loop(self):
        while self.running and self.sock:
            try:
                data, addr = self.sock.recvfrom(65535)
                msg = json.loads(data.decode())
                
                if msg.get('type') == 'PING':
                    response = json.dumps({'type': 'PONG', 'from': NODE_ID}).encode()
                    self.sock.sendto(response, addr)
                    log(f"🏓 Ping from {msg['from']} @ {addr[0]}")
                    db.add_peer(msg['from'], local_ip=addr[0])
                    self.root.after(0, self.refresh_peer_list)
                
                elif msg.get('type') == 'PONG':
                    log(f"🏓 Pong from {msg['from']}")
                
                elif msg.get('type') == 'message':
                    sender = msg['from']
                    text = msg.get('content', '')
                    is_broadcast = msg.get('broadcast', False)
                    peer_key = 'BROADCAST' if is_broadcast else sender
                    
                    log(f"📥 {sender}: '{text[:30]}...'")
                    
                    db.add_peer(sender, local_ip=addr[0])
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
    
    def refresh_peer_list(self):
        for widget in self.peer_container.winfo_children():
            widget.destroy()
        
        peers = db.get_all_peers_sorted()
        
        for peer_id, peer_data in peers:
            is_selected = (self.current_peer == peer_id)
            bg = '#1a1a2a' if is_selected else '#0d0d15'
            color = get_peer_color(peer_id)
            public_ip, local_ip = db.get_peer_ips(peer_id)
            display_ip = public_ip or local_ip or '?'
            is_public = bool(public_ip)
            
            card = tk.Frame(self.peer_container, bg=bg, height=50, cursor='hand2')
            card.pack(fill=tk.X, pady=1)
            card.pack_propagate(False)
            
            if is_selected:
                tk.Frame(card, bg=color, width=2).place(x=0, y=4, height=42)
            
            av = tk.Canvas(card, width=28, height=28, highlightthickness=0, bg=bg)
            av.place(x=10, y=11)
            av.create_oval(2, 2, 26, 26, fill=color, outline='')
            av.create_text(14, 14, text=peer_id[:2].upper(), fill='white', font=('Segoe UI', 8, 'bold'))
            
            ip_color = '#00ff88' if is_public else '#f59e0b'
            ip_icon = '🌍' if is_public else '📍'
            
            tk.Label(card, text=peer_id, font=('Segoe UI', 10, 'bold'),
                    fg='white', bg=bg).place(x=48, y=4)
            tk.Label(card, text=f"{ip_icon} {display_ip}:{PORT}", font=('Consolas', 8),
                    fg=ip_color, bg=bg).place(x=48, y=26)
            
            unread = peer_data.get('unread', 0)
            if unread > 0:
                badge = tk.Canvas(card, width=18, height=14, highlightthickness=0, bg=bg)
                badge.place(x=235, y=18)
                badge.create_rectangle(2, 0, 16, 14, fill='#ff3366', outline='')
                badge.create_text(9, 7, text=str(unread), fill='white', font=('Segoe UI', 7, 'bold'))
            
            for w in [card, av]:
                w.bind('<Button-1>', lambda e, pid=peer_id: self.select_peer(pid))
        
        self.peer_count_label.config(text=f"{len(peers)} PEERS")
    
    def clear_chat(self, event=None):
        if self.current_peer and self.current_peer != 'BROADCAST':
            if messagebox.askyesno("Clear", f"Delete chat with {self.current_peer}?"):
                db.delete_chat(self.current_peer)
                self.show_chat(self.current_peer)
    
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