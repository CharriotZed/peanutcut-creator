import os
import tempfile
import textwrap

from scripts.validate_skill import validate_skill_dir


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_missing_skill_md_is_reported():
    with tempfile.TemporaryDirectory() as d:
        problems = validate_skill_dir(d)
        assert any("SKILL.md" in p for p in problems)


def test_missing_frontmatter_fields_reported():
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "SKILL.md"), "# no frontmatter here\n")
        problems = validate_skill_dir(d)
        assert any("name" in p for p in problems)
        assert any("description" in p for p in problems)


def test_broken_reference_link_reported():
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "SKILL.md"),
            textwrap.dedent(
                """\
                ---
                name: sample
                description: sample skill
                ---
                See [topic](references/topic-selection.md).
                """
            ),
        )
        problems = validate_skill_dir(d)
        assert any("references/topic-selection.md" in p for p in problems)


def test_valid_skill_returns_no_problems():
    with tempfile.TemporaryDirectory() as d:
        _write(
            os.path.join(d, "SKILL.md"),
            textwrap.dedent(
                """\
                ---
                name: sample
                description: sample skill
                ---
                See [topic](references/topic-selection.md).
                """
            ),
        )
        _write(os.path.join(d, "references", "topic-selection.md"), "# topic\n")
        problems = validate_skill_dir(d)
        assert problems == []
