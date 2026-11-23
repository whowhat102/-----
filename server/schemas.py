"""Pydantic 请求/响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class PersonaIn(BaseModel):
    name: str = Field(min_length=1)
    identity: str = ""
    greeting: str = ""
    catchphrases: List[str] = []
    emoji_style: str = "light"          # none / light / rich
    colloquial: int = Field(default=60, ge=0, le=100)
    warmth: int = Field(default=70, ge=0, le=100)
    formality: int = Field(default=30, ge=0, le=100)
    is_default: int = 0


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: List[str] = []
    category: str = "未分组"


class KnowledgeImportIn(BaseModel):
    """批量导入：每行一条，格式 `标题 | 内容 | 标签(逗号分隔，可选)`。"""
    text: str


class ScriptIn(BaseModel):
    stage: str = Field(min_length=1)    # 开场/引导/报价/促成/收尾
    name: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    strategy: str = ""


class AudienceIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    tone_guide: str = ""


class SessionCreate(BaseModel):
    title: Optional[str] = None
    persona_id: Optional[int] = None
    scenario_id: Optional[int] = None
    audience_id: Optional[int] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    persona_id: Optional[int] = None
    scenario_id: Optional[int] = None
    audience_id: Optional[int] = None


class ChatRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1)


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int = 0                     # 1 好 / -1 差 / 0 撤销
    correction: Optional[str] = None    # 👎 时的标准答案


class SettingsIn(BaseModel):
    mode: str = "mock"                  # mock / llm
    api_base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    api_model: str = "gpt-4o-mini"
    api_temperature: float = Field(default=0.7, ge=0, le=2)
    disclose_bot: int = 0
    product_name: str = "小熙客服"
