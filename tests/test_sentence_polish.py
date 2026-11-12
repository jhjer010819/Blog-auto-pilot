"""문장 단위 문체 다듬기. 네트워크 없이 Gemini 호출을 흉내 낸다."""

import json
from pathlib import Path

import publish

ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscripts" / "2026-11-12-sinansan-line.md"


def _load_manuscript() -> str:
    return MANUSCRIPT.read_text(encoding="utf-8")


def _rows_from_prompt(user_prompt: str) -> list[dict]:
    payload = json.loads(user_prompt.split("SENTENCES_JSON:\n", 1)[1])
    assert isinstance(payload, list)
    return payload


def _reply(user_prompt: str, mutator) -> str:
    rows = [
        {"id": item["id"], "text": mutator(item["text"]), "merged_with_next": False}
        for item in _rows_from_prompt(user_prompt)
    ]
    return json.dumps(rows, ensure_ascii=False)


def _drift(text: str) -> str:
    if text.startswith("국가철도공단 사업 안내에 게시된 공정률"):
        return text.replace("입니다.", "이며 관보 고시입니다.")
    if text.startswith("여의도 이후"):
        return text.replace("이후", "이북", 1)
    if "확인하지 못했습니다" in text:
        return text.replace("환승 표기를 확인하지 못했습니다", "환승 표기가 누락되어 있습니다")
    if text.startswith("2019년"):
        return text.replace("2019", "2020", 1)
    if "경부고속철도" in text:
        return text.replace("**", "")
    if "알아 두는 것이 좋습니다" in text:
        return text.replace("알아 두는 것이 좋습니다.", "알아 두면 도움이 됩니다.")
    return text


def test_blocklist_is_the_required_list() -> None:
    assert publish.POLISH_BLOCKLIST == [
        "고시",
        "관보",
        "심의",
        "위원회",
        "누락",
        "공시",
        "의결",
        "시행령",
        "공포",
        "확정",
    ]


def test_sentence_rules_revert_known_drifts() -> None:
    assert publish.sentence_reject_reason("공정률은 74.73%입니다.", "공정률은 80%입니다.") == "숫자가 바뀌었습니다."
    assert "굵은" in (
        publish.sentence_reject_reason("이름은 **가칭**입니다.", "이름은 가칭입니다.") or ""
    )
    broken = publish.sentence_reject_reason("역명은 **가칭.** 다음입니다.", "역명은 **가칭.**다음입니다.")
    assert broken == "굵은 표시가 문장 부호에 붙어 있습니다."
    assert publish._bold_closer_breaks_commonmark("**가칭.**다음")
    assert not publish._bold_closer_breaks_commonmark("**가칭**으로")
    assert publish.sentence_reject_reason("일정을 확인하지 못했습니다.", "일정이 누락되어 있습니다.")
    assert "방향" in (publish.sentence_reject_reason("여의도 이후 구간입니다.", "여의도 이북 구간입니다.") or "")


def test_manuscript_reverts_drift_and_keeps_structure(capsys, monkeypatch) -> None:
    original = _load_manuscript()
    seen: dict[str, str] = {}

    def fake(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        seen["system"] = system_prompt
        seen["user"] = user_prompt
        return "gemini-3.6-flash", _reply(user_prompt, _drift)

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(publish, "call_polish_models", fake)
    result = publish.polish_markdown(original)
    captured = capsys.readouterr()

    assert seen["system"] == publish.POLISH_SYSTEM_PROMPT
    for phrase in ("합니다/입니다", "숫자, 날짜", "고유명사", "확인하지 못함", "이후를 이북", "merged_with_next", "**"):
        assert phrase in seen["system"]

    rows = _rows_from_prompt(seen["user"])
    assert len(rows) > 1
    joined = "\n".join(row["text"] for row in rows)
    assert "한양대 - 호수 - 중앙" not in seen["user"]
    assert "https://www.korea.kr" not in seen["user"]
    assert "**중앙**: 안산선(4호선)" not in joined
    assert "개통일은 아직 확정되지 않았습니다" not in joined
    assert "## 출처" not in seen["user"]
    assert "sinansanseon-gaetongiljeong" not in seen["user"]
    for disclaimer in publish._DISCLAIMERS:
        if disclaimer in original:
            assert disclaimer not in joined
    assert any("알아 두는 것이 좋습니다" in row["text"] for row in rows)

    assert "관보" not in result
    assert "고시" not in result
    assert "이북" not in result
    assert "누락" not in result
    assert "2020년" not in result
    assert "**경부고속철도 광명역**" in result
    assert "2019년" in result
    assert "여의도 이후" in result
    assert "확인하지 못했습니다" in result
    assert "알아 두면 도움이 됩니다." in result
    assert "알아 두는 것이 좋습니다." not in result

    front = publish._FRONT_MATTER_RE.match(original)
    assert front is not None
    assert result.startswith(original[: front.end()])
    assert original[original.rfind("\n---") :] == result[result.rfind("\n---") :]
    assert publish.headings_of(original) == publish.headings_of(result)
    for disclaimer in publish._DISCLAIMERS:
        assert original.count(disclaimer) == result.count(disclaimer)
    assert "- **중앙**: 안산선(4호선)" in result
    assert "**한양대 - 호수 - 중앙 - 성포 - 장하 - 목감 - 광명 - 석수" in result

    status = captured.out
    assert "POLISH_STATUS: ok model=gemini-3.6-flash applied=1 reverted=5 kept=" in status
    summary = json.loads(status.split("POLISH_SUMMARY: ", 1)[1].splitlines()[0])
    assert summary["status"] == "ok"
    assert summary["model"] == "gemini-3.6-flash"
    assert summary["applied"] == 1
    assert summary["reverted"] == 5
    reasons = {item["id"]: item["reason"] for item in summary["reverts"]}

    def reason_for(prefix: str) -> str:
        matches = [row["id"] for row in rows if row["text"].startswith(prefix)]
        assert matches, prefix
        return reasons[matches[0]]

    assert "행정 용어" in reason_for("국가철도공단 사업 안내에 게시된 공정률")
    assert "굵은 글씨" in reason_for("시행사가 밝힌 사업 목적에는")
    assert "행정 용어" in reason_for("영등포는 기존 1호선")
    assert "숫자" in reason_for("2019년")
    assert "방향" in reason_for("여의도 이후")
    assert publish._literal_bold_count(result) <= publish._literal_bold_count(original)


def test_bad_json_and_api_error_restore_the_whole_post(capsys, monkeypatch) -> None:
    original = "# 제목\n\n원문 문장입니다.\n"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    monkeypatch.setattr(publish, "call_polish_models", lambda *args, **kwargs: ("gemini-3.8-flash", "[]"))
    assert publish.polish_markdown(original) == original
    assert "POLISH_STATUS: error reason=count" in capsys.readouterr().out

    monkeypatch.setattr(
        publish,
        "call_polish_models",
        lambda *args, **kwargs: ("gemini-3.8-flash", "설명이 섞인 응답"),
    )
    assert publish.polish_markdown(original) == original
    assert "POLISH_STATUS: error reason=json" in capsys.readouterr().out

    def boom(*args, **kwargs):
        raise RuntimeError("연결에 실패했습니다")

    monkeypatch.setattr(publish, "call_polish_models", boom)
    assert publish.polish_markdown(original) == original
    assert "POLISH_STATUS: error reason=api" in capsys.readouterr().out


def test_one_request_fallback_chain(capsys, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeModel:
        def __init__(self, name: str, system_instruction: str | None = None) -> None:
            self.name = name
            calls.append(name)

        def generate_content(self, prompt: str, generation_config: dict | None = None) -> FakeResponse:
            assert "SENTENCES_JSON:" in prompt
            assert generation_config["response_mime_type"] == "application/json"
            if self.name == "gemini-3.8-flash":
                raise RuntimeError("models/gemini-3.8-flash is not found")
            rows = _reply(prompt, lambda text: text.replace("원문 문장", "다듬은 문장"))
            return FakeResponse(rows)

    import google.generativeai as genai

    monkeypatch.setattr(genai, "configure", lambda api_key: None)
    monkeypatch.setattr(genai, "GenerativeModel", FakeModel)
    result = publish.polish_markdown("# 제목\n\n원문 문장입니다.\n")
    assert calls == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert "다듬은 문장입니다." in result
    assert "POLISH_STATUS: ok model=gemini-3.6-flash applied=1 reverted=0" in capsys.readouterr().out


def test_daily_quota_retries_fallback_once(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    monkeypatch.delenv("GEMINI_POLISH_MODELS", raising=False)
    calls: list[str] = []

    class FakeModel:
        def __init__(self, name: str, system_instruction: str | None = None) -> None:
            calls.append(name)

        def generate_content(self, prompt: str, generation_config: dict | None = None) -> None:
            raise RuntimeError("Quota exceeded per day")

    import google.generativeai as genai

    monkeypatch.setattr(genai, "configure", lambda api_key: None)
    monkeypatch.setattr(genai, "GenerativeModel", FakeModel)
    original = "# 제목\n\n원문 문장입니다.\n"
    assert publish.polish_markdown(original) == original
    assert calls == ["gemini-3.8-flash", "gemini-3.6-flash"]


def test_quota_429_uses_fallback_model_once(capsys, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv(
        "GEMINI_POLISH_MODELS",
        "gemini-3.8-flash, gemini-3.6-flash, gemini-3.5-flash-lite",
    )
    calls: list[str] = []

    class ResourceExhausted(Exception):
        def __init__(self) -> None:
            super().__init__("429 RESOURCE_EXHAUSTED")
            self.code = 429

    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeModel:
        def __init__(self, name: str, system_instruction: str | None = None) -> None:
            self.name = name
            calls.append(name)

        def generate_content(self, prompt: str, generation_config: dict | None = None) -> FakeResponse:
            assert generation_config["response_mime_type"] == "application/json"
            if self.name == "gemini-3.8-flash":
                raise ResourceExhausted()
            return FakeResponse(_reply(prompt, lambda text: text.replace("원문 문장", "다듬은 문장")))

    import google.generativeai as genai

    monkeypatch.setattr(genai, "configure", lambda api_key: None)
    monkeypatch.setattr(genai, "GenerativeModel", FakeModel)
    result = publish.polish_markdown("# 제목\n\n원문 문장입니다.\n")
    assert calls == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert "다듬은 문장입니다." in result
    status = capsys.readouterr().out
    assert "POLISH_STATUS: ok model=gemini-3.6-flash applied=1 reverted=0" in status
    summary = json.loads(status.split("POLISH_SUMMARY: ", 1)[1].splitlines()[0])
    assert summary["model"] == "gemini-3.6-flash"


def test_adjacent_merge_and_rejected_merge(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    original = "# 제목\n\n첫 문장입니다. 둘째 문장입니다.\n"

    def merge(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        rows = _rows_from_prompt(user_prompt)
        assert len(rows) == 2
        rows[0]["text"] = "첫 문장이고 둘째 문장입니다."
        rows[0]["merged_with_next"] = True
        rows[1]["text"] = ""
        return "gemini-3.8-flash", json.dumps(rows, ensure_ascii=False)

    monkeypatch.setattr(publish, "call_polish_models", merge)
    merged = publish.polish_markdown(original)
    assert "첫 문장이고 둘째 문장입니다." in merged
    assert "첫 문장입니다." not in merged

    numbered = "# 제목\n\n역은 3곳입니다. 노선은 2개입니다.\n"

    def drop_numbers(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        rows = _rows_from_prompt(user_prompt)
        rows[0]["text"] = "역과 노선이 있습니다."
        rows[0]["merged_with_next"] = True
        rows[1]["text"] = ""
        return "gemini-3.8-flash", json.dumps(rows, ensure_ascii=False)

    monkeypatch.setattr(publish, "call_polish_models", drop_numbers)
    assert publish.polish_markdown(numbered) == numbered


def test_tables_code_and_labels_are_not_sent(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    original = (
        "# 제목\n\n"
        "앞 문장입니다.\n\n"
        "| 항목 | 값 |\n| --- | --- |\n| 역 | 3 |\n\n"
        "```\n코드 **그대로**\n```\n\n"
        "- **중앙**: 안산선(4호선)\n\n"
        "**한양대 - 호수 - 중앙**\n\n"
        "뒤 문장입니다.\n"
    )
    seen: dict[str, str] = {}

    def fake(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        seen["user"] = user_prompt
        return "gemini-3.5-flash-lite", _reply(user_prompt, lambda text: text.replace("입니다.", "입니다만."))

    monkeypatch.setattr(publish, "call_polish_models", fake)
    result = publish.polish_markdown(original)
    prompt = seen["user"]
    assert "| 역 | 3 |" not in prompt
    assert "코드 **그대로**" not in prompt
    assert "**중앙**: 안산선(4호선)" not in prompt
    assert "한양대 - 호수 - 중앙" not in prompt
    assert prompt.count('"id":') == 2
    assert "| 역 | 3 |" in result
    assert "코드 **그대로**" in result
    assert "- **중앙**: 안산선(4호선)" in result
    assert "**한양대 - 호수 - 중앙**" in result
    assert "앞 문장입니다만." in result
    assert "뒤 문장입니다만." in result


def test_dry_run_prints_status_before_polished_markdown(capsys, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        assert user_prompt.count("SENTENCES_JSON:") == 1
        return "gemini-3.6-flash", _reply(user_prompt, _drift)

    monkeypatch.setattr(publish, "call_polish_models", fake)
    args = publish.parse_args(
        [
            str(MANUSCRIPT),
            "--dry-run",
            "--polish",
            "--root",
            str(tmp_path),
        ]
    )
    assert publish.publish(args) is None
    text = capsys.readouterr().out
    assert text.index("POLISH_STATUS:") < text.index("POLISH_SUMMARY:") < text.index("=== POLISHED START ===")
    assert "=== POLISHED END ===" in text
    body = text.split("=== POLISHED START ===", 1)[1].split("=== POLISHED END ===", 1)[0]
    assert "알아 두면 도움이 됩니다." in body
    assert "관보" not in body
    assert "이북" not in body
    assert "2020년" not in body
    assert list(tmp_path.rglob("*")) == []


def test_missing_api_key_still_fails(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        publish.polish_markdown("# 제목\n\n본문입니다.\n")
    except publish.PublishError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    else:
        raise AssertionError("키가 없으면 실패해야 합니다.")


def test_default_model_order(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    monkeypatch.delenv("GEMINI_POLISH_MODELS", raising=False)
    assert publish._polish_model_names() == (
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    )


def test_polish_models_env_overrides_keyword_models(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODELS", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_POLISH_MODELS", "gemini-3.8-flash, gemini-3.6-flash")
    assert publish._polish_model_names() == ("gemini-3.8-flash", "gemini-3.6-flash")
