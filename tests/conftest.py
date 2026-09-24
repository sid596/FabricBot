"""Tests need no real Gemini token. Transport calls are replaced with mocks."""
import os
os.environ.setdefault("GEMINI_API_KEY", "test-token-not-used")

import pytest

@pytest.fixture(autouse=True)
def isolated_quotation_drafts(tmp_path, monkeypatch):
    import server
    from quote_conversation import DraftStore
    monkeypatch.setattr(server, 'draft_store', DraftStore(tmp_path / 'drafts.sqlite3'))
