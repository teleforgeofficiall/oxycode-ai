"""
Hermes-Style Context Engine for OXYGENT
- Token tracking
- Auto-compaction when approaching limit
- Conversation history management
- System prompt optimization
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Token limits
MAX_CONTEXT_TOKENS = 4000
COMPACTION_THRESHOLD = 0.8  # Compact at 80% capacity
SYSTEM_PROMPT_MAX_CHARS = 3000


class ContextEngine:
    """Manages conversation context with auto-compaction."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_history: List[Dict[str, str]] = []
        self.system_prompt: str = ""
        self.total_tokens: int = 0
        self.max_tokens: int = MAX_CONTEXT_TOKENS
    
    def set_system_prompt(self, prompt: str):
        """Set system prompt."""
        self.system_prompt = prompt[:SYSTEM_PROMPT_MAX_CHARS]
    
    def add_message(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(content) // 4
        self.total_tokens += estimated_tokens
        
        # Auto-compact if needed
        if self.total_tokens > self.max_tokens * COMPACTION_THRESHOLD:
            self._compact()
    
    def _compact(self):
        """Compact conversation history to fit within token limit."""
        if not self.conversation_history:
            return
        
        # Keep system prompt + last N messages
        target_tokens = int(self.max_tokens * 0.6)  # Target 60% capacity
        system_tokens = len(self.system_prompt) // 4
        
        # Calculate how many recent messages to keep
        remaining_tokens = target_tokens - system_tokens
        kept_messages = []
        current_tokens = 0
        
        # Keep from most recent (end of list)
        for msg in reversed(self.conversation_history):
            msg_tokens = len(msg["content"]) // 4
            if current_tokens + msg_tokens > remaining_tokens:
                break
            kept_messages.insert(0, msg)
            current_tokens += msg_tokens
        
        # Add summary of old messages
        old_count = len(self.conversation_history) - len(kept_messages)
        if old_count > 0:
            summary = f"[{old_count} older messages compacted]"
            kept_messages.insert(0, {
                "role": "system",
                "content": summary,
                "timestamp": datetime.now().isoformat(),
            })
        
        self.conversation_history = kept_messages
        self.total_tokens = current_tokens + system_tokens
        
        logger.info(f"Compacted {old_count} messages, {len(kept_messages)} kept")
    
    def build_messages(self) -> List[Dict[str, str]]:
        """Build messages array for AI API."""
        messages = []
        
        # System prompt
        if self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt,
            })
        
        # Conversation history
        for msg in self.conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        
        return messages
    
    def get_token_usage(self) -> Dict[str, Any]:
        """Get token usage stats."""
        return {
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "usage_percent": (self.total_tokens / self.max_tokens) * 100,
            "messages_count": len(self.conversation_history),
            "needs_compaction": self.total_tokens > self.max_tokens * COMPACTION_THRESHOLD,
        }
    
    def clear(self):
        """Clear conversation history."""
        self.conversation_history = []
        self.total_tokens = 0
    
    def export_history(self) -> List[Dict]:
        """Export conversation history."""
        return self.conversation_history.copy()
    
    def import_history(self, history: List[Dict]):
        """Import conversation history."""
        self.conversation_history = history
        self.total_tokens = sum(len(m.get("content", "")) // 4 for m in history)


class ConversationManager:
    """Manages multiple user conversations."""
    
    def __init__(self):
        self.engines: Dict[int, ContextEngine] = {}
    
    def get_engine(self, user_id: int) -> ContextEngine:
        """Get or create context engine for user."""
        if user_id not in self.engines:
            self.engines[user_id] = ContextEngine(user_id)
        return self.engines[user_id]
    
    def add_message(self, user_id: int, role: str, content: str):
        """Add message to user's conversation."""
        engine = self.get_engine(user_id)
        engine.add_message(role, content)
    
    def build_messages(self, user_id: int) -> List[Dict[str, str]]:
        """Build messages for user's AI API call."""
        engine = self.get_engine(user_id)
        return engine.build_messages()
    
    def clear(self, user_id: int):
        """Clear user's conversation."""
        engine = self.get_engine(user_id)
        engine.clear()
    
    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's conversation stats."""
        engine = self.get_engine(user_id)
        return engine.get_token_usage()


# Global instance
conversation_manager = ConversationManager()
