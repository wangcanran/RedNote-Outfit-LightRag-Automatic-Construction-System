import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 始终从项目根（本文件所在目录）加载 .env，避免从子目录启动时读不到
load_dotenv(Path(__file__).resolve().parent / ".env")

class Settings(BaseSettings):
    """Application configuration"""
    # LLM 提供商选择: "anthropic" 或 "openai"
    llm_provider: str = "openai"

    # Anthropic 配置
    anthropic_api_key: str = ""
    anthropic_base_url: str | None = None

    # OpenAI 配置
    openai_api_key: str = ""
    openai_base_url: str | None = None

    # 模型配置
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    openai_model: str = "gpt-4-vision"

    max_tokens: int = 4096
    temperature: float = 0.7

    # LangChain 单次请求超时（秒）；过小易误杀慢模型，过大易「假死」等网关
    llm_timeout_sec: float = 180.0

    # LightRAG：图谱抽取/合并摘要所用自然语言（写入 addon_params["language"]，如 Simplified Chinese）
    lightrag_language: str = "Simplified Chinese"

    # LightRAG 嵌入：传给 openai_embed 的单次请求超时，并作为 default_embedding_timeout
    #（LightRAG Worker 超时约为该值的 2 倍）。网关慢/429 多时可调到 180～300。
    embedding_timeout_sec: int = 180
    # 嵌入并发（过大易触发上游限流；与 EMBEDDING_FUNC_MAX_ASYNC 二选一以代码为准时可只改此项）
    embedding_func_max_async: int = 4

    # Database
    database_url: str = "sqlite:///./ecommerce.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()
