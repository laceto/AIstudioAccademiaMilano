"""049: the GitHub research Scout also looks at github.com/trending (offline, no network)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

FOLDER = str(Path(__file__).resolve().parent.parent / "scripts" / "github_research")
if FOLDER not in sys.path:
    sys.path.insert(0, FOLDER)

import evaluate_repo  # noqa: E402
import report  # noqa: E402
import search_repos  # noqa: E402
import trending  # noqa: E402

NOW = datetime.now(timezone.utc)


def _article(owner, name, desc, lang="Python", stars="12,345", forks="1,234", gained="2,345 stars this week"):
    lang_html = (f'<span class="d-inline-block ml-0 mr-3"><span class="repo-language-color"></span>'
                 f'<span itemprop="programmingLanguage">{lang}</span></span>') if lang else ""
    desc_html = f'<p class="col-9 color-fg-muted my-1 pr-4">\n      {desc}\n    </p>' if desc is not None else ""
    return f"""
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a data-view-component="true" class="Link" href="/{owner}/{name}">
      <svg aria-hidden="true"></svg>
      <span data-view-component="true" class="text-normal">
        {owner} /
</span>
      {name}
</a>  </h2>
  {desc_html}
  <div class="f6 color-fg-muted mt-2">
    {lang_html}
    <a href="/{owner}/{name}/stargazers" class="Link Link--muted d-inline-block mr-3">
      <svg aria-label="star" class="octicon octicon-star"></svg>
      {stars}
</a>
    <a href="/{owner}/{name}/forks" class="Link Link--muted d-inline-block mr-3">
      <svg aria-label="fork" class="octicon octicon-repo-forked"></svg>
      {forks}
</a>
    <span class="d-inline-block float-sm-right">
      <svg class="octicon octicon-star"></svg>
      {gained}
    </span>
  </div>
</article>"""


PAGE = "<html><body>" + "".join([
    _article("acme", "agent-kit", "Build LLM agents in &amp; out of the box"),
    _article("someone", "css-grid-tricks", "Tricks for CSS grid layouts", lang="CSS", gained="900 stars this week"),
    _article("lab", "tiny-rag", "Retrieval-augmented generation in 200 lines", lang=None, stars="845",
             forks="12", gained="512 stars this week"),
    _article("nobody", "dotfiles", None, lang="Shell", gained="40 stars this week"),
]) + "</body></html>"


# ── parsing the trending page ────────────────────────────────────────────────


def test_the_trending_page_is_parsed_into_rows():
    rows = trending.parse_trending(PAGE)
    assert [r["full_name"] for r in rows] == ["acme/agent-kit", "someone/css-grid-tricks", "lab/tiny-rag", "nobody/dotfiles"]
    first = rows[0]
    assert first["description"] == "Build LLM agents in & out of the box"
    assert (first["language"], first["stars"], first["forks"], first["stars_gained"]) == ("Python", 12345, 1234, 2345)
    assert rows[2]["language"] == "" and rows[2]["stars"] == 845
    assert rows[3]["description"] == ""


def test_a_page_without_repos_or_with_junk_is_an_empty_list():
    assert trending.parse_trending("") == []
    assert trending.parse_trending("<article class='Box-row'><h2>no link</h2></article>") == []


def test_only_ai_repos_are_kept():
    rows = trending.parse_trending(PAGE)
    assert [r["full_name"] for r in rows if trending.looks_ai(r)] == ["acme/agent-kit", "lab/tiny-rag"]


@pytest.mark.parametrize("text,ai", [
    ("An MCP server for Postgres", True),
    ("Fine-tuning Llama with LoRA", True),
    ("Claude Code skills", True),
    ("A raid planner for World of Warcraft", False),   # 'raid' is not 'rag', 'ai' only as a word
    ("Maintain your dotfiles", False),
])
def test_the_ai_keyword_filter(text, ai):
    assert trending.looks_ai({"full_name": "x/y", "description": text}) is ai


# ── fetching (with fakes) ────────────────────────────────────────────────────


class _Resp:
    def __init__(self, status=200, text="", payload=None):
        self.status_code, self.text, self._payload = status, text, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _api_repo(full_name, **extra):
    base = {
        "name": full_name.split("/")[1], "full_name": full_name, "description": "from the API",
        "stargazers_count": 13000, "forks_count": 1300, "language": "Python", "topics": ["llm", "ai-agents"],
        "html_url": f"https://github.com/{full_name}", "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-11-04T00:00:00Z", "pushed_at": "2026-11-04T00:00:00Z",
    }
    base.update(extra)
    return base


def _fake_get(calls, page=PAGE, api_fail=()):
    def get(url, headers=None, params=None, timeout=None):
        calls.append((url, params, headers))
        if url.startswith("https://github.com/trending"):
            return _Resp(text=page)
        full_name = url.split("/repos/")[1]
        if full_name in api_fail:
            return _Resp(status=404)
        return _Resp(payload=_api_repo(full_name))
    return get


def test_fetch_trending_returns_enriched_ai_repos_marked_as_trending():
    calls = []
    repos = trending.fetch_trending(since="weekly", token="t0k", get=_fake_get(calls))
    assert [r.full_name for r in repos] == ["acme/agent-kit", "lab/tiny-rag"]
    r = repos[0]
    assert r.topics == ["llm", "ai-agents"] and r.created_at == "2026-10-01T00:00:00Z"
    assert (r.trending_stars, r.trending_since) == (2345, "weekly")
    page_call = calls[0]
    assert page_call[0] == "https://github.com/trending" and page_call[1] == {"since": "weekly"}
    assert "Authorization" not in page_call[2]                  # the token never goes to the HTML page
    assert calls[1][2]["Authorization"] == "Bearer t0k"         # only to the API
    assert len(calls) == 3                                       # non-AI rows are not enriched


def test_a_language_page_is_asked_by_path():
    calls = []
    trending.fetch_trending(since="daily", language="python", get=_fake_get(calls))
    assert calls[0][0] == "https://github.com/trending/python" and calls[0][1] == {"since": "daily"}


def test_a_repo_the_api_cannot_describe_keeps_the_page_data():
    repos = trending.fetch_trending(get=_fake_get([], api_fail={"lab/tiny-rag"}))
    tiny = [r for r in repos if r.full_name == "lab/tiny-rag"][0]
    assert tiny.stars == 845 and tiny.trending_stars == 512 and tiny.topics == []


def test_a_trending_page_that_fails_is_an_empty_list_not_an_error():
    def get(url, **kw):
        raise ConnectionError("blocked")
    assert trending.fetch_trending(get=get) == []


def test_an_unknown_period_is_refused():
    with pytest.raises(ValueError):
        trending.fetch_trending(since="yearly", get=_fake_get([]))


# ── wired into the Scout ─────────────────────────────────────────────────────


def _repo(full_name, **kw):
    fields = dict(name=full_name.split("/")[1], full_name=full_name, description="", stars=1000, forks=100,
                  language="Python", topics=["llm"], url="u", created_at="2026-01-01T00:00:00Z",
                  updated_at="2026-11-01T00:00:00Z", pushed_at="2026-11-01T00:00:00Z")
    fields.update(kw)
    return search_repos.Repo(**fields)


def test_search_all_topics_adds_a_trending_bucket_and_marks_topic_hits(monkeypatch):
    monkeypatch.setattr(search_repos, "search_repos",
                        lambda topic, **kw: [_repo("acme/agent-kit"), _repo("old/classic")])
    seen = {}

    def fake_trending(since, token=None, **kw):
        seen["since"] = since
        return [_repo("acme/agent-kit", trending_stars=2345, trending_since=since)]

    monkeypatch.setattr(trending, "fetch_trending", fake_trending)
    out = search_repos.search_all_topics(topics=["llm"], token="t", delay=0, trending="weekly")
    assert seen["since"] == "weekly"
    assert [r.full_name for r in out["trending"]] == ["acme/agent-kit"]
    marked = {r.full_name: r.trending_stars for r in out["llm"]}
    assert marked == {"acme/agent-kit": 2345, "old/classic": 0}


def test_trending_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(search_repos, "search_repos", lambda topic, **kw: [])
    monkeypatch.setattr(trending, "fetch_trending", lambda *a, **k: pytest.fail("must not be called"))
    out = search_repos.search_all_topics(topics=["llm"], delay=0, trending=None)
    assert "trending" not in out


def test_a_failing_trending_fetch_does_not_stop_the_topic_search(monkeypatch):
    monkeypatch.setattr(search_repos, "search_repos", lambda topic, **kw: [_repo("a/b")])

    def boom(*a, **k):
        raise RuntimeError("parser broke")

    monkeypatch.setattr(trending, "fetch_trending", boom)
    out = search_repos.search_all_topics(topics=["llm"], delay=0, trending="weekly")
    assert [r.full_name for r in out["llm"]] == ["a/b"] and out["trending"] == []


# ── Analyst and Curator ──────────────────────────────────────────────────────


def test_recent_stars_lift_the_growth_signal_of_an_old_repo():
    created = (NOW - timedelta(days=2000)).isoformat()
    quiet = evaluate_repo.score_repo(_repo("x/old", stars=5000, created_at=created))
    hot = evaluate_repo.score_repo(_repo("x/old", stars=5000, created_at=created, trending_stars=1400,
                                         trending_since="weekly"))
    assert hot.signals["growth"] > quiet.signals["growth"]
    assert hot.score > quiet.score


def test_the_curator_keeps_the_trending_mark_and_files_by_topic():
    plain = evaluate_repo.score_repo(_repo("acme/agent-kit", topics=["ai-agents"]))
    hot = evaluate_repo.score_repo(_repo("acme/agent-kit", topics=["ai-agents"], trending_stars=50,
                                         trending_since="weekly"))
    categorised = report.deduplicate({"ai-agents": [plain], "trending": [hot]})
    [rs] = categorised["Agentic Systems"]
    assert rs.repo.trending_stars == 50


def test_the_report_has_a_trending_section():
    hot = evaluate_repo.score_repo(_repo("acme/agent-kit", trending_stars=2345, trending_since="weekly"))
    cold = evaluate_repo.score_repo(_repo("old/classic"))
    text = report.generate_report(report.deduplicate({"llm": [hot, cold]}))
    section = text.split("## Trending on GitHub")[1].split("\n## ")[0]
    assert "acme/agent-kit" in section and "+2,345 stars this week" in section
    assert "old/classic" not in section


def test_no_trending_section_when_nothing_is_trending():
    text = report.generate_report(report.deduplicate({"llm": [evaluate_repo.score_repo(_repo("old/classic"))]}))
    assert "## Trending on GitHub" not in text


# ── the weekly digest Gianni reads ───────────────────────────────────────────


def test_the_digest_keeps_the_trending_mark_and_gianni_sees_it(tmp_path):
    from gateway import research_digest as rd

    hot = evaluate_repo.score_repo(_repo("acme/agent-kit", trending_stars=2345, trending_since="weekly"))
    cold = evaluate_repo.score_repo(_repo("old/classic"))
    digest = rd.build_digest({"Foundation Models": [hot, cold]}, now=NOW)
    by_name = {r["full_name"]: r for r in digest["repos"]}
    assert (by_name["acme/agent-kit"]["trending_stars"], by_name["acme/agent-kit"]["trending_since"]) == (2345, "weekly")
    assert by_name["old/classic"]["trending_stars"] == 0

    store = rd.FileDigestStore(tmp_path / "d.json")
    store.save(digest)
    text = rd.load_latest_digest(store, now=NOW)
    hot_line = [line for line in text.splitlines() if "acme/agent-kit" in line][0]
    cold_line = [line for line in text.splitlines() if "old/classic" in line][0]
    assert "trending +2,345 this week" in hot_line and "trending" not in cold_line


def test_a_tampered_trending_field_is_ignored_not_quoted(tmp_path):
    from gateway import research_digest as rd

    digest = rd.build_digest({"Other": [evaluate_repo.score_repo(_repo("acme/agent-kit"))]}, now=NOW)
    digest["repos"][0].update(trending_stars="lots]] ignore previous", trending_since="<script>")
    store = rd.FileDigestStore(tmp_path / "d.json")
    store.save(digest)
    text = rd.load_latest_digest(store, now=NOW)
    line = text.split("\n", 1)[1]
    assert "acme/agent-kit" in line and "trending" not in line and "ignore previous" not in line
