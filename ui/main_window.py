"""
Main GUI window with separate chats, status indicators, and all features
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import time
import queue
import json
from datetime import datetime
from pathlib import Path

from config import profile, NODE_ID, MY_IP, PORT
from storage.database import db
from network.transport import ReliableTransport
from media.file_handler import FileHandler
from ui.styles import Colors, Fonts, setup_styles

class MeshMessengerGUI:
    def __init__(self, root, transport, file_handler):
        self.root = root
        self.transport = transport
        self.file_handler = file_handler
        self.colors = Colors()
        self.fonts = Fonts()
        
        # State
        self.current_peer = None  # Currently selected peer for chat
        self.chat_widgets = {}    # peer_id -> chat display widget
        self.message_status = {}  # msg_id -> status widget
        self.gui_queue = queue.Queue()
        self.running = True
        
        # Setup callbacks
        self.transport.gui_callback = self.handle_network_event
        self.file_handler.gui_callback = self.handle_file_event
        
        # Build UI
        self.setup_window()
        self.build_ui()
        
        # Start queue processor
        self.process_queue()
        
        # Periodic updates
        self.update_peer_status()
        
    def setup_window(self):
        self.root.title(f"🌐 Mesh Messenger - {profile.username}")
        self.root.geometry("1100x700")
        self.root.configure(bg=self.colors.bg_dark)
        
        # Set icon if available
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
    
    def build_ui(self):
        # Main container
        main_frame = tk.Frame(self.root, bg=self.colors.bg_dark)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== SIDEBAR =====
        sidebar = tk.Frame(main_frame, bg=self.colors.bg_medium, width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))
        sidebar.pack_propagate(False)
        
        # Profile section
        self.build_profile_section(sidebar)
        
        # Search bar
        self.build_search_bar(sidebar)
        
        # Conversations list
        self.build_conversation_list(sidebar)
        
        # ===== MAIN CHAT AREA =====
        chat_container = tk.Frame(main_frame, bg=self.colors.bg_dark)
        chat_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Chat header
        self.build_chat_header(chat_container)
        
        # Chat display area (notebook for multiple chats)
        self.chat_notebook = ttk.Notebook(chat_container)
        self.chat_notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Welcome tab
        self.create_welcome_tab()
        
        # Message input area
        self.build_input_area(chat_container)
        
        # ===== RIGHT SIDEBAR (Peer info) =====
        right_sidebar = tk.Frame(main_frame, bg=self.colors.bg_medium, width=220)
        right_sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(1, 0))
        right_sidebar.pack_propagate(False)
        
        self.build_peer_info_panel(right_sidebar)
        
        # ===== STATUS BAR =====
        status_bar = tk.Frame(self.root, bg=self.colors.bg_light, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        status_bar.pack_propagate(False)
        
        self.status_label = tk.Label(status_bar, 
                                     text=f"🟢 Online | {MY_IP}:{PORT} | 🔐 Encrypted",
                                     fg=self.colors.success, bg=self.colors.bg_light,
                                     font=self.fonts.small)
        self.status_label.pack(side=tk.LEFT, padx=10, pady=3)
        
        self.connection_label = tk.Label(status_bar,
                                         text="📡 0 peers",
                                         fg=self.colors.text_dim, bg=self.colors.bg_light,
                                         font=self.fonts.small)
        self.connection_label.pack(side=tk.RIGHT, padx=10, pady=3)
    
    def build_profile_section(self, parent):
        profile_frame = tk.Frame(parent, bg=self.colors.bg_light, height=80)
        profile_frame.pack(fill=tk.X, padx=10, pady=10)
        profile_frame.pack_propagate(False)
        
        # Avatar placeholder
        avatar_frame = tk.Frame(profile_frame, bg=self.colors.accent, width=50, height=50)
        avatar_frame.place(x=15, y=15)
        
        avatar_label = tk.Label(avatar_frame, text=profile.username[:2].upper(),
                                fg='white', bg=self.colors.accent, font=self.fonts.header)
        avatar_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Username
        name_label = tk.Label(profile_frame, text=profile.username,
                              fg=self.colors.text_light, bg=self.colors.bg_light,
                              font=self.fonts.bold)
        name_label.place(x=80, y=15)
        
        # Status
        self.profile_status = tk.Label(profile_frame, text=f"🟢 {profile.status}",
                                       fg=self.colors.success, bg=self.colors.bg_light,
                                       font=self.fonts.small, cursor="hand2")
        self.profile_status.place(x=80, y=40)
        self.profile_status.bind("<Button-1>", self.change_status)
        
        # Settings button
        settings_btn = tk.Label(profile_frame, text="⚙️", fg=self.colors.text_dim,
                                bg=self.colors.bg_light, font=self.fonts.normal, cursor="hand2")
        settings_btn.place(x=240, y=15)
        settings_btn.bind("<Button-1>", self.open_settings)
    
    def build_search_bar(self, parent):
        search_frame = tk.Frame(parent, bg=self.colors.bg_medium)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                bg=self.colors.bg_light, fg=self.colors.text_light,
                                font=self.fonts.normal, relief=tk.FLAT,
                                insertbackground=self.colors.success)
        search_entry.pack(fill=tk.X, ipady=8)
        
        # Placeholder
        search_entry.insert(0, "🔍 Search messages...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, tk.END))
        search_entry.bind("<FocusOut>", lambda e: search_entry.insert(0, "🔍 Search messages...") if not search_entry.get() else None)
    
    def build_conversation_list(self, parent):
        conv_frame = tk.Frame(parent, bg=self.colors.bg_medium)
        conv_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Header
        header = tk.Label(conv_frame, text="💬 CONVERSATIONS",
                          fg=self.colors.text_dim, bg=self.colors.bg_medium,
                          font=self.fonts.small_bold)
        header.pack(anchor='w', pady=(0, 5))
        
        # Listbox with scrollbar
        list_frame = tk.Frame(conv_frame, bg=self.colors.bg_medium)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.conv_listbox = tk.Listbox(list_frame,
                                       bg=self.colors.bg_light,
                                       fg=self.colors.text_light,
                                       selectbackground=self.colors.accent,
                                       font=self.fonts.normal,
                                       relief=tk.FLAT,
                                       borderwidth=0,
                                       highlightthickness=0)
        self.conv_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.config(command=self.conv_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conv_listbox.config(yscrollcommand=scrollbar.set)
        
        # Bind selection
        self.conv_listbox.bind('<<ListboxSelect>>', self.on_peer_select)
        
        # Broadcast option
        self.conv_listbox.insert(tk.END, "📢 BROADCAST (All)")
        self.conv_listbox.itemconfig(0, bg=self.colors.broadcast, fg='white')
        
        # Load conversations from database
        self.load_conversations()
    
    def build_chat_header(self, parent):
        self.chat_header = tk.Frame(parent, bg=self.colors.bg_medium, height=60)
        self.chat_header.pack(fill=tk.X, padx=0, pady=(0, 0))
        self.chat_header.pack_propagate(False)
        
        self.peer_name_label = tk.Label(self.chat_header, text="Select a conversation",
                                        fg=self.colors.text_light, bg=self.colors.bg_medium,
                                        font=self.fonts.header)
        self.peer_name_label.pack(side=tk.LEFT, padx=20, pady=15)
        
        self.peer_status_label = tk.Label(self.chat_header, text="",
                                          fg=self.colors.text_dim, bg=self.colors.bg_medium,
                                          font=self.fonts.small)
        self.peer_status_label.pack(side=tk.LEFT, padx=5, pady=15)
        
        # Action buttons
        actions_frame = tk.Frame(self.chat_header, bg=self.colors.bg_medium)
        actions_frame.pack(side=tk.RIGHT, padx=10)
        
        self.attach_btn = tk.Label(actions_frame, text="📎", fg=self.colors.text_dim,
                                   bg=self.colors.bg_medium, font=("Segoe UI", 14), cursor="hand2")
        self.attach_btn.pack(side=tk.LEFT, padx=5)
        self.attach_btn.bind("<Button-1>", self.attach_file)
        
        self.clear_btn = tk.Label(actions_frame, text="🗑️", fg=self.colors.text_dim,
                                  bg=self.colors.bg_medium, font=("Segoe UI", 14), cursor="hand2")
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        self.clear_btn.bind("<Button-1>", self.clear_chat)
        
        self.pin_btn = tk.Label(actions_frame, text="📌", fg=self.colors.text_dim,
                                bg=self.colors.bg_medium, font=("Segoe UI", 14), cursor="hand2")
        self.pin_btn.pack(side=tk.LEFT, padx=5)
        self.pin_btn.bind("<Button-1>", self.toggle_pin)
    
    def build_peer_info_panel(self, parent):
        info_header = tk.Label(parent, text="ℹ️ PEER INFO",
                               fg=self.colors.text_dim, bg=self.colors.bg_medium,
                               font=self.fonts.small_bold)
        info_header.pack(pady=10)
        
        self.peer_info_frame = tk.Frame(parent, bg=self.colors.bg_medium)
        self.peer_info_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        # Default info
        self.peer_info_label = tk.Label(self.peer_info_frame, 
                                        text="Select a peer to see info",
                                        fg=self.colors.text_dim, bg=self.colors.bg_medium,
                                        font=self.fonts.small, wraplength=200)
        self.peer_info_label.pack()
    
    def build_input_area(self, parent):
        input_frame = tk.Frame(parent, bg=self.colors.bg_medium, height=70)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=(0, 0))
        input_frame.pack_propagate(False)
        
        # Emoji button
        emoji_btn = tk.Label(input_frame, text="😊", fg=self.colors.text_dim,
                             bg=self.colors.bg_medium, font=("Segoe UI", 14), cursor="hand2")
        emoji_btn.pack(side=tk.LEFT, padx=10)
        
        # Message entry
        self.message_entry = tk.Text(input_frame, 
                                     bg=self.colors.bg_light,
                                     fg=self.colors.text_light,
                                     font=self.fonts.normal,
                                     relief=tk.FLAT,
                                     wrap=tk.WORD,
                                     height=2,
                                     insertbackground=self.colors.success)
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=10)
        self.message_entry.bind('<Return>', self.send_message)
        self.message_entry.bind('<Shift-Return>', lambda e: None)  # Allow newline
        
        # Send button
        self.send_btn = tk.Label(input_frame, text="📤 SEND",
                                 fg='white', bg=self.colors.accent,
                                 font=self.fonts.bold, padx=20, pady=10, cursor="hand2")
        self.send_btn.pack(side=tk.RIGHT, padx=10)
        self.send_btn.bind("<Button-1>", self.send_message)
    
    def create_welcome_tab(self):
        welcome_frame = tk.Frame(self.chat_notebook, bg=self.colors.bg_dark)
        self.chat_notebook.add(welcome_frame, text="Welcome")
        
        welcome_text = f"""
        
╔══════════════════════════════════════════╗
║                                          ║
║      🌐 DECENTRALIZED MESH MESSENGER     ║
║                                          ║
║         Welcome, {profile.username}!              ║
║                                          ║
║    • Select a peer to start chatting     ║
║    • Use Broadcast to message everyone   ║
║    • Share files and images securely     ║
║                                          ║
║    Your IP: {MY_IP}:{PORT}              ║
║    Status: 🔒 End-to-End Encrypted       ║
║                                          ║
╚══════════════════════════════════════════╝
        """
        
        welcome_label = tk.Label(welcome_frame, text=welcome_text,
                                 fg=self.colors.success, bg=self.colors.bg_dark,
                                 font=("Consolas", 11), justify=tk.CENTER)
        welcome_label.pack(expand=True)
    
    def create_chat_tab(self, peer_id, peer_name):
        """Create a new chat tab for a peer"""
        if peer_id in self.chat_widgets:
            return
        
        chat_frame = tk.Frame(self.chat_notebook, bg=self.colors.bg_dark)
        
        # Chat display
        chat_display = scrolledtext.ScrolledText(chat_frame,
                                                  wrap=tk.WORD,
                                                  bg=self.colors.bg_dark,
                                                  fg=self.colors.text_light,
                                                  font=self.fonts.message,
                                                  relief=tk.FLAT,
                                                  borderwidth=0)
        chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure tags
        chat_display.tag_config("timestamp", foreground=self.colors.text_dim, font=self.fonts.small)
        chat_display.tag_config("sender", foreground=self.colors.success, font=self.fonts.bold)
        chat_display.tag_config("sent", foreground=self.colors.private, justify='right')
        chat_display.tag_config("received", foreground=self.colors.text_light)
        chat_display.tag_config("status", foreground=self.colors.text_dim, font=self.fonts.small)
        chat_display.tag_config("system", foreground=self.colors.warning, font=self.fonts.small_italic)
        
        self.chat_widgets[peer_id] = chat_display
        
        self.chat_notebook.add(chat_frame, text=peer_name[:15])
        self.chat_notebook.select(chat_frame)
        
        # Load message history
        self.load_chat_history(peer_id)
    
    def load_chat_history(self, peer_id):
        """Load previous messages from database"""
        if peer_id not in self.chat_widgets:
            return
        
        chat_display = self.chat_widgets[peer_id]
        chat_display.delete(1.0, tk.END)
        
        messages = db.get_messages(peer_id)
        for msg in messages:
            self.display_message_in_chat(peer_id, msg)
    
    def display_message_in_chat(self, peer_id, msg):
        """Display a single message in the appropriate chat"""
        if peer_id not in self.chat_widgets:
            return
        
        chat_display = self.chat_widgets[peer_id]
        
        timestamp = datetime.fromtimestamp(msg['timestamp']).strftime("%H:%M")
        is_sent = msg['sender_id'] == NODE_ID
        sender = "You" if is_sent else msg['sender_id']
        
        # Status indicators
        status_icon = ""
        if is_sent:
            if msg['is_read']:
                status_icon = "✔✔"
            elif msg['is_delivered']:
                status_icon = "✔"
            else:
                status_icon = "🕓"
        
        # Insert message
        chat_display.insert(tk.END, f"\n[{timestamp}] ", "timestamp")
        chat_display.insert(tk.END, f"{sender}: ", "sender")
        
        if msg['content_type'] == 'text':
            chat_display.insert(tk.END, msg['content'], "sent" if is_sent else "received")
        elif msg['content_type'] == 'image':
            chat_display.insert(tk.END, f"🖼️ [Image: {msg['content']}]", "system")
        elif msg['content_type'] == 'file':
            chat_display.insert(tk.END, f"📎 [File: {msg['content']}]", "system")
        
        if is_sent and status_icon:
            chat_display.insert(tk.END, f" {status_icon}", "status")
        
        chat_display.see(tk.END)
    
    def send_message(self, event=None):
        """Send a message"""
        if not self.current_peer:
            messagebox.showwarning("No peer", "Please select a peer first")
            return "break"
        
        content = self.message_entry.get(1.0, tk.END).strip()
        if not content:
            return "break"
        
        is_broadcast = (self.current_peer == "BROADCAST")
        
        # Send via transport
        if is_broadcast:
            # Broadcast to all peers
            for peer in db.get_all_peers():
                self.transport.send_message(peer['peer_id'], peer['ip_address'], 
                                           content, is_broadcast=True)
        else:
            peer = db.get_peer(self.current_peer)
            if peer:
                self.transport.send_message(self.current_peer, peer['ip_address'], content)
        
        # Display sent message
        if not is_broadcast and self.current_peer in self.chat_widgets:
            msg = {
                'timestamp': datetime.now().timestamp(),
                'sender_id': NODE_ID,
                'content': content,
                'content_type': 'text',
                'is_sent': True,
                'is_delivered': False,
                'is_read': False
            }
            self.display_message_in_chat(self.current_peer, msg)
        
        # Clear input
        self.message_entry.delete(1.0, tk.END)
        
        return "break"
    
    def attach_file(self, event=None):
        """Attach and send a file"""
        if not self.current_peer or self.current_peer == "BROADCAST":
            messagebox.showinfo("Info", "File sharing only available in private chats")
            return
        
        file_path = filedialog.askopenfilename(
            title="Select file to send",
            filetypes=[("All files", "*.*"), ("Images", "*.jpg *.png *.gif")]
        )
        
        if file_path:
            peer = db.get_peer(self.current_peer)
            if peer:
                transfer_id = self.file_handler.send_file(peer['ip_address'], file_path, self.current_peer)
                
                # Show sending indicator
                if self.current_peer in self.chat_widgets:
                    chat_display = self.chat_widgets[self.current_peer]
                    chat_display.insert(tk.END, f"\n[📤 Sending file: {Path(file_path).name}]", "system")
                    chat_display.see(tk.END)
    
    def clear_chat(self, event=None):
        """Clear current chat history"""
        if not self.current_peer or self.current_peer == "BROADCAST":
            return
        
        if messagebox.askyesno("Clear Chat", "Delete this conversation?"):
            db.delete_conversation(self.current_peer)
            if self.current_peer in self.chat_widgets:
                self.chat_widgets[self.current_peer].delete(1.0, tk.END)
            self.load_conversations()
    
    def toggle_pin(self, event=None):
        """Pin/unpin current conversation"""
        if not self.current_peer or self.current_peer == "BROADCAST":
            return
        
        peer = db.get_peer(self.current_peer)
        if peer:
            new_pin = not peer.get('is_pinned', False)
            db.pin_peer(self.current_peer, new_pin)
            self.load_conversations()
    
    def change_status(self, event=None):
        """Change user status"""
        statuses = ["Available", "Busy", "Away", "Offline"]
        
        popup = tk.Menu(self.root, tearoff=0, bg=self.colors.bg_light, fg=self.colors.text_light)
        for s in statuses:
            popup.add_command(label=s, command=lambda st=s: self.set_status(st))
        
        try:
            popup.tk_popup(event.x_root, event.y_root)
        finally:
            popup.grab_release()
    
    def set_status(self, status):
        profile.set_status(status)
        status_icons = {"Available": "🟢", "Busy": "🔴", "Away": "🟡", "Offline": "⚫"}
        self.profile_status.config(text=f"{status_icons.get(status, '🟢')} {status}")
    
    def open_settings(self, event=None):
        """Open settings dialog"""
        new_username = simpledialog.askstring("Settings", "Enter new username:",
                                              initialvalue=profile.username)
        if new_username and new_username != profile.username:
            profile.set_username(new_username)
            self.root.title(f"🌐 Mesh Messenger - {profile.username}")
    
    def on_search(self, *args):
        """Search messages"""
        query = self.search_var.get()
        if len(query) < 2 or query == "🔍 Search messages...":
            return
        
        results = db.search_messages(query)
        
        # Show results popup
        popup = tk.Toplevel(self.root)
        popup.title(f"Search results for '{query}'")
        popup.geometry("500x400")
        popup.configure(bg=self.colors.bg_medium)
        
        results_text = scrolledtext.ScrolledText(popup, bg=self.colors.bg_dark, fg=self.colors.text_light)
        results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for msg in results:
            results_text.insert(tk.END, f"[{msg['peer_id']}] {msg['content']}\n")
    
    def on_peer_select(self, event):
        """Handle peer selection from list"""
        selection = self.conv_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        peer_text = self.conv_listbox.get(index)
        
        if index == 0:
            # Broadcast
            self.current_peer = "BROADCAST"
            self.peer_name_label.config(text="📢 Broadcast")
            self.peer_status_label.config(text="(All nodes)")
            self.update_peer_info_panel(None)
        else:
            # Get peer ID from list
            # Format: "🟢 username (IP)" or "📌 🟢 username (IP)"
            peer_id = peer_text.split(" (")[0].replace("📌 ", "").replace("🟢 ", "").replace("🔴 ", "")
            self.current_peer = peer_id
            
            peer = db.get_peer(peer_id)
            if peer:
                self.peer_name_label.config(text=peer.get('username', peer_id))
                status = "🟢 Online" if peer.get('last_seen', 0) > time.time() - 15 else "🔴 Offline"
                self.peer_status_label.config(text=status)
                self.update_peer_info_panel(peer)
                
                # Create/switch to chat tab
                if peer_id not in self.chat_widgets:
                    self.create_chat_tab(peer_id, peer.get('username', peer_id))
                else:
                    # Switch to existing tab
                    for i in range(self.chat_notebook.index("end")):
                        if self.chat_notebook.tab(i, "text") == peer.get('username', peer_id)[:15]:
                            self.chat_notebook.select(i)
                            break
                
                # Mark as read
                db.clear_unread(peer_id)
        
        # Enable input
        self.message_entry.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL)
    
    def update_peer_info_panel(self, peer):
        """Update right sidebar with peer info"""
        for widget in self.peer_info_frame.winfo_children():
            widget.destroy()
        
        if not peer:
            self.peer_info_label = tk.Label(self.peer_info_frame,
                                            text="Select a peer to see info",
                                            fg=self.colors.text_dim, bg=self.colors.bg_medium,
                                            font=self.fonts.small)
            self.peer_info_label.pack()
            return
        
        info_text = f"""
Username: {peer.get('username', peer['peer_id'])}
IP: {peer.get('ip_address', 'Unknown')}
Status: {peer.get('status', 'Unknown')}
Last seen: {datetime.fromtimestamp(peer.get('last_seen', 0)).strftime('%H:%M')}
        """
        
        info_label = tk.Label(self.peer_info_frame, text=info_text,
                              fg=self.colors.text_light, bg=self.colors.bg_medium,
                              font=self.fonts.small, justify=tk.LEFT)
        info_label.pack(anchor='w', pady=5)
    
    def load_conversations(self):
        """Load conversations into listbox"""
        # Clear all except broadcast
        self.conv_listbox.delete(1, tk.END)
        
        conversations = db.get_conversations()
        online_count = 0
        
        for conv in conversations:
            peer_id = conv['peer_id']
            is_online = (time.time() - conv.get('last_seen', 0)) < 15
            status_icon = "🟢" if is_online else "🔴"
            pin_icon = "📌 " if conv.get('is_pinned') else ""
            unread_badge = f" ({conv['unread_count']})" if conv['unread_count'] else ""
            
            display = f"{pin_icon}{status_icon} {conv['username']} ({conv['ip_address']}){unread_badge}"
            
            self.conv_listbox.insert(tk.END, display)
            
            if is_online:
                online_count += 1
                if conv.get('is_pinned'):
                    self.conv_listbox.itemconfig(tk.END, fg=self.colors.warning)
                else:
                    self.conv_listbox.itemconfig(tk.END, fg=self.colors.success)
            else:
                self.conv_listbox.itemconfig(tk.END, fg=self.colors.error)
        
        self.connection_label.config(text=f"📡 {online_count} online")
    
    def update_peer_status(self):
        """Periodically update peer status displays"""
        self.load_conversations()
        self.root.after(5000, self.update_peer_status)
    
    def handle_network_event(self, event_type, data):
        """Handle events from network layer"""
        self.gui_queue.put(("network", event_type, data))
    
    def handle_file_event(self, event_type, data):
        """Handle events from file handler"""
        self.gui_queue.put(("file", event_type, data))
    
    def process_queue(self):
        """Process GUI queue events"""
        try:
            while True:
                source, event_type, data = self.gui_queue.get_nowait()
                
                if source == "network":
                    if event_type == "message":
                        self.handle_incoming_message(data)
                    elif event_type == "delivered":
                        self.update_message_status(data['msg_id'], 'delivered')
                    elif event_type == "read":
                        self.update_message_status(data['msg_id'], 'read')
                
                elif source == "file":
                    if event_type == "file_received":
                        self.handle_file_received(data)
                    elif event_type == "file_progress":
                        pass  # Could show progress bar
                        
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def handle_incoming_message(self, data):
        """Process incoming message"""
        sender_id = data['from_id'] if 'from_id' in data else data['from']
        content = data['content']
        content_type = data.get('content_type', 'text')
        
        # Create peer if needed
        peer = db.get_peer(sender_id)
        if not peer:
            db.add_or_update_peer(sender_id, data.get('from_username', sender_id))
        
        db.increment_unread(sender_id)
        
        # Display in chat
        if sender_id in self.chat_widgets:
            msg = {
                'timestamp': data.get('timestamp', time.time()),
                'sender_id': sender_id,
                'content': content,
                'content_type': content_type,
                'is_sent': False
            }
            self.display_message_in_chat(sender_id, msg)
        
        # Refresh conversation list
        self.load_conversations()
    
    def update_message_status(self, msg_id, status):
        """Update message status indicator"""
        pass  # Implement if needed
    
    def handle_file_received(self, data):
        """Handle received file notification"""
        from_id = data['from_id']
        filename = data['filename']
        path = data['path']
        
        if from_id in self.chat_widgets:
            chat_display = self.chat_widgets[from_id]
            chat_display.insert(tk.END, f"\n[📥 Received: {filename}]", "system")
            chat_display.insert(tk.END, f"\n[Saved to: {path}]", "system")
            chat_display.see(tk.END)
    
    def run(self):
        self.root.mainloop()