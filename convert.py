#!/usr/bin/env python3
"""
convert.py — RAPP agent.py  ->  Copilot Studio solution (.zip)
==============================================================
Takes a Python RAPP agent (raw GitHub URL or local path), asks the RAPP brainstem
(REQUIRED LLM — the brainstem's model flipper picks the model) to author the
Copilot Studio agent definition, and packages a valid Dataverse/Copilot Studio
solution by rebranding the system skeleton and injecting the generated GPT
instructions. Output is import-ready for agent.py.

Stdlib only. The brainstem LLM step is required: if the brainstem is unreachable
the conversion fails (it is not optional).
"""
from __future__ import annotations
import argparse, io, json, os, re, sys, urllib.request, zipfile

from brainstem_llm import BrainstemClient, BrainstemError

SKELETON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline", "skeleton.zip")
REF_SCHEMA = "dealprogression"     # token in the skeleton to rebrand
REF_DISPLAY = "deal progression"
REF_VERSION = "1.0.470.0"

SYSTEM_PROMPT = (
    "You convert a Python AI agent into a Microsoft Copilot Studio agent. "
    "Read the agent's source and return ONLY a JSON object with keys: "
    "display_name (short human name), unique_name (lowercase letters/digits only, no spaces), "
    "description (one sentence), and instructions (a detailed system prompt for the Copilot "
    "Studio agent: its purpose, capabilities, and how it should behave). No prose, JSON only."
)


def fetch_text(src: str) -> str:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "rapp-convert"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8", "replace")
    with open(src, "r", encoding="utf-8") as f:
        return f.read()


def _sanitize_unique(name: str, fallback: str) -> str:
    u = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return u or re.sub(r"[^a-z0-9]", "", fallback.lower()) or "ragent"


def generate_agent_spec(source_code: str, client: BrainstemClient) -> dict:
    """REQUIRED brainstem call. Returns {display_name, unique_name, description, instructions}."""
    reply = client.complete([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Agent source:\n```python\n{source_code[:12000]}\n```"},
    ], model="opus")  # hint; the brainstem flipper decides
    spec = {}
    m = re.search(r"\{.*\}", reply, re.S)
    if m:
        try:
            spec = json.loads(m.group(0))
        except json.JSONDecodeError:
            spec = {}
    # Robust fallbacks (brainstem was still called; instructions come from it)
    guess = re.search(r"class\s+(\w+)", source_code)
    base = guess.group(1) if guess else "RAPP Agent"
    display = spec.get("display_name") or re.sub(r"(?<!^)(?=[A-Z])", " ", base)
    return {
        "display_name": display.strip()[:60],
        "unique_name": _sanitize_unique(spec.get("unique_name", ""), display),
        "description": (spec.get("description") or f"{display} — converted by RAPP.")[:200],
        "instructions": spec.get("instructions") or reply.strip(),
    }


def render_gpt_data(display_name: str, instructions: str) -> bytes:
    indented = "\n".join("  " + line for line in instructions.splitlines()) or "  Be a helpful agent."
    return (f"kind: GptComponentMetadata\n"
            f"displayName: {display_name}\n"
            f"instructions: |-\n{indented}\n").encode("utf-8")


def build_solution(skeleton_bytes: bytes, spec: dict, version: str = "1.0.1.0") -> bytes:
    uniq, disp = spec["unique_name"], spec["display_name"]
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(skeleton_bytes)) as zin, \
         zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            data = zin.read(item)
            newpath = item.replace(REF_SCHEMA, uniq)
            if newpath.endswith(".gpt.default/data"):
                data = render_gpt_data(disp, spec["instructions"])
            else:
                text = data.decode("utf-8", "replace")
                text = (text.replace(REF_SCHEMA, uniq)
                            .replace(REF_DISPLAY, disp)
                            .replace(REF_VERSION, version))
                data = text.encode("utf-8")
            zout.writestr(newpath, data)
    return out.getvalue()


def convert(source: str, brainstem_url: str | None = None,
            skeleton_path: str = SKELETON, version: str = "1.0.1.0") -> bytes:
    client = BrainstemClient(base_url=brainstem_url)
    code = fetch_text(source)
    spec = generate_agent_spec(code, client)            # REQUIRED LLM step
    with open(skeleton_path, "rb") as f:
        skel = f.read()
    return build_solution(skel, spec, version=version)


def main():
    ap = argparse.ArgumentParser(description="Convert a RAPP agent.py into a Copilot Studio solution")
    ap.add_argument("--source", required=True, help="raw agent.py URL or local path")
    ap.add_argument("--brainstem", default=os.environ.get("RAPP_BRAINSTEM", "http://localhost:7071"))
    ap.add_argument("--out", default="converted_solution.zip")
    args = ap.parse_args()
    try:
        zip_bytes = convert(args.source, brainstem_url=args.brainstem)
    except BrainstemError as e:
        print(f"✗ {e}\n  The conversion LLM step is required — start the brainstem and retry.", file=sys.stderr)
        sys.exit(2)
    with open(args.out, "wb") as f:
        f.write(zip_bytes)
    print(f"✓ Wrote {args.out} ({len(zip_bytes):,} bytes)")


if __name__ == "__main__":
    main()
