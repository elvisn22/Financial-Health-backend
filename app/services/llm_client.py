from __future__ import annotations

from typing import Optional

import httpx

from app.core.config import get_settings
from app.schemas import AssessmentResult


async def enhance_narrative_with_llm(result: AssessmentResult) -> AssessmentResult:
    """
    Optionally call an LLM to refine the narrative field.

    If OPENAI_API_KEY is not configured, this function is a no-op and returns
    the original result. This keeps the project runnable without external deps.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return result

    prompt = (
        "You are a financial analyst. Rewrite the following financial health summary "
        "into a concise, business-owner-friendly paragraph. Maintain the factual content "
        "but improve clarity and add 1–2 concrete recommendations.\n\n"
        f"Existing summary:\n{result.narrative}\n\n"
        f"Key metrics: {[(m.label, m.value, m.unit) for m in result.metrics]}"
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "You are a senior SME financial advisor."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        content: Optional[str] = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")  # type: ignore[assignment]
        )
        if content:
            result.narrative = content.strip()
    except Exception:
        # Fail gracefully; keep the original narrative
        return result

    return result

