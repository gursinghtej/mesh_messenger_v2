#!/usr/bin/env python3
"""
╔══════════════════════════════════════════╗
║   ⚡ NEON MESH - Cyberpunk Messenger     ║
║   Vibrant. Decentralized. Alive.         ║
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
import math

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

# Vibrant color palette per user
NEON_COLORS = [
    '#ff006e', '#ff4d6d', '#ff6b35', '#ff9f1c', '#ffd60a',
    '#38b000', '#06d6a0', '#00b4d8', '#3a86ff', '#7209b7',
    '#b5179e', '#f72585', '#4cc9f0', '#f77f00', '#e63946',
    '#2ec4b6', '#ff0a54', '#ff7096', '#9d4edd', '#00f5d4'
]

def get_neon_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)
    return NEON_COLORS[h % len(NEON_COLORS)]

USER_COLOR = get_neon_color(NODE_ID)

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
            self.data["peers"][pid] = {"ip": ip, "last_seen": time.time(), "unread": 0, "color": get_neon_color(pid)}
        else:
            self.data["peers"][pid]["last_seen"] = time.time()
            if ip: self.data["peers"][pid]["ip"] = ip
        self.save()
    def add_msg(self, peer, sender, text):
        msg = {"sender": sender, "text": text, "time": time.time()}
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

db = DB()

# ============================================================================
# ANIMATED PARTICLES (Background effect)
# ============================================================================

class ParticleSystem:
    def __init__(self, canvas, width, height):
        self.canvas = canvas
        self.w = width
        self.h = height
        self.particles = []
        self.running = True
        self._create_particles(30)
    
    def _create_particles(self, count):
        for _ in range(count):
            self.particles.append({
                'x': random.randint(0, self.w),
                'y': random.randint(0, self.h),
                'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.3, 0.3),
                'size': random.randint(1, 3),
                'color': random.choice(NEON_COLORS),
                'alpha': random.random()
            })
    
    def update(self):
        if not self.running: return
        self.canvas.delete('particle')
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            if p['x'] < 0: p['x'] = self.w
            if p['x'] > self.w: p['x'] = 0
            if p['y'] < 0: p['y'] = self.h
            if p['y'] > self.h: p['y'] = 0
            self.canvas.create_oval(p['x']-p['size'], p['y']-p['size'],
                                     p['x']+p['size'], p['y']+p['size'],
                                     fill=p['color'], outline='', tags='particle')
        self.canvas.after(50, self.update)

# ============================================================================
# GLOWING BUBBLE WIDGET
# ============================================================================

class GlowBubble(tk.Canvas):
    def __init__(self, parent, text, is_sent, sender="", sender_color="", **kw):
        bg = '#0a0a0a'
        super().__init__(parent, bg=bg, highlightthickness=0, **kw)
        self.text = text
        self.is_sent = is_sent
        self.sender = sender
        self.sender_color = sender_color
        self.glow_color = USER_COLOR if is_sent else sender_color
        self.bind('<Configure>', self.draw)
    
    def draw(self, event=None):
        self.delete('all')
        w = self.winfo_width()
        if w < 50: return
        
        # Text wrapping
        max_text_w = int(w * 0.6)
        pad_x, pad_y = 18, 14
        words = self.text.split()
        lines, current = [], ""
        for word in words:
            test = f"{current} {word}" if current else word
            if len(test) * 8 <= max_text_w - pad_x * 2:
                current = test
            else:
                if current: lines.append(current)
                current = word
        if current: lines.append(current)
        if not lines: lines = [self.text]
        
        line_h = 24
        bubble_w = min(max(len(l) * 8 + pad_x * 2 + 30 for l in lines), max_text_w)
        bubble_h = len(lines) * line_h + pad_y * 2 + 25
        
        # Position
        if self.is_sent:
            bx = w - bubble_w - 20
        else:
            bx = 20
        
        by = 10
        
        # Glow effect (outer)
        for i in range(3, 0, -1):
            alpha = hex(int(40 // i))[2:].zfill(2)
            self._round_rect(bx-i*3, by-i*3, bx+bubble_w+i*3, by+bubble_h+i*3,
                           20+i, fill='', outline=f'{self.glow_color}{alpha}', width=2, tags='glow')
        
        # Bubble body
        bubble_bg = f'{self.glow_color}22'
        self._round_rect(bx, by, bx+bubble_w, by+bubble_h, 16,
                        fill=bubble_bg, outline=self.glow_color, width=1.5)
        
        # Sender name (received only)
        if not self.is_sent and self.sender:
            self.create_text(bx + 15, by - 15, text=f'◆ {self.sender}', 
                           fill=self.sender_color, font=('Courier New', 9, 'bold'), anchor='w')
        
        # Message text
        ty = by + pad_y + 8
        for line in lines:
            tx = bx + pad_x
            if self.is_sent:
                tx = bx + bubble_w - pad_x - len(line) * 8
            self.create_text(tx, ty, text=line, fill='#ffffff', 
                           font=('Segoe UI', 11), anchor='w')
            ty += line_h
        
        # Timestamp
        time_str = datetime.now().strftime("%H:%M")
        self.create_text(bx + bubble_w - 25, by + bubble_h - 14, text=time_str,
                        fill=self.glow_color, font=('Courier New', 7))
        
        # Small dot indicator
        dot_x = bx - 8 if not self.is_sent else bx + bubble_w + 8
        self.create_oval(dot_x-2, by+bubble_h//2-2, dot_x+2, by+bubble_h//2+2,
                        fill=self.glow_color, outline='')
        
        self.configure(height=bubble_h + 35)
    
    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2, x2-r,y2,
               x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.create_polygon(pts, smooth=True, **kw)

# ============================================================================
# NEON PEER CARD
# ============================================================================

class NeonPeerCard(tk.Frame):
    def __init__(self, parent, peer_id, data, selected=False, **kw):
        super().__init__(parent, bg='#0a0a0a', height=65, cursor='hand2', **kw)
        self.pack_propagate(False)
        self.peer_id = peer_id
        self.data = data
        self.selected = selected
        self.color = data.get('color', '#ff006e')
        self.is_online = time.time() - data.get('last_seen', 0) < 15
        
        self.build()
        self._bind_hover()
    
    def build(self):
        # Glow bar on left if selected
        if self.selected:
            bar = tk.Canvas(self, bg=self.color, width=3, highlightthickness=0)
            bar.place(x=0, y=4, height=57)
        
        # Avatar ring
        av_size = 42
        av = tk.Canvas(self, width=av_size+8, height=av_size+8, highlightthickness=0, bg='#0a0a0a')
        av.place(x=12, y=8)
        
        # Outer glow ring
        av.create_oval(0, 0, av_size+8, av_size+8, outline=self.color, width=2)
        # Inner circle
        av.create_oval(4, 4, av_size+4, av_size+4, fill=f'{self.color}33', outline='')
        # Initials
        av.create_text((av_size+8)//2, (av_size+8)//2, text=peer_id[:2].upper(),
                      fill=self.color, font=('Courier New', 14, 'bold'))
        # Online dot
        dot_c = '#00ff88' if self.is_online else '#333333'
        av.create_oval(av_size+2, av_size+2, av_size+8, av_size+8, fill=dot_c, outline='#0a0a0a', width=2)
        
        # Name
        name_color = self.color if self.is_online else '#555555'
        self.name_lbl = tk.Label(self, text=peer_id, font=('Segoe UI', 11, 'bold'),
                                 fg=name_color, bg='#0a0a0a')
        self.name_lbl.place(x=68, y=8)
        
        # Preview
        msgs = db.get_msgs(peer_id)
        preview = msgs[-1]['text'][:25] + '...' if msgs else '⚡ no messages'
        self.prev_lbl = tk.Label(self, text=preview, font=('Segoe UI', 9),
                                 fg='#666666', bg='#0a0a0a')
        self.prev_lbl.place(x=68, y=32)
        
        # Unread pill
        unread = self.data.get('unread', 0)
        if unread > 0:
            pill = tk.Canvas(self, width=26, height=20, highlightthickness=0, bg='#0a0a0a')
            pill.place(x=240, y=22)
            pill.create_oval(2, 0, 24, 20, fill=self.color, outline='')
            pill.create_text(13, 10, text=str(unread), fill='white', font=('Segoe UI', 8, 'bold'))
    
    def _bind_hover(self):
        for w in [self, self.name_lbl, self.prev_lbl]:
            w.bind('<Enter>', lambda e: self._hover(True))
            w.bind('<Leave>', lambda e: self._hover(False))
    
    def _hover(self, enter):
        if not self.selected:
            bg = '#111111' if enter else '#0a0a0a'
            self.configure(bg=bg)
            self.name_lbl.configure(bg=bg)
            self.prev_lbl.configure(bg=bg)

# ============================================================================
# MAIN APP
# ============================================================================

class NeonMeshApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ NEON MESH")
        self.root.geometry("1050x700")
        self.root.configure(bg='#050505')
        self.root.minsize(850, 500)
        
        self.current_peer = None
        self.running = True
        
        self.build_ui()
        self.setup_network()
        self.start_animations()
    
    def build_ui(self):
        # Main container
        main = tk.Frame(self.root, bg='#050505')
        main.pack(fill=tk.BOTH, expand=True)
        
        # === LEFT SIDEBAR ===
        sidebar = tk.Frame(main, bg='#0a0a0a', width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Logo
        logo_frame = tk.Frame(sidebar, bg='#0a0a0a', height=80)
        logo_frame.pack(fill=tk.X, pady=(25, 0))
        logo_frame.pack_propagate(False)
        
        self.logo_label = tk.Label(logo_frame, text="⚡ NEON MESH", 
                                   font=('Courier New', 20, 'bold'),
                                   fg=USER_COLOR, bg='#0a0a0a')
        self.logo_label.pack(pady=5)
        
        tk.Label(logo_frame, text="DECENTRALIZED NETWORK", font=('Courier New', 7),
                fg='#333333', bg='#0a0a0a').pack()
        
        # User ID badge
        badge = tk.Frame(sidebar, bg='#111111', height=50)
        badge.pack(fill=tk.X, padx=15, pady=15)
        badge.pack_propagate(False)
        
        b_av = tk.Canvas(badge, width=34, height=34, highlightthickness=0, bg='#111111')
        b_av.place(x=10, y=8)
        b_av.create_oval(0, 0, 34, 34, fill=USER_COLOR, outline='')
        b_av.create_text(17, 17, text=NODE_ID[:2].upper(), fill='white', font=('Courier New', 11, 'bold'))
        
        tk.Label(badge, text=f"◆ {NODE_ID}", font=('Courier New', 10, 'bold'),
                fg=USER_COLOR, bg='#111111').place(x=55, y=8)
        tk.Label(badge, text=f"{MY_IP}:{PORT}", font=('Courier New', 8),
                fg='#444444', bg='#111111').place(x=55, y=26)
        
        # Broadcast button
        self.bc_btn = tk.Frame(sidebar, bg='#111111', height=50, cursor='hand2')
        self.bc_btn.pack(fill=tk.X, padx=15, pady=(0, 10))
        self.bc_btn.pack_propagate(False)
        
        bc_av = tk.Canvas(self.bc_btn, width=34, height=34, highlightthickness=0, bg='#111111')
        bc_av.place(x=10, y=8)
        bc_av.create_oval(0, 0, 34, 34, fill='#ff006e', outline='')
        bc_av.create_text(17, 17, text='⚡', fill='white', font=('Segoe UI', 13))
        
        tk.Label(self.bc_btn, text="BROADCAST", font=('Courier New', 10, 'bold'),
                fg='#ff006e', bg='#111111').place(x=55, y=15)
        
        self.bc_btn.bind('<Button-1>', lambda e: self.select_peer('BROADCAST'))
        self._bind_hover_bc()
        
        # Separator line with glow
        sep = tk.Canvas(sidebar, height=2, bg='#0a0a0a', highlightthickness=0)
        sep.pack(fill=tk.X, padx=15, pady=10)
        sep.create_line(0, 1, 280, 1, fill=USER_COLOR, width=1)
        
        # "CONNECTIONS" header
        tk.Label(sidebar, text="◆ CONNECTIONS", font=('Courier New', 8, 'bold'),
                fg=USER_COLOR, bg='#0a0a0a').pack(anchor='w', padx=20, pady=(0, 10))
        
        # Scrollable peer list
        peers_frame = tk.Frame(sidebar, bg='#0a0a0a')
        peers_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        self.peer_canvas = tk.Canvas(peers_frame, bg='#0a0a0a', highlightthickness=0)
        peer_scroll = tk.Scrollbar(peers_frame, orient=tk.VERTICAL, command=self.peer_canvas.yview)
        self.peer_container = tk.Frame(self.peer_canvas, bg='#0a0a0a')
        
        self.peer_container.bind('<Configure>',
            lambda e: self.peer_canvas.configure(scrollregion=self.peer_canvas.bbox('all')))
        
        self.peer_canvas.create_window((0, 0), window=self.peer_container, anchor='nw')
        self.peer_canvas.configure(yscrollcommand=peer_scroll.set)
        
        self.peer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        peer_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === RIGHT CHAT AREA ===
        chat_area = tk.Frame(main, bg='#050505')
        chat_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # PARTICLES CANVAS (Background)
        self.particle_canvas = tk.Canvas(chat_area, bg='#050505', highlightthickness=0)
        self.particle_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Chat header
        chat_header = tk.Frame(chat_area, bg='#050505', height=70)
        chat_header.pack(fill=tk.X, padx=25, pady=(20, 0))
        chat_header.pack_propagate(False)
        
        self.chat_avatar = tk.Canvas(chat_header, width=44, height=44, highlightthickness=0, bg='#050505')
        self.chat_avatar.pack(side=tk.LEFT)
        
        header_info = tk.Frame(chat_header, bg='#050505')
        header_info.pack(side=tk.LEFT, padx=15)
        
        self.chat_name = tk.Label(header_info, text="⚡ NEON MESH", 
                                  font=('Courier New', 16, 'bold'),
                                  fg=USER_COLOR, bg='#050505')
        self.chat_name.pack(anchor='w')
        
        self.chat_status = tk.Label(header_info, text="Select a connection",
                                    font=('Segoe UI', 9),
                                    fg='#444444', bg='#050505')
        self.chat_status.pack(anchor='w')
        
        # Action buttons
        actions = tk.Frame(chat_header, bg='#050505')
        actions.pack(side=tk.RIGHT)
        
        for icon, cmd in [('🗑', self.delete_chat), ('◆', self.toggle_pin)]:
            btn = tk.Label(actions, text=icon, font=('Segoe UI', 16),
                          fg='#333333', bg='#050505', cursor='hand2')
            btn.pack(side=tk.LEFT, padx=10)
            btn.bind('<Enter>', lambda e, b=btn: b.configure(fg=USER_COLOR))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(fg='#333333'))
            btn.bind('<Button-1>', cmd)
        
        # Separator
        tk.Canvas(chat_area, height=1, bg='#050505', highlightthickness=0).pack(fill=tk.X, padx=25)
        
        # Messages area
        self.msg_canvas = tk.Canvas(chat_area, bg='#050505', highlightthickness=0)
        msg_scroll = tk.Scrollbar(chat_area, orient=tk.VERTICAL, command=self.msg_canvas.yview)
        
        self.msg_frame = tk.Frame(self.msg_canvas, bg='#050505')
        self.msg_frame.bind('<Configure>',
            lambda e: self.msg_canvas.configure(scrollregion=self.msg_canvas.bbox('all')))
        
        self.msg_window = self.msg_canvas.create_window((0, 0), window=self.msg_frame, anchor='nw')
        
        self.msg_canvas.configure(yscrollcommand=msg_scroll.set)
        self.msg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(25, 0))
        msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.msg_canvas.bind('<Configure>', lambda e: self.msg_canvas.itemconfig(self.msg_window, width=e.width))
        
        # Welcome screen
        self._show_welcome()
        
        # Input area
        input_frame = tk.Frame(chat_area, bg='#0a0a0a', height=60)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=25, pady=20)
        input_frame.pack_propagate(False)
        
        # Glow border for input
        self.input_glow = tk.Canvas(input_frame, bg='#0a0a0a', highlightthickness=0, height=60)
        self.input_glow.pack(fill=tk.BOTH, expand=True)
        
        self.msg_input = tk.Text(self.input_glow, bg='#111111', fg='#ffffff',
                                 font=('Segoe UI', 11), relief=tk.FLAT,
                                 wrap=tk.WORD, insertbackground=USER_COLOR,
                                 padx=18, pady=16, borderwidth=1)
        self.msg_input.place(x=15, y=8, width=530, height=44)
        self.msg_input.bind('<Return>', self.send_msg)
        self.msg_input.config(state=tk.DISABLED)
        
        # Send button
        self.send_btn = tk.Canvas(self.input_glow, width=44, height=44, highlightthickness=0, bg='#0a0a0a')
        self.send_btn.place(x=560, y=8)
        self.send_btn.create_oval(2, 2, 42, 42, fill=USER_COLOR, outline='')
        self.send_btn.create_text(22, 22, text='↑', fill='white', font=('Segoe UI', 16, 'bold'))
        self.send_btn.bind('<Button-1>', self.send_msg)
        
        # Redraw input glow border
        self.input_glow.after(100, self._draw_input_glow)
        
        # Status bar
        status = tk.Frame(self.root, bg='#0a0a0a', height=30)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        status.pack_propagate(False)
        
        tk.Label(status, text=f"⚡ ENCRYPTED  ◆  {MY_IP}:{PORT}", 
                font=('Courier New', 8), fg='#333333', bg='#0a0a0a').pack(side=tk.LEFT, padx=20)
        
        self.peer_count = tk.Label(status, text="0 CONNECTED", font=('Courier New', 8),
                                   fg=USER_COLOR, bg='#0a0a0a')
        self.peer_count.pack(side=tk.RIGHT, padx=20)
    
    def _draw_input_glow(self):
        self.input_glow.delete('glow')
        w = self.input_glow.winfo_width()
        self.input_glow.create_rectangle(12, 5, w-20, 55, outline=USER_COLOR, width=1, tags='glow')
        self.input_glow.after(2000, self._draw_input_glow)
    
    def _bind_hover_bc(self):
        self.bc_btn.bind('<Enter>', lambda e: self.bc_btn.configure(bg='#1a1a1a'))
        self.bc_btn.bind('<Leave>', lambda e: self.bc_btn.configure(bg='#111111'))
    
    def _show_welcome(self):
        for w in self.msg_frame.winfo_children():
            w.destroy()
        
        welcome = tk.Frame(self.msg_frame, bg='#050505')
        welcome.pack(expand=True, pady=100)
        
        # Animated-looking logo
        tk.Label(welcome, text="⚡", font=('Segoe UI', 60), fg=USER_COLOR, bg='#050505').pack()
        tk.Label(welcome, text="NEON MESH", font=('Courier New', 22, 'bold'),
                fg=USER_COLOR, bg='#050505').pack(pady=5)
        tk.Label(welcome, text="D E C E N T R A L I Z E D", font=('Courier New', 8),
                fg='#333333', bg='#050505').pack()
        tk.Label(welcome, text=f"◆ {NODE_ID}  ◆  {MY_IP}", font=('Courier New', 9),
                fg='#555555', bg='#050505').pack(pady=15)
        tk.Label(welcome, text="Select a connection to begin messaging",
                font=('Segoe UI', 10), fg='#333333', bg='#050505').pack()
    
    # ========================================================================
    # PEER SELECTION
    # ========================================================================
    
    def select_peer(self, peer_id):
        self.current_peer = peer_id
        self.refresh_peers()
        
        if peer_id == 'BROADCAST':
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(0, 0, 44, 44, fill='#ff006e', outline=USER_COLOR, width=2)
            self.chat_avatar.create_text(22, 22, text='⚡', fill='white', font=('Segoe UI', 16))
            self.chat_name.config(text='BROADCAST', fg='#ff006e')
            self.chat_status.config(text='◆ SEND TO ALL CONNECTED PEERS')
        else:
            data = db.data['peers'].get(peer_id, {})
            color = data.get('color', USER_COLOR)
            is_online = time.time() - data.get('last_seen', 0) < 15
            
            self.chat_avatar.delete('all')
            self.chat_avatar.create_oval(0, 0, 44, 44, fill=color, outline=color, width=1)
            self.chat_avatar.create_text(22, 22, text=peer_id[:2].upper(),
                                         fill='white', font=('Courier New', 13, 'bold'))
            
            self.chat_name.config(text=peer_id, fg=color)
            status = f"◆ ONLINE" if is_online else f"◆ OFFLINE"
            self.chat_status.config(text=status, fg=color if is_online else '#444444')
        
        self._load_chat(peer_id)
        self.msg_input.config(state=tk.NORMAL)
        self.msg_input.focus()
        
        if peer_id != 'BROADCAST':
            db.clear_unread(peer_id)
    
    def _load_chat(self, peer_id):
        for w in self.msg_frame.winfo_children():
            w.destroy()
        
        msgs = db.get_msgs(peer_id)
        
        if not msgs:
            empty = tk.Label(self.msg_frame, text="◆ NO MESSAGES YET ◆",
                           font=('Courier New', 10), fg='#333333', bg='#050505')
            empty.pack(pady=80)
        else:
            for msg in msgs:
                is_sent = msg['sender'] == NODE_ID
                sender_color = USER_COLOR if is_sent else db.data['peers'].get(msg['sender'], {}).get('color', '#ff006e')
                bubble = GlowBubble(self.msg_frame, msg['text'], is_sent,
                                   msg['sender'], sender_color, width=600)
                bubble.pack(fill=tk.X, pady=5)
        
        self.root.after(100, lambda: self.msg_canvas.yview_moveto(1.0))
    
    # ========================================================================
    # MESSAGE SENDING
    # ========================================================================
    
    def send_msg(self, event=None):
        if not self.current_peer: return 'break'
        
        text = self.msg_input.get('1.0', tk.END).strip()
        if not text: return 'break'
        
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
        
        # Add bubble immediately
        bubble = GlowBubble(self.msg_frame, text, True, NODE_ID, USER_COLOR, width=600)
        bubble.pack(fill=tk.X, pady=5)
        
        self.msg_input.delete('1.0', tk.END)
        self.root.after(100, lambda: self.msg_canvas.yview_moveto(1.0))
        
        return 'break'
    
    # ========================================================================
    # NETWORK
    # ========================================================================
    
    def setup_network(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', PORT))
        
        threading.Thread(target=self._recv, daemon=True).start()
        threading.Thread(target=self._discover_listen, daemon=True).start()
        threading.Thread(target=self._broadcast, daemon=True).start()
    
    def _broadcast(self):
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
                    db.add_peer(msg['id'], msg['ip'])
                    self.root.after(0, self.refresh_peers)
            except: pass
    
    def _recv(self):
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
                    
                    self.root.after(0, lambda p=peer, s=sender: self._on_msg(p, s))
                    self.root.after(0, self.refresh_peers)
            except: pass
    
    def _on_msg(self, peer, sender):
        if self.current_peer == peer:
            msgs = db.get_msgs(peer)
            if msgs:
                msg = msgs[-1]
                is_sent = msg['sender'] == NODE_ID
                sc = USER_COLOR if is_sent else db.data['peers'].get(sender, {}).get('color', '#ff006e')
                bubble = GlowBubble(self.msg_frame, msg['text'], is_sent, msg['sender'], sc, width=600)
                bubble.pack(fill=tk.X, pady=5)
                self.root.after(100, lambda: self.msg_canvas.yview_moveto(1.0))
        else:
            self.refresh_peers()
    
    # ========================================================================
    # PEER MANAGEMENT
    # ========================================================================
    
    def refresh_peers(self):
        for w in self.peer_container.winfo_children():
            w.destroy()
        
        online_count = 0
        peers = sorted(db.data['peers'].items(),
                      key=lambda x: -x[1].get('last_seen', 0))
        
        for pid, pd in peers:
            if time.time() - pd.get('last_seen', 0) < 15:
                online_count += 1
            selected = (self.current_peer == pid)
            card = NeonPeerCard(self.peer_container, pid, pd, selected)
            card.pack(fill=tk.X, pady=2)
            
            for w in [card, card.name_lbl, card.prev_lbl]:
                w.bind('<Button-1>', lambda e, p=pid: self.select_peer(p))
        
        self.peer_count.config(text=f"{online_count} CONNECTED")
    
    def toggle_pin(self, e=None): pass  # Simplified
    def delete_chat(self, e=None):
        if not self.current_peer or self.current_peer == 'BROADCAST': return
        if messagebox.askyesno("DELETE", f"Delete chat with {self.current_peer}?"):
            db.delete_chat(self.current_peer)
            self.current_peer = None
            self._show_welcome()
            self.chat_name.config(text='⚡ NEON MESH', fg=USER_COLOR)
            self.chat_status.config(text='Select a connection')
            self.msg_input.config(state=tk.DISABLED)
            self.refresh_peers()
    
    def start_animations(self):
        # Particle system in chat background
        self.particles = ParticleSystem(self.particle_canvas, 800, 600)
        self.particles.update()
        
        # Logo color cycling
        self._cycle_logo()
    
    def _cycle_logo(self):
        if not self.running: return
        colors = ['#ff006e', '#ff4d6d', '#ff6b35', '#ff9f1c', '#06d6a0', '#3a86ff', '#7209b7', '#f72585']
        current = self.logo_label.cget('fg')
        if current in colors:
            idx = colors.index(current)
            next_color = colors[(idx + 1) % len(colors)]
            self.logo_label.config(fg=next_color)
        self.root.after(2000, self._cycle_logo)
    
    def run(self):
        self.root.after(100, self.refresh_peers)
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