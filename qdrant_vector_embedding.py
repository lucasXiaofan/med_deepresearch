#!/usr/bin/env python3
"""Shared setup helpers for OpenRouter embeddings and Qdrant."""

from __future__ import annotations

import os
from typing import Sequence

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

load_dotenv()

DEFAULT_QDRANT_URL = (
    "https://c69aea96-9486-4253-889b-edd5d5cc1fd7.us-east-1-1.aws.cloud.qdrant.io:6333"
)
DEFAULT_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_qdrant_client(url: str | None = None, api_key: str | None = None) -> QdrantClient:
    """Build a Qdrant client from env vars or explicit args."""
    resolved_url = url or os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL
    resolved_api_key = api_key or os.getenv("QDRANT_API_KEY")
    return QdrantClient(url=resolved_url, api_key=resolved_api_key)


def get_openrouter_client(api_key: str | None = None) -> OpenAI:
    """Build an OpenAI-compatible client pointed at OpenRouter."""
    resolved_api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required.")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=resolved_api_key)


def embed_texts(
    texts: Sequence[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    client: OpenAI | None = None,
) -> list[list[float]]:
    """Embed a batch of texts with OpenRouter and return vectors."""
    if not texts:
        return []
    embed_client = client or get_openrouter_client()
    response = embed_client.embeddings.create(model=model, input=list(texts))
    return [item.embedding for item in response.data]
