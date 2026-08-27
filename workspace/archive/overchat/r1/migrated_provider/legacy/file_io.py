"""Input/output file handling.

Migrated from source L98 (`BASE_DIR`), L152-174 (`read_input_content`), and
L309-314 (reply saving).

PRESERVED SEMANTICS:
  * paths resolve against the PACKAGE directory, not the process CWD, because
    the source anchors on `pathlib.Path(__file__).resolve().parent` (L98);
  * `read_text(...).strip()` then `splitlines()` (L157-159);
  * the limit checks are FALSY checks (`if cfg.max_lines and ...`), so 0 is
    treated as "no limit" exactly as in the source (L160, L167);
  * the Arabic labels are returned verbatim - they are observable output;
  * a read failure warns and yields ("", "") rather than raising (L172-174);
  * a write failure warns but the reply is still returned by the caller
    (L313-314).
"""

from __future__ import annotations

import pathlib
from typing import Callable

from ..config import OverchatConfig
from .colors import Fore, Style

#: Source L98 equivalent: anchor on this module's package directory.
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def resolve_path(file_name: str, base_dir: pathlib.Path | None = None) -> pathlib.Path:
    """Resolve a configured file name against BASE_DIR (source L154, L309)."""
    root = BASE_DIR if base_dir is None else base_dir
    return root / file_name


def read_input_content(
    config: OverchatConfig,
    *,
    base_dir: pathlib.Path | None = None,
    printer: Callable[[str], None] = print,
) -> tuple[str, str]:
    """Read and optionally truncate the input file.

    Source L152-174, behavior-identical. Returns `(text, label)`; both are ""
    when the file is missing, empty, or unreadable.
    """
    target_path = resolve_path(config.input_file, base_dir)
    if target_path.exists():
        try:
            raw_text = target_path.read_text(encoding="utf-8").strip()
            if raw_text:
                lines = raw_text.splitlines()
                # Falsy check preserved from source L160.
                if config.max_lines and len(lines) > config.max_lines:
                    filtered_text = "\n".join(lines[: config.max_lines])
                    label = (
                        f"ملف ({config.input_file}) "
                        f"[تم تحديد أول {config.max_lines} سطر]"
                    )
                else:
                    filtered_text = raw_text
                    label = f"ملف ({config.input_file}) [كامل بدون ليمت]"

                # Falsy check preserved from source L167.
                if config.max_chars and len(filtered_text) > config.max_chars:
                    filtered_text = filtered_text[: config.max_chars]
                    label += f" [محدد بـ {config.max_chars} حرف]"

                return filtered_text, label
        except Exception as exc:  # noqa: BLE001 - source L172-173
            printer(
                f"{Fore.YELLOW}⚠️ تعذر قراءة ملف {config.input_file}: "
                f"{exc}{Style.RESET_ALL}"
            )
    return "", ""


def write_output(
    reply_text: str,
    config: OverchatConfig,
    *,
    base_dir: pathlib.Path | None = None,
    printer: Callable[[str], None] = print,
) -> bool:
    """Save the full reply.

    Source L308-314. A failure is reported but NOT fatal: the caller still
    returns the reply text. Returns True on success, False on failure.
    """
    out_path = resolve_path(config.output_file, base_dir)
    try:
        out_path.write_text(reply_text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - source L313-314
        printer(
            f"{Fore.YELLOW}⚠️ تعذر حفظ الرد في ملف: {exc}{Style.RESET_ALL}\n"
        )
        return False
    printer(
        f"{Fore.GREEN}💾 تم حفظ الرد كاملاً في: "
        f"{Fore.CYAN}{config.output_file}{Style.RESET_ALL}\n"
    )
    return True
