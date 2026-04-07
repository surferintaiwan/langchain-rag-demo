from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import Settings


def build_chat_model(settings: Settings) -> Optional[ChatOpenAI]:
    if not settings.is_live_mode:
        return None

    return ChatOpenAI(
        model=settings.llm_chat_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.1,
    )


def build_embeddings(settings: Settings) -> Optional[OpenAIEmbeddings]:
    if not settings.is_live_mode:
        return None

    return OpenAIEmbeddings(
        model=settings.llm_embedding_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
