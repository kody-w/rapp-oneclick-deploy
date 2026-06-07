"""
CopilotStudioDeploy — a RAPP brainstem agent.
=============================================
Drop this single file into the brainstem's `agents/` folder. The kernel's Copilot
LLM does the reasoning (reads an agent.py, authors the Copilot Studio instructions,
picks the environment from the conversation) and calls this agent to do the
deterministic work: package a valid solution and import it into the user's own
Copilot Studio environment.

Self-contained, stdlib only. Public assets (system skeleton + prebuilt catalog)
are pulled from https://github.com/kody-w/rapp-oneclick-deploy.

Actions (the `action` parameter):
  list_catalog     -> available agents (prebuilt + convert-from-source)
  fetch_source     -> fetch an agent.py from a raw URL (so the LLM can author instructions)
  package          -> {agent_name, instructions} -> a packaged solution (cached, returns package_id)
  deploy           -> {solution_url|package_id} -> begin device-code sign-in (returns code to relay)
  complete_deploy  -> {device_code} -> finish sign-in, discover env, ImportSolution + publish
"""
import base64, io, json, os, re, time, urllib.request, urllib.parse, uuid, zipfile
from openrappter.agents.basic_agent import BasicAgent

REPO_RAW = "https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/main"
PUBLIC_CLIENT = "9cee029c-6210-4654-90bb-17e6e9d36617"   # Power Platform CLI public client
AUTH = "https://login.microsoftonline.com"
DISCO = "https://globaldisco.crm.dynamics.com"
REF_SCHEMA, REF_DISPLAY, REF_VERSION = "dealprogression", "deal progression", "1.0.470.0"

_CACHE = {}   # package_id -> zip bytes ;  device_code -> {"zip":bytes,"env":str|None}


# ── http ──────────────────────────────────────────────────────────────────────
def _req(url, data=None, headers=None, method=None, timeout=300):
    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    elif data is not None and not isinstance(data, (bytes, bytearray)):
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(body) if body[:1] in ("{", "[") else body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try: body = json.loads(body)
        except Exception: pass
        return e.code, body

def _get_bytes(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "rapp"}), timeout=timeout) as r:
        return r.read()


# ── packaging (rebrand skeleton + inject brainstem-authored instructions) ──────
def _render_gpt(display_name, instructions):
    body = "\n".join("  " + ln for ln in (instructions or "Be a helpful agent.").splitlines())
    return f"kind: GptComponentMetadata\ndisplayName: {display_name}\ninstructions: |-\n{body}\n".encode()

def _sanitize(name, fallback="ragent"):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower()) or fallback

def build_solution(skeleton_bytes, agent_name, unique_name, instructions, version="1.0.1.0"):
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(skeleton_bytes)) as zin, \
         zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.namelist():
            data = zin.read(item)
            newpath = item.replace(REF_SCHEMA, unique_name)
            if newpath.endswith(".gpt.default/data"):
                data = _render_gpt(agent_name, instructions)
            else:
                data = (data.decode("utf-8", "replace")
                        .replace(REF_SCHEMA, unique_name)
                        .replace(REF_DISPLAY, agent_name)
                        .replace(REF_VERSION, version)).encode()
            zout.writestr(newpath, data)
    return out.getvalue()


# ── auth + deploy ──────────────────────────────────────────────────────────────
def _device_start(scope):
    code, r = _req(f"{AUTH}/organizations/oauth2/v2.0/devicecode",
                   data={"client_id": PUBLIC_CLIENT, "scope": scope},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200:
        raise RuntimeError(f"device code start failed: {r}")
    return r

def _token_from_device(device_code):
    return _req(f"{AUTH}/organizations/oauth2/v2.0/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                      "client_id": PUBLIC_CLIENT, "device_code": device_code},
                headers={"Content-Type": "application/x-www-form-urlencoded"})

def _refresh(refresh_token, scope):
    code, t = _req(f"{AUTH}/organizations/oauth2/v2.0/token",
                   data={"grant_type": "refresh_token", "refresh_token": refresh_token,
                         "client_id": PUBLIC_CLIENT, "scope": scope},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200:
        raise RuntimeError(f"token refresh failed: {t}")
    return t["access_token"]

def _discover(disco_token):
    code, r = _req(f"{DISCO}/api/discovery/v2.0/Instances",
                   headers={"Authorization": "Bearer " + disco_token, "Accept": "application/json"})
    return [e for e in (r.get("value", []) if isinstance(r, dict) else []) if e.get("ApiUrl")]

def _dataverse(env, token, action, body=None, method="POST"):
    return _req(f"{env.rstrip('/')}/api/data/v9.2/{action}",
                data=body, method=method,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                         "Accept": "application/json", "OData-MaxVersion": "4.0", "OData-Version": "4.0"})

def _import(env, token, zip_bytes):
    code, r = _dataverse(env, token, "ImportSolution", {
        "OverwriteUnmanagedCustomizations": True, "PublishWorkflows": True,
        "ImportJobId": str(uuid.uuid4()), "CustomizationFile": base64.b64encode(zip_bytes).decode()})
    if code not in (200, 204):
        raise RuntimeError(f"ImportSolution failed ({code}): {r}")
    _dataverse(env, token, "PublishAllXml")


class CopilotStudioDeployAgent(BasicAgent):
    def __init__(self):
        self.name = "CopilotStudioDeploy"
        self.metadata = {
            "name": self.name,
            "description": (
                "Convert and deploy a RAPP agent into the user's own Microsoft Copilot Studio "
                "environment. Workflow: (1) action=fetch_source with a raw agent.py URL to read it, "
                "then YOU author a short display name + a detailed Copilot Studio instructions prompt; "
                "(2) action=package with agent_name + instructions to build the solution; "
                "(3) action=deploy with the returned package_id (or a solution_url for a prebuilt agent) "
                "to start sign-in and relay the code to the user; (4) action=complete_deploy with the "
                "device_code once they have signed in. Use action=list_catalog to show ready-made agents."),
            "parameters": {"type": "object", "properties": {
                "action": {"type": "string", "enum": ["list_catalog", "fetch_source", "package",
                                                       "deploy", "complete_deploy"]},
                "source_url": {"type": "string", "description": "raw agent.py URL (fetch_source)"},
                "agent_name": {"type": "string", "description": "human display name (package)"},
                "instructions": {"type": "string", "description": "Copilot Studio system instructions you authored (package)"},
                "unique_name": {"type": "string", "description": "optional lowercase id (package)"},
                "package_id": {"type": "string", "description": "id returned by package (deploy)"},
                "solution_url": {"type": "string", "description": "raw URL of a prebuilt solution .zip (deploy)"},
                "environment_url": {"type": "string", "description": "optional target env https://org.crm.dynamics.com"},
                "device_code": {"type": "string", "description": "device_code from deploy (complete_deploy)"},
            }, "required": ["action"]},
        }
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        action = (kwargs.get("action") or "").strip()
        try:
            if action == "list_catalog":
                cat = json.loads(_get_bytes(f"{REPO_RAW}/catalog/agents.json").decode())
                return json.dumps({"status": "success", "agents": [
                    {"id": a["id"], "name": a["name"], "category": a.get("category"),
                     "status": a["status"],
                     "solution_url": (f"{REPO_RAW}/{a['solution']}" if a.get("solution") else None),
                     "source": a.get("source")} for a in cat.get("agents", [])]})

            if action == "fetch_source":
                src = kwargs.get("source_url", "")
                if not src.startswith("http"):
                    return json.dumps({"status": "error", "message": "source_url (raw agent.py URL) required"})
                text = _get_bytes(src).decode("utf-8", "replace")
                return json.dumps({"status": "success", "source_url": src, "length": len(text),
                                   "source": text[:12000],
                                   "next": "Author agent_name + instructions, then call action=package."})

            if action == "package":
                name = kwargs.get("agent_name") or "RAPP Agent"
                instr = kwargs.get("instructions")
                if not instr:
                    return json.dumps({"status": "error", "message": "instructions required — author them from the agent source first"})
                uniq = _sanitize(kwargs.get("unique_name") or name)
                skel = _get_bytes(f"{REPO_RAW}/pipeline/skeleton.zip")
                zip_bytes = build_solution(skel, name, uniq, instr)
                pid = uniq + "-" + uuid.uuid4().hex[:8]
                _CACHE[pid] = zip_bytes
                return json.dumps({"status": "success", "package_id": pid, "unique_name": uniq,
                                   "size": len(zip_bytes), "next": "Call action=deploy with this package_id."})

            if action == "deploy":
                if kwargs.get("solution_url"):
                    zip_bytes = _get_bytes(kwargs["solution_url"])
                elif kwargs.get("package_id") in _CACHE:
                    zip_bytes = _CACHE[kwargs["package_id"]]
                else:
                    return json.dumps({"status": "error", "message": "provide solution_url or a valid package_id"})
                dc = _device_start(f"{DISCO}/user_impersonation offline_access")
                _CACHE[dc["device_code"]] = {"zip": zip_bytes, "env": kwargs.get("environment_url")}
                return json.dumps({"status": "auth_required", "device_code": dc["device_code"],
                                   "user_code": dc["user_code"], "verification_uri": dc["verification_uri"],
                                   "message": (f"Tell the user: open {dc['verification_uri']} and enter code "
                                               f"{dc['user_code']}, sign into the Copilot Studio environment, "
                                               "then call action=complete_deploy with this device_code.")})

            if action == "complete_deploy":
                dc = kwargs.get("device_code", "")
                pending = _CACHE.get(dc)
                if not pending:
                    return json.dumps({"status": "error", "message": "unknown device_code — call action=deploy first"})
                # poll briefly for the token (user should have signed in by now)
                tok = None
                for _ in range(20):
                    code, t = _token_from_device(dc)
                    if code == 200:
                        tok = t; break
                    if isinstance(t, dict) and t.get("error") in ("authorization_pending", "slow_down"):
                        time.sleep(3); continue
                    return json.dumps({"status": "error", "message": f"sign-in failed: {t}"})
                if not tok:
                    return json.dumps({"status": "pending", "message": "Still waiting on sign-in — retry complete_deploy."})
                envs = _discover(tok["access_token"])
                want = pending.get("env")
                env = next((e for e in envs if e["ApiUrl"].rstrip("/").lower() == (want or "").rstrip("/").lower()),
                           envs[0] if envs else None)
                if env is None:
                    return json.dumps({"status": "error", "message": "no Power Platform environments for this account"})
                if want is None and len(envs) > 1:
                    return json.dumps({"status": "choose_environment",
                                       "environments": [{"name": e["FriendlyName"], "url": e["ApiUrl"]} for e in envs],
                                       "message": "Multiple environments — call complete_deploy again with environment_url set."})
                env_token = _refresh(tok["refresh_token"], f"{env['ApiUrl'].rstrip('/')}/user_impersonation")
                _import(env["ApiUrl"], env_token, pending["zip"])
                _CACHE.pop(dc, None)
                return json.dumps({"status": "success",
                                   "environment": env["FriendlyName"], "environment_url": env["ApiUrl"],
                                   "message": f"Deployed to {env['FriendlyName']}. Open https://copilotstudio.microsoft.com/ to use the agent."})

            return json.dumps({"status": "error", "message": f"unknown action '{action}'"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
