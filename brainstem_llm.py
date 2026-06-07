"""
Brainstem LLM client — the intelligence injection point.
=======================================================
Routes the pipeline's required LLM steps through the RAPP brainstem's `/chat`
endpoint, which uses the brainstem's GitHub/Copilot-model access. Model selection
is the brainstem's job (its model flipper) — we don't pin a model here.

Two surfaces:
  * BrainstemClient — OpenAI-compatible (`client.chat.completions.create(...)`),
    a drop-in for pipeline code that expects an OpenAI client.
  * complete(messages) / chat(prompt) — direct helpers.

Stdlib only (urllib). Raises BrainstemError if the brainstem is unreachable —
the LLM step is REQUIRED, not optional.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error


class BrainstemError(RuntimeError):
    pass


def _post_chat(base_url: str, payload: dict, timeout: int = 600) -> dict:
    url = base_url.rstrip("/") + "/chat"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise BrainstemError(f"RAPP brainstem unreachable at {url}: {e}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"reply": body}


def _extract_text(resp: dict) -> str:
    """Pull the assistant text out of whatever shape the brainstem returns."""
    if not isinstance(resp, dict):
        return str(resp)
    # OpenAI-style
    if "choices" in resp and resp["choices"]:
        ch = resp["choices"][0]
        msg = ch.get("message", ch)
        if isinstance(msg, dict) and "content" in msg:
            return msg["content"]
    for k in ("reply", "response", "message", "content", "text", "result", "output", "answer"):
        v = resp.get(k)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict) and isinstance(v.get("content"), str):
            return v["content"]
    return json.dumps(resp)


class _Message:
    def __init__(self, content): self.content = content
class _Choice:
    def __init__(self, content): self.message = _Message(content)
class _Completion:
    def __init__(self, content): self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, client): self._c = client
    def create(self, messages, model=None, temperature=None, **kw):
        return _Completion(self._c.complete(messages, model=model, temperature=temperature, **kw))
class _Chat:
    def __init__(self, client): self.completions = _Completions(client)


class BrainstemClient:
    """OpenAI-compatible client backed by the RAPP brainstem."""
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("RAPP_BRAINSTEM_URL", "http://localhost:7071")
        self.chat = _Chat(self)

    def health(self) -> bool:
        try:
            req = urllib.request.Request(self.base_url.rstrip("/") + "/health")
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status == 200
        except Exception:
            return False

    def complete(self, messages, model=None, temperature=None, **kw) -> str:
        # Flatten OpenAI-style messages into one prompt; keep system separate.
        system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
        convo = "\n".join(m["content"] for m in messages if m.get("role") != "system")
        prompt = (system + "\n\n" + convo).strip() if system else convo
        # Brainstem /chat contract: {"user_input": ...} -> {"response": ...}
        payload = {"user_input": prompt, "source": "rapp-oneclick-pipeline"}
        if model:
            payload["model_preference"] = model      # the brainstem's flipper may honor it
        if temperature is not None:
            payload["temperature"] = temperature
        return _extract_text(_post_chat(self.base_url, payload, timeout=kw.get("timeout", 600)))


def create_llm_client(mode: str = "brainstem", base_url: str | None = None, **_) -> BrainstemClient:
    """Drop-in for the pipeline's llm_client factory — always returns a brainstem client."""
    return BrainstemClient(base_url=base_url)
