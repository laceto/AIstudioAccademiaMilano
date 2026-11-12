"""learning_loop.update_agent_stats: what counts as a success, and a success rate that can recover.

Two defects, both visible in config/global_settings.json:
  * only the exact word `success` counted as a success, but audit logs also say `ok` (50 times), `pass`
    (19) and `completed` (4), so agents that did well showed a low success rate;
  * the rate only ever went down: after the first failure it stayed there whatever came next
    (a failure followed by three successes gave 0.0 instead of 0.75).
"""

import pytest

from scripts import learning_loop as ll


def _run(statuses, intent="x", durations=None):
    settings = {"agents": {}}
    durations = durations or [1] * len(statuses)
    for status, secs in zip(statuses, durations):
        entry = {"name": "A", "duration_sec": secs}
        if status is not ...:
            entry["status"] = status
        ll.update_agent_stats(settings, {"intent": intent, "agents_invoked": [entry]})
    return settings["agents"]["A"]["task_stats"][intent]


@pytest.mark.parametrize("status", ["success", "ok", "pass", "completed", "OK", " Success ", "Pass"])
def test_the_words_audit_logs_use_for_success_count_as_success(status):
    assert _run([status])["success_rate"] == 1.0


@pytest.mark.parametrize(
    "status",
    ["pending", "pending_push", "escalated", "blocked", "blocked_pricing", "fail_then_fixed",
     "in_progress", "passive", "success_voided_to_rd", "failure", "error", "", None],
)
def test_everything_else_is_not_a_success(status):
    assert _run([status])["success_rate"] == 0.0


def test_an_entry_without_a_status_does_not_crash_and_counts_as_not_successful():
    assert _run([...])["success_rate"] == 0.0


def test_the_success_rate_is_a_running_mean_and_can_recover():
    # failure, then three successes: 0/1, 1/2, 2/3, 3/4
    stats = {"agents": {}}
    rates = []
    for status in ["fail", "success", "success", "success"]:
        ll.update_agent_stats(stats, {"intent": "x", "agents_invoked": [{"name": "A", "status": status}]})
        rates.append(stats["agents"]["A"]["task_stats"]["x"]["success_rate"])
    assert rates == [0.0, 0.5, 0.667, 0.75]


def test_a_failure_after_successes_lowers_the_rate_by_the_right_amount():
    assert _run(["ok", "ok", "ok", "blocked"])["success_rate"] == 0.75


def test_all_successes_stay_at_one():
    assert _run(["success", "ok", "pass", "completed", "success"])["success_rate"] == 1.0


def test_count_and_average_duration_are_unchanged():
    stats = _run(["ok", "blocked", "success"], durations=[2, 4, 6])
    assert stats["count"] == 3 and stats["avg_sec"] == 4.0


def test_stats_are_kept_per_intent():
    settings = {"agents": {}}
    ll.update_agent_stats(settings, {"intent": "a", "agents_invoked": [{"name": "A", "status": "ok"}]})
    ll.update_agent_stats(settings, {"intent": "b", "agents_invoked": [{"name": "A", "status": "blocked"}]})
    stats = settings["agents"]["A"]["task_stats"]
    assert stats["a"]["success_rate"] == 1.0 and stats["b"]["success_rate"] == 0.0
