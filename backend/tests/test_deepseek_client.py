import unittest
from unittest.mock import AsyncMock, patch

from app.llm.deepseek import chat_json, chat_with_tools


class DeepSeekClientTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_tool_loop_uses_auto_single_tool_calls(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        settings.deepseek_model = "deepseek-test"
        message = {"role": "assistant", "content": None, "tool_calls": []}
        send.return_value = {"choices": [{"message": message}]}
        result = await chat_with_tools(messages=[{"role": "user", "content": "test"}], tools=[{"type": "function"}])
        self.assertIs(result, message)
        payload = send.await_args.args[0]
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("response_format", payload)
        self.assertEqual(send.await_args.kwargs["purpose"], "agent_loop")

    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_retries_empty_content_once(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.side_effect = [
            {"choices": [{"message": {"content": ""}}]},
            {"choices": [{"message": {"content": '{"ok": true}'}}]},
        ]
        result = await chat_json(messages=[], temperature=0, max_tokens=100, purpose="test")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(send.await_count, 2)
        self.assertEqual(send.await_args_list[0].args[0]["max_tokens"], 100)
        self.assertEqual(send.await_args_list[1].args[0]["max_tokens"], 200)
        self.assertEqual(send.await_args_list[0].args[0]["thinking"], {"type": "disabled"})
        self.assertEqual(send.await_args_list[0].kwargs["read_timeout"], 75)

    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_report_uses_longer_read_timeout(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        await chat_json(messages=[], temperature=0, max_tokens=100, purpose="report")
        self.assertEqual(send.await_args.kwargs["read_timeout"], 180)

    @patch("app.llm.deepseek.settings")
    @patch("app.llm.deepseek._send", new_callable=AsyncMock)
    async def test_fails_after_two_invalid_responses(self, send: AsyncMock, settings: object) -> None:
        settings.deepseek_api_key = "configured"
        send.side_effect = [
            {"choices": [{"message": {"content": "not-json"}}]},
            {"choices": [{"message": {"content": "[]"}}]},
        ]
        with self.assertRaisesRegex(RuntimeError, "after one retry"):
            await chat_json(messages=[], temperature=0, max_tokens=100, purpose="test")


if __name__ == "__main__":
    unittest.main()
