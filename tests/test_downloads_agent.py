"""Downloads agent: classification, plan -> approve -> move, undo."""
import os
import time

import pytest
from langgraph.checkpoint.memory import MemorySaver

from downloads_agent.categories import classify
from downloads_agent.graph import build_graph, undo_last_run


def _touch(path, age_min=60):
    path.write_text("x")
    t = time.time() - age_min * 60
    os.utime(path, (t, t))


@pytest.mark.parametrize("name,cat", [
    ("a.PDF", "Documents"), ("b.jpg", "Images"), ("c.exe", "Installers"),
    ("d.zip", "Archives"), ("e.mp4", "Video"), ("f.mp3", "Audio"),
    ("g.xyz", None), ("noext", None),
])
def test_classify(name, cat):
    assert classify(name) == cat


def _run(tmp_path):
    g = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t", "root": str(tmp_path),
                            "state_dir": str(tmp_path / "_state"),
                            "min_age_minutes": 10}}
    return g, cfg


def test_plan_pauses_and_moves_nothing(tmp_path):
    _touch(tmp_path / "a.pdf")
    g, cfg = _run(tmp_path)
    g.invoke({}, cfg)
    assert g.get_state(cfg).next == ("execute",)
    assert (tmp_path / "a.pdf").exists()


def test_skips_recent_partial_unknown_and_dirs(tmp_path):
    _touch(tmp_path / "new.pdf", age_min=1)
    _touch(tmp_path / "x.crdownload")
    _touch(tmp_path / "x.xyz")
    (tmp_path / "folder").mkdir()
    g, cfg = _run(tmp_path)
    g.invoke({}, cfg)
    assert g.get_state(cfg).values["plan"] == []
    assert g.get_state(cfg).next == ()  # nothing to approve -> finished


def test_approve_moves_and_avoids_overwrite(tmp_path):
    _touch(tmp_path / "a.pdf")
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "a.pdf").write_text("old")
    g, cfg = _run(tmp_path)
    g.invoke({}, cfg)
    g.update_state(cfg, {"decision": "approved"})
    g.invoke(None, cfg)
    assert (tmp_path / "Documents" / "a.pdf").read_text() == "old"
    assert (tmp_path / "Documents" / "a (1).pdf").read_text() == "x"
    assert not (tmp_path / "a.pdf").exists()


def test_reject_moves_nothing(tmp_path):
    _touch(tmp_path / "a.pdf")
    g, cfg = _run(tmp_path)
    g.invoke({}, cfg)
    g.update_state(cfg, {"decision": "rejected"})
    g.invoke(None, cfg)
    assert (tmp_path / "a.pdf").exists()


def test_undo_restores(tmp_path):
    _touch(tmp_path / "a.pdf")
    g, cfg = _run(tmp_path)
    g.invoke({}, cfg)
    g.update_state(cfg, {"decision": "approved"})
    g.invoke(None, cfg)
    assert undo_last_run(str(tmp_path / "_state")) == 1
    assert (tmp_path / "a.pdf").exists()


def test_default_root_is_repo_data_download():
    from downloads_agent.nodes import DEFAULT_ROOT
    assert DEFAULT_ROOT.parts[-2:] == ("data", "Download")
