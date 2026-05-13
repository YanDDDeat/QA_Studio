"""SQLAlchemy ORM models for QA Studio"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey,
    Enum, JSON, Boolean, DefaultClause,
)
from sqlalchemy.orm import relationship

from app.database import Base


class StageEnum(str, PyEnum):
    """Pipeline stage enumeration"""
    QUESTION_GENERATE = "question_generate"
    KNOWLEDGE_GENERATE = "knowledge_generate"
    QUESTION_VALIDATE = "question_validate"
    ANSWER_GENERATE = "answer_generate"
    ANSWER_VALIDATE = "answer_validate"
    DATA_EVALUATE = "data_evaluate"
    COT_FILTER = "cot_filter"
    DATASET_SPLIT = "dataset_split"
    DATASET_ASSESSMENT = "dataset_assessment"


# SQLAlchemy 2.0 解析混合 Enum 类时 dict keys 用的是 member 名称而非值
# 通过 values_callable 让 SA 正确获取枚举的字符串值
def _stage_enum_type(**kw):
    return Enum(StageEnum, values_callable=lambda x: [m.value for m in x], **kw)


class TaskStatusEnum(str, PyEnum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceTypeEnum(str, PyEnum):
    """Source type enumeration"""
    BOOK = "图书"
    PATENT = "专利"
    PAPER = "文献"
    OTHER = "其他"


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL=全局共享
    name = Column(String(128), nullable=False)
    base_url = Column(String(512), nullable=False)
    api_key = Column(String(512), nullable=False)  # 明文存储(开发环境)
    proxy = Column(String(512), nullable=True, default=None)  # 可选代理，如 http://host:port
    models = Column(JSON, nullable=False)  # 模型名列表，如["qwen3-max","qwen3-turbo"]
    default_model = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="llm_configs")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    datasets = relationship("Dataset", back_populates="user")
    files = relationship("File", back_populates="user")
    prompts = relationship("Prompt", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    llm_configs = relationship("LLMConfig", back_populates="user")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    domain = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)  # 枚举: 知识问答, 逻辑生成
    task_type = Column(String(64), nullable=True)
    input = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    cot = Column(Text, nullable=True)
    corpus_cate = Column(Integer, default=1, nullable=False)
    scene = Column(Text, nullable=True)
    Assessment = Column(String(256), default="", nullable=False)
    source = Column(String(128), nullable=True)
    source_id = Column(String(128), nullable=True)
    source_type = Column(String(32), default="图书", nullable=True)
    originContent = Column(Text, nullable=True)
    knowledge = Column(Text, nullable=True)
    step_count = Column(String(32), nullable=True)
    extra_fields = Column(JSON, nullable=True)
    difficulty = Column(String(32), nullable=True)
    relevance = Column(Integer, nullable=True)
    clarity = Column(Integer, nullable=True)
    reasoning = Column(Integer, nullable=True)
    terminology = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    passed = Column(String(16), default="是", nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True, index=True)
    current_stage = Column(_stage_enum_type(), default=StageEnum.QUESTION_GENERATE, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="datasets")
    file = relationship("File", back_populates="datasets")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    file_type = Column(String(64), nullable=True)
    file_path = Column(String(512), nullable=False)
    source_stage = Column(_stage_enum_type(), nullable=True)
    text_field = Column(String(128), default="text", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="files")
    datasets = relationship("Dataset", back_populates="file")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL=全局共享
    stage = Column(_stage_enum_type(), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String(128), nullable=True)
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True, index=True)
    is_default = Column(Boolean, default=False, nullable=False)
    reference_fields = Column(JSON, nullable=True)  # 附加参考字段列表，如 ["input","output","domain"]
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="prompts")
    llm_config = relationship("LLMConfig")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stage = Column(_stage_enum_type(), nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    model = Column(String(128), nullable=True)
    prompt_id = Column(Integer, ForeignKey("prompts.id"), nullable=True)
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.PENDING, nullable=False)
    progress_current = Column(Integer, default=0, nullable=True)
    progress_total = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tasks")
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    log_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="logs")