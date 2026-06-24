"""Thin OpenAI wrapper that returns a validated LLMAnalysis via structured outputs."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from .models import LLMAnalysis

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = OpenAI()
    return _client


def analyse(system_prompt: str, user_content: list[dict], model: str | None = None) -> LLMAnalysis:
    """Run one structured-output call.

    user_content is a list of OpenAI content parts (text and/or image_url) so the same
    call handles text-only and vision cases.
    """
    client = get_client()
    completion = client.beta.chat.completions.parse(
        model=model or DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format=LLMAnalysis,
        temperature=0,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:  # refusal or empty
        raise RuntimeError("Model did not return a parsable analysis.")
    return parsed
