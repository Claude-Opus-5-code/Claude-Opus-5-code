"""CLI application shell.

Migrated from source L176-189 + L308-324 (`send_chat_request` presentation),
L326-340 (`interactive_chat_mode`), and L342-400 (`main`).

This module reproduces the original script's user-facing behavior on top of the
V3-structured runtime. It is NOT part of the provider contract surface: the Core
never calls it. It exists so the migrated package remains a faithful,
runnable replacement for the original script (README §2).
"""

from __future__ import annotations

import argparse
import time
from typing import Callable, Sequence

from ..config import OverchatConfig
from ..discovery.models import resolve_model
from ..operations.text_generation import generate_text
from ..runtime.headers import build_mobile_headers
from ..runtime.session import Transport
from .banner import print_banner, print_input_stats, print_output_stats
from .colors import Fore, Style
from .file_io import read_input_content, write_output
from .stats import input_stats, output_stats

#: Source L334: exit words, matched case-insensitively.
EXIT_WORDS = ("exit", "quit", "خروج", "q")


def _default_transport() -> Transport:
    """Real transport: the `requests` module itself (source uses it directly)."""
    import requests

    return requests  # type: ignore[return-value]


def send_chat_request(
    prompt_text: str,
    config: OverchatConfig,
    source_label: str = "مباشر",
    *,
    transport: Transport | None = None,
    printer: Callable[[str], None] = print,
    writer: Callable[[str], None] | None = None,
) -> str | None:
    """Full original request cycle including printing and file saving.

    Source `send_chat_request` L176-324. Returns the reply text, or None on
    failure - the exact return contract of the source.
    """
    active_transport = _default_transport() if transport is None else transport

    stats_in = input_stats(prompt_text)
    print_input_stats(stats_in, config, source_label, printer=printer)

    printer(
        f"{Fore.YELLOW}⏳ جاري إرسال السؤال لـ [{config.persona_id}] "
        f"واستقبال الرد...{Style.RESET_ALL}\n"
    )
    printer(
        f"{Fore.GREEN}🤖 الرد المباشر ({config.persona_id}):{Style.RESET_ALL}\n"
        f"{Fore.CYAN}{'─' * 74}{Style.RESET_ALL}"
    )

    emit = writer if writer is not None else _stdout_writer

    def _on_delta(delta: str) -> None:
        # Source L284-285: incremental write + flush.
        emit(f"{Fore.WHITE}{delta}{Style.RESET_ALL}")

    def _on_stream_error(message: object) -> None:
        # Source L288: reported, non-terminal.
        printer(
            f"\n{Fore.RED}⚠️ خطأ من السيرفر أثناء التدفق: "
            f"{message}{Style.RESET_ALL}"
        )

    t0 = time.time()  # source L265
    result = generate_text(
        prompt_text,
        config,
        active_transport,
        on_delta=_on_delta,
        on_stream_error=_on_stream_error,
    )

    if not result.ok:
        assert result.error is not None
        stage = result.error.metadata.get("stage", "generation")
        body = result.error.metadata.get("raw_body_truncated", "")
        code = result.error.provider_code
        if stage == "auth":
            # Source L198-199.
            printer(
                f"{Fore.RED}❌ فشل جلب معرف المستخدم ({code}): "
                f"{body}{Style.RESET_ALL}"
            )
        else:
            # Source L319.
            printer(
                f"\n{Fore.RED}❌ فشل الطلب ({code}): {body}{Style.RESET_ALL}\n"
            )
        return None  # source returns None on every failure path

    elapsed = time.time() - t0  # source L292
    stats_out = output_stats(result.text, elapsed)
    print_output_stats(stats_out, config, printer=printer)

    write_output(result.text, config, printer=printer)  # source L308-314
    return result.text


def _stdout_writer(text: str) -> None:
    """Source L284-285: write to stdout and flush immediately."""
    import sys

    sys.stdout.write(text)
    sys.stdout.flush()


def interactive_chat_mode(
    config: OverchatConfig,
    *,
    transport: Transport | None = None,
    printer: Callable[[str], None] = print,
    reader: Callable[[str], str] | None = None,
) -> None:
    """Interactive line-by-line chat.

    Source L326-340, preserved: blank input is skipped, the four exit words end
    the loop case-insensitively, and KeyboardInterrupt/EOFError break cleanly.
    """
    ask = reader if reader is not None else input
    printer(
        f"{Fore.YELLOW}💬 الوضع التفاعلي جاهز (الموديل: {config.persona_id}) - "
        f"اكتب 'exit' للخروج:{Style.RESET_ALL}\n"
    )
    while True:
        try:
            user_text = ask(f"{Fore.WHITE}👤 أنت: {Style.RESET_ALL}").strip()
            if not user_text:  # source L332-333
                continue
            if user_text.lower() in EXIT_WORDS:  # source L334
                printer(f"{Fore.RED}👋 سلام يا ريس!{Style.RESET_ALL}")
                break
            send_chat_request(
                user_text,
                config,
                "شات تفاعلي",
                transport=transport,
                printer=printer,
            )
        except (KeyboardInterrupt, EOFError):  # source L338-340
            printer(f"\n{Fore.RED}⛔ تم إيقاف الجلسة.{Style.RESET_ALL}")
            break


def build_parser() -> argparse.ArgumentParser:
    """Source L344-353: the exact flag surface, including short options."""
    parser = argparse.ArgumentParser(
        description="Overchat Dual-Models Master ByPass Hub"
    )
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من التيرمينال")
    parser.add_argument("--model", "-m", type=str, default=None)
    parser.add_argument("--file", "-f", type=str, default=None)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--max-lines", "-l", type=int, default=None)
    parser.add_argument("--max-chars", "-c", type=int, default=None)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--cli", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    transport: Transport | None = None,
    printer: Callable[[str], None] = print,
    reader: Callable[[str], str] | None = None,
) -> int:
    """Entry point.

    Source `main` L342-400. Dispatch precedence is preserved exactly:
    --list-models > positional prompt > --cli > input file > interactive.
    """
    args = build_parser().parse_args(argv)
    config = OverchatConfig()

    if args.list_models:  # source L357-362
        printer(
            f"\n{Fore.CYAN}📋 قائمة الموديلات المجانية المتاحة في السكربت:"
            f"{Style.RESET_ALL}"
        )
        for pid, meta in config.available_models.items():
            printer(
                f"  • {Fore.YELLOW}{pid:<22}{Style.RESET_ALL} "
                f"({meta['model']}) -> {meta['desc']}"
            )
        printer("")
        return 0

    if args.model:  # source L364-370 (incl. unknown-model passthrough)
        persona_id, model = resolve_model(args.model)
        config = config.with_values(persona_id=persona_id, model=model)

    # Source L372-379.
    if args.file:
        config = config.with_values(input_file=args.file)
    if args.output:
        config = config.with_values(output_file=args.output)
    if args.max_lines:
        config = config.with_values(max_lines=args.max_lines)
    if args.max_chars:
        config = config.with_values(max_chars=args.max_chars)

    # Source L381-382: headers minted purely for the banner, then discarded.
    _headers, dev_id, sp_ip = build_mobile_headers(
        include_ip_spoof_headers=config.include_ip_spoof_headers,
    )
    print_banner(config, dev_id, sp_ip, printer=printer)

    if args.prompt:  # source L384-387
        direct_prompt = " ".join(args.prompt).strip()
        send_chat_request(
            direct_prompt,
            config,
            "CLI Argument",
            transport=transport,
            printer=printer,
        )
        return 0

    if args.cli:  # source L389-391
        interactive_chat_mode(
            config, transport=transport, printer=printer, reader=reader
        )
        return 0

    # Source L393-400: auto mode.
    content, label = read_input_content(config, printer=printer)
    if content:
        printer(
            f"{Fore.GREEN}📂 تم العثور على نص جاهز في: "
            f"{Fore.YELLOW}{config.input_file}{Style.RESET_ALL}"
        )
        send_chat_request(
            content, config, label, transport=transport, printer=printer
        )
    else:
        printer(
            f"{Fore.YELLOW}ℹ️ ملف {config.input_file} فارغ أو غير موجود. "
            f"تم التحويل للوضع التفاعلي.{Style.RESET_ALL}\n"
        )
        interactive_chat_mode(
            config, transport=transport, printer=printer, reader=reader
        )
    return 0
