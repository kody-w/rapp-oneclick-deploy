#!/usr/bin/env python3
"""
RAPP one-click Copilot Studio deployer (agent.py)
=================================================
Imports a Power Platform / Copilot Studio solution (.zip) into the user's OWN
environment. Two auth modes:

  * device-code  (default) — interactive, zero secrets, zero app registration.
                  You sign in once in the browser; the agent then discovers your
                  environments and imports the solution autonomously.
  * service-principal       — unattended (CI). Provide --client-id/--client-secret
                  /--tenant and --environment.

Dependencies: Python 3.8+ standard library only (urllib). No pip install required.

Usage:
  python3 agent.py                          # device-code, auto-discover env, bundled solution
  python3 agent.py --environment https://org.crm.dynamics.com
  python3 agent.py --solution ./my_solution.zip
  python3 agent.py --service-principal --client-id .. --client-secret .. \
                   --tenant .. --environment https://org.crm.dynamics.com
"""
import argparse, base64, json, os, sys, time, urllib.request, urllib.parse, uuid

# Public client used for interactive device-code sign-in (Power Platform CLI's
# well-known public client). Override with --client-id or $RAPP_CLIENT_ID, e.g.
# to use your own registered multi-tenant public client in production.
DEFAULT_PUBLIC_CLIENT = "9cee029c-6210-4654-90bb-17e6e9d36617"
# Default solution shipped with this repo (raw GitHub URL), overridable.
DEFAULT_SOLUTION_URL = ("https://raw.githubusercontent.com/kody-w/rapp-oneclick-deploy/"
                        "main/solution/dealprogression_solution.zip")
DISCO = "https://globaldisco.crm.dynamics.com"
AUTH = "https://login.microsoftonline.com"

C = {"b": "\033[1m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "c": "\033[36m", "x": "\033[0m"}
def say(msg, k="x"): print(f"{C.get(k,'')}{msg}{C['x']}", flush=True)
def die(msg): say("✗ " + msg, "r"); sys.exit(1)


# ---------------------------------------------------------------- HTTP helpers
def _req(url, data=None, headers=None, method=None, timeout=600):
    if isinstance(data, dict):  # form-encode
        data = urllib.parse.urlencode(data).encode()
    elif isinstance(data, (bytes, bytearray)) or data is None:
        pass
    else:  # json
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8") or "{}"
            return r.status, (json.loads(body) if body.strip().startswith(("{", "[")) else body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try: body = json.loads(body)
        except Exception: pass
        return e.code, body


# ---------------------------------------------------------------- auth
def device_login(client_id, tenant, scope):
    code, r = _req(f"{AUTH}/{tenant}/oauth2/v2.0/devicecode",
                   data={"client_id": client_id, "scope": scope},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200 or "device_code" not in r:
        die(f"Could not start device login: {r}")
    say("\n  ┌─────────────────────────────────────────────────────────────┐")
    say(f"  │  1. Open:  {C['c']}{r['verification_uri']}{C['x']}")
    say(f"  │  2. Enter code:  {C['b']}{r['user_code']}{C['x']}")
    say("  │  3. Sign in with your Copilot Studio / Power Platform account  │")
    say("  └─────────────────────────────────────────────────────────────┘\n")
    say("  Waiting for sign-in…", "y")
    interval, deadline = int(r.get("interval", 5)), time.time() + int(r.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(interval)
        code, t = _req(f"{AUTH}/{tenant}/oauth2/v2.0/token",
                       data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                             "client_id": client_id, "device_code": r["device_code"]},
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
        if code == 200:
            say("  ✓ Signed in\n", "g"); return t
        if isinstance(t, dict) and t.get("error") == "authorization_pending":
            continue
        if isinstance(t, dict) and t.get("error") == "slow_down":
            interval += 5; continue
        die(f"Sign-in failed: {t.get('error_description', t) if isinstance(t,dict) else t}")
    die("Sign-in timed out.")


def refresh_for(refresh_token, client_id, tenant, scope):
    code, t = _req(f"{AUTH}/{tenant}/oauth2/v2.0/token",
                   data={"grant_type": "refresh_token", "refresh_token": refresh_token,
                         "client_id": client_id, "scope": scope},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200 or "access_token" not in t:
        die(f"Token exchange failed: {t}")
    return t


def sp_token(client_id, client_secret, tenant, resource):
    code, t = _req(f"{AUTH}/{tenant}/oauth2/v2.0/token",
                   data={"grant_type": "client_credentials", "client_id": client_id,
                         "client_secret": client_secret, "scope": resource.rstrip('/') + "/.default"},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    if code != 200 or "access_token" not in t:
        die(f"Service-principal auth failed: {t}")
    return t["access_token"]


# ---------------------------------------------------------------- discovery
def discover(disco_token):
    code, r = _req(f"{DISCO}/api/discovery/v2.0/Instances",
                   headers={"Authorization": "Bearer " + disco_token, "Accept": "application/json"})
    if code != 200:
        die(f"Environment discovery failed: {r}")
    return r.get("value", [])


def pick_environment(envs, wanted):
    if wanted:
        w = wanted.rstrip("/").lower()
        for e in envs:
            if (e.get("ApiUrl", "").rstrip("/").lower() == w or e.get("Url", "").rstrip("/").lower() == w):
                return e
        die(f"Environment '{wanted}' not found in your accessible environments.")
    if not envs:
        die("No Power Platform environments found for this account.")
    if len(envs) == 1:
        return envs[0]
    say("Select the target environment:", "b")
    for i, e in enumerate(envs, 1):
        say(f"  {i}. {e.get('FriendlyName','?')}   {C['c']}{e.get('ApiUrl','')}{C['x']}")
    while True:
        try:
            n = int(input("  Number: ").strip())
            if 1 <= n <= len(envs): return envs[n - 1]
        except (ValueError, EOFError):
            die("No selection made.")


# ---------------------------------------------------------------- solution load + import
def load_solution(src):
    if src.startswith(("http://", "https://")):
        say(f"  Downloading solution: {src}")
        code, _ = (200, None)
        req = urllib.request.Request(src, headers={"User-Agent": "rapp-agent"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    if not os.path.isfile(src):
        die(f"Solution file not found: {src}")
    with open(src, "rb") as f:
        return f.read()


def convert_source(source, brainstem):
    """Convert a RAPP agent.py (raw URL or path) into a Copilot Studio solution by
    running convert.py, whose required LLM steps route through the RAPP brainstem
    (the brainstem's model flipper picks the model). Returns solution zip bytes."""
    try:
        import convert
    except ImportError:
        die("convert.py / brainstem_llm.py not found next to agent.py — needed for --source.")
    say(f"  🧠 Converting via the RAPP brainstem: {C['c']}{source}{C['x']}")
    try:
        zip_bytes = convert.convert(source, brainstem_url=brainstem)
    except Exception as e:
        die(f"Conversion failed: {e}")
    say("  ✓ Brainstem authored the agent and packaged the solution", "g")
    return zip_bytes


def api(env, token, action, body=None, method="POST", timeout=600):
    url = f"{env.rstrip('/')}/api/data/v9.2/{action}"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
               "Accept": "application/json", "OData-MaxVersion": "4.0", "OData-Version": "4.0"}
    return _req(url, data=body if body is not None else None, headers=headers, method=method, timeout=timeout)


def import_solution(env, token, zip_bytes):
    import_job_id = str(uuid.uuid4())
    say(f"  Importing solution into {C['c']}{env}{C['x']} …", "y")
    code, r = api(env, token, "ImportSolution", {
        "OverwriteUnmanagedCustomizations": True,
        "PublishWorkflows": True,
        "ImportJobId": import_job_id,
        "CustomizationFile": base64.b64encode(zip_bytes).decode(),
    })
    if code not in (200, 204):
        die(f"Import failed (HTTP {code}): {r}")
    # best-effort: read import job result
    jc, jr = api(env, token, f"importjobs({import_job_id})?$select=solutionname,progress", method="GET")
    if jc == 200 and isinstance(jr, dict):
        say(f"  ✓ Imported '{jr.get('solutionname','solution')}' (progress {jr.get('progress','100')}%)", "g")
    else:
        say("  ✓ Solution imported", "g")
    # publish customizations (needed for unmanaged solutions)
    pc, _ = api(env, token, "PublishAllXml")
    say("  ✓ Published customizations" if pc in (200, 204) else "  • Publish step skipped", "g")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="One-click Copilot Studio solution deployer")
    ap.add_argument("--solution", default=os.environ.get("RAPP_SOLUTION_URL", DEFAULT_SOLUTION_URL),
                    help="Path or URL to the solution .zip (defaults to the bundled RAPP solution)")
    ap.add_argument("--environment", default=os.environ.get("RAPP_ENVIRONMENT"),
                    help="Target environment URL e.g. https://org.crm.dynamics.com (else auto/prompt)")
    ap.add_argument("--client-id", default=os.environ.get("RAPP_CLIENT_ID", DEFAULT_PUBLIC_CLIENT))
    ap.add_argument("--tenant", default=os.environ.get("RAPP_TENANT", "organizations"))
    ap.add_argument("--service-principal", action="store_true", help="Unattended client-credentials auth")
    ap.add_argument("--client-secret", default=os.environ.get("RAPP_CLIENT_SECRET"))
    ap.add_argument("--source", default=os.environ.get("RAPP_SOURCE"),
                    help="Raw agent.py URL or AI-Agent-Templates stack to convert via the RAPP brainstem")
    ap.add_argument("--brainstem", default=os.environ.get("RAPP_BRAINSTEM", "http://localhost:7071"),
                    help="RAPP brainstem base URL (drives conversion + Copilot-model LLM steps)")
    args = ap.parse_args()

    say(f"\n{C['b']}🚀 RAPP → Copilot Studio one-click deploy{C['x']}")
    zip_bytes = convert_source(args.source, args.brainstem) if args.source else load_solution(args.solution)
    say(f"  Solution ready ({len(zip_bytes):,} bytes)\n")

    if args.service_principal:
        if not (args.client_secret and args.environment):
            die("--service-principal requires --client-secret and --environment")
        token = sp_token(args.client_id, args.client_secret, args.tenant, args.environment)
        import_solution(args.environment, token, zip_bytes)
    else:
        first = device_login(args.client_id, args.tenant,
                             f"{DISCO}/user_impersonation offline_access")
        if "refresh_token" not in first:
            die("No refresh token returned; cannot acquire environment token.")
        envs = discover(first["access_token"])
        env = pick_environment(envs, args.environment)
        api_url = env.get("ApiUrl") or env.get("Url")
        say(f"  Target: {C['b']}{env.get('FriendlyName','')}{C['x']}  {api_url}")
        env_tok = refresh_for(first["refresh_token"], args.client_id, args.tenant,
                              f"{api_url.rstrip('/')}/user_impersonation")
        import_solution(api_url, env_tok["access_token"], zip_bytes)
        say(f"\n{C['g']}{C['b']}✅ Done.{C['x']} Open Copilot Studio to find your new agent:")
        say(f"   {C['c']}https://copilotstudio.microsoft.com/{C['x']}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        die("Cancelled.")
