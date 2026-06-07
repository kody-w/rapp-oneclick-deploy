"""agent.py deploy engine: ImportSolution payload + environment selection (mocked HTTP)."""
import base64, json, importlib
import agent


def test_pick_environment_single():
    envs = [{"ApiUrl": "https://org.crm.dynamics.com", "FriendlyName": "Prod"}]
    assert agent.pick_environment(envs, None)["ApiUrl"] == "https://org.crm.dynamics.com"


def test_pick_environment_matches_wanted():
    envs = [{"ApiUrl": "https://a.crm.dynamics.com", "FriendlyName": "A"},
            {"ApiUrl": "https://b.crm.dynamics.com", "FriendlyName": "B"}]
    got = agent.pick_environment(envs, "https://b.crm.dynamics.com/")
    assert got["FriendlyName"] == "B"


def test_import_solution_builds_correct_payload(monkeypatch):
    seen = {}
    def fake_api(env, token, action, body=None, method="POST", timeout=600):
        seen.setdefault("calls", []).append((action, body, method))
        if action == "ImportSolution":
            return 204, ""
        if action.startswith("importjobs"):
            return 200, {"solutionname": "x", "progress": "100"}
        return 200, {}
    monkeypatch.setattr(agent, "api", fake_api)

    agent.import_solution("https://org.crm.dynamics.com", "tok", b"PKZIPBYTES")

    actions = [c[0] for c in seen["calls"]]
    assert "ImportSolution" in actions
    assert any(a == "PublishAllXml" for a in actions), "must publish customizations"

    imp_body = next(c[1] for c in seen["calls"] if c[0] == "ImportSolution")
    assert imp_body["OverwriteUnmanagedCustomizations"] is True
    assert imp_body["PublishWorkflows"] is True
    assert "ImportJobId" in imp_body
    # CustomizationFile must be valid base64 of the zip bytes
    assert base64.b64decode(imp_body["CustomizationFile"]) == b"PKZIPBYTES"
