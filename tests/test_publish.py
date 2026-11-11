import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

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
                "예시",
                "--slug",
                "format-check",
                "--date",
                "2026-11-10",
                "--no-related",
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
            self.assertEqual(meta["category"], "예시")
            self.assertEqual(meta["date"], "2026-11-10")
            self.assertEqual(meta["cover"], "")
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
            self.assertNotIn("<h1>", body.lower())
            self.assertNotIn("<!doctype", text.lower())
            self.assertNotIn("<html", text.lower())
            self.assertNotIn("함께 읽으면 유용한 정보", text)
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
            common = ["--category", "예시", "--slug", "same-slug", "--date", "2026-11-10", "--no-related"]
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
                    category: 정책
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
            self.assertEqual(meta["category"], "정책")
            self.assertEqual(meta["date"], "2026-03-03")
            self.assertEqual(meta["cover"], "/images/cover.jpg")
            self.assertEqual(meta["related"], [{"title": "다른 글", "href": "/posts/other/"}])

    def test_dry_run_does_not_write_or_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_publish(
                root,
                str(FIXTURE),
                "--category",
                "예시",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("파일은 쓰지 않았습니다", result.stdout)
            self.assertIn("푸시: 하지 않음", result.stdout)
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
                "예시",
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
                "예시",
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
                "예시",
                "--slug",
                "push-check",
                "--date",
                "2026-11-10",
                "--no-related",
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
        self.assertIn("gemini-3.8-flash", (ROOT / "publish.py").read_text(encoding="utf-8"))

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
            result = run_publish(root, str(source), "--category", "정부혜택", "--date", "2026-11-11")
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


def sample_post(title: str, date: str) -> str:
    meta = {
        "title": title,
        "category": "예시",
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


def git_config(repo: Path) -> None:
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Publish Test"], cwd=repo, check=True)


if __name__ == "__main__":
    unittest.main()
