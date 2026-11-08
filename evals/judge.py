"""LLM-as-judge: scores one batch of variants against a fixed rubric. Model identity is hidden from the judge."""

import json

from hookgen.facts import DEFAULT_FACTS
from hookgen.llm import _extract_json, chat
from hookgen.schema import Generation

# Primary judge: mid-tier, non-frontier, cheap at minimal reasoning (~$0.0014/call). It shares a family with one
# candidate (gemini-3.5-flash-lite), so the top-2 are re-scored by CROSS_JUDGE, chosen from a family that is not
# among the top-2. Mistral Large 4 was tried for both roles and dropped: its reasoning can't be turned off and
# regularly ran past 8k tokens (~$0.016-0.02/call, often with no answer).
JUDGE_MODEL = "google/gemini-3.8-flash"
JUDGE_EFFORT = "minimal"
CROSS_JUDGE = "openai/gpt-6-luna"

RUBRIC = """\
You are the creative director of a direct-response team running Meta video ads in the US.
A copywriter delivered hook variants (first 3 seconds) for MODIFICATIONS of a winning ad. The body of
the winning script stays unchanged; only hook, on-screen text and a bridge line are replaced.

Score the whole batch 1-5 on each criterion (5 = excellent, 3 = usable with edits, 1 = unusable):
- scroll_stop: would these hooks stop a thumb in the first second? Specific, punchy, native to Reels.
- angle_fidelity: do they keep the winning script's angle and promise, so the unchanged body still fits?
- variety: are they genuinely different from each other (type, wording, imagery), not rewordings?
- truthfulness: do they stick to the product facts, with no invented stats, discounts or guarantees?
- production_ready: could a motion designer produce them as-is (clear visual note, bridge flows into body)?

Also count usable_variants: how many variants you would put into production without editing.

Be strict and consistent. Return ONLY JSON:
{"scroll_stop": int, "angle_fidelity": int, "variety": int, "truthfulness": int,
 "production_ready": int, "usable_variants": int, "comment": "one sentence"}
"""

CRITERIA = ["scroll_stop", "angle_fidelity", "variety", "truthfulness", "production_ready"]


def judge(script: str, gen: Generation, model: str = JUDGE_MODEL, effort: str = JUDGE_EFFORT) -> tuple[dict, float]:
    variants = [v.model_dump(exclude={"rationale"}) for v in gen.variants]
    user = (f"PRODUCT FACTS:\n{DEFAULT_FACTS}\nWINNING SCRIPT:\n\"\"\"\n{script}\n\"\"\"\n\n"
            f"VARIANTS ({len(variants)}):\n{json.dumps(variants, indent=1)}")
    msgs = [{"role": "system", "content": RUBRIC}, {"role": "user", "content": user}]
    content, cost = chat(msgs, model, temperature=0.0, max_tokens=8000, reasoning_effort=effort)
    data = _extract_json(content)
    scores = {c: max(1, min(5, int(data[c]))) for c in CRITERIA}
    scores["usable_variants"] = max(0, min(len(variants), int(data.get("usable_variants", 0))))
    scores["mean"] = sum(scores[c] for c in CRITERIA) / len(CRITERIA)
    scores["comment"] = str(data.get("comment", ""))[:300]
    return scores, cost
