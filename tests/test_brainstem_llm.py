"""The brainstem LLM client: OpenAI-compatible, required (raises if unreachable)."""
import json, pytest
import brainstem_llm
from brainstem_llm import BrainstemClient, BrainstemError, _extract_text


def test_extract_text_shapes():
    assert _extract_text({"reply": "hi"}) == "hi"
    assert _extract_text({"response": "yo"}) == "yo"
    assert _extract_text({"choices": [{"message": {"content": "openai-shape"}}]}) == "openai-shape"
    assert _extract_text({"message": {"content": "nested"}}) == "nested"


def test_openai_compatible_surface(monkeypatch):
    captured = {}
    def fake_post(base, payload, timeout=600):
        captured["payload"] = payload
        return {"reply": "MODELED-RESPONSE"}
    monkeypatch.setattr(brainstem_llm, "_post_chat", fake_post)

    client = BrainstemClient(base_url="http://x")
    resp = client.chat.completions.create(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "do it"}],
        model="opus")
    # drop-in OpenAI shape
    assert resp.choices[0].message.content == "MODELED-RESPONSE"
    # model hint forwarded to the brainstem flipper; uses /chat's user_input contract
    assert captured["payload"]["model_preference"] == "opus"
    assert "sys" in captured["payload"]["user_input"]
    assert "do it" in captured["payload"]["user_input"]


def test_required_raises_when_unreachable(monkeypatch):
    def boom(base, payload, timeout=600):
        raise BrainstemError("unreachable")
    monkeypatch.setattr(brainstem_llm, "_post_chat", boom)
    with pytest.raises(BrainstemError):
        BrainstemClient(base_url="http://x").complete([{"role": "user", "content": "hi"}])
