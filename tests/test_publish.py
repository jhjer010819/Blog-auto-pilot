import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import publish  # noqa: E402


FIXTURE = ROOT / "examples" / "fixture-post.md"
APPROVED_TITLE = "사관학교 신체검사 불합격 기준과 입시 지원자 재검 대처법"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_publish(root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "publish.py"), *args, "--root", str(root)]
    return subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        env=env if env is not None else os.environ.copy(),
        check=False,
    )


class PublishTests(unittest.TestCase):
    def test_fixture_becomes_post_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--slug",
                "format-check",
                "--date",
                "2026-11-10",
                "--no-related",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            destination = root / "content" / "posts" / "format-check.html"
            text = destination.read_text(encoding="utf-8")
            self.assertTrue(text.startswith('<script type="application/json" id="post-meta">'))
            meta, body = publish.parse_post_file(text)
            self.assertEqual(
                list(meta.keys()),
                ["title", "category", "date", "cover", "description", "related"],
            )
            self.assertEqual(meta["title"], "게시 형식 확인용 예시")
            self.assertEqual(
                meta["description"],
                "이 파일은 게시 스크립트가 표, 제목, 강조, 목록을 지키는지 확인하는 짧은 예시입니다. 실제 게시 글이 아닙니다.",
            )
            self.assertNotIn("첫 번째 소제목", meta["description"])
            self.assertEqual(meta["category"], "생활정보")
            self.assertEqual(meta["date"], "2026-11-10")
            self.assertEqual(meta["cover"], "/images/cover.jpg")
            self.assertEqual(meta["related"], [])
            self.assertIn("<h2>첫 번째 소제목</h2>", body)
            self.assertIn("<h3>세부 항목</h3>", body)
            self.assertIn("<strong>굵은 글</strong>", body)
            self.assertIn("<li>첫째</li>", body)
            self.assertIn("<li>둘째</li>", body)
            self.assertIn("<table>", body)
            self.assertIn("예시", body)
            self.assertIn("전문의와 상담하시기 바랍니다.", body)
            self.assertIn("공식 기관 공고를 확인해 주세요.", body)
            self.assertIn('<p class="post-disclaimer">', body)
            self.assertEqual(body.count("post-disclaimer"), 1)
            self.assertNotIn("<h1>", body.lower())
            self.assertNotIn("<!doctype", text.lower())
            self.assertNotIn("<html", text.lower())
            self.assertNotIn("함께 읽으면 유용한 정보", text)
            self.assertNotIn("개인정보 처리방침", text)
            self.assertNotIn("이용약관", text)
            self.assertNotIn("adsbygoogle", text)
            self.assertFalse((root / "index.html").exists())
            self.assertFalse((root / "post-template.html").exists())
            self.assertNotIn(APPROVED_TITLE, text)

    def test_same_slug_updates_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.md"
            second = root / "second.md"
            write_text(first, "# 첫 제목\n\n본문입니다.\n")
            write_text(second, "# 고친 제목\n\n본문을 고쳤습니다.\n")
            common = [
                "--category",
                "생활정보",
                "--slug",
                "same-slug",
                "--date",
                "2026-11-10",
                "--no-related",
                "--cover",
                "/images/cover.jpg",
            ]
            self.assertEqual(run_publish(root, str(first), *common).returncode, 0)
            self.assertEqual(run_publish(root, str(second), *common).returncode, 0)
            files = list((root / "content" / "posts").glob("*.html"))
            self.assertEqual([path.name for path in files], ["same-slug.html"])
            meta, body = publish.parse_post_file(files[0].read_text(encoding="utf-8"))
            self.assertEqual(meta["title"], "고친 제목")
            self.assertIn("본문을 고쳤습니다.", body)
            again = run_publish(root, str(second), *common)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(
                files[0].read_text(encoding="utf-8"),
                (root / "content" / "posts" / "same-slug.html").read_text(encoding="utf-8"),
            )

    def test_auto_related_uses_newest_posts_and_skips_self(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content" / "posts"
            write_text(posts / "older.html", sample_post("오래된 글", "2020-01-01"))
            write_text(posts / "newer.html", sample_post("최근 글", "2026-02-02"))
            write_text(posts / "target.html", sample_post("기존 제목", "2024-04-04"))
            source = root / "draft.md"
            write_text(source, "# 새 글\n\n본문입니다.\n")
            result = run_publish(
                root,
                str(source),
                "--category",
                "건강",
                "--slug",
                "target",
                "--date",
                "2026-11-10",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            meta, _body = publish.parse_post_file((posts / "target.html").read_text(encoding="utf-8"))
            self.assertEqual(
                meta["related"],
                [
                    {"title": "최근 글", "href": "/posts/newer/"},
                    {"title": "오래된 글", "href": "/posts/older/"},
                ],
            )
            self.assertNotIn("target", json.dumps(meta["related"], ensure_ascii=False))

    def test_front_matter_and_explicit_related(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "post.md"
            write_text(
                source,
                textwrap.dedent(
                    """\
                    ---
                    title: 프론트 제목
                    category: 정책·제도
                    description: 지정한 설명입니다.
                    date: 2026-03-03
                    slug: front-slug
                    cover: /images/cover.jpg
                    related:
                      - title: 다른 글
                        href: /posts/other
                    ---
                    # 프론트 제목

                    본문입니다.
                    """
                ),
            )
            result = run_publish(root, str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            meta, _body = publish.parse_post_file(
                (root / "content" / "posts" / "front-slug.html").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["title"], "프론트 제목")
            self.assertEqual(meta["category"], "정책·제도")
            self.assertEqual(meta["description"], "지정한 설명입니다.")
            self.assertEqual(meta["date"], "2026-03-03")
            self.assertEqual(meta["cover"], "/images/cover.jpg")
            self.assertEqual(meta["related"], [{"title": "다른 글", "href": "/posts/other/"}])

    def test_dry_run_does_not_write_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--dry-run",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("파일은 쓰지 않았습니다", result.stdout)
            self.assertIn("푸시: 하지 않음", result.stdout)
            self.assertIn("320×320 JPEG를 생성합니다", result.stdout)
            self.assertIn("이미지 API를 호출하지 않고", result.stdout)
            self.assertEqual(list((root / "content").glob("**/*")), [])

    def test_failures_exit_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = run_publish(root, str(root / "missing.md"), "--category", "예시")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("찾을 수 없습니다", missing.stderr)

            empty = root / "empty.md"
            write_text(empty, "   \n")
            empty_result = run_publish(root, str(empty), "--category", "예시")
            self.assertNotEqual(empty_result.returncode, 0)
            self.assertIn("비어 있습니다", empty_result.stderr)

            untitled = root / "untitled.md"
            write_text(untitled, "제목 표시가 없습니다.\n")
            untitled_result = run_publish(root, str(untitled), "--category", "예시")
            self.assertNotEqual(untitled_result.returncode, 0)
            self.assertIn("제목", untitled_result.stderr)

            bad_date = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--date",
                "2026/11/10",
            )
            self.assertNotEqual(bad_date.returncode, 0)

            no_category = run_publish(root, str(FIXTURE))
            self.assertNotEqual(no_category.returncode, 0)
            self.assertIn("분류", no_category.stderr)

            both = run_publish(root, str(FIXTURE), "--category", "예시", "--dry-run", "--push")
            self.assertNotEqual(both.returncode, 0)
            self.assertFalse((root / "content" / "posts").exists())

    def test_polish_without_api_key_exits_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--polish",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GEMINI_API_KEY", result.stderr)
            self.assertFalse((root / "content" / "posts").exists())

    def test_import_does_not_require_api_key(self) -> None:
        env = os.environ.copy()
        env.pop("GEMINI_API_KEY", None)
        result = subprocess.run(
            [sys.executable, "-c", "import publish"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_polish_guards(self) -> None:
        original = long_article()
        self.assertGreaterEqual(publish.manuscript_length(original), 1800)
        self.assertLessEqual(publish.manuscript_length(original), 2500)
        self.assertEqual(publish.validate_polish(original, original), [])

        changed_heading = original.replace("## 기준", "## 바꾼 기준", 1)
        self.assertTrue(publish.validate_polish(original, changed_heading))

        changed_number = original.replace("0.6", "0.7", 1)
        self.assertTrue(any("숫자" in problem for problem in publish.validate_polish(original, changed_number)))

        dropped = original.replace(
            "본 글은 정보 제공을 목적으로 작성되었으며, 정확한 진단 및 치료는 반드시 전문의와 상담하시기 바랍니다.",
            "참고만 하세요.",
            1,
        )
        self.assertTrue(any("고지" in problem for problem in publish.validate_polish(original, dropped)))

        casual = original.replace("불합격입니다.", "불합격이에요.", 1)
        self.assertTrue(any("해요체" in problem for problem in publish.validate_polish(original, casual)))

        shortened = "# 제목\n\n짧습니다.\n"
        self.assertTrue(publish.validate_polish(original, shortened))

    def test_dry_run_polish_prints_marked_markdown_without_writing(self) -> None:
        original = long_article()
        bad = original.replace("0.6", "0.7", 1)
        good = original.replace("확인해야 합니다.", "점검해야 합니다.", 1)
        self.assertTrue(any("숫자" in problem for problem in publish.validate_polish(original, bad)))
        self.assertEqual(publish.validate_polish(original, good), [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, original)
            args = publish.parse_args(
                [
                    str(source),
                    "--category",
                    "건강",
                    "--slug",
                    "polish-preview",
                    "--date",
                    "2026-11-12",
                    "--no-related",
                    "--dry-run",
                    "--polish",
                    "--root",
                    str(root),
                ]
            )
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(publish, "call_gemini", side_effect=[bad, good]) as gemini,
                patch.object(publish, "fetch_cover_image_bytes", side_effect=AssertionError("image api")),
                patch.object(publish, "request_cover_stem", side_effect=AssertionError("name api")),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertIsNone(publish.publish(args))
            self.assertEqual(gemini.call_count, 2)
            text = stdout.getvalue()
            self.assertIn("파일은 쓰지 않았습니다", text)
            self.assertIn("이미지 API를 호출하지 않고", text)
            self.assertIn("320×320 JPEG를 생성합니다", text)
            body = polished_between_markers(text)
            self.assertEqual(body, good.strip("\n"))
            self.assertIn("점검해야 합니다.", body)
            self.assertIn("0.6", body)
            self.assertNotIn("0.7", body)
            self.assertIn("# 제목", body)
            self.assertIn("## 기준", body)
            for disclaimer in publish._DISCLAIMERS:
                self.assertIn(disclaimer, body)
            self.assertEqual([path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()], ["draft.md"])

    def test_failed_polish_does_not_print_or_write(self) -> None:
        original = long_article()
        bad = original.replace("0.6", "0.7", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, original)
            args = publish.parse_args(
                [
                    str(source),
                    "--category",
                    "건강",
                    "--dry-run",
                    "--polish",
                    "--no-related",
                    "--root",
                    str(root),
                ]
            )
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(publish, "call_gemini", side_effect=[bad, bad]),
                patch.object(publish, "fetch_cover_image_bytes", side_effect=AssertionError("image api")),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                with self.assertRaises(publish.PublishError):
                    publish.publish(args)
            self.assertNotIn("=== POLISHED START ===", stdout.getvalue())
            self.assertEqual(list(root.rglob("*")), [source])

    def test_publish_polish_does_not_print_review_markers(self) -> None:
        original = long_article()
        good = original.replace("확인해야 합니다.", "점검해야 합니다.", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, original)
            args = publish.parse_args(
                [
                    str(source),
                    "--category",
                    "건강",
                    "--slug",
                    "polish-write",
                    "--date",
                    "2026-11-12",
                    "--no-related",
                    "--cover",
                    "/images/cover.jpg",
                    "--polish",
                    "--root",
                    str(root),
                ]
            )
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
                patch.object(publish, "call_gemini", return_value=good),
                patch.object(publish, "fetch_cover_image_bytes", side_effect=AssertionError("image api")),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                destination = publish.publish(args)
            self.assertIsNotNone(destination)
            text = stdout.getvalue()
            self.assertNotIn("=== POLISHED START ===", text)
            written = (root / "content" / "posts" / "polish-write.html").read_text(encoding="utf-8")
            self.assertIn("점검해야 합니다.", written)
            self.assertIn("0.6", written)
            for disclaimer in publish._DISCLAIMERS:
                self.assertIn(disclaimer, written)

    def test_push_command_is_not_forced(self) -> None:
        command = publish.push_command("cursor/stage2-post-publisher-521f")
        self.assertEqual(
            command,
            ["git", "push", "origin", "HEAD:refs/heads/cursor/stage2-post-publisher-521f"],
        )
        self.assertFalse(any(part.startswith("+") or "force" in part for part in command))
        with self.assertRaises(publish.PublishError):
            publish.push_command("HEAD")

    def test_push_commits_only_the_post_to_the_current_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bare = tmp_path / "origin.git"
            work = tmp_path / "work"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
            git_config(work)
            write_text(work / "README.md", "base\n")
            subprocess.run(["git", "add", "README.md"], cwd=work, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=work, check=True)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=work, check=True, capture_output=True)
            write_text(work / "notes.txt", "남으면 안 되는 파일\n")
            subprocess.run(["git", "add", "notes.txt"], cwd=work, check=True)

            source = work / "draft.md"
            write_text(source, "# 푸시 확인\n\n본문입니다.\n")
            result = run_publish(
                work,
                str(source),
                "--category",
                "생활정보",
                "--slug",
                "push-check",
                "--date",
                "2026-11-10",
                "--no-related",
                "--cover",
                "/images/cover.jpg",
                "--push",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            shown = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:%s", "HEAD"],
                cwd=bare,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("글 게시: 푸시 확인", shown.stdout)
            self.assertIn("content/posts/push-check.html", shown.stdout)
            self.assertNotIn("notes.txt", shown.stdout)
            self.assertTrue((work / "notes.txt").is_file())
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=work,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("notes.txt", staged.stdout)

    def test_stage1_workflow_and_stage2_dispatch_contract(self) -> None:
        stage1 = (ROOT / ".github" / "workflows" / "keyword_selector.yml").read_text(encoding="utf-8")
        self.assertIn("python main.py", stage1)
        self.assertIn("secrets.GEMINI_API_KEY", stage1)
        self.assertIn("cron:", stage1)
        compile((ROOT / "main.py").read_text(encoding="utf-8"), "main.py", "exec")

        stage2 = (ROOT / ".github" / "workflows" / "publish_post.yml").read_text(encoding="utf-8")
        head, jobs = stage2.split("jobs:", 1)
        self.assertIn("workflow_dispatch:", head)
        self.assertNotIn("schedule:", head)
        self.assertNotIn("pull_request:", head)
        self.assertNotIn("\n  push:", head)
        self.assertIn("contents: write", stage2)
        self.assertIn("secrets.GEMINI_API_KEY", stage2)
        self.assertIn("python publish.py", jobs)
        self.assertIn('default: true', stage2)
        self.assertIn('default: false', stage2)
        self.assertIn('cmd+=(--cover "$COVER")', jobs)
        self.assertIn("polished_path:", head)
        self.assertIn("POLISHED_PATH:", jobs)
        self.assertIn('source_path="$POLISHED_PATH"', jobs)
        self.assertIn("use_polish=true", jobs)
        publisher = (ROOT / "publish.py").read_text(encoding="utf-8")
        self.assertIn("gemini-3.8-flash", publisher)
        self.assertIn("gemini-nano-banana-2.1", publisher)
        self.assertIn('"image_size": "1K"', publisher)
        self.assertIn("=== POLISHED START ===", publisher)
        self.assertIn("=== POLISHED END ===", publisher)

    def test_disclaimer_paragraphs_are_marked_without_changing_wording(self) -> None:
        health, policy = publish._DISCLAIMERS
        both = f"<p>{health} {policy}</p>"
        marked = publish.mark_disclaimer_paragraphs(both)
        self.assertEqual(marked, f'<p class="post-disclaimer">{health} {policy}</p>')
        self.assertEqual(publish.mark_disclaimer_paragraphs(marked), marked)

        separate = publish.mark_disclaimer_paragraphs(f"<p>{health}</p>\n<p>{policy}</p>")
        self.assertEqual(
            separate,
            f'<p class="post-disclaimer">{health}</p>\n<p class="post-disclaimer">{policy}</p>',
        )

        mixed = publish.mark_disclaimer_paragraphs(f"<p>마지막 안내입니다. {health} {policy}</p>")
        self.assertEqual(
            mixed,
            "<p>마지막 안내입니다.</p>\n"
            f'<p class="post-disclaimer">{health} {policy}</p>',
        )
        self.assertEqual(mixed.count(health), 1)
        self.assertEqual(mixed.count(policy), 1)

        self.assertEqual(
            publish.mark_disclaimer_paragraphs("<p>정부 정책은 바뀝니다.</p>"),
            "<p>정부 정책은 바뀝니다.</p>",
        )
        tagged = f"<p>안내 <strong>{health}</strong></p>"
        self.assertEqual(publish.mark_disclaimer_paragraphs(tagged), tagged)

        from_markdown = publish.markdown_to_html(f"본문입니다.\n\n{health}\n\n{policy}\n")
        self.assertEqual(from_markdown.count("post-disclaimer"), 2)
        self.assertIn(f'<p class="post-disclaimer">{health}</p>', from_markdown)
        self.assertIn(f'<p class="post-disclaimer">{policy}</p>', from_markdown)
        self.assertIn("<p>본문입니다.</p>", from_markdown)

    def test_description_uses_two_intro_sentences_and_skips_headings(self) -> None:
        html = (
            "<p>청년 월세 지원은 해마다 나이, 소득, 주택 기준이 조금씩 달라집니다. "
            "금액을 외우기보다, 올해 공고에서 빠지는 서류만 먼저 막으세요.</p>"
            "<h2>신청 전에 볼 것</h2><p>나이와 소득은 공고에 적힌 기준일을 따릅니다.</p>"
        )
        description = publish.description_from_html(html)
        self.assertEqual(
            description,
            "청년 월세 지원은 해마다 나이, 소득, 주택 기준이 조금씩 달라집니다. "
            "금액을 외우기보다, 올해 공고에서 빠지는 서류만 먼저 막으세요.",
        )
        self.assertNotIn("신청 전에 볼 것", description)
        self.assertNotIn("<", description)
        decimal = publish.description_from_plain(
            "나쁜 눈의 최대 교정시력이 0.6 미만이면 불합격입니다. 재검 서류를 기간 안에 냅니다."
        )
        self.assertIn("0.6", decimal)
        self.assertTrue(decimal.startswith("나쁜 눈"))
        self.assertTrue(decimal.endswith("냅니다."))

    def test_slug_comes_from_the_title_and_matches_the_site(self) -> None:
        expected = "sagwanhakgyo-sinchegeomsa-bulhapgyeok-gijungwa-ipsi-jiwonja-jaegeom-daecheobeop"
        self.assertEqual(publish.slugify(APPROVED_TITLE), expected)
        self.assertLessEqual(len(expected), 80)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "post-20261111.md"
            write_text(source, f"# {APPROVED_TITLE}\n\n본문입니다.\n")
            result = run_publish(
                root,
                str(source),
                "--category",
                "정부혜택",
                "--date",
                "2026-11-11",
                "--no-related",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            destination = root / "content" / "posts" / f"{expected}.html"
            self.assertTrue(destination.is_file())
            meta, body = publish.parse_post_file(destination.read_text(encoding="utf-8"))
            self.assertEqual(meta["title"], APPROVED_TITLE)
            self.assertNotIn("<h1>", body.lower())
            again = run_publish(
                root,
                str(source),
                "--category",
                "정부혜택",
                "--date",
                "2026-11-11",
                "--no-related",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(list((root / "content" / "posts").glob("*.html")), [destination])

    def test_related_reads_current_info_lab_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content" / "posts"
            write_text(
                posts / "2026-youth-rent-support.html",
                info_lab_post("2026 청년 월세 지원금 신청 자격 및 필수 서류 3가지", "2026-11-10"),
            )
            source = root / "draft.md"
            write_text(source, "# 새 정책 글\n\n첫 문장입니다. 둘째 문장입니다.\n")
            result = run_publish(
                root,
                str(source),
                "--category",
                "정부혜택",
                "--date",
                "2026-11-11",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            written = list(posts.glob("*.html"))
            self.assertEqual(len(written), 2)
            generated = next(path for path in written if path.name != "2026-youth-rent-support.html")
            meta, _body = publish.parse_post_file(generated.read_text(encoding="utf-8"))
            self.assertEqual(
                meta["related"],
                [
                    {
                        "title": "2026 청년 월세 지원금 신청 자격 및 필수 서류 3가지",
                        "href": "/posts/2026-youth-rent-support/",
                    }
                ],
            )

    def test_provided_cover_skips_generation_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--slug",
                "has-cover",
                "--date",
                "2026-11-10",
                "--no-related",
                "--cover",
                "/images/given.jpg",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            meta, _body = publish.parse_post_file(
                (root / "content" / "posts" / "has-cover.html").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["cover"], "/images/given.jpg")
            self.assertFalse((root / "public" / "images").exists())
            self.assertNotIn("이미지 API를 호출하지 않고", result.stdout)
            self.assertIn("표지: /images/given.jpg", result.stdout)

    def test_dry_run_with_key_does_not_call_image_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, "# 제목\n\n본문입니다.\n")
            args = cover_args(root, source, "dry-cover")
            args.dry_run = True
            with (
                patch.object(publish, "fetch_cover_image_bytes", side_effect=AssertionError("image api")),
                patch.object(publish, "request_cover_stem", side_effect=AssertionError("name api")),
                patch.dict(os.environ, {"GEMINI_API_KEY": "present"}),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertIsNone(publish.publish(args))
            self.assertIn("이미지 API를 호출하지 않고", stdout.getvalue())
            self.assertEqual(list(root.rglob("*")), [source])

    def test_generates_320_cover_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, "# 검진 안내\n\n본문입니다.\n")
            args = cover_args(root, source, "exam-note", category="건강")
            with (
                patch.object(publish, "request_cover_stem", return_value="clinic-room") as stem,
                patch.object(publish, "fetch_cover_image_bytes", return_value=png_bytes(120, 80)) as fetch,
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            ):
                destination = publish.publish(args)
            stem.assert_called_once()
            self.assertEqual(fetch.call_count, 1)
            prompt = fetch.call_args.args[1]
            self.assertIn("검진 안내", prompt)
            self.assertIn("건강", prompt)
            self.assertIn("1K", (ROOT / "publish.py").read_text(encoding="utf-8"))
            image = root / "public" / "images" / "clinic-room.jpg"
            self.assertTrue(image.is_file())
            meta, _body = publish.parse_post_file(destination.read_text(encoding="utf-8"))
            self.assertEqual(meta["cover"], "/images/clinic-room.jpg")
            self.assertEqual(jpeg_size(image.read_bytes()), (320, 320, "RGB"))
            self.assertLessEqual(image.stat().st_size, 20 * 1024)

    def test_generated_cover_does_not_overwrite_an_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "public" / "images" / "clinic-room.jpg"
            write_text(existing, "keep")
            source = root / "draft.md"
            write_text(source, "# 검진 안내\n\n본문입니다.\n")
            args = cover_args(root, source, "exam-note", category="건강")
            with (
                patch.object(publish, "request_cover_stem", return_value="clinic-room"),
                patch.object(publish, "fetch_cover_image_bytes", return_value=png_bytes(40, 40)),
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            ):
                destination = publish.publish(args)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
            meta, _body = publish.parse_post_file(destination.read_text(encoding="utf-8"))
            self.assertEqual(meta["cover"], "/images/clinic-room-2.jpg")
            self.assertEqual(jpeg_size((root / "public" / "images" / "clinic-room-2.jpg").read_bytes())[:2], (320, 320))

    def test_missing_cover_api_key_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "생활정보",
                "--slug",
                "no-key",
                "--date",
                "2026-11-10",
                "--no-related",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("GEMINI_API_KEY", result.stderr)
            self.assertIn("표지", result.stderr)
            self.assertFalse((root / "content").exists())
            self.assertFalse((root / "public").exists())

    def test_cover_generation_failure_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.md"
            write_text(source, "# 제목\n\n본문입니다.\n")
            args = cover_args(root, source, "failed-cover")
            with (
                patch.object(publish, "request_cover_stem", return_value="quiet-desk"),
                patch.object(
                    publish,
                    "fetch_cover_image_bytes",
                    side_effect=publish.PublishError("표지 이미지를 만들지 못했습니다: 503"),
                ),
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            ):
                with self.assertRaises(publish.PublishError) as caught:
                    publish.publish(args)
            self.assertIn("표지 이미지", str(caught.exception))
            self.assertFalse((root / "content").exists())
            self.assertFalse((root / "public" / "images").exists())

    def test_cover_request_uses_smallest_square_output_and_retries(self) -> None:
        calls: list[dict] = []

        class Interactions:
            def create(self, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    raise RuntimeError("temporary")
                return Mock(output_image=Mock(data=base64.b64encode(b"\xff\xd8jpeg").decode()))

        class Client:
            def __init__(self, api_key):
                self.api_key = api_key
                self.interactions = Interactions()

        created: list[Client] = []

        def client_factory(*_args, **kwargs):
            client = Client(kwargs.get("api_key"))
            created.append(client)
            return client

        fake = Mock()
        fake.Client = client_factory
        with (
            patch.object(publish, "load_genai", return_value=fake),
            patch.object(publish.time, "sleep") as sleep,
        ):
            data = publish.fetch_cover_image_bytes("secret", "a quiet room")
        self.assertEqual(data, b"\xff\xd8jpeg")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["model"], "gemini-nano-banana-2.1")
        self.assertEqual(calls[0]["input"], "a quiet room")
        self.assertEqual(calls[0]["response_format"]["image_size"], "1K")
        self.assertEqual(calls[0]["response_format"]["aspect_ratio"], "1:1")
        self.assertEqual(calls[0]["response_format"]["mime_type"], "image/jpeg")
        self.assertNotIn("2K", json.dumps(calls))
        self.assertNotIn("4K", json.dumps(calls))
        sleep.assert_called_once()
        self.assertEqual(created[0].api_key, "secret")

    def test_cover_request_fails_after_retry(self) -> None:
        class Interactions:
            calls = 0

            def create(self, **_kwargs):
                Interactions.calls += 1
                raise RuntimeError("still down")

        fake = Mock()
        fake.Client.return_value.interactions = Interactions()
        with (
            patch.object(publish, "load_genai", return_value=fake),
            patch.object(publish.time, "sleep") as sleep,
        ):
            with self.assertRaises(publish.PublishError) as caught:
                publish.fetch_cover_image_bytes("secret", "prompt")
        self.assertIn("still down", str(caught.exception))
        self.assertEqual(Interactions.calls, 2)
        sleep.assert_called_once()

    def test_normalize_cover_jpeg_downscales_and_compresses(self) -> None:
        from PIL import Image

        rng_colors = [(index * 37) % 256 for index in range(256)]
        image = Image.new("RGB", (1024, 640))
        pixels = image.load()
        for y in range(0, 640, 4):
            for x in range(0, 1024, 4):
                color = (
                    rng_colors[(x + y) % 256],
                    rng_colors[(x * 3 + y) % 256],
                    rng_colors[(x + y * 5) % 256],
                )
                for dy in range(4):
                    for dx in range(4):
                        pixels[x + dx, y + dy] = color
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        jpeg = publish.normalize_cover_jpeg(buffer.getvalue())
        self.assertEqual(jpeg_size(jpeg), (320, 320, "RGB"))
        self.assertLessEqual(len(jpeg), 20 * 1024)
        self.assertGreater(len(jpeg), 1024)

    def test_cover_stem_is_short_english_kebab(self) -> None:
        self.assertEqual(publish.normalize_cover_stem("Clinic Room\nextra"), "clinic-room")
        self.assertEqual(publish.normalize_cover_stem("`Year_End_Tax.jpg`"), "year-end-tax")
        self.assertEqual(publish.validate_cover_stem("youth-rent"), "youth-rent")
        with self.assertRaises(publish.PublishError):
            publish.validate_cover_stem("cover")
        with self.assertRaises(publish.PublishError):
            publish.validate_cover_stem("blog-photo")
        with patch.object(publish, "call_gemini", side_effect=["cover", "clinic-room"]) as call:
            self.assertEqual(publish.request_cover_stem("key", "제목", "건강"), "clinic-room")
        self.assertEqual(call.call_count, 2)
        with patch.object(publish, "call_gemini", side_effect=["!!!", "photo"]):
            with self.assertRaises(publish.PublishError) as caught:
                publish.request_cover_stem("key", "제목", "건강")
        self.assertIn("짧은 영문", str(caught.exception))

    def test_push_commits_generated_cover_with_the_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bare = tmp_path / "origin.git"
            work = tmp_path / "work"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
            git_config(work)
            write_text(work / "README.md", "base\n")
            subprocess.run(["git", "add", "README.md"], cwd=work, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=work, check=True)
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=work, check=True, capture_output=True)
            write_text(work / "notes.txt", "남으면 안 되는 파일\n")
            subprocess.run(["git", "add", "notes.txt"], cwd=work, check=True)

            source = work / "draft.md"
            write_text(source, "# 푸시 표지\n\n본문입니다.\n")
            args = cover_args(work, source, "push-cover")
            args.push = True
            with (
                patch.object(publish, "request_cover_stem", return_value="quiet-desk"),
                patch.object(publish, "fetch_cover_image_bytes", return_value=png_bytes(64, 40)),
                patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}),
            ):
                publish.publish(args)

            shown = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:%s", "HEAD"],
                cwd=bare,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("글 게시: 푸시 표지", shown.stdout)
            self.assertIn("content/posts/push-cover.html", shown.stdout)
            self.assertIn("public/images/quiet-desk.jpg", shown.stdout)
            self.assertNotIn("notes.txt", shown.stdout)
            self.assertTrue((work / "notes.txt").is_file())
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=work,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("notes.txt", staged.stdout)
            self.assertEqual(
                jpeg_size((work / "public" / "images" / "quiet-desk.jpg").read_bytes())[:2],
                (320, 320),
            )

    def test_image_libraries_import_without_breaking_text_gemini(self) -> None:
        genai = publish.load_genai()
        self.assertTrue(hasattr(genai, "Client"))
        import google.generativeai as generativeai

        self.assertTrue(hasattr(generativeai, "GenerativeModel"))


    def test_category_allowlist_accepts_nine_labels_and_rejects_others(self) -> None:
        expected = (
            "교육",
            "건강",
            "과학",
            "IT",
            "부동산",
            "정부혜택",
            "세금",
            "정책\u00b7제도",
            "생활정보",
        )
        self.assertEqual(publish.ALLOWED_CATEGORIES, expected)
        self.assertEqual(tuple(publish.CATEGORY_PURPOSES), expected)
        policy = expected[7]
        self.assertEqual(policy[2], "\u00b7")
        self.assertNotEqual(policy[2], "\u30fb")
        for category in expected:
            self.assertEqual(publish.validate_category(f"  {category}  "), category)
        for bad in ("", "예시", "정책", "IT생활", "it", "정책.제도", "정책\u30fb제도"):
            with self.assertRaises(publish.PublishError):
                publish.validate_category(bad)

        prompt = publish.category_selection_prompt()
        for category in expected:
            self.assertIn(category, prompt)
        self.assertIn("목적", prompt)
        self.assertIn("realtime_trending", prompt)
        self.assertIn("fallback_sample", prompt)
        self.assertIn("사관학교", prompt)
        self.assertIn("청년 월세", prompt)
        self.assertIn("스타벅스", prompt)
        self.assertIn("건강 조언", prompt)
        self.assertIn("지원금 신청은 여기에 넣지 않는다", prompt)

        selector = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("category_selection_prompt()", selector)
        self.assertIn("validate_category(", selector)
        self.assertIn("글의 목적", selector)
        self.assertNotIn("IT생활", selector)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        posts_ts = (ROOT / "src" / "lib" / "posts.ts").read_text(encoding="utf-8")
        for category in expected:
            self.assertIn(category, readme)
            self.assertIn(category, posts_ts)
        self.assertIn("같은 분류", readme)
        self.assertIn("다른 분류", readme)
        self.assertIn("ALLOWED_CATEGORIES", posts_ts)

    def test_invalid_category_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bad in ("예시", "정책", "IT생활", "정책\u30fb제도"):
                result = run_publish(
                    root,
                    str(FIXTURE),
                    "--category",
                    bad,
                    "--slug",
                    "rejected",
                    "--date",
                    "2026-11-10",
                    "--no-related",
                    "--cover",
                    "/images/cover.jpg",
                )
                self.assertNotEqual(result.returncode, 0, bad)
                self.assertIn("허용", result.stderr)
                self.assertIn(bad, result.stderr)
                self.assertFalse((root / "content" / "posts").exists())

            source = root / "front.md"
            write_text(
                source,
                textwrap.dedent(
                    """\
                    ---
                    category: 정책
                    ---
                    # 프론트 제목

                    본문입니다.
                    """
                ),
            )
            front = run_publish(root, str(source), "--cover", "/images/cover.jpg", "--no-related")
            self.assertNotEqual(front.returncode, 0)
            self.assertIn("허용", front.stderr)
            self.assertIn("정책", front.stderr)
            self.assertFalse((root / "content" / "posts").exists())

    def test_each_allowed_category_passes_without_api_key(self) -> None:
        env = os.environ.copy()
        env.pop("GEMINI_API_KEY", None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for category in publish.ALLOWED_CATEGORIES:
                result = run_publish(
                    root,
                    str(FIXTURE),
                    "--category",
                    category,
                    "--dry-run",
                    "--no-related",
                    env=env,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"분류: {category}", result.stdout)
            self.assertEqual(list((root / "content").glob("**/*")), [])

    def test_auto_related_same_category_does_not_pad(self) -> None:
        posts = [
            {"slug": "old-health", "title": "오래된 건강", "date": "2020-01-01", "category": "건강"},
            {"slug": "new-tax", "title": "최신 세금", "date": "2026-08-01", "category": "세금"},
            {"slug": "mid-life", "title": "생활", "date": "2026-05-05", "category": "생활정보"},
            {"slug": "also-health", "title": "다른 건강", "date": "2024-04-04", "category": "건강"},
            {"slug": "self", "title": "자기", "date": "2026-11-11", "category": "건강"},
            {"slug": "h1", "title": "하나", "date": "2026-01-01", "category": "건강"},
            {"slug": "h2", "title": "둘", "date": "2026-02-02", "category": "건강"},
            {"slug": "h3", "title": "셋", "date": "2026-03-03", "category": "건강"},
        ]
        related = publish.auto_related(posts, "self", "건강")
        self.assertEqual([item["title"] for item in related], ["셋", "둘", "하나"])
        blob = json.dumps(related, ensure_ascii=False)
        self.assertNotIn("세금", blob)
        self.assertNotIn("생활", blob)
        self.assertNotIn("fieldtrip", blob)
        self.assertNotIn("tone", blob)
        self.assertTrue(all(set(item) == {"title", "href"} for item in related))
        self.assertTrue(all(item["href"].startswith("/posts/") for item in related))

        only_one = [post for post in posts if post["slug"] in {"old-health", "new-tax", "self"}]
        self.assertEqual(
            publish.auto_related(only_one, "self", "건강"),
            [{"title": "오래된 건강", "href": "/posts/old-health/"}],
        )

    def test_auto_related_falls_back_only_when_category_has_no_siblings(self) -> None:
        posts = [
            {"slug": "a", "title": "A", "date": "2026-01-01", "category": "세금"},
            {"slug": "b", "title": "B", "date": "2026-03-03", "category": "IT"},
            {"slug": "c", "title": "C", "date": "2026-05-05", "category": "부동산"},
            {"slug": "d", "title": "D", "date": "2024-01-01", "category": "생활정보"},
            {"slug": "self", "title": "자기", "date": "2026-11-11", "category": "교육"},
        ]
        related = publish.auto_related(posts, "self", "교육")
        self.assertEqual(
            [item["href"] for item in related],
            ["/posts/c/", "/posts/b/", "/posts/a/"],
        )
        self.assertNotIn("/posts/d/", [item["href"] for item in related])
        self.assertNotIn("/posts/self/", [item["href"] for item in related])

        posts.append({"slug": "edu", "title": "입학", "date": "2020-01-01", "category": "교육"})
        self.assertEqual(
            publish.auto_related(posts, "self", "교육"),
            [{"title": "입학", "href": "/posts/edu/"}],
        )

    def test_publish_related_prefers_same_category_and_skips_tool_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content" / "posts"
            write_text(posts / "old-health.html", sample_post("오래된 건강 글", "2020-01-01", "건강"))
            tool_meta = {
                "title": "최신 세금 글",
                "category": "세금",
                "date": "2026-08-01",
                "cover": "",
                "related": [
                    {
                        "title": "[추천 툴] 초등 체험학습 보고서 3초 자동 생성기",
                        "href": "https://fieldtrip.mymallow.cloud/",
                        "tone": "tool",
                    }
                ],
            }
            write_text(posts / "new-tax.html", publish.render_post_file(tool_meta, "<p>본문</p>"))
            before = (posts / "new-tax.html").read_text(encoding="utf-8")
            self.assertIn("fieldtrip.mymallow.cloud", before)
            self.assertIn('"tone": "tool"', before)
            source = root / "draft.md"
            write_text(source, "# 새 건강 글\n\n본문입니다.\n")
            result = run_publish(
                root,
                str(source),
                "--category",
                "건강",
                "--slug",
                "new-health",
                "--date",
                "2026-11-11",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            meta, _body = publish.parse_post_file((posts / "new-health.html").read_text(encoding="utf-8"))
            self.assertEqual(
                meta["related"],
                [{"title": "오래된 건강 글", "href": "/posts/old-health/"}],
            )
            self.assertNotIn("fieldtrip", json.dumps(meta["related"], ensure_ascii=False))
            self.assertEqual((posts / "new-tax.html").read_text(encoding="utf-8"), before)

            overridden = run_publish(
                root,
                str(source),
                "--category",
                "건강",
                "--slug",
                "manual-health",
                "--date",
                "2026-11-11",
                "--cover",
                "/images/cover.jpg",
                "--related",
                "[추천 툴] 초등 체험학습 보고서 3초 자동 생성기|https://fieldtrip.mymallow.cloud/",
            )
            self.assertEqual(overridden.returncode, 0, overridden.stderr)
            manual, _body = publish.parse_post_file(
                (posts / "manual-health.html").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manual["related"],
                [
                    {
                        "title": "[추천 툴] 초등 체험학습 보고서 3초 자동 생성기",
                        "href": "https://fieldtrip.mymallow.cloud/",
                    }
                ],
            )

    def test_publish_related_falls_back_when_category_has_no_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content" / "posts"
            write_text(posts / "tax.html", sample_post("세금 글", "2026-01-01", "세금"))
            write_text(posts / "it.html", sample_post("IT 글", "2026-03-03", "IT"))
            write_text(posts / "land.html", sample_post("부동산 글", "2026-05-05", "부동산"))
            write_text(posts / "life.html", sample_post("생활 글", "2024-01-01", "생활정보"))
            source = root / "draft.md"
            write_text(source, "# 교육 글\n\n본문입니다.\n")
            result = run_publish(
                root,
                str(source),
                "--category",
                "교육",
                "--slug",
                "edu-note",
                "--date",
                "2026-11-11",
                "--cover",
                "/images/cover.jpg",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            meta, _body = publish.parse_post_file((posts / "edu-note.html").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["href"] for item in meta["related"]],
                ["/posts/land/", "/posts/it/", "/posts/tax/"],
            )
            self.assertNotIn("fieldtrip", json.dumps(meta["related"], ensure_ascii=False))

    def test_existing_posts_keep_tool_links_and_allowlisted_categories(self) -> None:
        posts = publish.load_existing_posts(ROOT / "content" / "posts")
        by_slug = {post["slug"]: post for post in posts}
        sagwan = "sagwanhakgyo-sinchegeomsa-bulhapgyeok-gijungwa-ipsi-jiwonja-jaegeom-daecheobeop"
        self.assertEqual(by_slug[sagwan]["category"], "교육")
        self.assertEqual(by_slug["2026-year-end-tax-refund"]["category"], "세금")
        self.assertEqual(by_slug["2026-youth-rent-support"]["category"], "정부혜택")
        self.assertEqual(by_slug["starbucks-winter-frequency"]["category"], "생활정보")

        benefit = publish.auto_related(posts, "brand-new", "정부혜택")
        benefit_hrefs = [item["href"] for item in benefit]
        self.assertIn("/posts/2026-youth-rent-support/", benefit_hrefs)
        self.assertNotIn(f"/posts/{sagwan}/", benefit_hrefs)
        self.assertLessEqual(len(benefit), publish.RELATED_LIMIT)
        self.assertTrue(all(item["href"].startswith("/posts/") for item in benefit))

        education = publish.auto_related(posts, "brand-new", "교육")
        self.assertEqual(education, [{"title": by_slug[sagwan]["title"], "href": f"/posts/{sagwan}/"}])

        science = publish.auto_related(posts, "brand-new", "과학")
        self.assertEqual(len(science), publish.RELATED_LIMIT)
        self.assertTrue(all(item["href"].startswith("/posts/") and "fieldtrip" not in item["href"] for item in science))

        tax = (ROOT / "content" / "posts" / "2026-year-end-tax-refund.html").read_text(encoding="utf-8")
        youth = (ROOT / "content" / "posts" / "2026-youth-rent-support.html").read_text(encoding="utf-8")
        life = (ROOT / "content" / "posts" / "starbucks-winter-frequency.html").read_text(encoding="utf-8")
        school = (ROOT / "content" / "posts" / f"{sagwan}.html").read_text(encoding="utf-8")
        for source, category in (
            (tax, "세금"),
            (youth, "정부혜택"),
            (life, "생활정보"),
            (school, "교육"),
        ):
            self.assertIn(f'"category": "{category}"', source)
        for source in (tax, youth, life):
            self.assertIn("https://fieldtrip.mymallow.cloud/", source)
            self.assertIn('"tone": "tool"', source)
        self.assertNotIn("fieldtrip", school)
        self.assertIn("/posts/2026-youth-rent-support/", school)
        self.assertIn("/posts/starbucks-winter-frequency/", school)
        self.assertIn("/posts/2026-year-end-tax-refund/", school)
        self.assertIn("2026 연말정산 환급금 3초 조회 방법", tax)
        self.assertIn(APPROVED_TITLE, school)


def polished_between_markers(text: str) -> str:
    start_mark = "=== POLISHED START ==="
    end_mark = "=== POLISHED END ==="
    start = text.index(start_mark) + len(start_mark)
    end = text.index(end_mark)
    return text[start:end].strip("\n")


def sample_post(title: str, date: str, category: str = "건강") -> str:
    meta = {
        "title": title,
        "category": category,
        "date": date,
        "cover": "",
        "related": [],
    }
    return publish.render_post_file(meta, "<p>본문</p>")


def long_article() -> str:
    sentence = "사관학교 지원 전 신체검사 기준은 모집요강과 해당 군 규정을 확인해야 합니다. "
    body = sentence * 40
    body += "나쁜 눈의 최대 교정시력이 0.6 미만이면 불합격입니다. "
    body += (
        "본 글은 정보 제공을 목적으로 작성되었으며, 정확한 진단 및 치료는 반드시 전문의와 상담하시기 바랍니다. "
        "정부 정책 및 지원 기준은 시기별로 개정될 수 있으므로 정확한 내용은 공식 기관 공고를 확인해 주세요."
    )
    return f"# 제목\n\n## 기준\n\n{body}\n"


def info_lab_post(title: str, date: str) -> str:
    meta = {
        "title": title,
        "category": "정부혜택",
        "date": date,
        "thumbnail": "/images/youth-rent.jpg",
        "thumbnailAlt": title,
        "links": [],
    }
    payload = json.dumps(meta, ensure_ascii=False, indent=2)
    return f'<script type="application/json" id="post-meta">\n{payload}\n</script>\n<p>본문</p>\n'


def cover_args(root: Path, source: Path, slug: str, category: str = "생활정보") -> publish.argparse.Namespace:
    return publish.parse_args(
        [
            str(source),
            "--category",
            category,
            "--slug",
            slug,
            "--date",
            "2026-11-11",
            "--no-related",
            "--root",
            str(root),
        ]
    )


def png_bytes(width: int, height: int) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), (180, 90, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_size(data: bytes) -> tuple[int, int, str]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return image.size[0], image.size[1], image.mode


def git_config(repo: Path) -> None:
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Publish Test"], cwd=repo, check=True)


if __name__ == "__main__":
    unittest.main()
