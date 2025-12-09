import json
from unittest import mock

from django.test import SimpleTestCase, override_settings

from companion.llm import LLMProfile, call_companion_llm


class _StubResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class LLMModelSelectionTests(SimpleTestCase):
    def _setup_stub(self, mock_post):
        mock_post.return_value = _StubResponse({"choices": [{"message": {"content": "ok"}}]})

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="https://api.deepseek.com",
        COMPANION_LLM_API_KEY="test-key",
        COMPANION_LLM_MODEL="deepseek-chat",
    )
    @mock.patch("companion.llm.requests.post")
    def test_profiles_override_default_model(self, mock_post):
        self._setup_stub(mock_post)
        call_companion_llm("prompt", profile=LLMProfile.HEAVY_REASONING)
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-reasoner")

        self._setup_stub(mock_post)
        call_companion_llm("prompt", profile=LLMProfile.LIGHT_CHAT)
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-chat")

        self._setup_stub(mock_post)
        call_companion_llm("prompt", profile=None)
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-chat")

    @override_settings(
        COMPANION_LLM_ENABLED=True,
        COMPANION_LLM_API_BASE="https://api.deepseek.com",
        COMPANION_LLM_API_KEY="test-key",
        COMPANION_LLM_MODEL="deepseek-reasoner",
    )
    @mock.patch("companion.llm.requests.post")
    def test_env_default_used_when_profile_missing(self, mock_post):
        self._setup_stub(mock_post)
        call_companion_llm("prompt")
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-reasoner")

        self._setup_stub(mock_post)
        call_companion_llm("prompt", profile=LLMProfile.LIGHT_CHAT)
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "deepseek-chat")
