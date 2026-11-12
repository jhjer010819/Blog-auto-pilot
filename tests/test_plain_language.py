"""쉬운 말 검사와, 굵은 글씨 안의 사전 치환만 허용하는 문장 검증."""

import json
from pathlib import Path

import publish

ROOT = Path(__file__).resolve().parents[1]
FUNERAL = ROOT / "manuscripts" / "2026-11-13-funeral-admin.md"
WORKFLOW = ROOT / ".github" / "workflows" / "publish_post.yml"


def _rows_from_prompt(user_prompt: str) -> list[dict]:
    payload = json.loads(user_prompt.split("SENTENCES_JSON:\n", 1)[1])
    assert isinstance(payload, list)
    return payload


def test_dictionary_substitution_inside_bold_is_allowed() -> None:
    original = "장제급여는 사망자 **1구당 80만원**입니다."
    polished = "장제급여는 사망자 **1명당 80만원**입니다."
    assert publish.sentence_reject_reason(original, polished) is None

    longer = "**상속개시 있음을 안 날부터 3개월 이내**에 해야 합니다."
    rewritten = "**상속이 시작된 것을 안 날부터 3개월 이내**에 해야 합니다."
    assert publish.sentence_reject_reason(longer, rewritten) is None
    assert publish.sentence_reject_reason("관서가 기간을 정합니다.", "관청이 기간을 정합니다.") is None
    kept_place = publish.sentence_reject_reason(
        "관서가 여의도에서 접수합니다.",
        "관청이 서울에서 접수합니다.",
    )
    assert kept_place == "고유명사가 바뀌었습니다."


def test_bold_change_outside_the_dictionary_is_rejected() -> None:
    reason = publish.sentence_reject_reason("이름은 **가칭**입니다.", "이름은 **임시 이름**입니다.")
    assert reason == "굵은 글씨가 바뀌었습니다."
    removed = publish.sentence_reject_reason("이름은 **가칭**입니다.", "이름은 가칭입니다.")
    assert removed is not None and "굵은" in removed


def test_bold_dictionary_substitution_keeps_number_check() -> None:
    original = "사망자 **1구당 80만원**입니다."
    polished = "사망자 **1명당 90만원**입니다."
    assert publish.sentence_reject_reason(original, polished) == "숫자가 바뀌었습니다."


def test_superlative_최고_is_not_a_jargon_hit() -> None:
    flags = publish.plain_language_flags("# 제목\n\n최고속도는 110km/h입니다. 필요함은 그대로입니다.\n")
    assert flags == []
    urged = publish.plain_language_flags("# 제목\n\n관서가 기간을 정해 최고한 뒤입니다.\n")
    terms = [flag["term"] for flag in urged]
    assert terms == ["관서", "최고"]
    kept = publish.sentence_reject_reason(
        "최고속도는 **110km/h**입니다.",
        "독촉속도는 **110km/h**입니다.",
    )
    assert kept == "고유명사가 바뀌었습니다."
    preserved = publish.sentence_reject_reason("필요함은 그대로입니다.", "필요사항은 그대로입니다.")
    assert preserved == "사전에서 예외로 둔 단어를 바꿨습니다."


def test_lint_skips_front_matter_sources_tables_code_and_disclaimer() -> None:
    text = "\n".join(
        [
            "---",
            "title: 신고의무자 안내",
            "---",
            "# 제목",
            "",
            "## 신고의무자 안내",
            "",
            "본문에 관서가 나옵니다.",
            "",
            "| 관서 | 값 |",
            "| --- | --- |",
            "| 예시 | 1 |",
            "",
            "```",
            "관서",
            "```",
            "",
            "정부 정책 및 지원 기준은 시기별로 개정될 수 있으므로 정확한 내용은 공식 기관 공고를 확인해 주세요.",
            "",
            "---",
            "",
            "## 출처",
            "",
            "1. 관서 안내",
            "",
        ]
    )
    flags = publish.plain_language_flags(text)
    assert [(flag["term"], flag["line"]) for flag in flags] == [
        ("신고의무자", 6),
        ("관서", 8),
    ]
    for flag in flags:
        assert set(flag) == {"term", "suggestion", "excerpt", "line"}
        assert flag["term"] in flag["excerpt"]


def test_funeral_manuscript_flags_the_hand_edited_phrases() -> None:
    flags = publish.plain_language_flags(FUNERAL.read_text(encoding="utf-8"))
    assert [(flag["line"], flag["term"], flag["suggestion"]) for flag in flags] == [
        (15, "신고의무자", "신고할 사람"),
        (19, "부과됩니다", "나옵니다"),
        (19, "관서", "관청"),
        (19, "최고", "독촉"),
        (25, "경우에는 방문 신청만 가능", "직접 방문해서만 신청할 수 있습니다"),
        (31, "1구당", "1명당"),
        (31, "장제를 실시한 사람", "장례를 치른 사람"),
        (45, "상속개시 있음을 안 날", "상속이 시작된 것을 안 날"),
        (45, "기산점", "시작하는 날"),
        (49, "출발점", "시작하는 날"),
        (49, "제각각", "항목마다 다릅니다"),
    ]


def test_publish_prints_flags_and_strict_fails(capsys, tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    source.write_text("# 제목\n\n신고의무자가 신청합니다.\n", encoding="utf-8")
    common = [
        str(source),
        "--category",
        "정부혜택",
        "--slug",
        "plain-check",
        "--date",
        "2026-11-13",
        "--no-related",
        "--dry-run",
        "--root",
        str(tmp_path),
    ]
    assert publish.publish(publish.parse_args(common)) is None
    text = capsys.readouterr().out
    assert text.index("PLAIN_LANG_FLAGS:") < text.index("PLAIN_LANG_STATUS:")
    assert "PLAIN_LANG_STATUS: flags=1" in text
    payload = json.loads(text.split("PLAIN_LANG_FLAGS: ", 1)[1].splitlines()[0])
    assert payload[0]["term"] == "신고의무자"
    assert payload[0]["suggestion"] == "신고할 사람"
    assert list(tmp_path.rglob("*")) == [source]

    try:
        publish.publish(publish.parse_args([*common, "--plain-lang-strict"]))
    except publish.PublishError as exc:
        assert "쉬운 말 검사" in str(exc)
    else:
        raise AssertionError("strict 모드에서는 실패해야 합니다.")
    strict_out = capsys.readouterr().out
    assert "PLAIN_LANG_STATUS: flags=1" in strict_out
    assert list(tmp_path.rglob("*")) == [source]


def test_flagged_heading_is_sent_and_dictionary_is_in_the_one_request(capsys, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    original = "# 제목\n\n## 신고의무자 안내\n\n본문 문장입니다.\n\n| 관서 | 1 |\n| --- | --- |\n"
    seen: dict[str, str] = {}

    def fake(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        seen["system"] = system_prompt
        seen["user"] = user_prompt
        rows = _rows_from_prompt(user_prompt)
        return "gemini-3.8-flash", json.dumps(
            [
                {"id": item["id"], "text": item["text"].replace("신고의무자", "신고할 사람"), "merged_with_next": False}
                for item in rows
            ],
            ensure_ascii=False,
        )

    monkeypatch.setattr(publish, "call_polish_models", fake)
    result = publish.polish_markdown(original)
    rows = _rows_from_prompt(seen["user"])
    flagged = [row for row in rows if row.get("plain_language")]
    assert len(flagged) == 1
    assert flagged[0]["text"] == "신고의무자 안내"
    assert "## 신고할 사람 안내" in result
    assert "| 관서 | 1 |" not in seen["user"].split("PLAIN_DICTIONARY:", 1)[-1].split("SENTENCES_JSON:", 1)[-1]
    assert "| 관서 | 1 |" in result
    assert "PLAIN_DICTIONARY:" in seen["user"]
    assert "신고의무자" in seen["user"].split("PLAIN_DICTIONARY:", 1)[1].split("PLAIN_LANG_HITS:", 1)[0]
    assert '"id": 1' in seen["user"].split("PLAIN_LANG_HITS:", 1)[1].split("SENTENCES_JSON:", 1)[0]
    assert seen["user"].count("SENTENCES_JSON:") == 1
    assert "쉬운 말" in seen["system"]
    assert "직접 방문해서만 신청할 수 있습니다" in seen["system"]
    status = capsys.readouterr().out
    assert "POLISH_STATUS: ok model=gemini-3.8-flash" in status


def test_workflow_exposes_plain_lang_strict_and_polish_models() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "plain_lang_strict:" in text
    assert "gemini_polish_models:" in text
    assert "GEMINI_POLISH_MODELS:" in text
    assert 'cmd+=(--plain-lang-strict)' in text
    assert "deploy-pages.yml --ref main" in text
