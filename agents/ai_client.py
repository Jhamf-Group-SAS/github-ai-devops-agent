"""
Thin wrapper around the Anthropic SDK.
All agents go through here — one place to swap models or add rate limiting.
"""

from functools import lru_cache

import anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096


@lru_cache
def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env


async def ask(
    system: str,
    user: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Send a single prompt to Claude and return the text response."""
    client = get_client()
    message = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text
