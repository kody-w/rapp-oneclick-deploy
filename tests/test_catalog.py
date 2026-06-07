"""Catalog integrity: every 'ready' agent points at a real, valid solution zip."""
import io, json, os, zipfile
from conftest import REPO


def _is_valid_solution(zip_bytes: bytes) -> bool:
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = z.namelist()
    if not ({"solution.xml", "customizations.xml", "[Content_Types].xml"} <= set(names)):
        return False
    sol = z.read("solution.xml").decode("utf-8", "replace")
    return "<UniqueName>" in sol and "<Version>" in sol


def test_catalog_loads():
    with open(os.path.join(REPO, "catalog/agents.json")) as f:
        cat = json.load(f)
    assert cat["agents"], "catalog must list agents"


def test_ready_agents_have_valid_solutions():
    with open(os.path.join(REPO, "catalog/agents.json")) as f:
        cat = json.load(f)
    ready = [a for a in cat["agents"] if a["status"] == "ready"]
    assert ready, "expected at least one ready (prebuilt) agent"
    for a in ready:
        path = os.path.join(REPO, a["solution"])
        assert os.path.isfile(path), f"{a['id']}: missing {a['solution']}"
        with open(path, "rb") as f:
            assert _is_valid_solution(f.read()), f"{a['id']}: invalid solution structure"


def test_convert_agents_have_source():
    with open(os.path.join(REPO, "catalog/agents.json")) as f:
        cat = json.load(f)
    for a in cat["agents"]:
        if a["status"] == "convert":
            assert a.get("source", "").startswith("http"), f"{a['id']}: convert entry needs a source URL"


def test_skeleton_is_valid_solution():
    with open(os.path.join(REPO, "pipeline/skeleton.zip"), "rb") as f:
        assert _is_valid_solution(f.read()), "skeleton must be a valid solution shell"
