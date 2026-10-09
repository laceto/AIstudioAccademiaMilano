"""The pipeline worker's container must carry everything the pipeline reads at run time.

None of this can be checked by running Docker in CI, so these tests read the Dockerfile and
requirements and compare them with what the code actually imports and opens.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = (ROOT / "gateway" / "Dockerfile.worker").read_text(encoding="utf-8")
REQS = (ROOT / "gateway" / "requirements.worker.txt").read_text(encoding="utf-8")
CLOUDBUILD = (ROOT / "deploy" / "cloudbuild.worker.yaml").read_text(encoding="utf-8")


def _copied():
    return {line.split()[1].rstrip("/") for line in DOCKERFILE.splitlines() if line.startswith("COPY ")}


@pytest.mark.parametrize(
    "path",
    [
        "gateway",  # the worker code
        "config",  # config.brand, global_settings.json (prices), brand.json
        "templates",  # Chiara's landing page / invoice / chatbot templates
        "deliverables/2026-05-25_016_aistudio-langgraph",  # the pipeline itself
    ],
)
def test_the_image_copies_what_the_pipeline_reads(path):
    assert path in _copied()
    assert (ROOT / path).exists()


def test_the_image_does_not_copy_the_whole_deliverables_folder():
    assert "deliverables" not in _copied()  # dozens of unrelated projects


def test_the_container_starts_the_worker_on_the_cloud_run_port():
    cmd = [l for l in DOCKERFILE.splitlines() if l.startswith("CMD")][0]
    assert "gateway.pipeline_worker:app" in cmd and "${PORT" in cmd and "0.0.0.0" in cmd


def test_the_worker_module_exists_and_exposes_app():
    assert "app = FastAPI" in (ROOT / "gateway" / "pipeline_worker.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "package",
    ["fastapi", "uvicorn", "pydantic", "httpx", "pyyaml", "google-cloud-firestore",
     "langgraph", "langchain-core", "langchain-openai"],
)
def test_the_requirements_cover_the_runtime_imports(package):
    assert re.search(rf"^{re.escape(package)}\b", REQS, re.M | re.I), package


def test_the_worker_image_stays_light():
    # Streamlit, Telegram's client and Twilio belong to the gateway, not to a batch worker.
    packages = " ".join(l for l in REQS.lower().splitlines() if not l.lstrip().startswith("#"))
    for heavy in ("streamlit", "python-telegram-bot", "twilio"):
        assert heavy not in packages, heavy


def test_the_gateway_has_the_cloud_tasks_client():
    assert re.search(r"^google-cloud-tasks\b", (ROOT / "gateway" / "requirements.txt").read_text(encoding="utf-8"), re.M)


def test_cloud_build_names_the_worker_dockerfile_explicitly():
    # The repo holds several Dockerfiles; a default source build picks the wrong one.
    assert "gateway/Dockerfile.worker" in CLOUDBUILD and "${_IMAGE}" in CLOUDBUILD


# ── Cloud Tasks is not available in every Cloud Run region ───────────────────
# europe-west8 (Milan) hosts the services but Cloud Tasks refuses it:
#   "Location 'europe-west8' is not a valid location".


def _script():
    return (ROOT / "scripts" / "deploy_cloudrun.sh").read_text(encoding="utf-8")


def test_the_queue_has_its_own_region_that_cloud_tasks_supports():
    text = _script()
    match = re.search(r'TASKS_LOCATION="\$\{TASKS_LOCATION:-([a-z0-9-]+)\}"', text)
    assert match, "TASKS_LOCATION default missing"
    # regions Cloud Tasks lists for Europe (gcloud tasks locations list); Milan is not one of them
    assert match.group(1) in {"europe-west1", "europe-west2", "europe-west3", "europe-west6", "europe-central2"}


def test_the_queue_is_created_in_the_tasks_region_not_the_service_region():
    text = _script()
    assert 'ensure_tasks_queue "$QUEUE_NAME" "$TASKS_LOCATION"' in text
    assert 'ensure_tasks_queue "$QUEUE_NAME" "$REGION"' not in text


def test_the_gateway_is_told_where_the_queue_lives():
    assert '"TASKS_LOCATION=$TASKS_LOCATION"' in _script()
    assert '"TASKS_LOCATION=$REGION"' not in _script()
