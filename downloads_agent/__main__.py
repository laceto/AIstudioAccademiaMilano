"""CLI: python -m downloads_agent {plan|show|approve|reject|undo}

plan     scan Downloads, build a plan, pause for approval (safe to schedule)
show     print the pending plan
approve  resume the paused graph and move the files
reject   discard the pending plan
undo     move the files of the last approved run back
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from .graph import build_graph, undo_last_run
from .nodes import DEFAULT_MIN_AGE_MIN, DEFAULT_ROOT, default_state_dir


def _print_plan(values: dict) -> None:
    plan = values.get("plan", [])
    for item in plan:
        print(f"  {Path(item['src']).name}  ->  {item['category']}/")
    for s in values.get("skipped", []):
        print(f"  (skip) {s['name']}: {s['reason']}")
    print(f"{len(plan)} file(s) to move.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="downloads_agent", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "show", "approve", "reject", "undo"])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--state-dir", default=str(default_state_dir()))
    ap.add_argument("--min-age-minutes", type=int, default=DEFAULT_MIN_AGE_MIN)
    args = ap.parse_args(argv)

    sd = Path(args.state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    pending_file = sd / "pending.json"

    if args.command == "undo":
        print(f"Restored {undo_last_run(str(sd))} file(s).")
        return 0

    with SqliteSaver.from_conn_string(str(sd / "checkpoints.db")) as saver:
        graph = build_graph(saver)

        if args.command == "plan":
            thread_id = f"run-{int(time.time())}"
            cfg = {"configurable": {"thread_id": thread_id, "root": args.root,
                                    "state_dir": str(sd),
                                    "min_age_minutes": args.min_age_minutes}}
            graph.invoke({}, cfg)  # a new plan replaces any older pending one
            values = graph.get_state(cfg).values
            if graph.get_state(cfg).next:
                pending_file.write_text(json.dumps({"config": cfg}), encoding="utf-8")
            else:
                pending_file.unlink(missing_ok=True)
            _print_plan(values)
            return 0

        if not pending_file.exists():
            print("No pending plan. Run: python -m downloads_agent plan")
            return 1
        cfg = json.loads(pending_file.read_text(encoding="utf-8"))["config"]

        if args.command == "show":
            _print_plan(graph.get_state(cfg).values)
        elif args.command == "approve":
            graph.update_state(cfg, {"decision": "approved"})
            graph.invoke(None, cfg)
            print(f"Moved {len(graph.get_state(cfg).values.get('moved', []))} file(s).")
            pending_file.unlink()
        else:  # reject
            graph.update_state(cfg, {"decision": "rejected"})
            graph.invoke(None, cfg)
            pending_file.unlink()
            print("Plan rejected, nothing moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
