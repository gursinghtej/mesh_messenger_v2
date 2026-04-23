"""
UI Styling and theming
"""

class Colors:
    def __init__(self):
        self.bg_dark = '#1a1a2e'
        self.bg_medium = '#16213e'
        self.bg_light = '#0f3460'
        self.accent = '#e94560'
        self.text_light = '#ffffff'
        self.text_dim = '#a0a0a0'
        self.success = '#00ff88'
        self.warning = '#ffaa00'
        self.error = '#ff3366'
        self.broadcast = '#ff6b6b'
        self.private = '#4ecdc4'
        self.system = '#95a5a6'

class Fonts:
    def __init__(self):
        self.normal = ("Segoe UI", 10)
        self.bold = ("Segoe UI", 10, "bold")
        self.small = ("Segoe UI", 9)
        self.small_bold = ("Segoe UI", 9, "bold")
        self.small_italic = ("Segoe UI", 9, "italic")
        self.header = ("Segoe UI", 12, "bold")
        self.message = ("Consolas", 10)

def setup_styles():
    """Setup ttk styles"""
    import tkinter as tk
    from tkinter import ttk
    
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure notebook style
    style.configure('TNotebook', background='#16213e', borderwidth=0)
    style.configure('TNotebook.Tab', background='#0f3460', foreground='white', padding=[15, 5])
    style.map('TNotebook.Tab', background=[('selected', '#e94560')])