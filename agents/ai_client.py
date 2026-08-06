"""
Thin wrapper around the MiniMax AI SDK (OpenAI-compatible endpoint).
All agents go through here — one place to swap models or add rate limiting.
"""

import os
from functools import lru_cache

from openai import AsyncOpenAI

MINIMAX_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_MODEL = "MiniMax-M3"
MAX_TOKENS = 4096


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url=MINIMAX_BASE_URL,
    )


async def ask(
    system: str,
    user: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Send a single prompt to MiniMax and return the text response."""
    client = get_client()
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content
