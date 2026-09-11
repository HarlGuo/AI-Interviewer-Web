"""Backward-compatible import path. Provider code lives in app.llm.deepseek."""

from .llm.deepseek import LLMNotConfiguredError, _send, chat_json

__all__ = ["LLMNotConfiguredError", "_send", "chat_json"]
