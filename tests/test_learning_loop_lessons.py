"""learning_loop.update_lessons / write_lessons_md: lessons learned from a delivery (044).

Idea taken from Harness² (google-research/harness2): after an execution, write down what was learned as
a structured "experience" entry -- cue (when it applies), lesson (what to do), evidence (what was
observed), confidence -- and carry it to the next tasks instead of keeping only counters.

In the audit log the lessons live under learning_flags.lessons. The loop keeps them in
settings["lessons"], merges repeats of the same lesson, and writes a readable digest for the agents.
"""

import pytest

from scripts import learning_loop as ll


def _lesson(**over):
    entry = {
        "agent": "Gianni",
        "cue": "When a service runs on Azure App Service F1",
        "lesson": "Plan an external cron: F1 has no Always On, so an in-process scheduler sleeps.",
        "evidence": "043: APScheduler never fires after the app idles out on F1.",
        "confidence": "high",
    }
    entry.update(over)
    return entry


def _audit(lessons, request_id="044", intent="x"):
    return {"request_id": request_id, "intent": intent, "learning_flags": {"lessons": lessons}}


def test_a_lesson_is_stored_with_where_it_came_from():
    settings = {}
    assert ll.update_lessons(settings, _audit([_lesson()])) == 1
    (stored,) = settings["lessons"]
    assert stored["cue"] == "When a service runs on Azure App Service F1"
    assert stored["agent"] == "Gianni"
    assert stored["confidence"] == "high"
    assert stored["requests"] == ["044"]
    assert stored["intents"] == ["x"]
    assert stored["seen"] == 1
    assert stored["evidence"] == ["043: APScheduler never fires after the app idles out on F1."]


def test_an_audit_without_lessons_changes_nothing():
    settings = {}
    assert ll.update_lessons(settings, {"request_id": "1", "learning_flags": {}}) == 0
    assert ll.update_lessons(settings, {"request_id": "1"}) == 0
    assert ll.update_lessons(settings, _audit(None)) == 0
    assert settings.get("lessons", []) == []


def test_the_same_lesson_again_is_merged_not_duplicated():
    settings = {}
    ll.update_lessons(settings, _audit([_lesson()], request_id="043"))
    again = _lesson(cue="  when a service runs on azure app service F1 ", evidence="044: same on a second app.")
    assert ll.update_lessons(settings, _audit([again], request_id="044", intent="y")) == 1
    (stored,) = settings["lessons"]
    assert stored["seen"] == 2
    assert stored["requests"] == ["043", "044"]
    assert stored["intents"] == ["x", "y"]
    assert stored["evidence"] == [
        "043: APScheduler never fires after the app idles out on F1.",
        "044: same on a second app.",
    ]


def test_reprocessing_the_same_request_does_not_count_twice():
    settings = {}
    ll.update_lessons(settings, _audit([_lesson()]))
    assert ll.update_lessons(settings, _audit([_lesson()])) == 0
    assert settings["lessons"][0]["seen"] == 1


def test_a_different_agent_or_lesson_is_a_separate_entry():
    settings = {}
    ll.update_lessons(settings, _audit([_lesson(), _lesson(agent="Chiara"), _lesson(lesson="Other.")]))
    assert len(settings["lessons"]) == 3


@pytest.mark.parametrize("missing", ["cue", "lesson", "evidence"])
def test_a_lesson_without_cue_lesson_or_evidence_is_skipped(missing, capsys):
    settings = {}
    bad = _lesson()
    bad[missing] = "  "
    assert ll.update_lessons(settings, _audit([bad, "not a mapping"])) == 0
    assert settings.get("lessons", []) == []
    assert "skipped" in capsys.readouterr().out


def test_confidence_is_normalised_and_unknown_values_become_low():
    settings = {}
    ll.update_lessons(settings, _audit([_lesson(confidence="High"), _lesson(agent="B", confidence="sure")]))
    assert [x["confidence"] for x in settings["lessons"]] == ["high", "low"]


def test_a_missing_agent_means_the_whole_studio():
    settings = {}
    entry = _lesson()
    del entry["agent"]
    ll.update_lessons(settings, _audit([entry]))
    assert settings["lessons"][0]["agent"] == "studio"


def test_confidence_keeps_the_highest_seen():
    settings = {}
    ll.update_lessons(settings, _audit([_lesson(confidence="low")], request_id="1"))
    ll.update_lessons(settings, _audit([_lesson(confidence="high")], request_id="2"))
    ll.update_lessons(settings, _audit([_lesson(confidence="medium")], request_id="3"))
    assert settings["lessons"][0]["confidence"] == "high"


def test_the_digest_groups_by_agent_and_puts_strong_lessons_first(tmp_path):
    settings = {}
    ll.update_lessons(settings, _audit([
        _lesson(agent="Gianni", cue="Cue weak", lesson="Weak.", confidence="low"),
        _lesson(agent="Gianni", cue="Cue strong", lesson="Strong."),
        _lesson(agent="Chiara", cue="Cue chiara", lesson="Tests first."),
    ]))
    out = tmp_path / "lessons.md"
    assert ll.write_lessons_md(settings, out) == 1
    text = out.read_text(encoding="utf-8")
    assert text.index("## Chiara") < text.index("## Gianni")
    assert text.index("Cue strong") < text.index("Cue weak")
    assert "Tests first." in text and "044" in text
    # unchanged content: no rewrite
    assert ll.write_lessons_md(settings, out) == 0


def test_no_lessons_no_digest(tmp_path):
    out = tmp_path / "lessons.md"
    assert ll.write_lessons_md({}, out) == 0
    assert not out.exists()
