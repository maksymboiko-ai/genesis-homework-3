# Model selection — eval results

Eval set: 12 winning scripts x 10 variants each. Judge: `google/gemini-3.8-flash` (temperature 0, model names hidden).
Total eval spend: **$0.3202**.

Selection rule (fixed before the run): see the docstring of `evals/run.py`.

| Model | Valid JSON | Check pass-rate | Judge mean (1-5) | Usable /10 | Scroll | Angle | Variety | Truth | Prod-ready | $/call | p50 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | 100% | 100% | 4.25 | 6.2 | 4.0 | 3.8 | 4.8 | 5.0 | 3.7 | $0.0023 | 17.4 |
| `xiaomi/mimo-v2.6-flash` | 100% | 99% | 4.22 | 6.4 | 4.0 | 3.8 | 4.8 | 5.0 | 3.6 | $0.0009 | 49.0 |
| `z-ai/glm-5.3-flash` | 100% | 98% | 3.95 | 4.9 | 4.0 | 3.2 | 4.5 | 4.9 | 3.1 | $0.0008 | 9.9 |
| `openai/gpt-6-luna` | 100% | 99% | 3.88 | 4.7 | 3.7 | 3.5 | 4.1 | 5.0 | 3.2 | $0.0008 | 14.3 |
| `google/gemini-3.5-flash-lite` | 100% | 99% | 3.78 | 4.1 | 4.0 | 2.9 | 4.2 | 5.0 | 2.8 | $0.0032 | 4.7 |
| `anthropic/claude-haiku-5.5` | 100% | 100% | 3.72 | 3.8 | 3.8 | 2.8 | 4.3 | 5.0 | 2.8 | $0.0021 | 17.7 |
| `minimax/minimax-m3.1-flash` | 100% | 100% | 3.63 | 3.4 | 3.5 | 2.9 | 4.0 | 4.9 | 2.8 | $0.0007 | 7.8 |
| `qwen/qwen3.8-flash` | 83% | 100% | 3.34 | 1.5 | 3.0 | 2.8 | 4.0 | 4.9 | 2.0 | $0.0055 | 85.8 |

Pool: eligible pool (valid JSON 100%, pass-rate >= 95%, p50 <= 30 s).

**Winner: `deepseek/deepseek-v4.1-flash`** — judge 4.25, pass-rate 100%, $0.0023/call, p50 17.4s.
Runner-up: `z-ai/glm-5.3-flash` — judge 3.95, $0.0008/call.

Errors (first 3 per model):
- `qwen/qwen3.8-flash`: generation: Model qwen/qwen3.8-flash hit the token limit before answering (cost $0.0057)
- `qwen/qwen3.8-flash`: generation: Model qwen/qwen3.8-flash hit the token limit before answering (cost $0.0057)

## Cross-check with `openai/gpt-6-luna` (first 6 scripts)

| Model | Runs | Primary judge | Cross judge |
|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | 6 | 4.23 | 3.23 |
| `z-ai/glm-5.3-flash` | 6 | 3.73 | 2.87 |

Ranking agrees with the primary judge. Cross-check spend: $0.0039.

## Decision

- **Production model: `deepseek/deepseek-v4.1-flash`.** Best judge score among eligible models, 100% schema-valid,
  100% of variants pass the checks, ~$0.0023 per 10-variant batch, p50 ~17 s.
- **Fallback: `z-ai/glm-5.3-flash`.** Used automatically if the primary call fails.
- `xiaomi/mimo-v2.6-flash` scored about the same (4.22) but was excluded on latency (p50 49 s > 30 s).
- The judges disagree on absolute level (the cross judge is stricter) but agree on the ranking.
- Weak spot seen in the judge comments: when asked to cover every hook type, models write some variants
  (gift/callout) that drift from the winning angle. The UI lets the designer pick hook types; prompt v2 is next.
- Prompt and rubric were frozen for this run; any prompt change needs a re-run (~$0.40) before shipping.
