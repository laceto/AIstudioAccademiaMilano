"""scripts/unpack_bundle.py turns Chiara's text bundle (050) back into files, safely."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.unpack_bundle import UnsafeBundle, parse_bundle, unpack

ROOT = Path(__file__).resolve().parent.parent

BUNDLE = """# Deliverable bundle - built by Claude Code (Chiara)
# Files: 2

===== FILE: README.md =====
# Hello
===== FILE: src/app.py =====
print("hi")

x = 1
===== END OF BUNDLE =====
"""


def test_parse_returns_each_file_with_its_exact_text():
    files = dict(parse_bundle(BUNDLE))
    assert files == {"README.md": "# Hello\n", "src/app.py": 'print("hi")\n\nx = 1\n'}


def test_unpack_writes_the_files(tmp_path):
    written = unpack(BUNDLE, tmp_path / "out")
    assert (tmp_path / "out" / "src" / "app.py").read_text() == 'print("hi")\n\nx = 1\n'
    assert sorted(written) == ["README.md", "src/app.py"]


@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", "a/../../b.py", "C:/win.py", "..\\x.py"])
def test_unpack_refuses_paths_that_leave_the_folder(tmp_path, bad):
    with pytest.raises(UnsafeBundle):
        unpack(f"===== FILE: {bad} =====\nboom\n===== END OF BUNDLE =====\n", tmp_path / "out")
    assert not (tmp_path / "escape.py").exists()


def test_unpack_refuses_a_non_empty_target(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    with pytest.raises(UnsafeBundle):
        unpack(BUNDLE, out)
    assert (out / "keep.txt").read_text() == "mine"


def test_cli(tmp_path):
    src = tmp_path / "chatbot_app_bundle.txt"
    src.write_text(BUNDLE)
    res = subprocess.run([sys.executable, "-m", "scripts.unpack_bundle", str(src), str(tmp_path / "o")],
                         cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert (tmp_path / "o" / "README.md").exists() and "2 files" in res.stdout


def test_round_trip_with_a_bundle_built_by_the_engine(tmp_path):
    from gateway.studio_runner import load_pipeline

    cc = load_pipeline().nodes._cc
    files = [("README.md", "# Bot\n"), ("app.py", "x = 1\n\n\n"), ("tests/test_app.py", "def test():\n    pass")]
    bundle = cc._bundle("chatbot_app", files, [("logo.png", "binary")], "passed (1 passed)", 0.1)
    unpack(bundle, tmp_path / "o")
    assert (tmp_path / "o" / "app.py").read_text() == "x = 1\n\n\n"
    assert (tmp_path / "o" / "tests" / "test_app.py").read_text() == "def test():\n    pass\n"  # newline added
    assert not (tmp_path / "o" / "logo.png").exists()
