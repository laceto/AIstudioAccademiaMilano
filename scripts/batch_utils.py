"""
batch_utils.py — Shared kitai batch helper.

GA detection: GITHUB_ACTIONS=true + OPENAI_API_KEY must be set.
Falls back gracefully when either is missing.

Usage:
    from scripts.batch_utils import is_ga_batch_available, submit_and_wait
"""
import os


def is_ga_batch_available() -> bool:
    """True only inside GitHub Actions with OPENAI_API_KEY configured."""
    return os.environ.get("GITHUB_ACTIONS") == "true" and bool(os.environ.get("OPENAI_API_KEY"))


def submit_and_wait(tasks: list[dict], poll_interval: float = 30.0) -> list[dict]:
    """Submit tasks to kitai batch and block until all complete.

    Each task follows the OpenAI batch format:
        {
            "custom_id": "unique-id",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": { "model": ..., "messages": [...] }
        }

    Returns the raw result list from download_batch_results.
    Raises RuntimeError if the batch job does not complete.
    """
    from openai import OpenAI
    from kitai.batch import submit_batch_job, poll_until_complete, download_batch_results

    client = OpenAI()
    job_id = submit_batch_job(client, tasks, endpoint="/v1/chat/completions")
    print(f"[kitai.batch] Submitted {len(tasks)} task(s) — job: {job_id}")

    completed = poll_until_complete(client, [job_id], poll_interval=poll_interval)
    if job_id not in completed:
        raise RuntimeError(
            f"[kitai.batch] Job {job_id} did not complete within timeout. "
            "Check the OpenAI dashboard."
        )

    results = download_batch_results(client, job_id)
    print(f"[kitai.batch] {len(results)}/{len(tasks)} results downloaded.")
    return results
