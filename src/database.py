import aiosqlite
import asyncio
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        
    async def initialize(self):
        """Initialize database and create tables"""
        self.conn = await aiosqlite.connect(self.db_path)
        
        # Create tables
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                moderator_id INTEGER,
                channel_id INTEGER
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mute_end DATETIME NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                permanent BOOLEAN DEFAULT TRUE
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS link_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                threat_level TEXT,
                action_taken TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.conn.commit()
        logger.info("Database initialized")
        
    async def add_warning(self, guild_id: int, user_id: int, reason: str, channel_id: int = None) -> int:
        """Add a warning for a user"""
        await self.conn.execute(
            '''INSERT INTO warnings (guild_id, user_id, reason, channel_id) 
               VALUES (?, ?, ?, ?)''',
            (guild_id, user_id, reason, channel_id)
        )
        await self.conn.commit()
        
        # Get warning count
        cursor = await self.conn.execute(
            'SELECT COUNT(*) FROM warnings WHERE guild_id = ? AND user_id = ?',
            (guild_id, user_id)
        )
        count = await cursor.fetchone()
        return count[0]
        
    async def get_warnings(self, guild_id: int, user_id: int) -> list:
        """Get all warnings for a user"""
        cursor = await self.conn.execute(
            '''SELECT * FROM warnings 
               WHERE guild_id = ? AND user_id = ? 
               ORDER BY timestamp DESC''',
            (guild_id, user_id)
        )
        warnings = await cursor.fetchall()
        
        return [
            {
                'id': w[0],
                'reason': w[3],
                'timestamp': w[4],
                'channel_id': w[6]
            }
            for w in warnings
        ]
        
    async def add_mute(self, guild_id: int, user_id: int, mute_end: datetime, reason: str):
        """Add a mute record"""
        await self.conn.execute(
            '''INSERT INTO mutes (guild_id, user_id, mute_end, reason) 
               VALUES (?, ?, ?, ?)''',
            (guild_id, user_id, mute_end, reason)
        )
        await self.conn.commit()
        
    async def get_active_mutes(self, guild_id: int):
        """Get all active mutes for a guild"""
        cursor = await self.conn.execute(
            '''SELECT * FROM mutes 
               WHERE guild_id = ? AND mute_end > datetime('now')''',
            (guild_id,)
        )
        return await cursor.fetchall()
        
    async def remove_mute(self, guild_id: int, user_id: int):
        """Remove a mute record"""
        await self.conn.execute(
            'DELETE FROM mutes WHERE guild_id = ? AND user_id = ?',
            (guild_id, user_id)
        )
        await self.conn.commit()
        
    async def log_link(
        self, 
        guild_id: int, 
        user_id: int, 
        url: str, 
        threat_level: str, 
        action: str
    ):
        """Log a processed link"""
        await self.conn.execute(
            '''INSERT INTO link_history 
               (guild_id, user_id, url, threat_level, action_taken) 
               VALUES (?, ?, ?, ?, ?)''',
            (guild_id, user_id, url, threat_level, action)
        )
        await self.conn.commit()
