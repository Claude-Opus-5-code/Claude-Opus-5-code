"""Terminal banner and statistics rendering.

Migrated from source L127-150 (`print_banner`), L183-189 (input stats block),
and L298-306 (output stats block).

This is pure presentation, but it is real observable behavior of the original
provider, so it is preserved rather than dropped (README §17). It lives in
`legacy/` because V3 forbids provider presentation concerns from reaching the
Core; nothing in the V3 adapter path calls these functions.
"""

from __future__ import annotations

from typing import Callable

from ..config import OverchatConfig
from .colors import Fore, Style
from .stats import InputStats, OutputStats


def print_banner(
    config: OverchatConfig,
    device_id: str,
    spoofed_ip: str,
    *,
    printer: Callable[[str], None] = print,
) -> None:
    """Source L127-150, output preserved."""
    printer(f"\n{Fore.GREEN}╔{'═' * 74}╗")
    printer(
        "║  🟢 Overchat Dual-Models Master Bypass Hub (Free & Active 100%)        ║"
    )
    printer(
        f"║  🚀 تشغيل فوري بدون ليمت سطور/حروف + حفظ تلقائي في "
        f"{config.output_file:<18}║"
    )
    printer(f"╚{'═' * 74}╝{Style.RESET_ALL}")

    printer(f"{Fore.CYAN}🕵️  بيانات التخفي والمحاكاة:")
    printer(f"   📱 بصمة الموبايل الوهمي : {Fore.YELLOW}{device_id}{Style.RESET_ALL}")
    printer(f"   🌍 عنوان IP التمويه     : {Fore.YELLOW}{spoofed_ip}{Style.RESET_ALL}")

    printer(f"{Fore.GREEN}{'─' * 76}{Style.RESET_ALL}")
    printer(f"{Fore.CYAN}📋 الموديلات المجانية الشغالة 100% في السكربت:{Style.RESET_ALL}")
    for pid, meta in config.available_models.items():
        is_active = pid == config.persona_id
        mark = (
            f"{Fore.GREEN}◄ [الموديل النشط الحالي]{Style.RESET_ALL}" if is_active else ""
        )
        color = Fore.YELLOW if is_active else Fore.WHITE
        printer(f"   • {color}{pid:<22}{Style.RESET_ALL} -> {meta['desc']} {mark}")

    printer(f"{Fore.GREEN}{'─' * 76}{Style.RESET_ALL}")
    printer(
        f"{Fore.MAGENTA}🎯 الموديل النشط الحالي : "
        f"{Fore.YELLOW}{config.persona_id} ({config.model}){Style.RESET_ALL}"
    )
    printer(
        f"{Fore.MAGENTA}📂 ملف الإدخال          : "
        f"{Fore.WHITE}{config.input_file}{Style.RESET_ALL}"
    )
    printer(
        f"{Fore.MAGENTA}💾 ملف الإخراج          : "
        f"{Fore.WHITE}{config.output_file}{Style.RESET_ALL}"
    )
    printer(f"{Fore.GREEN}{'─' * 76}{Style.RESET_ALL}\n")


def print_input_stats(
    stats: InputStats,
    config: OverchatConfig,
    source_label: str,
    *,
    printer: Callable[[str], None] = print,
) -> None:
    """Source L183-189, output preserved."""
    printer(
        f"{Fore.MAGENTA}┌─── 📊 إحصائيات السؤال ({source_label}) "
        f"────────────────────────┐"
    )
    printer(
        f"│ 🤖 الموديل     : {Fore.YELLOW}{config.persona_id} "
        f"({config.model}){Fore.MAGENTA}"
    )
    printer(f"│ 📝 عدد الحروف : {Fore.YELLOW}{stats.chars:,}{Fore.MAGENTA} حرف (بدون ليمت)")
    printer(f"│ 📄 عدد الأسطر  : {Fore.YELLOW}{stats.lines:,}{Fore.MAGENTA} سطر")
    printer(f"│ 🔤 عدد الكلمات : {Fore.YELLOW}{stats.words:,}{Fore.MAGENTA} كلمة")
    printer(f"│ 🪙 Tokens تقريبي: {Fore.YELLOW}~{stats.approx_tokens:,}{Fore.MAGENTA}")
    printer(
        f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n"
    )


def print_output_stats(
    stats: OutputStats,
    config: OverchatConfig,
    *,
    printer: Callable[[str], None] = print,
) -> None:
    """Source L298-306, output preserved."""
    printer(f"\n{Fore.CYAN}{'─' * 74}{Style.RESET_ALL}")
    printer(
        f"\n{Fore.GREEN}┌─── 🏆 إحصائيات الرد وسرعة التوليد "
        f"────────────────────────┐"
    )
    printer(f"│ ⏱️  الوقت المستغرق: {Fore.YELLOW}{stats.elapsed_seconds:.2f} ثانية")
    printer(f"│ 📝 حروف الرد     : {Fore.YELLOW}{stats.chars:,}{Fore.GREEN} حرف")
    printer(f"│ 📄 أسطر الرد     : {Fore.YELLOW}{stats.lines:,}{Fore.GREEN} سطر")
    printer(f"│ 🔤 كلمات الرد    : {Fore.YELLOW}{stats.words:,}{Fore.GREEN} كلمة")
    printer(
        f"│ ⚡ معدل التوليد  : {Fore.YELLOW}{stats.chars_per_second:.1f}"
        f"{Fore.GREEN} حرف/ثانية"
    )
    printer(f"│ 🏷️  الموديل الفعلي: {Fore.YELLOW}{config.persona_id}")
    printer(
        f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n"
    )
