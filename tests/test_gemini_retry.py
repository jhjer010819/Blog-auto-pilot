import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, ServiceUnavailable
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
