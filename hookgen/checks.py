"""Deterministic quality checks on a generation. Used by the eval and shown in the UI as warnings."""

import re
from difflib import SequenceMatcher
from itertools import combinations

from .facts import ALLOWED_DOLLAR_AMOUNTS, BANNED_PHRASES
from .schema import HOOK_TYPES, LIMITS, Generation

SIMILARITY_MAX = 0.70  # two hooks more similar than this count as near-duplicates

_MONEY_OR_PCT = re.compile(r"\$\d[\d,.]*|\d[\d,.]*\s?%")
# Invented social proof: "10,000 customers", "50k+ families", "1 million socks sold"
_PROOF_COUNT = re.compile(
    r"\d[\d,.]*\s*(?:k|m|million|thousand)?\+?\s+(?:happy\s+)?"
    r"(?:customers|people|families|reviews|users|subscribers|orders|households|parents|buyers|sold)",
    re.IGNORECASE,
)


def _words(s: str) -> int:
    return len(s.split())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def unverified_claims(text: str) -> list[str]:
    """Dollar amounts, percentages, social-proof counts or banned phrases not backed by the product facts.

    Plain anecdotal numbers ("I've lost 47 single socks") are allowed: they are persona voice, not a claim.
    """
    found = []
    low = text.lower()
    for p in BANNED_PHRASES:
        if p in low:
            found.append(p)
    for tok in _MONEY_OR_PCT.findall(text):
        tok = tok.rstrip(".,").replace(" ", "")
        if tok not in ALLOWED_DOLLAR_AMOUNTS:
            found.append(tok)
    found += [m.group(0) for m in _PROOF_COUNT.finditer(text)]
    return found


def variant_issues(v) -> list[str]:
    issues = []
    if v.hook_type not in HOOK_TYPES:
        issues.append(f"unknown hook type '{v.hook_type}'")
    if _words(v.hook_vo) > LIMITS["hook_vo_words"]:
        issues.append(f"hook is {_words(v.hook_vo)} words (max {LIMITS['hook_vo_words']})")
    if len(v.on_screen_text) > LIMITS["on_screen_chars"]:
        issues.append(f"on-screen text is {len(v.on_screen_text)} chars (max {LIMITS['on_screen_chars']})")
    if _words(v.bridge_line) > LIMITS["bridge_words"]:
        issues.append(f"bridge is {_words(v.bridge_line)} words (max {LIMITS['bridge_words']})")
    if _words(v.visual_note) > LIMITS["visual_words"]:
        issues.append(f"visual note is {_words(v.visual_note)} words (max {LIMITS['visual_words']})")
    for f in ("hook_vo", "on_screen_text", "bridge_line"):
        if not getattr(v, f).strip():
            issues.append(f"empty {f}")
    claims = unverified_claims(" ".join([v.hook_vo, v.on_screen_text, v.bridge_line]))
    if claims:
        issues.append("unverified claim: " + ", ".join(sorted(set(claims))))
    return issues


def run_checks(gen: Generation, n_expected: int, original_script: str = "") -> dict:
    """Returns per-variant issues plus batch-level pass/fail flags."""
    per_variant = [variant_issues(v) for v in gen.variants]
    hooks = [v.hook_vo for v in gen.variants]
    dup_pairs = [(i, j) for i, j in combinations(range(len(hooks)), 2)
                 if similarity(hooks[i], hooks[j]) > SIMILARITY_MAX]
    for i, j in dup_pairs:
        per_variant[j].append(f"too similar to variant {i + 1}")
    first_line = next((ln for ln in original_script.splitlines() if ln.strip()), "")
    if first_line:
        for k, h in enumerate(hooks):
            if similarity(h, first_line) > SIMILARITY_MAX:
                per_variant[k].append("near-copy of the original hook")
    distinct_types = len({v.hook_type for v in gen.variants})
    min_types = min(4, n_expected)
    batch = {
        "count_ok": len(gen.variants) == n_expected,
        "type_variety_ok": distinct_types >= min_types,
        "no_duplicates": not dup_pairs,
    }
    clean = sum(1 for p in per_variant if not p)
    return {
        "batch": batch,
        "distinct_hook_types": distinct_types,
        "variant_issues": per_variant,
        "clean_variants": clean,
        "clean_rate": clean / max(1, len(gen.variants)),
        "passed": all(batch.values()) and clean / max(1, len(gen.variants)) >= 0.8,
    }
