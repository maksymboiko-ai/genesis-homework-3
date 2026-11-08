"""CSV export shaped for an Airtable 'Mod briefs' table: one row per variant."""

import csv
import io
from datetime import datetime, timezone

COLUMNS = ["variant_id", "hook_type", "hook_vo", "on_screen_text", "bridge_line", "visual_note",
           "rationale", "check_issues", "winning_angle", "source_script", "model", "created_at"]


def to_csv(variants: list[dict], *, source_script: str = "", winning_angle: str = "", model: str = "") -> str:
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for i, v in enumerate(variants, 1):
        w.writerow({
            "variant_id": f"V{i:02d}",
            "hook_type": v.get("hook_type", ""),
            "hook_vo": v.get("hook_vo", ""),
            "on_screen_text": v.get("on_screen_text", ""),
            "bridge_line": v.get("bridge_line", ""),
            "visual_note": v.get("visual_note", ""),
            "rationale": v.get("rationale", ""),
            "check_issues": "; ".join(v.get("issues") or []),
            "winning_angle": winning_angle,
            "source_script": source_script,
            "model": model,
            "created_at": created,
        })
    return buf.getvalue()
