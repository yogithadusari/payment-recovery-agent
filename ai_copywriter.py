"""
Optional layer: rewrites the agent's template message into something more
natural and persuasive using Claude, while keeping the same facts (amount,
link, discount). This is genuinely optional — if ANTHROPIC_API_KEY isn't
set, agent.py never imports this successfully and just uses the plain
template, so the demo always works.

Requires: pip install anthropic
"""

import anthropic

from config import Config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = (
    "You rewrite short payment-reminder WhatsApp messages for an Indian small "
    "business. Keep every fact exactly the same (amount, discount, link, item). "
    "Keep it under 3 sentences, friendly but not pushy, no emojis, no markdown. "
    "Output ONLY the rewritten message, nothing else."
)


def craft_message(action_kind: str, order: dict, fallback_message: str) -> str:
    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Situation: {action_kind}. Original draft to rewrite:\n\n"
                f"{fallback_message}"
            ),
        }],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or fallback_message
