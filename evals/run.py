"""Run candidate models over the eval set, score them, and write evals/RESULTS.md.

Usage:
  python -m evals.run                       # all candidates, all scripts
  python -m evals.run --models openai/gpt-6-luna --limit 2
  python -m evals.run --budget 1.0          # stop starting new calls once spend reaches $1

Selection rule (fixed BEFORE looking at results):
  1. Eligible = 100% valid JSON, check pass-rate (share of variants with zero issues) >= 95%,
     p50 latency <= 30 s.
  2. Winner = highest mean judge score among eligible models; if within 0.1, the cheaper one wins.
  3. If no model is eligible, take the 3 models with the best pass-rate and apply rule 2 to them.
"""

import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from hookgen.checks import run_checks
from hookgen.llm import LLMError, generate

from .judge import CRITERIA, JUDGE_MODEL, judge

ROOT = Path(__file__).parent
CANDIDATES = [
    "anthropic/claude-haiku-5.5",
    "openai/gpt-6-luna",
    "deepseek/deepseek-v4.1-flash",
    "qwen/qwen3.8-flash",
    "xiaomi/mimo-v2.6-flash",
    "minimax/minimax-m3.1-flash",
    "z-ai/glm-5.3-flash",
    "google/gemini-3.5-flash-lite",
]
N_VARIANTS = 10


class Budget:
    def __init__(self, limit: float):
        self.limit, self.spent, self.lock = limit, 0.0, threading.Lock()

    def add(self, x: float):
        with self.lock:
            self.spent += x

    def exhausted(self) -> bool:
        with self.lock:
            return self.spent >= self.limit


def run_one(model: str, item: dict, budget: Budget) -> dict:
    rec = {"model": model, "script_id": item["id"], "ok": False}
    if budget.exhausted():
        rec["error"] = "budget exhausted"
        return rec
    try:
        res = generate(item["script"], N_VARIANTS, model=model)
    except LLMError as e:
        rec["error"] = f"generation: {str(e)[:300]}"
        return rec
    budget.add(res.cost_usd)
    rec.update(gen_cost=res.cost_usd, latency=res.latency_s, attempts=res.attempts,
               generation=res.generation.model_dump())
    rec["checks"] = run_checks(res.generation, N_VARIANTS, item["script"])
    try:
        scores, jcost = judge(item["script"], res.generation)
    except (LLMError, ValueError, KeyError, TypeError) as e:
        rec["error"] = f"judge: {str(e)[:300]}"  # generation data is kept; this run is excluded from scoring
        return rec
    budget.add(jcost)
    rec.update(judge=scores, judge_cost=jcost, ok=True)
    return rec


def summarize(records: list[dict], models: list[str]) -> list[dict]:
    rows = []
    for m in models:
        rs = [r for r in records if r["model"] == m]
        ok = [r for r in rs if r["ok"]]
        if not rs:
            continue
        variants = sum(len(r["generation"]["variants"]) for r in ok)
        clean = sum(r["checks"]["clean_variants"] for r in ok)
        row = {
            "model": m,
            "runs": len(rs),
            "valid_json_rate": len(ok) / len(rs),
            "pass_rate": clean / variants if variants else 0.0,
            "judge_mean": statistics.mean(r["judge"]["mean"] for r in ok) if ok else 0.0,
            "usable_per_10": statistics.mean(r["judge"]["usable_variants"] for r in ok) if ok else 0.0,
            "cost_per_call": statistics.mean(r["gen_cost"] for r in ok) if ok else 0.0,
            "p50_latency": statistics.median(r["latency"] for r in ok) if ok else 0.0,
            "retries": sum(r["attempts"] - 1 for r in ok),
            "errors": [r.get("error") for r in rs if not r["ok"]][:3],
        }
        for c in CRITERIA:
            row[c] = statistics.mean(r["judge"][c] for r in ok) if ok else 0.0
        rows.append(row)
    return rows


def pick_winner(rows: list[dict]) -> tuple[dict | None, dict | None, str]:
    rows = [r for r in rows if r["valid_json_rate"] > 0]
    if not rows:
        return None, None, "no model produced a single scored run"
    eligible = [r for r in rows if r["valid_json_rate"] == 1.0 and r["pass_rate"] >= 0.95
                and r["p50_latency"] <= 30]
    note = "eligible pool (valid JSON 100%, pass-rate >= 95%, p50 <= 30 s)"
    if not eligible:
        eligible = sorted(rows, key=lambda r: -r["pass_rate"])[:3]
        note = "no model met the bar -> fallback pool: top-3 by pass-rate"
    ranked = sorted(eligible, key=lambda r: -r["judge_mean"])
    if len(ranked) >= 2 and ranked[0]["judge_mean"] - ranked[1]["judge_mean"] <= 0.1 \
            and ranked[1]["cost_per_call"] < ranked[0]["cost_per_call"]:
        ranked[0], ranked[1] = ranked[1], ranked[0]
    return (ranked[0] if ranked else None), (ranked[1] if len(ranked) > 1 else None), note


def write_report(rows, winner, runner_up, note, total_cost, n_scripts: int, path: Path):
    lines = [
        "# Model selection — eval results", "",
        f"Eval set: {n_scripts} winning scripts "
        f"x {N_VARIANTS} variants each. Judge: `{JUDGE_MODEL}` (temperature 0, model names hidden).",
        f"Total eval spend: **${total_cost:.4f}**.", "",
        "Selection rule (fixed before the run): see the docstring of `evals/run.py`.", "",
        "| Model | Valid JSON | Check pass-rate | Judge mean (1-5) | Usable /10 | Scroll | Angle | Variety | Truth | Prod-ready | $/call | p50 s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: -r["judge_mean"]):
        lines.append(
            f"| `{r['model']}` | {r['valid_json_rate']:.0%} | {r['pass_rate']:.0%} | {r['judge_mean']:.2f} | "
            f"{r['usable_per_10']:.1f} | {r['scroll_stop']:.1f} | {r['angle_fidelity']:.1f} | {r['variety']:.1f} | "
            f"{r['truthfulness']:.1f} | {r['production_ready']:.1f} | ${r['cost_per_call']:.4f} | {r['p50_latency']:.1f} |")
    lines += ["", f"Pool: {note}.", ""]
    if winner:
        lines.append(f"**Winner: `{winner['model']}`** — judge {winner['judge_mean']:.2f}, pass-rate "
                     f"{winner['pass_rate']:.0%}, ${winner['cost_per_call']:.4f}/call, p50 {winner['p50_latency']:.1f}s.")
    if runner_up:
        lines.append(f"Runner-up: `{runner_up['model']}` — judge {runner_up['judge_mean']:.2f}, "
                     f"${runner_up['cost_per_call']:.4f}/call.")
    errs = [(r["model"], e) for r in rows for e in r["errors"]]
    if errs:
        lines += ["", "Errors (first 3 per model):"] + [f"- `{m}`: {e}" for m, e in errs]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=CANDIDATES)
    ap.add_argument("--limit", type=int, default=0, help="only first N scripts")
    ap.add_argument("--budget", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    items = json.loads((ROOT / "scripts.json").read_text(encoding="utf-8"))
    if args.limit:
        items = items[:args.limit]
    budget = Budget(args.budget)
    jobs = [(m, it) for it in items for m in args.models]
    print(f"{len(jobs)} jobs, budget ${args.budget}", file=sys.stderr)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        records = list(ex.map(lambda j: run_one(j[0], j[1], budget), jobs))
    out_dir = ROOT / args.out
    out_dir.mkdir(exist_ok=True)
    (out_dir / "raw.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    rows = summarize(records, args.models)
    winner, runner_up, note = pick_winner(rows)
    write_report(rows, winner, runner_up, note, budget.spent, len(items), ROOT / "RESULTS.md")
    print(f"done in {time.time() - t0:.0f}s, spent ${budget.spent:.4f}", file=sys.stderr)
    print((ROOT / "RESULTS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
