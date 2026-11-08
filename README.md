# SockLock Hook Lab

Takes one **winning ad script** and returns 10 ready-to-produce **modifications**: new spoken hooks, on-screen text,
a bridge line into the unchanged body, and a shot note for the first 3 seconds. Designers keep the good ones and
export them as CSV briefs for Airtable.

**Why it exists.** To double spend to $800k/mo, SockLock needs about 500 mods a month instead of today's 240. The six motion designers
already log about 1,200 h of work a month against 960 h nominal, and about 30% of that time goes on rewriting hooks and on-screen copy by hand.
Hook Lab takes over the copy part, so a mod should drop from about 3 h to about 2 h. That frees capacity for about 120 more mods a month at the same headcount.

---

## Run it

Needs Python 3.11+ and an [OpenRouter](https://openrouter.ai) key.

```bash
pip install -r requirements.txt
cp .env.example .env        # then put your key in OPENROUTER_API_KEY
python -m app               # open http://127.0.0.1:8000
```

No key? `python -m app --mock` serves fixture output so you can try the whole UI offline.
Options: `--port 8080`; env `HOOKGEN_MODEL=<openrouter id>` overrides the model.

**Use it:** paste a winning script (or click *Load example*) → choose how many variants and which hook types →
*Generate* (about 15 s, about $0.003) → *Keep* the ones worth producing (↻ rewrites a single card) → *Export kept to CSV* → import into Airtable.

Tests: `python -m pytest -q` (25 tests, offline).

---

## How it works

```
static/index.html ──POST /api/generate──▶ app/main.py ──▶ hookgen/llm.py ──▶ OpenRouter (deepseek-v4.1-flash)
      ▲                                       │  validate input        │  prompt.py builds the messages
      │                                       │  fallback model on error  │  JSON → pydantic schema, 1 retry
      └────── variants + per-card issues ◀───┘  checks.py per variant  └─ cost + latency reported
                POST /api/export ─▶ hookgen/export.py ─▶ CSV (Airtable columns)
```

| Part | What it does |
|---|---|
| `hookgen/prompt.py` | The system prompt encodes what a *modification* is: same body, new first 3 seconds. It sets length limits, the 10 hook types and the product facts, and asks for JSON only. |
| `hookgen/schema.py` | Output structure (pydantic). Content rules live in the checks, not here. |
| `hookgen/checks.py` | Deterministic checks: word and character limits, near-duplicate hooks, copying the original hook, hook-type variety, and **claims not in the product facts** (invented prices, %, "10,000 customers", guarantees). The UI shows failures as a warning badge on the card. |
| `hookgen/llm.py` | OpenRouter call with low reasoning effort (otherwise reasoning models spend the whole token budget before answering), JSON extraction, one repair retry, cost from `usage`. |
| `app/main.py` | FastAPI: `/api/config`, `/api/generate` (tries the eval runner-up automatically if the primary model fails), `/api/export`. |
| `static/index.html` | One page with no build step, implementing the Claude Design layout. Model text is inserted as text nodes, never parsed as HTML. |
| `evals/` | How the model was chosen (below). |

### Model choice: an eval, not a guess

`python -m evals.run` runs 8 cheap OpenRouter models over 12 winning scripts (10 variants each). Each batch is scored by the deterministic
checks plus an LLM judge (gemini-3.8-flash, rubric: scroll-stop, angle fidelity, variety, truthfulness, production-ready). The
selection rule was fixed before the run. Results are in [evals/RESULTS.md](evals/RESULTS.md):

| | Judge (1–5) | Checks passed | $/batch | p50 |
|---|---|---|---|---|
| **deepseek-v4.1-flash** (used) | 4.25 | 100% | $0.0023 | 17 s |
| glm-5.3-flash (fallback) | 3.95 | 98% | $0.0008 | 10 s |

A second judge from another model family confirmed the ranking. The whole eval cost $0.55. Running cost at 500 mods a month is about **$2–3 a month**.

---

## How we'd measure success

Baseline: 2 weeks of time-tracking on mod tasks **before** rollout (Airtable start/finish timestamps).

| Metric | Baseline | Target | When | How measured |
|---|---|---|---|---|
| Designer hours per mod | ~3.0 h | **≤ 2.0 h** (stretch 1.6 h) | 4 weeks after rollout | Airtable task timestamps |
| Mods shipped per month, same 6 designers | ~240 | **≥ 360** (stretch 450+) | month 2 | Airtable count |
| Extra designers needed to reach 500 mods/mo | 3.9 | **≤ 1.5** | month 3 | capacity model |
| Share of generated variants kept | n/a | **≥ 30%** | week 2 | export logs |
| ROMI of tool-assisted mods vs manual mods (guardrail) | 140% | **not lower** (±5 pp) | 4-week A/B, equal budgets | Meta export by ad naming tag |
| Token cost | n/a | < $10/mo | monthly | OpenRouter usage |

**Kill or iterate:** if after 4 weeks a mod still takes more than 2.6 h, or tool-assisted mods underperform manual ones by more than 5 pp of
ROMI, stop the rollout and fix the prompt or workflow before scaling.

## Next iteration

1. **Prompt v2:** pick only the hook types that fit the winning angle (the judge's most common criticism). Re-run the eval before shipping (about $0.40).
2. **Learn from results:** import the Meta ads export CSV, tag each mod by hook type, and feed the best-performing hooks back into the prompt as examples.
3. **Airtable push** instead of CSV, once we have API access, so kept variants become brief records directly.
4. **Editable product facts** for each market. The same pipeline then gives first-draft **DE/FR localization** (the Head of Marketing's ask).
5. **Shared deployment:** a small VM with SSO for the team (about $10 a month), plus usage logging for the metrics above.
6. **Batch mode:** this week's 5 winners in, 50 variants out.

---

## Repo layout

```
app/        FastAPI app (python -m app)
hookgen/    prompt, schema, checks, LLM client, CSV export (shared by app and evals)
static/     the single-page UI
evals/      eval set, judge, runner, results (RESULTS.md, results/raw.jsonl)
tests/      pytest suite (offline)
```
