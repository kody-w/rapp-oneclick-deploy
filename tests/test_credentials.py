"""Import/export of a local.settings.json service principal + credentialed deploy."""
import json, os, tempfile, pytest
import copilot_deploy_agent as cda

SETTINGS = {
    "IsEncrypted": False,
    "Values": {
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "DYNAMICS_365_CLIENT_ID": "d477eb91-586c-46d2-8729-eca25ea2e7bf",
        "DYNAMICS_365_CLIENT_SECRET": "secret-value",
        "DYNAMICS_365_TENANT_ID": "0b3c5fb8-96dc-4802-b1e3-994d0167ecda",
        "DYNAMICS_365_RESOURCE": "https://kodyD365.crm.dynamics.com",
        "USE_DYNAMICS_STORAGE": "true",
    },
}


def agent():
    return cda.CopilotStudioDeployAgent()


def test_extract_dyn_from_full_settings_and_values_and_string():
    d = cda._extract_dyn(SETTINGS)
    assert d["client_id"].startswith("d477eb91")
    assert d["resource"] == "https://kodyD365.crm.dynamics.com"
    assert cda._extract_dyn(SETTINGS["Values"]) == d        # bare Values dict
    assert cda._extract_dyn(json.dumps(SETTINGS)) == d       # JSON string
    assert cda._extract_dyn({"Values": {}}) is None          # missing keys


def test_action_has_credential_actions():
    enum = agent().to_tool()["function"]["parameters"]["properties"]["action"]["enum"]
    assert {"set_credentials", "credentials_status", "deploy_with_credentials"} <= set(enum)


def test_set_credentials_writes_local_file(monkeypatch, tmp_path):
    path = str(tmp_path / "settings.json")
    monkeypatch.setattr(cda, "SETTINGS_PATH", path)
    r = json.loads(agent().perform(action="set_credentials", credentials=SETTINGS))
    assert r["status"] == "success" and r["resource"].endswith("dynamics.com")
    assert json.load(open(path))["Values"]["DYNAMICS_365_CLIENT_ID"].startswith("d477eb91")


def test_credentials_status(monkeypatch, tmp_path):
    path = str(tmp_path / "settings.json")
    json.dump(SETTINGS, open(path, "w"))
    monkeypatch.setattr(cda, "SETTINGS_PATH", path)
    monkeypatch.setenv("RAPP_DEPLOY_SETTINGS", path)
    r = json.loads(agent().perform(action="credentials_status"))
    assert r["found"] is True and r["client_secret"] == "***"   # never leaks the secret


def test_deploy_with_credentials_uses_service_principal(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: b"SOLUTIONZIP")
    monkeypatch.setattr(cda, "_sp_token",
                        lambda cid, sec, ten, res: "SPTOKEN" if sec == "secret-value" else pytest.fail("bad creds"))
    captured = {}
    monkeypatch.setattr(cda, "_import", lambda env, tok, zb: captured.update(env=env, tok=tok, zip=zb))
    r = json.loads(agent().perform(action="deploy_with_credentials",
                                   solution_url="https://x/sol.zip", credentials=SETTINGS))
    assert r["status"] == "success"
    assert captured["env"] == "https://kodyD365.crm.dynamics.com"
    assert captured["tok"] == "SPTOKEN" and captured["zip"] == b"SOLUTIONZIP"


def test_deploy_with_credentials_errors_without_creds(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: b"Z")
    monkeypatch.setattr(cda, "_load_local_settings", lambda: None)
    r = json.loads(agent().perform(action="deploy_with_credentials", solution_url="https://x/s.zip"))
    assert r["status"] == "error"


def test_dataverse_sends_json_body_not_formencoded(monkeypatch):
    """Regression: the Dataverse Web API needs a JSON body. Form-encoding it caused
    ImportSolution 0x80048d19 'Stream was not readable'."""
    cap = {}
    def fake_req(url, data=None, headers=None, method=None, timeout=300):
        cap["data"] = data; cap["ct"] = (headers or {}).get("Content-Type"); return 204, ""
    monkeypatch.setattr(cda, "_req", fake_req)
    cda._dataverse("https://org.crm.dynamics.com", "tok", "ImportSolution",
                   {"CustomizationFile": "AAA", "ImportJobId": "x", "OverwriteUnmanagedCustomizations": True})
    body = json.loads(cap["data"])                 # must parse as JSON, not a&b=c form string
    assert body["CustomizationFile"] == "AAA" and body["OverwriteUnmanagedCustomizations"] is True
    assert cap["ct"] == "application/json"
