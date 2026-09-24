"""Tests need no real Gemini token. Transport calls are replaced with mocks."""
import os
os.environ.setdefault("GEMINI_API_KEY", "test-token-not-used")
