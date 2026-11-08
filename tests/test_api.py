import pytest
from fastapi.testclient import TestClient

import app.main as main
from hookgen.llm import LLMError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    return TestClient(main.app)


def test_index_and_config(client):
    assert client.get("/").status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["mock"] is True and "humor" in cfg["hook_types"] and cfg["example_script"]


def test_generate_happy_path(client):
    r = client.post("/api/generate", json={"script": "Line one\nLine two", "n_variants": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["variants"]) == 10
    assert all(v["issues"] == [] for v in body["variants"])
    assert body["batch_checks"] == {"count_ok": True, "type_variety_ok": True, "no_duplicates": True}


@pytest.mark.parametrize("payload,msg", [
    ({"script": "   "}, "Paste a script"),
    ({"script": "x" * 7000}, "limit is 6000"),
    ({"script": "ok", "n_variants": 0}, "between 1 and 20"),
    ({"script": "ok", "n_variants": 21}, "between 1 and 20"),
    ({"script": "ok", "hook_types": ["nope"]}, "Unknown hook types"),
    ({"script": "ok", "hook_types": []}, "at least one"),
])
def test_generate_validation(client, payload, msg):
    r = client.post("/api/generate", json=payload)
    assert r.status_code == 400 and msg in r.json()["detail"]


def test_generate_falls_back_then_reports_errors(monkeypatch):
    monkeypatch.delenv("MOCK_LLM", raising=False)
    calls = []

    def boom(*a, model=None, **k):
        calls.append(model)
        raise LLMError(f"{model} down")

    monkeypatch.setattr(main, "generate", boom)
    r = TestClient(main.app).post("/api/generate", json={"script": "hello"})
    assert r.status_code == 502
    assert len(calls) == 2 and calls[1] == main.FALLBACK_MODEL
    assert "down" in r.json()["detail"]


def test_generate_uses_fallback_when_primary_fails(monkeypatch):
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from hookgen.llm import CallResult
    from hookgen.mock import mock_generation

    def flaky(script, n, *, model=None, **k):
        if model != main.FALLBACK_MODEL:
            raise LLMError("primary timeout")
        return CallResult(mock_generation(n), model, 0.001, 1.0)

    monkeypatch.setattr(main, "generate", flaky)
    r = TestClient(main.app).post("/api/generate", json={"script": "hello", "n_variants": 3})
    assert r.status_code == 200
    assert r.json()["fallback_used"] is True and r.json()["model"] == main.FALLBACK_MODEL


def test_export(client):
    r = client.post("/api/export", json={"variants": [{"hook_type": "pain", "hook_vo": "Hi"}],
                                         "source_script": "s", "model": "m"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.decode("utf-8-sig").startswith("variant_id,hook_type")


def test_export_empty(client):
    assert client.post("/api/export", json={"variants": []}).status_code == 400
