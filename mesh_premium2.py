    #!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   ⚡ NEON MESH v3 - System Interface     ║
║   Live. Reactive. Intentional.           ║
╚══════════════════════════════════════════╝
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
import random

# ============================================================================
# CONFIG
# ============================================================================

PORT = 5007
DISCOVERY_PORT = 5008

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

MY_IP = get_ip()
NODE_ID = platform.node().split('.')[0][:8]

# ============================================================================
# DESIGN TOKENS - Intentional color roles
# ============================================================================

C = {
    # Depth layers (darkest → lightest)
    'void':    '#000000',  # Root background
    'base':    '#080808',  # Main surfaces
    'surface': '#0d0d0d',  # Cards, panels
    'elevated':'#141414',  # Hover, selected
    'overlay': '#1a1a1a',  # Inputs, active elements
    
    # Semantic colors
    'action':  '#f59e0b',  # ORANGE - ONLY for interactions/actions
    'online':  '#22c55e',  # Green - online status
    'offline': '#525252',  # Gray - offline
    'warn':    '#ef4444',  # Red - errors, delete
    'info':    '#3b82f6',  # Blue - system info
    
    # Text hierarchy
    'text_primary':   '#e5e5e5',
    'text_secondary': '#737373',
    'text_dim':       '#404040',
    'text_inverse':   '#000000',
    
    # Accent colors per peer (for differentiation only, not actions)
    'peers': ['#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4', '#f59e0b', '#10b981', '#6366f1', '#14b8a6'],
}

def peer_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return C['peers'][h % len(C['peers'])]

PEER_COLOR = peer_color(NODE_ID)

# ============================================================================
# DATABASE
# ============================================================================

DATA_DIR = Path("mesh_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "mesh_db.json"

class DB:
    def __init__(self):
        self.data = self.load()
    def load(self):
        if DB_FILE.exists():
            try:
                with open(DB_FILE) as f: return json.load(f)
            except: pass
        return {"peers": {}, "messages": {}}
    def save(self):
        with open(DB_FILE, 'w') as f: json.dump(self.data, f, indent=2)
    def add_peer(self, pid, ip=None):
        if pid not in self.data["peers"]:
            self.data["peers"][pid] = {"ip": ip, "first_seen": time.time(), "last_seen": time.time(), "unread": 0, "color": peer_color(pid)}
        else:
            self.data["peers"][pid]["last_seen"] = time.time()
            if ip: self.data["peers"][pid]["ip"] = ip
        self.save()
    def add_msg(self, peer, sender, text):
        msg = {"sender": sender, "text": text, "time": time.time(), "id": f"msg_{int(time.time()*1000)}"}
        if peer not in self.data["messages"]: self.data["messages"][peer] = []
        self.data["messages"][peer].append(msg)
        if sender != NODE_ID and peer in self.data["peers"]:
            self.data["peers"][peer]["unread"] = self.data["peers"][peer].get("unread", 0) + 1
        self.save()
        return msg
    def get_msgs(self, peer): return self.data["messages"].get(peer, [])
    def clear_unread(self, peer):
        if peer in self.data["peers"]: self.data["peers"][peer]["unread"] = 0; self.save()
    def delete_chat(self, peer):
        if peer in self.data["messages"]: del self.data["messages"][peer]
        self.clear_unread(peer); self.save()
    def get_stats(self):
        online = sum(1 for p in self.data["peers"].values() if time.time() - p.get("last_seen",0) < 15)
        total_msgs = sum(len(v) for v in self.data["messages"].values())
        return {"peers_discovered": len(self.data["peers"]), "peers_online": online, "total_messages": total_msgs}

db = DB()

# ============================================================================
# ACTIVITY LOG (System events)
# ============================================================================

activity_log = []
MAX_LOG = 50

def log_activity(event_type, detail=""):
    global activity_log
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "type": event_type, "detail": detail}
    activity_log.append(entry)
    if len(activity_log) > MAX_LOG: activity_log.pop(0)

log_activity("SYSTEM", f"Node initialized: {NODE_ID}")
log_activity("NETWORK", f"Listening on {MY_IP}:{PORT}")

# ============================================================================
# SYSTEM MODE INDICATOR
# ============================================================================

class SystemMode:
    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    ACTIVE = "ACTIVE"
    TRANSMITTING = "TRANSMITTING"
    
    def __init__(self):
        self.current = self.IDLE
        self.callbacks = []
    
    def set_mode(self, mode, detail=""):
        old = self.current
        self.current = mode
        if old != mode:
            log_activity("MODE", f"{old} → {mode} {detail}")
            for cb in self.callbacks: cb(mode)
    
    def pulse_transmit(self):
        self.set_mode(self.TRANSMITTING)
        threading.Timer(0.8, lambda: self.set_mode(self.ACTIVE)).start()

sys_mode = SystemMode()

# ============================================================================
# UI COMPONENTS
# ============================================================================

class PeerRow(tk.Frame):
    """Single peer in sidebar - clean, intentional"""
    def __init__(self, parent, peer_id, data, selected=False, on_select=None):
        bg = C['elevated'] if selected else C['surface']
        super().__init__(parent, bg=bg, height=56, cursor='hand2')
        self.pack_propagate(False)
        self.pid = peer_id
        self.data = data
        self.selected = selected
        self.on_select = on_select
        self.is_online = time.time() - data.get('last_seen', 0) < 15
        self.color = data.get('color', C['info'])
        
        self._build()
        self._bind_hover()
    
    def _build(self):
        # Selection indicator bar (left edge)
        if self.selected:
            tk.Frame(self, bg=C['action'], width=2).place(x=0, y=4, height=48)
        
        # Status dot
        dot_color = C['online'] if self.is_online else C['offline']
        dot = tk.Canvas(self, width=8, height=8, highlightthickness=0, bg=self['bg'])
        dot.place(x=14, y=24)
        dot.create_oval(0, 0, 8, 8, fill=dot_color, outline='')
        
        # Peer identifier
        name_color = C['text_primary'] if self.is_online else C['text_secondary']
        name = tk.Label(self, text=self.pid, font=('SF Mono', 11, 'bold' if self.selected else 'normal'),
                       fg=name_color, bg=self['bg'], anchor='w')
        name.place(x=34, y=8)
        
        # IP / status line
        status_text = "● online" if self.is_online else "○ offline"
        status = tk.Label(self, text=status_text, font=('SF Mono', 8),
                         fg=C['online'] if self.is_online else C['text_dim'], bg=self['bg'])
        status.place(x=34, y=30)
        
        # Unread indicator
        unread = self.data.get('unread', 0)
        if unread > 0:
            badge = tk.Canvas(self, width=20, height=18, highlightthickness=0, bg=self['bg'])
            badge.place(x=225, y=19)
            badge.create_rectangle(2, 0, 18, 18, fill=C['warn'], outline='')
            badge.create_text(10, 9, text=str(unread), fill='white', font=('SF Mono', 7, 'bold'))
        
        # Store widgets for hover
        self._widgets = [name, status]
    
    def _bind_hover(self):
        for w in [self] + self._widgets:
            w.bind('<Enter>', lambda e: self._hover(True))
            w.bind('<Leave>', lambda e: self._hover(False))
            w.bind('<Button-1>', lambda e: self.on_select(self.pid) if self.on_select else None)
    
    def _hover(self, enter):
        if not self.selected:
            bg = C['elevated'] if enter else C['surface']
            self.configure(bg=bg)
            for w in self._widgets:
                w.configure(bg=bg)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class NeonMeshApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NEON MESH")
        self.root.geometry("1050x680")
        self.root.configure(bg=C['void'])
        self.root.minsize(850, 500)
        
        self.current_peer = None
        self.running = True
        self.msg_bubbles = []
        
        self._build_layout()
        self._setup_network()
        self._start_system_loop()
    
    # ========================================================================
    # LAYOUT
    # ========================================================================
    
    def _build_layout(self):
        main = tk.Frame(self.root, bg=C['void'])
        main.pack(fill=tk.BOTH, expand=True)
        
        # === SIDEBAR ===
        sidebar = tk.Frame(main, bg=C['base'], width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Header
        header = tk.Frame(sidebar, bg=C['base'], height=55)
        header.pack(fill=tk.X, padx=18, pady=(20, 0))
        
        self.mode_label = tk.Label(header, text=f"NEON MESH [{sys_mode.current}]",
                                   font=('SF Mono', 11, 'bold'),
                                   fg=C['action'] if sys_mode.current != sys_mode.IDLE else C['text_secondary'],
                                   bg=C['base'])
        self.mode_label.pack(side=tk.LEFT)
        
        # Listen for mode changes
        sys_mode.callbacks.append(self._on_mode_change)
        
        # Separator
        tk.Frame(sidebar, bg=C['surface'], height=1).pack(fill=tk.X, padx=18, pady=12)
        
        # Broadcast row
        bc_frame = tk.Frame(sidebar, bg=C['surface'], height=48, cursor='hand2')
        bc_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
        bc_frame.pack_propagate(False)
        
        tk.Canvas(bc_frame, width=8, height=8, highlightthickness=0, bg=C['surface']).place(x=12, y=20)
        tk.Label(bc_frame, text="▸ BROADCAST", font=('SF Mono', 10, 'bold'),
                fg=C['action'], bg=C['surface']).place(x=30, y=14)
        
        bc_frame.bind('<Button-1>', lambda e: self._select_peer('BROADCAST'))
        
        # "CONNECTIONS" label
        tk.Frame(sidebar, bg=C['base'], height=30).pack(fill=tk.X, padx=18)
        tk.Label(sidebar, text="CONNECTIONS", font=('SF Mono', 8, 'bold'),
                fg=C['text_dim'], bg=C['base']).pack(anchor='w', padx=20)
        
        # Scrollable peer container
        peer_wrapper = tk.Frame(sidebar, bg=C['base'])
        peer_wrapper.pack(fill=tk.BOTH, expand=True, padx=10)
        
        self.peer_canvas = tk.Canvas(peer_wrapper, bg=C['base'], highlightthickness=0)
        peer_scroll = tk.Scrollbar(peer_wrapper, orient=tk.VERTICAL, command=self.peer_canvas.yview)
        self.peer_container = tk.Frame(self.peer_canvas, bg=C['base'])
        
        self.peer_container.bind('<Configure>',
            lambda e: self.peer_canvas.configure(scrollregion=self.peer_canvas.bbox('all')))
        
        self.peer_canvas.create_window((0, 0), window=self.peer_container, anchor='nw')
        self.peer_canvas.configure(yscrollcommand=peer_scroll.set)
        self.peer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        peer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === RIGHT PANEL ===
        right = tk.Frame(main, bg=C['void'])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Chat header
        self._build_chat_header(right)
        
        # Content area (chat or system view)
        self.content_frame = tk.Frame(right, bg=C['void'])
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Show system view by default
        self._show_system_view()
        
        # Input area
        self._build_input_area(right)
        
        # Status bar
        self._build_status_bar()
    
    def _build_chat_header(self, parent):
        self.chat_header = tk.Frame(parent, bg=C['void'], height=55)
        self.chat_header.pack(fill=tk.X, padx=25, pady=(15, 0))
        
        self.chat_title = tk.Label(self.chat_header, text="SYSTEM", font=('SF Mono', 14, 'bold'),
                                   fg=C['text_primary'], bg=C['void'])
        self.chat_title.pack(side=tk.LEFT)
        
        self.chat_subtitle = tk.Label(self.chat_header, text="network overview",
                                      font=('SF Mono', 9), fg=C['text_dim'], bg=C['void'])
        self.chat_subtitle.pack(side=tk.LEFT, padx=10)
        
        # Actions (only show when peer selected)
        self.action_frame = tk.Frame(self.chat_header, bg=C['void'])
        self.action_frame.pack(side=tk.RIGHT)
    
    def _build_input_area(self, parent):
        input_frame = tk.Frame(parent, bg=C['base'], height=56)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=25, pady=20)
        input_frame.pack_propagate(False)
        
        self.msg_input = tk.Text(input_frame, bg=C['overlay'], fg=C['text_primary'],
                                 font=('SF Mono', 11), relief=tk.FLAT, wrap=tk.WORD,
                                 insertbackground=C['action'], padx=14, pady=14,
                                 height=2, borderwidth=1, highlightthickness=1,
                                 highlightbackground=C['surface'])
        self.msg_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.msg_input.bind('<Return>', self._send_message)
        self.msg_input.config(state=tk.DISABLED)
        
        # Send indicator
        self.send_frame = tk.Frame(input_frame, bg=C['base'])
        self.send_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.send_btn = tk.Label(self.send_frame, text="TRANSMIT ▸", font=('SF Mono', 9, 'bold'),
                                 fg=C['action'], bg=C['base'], cursor='hand2')
        self.send_btn.pack(pady=14)
        self.send_btn.bind('<Button-1>', self._send_message)
    
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=C['base'], height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        
        self.status_left = tk.Label(bar, text=f"● {MY_IP}:{PORT}  |  ENCRYPTED",
                                    font=('SF Mono', 7), fg=C['text_dim'], bg=C['base'])
        self.status_left.pack(side=tk.LEFT, padx=16)
        
        self.status_right = tk.Label(bar, text="0 CONNECTED",
                                     font=('SF Mono', 7), fg=C['text_dim'], bg=C['base'])
        self.status_right.pack(side=tk.RIGHT, padx=16)
    
    # ========================================================================
    # SYSTEM VIEW (Center panel default state)
    # ========================================================================
    
    def _show_system_view(self):
        for w in self.content_frame.winfo_children():
            w.destroy()
        
        # Live system status panel
        panel = tk.Frame(self.content_frame, bg=C['base'])
        panel.place(relx=0.5, rely=0.5, anchor='center', width=500, height=400)
        
        # Header
        tk.Label(panel, text="⚡ NEON MESH // SYSTEM", font=('SF Mono', 13, 'bold'),
                fg=C['action'], bg=C['base']).pack(pady=(25, 20))
        
        # Status grid
        stats = db.get_stats()
        grid = tk.Frame(panel, bg=C['base'])
        grid.pack(pady=10)
        
        items = [
            ("NODE ID", NODE_ID),
            ("IP ADDRESS", f"{MY_IP}:{PORT}"),
            ("NODES DISCOVERED", str(stats['peers_discovered'])),
            ("ACTIVE CONNECTIONS", str(stats['peers_online'])),
            ("MESSAGES ROUTED", str(stats['total_messages'])),
            ("NETWORK MODE", "MESH (P2P)"),
            ("ENCRYPTION", "AES-256-GCM"),
            ("STATUS", "ONLINE"),
        ]
        
        for i, (label, value) in enumerate(items):
            row = tk.Frame(grid, bg=C['base'])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=f"{label:<20}", font=('SF Mono', 10),
                    fg=C['text_secondary'], bg=C['base']).pack(side=tk.LEFT)
            val_color = C['online'] if value in ['ONLINE', 'MESH (P2P)', 'AES-256-GCM'] else C['text_primary']
            if value.isdigit() and int(value) > 0: val_color = C['action']
            tk.Label(row, text=value, font=('SF Mono', 10, 'bold'),
                    fg=val_color, bg=C['base']).pack(side=tk.RIGHT)
        
        # Activity log
        tk.Frame(panel, bg=C['surface'], height=1).pack(fill=tk.X, padx=30, pady=15)
        
        tk.Label(panel, text="ACTIVITY LOG", font=('SF Mono', 8, 'bold'),
                fg=C['text_dim'], bg=C['base']).pack(anchor='w', padx=30)
        
        log_frame = tk.Frame(panel, bg=C['base'])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        self.log_text = tk.Text(log_frame, bg=C['base'], fg=C['text_secondary'],
                                font=('SF Mono', 8), relief=tk.FLAT,
                                height=8, borderwidth=0, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Typing animation
        self.typing_label = tk.Label(panel, text="> _", font=('SF Mono', 9, 'bold'),
                                     fg=C['action'], bg=C['base'])
        self.typing_label.pack(anchor='w', padx=30, pady=(5, 20))
        
        self._blink_cursor()
        self._update_activity_log()
    
    def _update_activity_log(self):
        if not hasattr(self, 'log_text') or self.current_peer is not None:
            return
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        for entry in activity_log[-12:]:
            self.log_text.insert(tk.END, f"[{entry['time']}] {entry['type']:<10} {entry['detail']}\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)
        
        self.root.after(2000, self._update_activity_log)
    
    def _blink_cursor(self):
        if self.current_peer is not None: return
        current = self.typing_label.cget('text')
        if current.endswith('_'):
            self.typing_label.config(text=current[:-1])
        else:
            self.typing_label.config(text=current + '_')
        self.root.after(600, self._blink_cursor)
    
    # ========================================================================
    # CHAT VIEW
    # ========================================================================
    
    def _show_chat_view(self, peer_id):
        for w in self.content_frame.winfo_children():
            w.destroy()
        
        # Clean system-like message display
        chat_canvas = tk.Canvas(self.content_frame, bg=C['void'], highlightthickness=0)
        chat_scroll = tk.Scrollbar(self.content_frame, orient=tk.VERTICAL, command=chat_canvas.yview)
        
        self.chat_frame = tk.Frame(chat_canvas, bg=C['void'])
        self.chat_frame.bind('<Configure>',
            lambda e: chat_canvas.configure(scrollregion=chat_canvas.bbox('all')))
        
        self.chat_window = chat_canvas.create_window((0, 0), window=self.chat_frame, anchor='nw')
        
        chat_canvas.configure(yscrollcommand=chat_scroll.set)
        chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(25, 0))
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        chat_canvas.bind('<Configure>', lambda e: chat_canvas.itemconfig(self.chat_window, width=e.width))
        
        # Load messages
        msgs = db.get_msgs(peer_id)
        
        if not msgs:
            empty = tk.Frame(self.chat_frame, bg=C['void'])
            empty.pack(expand=True, pady=150)
            tk.Label(empty, text="╔════════════════════════╗", font=('SF Mono', 9),
                    fg=C['text_dim'], bg=C['void']).pack()
            tk.Label(empty, text="║   NO MESSAGES YET      ║", font=('SF Mono', 9),
                    fg=C['text_dim'], bg=C['void']).pack()
            tk.Label(empty, text="║   Type to initiate     ║", font=('SF Mono', 9),
                    fg=C['text_dim'], bg=C['void']).pack()
            tk.Label(empty, text="╚════════════════════════╝", font=('SF Mono', 9),
                    fg=C['text_dim'], bg=C['void']).pack()
        else:
            for msg in msgs:
                self._add_msg_bubble(msg)
        
        self.content_frame.chat_canvas = chat_canvas
        self.root.after(100, lambda: chat_canvas.yview_moveto(1.0))
    
    def _add_msg_bubble(self, msg):
        if not hasattr(self.content_frame, 'chat_frame'):
            return
        
        is_mine = msg['sender'] == NODE_ID
        sender_color = PEER_COLOR if is_mine else db.data['peers'].get(msg['sender'], {}).get('color', C['info'])
        
        frame = tk.Frame(self.chat_frame, bg=C['void'])
        frame.pack(fill=tk.X, pady=4, padx=20)
        
        time_str = datetime.fromtimestamp(msg['time']).strftime("%H:%M:%S")
        
        # Direction arrow
        arrow = ">" if is_mine else "<"
        tk.Label(frame, text=arrow, font=('SF Mono', 9, 'bold'),
                fg=sender_color, bg=C['void']).pack(side=tk.LEFT, padx=(0, 6))
        
        # Sender
        sender_display = "YOU" if is_mine else msg['sender']
        tk.Label(frame, text=f"[{time_str}] {sender_display}", font=('SF Mono', 8, 'bold'),
                fg=sender_color, bg=C['void']).pack(side=tk.LEFT)
        
        # Message content
        content_frame = tk.Frame(self.chat_frame, bg=C['void'])
        content_frame.pack(fill=tk.X, padx=60, pady=(0, 8))
        
        tk.Label(content_frame, text=msg['text'], font=('SF Mono', 10),
                fg=C['text_primary'], bg=C['void'],
                wraplength=550, justify=tk.LEFT).pack(anchor='w')
        
        self.msg_bubbles.append(frame)
    
    # ========================================================================
    # PEER SELECTION
    # ========================================================================
    
    def _select_peer(self, peer_id):
        self.current_peer = peer_id
        sys_mode.set_mode(sys_mode.ACTIVE, f"connected to {peer_id}")
        self._refresh_peers()
        
        if peer_id == 'BROADCAST':
            self.chat_title.config(text="BROADCAST", fg=C['action'])
            self.chat_subtitle.config(text="→ all connected nodes")
        else:
            data = db.data['peers'].get(peer_id, {})
            color = data.get('color', C['info'])
            is_online = time.time() - data.get('last_seen', 0) < 15
            
            self.chat_title.config(text=peer_id, fg=color)
            self.chat_subtitle.config(text="● online" if is_online else "○ offline",
                                      fg=C['online'] if is_online else C['text_dim'])
        
        self._add_action_buttons()
        self._show_chat_view(peer_id)
        self.msg_input.config(state=tk.NORMAL, highlightbackground=C['action'])
        self.msg_input.focus()
        
        if peer_id != 'BROADCAST':
            db.clear_unread(peer_id)
    
    def _add_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()
        
        for text, cmd in [("CLEAR", self._clear_chat), ("CLOSE", self._close_chat)]:
            btn = tk.Label(self.action_frame, text=text, font=('SF Mono', 8),
                          fg=C['text_dim'], bg=C['void'], cursor='hand2')
            btn.pack(side=tk.RIGHT, padx=10)
            btn.bind('<Enter>', lambda e, b=btn: b.configure(fg=C['warn'] if text == 'CLOSE' else C['action']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(fg=C['text_dim']))
            btn.bind('<Button-1>', cmd)
    
    # ========================================================================
    # MESSAGING
    # ========================================================================
    
    def _send_message(self, event=None):
        if not self.current_peer: return 'break'
        
        text = self.msg_input.get('1.0', tk.END).strip()
        if not text: return 'break'
        
        sys_mode.pulse_transmit()
        log_activity("TRANSMIT", f"→ {self.current_peer}: {text[:30]}...")
        
        is_bc = self.current_peer == 'BROADCAST'
        
        pkt = json.dumps({
            'type': 'message', 'from': NODE_ID, 'content': text,
            'broadcast': is_bc, 'time': time.time()
        }).encode()
        
        if is_bc:
            for pid, pd in db.data['peers'].items():
                if pd.get('ip'):
                    try: self.sock.sendto(pkt, (pd['ip'], PORT))
                    except: pass
            db.add_msg('BROADCAST', NODE_ID, text)
        else:
            pd = db.data['peers'].get(self.current_peer, {})
            if pd.get('ip'):
                try: self.sock.sendto(pkt, (pd['ip'], PORT))
                except: pass
            db.add_msg(self.current_peer, NODE_ID, text)
        
        # Add to chat view immediately
        msg = db.get_msgs(self.current_peer)[-1]
        self._add_msg_bubble(msg)
        
        self.msg_input.delete('1.0', tk.END)
        
        if hasattr(self.content_frame, 'chat_canvas'):
            self.root.after(100, lambda: self.content_frame.chat_canvas.yview_moveto(1.0))
        
        return 'break'
    
    # ========================================================================
    # ACTIONS
    # ========================================================================
    
    def _clear_chat(self, event=None):
        if self.current_peer and self.current_peer != 'BROADCAST':
            db.delete_chat(self.current_peer)
            self._show_chat_view(self.current_peer)
    
    def _close_chat(self, event=None):
        self.current_peer = None
        sys_mode.set_mode(sys_mode.IDLE)
        self._show_system_view()
        self.chat_title.config(text="SYSTEM", fg=C['text_primary'])
        self.chat_subtitle.config(text="network overview")
        self.msg_input.config(state=tk.DISABLED, highlightbackground=C['surface'])
        for w in self.action_frame.winfo_children():
            w.destroy()
        self._refresh_peers()
    
    # ========================================================================
    # NETWORK
    # ========================================================================
    
    def _setup_network(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', PORT))
        
        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._discover_listen, daemon=True).start()
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
    
    def _broadcast_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        while self.running:
            try:
                pkt = json.dumps({'type': 'DISCOVER', 'id': NODE_ID, 'ip': MY_IP})
                s.sendto(pkt.encode(), ('255.255.255.255', DISCOVERY_PORT))
            except: pass
            time.sleep(5)
    
    def _discover_listen(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind(('0.0.0.0', DISCOVERY_PORT))
        except: return
        while self.running:
            try:
                data, addr = s.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get('type') == 'DISCOVER' and msg['id'] != NODE_ID:
                    is_new = msg['id'] not in db.data['peers']
                    db.add_peer(msg['id'], msg['ip'])
                    if is_new:
                        log_activity("DISCOVERY", f"New node: {msg['id']} @ {msg['ip']}")
                    self.root.after(0, self._refresh_peers)
            except: pass
    
    def _recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)
                msg = json.loads(data.decode())
                if msg.get('type') == 'message':
                    sender = msg['from']
                    text = msg.get('content', '')
                    is_bc = msg.get('broadcast', False)
                    peer = 'BROADCAST' if is_bc else sender
                    
                    db.add_peer(sender, addr[0])
                    db.add_msg(peer, sender, text)
                    log_activity("RECEIVE", f"← {sender}: {text[:30]}...")
                    
                    self.root.after(0, lambda p=peer, s=sender: self._on_msg(p, s))
                    self.root.after(0, self._refresh_peers)
            except: pass
    
    def _on_msg(self, peer, sender):
        if self.current_peer == peer:
            msgs = db.get_msgs(peer)
            if msgs:
                self._add_msg_bubble(msgs[-1])
                if hasattr(self.content_frame, 'chat_canvas'):
                    self.root.after(100, lambda: self.content_frame.chat_canvas.yview_moveto(1.0))
        else:
            self._refresh_peers()
    
    # ========================================================================
    # PEER LIST
    # ========================================================================
    
    def _refresh_peers(self):
        for w in self.peer_container.winfo_children():
            w.destroy()
        
        online_count = 0
        peers = sorted(db.data['peers'].items(),
                      key=lambda x: -x[1].get('last_seen', 0))
        
        for pid, pd in peers:
            if time.time() - pd.get('last_seen', 0) < 15:
                online_count += 1
            selected = (self.current_peer == pid)
            card = PeerRow(self.peer_container, pid, pd, selected, on_select=self._select_peer)
            card.pack(fill=tk.X, pady=1)
        
        self.status_right.config(text=f"{online_count} CONNECTED")
    
    def _on_mode_change(self, mode):
        colors = {SystemMode.IDLE: C['text_secondary'], SystemMode.CONNECTING: C['info'],
                  SystemMode.ACTIVE: C['online'], SystemMode.TRANSMITTING: C['action']}
        self.mode_label.config(text=f"NEON MESH [{mode}]", fg=colors.get(mode, C['text_secondary']))
    
    def _start_system_loop(self):
        self.root.after(200, self._refresh_peers)
    
    # ========================================================================
    # RUN
    # ========================================================================
    
    def run(self):
        self.root.protocol('WM_DELETE_WINDOW', self._close)
        self.root.mainloop()
    
    def _close(self):
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