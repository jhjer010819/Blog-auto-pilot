import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from google.api_core.exceptions import DeadlineExceeded, NotFound, ResourceExhausted, ServiceUnavailable
from requests.exceptions import ReadTimeout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMINI_API_KEY", "test-key")

import main  # noqa: E402


def gemini_response(payload: dict) -> Mock:
    response = Mock()
    response.text = json.dumps(payload, ensure_ascii=False)
    return response


SELECTION = {
    "category": "건강",
    "selected_seed": "커피 혈당",
    "reason": "에버그린",
    "longtail_title": "커피 혈당 상승 원인",
}


class GeminiRetryTests(unittest.TestCase):
    def test_retries_after_504_then_returns_selection(self) -> None:
        error = DeadlineExceeded("504 Deadline expired")
        with (
            patch.object(
                main.model,
                "generate_content",
                side_effect=[error, gemini_response(SELECTION)],
            ) as generate,
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main.select_best_longtail_with_gemini(["커피 혈당 상승"])

        self.assertEqual(result["category"], "건강")
        self.assertEqual(result["selected_seed"], "커피 혈당")
        self.assertEqual(result["longtail_title"], "커피 혈당 상승 원인")
        self.assertEqual(generate.call_count, 2)
        for call in generate.call_args_list:
            self.assertEqual(
                call.kwargs["generation_config"],
                {"response_mime_type": "application/json", "temperature": 0.2},
            )
            self.assertEqual(call.kwargs["request_options"]["timeout"], 90)
            self.assertIsNone(call.kwargs["request_options"]["retry"])
        sleep.assert_called_once_with(20)
        logs = stdout.getvalue()
        self.assertIn("일시 오류", logs)
        self.assertIn("504", logs)
        self.assertIn("20초", logs)
        self.assertIn("재시도합니다", logs)

    def test_gives_up_after_max_attempts(self) -> None:
        error = DeadlineExceeded("504 Deadline expired")
        with (
            patch.dict(os.environ, {"GEMINI_MODELS": "gemini-3.8-flash"}),
            patch.object(main.model, "generate_content", side_effect=[error, error, error]) as generate,
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(DeadlineExceeded):
                main._call_gemini("prompt")

        self.assertEqual(generate.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [20, 60])
        for call in generate.call_args_list:
            self.assertEqual(call.kwargs["request_options"]["timeout"], 90)
        logs = stdout.getvalue()
        self.assertIn("3회 모두 실패", logs)
        self.assertIn("재시도를 중단", logs)
        self.assertIn("60초", logs)

    def test_retries_503_429_and_timeouts(self) -> None:
        cases = [
            ServiceUnavailable("503"),
            ResourceExhausted("429 per minute"),
            ReadTimeout("read timed out"),
            TimeoutError("timed out"),
        ]
        for error in cases:
            with self.subTest(error=type(error).__name__):
                with (
                    patch.object(
                        main.model,
                        "generate_content",
                        side_effect=[error, gemini_response(SELECTION)],
                    ) as generate,
                    patch.object(main.time, "sleep") as sleep,
                    redirect_stdout(io.StringIO()),
                ):
                    result = main._call_gemini("prompt")
                self.assertEqual(json.loads(result.text)["longtail_title"], SELECTION["longtail_title"])
                self.assertEqual(generate.call_count, 2)
                sleep.assert_called_once_with(20)

    def test_daily_quota_is_not_retried(self) -> None:
        error = ResourceExhausted("Quota exceeded per day")
        with (
            patch.object(main.model, "generate_content", side_effect=error) as generate,
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(ResourceExhausted):
                main.select_best_longtail_with_gemini(["커피 혈당 상승"])
        self.assertEqual(generate.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("일일 한도로 보여 재시도하지 않고 종료합니다", stdout.getvalue())

    def test_non_transient_error_is_not_retried(self) -> None:
        with (
            patch.object(main.model, "generate_content", side_effect=ValueError("bad json request")) as generate,
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(ValueError):
                main._call_gemini("prompt")
        self.assertEqual(generate.call_count, 1)
        sleep.assert_not_called()
        self.assertNotIn("재시도", stdout.getvalue())


def _clients(responses_by_model: dict[str, list]) -> dict[str, Mock]:
    clients = {}
    for name, outcomes in responses_by_model.items():
        client = Mock()
        client.generate_content.side_effect = outcomes
        clients[name] = client
    return clients


class GeminiFallbackTests(unittest.TestCase):
    def test_default_and_env_model_order(self) -> None:
        env = os.environ.copy()
        env.pop("GEMINI_MODELS", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                main._gemini_model_names(),
                ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"),
            )
        with patch.dict(os.environ, {"GEMINI_MODELS": " gemini-3.5-flash-lite, gemini-3.6-flash "}):
            self.assertEqual(
                main._gemini_model_names(),
                ("gemini-3.5-flash-lite", "gemini-3.6-flash"),
            )
        self.assertEqual(main._gemini_attempt_budget(0)[0], 3)
        self.assertEqual(main._gemini_attempt_budget(0)[1], 90)
        self.assertEqual(main._gemini_attempt_budget(1), (2, 45, (15,)))
        self.assertEqual(main._gemini_attempt_budget(2), (2, 30, (10,)))
        self.assertEqual(main._gemini_attempt_budget(4), (2, 30, (10,)))
        worst = 0
        for index in range(3):
            attempts, timeout, backoff = main._gemini_attempt_budget(index)
            worst += attempts * timeout + sum(backoff)
        self.assertEqual(worst, 525)

    def test_primary_503_then_fallback_succeeds(self) -> None:
        error = ServiceUnavailable(
            '503 UNAVAILABLE model is currently experiencing high demand'
        )
        clients = _clients(
            {
                "gemini-3.8-flash": [error, error, error],
                "gemini-3.6-flash": [gemini_response(SELECTION)],
                "gemini-3.5-flash-lite": [AssertionError("lite should not be called")],
            }
        )
        with (
            patch.object(main, "_generative_model", side_effect=lambda name: clients[name]),
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            result = main._call_gemini("prompt")

        self.assertEqual(json.loads(result.text)["longtail_title"], SELECTION["longtail_title"])
        self.assertEqual(clients["gemini-3.8-flash"].generate_content.call_count, 3)
        self.assertEqual(clients["gemini-3.6-flash"].generate_content.call_count, 1)
        clients["gemini-3.5-flash-lite"].generate_content.assert_not_called()
        self.assertEqual(
            clients["gemini-3.8-flash"].generate_content.call_args.kwargs["request_options"]["timeout"],
            90,
        )
        fallback_call = clients["gemini-3.6-flash"].generate_content.call_args
        self.assertEqual(fallback_call.kwargs["request_options"]["timeout"], 45)
        self.assertIsNone(fallback_call.kwargs["request_options"]["retry"])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [20, 60])
        logs = stdout.getvalue()
        self.assertIn("gemini-3.8-flash로 요청합니다", logs)
        self.assertIn("gemini-3.6-flash로 넘어갑니다", logs)
        self.assertIn("최종 사용 모델: gemini-3.6-flash", logs)
        self.assertEqual(main.gemini_model_used, "gemini-3.6-flash")

    def test_model_not_found_skips_to_next_without_retry(self) -> None:
        cases = [
            NotFound("models/gemini-3.8-flash is not found"),
            Exception("gemini-2.5-flash is not available to new users"),
        ]
        for error in cases:
            with self.subTest(error=str(error)):
                clients = _clients(
                    {
                        "gemini-3.8-flash": [error],
                        "gemini-3.6-flash": [gemini_response(SELECTION)],
                        "gemini-3.5-flash-lite": [AssertionError("lite should not be called")],
                    }
                )
                with (
                    patch.object(main, "_generative_model", side_effect=lambda name: clients[name]),
                    patch.object(main.time, "sleep") as sleep,
                    redirect_stdout(io.StringIO()) as stdout,
                ):
                    result = main._call_gemini("prompt")
                self.assertEqual(json.loads(result.text)["category"], "건강")
                self.assertEqual(clients["gemini-3.8-flash"].generate_content.call_count, 1)
                self.assertEqual(clients["gemini-3.6-flash"].generate_content.call_count, 1)
                clients["gemini-3.5-flash-lite"].generate_content.assert_not_called()
                sleep.assert_not_called()
                logs = stdout.getvalue()
                self.assertIn("다시 호출하지 않고", logs)
                self.assertIn("gemini-3.6-flash로 넘어갑니다", logs)
                self.assertNotIn("재시도합니다", logs)
                self.assertIn("최종 사용 모델: gemini-3.6-flash", logs)

    def test_all_models_fail_raises(self) -> None:
        error = ServiceUnavailable("503 UNAVAILABLE high demand")
        clients = _clients(
            {
                "gemini-3.8-flash": [error, error, error],
                "gemini-3.6-flash": [error, error],
                "gemini-3.5-flash-lite": [error, error],
            }
        )
        with (
            patch.object(main, "_generative_model", side_effect=lambda name: clients[name]),
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(ServiceUnavailable):
                main._call_gemini("prompt")

        self.assertEqual(clients["gemini-3.8-flash"].generate_content.call_count, 3)
        self.assertEqual(clients["gemini-3.6-flash"].generate_content.call_count, 2)
        self.assertEqual(clients["gemini-3.5-flash-lite"].generate_content.call_count, 2)
        self.assertEqual(
            clients["gemini-3.6-flash"].generate_content.call_args.kwargs["request_options"]["timeout"],
            45,
        )
        self.assertEqual(
            clients["gemini-3.5-flash-lite"].generate_content.call_args.kwargs["request_options"]["timeout"],
            30,
        )
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [20, 60, 15, 10])
        logs = stdout.getvalue()
        self.assertIn("gemini-3.6-flash로 넘어갑니다", logs)
        self.assertIn("gemini-3.5-flash-lite로 넘어갑니다", logs)
        self.assertIn("2회 모두 실패", logs)
        self.assertIn("재시도를 중단", logs)
        self.assertIsNone(main.gemini_model_used)

    def test_daily_quota_does_not_try_the_next_model(self) -> None:
        error = ResourceExhausted("Quota exceeded per day")
        clients = _clients(
            {
                "gemini-3.8-flash": [error],
                "gemini-3.6-flash": [gemini_response(SELECTION)],
            }
        )
        with (
            patch.object(main, "_generative_model", side_effect=lambda name: clients[name]),
            patch.object(main.time, "sleep") as sleep,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(ResourceExhausted):
                main._call_gemini("prompt")
        self.assertEqual(clients["gemini-3.8-flash"].generate_content.call_count, 1)
        clients["gemini-3.6-flash"].generate_content.assert_not_called()
        sleep.assert_not_called()
        self.assertIn("일일 한도로 보여 재시도하지 않고 종료합니다", stdout.getvalue())
