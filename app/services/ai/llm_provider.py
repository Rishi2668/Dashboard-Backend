"""Optional LLM provider (Gemini / OpenRouter) for coaching insights."""

from __future__ import annotations

import json
import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def generate_llm_insight(prompt: str) -> str | None:
    """Return model text or None to fall back to rule-based insights."""
    if settings.AI_PROVIDER == "rule_based":
        return None
    if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return await _gemini_generate(prompt)
    if settings.AI_PROVIDER == "openrouter" and settings.OPENROUTER_API_KEY:
        return await _openrouter_generate(prompt)
    return None


async def _gemini_generate(prompt: str) -> str | None:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash:generateContent"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts") or []
            return parts[0].get("text") if parts else None
    except Exception as exc:
        logger.warning("Gemini insight request failed: %s", exc)
        return None


async def _openrouter_generate(prompt: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.0-flash-001:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            return choices[0].get("message", {}).get("content")
    except Exception as exc:
        logger.warning("OpenRouter insight request failed: %s", exc)
        return None


def parse_insights_json(text: str) -> list[dict] | None:
    """Extract a JSON array of insight objects from model output."""
    if not text:
        return None
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "insights" in parsed:
            return parsed["insights"]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", stripped)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    return None
