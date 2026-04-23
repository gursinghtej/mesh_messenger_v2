"""
Configuration for Decentralized Mesh Messenger
"""

import os
import json
from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
AVATAR_DIR = DATA_DIR / "avatars"
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "mesh.db"
CONFIG_PATH = DATA_DIR / "config.json"

# Create directories
for d in [DATA_DIR, AVATAR_DIR, FILES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# NETWORK CONFIG
# ============================================================================

PORT = 5007
DISCOVERY_PORT = 5008
FILE_PORT = 5009              # Separate port for file transfers
DISCOVERY_INTERVAL = 5        # Seconds
PEER_TIMEOUT = 15             # Seconds before peer considered offline
MAX_RETRIES = 3               # Message retry count
ACK_TIMEOUT = 3               # Seconds to wait for ACK

# Multicast for smarter discovery
MULTICAST_GROUP = "224.1.1.1"
USE_MULTICAST = True

# ============================================================================
# ENCRYPTION CONFIG
# ============================================================================

# Pre-shared key (in production, use key exchange)
ENCRYPTION_KEY = "meshnet2024securekey"

# ============================================================================
# USER PROFILE
# ============================================================================

class UserProfile:
    """User identity and preferences"""
    
    def __init__(self):
        self.config = self.load_config()
        self.username = self.config.get("username", self.get_default_username())
        self.status = self.config.get("status", "Available")
        self.avatar_path = self.config.get("avatar", None)
        self.theme = self.config.get("theme", "dark")
        
    def get_default_username(self):
        import platform
        import socket
        hostname = platform.node().split('.')[0]
        ip_suffix = socket.gethostbyname(socket.gethostname()).split('.')[-1]
        return f"{hostname}_{ip_suffix}"
    
    def load_config(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self):
        config = {
            "username": self.username,
            "status": self.status,
            "avatar": self.avatar_path,
            "theme": self.theme
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    
    def set_username(self, username):
        self.username = username
        self.save_config()
    
    def set_status(self, status):
        self.status = status
        self.save_config()

# Global profile
profile = UserProfile()

# ============================================================================
# NETWORK INFO
# ============================================================================

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

MY_IP = get_local_ip()
NODE_ID = profile.username