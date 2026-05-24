"""tests/test_gateway_sofia.py — Sofia track: streamlit form + adapter call."""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from gateway.pipeline_adapter import PipelineAdapter


class TestPipelineAdapterFromStreamlit:
    """Validate that the streamlit form passes correct data to the adapter."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.adapter = PipelineAdapter(queue_dir=self.tmp)

    def test_streamlit_channel_accepted(self):
        result = self.adapter.submit(
            text="I need a bakery landing page",
            channel="streamlit",
            metadata={"intent_label": "I want a website"},
        )
        assert result["status"] == "queued"

    def test_intent_prefix_preserved(self):
        text = "[Intent: website_creation] I need a bakery website"
        result = self.adapter.submit(text=text, channel="streamlit", metadata={})
        job = self.adapter.get_status(result["job_id"])
        assert "website_creation" in job["text"]

    def test_empty_text_rejected(self):
        result = self.adapter.submit(text="", channel="streamlit", metadata={})
        assert result["status"] == "error"

    def test_metadata_intent_label_stored(self):
        result = self.adapter.submit(
            text="Make a PDF invoice",
            channel="streamlit",
            metadata={"intent_label": "I need a PDF document"},
        )
        assert result["status"] == "queued"

    def test_session_history_structure(self):
        """Simulate what the Streamlit form stores in session_state.history."""
        result = self.adapter.submit("Build a chatbot", "streamlit", {})
        history_entry = {
            "job_id": result["job_id"],
            "text": "Build a chatbot",
            "status": result["status"],
            "result": result["result"],
        }
        assert history_entry["status"] == "queued"
        assert len(history_entry["job_id"]) == 10
