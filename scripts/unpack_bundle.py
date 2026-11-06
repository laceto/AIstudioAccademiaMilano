"""Unpack a deliverable bundle built by Chiara's Claude Code engine (050) into a folder.

    python -m scripts.unpack_bundle chatbot_app_bundle.txt ./chatbot_app

The bundle is one text file: a commented header, then for each file a line
`===== FILE: <path> =====` followed by its text, and `===== END OF BUNDLE =====` at the end.
The target folder must be new or empty; paths that would land outside it are refused.
Standard library only, so it runs anywhere Python does.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path, PurePosixPath

_MARKER = re.compile(r"^===== FILE: (.+) =====$")
_END = "===== END OF BUNDLE ====="


class UnsafeBundle(ValueError):
    """The bundle or the target folder would make unpacking unsafe."""


def parse_bundle(text: str) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    current, lines = None, []
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        match = _MARKER.match(stripped)
        if match or stripped == _END:
            if current is not None:
                files.append((current, "".join(lines)))
            current, lines = (match.group(1) if match else None), []
            if not match:
                break
        elif current is not None:
            lines.append(line)
    if current is not None:  # no end marker: keep what was there
        files.append((current, "".join(lines)))
    return files


def _safe_rel(rel: str) -> PurePosixPath:
    p = PurePosixPath(rel)
    if (not rel or "\\" in rel or p.is_absolute() or re.match(r"^[A-Za-z]:", rel)
            or any(part in ("..", "") for part in p.parts)):
        raise UnsafeBundle(f"unsafe path in bundle: {rel!r}")
    return p


def unpack(text: str, target) -> list[str]:
    target = Path(target)
    files = parse_bundle(text)
    rels = [_safe_rel(rel) for rel, _ in files]  # check them all before writing anything
    if target.exists() and any(target.iterdir()):
        raise UnsafeBundle(f"{target} is not empty")
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    for rel, (_, content) in zip(rels, files):
        dest = (root / rel).resolve()
        if not dest.is_relative_to(root):
            raise UnsafeBundle(f"unsafe path in bundle: {rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="")
    return [str(r) for r in rels]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle", type=Path)
    ap.add_argument("target", type=Path)
    a = ap.parse_args(argv)
    try:
        written = unpack(a.bundle.read_text(encoding="utf-8"), a.target)
    except UnsafeBundle as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    print(f"{len(written)} files written to {a.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
