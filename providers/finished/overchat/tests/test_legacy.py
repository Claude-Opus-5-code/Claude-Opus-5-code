"""Legacy layer tests (README §17: preserved, isolated, documented).

These behaviors are NOT part of the V3 provider contract - they are the original
script's CLI/file/statistics surface. They were preserved rather than deleted,
so they must also be proven, particularly the falsy-limit quirk that a rewrite
would "fix" into a bug.
"""

from __future__ import annotations

import pathlib

from overchat.config import OverchatConfig
from overchat.legacy.file_io import read_input_content, resolve_path, write_output
from overchat.legacy.stats import CHARS_PER_TOKEN, input_stats, output_stats

CONFIG = OverchatConfig()


# --------------------------------------------------------------------------
# Statistics (source L178-189, L292-306)
# --------------------------------------------------------------------------


def test_input_stats_match_source_formulas() -> None:
    stats = input_stats("hello world\nsecond line")
    assert stats.chars == 23
    assert stats.lines == 2
    assert stats.words == 4


def test_approx_tokens_uses_the_source_3_5_divisor_and_int_truncation() -> None:
    """Source L181: `int(char_count / 3.5)` - truncation, not rounding."""
    assert CHARS_PER_TOKEN == 3.5
    assert input_stats("x" * 10).approx_tokens == 2  # 10/3.5 = 2.857 -> 2
    assert input_stats("x" * 7).approx_tokens == 2


def test_input_stats_on_empty_prompt() -> None:
    stats = input_stats("")
    assert (stats.chars, stats.lines, stats.words, stats.approx_tokens) == (0, 0, 0, 0)


def test_output_stats_speed_formula() -> None:
    stats = output_stats("x" * 100, 4.0)
    assert stats.chars == 100
    assert stats.chars_per_second == 25.0


def test_output_stats_zero_elapsed_does_not_divide_by_zero() -> None:
    """Source L296 guard: `if elapsed > 0 else 0`. Instant replies must not
    raise ZeroDivisionError."""
    stats = output_stats("abc", 0.0)
    assert stats.chars_per_second == 0


def test_output_stats_counts_lines_and_words_of_reply() -> None:
    stats = output_stats("one two\nthree", 1.0)
    assert stats.lines == 2
    assert stats.words == 3


# --------------------------------------------------------------------------
# File IO (source L152-174, L308-314)
# --------------------------------------------------------------------------


def test_read_returns_full_text_when_no_limits_are_set() -> None:
    """Default config has max_lines=None/max_chars=None: the source's headline
    'unlimited' behavior (L77-79)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("l1\nl2\nl3", encoding="utf-8")

        text, label = read_input_content(CONFIG, base_dir=base)

        assert text == "l1\nl2\nl3"
        assert "كامل بدون ليمت" in label


def test_read_applies_line_limit_when_set() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("l1\nl2\nl3\nl4", encoding="utf-8")

        text, label = read_input_content(CONFIG.with_values(max_lines=2), base_dir=base)

        assert text == "l1\nl2"
        assert "أول 2 سطر" in label


def test_read_applies_char_limit_when_set() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("abcdefghij", encoding="utf-8")

        text, label = read_input_content(CONFIG.with_values(max_chars=4), base_dir=base)

        assert text == "abcd"
        assert "محدد بـ 4 حرف" in label


def test_zero_limits_mean_no_limit_because_source_uses_falsy_checks() -> None:
    """Source L160/L167 use `if cfg.max_lines and ...`, so 0 is FALSY and means
    'no limit', NOT 'truncate to nothing'.

    A rewrite using `is not None` would silently truncate all input to empty.
    README §17 requires preserving this quirk.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("l1\nl2\nl3", encoding="utf-8")

        text, _ = read_input_content(
            CONFIG.with_values(max_lines=0, max_chars=0), base_dir=base
        )

        assert text == "l1\nl2\nl3"  # untruncated


def test_read_strips_surrounding_whitespace() -> None:
    """Source L157 calls .strip() on the raw text."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("\n\n  hello  \n\n", encoding="utf-8")

        text, _ = read_input_content(CONFIG, base_dir=base)
        assert text == "hello"


def test_missing_file_returns_empty_pair_without_raising() -> None:
    """Source falls through to `return "", ""` (L174), which makes main() switch
    to interactive mode instead of crashing."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        text, label = read_input_content(CONFIG, base_dir=pathlib.Path(tmp))
        assert (text, label) == ("", "")


def test_whitespace_only_file_returns_empty_pair() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("   \n  \n", encoding="utf-8")

        assert read_input_content(CONFIG, base_dir=base) == ("", "")


def test_unicode_content_is_read_as_utf8() -> None:
    """The provider's whole purpose is Arabic text; encoding must be explicit."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").write_text("مرحبا بالعالم", encoding="utf-8")

        text, _ = read_input_content(CONFIG, base_dir=base)
        assert text == "مرحبا بالعالم"


def test_write_output_saves_full_reply_as_utf8() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        messages: list[str] = []

        ok = write_output("الرد الكامل", CONFIG, base_dir=base, printer=messages.append)

        assert ok is True
        assert (base / "chat_reply.txt").read_text(encoding="utf-8") == "الرد الكامل"
        assert any("💾" in m for m in messages)


def test_write_failure_is_reported_but_not_raised() -> None:
    """Source L313-314: a save failure warns; the reply is still returned."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        # Make the target a DIRECTORY so write_text() fails.
        (base / "chat_reply.txt").mkdir()
        messages: list[str] = []

        ok = write_output("reply", CONFIG, base_dir=base, printer=messages.append)

        assert ok is False
        assert any("تعذر حفظ" in m for m in messages)


def test_read_failure_is_reported_but_not_raised() -> None:
    """Source L172-173 catches read errors and warns."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        (base / "chat_send.txt").mkdir()  # a directory: read_text() raises
        messages: list[str] = []

        text, label = read_input_content(CONFIG, base_dir=base, printer=messages.append)

        assert (text, label) == ("", "")
        assert any("تعذر قراءة" in m for m in messages)


def test_paths_resolve_against_package_dir_not_process_cwd() -> None:
    """Source L98 anchors on `Path(__file__).resolve().parent`, so behavior does
    NOT depend on where the process was launched."""
    resolved = resolve_path("chat_send.txt")
    assert resolved.is_absolute()
    assert resolved.name == "chat_send.txt"
    assert resolved.parent.name == "overchat"


def test_custom_output_file_name_is_honored() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        config = CONFIG.with_values(output_file="custom.txt")

        write_output("x", config, base_dir=base, printer=lambda _m: None)

        assert (base / "custom.txt").read_text(encoding="utf-8") == "x"
