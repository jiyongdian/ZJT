"""
Skill Definitions Model - 用户级技能配置
支持每个用户自定义 AI 专家的 prompt 内容
"""
from typing import Optional, List, Dict, Any
import logging

from .database import execute_query, execute_update, execute_insert

logger = logging.getLogger(__name__)


class SkillDefinition:
    """Skill definition entity class"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.user_id = kwargs.get('user_id')
        self.skill_name = kwargs.get('skill_name')
        self.display_name = kwargs.get('display_name')
        self.description = kwargs.get('description')
        self.prompt_content = kwargs.get('prompt_content')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'skill_name': self.skill_name,
            'display_name': self.display_name,
            'description': self.description,
            'prompt_content': self.prompt_content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SkillDefinitionsModel:
    """Skill definitions database operations"""

    @staticmethod
    def get_user_skill(user_id: int, skill_name: str) -> Optional[SkillDefinition]:
        """获取用户自定义的 skill，不存在返回 None"""
        row = execute_query(
            "SELECT * FROM skill_definitions WHERE user_id = %s AND skill_name = %s",
            (user_id, skill_name),
            fetch_one=True
        )
        if row:
            return SkillDefinition(**row)
        return None

    @staticmethod
    def get_user_all_skills(user_id: int) -> List[SkillDefinition]:
        """获取用户所有自定义 skill"""
        rows = execute_query(
            "SELECT * FROM skill_definitions WHERE user_id = %s ORDER BY skill_name",
            (user_id,),
            fetch_all=True
        )
        return [SkillDefinition(**row) for row in rows] if rows else []

    @staticmethod
    def upsert_user_skill(
        user_id: int,
        skill_name: str,
        prompt_content: str,
        display_name: str = None,
        description: str = None
    ) -> int:
        """创建或更新用户自定义 skill"""
        existing = SkillDefinitionsModel.get_user_skill(user_id, skill_name)
        if existing:
            execute_update(
                """UPDATE skill_definitions
                   SET prompt_content = %s, display_name = %s, description = %s
                   WHERE user_id = %s AND skill_name = %s""",
                (prompt_content, display_name, description, user_id, skill_name)
            )
            return existing.id
        else:
            return execute_insert(
                """INSERT INTO skill_definitions
                   (user_id, skill_name, display_name, description, prompt_content)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, skill_name, display_name, description, prompt_content)
            )

    @staticmethod
    def delete_user_skill(user_id: int, skill_name: str) -> bool:
        """删除用户自定义 skill（回退到默认）"""
        affected = execute_update(
            "DELETE FROM skill_definitions WHERE user_id = %s AND skill_name = %s",
            (user_id, skill_name)
        )
        return affected > 0

    @staticmethod
    def get_custom_skill_names(user_id: int) -> set:
        """获取用户已自定义的 skill 名称集合"""
        rows = execute_query(
            "SELECT skill_name FROM skill_definitions WHERE user_id = %s",
            (user_id,),
            fetch_all=True
        )
        return {row['skill_name'] for row in rows} if rows else set()
