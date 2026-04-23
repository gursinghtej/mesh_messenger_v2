"""
SQLite database for persistent chat storage
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH

class MessageDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Peers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS peers (
                peer_id TEXT PRIMARY KEY,
                username TEXT,
                ip_address TEXT,
                last_seen REAL,
                avatar_path TEXT,
                status TEXT,
                is_pinned INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                peer_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                content TEXT,
                content_type TEXT DEFAULT 'text',
                timestamp REAL,
                is_sent INTEGER DEFAULT 0,
                is_delivered INTEGER DEFAULT 0,
                is_read INTEGER DEFAULT 0,
                file_path TEXT,
                FOREIGN KEY (peer_id) REFERENCES peers(peer_id)
            )
        ''')
        
        # Conversations (separate chat windows)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                peer_id TEXT PRIMARY KEY,
                last_message TEXT,
                last_timestamp REAL,
                FOREIGN KEY (peer_id) REFERENCES peers(peer_id)
            )
        ''')
        
        self.conn.commit()
    
    # ========================================================================
    # PEER OPERATIONS
    # ========================================================================
    
    def add_or_update_peer(self, peer_id, username=None, ip=None, status=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO peers (peer_id, username, ip_address, last_seen, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (peer_id, username or peer_id, ip, datetime.now().timestamp(), status))
        
        # Create conversation if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO conversations (peer_id, last_timestamp)
            VALUES (?, ?)
        ''', (peer_id, datetime.now().timestamp()))
        
        self.conn.commit()
    
    def update_peer_last_seen(self, peer_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE peers SET last_seen = ? WHERE peer_id = ?',
                      (datetime.now().timestamp(), peer_id))
        self.conn.commit()
    
    def get_peer(self, peer_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM peers WHERE peer_id = ?', (peer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_peers(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM peers ORDER BY is_pinned DESC, last_seen DESC')
        return [dict(row) for row in cursor.fetchall()]
    
    def pin_peer(self, peer_id, pinned=True):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE peers SET is_pinned = ? WHERE peer_id = ?',
                      (1 if pinned else 0, peer_id))
        self.conn.commit()
    
    def increment_unread(self, peer_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE peers SET unread_count = unread_count + 1 WHERE peer_id = ?',
                      (peer_id,))
        self.conn.commit()
    
    def clear_unread(self, peer_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE peers SET unread_count = 0 WHERE peer_id = ?',
                      (peer_id,))
        self.conn.commit()
    
    def get_unread_counts(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT peer_id, unread_count FROM peers WHERE unread_count > 0')
        return {row['peer_id']: row['unread_count'] for row in cursor.fetchall()}
    
    # ========================================================================
    # MESSAGE OPERATIONS
    # ========================================================================
    
    def save_message(self, msg_id, peer_id, sender_id, content, 
                     content_type='text', file_path=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO messages 
            (msg_id, peer_id, sender_id, content, content_type, timestamp, is_sent, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, peer_id, sender_id, content, content_type, 
              datetime.now().timestamp(), 1, file_path))
        
        # Update conversation
        cursor.execute('''
            UPDATE conversations 
            SET last_message = ?, last_timestamp = ?
            WHERE peer_id = ?
        ''', (content[:100], datetime.now().timestamp(), peer_id))
        
        self.conn.commit()
    
    def update_message_status(self, msg_id, is_delivered=False, is_read=False):
        cursor = self.conn.cursor()
        if is_read:
            cursor.execute('UPDATE messages SET is_read = 1 WHERE msg_id = ?', (msg_id,))
        if is_delivered:
            cursor.execute('UPDATE messages SET is_delivered = 1 WHERE msg_id = ?', (msg_id,))
        self.conn.commit()
    
    def get_messages(self, peer_id, limit=100):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM messages 
            WHERE peer_id = ? 
            ORDER BY timestamp ASC 
            LIMIT ?
        ''', (peer_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    
    def search_messages(self, query, peer_id=None):
        cursor = self.conn.cursor()
        if peer_id:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE peer_id = ? AND content LIKE ? 
                ORDER BY timestamp DESC
            ''', (peer_id, f'%{query}%'))
        else:
            cursor.execute('''
                SELECT * FROM messages 
                WHERE content LIKE ? 
                ORDER BY timestamp DESC
            ''', (f'%{query}%',))
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_conversation(self, peer_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM messages WHERE peer_id = ?', (peer_id,))
        cursor.execute('DELETE FROM conversations WHERE peer_id = ?', (peer_id,))
        cursor.execute('UPDATE peers SET unread_count = 0 WHERE peer_id = ?', (peer_id,))
        self.conn.commit()
    
    def get_conversations(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT c.*, p.username, p.ip_address, p.status, p.unread_count, p.is_pinned
            FROM conversations c
            JOIN peers p ON c.peer_id = p.peer_id
            ORDER BY p.is_pinned DESC, c.last_timestamp DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

# Global database instance
db = MessageDatabase()