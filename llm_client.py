"""
LLM 客户端工厂 - 支持 Anthropic 和 OpenAI（使用 LangChain）
"""
from config import settings

def get_llm_client():
    """获取 LLM 客户端（带超时，避免网关挂起时无限等待）"""
    timeout = float(settings.llm_timeout_sec)
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=settings.temperature,
            timeout=timeout,
            max_retries=2,
        )
    else:  # anthropic
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            model=settings.anthropic_model,
            temperature=settings.temperature,
            timeout=timeout,
            max_retries=2,
        )

def get_model_name():
    """获取当前模型名称"""
    if settings.llm_provider == "openai":
        return settings.openai_model
    else:
        return settings.anthropic_model
