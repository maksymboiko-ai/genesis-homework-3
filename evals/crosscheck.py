"""Re-judge stored generations of the top models with a second judge from another family.

Guards against the primary judge favouring its own family. Reads evals/results/raw.jsonl; appends to RESULTS.md.
Usage: python -m evals.crosscheck --models deepseek/deepseek-v4.1-flash z-ai/glm-5.3-flash --limit 4
"""

import argparse
import json
import statistics
from pathlib import Path

from dotenv import load_dotenv

from hookgen.llm import LLMError
from hookgen.schema import Generation

from .judge import CROSS_JUDGE, judge

ROOT = Path(__file__).parent


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=4, help="first N scripts per model")
    args = ap.parse_args()

    scripts = {s["id"]: s["script"] for s in json.loads((ROOT / "scripts.json").read_text(encoding="utf-8"))}
    recs = [json.loads(line) for line in (ROOT / "results" / "raw.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    ids = list(scripts)[:args.limit]
    total, rows = 0.0, []
    for m in args.models:
        primary, cross = [], []
        for r in recs:
            if r["model"] != m or r["script_id"] not in ids or not r.get("ok"):
                continue
            if r["model"].split("/")[0] == CROSS_JUDGE.split("/")[0]:
                raise SystemExit(f"{CROSS_JUDGE} would judge its own family ({m}); pick another cross judge")
            try:
                scores, cost = judge(scripts[r["script_id"]], Generation.model_validate(r["generation"]),
                                     model=CROSS_JUDGE, effort="low")
            except (LLMError, ValueError, KeyError) as e:
                print(f"skip {m} {r['script_id']}: {e}")
                continue
            total += cost
            primary.append(r["judge"]["mean"])
            cross.append(scores["mean"])
        rows.append((m, len(cross), statistics.mean(primary), statistics.mean(cross)))

    lines = ["", f"## Cross-check with `{CROSS_JUDGE}` (first {args.limit} scripts)", "",
             "| Model | Runs | Primary judge | Cross judge |", "|---|---|---|---|"]
    lines += [f"| `{m}` | {n} | {p:.2f} | {c:.2f} |" for m, n, p, c in rows]
    order_primary = [m for m, *_ in sorted(rows, key=lambda x: -x[2])]
    order_cross = [m for m, *_ in sorted(rows, key=lambda x: -x[3])]
    verdict = "agrees" if order_primary == order_cross else "DISAGREES"
    lines += ["", f"Ranking {verdict} with the primary judge. Cross-check spend: ${total:.4f}."]
    with open(ROOT / "RESULTS.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
