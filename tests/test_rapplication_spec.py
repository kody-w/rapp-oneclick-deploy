"""Spec compliance for the copilot_studio_deploy rapplication."""
import ast, hashlib, json, os, re, zipfile

import pytest
from conftest import REPO

APP = os.path.join(REPO, "apps", "@kody-w", "copilot_studio_deploy")
EGG = os.path.join(REPO, "api/v1/egg/copilot_studio_deploy.egg")
SING = os.path.join(APP, "singleton", "copilot_studio_deploy_agent.py")
UI = os.path.join(APP, "ui", "index.html")

LOCKED_CATEGORIES = {"productivity", "creative", "analysis", "data", "integration", "platform", "workspace"}
RESERVED = {"binder", "dashboard", "kanban", "swarms", "webhook", "vibe_builder",
            "learn_new", "swarm_factory", "senses", "publish_to_rapp_store", "scripts", "tests", "versions", "eggs"}
# Eternity envelope: rappid:@owner/slug:<hex>. Hash is 64-hex (fresh mint) or
# 32-hex (grandfathered legacy, preserved per SPEC §2) — never re-versioned.
ETERNITY = re.compile(r"^rappid:@[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*:(?:[a-f0-9]{32}|[a-f0-9]{64})$")


def test_store_manifest_rapp_application_1_0():
    m = json.load(open(os.path.join(APP, "manifest.json")))
    assert m["schema"] == "rapp-application/1.0"
    for k in ("id", "name", "version", "publisher", "summary", "category", "tags", "agent", "ui"):
        assert k in m, f"missing required field {k}"
    assert re.match(r"^[a-z][a-z0-9_]*$", m["id"]) and m["id"] not in RESERVED
    assert re.match(r"^\d+\.\d+\.\d+$", m["version"])
    assert m["publisher"].startswith("@")
    assert m["category"] in LOCKED_CATEGORIES
    assert "rapplication" in m["tags"]
    assert os.path.isfile(os.path.join(APP, m["agent"]))   # both agent AND ui present
    assert os.path.isfile(os.path.join(APP, m["ui"]))


def test_singleton_ast_contract():
    src = open(SING).read()
    t = ast.parse(src)
    agent_classes = [n for n in t.body if isinstance(n, ast.ClassDef)
                     and n.name.endswith("Agent") and n.name != "BasicAgent"]
    assert len(agent_classes) == 1
    cls = agent_classes[0]
    assert any(getattr(b, "id", None) == "BasicAgent" for b in cls.bases)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "perform" for n in cls.body)
    man = next((n for n in t.body if isinstance(n, ast.Assign)
                and any(getattr(tg, "id", None) == "__manifest__" for tg in n.targets)), None)
    assert man is not None
    md = ast.literal_eval(man.value)
    assert md["schema"] == "rapp-agent/1.0"
    assert {"name", "version", "description"} <= set(md)
    assert "import BasicAgent" in src
    assert not re.search(r"\{\{PLACEHOLDER\}\}|YOUR LOGIC|TODO REPLACE|RAPP AGENT TEMPLATE", src)
    # no embedded secret literal
    assert not re.search(r"client_secret\s*=\s*[\"'][A-Za-z0-9~._-]{20,}[\"']", src)


def test_size_caps():
    assert os.path.getsize(SING) < 200_000, "singleton must be < 200 KB"
    assert os.path.getsize(UI) < 500_000, "UI must be < 500 KB"
    assert os.path.getsize(EGG) < 5_000_000, "bundle must be < 5 MB"


def _hb(space: str, data: bytes) -> str:
    return hashlib.sha256(space.encode() + b"\n" + data).hexdigest()


def test_egg_is_strict_rapp_1_rapplication():
    with zipfile.ZipFile(EGG) as z:
        infos = z.infolist()
        names = [info.filename for info in infos]
        assert names[0] == "manifest.json"
        assert all(info.compress_type == zipfile.ZIP_STORED for info in infos)
        assert all(info.flag_bits == 0x800 for info in infos)
        manifest_bytes = z.read("manifest.json")
        manifest = json.loads(manifest_bytes)
        assert set(manifest) == {
            "schema", "variant", "rappid", "created_utc",
            "contents", "payload", "sig",
        }
        assert manifest["schema"] == "rapp/1-egg"
        assert manifest["variant"] == "rapplication"
        assert manifest["sig"] is None
        assert manifest["rappid"] == json.loads(z.read("rappid.json"))["rappid"]
        contents = manifest["contents"]
        paths = [item["path"] for item in contents]
        assert paths == sorted(paths, key=lambda value: value.encode("utf-8"))
        assert paths == [
            "agent.py",
            "rapp_ui/copilot_studio_deploy/index.html",
            "rappid.json",
        ]
        assert set(names) == {"manifest.json", *paths}
        for item in contents:
            assert set(item) == {"path", "hash"}
            assert item["hash"] == _hb("rapp/1:egg", z.read(item["path"]))


def test_eternity_rappid_in_record_and_egg():
    rj = json.load(open(os.path.join(APP, "rappid.json")))
    assert rj["schema"] == "rapp/1"
    assert ETERNITY.match(rj["rappid"]), f"not Eternity form: {rj['rappid']}"
    assert rj["kind"] == "rapplication"                       # kind in the record, not the string
    assert "v2:" not in rj["rappid"] and "@github.com" not in rj["rappid"]
    assert ETERNITY.match(rj["parent_rappid"])                # parent also Eternity


@pytest.mark.xfail(
    strict=True,
    reason="identity divergence awaiting the owner's decision: "
           "https://github.com/kody-w/rapp-oneclick-deploy/issues/5",
)
def test_egg_rappid_matches_app_record():
    rj = json.load(open(os.path.join(APP, "rappid.json")))
    with zipfile.ZipFile(EGG) as z:
        egg_rj = json.loads(z.read("rappid.json"))
    assert egg_rj["rappid"] == rj["rappid"]


def test_pokedex_and_index():
    p = json.load(open(os.path.join(REPO, "api/v1/rapplication/copilot_studio_deploy.json")))
    assert p["schema"] == "rapp-pokedex-rapp/1.0" and p["kind"] == "rapplication"
    assert p["egg_url"].endswith("copilot_studio_deploy.egg")
    assert ETERNITY.match(p["rappid"])
    idx = json.load(open(os.path.join(REPO, "api/v1/index.json")))
    assert idx["schema"] == "rapp-pokedex-api/1.0"
    assert any(r["id"] == "copilot_studio_deploy" for r in idx["rapplications"])
