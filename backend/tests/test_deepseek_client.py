import unittest
from unittest.mock import AsyncMock, patch

from app.llm.deepseek import chat_json


class DeepSeekClientTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_uses_interactive_timeout_budget(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        result = await chat_json(messages=[], temperature=0, max_tokens=100, purpose="test")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(send.await_count, 1)
        self.assertEqual(send.await_args.args[0]["max_tokens"], 100)
        self.assertEqual(send.await_args.args[0]["thinking"], {"type": "disabled"})
        self.assertEqual(send.await_args.kwargs["read_timeout"], 22)

    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_report_uses_longer_read_timeout(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        await chat_json(messages=[], temperature=0, max_tokens=100, purpose="report")
        self.assertEqual(send.await_args.kwargs["read_timeout"], 50)

    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_fails_after_invalid_response_without_gateway_risky_retry(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.return_value = {"choices": [{"message": {"content": "not-json"}}]}
        with self.assertRaisesRegex(RuntimeError, "invalid or malformed JSON"):
            await chat_json(messages=[], temperature=0, max_tokens=100, purpose="test")
        self.assertEqual(send.await_count, 1)


if __name__ == "__main__":
    unittest.main()
