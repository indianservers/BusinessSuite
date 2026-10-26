from __future__ import annotations

from typing import Any

try:
    from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
except ImportError:  # pragma: no cover - dependency is declared in requirements.txt
    class _MissingOpenAiException(Exception):
        pass

    APIConnectionError = APIStatusError = APITimeoutError = RateLimitError = _MissingOpenAiException
    OpenAI = None

from app.core.config import settings


class OpenAiService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key, timeout=30, max_retries=0) if self.api_key and OpenAI else None

    def create_response(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        if OpenAI is None:
            return {
                "success": False,
                "error_code": "OPENAI_SDK_MISSING",
                "message": "The OpenAI SDK is not installed in the backend environment.",
                "details": {},
            }
        if not self.client:
            return {
                "success": False,
                "error_code": "OPENAI_API_KEY_MISSING",
                "message": "The AI service is not configured. Please add OPENAI_API_KEY on the backend.",
                "details": {},
            }
        try:
            kwargs: dict[str, Any] = {
                "model": model or settings.OPENAI_MODEL,
                "messages": messages,
                "temperature": temperature if temperature is not None else settings.AI_AGENT_DEFAULT_TEMPERATURE,
                "max_completion_tokens":4096,
                "timeout": max(0.1, min(30, timeout)),
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message
            tool_calls = []
            for call in message.tool_calls or []:
                tool_calls.append(
                    {
                        "id": call.id,
                        "type": call.type,
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    }
                )
            return {
                "success": True,
                "message": message.content or "",
                "tool_calls": tool_calls,
                "raw": {
                    "id": response.id,
                    "model": response.model,
                    "finish_reason": choice.finish_reason,
                    "usage": {
                        "input_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
                        "output_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
                        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
                    },
                },
            }
        except RateLimitError as exc:
            return self._failure("OPENAI_RATE_LIMIT", "The AI service is rate limited. Please try again shortly.", exc)
        except APITimeoutError as exc:
            return self._failure("OPENAI_TIMEOUT", "The AI service timed out. Please try again.", exc)
        except APIConnectionError as exc:
            return self._failure("OPENAI_NETWORK_ERROR", "The AI service is temporarily unavailable.", exc)
        except APIStatusError as exc:
            return self._failure("OPENAI_ERROR", "The AI service returned an error.", exc, {"status_code": exc.status_code})
        except Exception as exc:
            return self._failure("OPENAI_ERROR", "AI service is temporarily unavailable.", exc)

    def _failure(self, code: str, message: str, exc: Exception, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        details = {"error": exc.__class__.__name__}
        if extra:
            details.update(extra)
        return {"success": False, "error_code": code, "message": message, "details": details}
