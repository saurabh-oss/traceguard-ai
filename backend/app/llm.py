"""LLM factory — returns the right LangChain chat model based on LLM_PROVIDER env var."""
from app.config import settings


def get_llm(temperature: float = 0.2):
    provider = (settings.llm_provider or "groq").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            temperature=temperature,
            api_key=settings.openai_api_key or None,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.anthropic_model,
            temperature=temperature,
            api_key=settings.anthropic_api_key or None,
        )

    # Default: Groq
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=settings.groq_model,
        temperature=temperature,
        api_key=settings.groq_api_key or None,
    )
