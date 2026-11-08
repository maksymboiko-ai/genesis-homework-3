"""Prompt for turning one winning script into N modification variants."""

import json

from .facts import DEFAULT_FACTS
from .schema import HOOK_TYPES, LIMITS

SYSTEM = """\
You are a senior direct-response copywriter for Meta video ads (Reels/Stories, US audience).
Your job: produce MODIFICATIONS of a proven winning ad. A modification keeps the body of the winning
script unchanged and replaces only the first 3 seconds: the spoken hook, the on-screen text, and a bridge
line that flows naturally into the original body. Designers will produce each variant as-is, so every
field must be ready to use without editing.

Rules:
- Keep the winning angle. Change the entry point, not the promise.
- Every variant must feel clearly different: different hook type, different first words, different image.
- Spoken hook: max {hook_words} words, conversational, no hashtags, no emojis.
- On-screen text: max {screen_chars} characters, readable in 1 second with the sound off.
- Bridge line: max {bridge_words} words; the next line of the original body must still make sense after it.
- Visual note: max {visual_words} words, concrete and filmable (what is on screen in seconds 0-3).
- Use ONLY the product facts given. Never invent numbers, percentages, discounts, guarantees, reviews
  counts, awards or press. First-person customer voice is fine; fake statistics are not.
- Write in English.

Hook types you may use (spread them across variants):
{hook_types}

Return ONLY a JSON object, no markdown, exactly in this shape:
{schema}
"""

SCHEMA_EXAMPLE = {
    "winning_angle": "one sentence on why the original works",
    "variants": [
        {
            "hook_type": "one of the hook type keys",
            "hook_vo": "spoken first line",
            "on_screen_text": "overlay text",
            "bridge_line": "line that leads into the original body",
            "visual_note": "what is shown in seconds 0-3",
            "rationale": "why this could beat the original",
        }
    ],
}


def build_messages(script: str, n_variants: int, hook_types: list[str] | None = None,
                   notes: str | None = None, facts: str | None = None) -> list[dict]:
    allowed = [t for t in (hook_types or HOOK_TYPES) if t in HOOK_TYPES] or list(HOOK_TYPES)
    types_txt = "\n".join(f"- {t}: {HOOK_TYPES[t]}" for t in allowed)
    system = SYSTEM.format(
        hook_words=LIMITS["hook_vo_words"],
        screen_chars=LIMITS["on_screen_chars"],
        bridge_words=LIMITS["bridge_words"],
        visual_words=LIMITS["visual_words"],
        hook_types=types_txt,
        schema=json.dumps(SCHEMA_EXAMPLE, indent=2),
    )
    user = (
        f"PRODUCT FACTS:\n{facts or DEFAULT_FACTS}\n"
        f"WINNING SCRIPT:\n\"\"\"\n{script.strip()}\n\"\"\"\n\n"
        f"Write exactly {n_variants} variants."
    )
    if notes:
        user += f"\nExtra direction from the team: {notes.strip()}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
