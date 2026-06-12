"""
Chat History Summaries Model - Database operations for chat_history_summaries table

记录上下文压缩摘要的元数据：覆盖范围、摘要级别、父摘要关系。
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from .database import execute_query, execute_update, execute_insert
import logging

logger = logging.getLogger(__name__)


class ChatHistorySummaryEntity:
    """Chat history summary database entity class"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.summary_id = kwargs.get('summary_id')
        self.session_id = kwargs.get('session_id')

        self.from_message_id = kwargs.get('from_message_id')
        self.to_message_id = kwargs.get('to_message_id')
        self.summary_message_id = kwargs.get('summary_message_id')

        self.summary_level = kwargs.get('summary_level', 1)

        # Deserialize parent_summary_ids from JSON
        psids_raw = kwargs.get('parent_summary_ids')
        if isinstance(psids_raw, str):
            try:
                self.parent_summary_ids = json.loads(psids_raw)
            except (json.JSONDecodeError, TypeError):
                self.parent_summary_ids = None
        else:
            self.parent_summary_ids = psids_raw

        self.summary_text = kwargs.get('summary_text', '')
        self.raw_message_count = kwargs.get('raw_message_count', 0)

        self.model_id = kwargs.get('model_id')
        self.vendor_id = kwargs.get('vendor_id')

        self.create_at = kwargs.get('create_at')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'summary_id': self.summary_id,
            'session_id': self.session_id,
            'from_message_id': self.from_message_id,
            'to_message_id': self.to_message_id,
            'summary_message_id': self.summary_message_id,
            'summary_level': self.summary_level,
            'parent_summary_ids': self.parent_summary_ids,
            'summary_text': self.summary_text,
            'raw_message_count': self.raw_message_count,
            'model_id': self.model_id,
            'vendor_id': self.vendor_id,
            'create_at': self.create_at.isoformat() if isinstance(self.create_at, datetime) else self.create_at,
        }


class ChatHistorySummariesModel:
    """Static methods for chat_history_summaries table operations"""

    @staticmethod
    def _row_to_entity(row: Dict[str, Any]) -> ChatHistorySummaryEntity:
        return ChatHistorySummaryEntity(**row)

    @staticmethod
    def create(
        summary_id: str,
        session_id: str,
        summary_message_id: int,
        summary_text: str,
        from_message_id: int = None,
        to_message_id: int = None,
        summary_level: int = 1,
        parent_summary_ids: List[str] = None,
        raw_message_count: int = 0,
        model_id: int = None,
        vendor_id: int = None,
    ) -> int:
        """Insert a summary record. Returns the auto-increment id."""
        parent_json = json.dumps(parent_summary_ids) if parent_summary_ids else None

        sql = """
            INSERT INTO `chat_history_summaries` (
                summary_id, session_id, from_message_id, to_message_id,
                summary_message_id, summary_level, parent_summary_ids,
                summary_text, raw_message_count, model_id, vendor_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        return execute_insert(sql, (
            summary_id, session_id, from_message_id, to_message_id,
            summary_message_id, summary_level, parent_json,
            summary_text, raw_message_count, model_id, vendor_id,
        ))

    @staticmethod
    def get_by_summary_id(summary_id: str) -> Optional[ChatHistorySummaryEntity]:
        row = execute_query(
            "SELECT * FROM `chat_history_summaries` WHERE summary_id = %s",
            (summary_id,),
            fetch_one=True
        )
        return ChatHistorySummariesModel._row_to_entity(row) if row else None

    @staticmethod
    def list_for_session(session_id: str) -> List[ChatHistorySummaryEntity]:
        rows = execute_query(
            "SELECT * FROM `chat_history_summaries` WHERE session_id = %s ORDER BY id ASC",
            (session_id,),
            fetch_all=True
        )
        return [ChatHistorySummariesModel._row_to_entity(r) for r in (rows or [])]
