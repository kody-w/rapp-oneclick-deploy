"""The drop-in brainstem agent: loadable + each action behaves (mocked I/O)."""
import io, json, os, zipfile, pytest
import copilot_deploy_agent as cda
from conftest import REPO, CANNED_SPEC

SKELETON = open(os.path.join(REPO, "pipeline/skeleton.zip"), "rb").read()


def agent():
    return cda.CopilotStudioDeployAgent()


def test_agent_is_loadable_tool():
    a = agent()
    assert a.name == "CopilotStudioDeploy"
    tool = a.to_tool()
    assert tool["function"]["name"] == "CopilotStudioDeploy"
    enum = tool["function"]["parameters"]["properties"]["action"]["enum"]
    assert {"list_catalog", "fetch_source", "package", "deploy", "complete_deploy"} <= set(enum)


def test_list_catalog(monkeypatch):
    fake = json.dumps({"agents": [
        {"id": "x", "name": "X", "category": "C", "status": "ready", "solution": "solutions/x.zip"}]}).encode()
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: fake)
    r = json.loads(agent().perform(action="list_catalog"))
    assert r["status"] == "success"
    assert r["agents"][0]["solution_url"].endswith("solutions/x.zip")


def test_fetch_source(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: b"class FooAgent:\n    pass\n")
    r = json.loads(agent().perform(action="fetch_source",
                                   source_url="https://raw.githubusercontent.com/x/y/main/a.py"))
    assert r["status"] == "success" and "FooAgent" in r["source"]


def test_package_builds_valid_solution(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: SKELETON)
    r = json.loads(agent().perform(action="package", agent_name="Account Intelligence",
                                   instructions=CANNED_SPEC["instructions"], unique_name="accountintel"))
    assert r["status"] == "success"
    z = zipfile.ZipFile(io.BytesIO(cda._CACHE[r["package_id"]]))
    names = z.namelist()
    assert "solution.xml" in names and "[Content_Types].xml" in names
    assert not any("dealprogression" in n for n in names)
    assert "<UniqueName>accountintel</UniqueName>" in z.read("solution.xml").decode()
    gpt = z.read("botcomponents/rapp_accountintel.gpt.default/data").decode()
    assert "account intelligence agent" in gpt.lower()


def test_package_requires_instructions(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: SKELETON)
    r = json.loads(agent().perform(action="package", agent_name="X"))
    assert r["status"] == "error"


def test_deploy_then_complete(monkeypatch):
    # deploy: stub device-code start
    monkeypatch.setattr(cda, "_device_start", lambda scope: {
        "device_code": "DEV123", "user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin"})
    r = json.loads(agent().perform(action="deploy", solution_url="https://x/solution.zip"))
    # ... but solution_url fetch happens first; stub it
    # (re-run with _get_bytes stubbed)
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: b"ZIPBYTES")
    r = json.loads(agent().perform(action="deploy", solution_url="https://x/solution.zip"))
    assert r["status"] == "auth_required"
    dc = r["device_code"]
    assert cda._CACHE[dc]["zip"] == b"ZIPBYTES"

    # complete: stub token, discovery, refresh, import
    monkeypatch.setattr(cda, "_token_from_device", lambda d: (200, {"access_token": "disco", "refresh_token": "rt"}))
    monkeypatch.setattr(cda, "_discover", lambda t: [{"ApiUrl": "https://org.crm.dynamics.com", "FriendlyName": "Prod"}])
    monkeypatch.setattr(cda, "_refresh", lambda rt, scope: "envtoken")
    imported = {}
    monkeypatch.setattr(cda, "_import", lambda env, tok, zb: imported.update(env=env, zip=zb))
    r2 = json.loads(agent().perform(action="complete_deploy", device_code=dc))
    assert r2["status"] == "success"
    assert imported["env"] == "https://org.crm.dynamics.com"
    assert imported["zip"] == b"ZIPBYTES"
    assert dc not in cda._CACHE  # consumed


def test_search_templates_default_repo(monkeypatch):
    fake_tree = {"tree": [
        {"type": "blob", "path": "agent_stacks/b2b_sales_stacks/proposal_generation_stack/agents/proposal_generation_agent.py"},
        {"type": "blob", "path": "agent_stacks/b2b_sales_stacks copy 2/x/agents/x_agent.py"},  # 'copy' -> skipped
        {"type": "blob", "path": "README.md"},  # not an agent
    ]}
    monkeypatch.setattr(cda, "_req", lambda url, **k: (200, fake_tree))
    r = json.loads(agent().perform(action="search_templates", query="proposal"))
    assert r["status"] == "success" and r["repo"] == "kody-w/AI-Agent-Templates"
    assert r["count"] == 1
    # multi-word query matches the underscore path (the bug that caused count:0 loops)
    fake = {"tree": [{"type": "blob", "path": "agent_stacks/energy_stacks/emission_tracking_stack/agents/emission_tracking_agent.py"}]}
    monkeypatch.setattr(cda, "_req", lambda url, **k: (200, fake))
    r2 = json.loads(agent().perform(action="search_templates", query="emission tracking"))
    assert r2["count"] == 1, "multi-word query must match underscore paths"
    t = r["templates"][0]
    assert t["name"] == "Proposal Generation" and t["stack"] == "proposal_generation_stack"
    assert t["raw_url"].startswith("https://raw.githubusercontent.com/kody-w/AI-Agent-Templates/main/")


def test_fetch_source_local_file(tmp_path):
    p = tmp_path / "my_agent.py"
    p.write_text("class MyLocalAgent:\n    '''local'''\n    pass\n")
    r = json.loads(agent().perform(action="fetch_source", source_url=str(p)))
    assert r["status"] == "success" and r["origin"] == "local-file"
    assert "MyLocalAgent" in r["source"]


def test_fetch_source_public_url(monkeypatch):
    monkeypatch.setattr(cda, "_get_bytes", lambda url, **k: b"class WebAgent:\n    pass\n")
    r = json.loads(agent().perform(action="fetch_source",
                                   source_url="https://raw.githubusercontent.com/x/y/main/a_agent.py"))
    assert r["status"] == "success" and r["origin"] == "url" and "WebAgent" in r["source"]


def test_fetch_source_missing():
    r = json.loads(agent().perform(action="fetch_source", source_url="/no/such/file_agent.py"))
    assert r["status"] == "error"


def test_unknown_action():
    assert json.loads(agent().perform(action="nope"))["status"] == "error"
