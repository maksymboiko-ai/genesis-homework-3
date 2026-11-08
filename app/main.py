"""Hook Lab web app: one page + a small JSON API around hookgen."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hookgen.checks import run_checks
from hookgen.export import to_csv
from hookgen.llm import FALLBACK_MODEL, LLMError, generate, model_from_env
from hookgen.schema import HOOK_TYPES, LIMITS, GenerateRequest

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
MAX_SCRIPT_CHARS = 6000
EXAMPLE = next(s for s in json.loads((ROOT / "evals" / "scripts.json").read_text(encoding="utf-8"))
               if s["id"] == "s05_humor_dryer")["script"]

app = FastAPI(title="SockLock Hook Lab")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def config():
    return {
        "model": model_from_env(),
        "fallback_model": FALLBACK_MODEL,
        "mock": os.getenv("MOCK_LLM") == "1",
        "hook_types": HOOK_TYPES,
        "limits": LIMITS,
        "max_script_chars": MAX_SCRIPT_CHARS,
        "example_script": EXAMPLE,
    }


def _validate(req: GenerateRequest) -> None:
    script = req.script.strip()
    if not script:
        raise HTTPException(400, "Paste a script first.")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(400, f"Script is {len(script)} characters; the limit is {MAX_SCRIPT_CHARS}.")
    if not 1 <= req.n_variants <= LIMITS["n_max"]:
        raise HTTPException(400, f"Variants must be between 1 and {LIMITS['n_max']}.")
    if req.hook_types is not None:
        unknown = [t for t in req.hook_types if t not in HOOK_TYPES]
        if unknown:
            raise HTTPException(400, f"Unknown hook types: {', '.join(unknown)}")
        if not req.hook_types:
            raise HTTPException(400, "Pick at least one hook type.")


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    _validate(req)
    script = req.script.strip()
    errors, res, fallback_used = [], None, False
    for model in (model_from_env(), FALLBACK_MODEL):
        try:
            res = generate(script, req.n_variants, hook_types=req.hook_types, notes=req.notes,
                           facts=req.facts, model=model)
            break
        except LLMError as e:
            errors.append(str(e))
            fallback_used = True
            if os.getenv("MOCK_LLM") == "1":
                break
    if res is None:
        raise HTTPException(502, " / ".join(errors))
    checks = run_checks(res.generation, req.n_variants, script)
    variants = [v.model_dump() | {"issues": issues}
                for v, issues in zip(res.generation.variants, checks["variant_issues"])]
    return {
        "winning_angle": res.generation.winning_angle,
        "variants": variants,
        "batch_checks": checks["batch"],
        "model": res.model,
        "fallback_used": fallback_used,
        "cost_usd": round(res.cost_usd, 5),
        "latency_s": round(res.latency_s, 1),
        "attempts": res.attempts,
    }


class ExportRequest(BaseModel):
    variants: list[dict]
    source_script: str = ""
    winning_angle: str = ""
    model: str = ""


@app.post("/api/export")
def api_export(req: ExportRequest):
    if not req.variants:
        raise HTTPException(400, "Nothing to export: keep at least one variant.")
    csv_text = to_csv(req.variants, source_script=req.source_script, winning_angle=req.winning_angle,
                      model=req.model)
    # BOM so Excel opens UTF-8 (curly quotes, dashes) correctly; Airtable ignores it.
    return Response("﻿" + csv_text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="hook-lab-variants.csv"'})
