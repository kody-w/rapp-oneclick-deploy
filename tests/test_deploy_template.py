"""The one-shot deploy_template: search -> fetch -> derive -> package -> deploy in ONE call."""
import io, json, zipfile, pytest
import copilot_deploy_agent as cda
from conftest import REPO
import os

SKELETON = open(os.path.join(REPO, "pipeline/skeleton.zip"), "rb").read()
SAMPLE = ('class EmissionTrackingAgent:\n'
          '    """Tracks facility emissions and flags threshold breaches."""\n'
          '    def calculate_footprint(self, site):\n'
          '        """Return the carbon footprint for a site."""\n'
          '    def flag_breaches(self, readings):\n'
          '        """Flag readings above regulatory limits."""\n')


def agent():
    return cda.CopilotStudioDeployAgent()


def test_derive_spec_from_source():
    spec = cda._derive_spec(SAMPLE)
    assert spec["display_name"] == "Emission Tracking"
    assert spec["unique_name"] == "emissiontracking"
    assert "facility emissions" in spec["instructions"]
    assert "Calculate Footprint" in spec["instructions"]   # capabilities derived from methods


def test_deploy_template_one_shot_device_code(monkeypatch):
    # search resolves the name -> one template
    monkeypatch.setattr(cda, "_search_templates",
                        lambda q, repo=cda.TEMPLATES_REPO, limit=60: [{"name": "Emission Tracking",
                        "raw_url": "https://raw.githubusercontent.com/kody-w/AI-Agent-Templates/main/x_agent.py", "stack": "s"}])
    monkeypatch.setattr(cda, "_read_source", lambda ref: SAMPLE)
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: SKELETON)        # skeleton fetch
    monkeypatch.setattr(cda, "_load_local_settings", lambda: None)           # no creds -> device path
    monkeypatch.setattr(cda, "_device_start", lambda scope: {
        "device_code": "DC1", "user_code": "AAAA-BBBB", "verification_uri": "https://microsoft.com/devicelogin"})

    r = json.loads(agent().perform(action="deploy_template", query_or_url="emission tracking"))
    assert r["status"] == "auth_required"
    assert r["user_code"] == "AAAA-BBBB" and r["agent"] == "Emission Tracking"
    # the converted solution was packaged and cached, ready for complete_deploy
    z = zipfile.ZipFile(io.BytesIO(cda._CACHE["DC1"]["zip"]))
    assert "<UniqueName>emissiontracking</UniqueName>" in z.read("solution.xml").decode()
    gpt = z.read("botcomponents/rapp_emissiontracking.gpt.default/data").decode()
    assert "facility emissions" in gpt


def test_deploy_template_autonomous_with_credentials(monkeypatch):
    monkeypatch.setattr(cda, "_read_source", lambda ref: SAMPLE)
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: SKELETON)
    monkeypatch.setattr(cda, "_load_local_settings",
                        lambda: {"client_id": "c", "client_secret": "s", "tenant_id": "t", "resource": "https://org.crm.dynamics.com"})
    monkeypatch.setattr(cda, "_sp_token", lambda *a: "TOK")
    done = {}
    monkeypatch.setattr(cda, "_import", lambda env, tok, zb: done.update(env=env))
    # URL source (no search needed)
    r = json.loads(agent().perform(action="deploy_template",
                                   query_or_url="https://raw.githubusercontent.com/x/y/main/a_agent.py"))
    assert r["status"] == "success" and done["env"] == "https://org.crm.dynamics.com"


def test_deploy_template_no_match(monkeypatch):
    monkeypatch.setattr(cda, "_search_templates", lambda q, **k: [])
    r = json.loads(agent().perform(action="deploy_template", query_or_url="nonexistent-xyz"))
    assert r["status"] == "error"


def test_deploy_template_is_default_action():
    enum = agent().to_tool()["function"]["parameters"]["properties"]["action"]["enum"]
    assert enum[0] == "deploy_template"   # first = the steered default
