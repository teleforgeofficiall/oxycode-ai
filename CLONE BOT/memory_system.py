"""
Hermes-Style Memory System for OXYGENT
- MEMORY.md: Agent's personal notes (environment, conventions, quirks)
- USER.md: User profile (preferences, style, workflow)
- Per-user sandboxed storage
- Character-based limits (not tokens)
- Frozen snapshot pattern
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Memory directory
MEMORY_DIR = Path(__file__).parent / "user_memories"
MEMORY_DIR.mkdir(exist_ok=True)

# Entry delimiter (Hermes style)
ENTRY_DELIMITER = "\n§\n"

# Character limits per user
MEMORY_MAX_CHARS = 4000
USER_MAX_CHARS = 2000

# Block headers for system prompt
MEMORY_BLOCK_HEADERS = {
    "memory": "MEMORY (your personal notes)",
    "user": "USER PROFILE (who the user is)",
}


class HermesMemory:
    """Hermes-style memory system with per-user sandboxing."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.user_dir = MEMORY_DIR / str(user_id)
        self.user_dir.mkdir(exist_ok=True)
        self.memory_file = self.user_dir / "MEMORY.md"
        self.user_file = self.user_dir / "USER.md"
        
        # Initialize files if not exist
        if not self.memory_file.exists():
            self.memory_file.write_text("")
        if not self.user_file.exists():
            self.user_file.write_text("")
    
    def _read_file(self, filepath: Path) -> str:
        """Read file content."""
        try:
            return filepath.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return ""
    
    def _write_file(self, filepath: Path, content: str):
        """Write file content."""
        try:
            filepath.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Error writing {filepath}: {e}")
    
    def _truncate_to_limit(self, content: str, limit: int) -> str:
        """Truncate content to character limit, keeping most recent entries."""
        if len(content) <= limit:
            return content
        
        # Split by delimiter and keep most recent entries
        entries = content.split(ENTRY_DELIMITER)
        truncated = []
        total_chars = 0
        
        # Keep from most recent (end of list)
        for entry in reversed(entries):
            entry_chars = len(entry) + len(ENTRY_DELIMITER)
            if total_chars + entry_chars > limit - 100:  # Leave buffer
                break
            truncated.insert(0, entry)
            total_chars += entry_chars
        
        return ENTRY_DELIMITER.join(truncated)
    
    # === MEMORY (Agent's notes) ===
    
    def get_memory(self) -> str:
        """Get agent's personal notes."""
        return self._read_file(self.memory_file)
    
    def add_memory(self, content: str, category: str = "general") -> bool:
        """Add entry to agent's memory."""
        content = content.strip()
        if not content:
            return False
        
        # Format entry with metadata
        entry = f"[{category}] {content}"
        
        # Read existing
        existing = self.get_memory()
        
        # Add new entry
        if existing:
            new_content = existing + ENTRY_DELIMITER + entry
        else:
            new_content = entry
        
        # Truncate if needed
        new_content = self._truncate_to_limit(new_content, MEMORY_MAX_CHARS)
        
        # Write
        self._write_file(self.memory_file, new_content)
        return True
    
    def search_memory(self, query: str) -> List[str]:
        """Search memory for matching entries."""
        content = self.get_memory()
        if not content:
            return []
        
        entries = content.split(ENTRY_DELIMITER)
        query_lower = query.lower()
        
        return [e for e in entries if query_lower in e.lower()]
    
    # === USER PROFILE ===
    
    def get_user_profile(self) -> str:
        """Get user profile."""
        return self._read_file(self.user_file)
    
    def add_user_info(self, key: str, value: str) -> bool:
        """Add/update user info."""
        key = key.strip().lower()
        value = value.strip()
        
        if not key or not value:
            return False
        
        # Read existing
        profile = self.get_user_profile()
        entries = {}
        
        # Parse existing entries
        if profile:
            for entry in profile.split(ENTRY_DELIMITER):
                if ":" in entry:
                    k, v = entry.split(":", 1)
                    entries[k.strip().lower()] = v.strip()
        
        # Add/update entry
        entries[key] = value
        
        # Build new content
        new_content = ENTRY_DELIMITER.join([f"{k}: {v}" for k, v in entries.items()])
        
        # Truncate if needed
        new_content = self._truncate_to_limit(new_content, USER_MAX_CHARS)
        
        # Write
        self._write_file(self.user_file, new_content)
        return True
    
    def get_user_info(self, key: str) -> Optional[str]:
        """Get specific user info."""
        profile = self.get_user_profile()
        if not profile:
            return None
        
        key = key.strip().lower()
        for entry in profile.split(ENTRY_DELIMITER):
            if ":" in entry:
                k, v = entry.split(":", 1)
                if k.strip().lower() == key:
                    return v.strip()
        
        return None
    
    def get_all_user_info(self) -> Dict[str, str]:
        """Get all user info as dict."""
        profile = self.get_user_profile()
        if not profile:
            return {}
        
        entries = {}
        for entry in profile.split(ENTRY_DELIMITER):
            if ":" in entry:
                k, v = entry.split(":", 1)
                entries[k.strip().lower()] = v.strip()
        
        return entries
    
    # === SYSTEM PROMPT CONTEXT ===
    
    def build_system_context(self) -> str:
        """Build memory context for system prompt."""
        parts = []
        
        # Memory block
        memory = self.get_memory()
        if memory:
            parts.append(f"## {MEMORY_BLOCK_HEADERS['memory']}\n{memory}")
        
        # User profile block
        user_profile = self.get_user_profile()
        if user_profile:
            parts.append(f"## {MEMORY_BLOCK_HEADERS['user']}\n{user_profile}")
        
        return "\n\n".join(parts)
    
    # === AUTO-DETECT PERSONAL INFO ===
    
    def auto_detect_and_save(self, message: str) -> List[str]:
        """Auto-detect personal info from message and save."""
        import re
        
        saved = []
        message_lower = message.lower()
        
        # Question patterns (don't save questions)
        question_patterns = [
            r'kya hai', r'kya hoon', r'what is', r'what are',
            r'kaun hoon', r'kaun hai', r'who am i', r'who are you',
            r'mujhe kya yaad', r'what do you know', r'yaad hai',
        ]
        
        is_question = any(re.search(p, message_lower) for p in question_patterns)
        if is_question:
            return saved
        
        # Patterns to detect and save
        patterns = [
            # Name
            (r'(?:mera|my)\s+(?:naam|name)\s+(\w+)', 'name'),
            (r'(?:call me|i am called)\s+(\w+)', 'name'),
            (r'(?:my name is)\s+(\w+)', 'name'),
            
            # Favourite
            (r'(?:mujhe|mein)\s+(.+?)\s+pasand', 'favourite'),
            (r'(?:i like|i love|i prefer)\s+(.+?)(?:\.|$)', 'favourite'),
            (r'(?:my favourite|favourite)\s+(\w+)\s+(?:hai|is)?\s*(.+?)(?:\.|$)', 'favourite'),
            
            # Age
            (r'(?:meri|my)\s+(?:age|umar)\s+(\d+)', 'age'),
            (r'(?:i am|i\'m)\s+(\d+)\s+years?\s+old', 'age'),
            
            # City
            (r'(?:main|mai)\s+(\w+)\s+(?:se hoon|se hun|from)', 'city'),
            (r'(?:i live in|i\'m from)\s+(\w+)', 'city'),
            
            # Occupation
            (r'(?:main|mai)\s+(?:ek\s+)?(\w+)\s+(?:hoon|hu|am)', 'occupation'),
            (r'(?:i am a|i\'m a|i work as)\s+(.+?)(?:\.|$)', 'occupation'),
            
            # Hobby
            (r'(?:mera|my)\s+(?:hobby|interest)\s+(?:hai|is)?\s*(.+?)(?:\.|$)', 'hobby'),
            (r'(?:i like doing|i enjoy)\s+(.+?)(?:\.|$)', 'hobby'),
        ]
        
        for pattern, key in patterns:
            match = re.search(pattern, message_lower)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                value = re.sub(r'\s+(hai|is|hoon|hu|am|se).*$', '', value).strip()
                
                if value and len(value) > 1 and len(value) < 50:
                    if self.add_user_info(key, value):
                        saved.append(f"{key}: {value}")
        
        return saved
    
    # === CONVERSATION HISTORY ===
    
    def save_conversation_turn(self, user_msg: str, assistant_msg: str):
        """Save a conversation turn to memory."""
        # Extract interesting facts from the conversation
        import re
        
        # Look for user sharing info
        info_patterns = [
            (r'(?:mera|my)\s+(?:naam|name)\s+(\w+)', 'name'),
            (r'(?:mujhe|mein)\s+(.+?)\s+pasand', 'favourite'),
            (r'(?:i like|i love)\s+(.+?)(?:\.|$)', 'favourite'),
        ]
        
        for pattern, key in info_patterns:
            match = re.search(pattern, user_msg.lower())
            if match:
                value = match.group(1).strip()
                if value and len(value) > 1:
                    self.add_user_info(key, value)
    
    # === EXPORT/IMPORT ===
    
    def export_data(self) -> Dict[str, str]:
        """Export all memory data."""
        return {
            "memory": self.get_memory(),
            "user_profile": self.get_user_profile(),
            "user_id": self.user_id,
        }
    
    def import_data(self, data: Dict[str, str]):
        """Import memory data."""
        if "memory" in data:
            self._write_file(self.memory_file, data["memory"])
        if "user_profile" in data:
            self._write_file(self.user_file, data["user_profile"])


# === DATABASE-BACKED PERSISTENCE ===

class MemoryDatabase:
    """SQLite-backed memory persistence."""
    
    def __init__(self, db_path: str = "oxygent_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def store(self, user_id: int, key: str, value: str, category: str = "general"):
        """Store memory entry."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO memories (user_id, key, value, category)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, key, value, category))
        conn.commit()
        conn.close()
    
    def retrieve(self, user_id: int, key: str = None) -> List[Dict]:
        """Retrieve memory entries."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        if key:
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id = ? AND key = ?",
                (user_id, key)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE user_id = ?",
                (user_id,)
            ).fetchall()
        
        conn.close()
        return [dict(r) for r in rows]
    
    def save_conversation(self, user_id: int, role: str, content: str):
        """Save conversation turn."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        conn.commit()
        conn.close()
    
    def get_conversation_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation history."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        
        conn.close()
        return [dict(r) for r in reversed(rows)]


# === UNIFIED MEMORY SYSTEM ===

class OxygentMemory:
    """Unified memory system combining file-based and database persistence."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.hermes_memory = HermesMemory(user_id)
        self.db = MemoryDatabase()
    
    def store(self, key: str, value: str, category: str = "general"):
        """Store memory entry (both file and DB)."""
        self.db.store(self.user_id, key, value, category)
        self.hermes_memory.add_user_info(key, value)
    
    def retrieve(self, key: str = None) -> Any:
        """Retrieve memory entry."""
        if key:
            entries = self.db.retrieve(self.user_id, key)
            return entries[0] if entries else None
        else:
            return self.db.retrieve(self.user_id)
    
    def get_user_info(self, key: str) -> Optional[str]:
        """Get specific user info."""
        # Try file first
        value = self.hermes_memory.get_user_info(key)
        if value:
            return value
        
        # Try DB
        entry = self.retrieve(key)
        return entry.get("value") if entry else None
    
    def add_user_info(self, key: str, value: str):
        """Add user info."""
        self.store(key, value, "personal")
    
    def get_all_user_info(self) -> Dict[str, str]:
        """Get all user info."""
        return self.hermes_memory.get_all_user_info()
    
    def build_system_context(self) -> str:
        """Build memory context for system prompt."""
        return self.hermes_memory.build_system_context()
    
    def auto_detect_and_save(self, message: str) -> List[str]:
        """Auto-detect personal info from message."""
        saved = self.hermes_memory.auto_detect_and_save(message)
        
        # Also save to DB
        for item in saved:
            if ":" in item:
                key, value = item.split(":", 1)
                self.db.store(self.user_id, key.strip(), value.strip(), "personal")
        
        return saved
    
    def search_memory(self, query: str) -> List[str]:
        """Search memory."""
        return self.hermes_memory.search_memory(query)
    
    def save_conversation(self, role: str, content: str):
        """Save conversation turn."""
        self.db.save_conversation(self.user_id, role, content)
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        """Get conversation history."""
        return self.db.get_conversation_history(self.user_id, limit)
    
    def export_data(self) -> Dict:
        """Export all data."""
        return {
            "hermes": self.hermes_memory.export_data(),
            "db": self.db.retrieve(self.user_id),
        }
    
    def import_data(self, data: Dict):
        """Import data."""
        if "hermes" in data:
            self.hermes_memory.import_data(data["hermes"])
        if "db" in data:
            for entry in data["db"]:
                self.db.store(self.user_id, entry["key"], entry["value"], entry.get("category", "general"))


# Global instances
_memory_instances: Dict[int, OxygentMemory] = {}

def get_memory(user_id: int) -> OxygentMemory:
    """Get or create memory instance for user."""
    if user_id not in _memory_instances:
        _memory_instances[user_id] = OxygentMemory(user_id)
    return _memory_instances[user_id]
