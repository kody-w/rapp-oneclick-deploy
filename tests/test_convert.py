"""convert.py: brainstem-driven (required) agent.py -> valid Copilot Studio solution."""
import io, zipfile, pytest
import convert
import brainstem_llm
from conftest import SAMPLE_AGENT, CANNED_SPEC


def _import_brainstem(monkeypatch, reply):
    """Make every brainstem call return `reply` and record that it was called."""
    calls = {"n": 0}
    def fake_post(base, payload, timeout=600):
        calls["n"] += 1
        return {"reply": reply}
    monkeypatch.setattr(brainstem_llm, "_post_chat", fake_post)
    return calls


def test_convert_requires_brainstem(monkeypatch):
    """If the brainstem is down, conversion fails — the LLM step is not optional."""
    def boom(base, payload, timeout=600):
        raise brainstem_llm.BrainstemError("down")
    monkeypatch.setattr(brainstem_llm, "_post_chat", boom)
    monkeypatch.setattr(convert, "fetch_text", lambda s: SAMPLE_AGENT)
    with pytest.raises(brainstem_llm.BrainstemError):
        convert.convert("dummy")


def test_convert_calls_brainstem_and_builds_valid_solution(monkeypatch):
    import json
    calls = _import_brainstem(monkeypatch, json.dumps(CANNED_SPEC))
    monkeypatch.setattr(convert, "fetch_text", lambda s: SAMPLE_AGENT)

    zip_bytes = convert.convert("https://example/agent.py", version="1.0.7.0")
    assert calls["n"] >= 1, "brainstem (LLM) must be invoked"

    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = z.namelist()

    # 1. valid solution structure
    assert "solution.xml" in names
    assert "customizations.xml" in names
    assert "[Content_Types].xml" in names

    # 2. rebranded to the new agent — no source agent token leaks
    assert not any("dealprogression" in n for n in names)
    assert any(n.startswith("bots/rapp_accountintelligence/") for n in names)

    # 3. solution.xml carries the new unique name + version
    sol = z.read("solution.xml").decode()
    assert "<UniqueName>accountintelligence</UniqueName>" in sol
    assert "1.0.7.0" in sol

    # 4. GPT instructions came from the brainstem
    gpt = z.read("botcomponents/rapp_accountintelligence.gpt.default/data").decode()
    assert "account intelligence agent" in gpt.lower()
    assert gpt.startswith("kind: GptComponentMetadata")

    # 5. [Content_Types] references every /data part that exists (manifest consistency)
    ct = z.read("[Content_Types].xml").decode()
    for n in names:
        if n.endswith("/data"):
            assert f'PartName="/{n}"' in ct, f"missing content-type override for {n}"


def test_spec_fallback_still_uses_brainstem_text(monkeypatch):
    """If the brainstem returns prose (not JSON), its text becomes the instructions."""
    _import_brainstem(monkeypatch, "Be an excellent account intelligence assistant.")
    monkeypatch.setattr(convert, "fetch_text", lambda s: SAMPLE_AGENT)
    client = brainstem_llm.BrainstemClient(base_url="http://x")
    spec = convert.generate_agent_spec(SAMPLE_AGENT, client)
    assert spec["unique_name"].isalnum()
    assert "account intelligence" in spec["instructions"].lower()
