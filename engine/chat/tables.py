"""Canonical DDE Chat table exports.

Physical table names remain `frontend_*` for migration compatibility. New Chat
code imports them through this module so storage naming does not imply that
Frontend Studio owns the universal conversation domain.
"""

from engine.studio.tables import (
    frontend_chat_activities,
    frontend_chat_attachments,
    frontend_chat_change_reviews,
    frontend_chat_checkpoints,
    frontend_chat_plans,
    frontend_conversation_turns,
    frontend_conversations,
)

__all__ = [
    "frontend_chat_activities",
    "frontend_chat_attachments",
    "frontend_chat_change_reviews",
    "frontend_chat_checkpoints",
    "frontend_chat_plans",
    "frontend_conversation_turns",
    "frontend_conversations",
]
