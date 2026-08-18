"""
Menentukan path output jurnal berdasarkan tanggal:
    <JOURNAL_BASE_DIR>/<tahun>-<bulan-2digit>-<nama_bulan>/minggu-<N>.md

Contoh: 16 Agustus 2026 -> jurnal-pkl/2026-08-agustus/minggu-3.md
(karena tanggal 16 masuk rentang hari 15-21 = minggu ke-3 bulan itu)

Pembagian minggu: minggu ke-N mencakup hari ((N-1)*7 + 1) sampai (N*7) di
bulan itu -- jadi minggu 1 = tanggal 1-7, minggu 2 = tanggal 8-14, dst.
Ini bukan minggu kalender (Senin-Minggu), tapi minggu-ke-berapa dalam bulan
dihitung dari tanggal 1.
"""

from __future__ import annotations

import datetime
from pathlib import Path

MONTH_NAMES_ID = {
    1: "januari", 2: "februari", 3: "maret", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "agustus",
    9: "september", 10: "oktober", 11: "november", 12: "desember",
}


def week_of_month(date: datetime.date) -> int:
    """Minggu ke berapa dalam bulan ini (1-5), dihitung dari tanggal 1."""
    return ((date.day - 1) // 7) + 1


def month_folder_name(date: datetime.date) -> str:
    return f"{date.year}-{date.month:02d}-{MONTH_NAMES_ID[date.month]}"


def format_date_id(date: datetime.date) -> str:
    return f"{date.day} {MONTH_NAMES_ID[date.month].capitalize()} {date.year}"


def get_output_path(base_dir: Path, date: datetime.date | None = None) -> Path:
    """Return path file minggu untuk tanggal tertentu, sekaligus membuat
    folder bulan-nya kalau belum ada."""
    date = date or datetime.date.today()
    folder = base_dir / month_folder_name(date)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"minggu-{week_of_month(date)}.md"