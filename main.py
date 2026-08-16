"""
PKL Jurnal Generator
=====================
Merangkum aktivitas coding harian dari beberapa project git menjadi draf
laporan jurnal PKL, menggunakan Gemini API.

Cara pakai:
    # Jalan sekali, langsung generate jurnal hari ini
    python main.py

    # Jalan dalam mode terjadwal (otomatis tiap jam 17:00, proses tetap hidup)
    python main.py --schedule

Environment variables yang dibutuhkan:
    GEMINI_API_KEY   -> API key Gemini kamu
    GIT_USERNAME     -> (opsional) override username git dari config.py
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from config import GIT_USERNAME, OUTPUT_FILE, PROJECTS
from context_builder import build_full_context, truncate_context
from gemini_summarizer import summarize
from git_collector import collect_all_projects
from state_store import load_state, save_state


def run_once() -> None:
    print(f"[1/5] Mengecek git log & diff untuk {len(PROJECTS)} project...")
    prev_state = load_state()
    all_data = collect_all_projects(PROJECTS, GIT_USERNAME, prev_state)

    for d in all_data:
        status = "OK" if d.is_git_repo else f"DILEWATI ({d.error})"
        print(f"      - {d.name}: {status}")

    print("[2/5] Menggabungkan & memotong konteks (token guard)...")
    full_context = build_full_context(all_data)
    context, was_truncated = truncate_context(full_context)
    if was_truncated:
        print(f"      Konteks dipotong ke {len(context)} karakter.")
    else:
        print(f"      Total konteks: {len(context)} karakter.")

    print("[3/5] Mengirim ke Gemini API untuk dirangkum...")
    try:
        result = summarize(context)
    except Exception as exc:  # noqa: BLE001 - ditampilkan langsung ke user
        print(f"      Gagal memanggil Gemini API: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[4/5] Menambahkan entri baru ke jurnal...")
    output_path = Path(OUTPUT_FILE)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n\n---\n\n<!-- Run: {timestamp} -->\n\n{result}\n"

    if output_path.exists():
        with output_path.open("a", encoding="utf-8") as f:
            f.write(entry)
    else:
        # File belum ada -> tulis tanpa separator/awalan kosong di depan
        output_path.write_text(f"<!-- Run: {timestamp} -->\n\n{result}\n", encoding="utf-8")

    print("[5/5] Menyimpan state (biar diff yang sama tidak dilaporkan ulang)...")
    new_state = dict(prev_state)
    for d in all_data:
        new_state.update(d.state_updates)
    save_state(new_state)

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)
    print(f"\nEntri baru ditambahkan ke: {output_path.resolve()}")


def run_scheduled() -> None:
    """Mode terjadwal sederhana: jalan tiap hari jam 17:00 selama proses ini hidup.
    Untuk penjadwalan yang lebih andal (tetap jalan walau komputer restart),
    lebih disarankan pakai cron (Linux/Mac) atau Task Scheduler (Windows) —
    lihat README.md.
    """
    try:
        import schedule
    except ImportError:
        print(
            "Paket 'schedule' belum terinstall. Jalankan: pip install schedule",
            file=sys.stderr,
        )
        sys.exit(1)

    import time

    schedule.every().day.at("17:00").do(run_once)
    print("Mode terjadwal aktif. Menunggu jam 17:00 tiap hari... (Ctrl+C untuk berhenti)")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="PKL Jurnal Generator")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Jalankan dalam mode terjadwal (otomatis tiap jam 17:00)",
    )
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        run_once()


if __name__ == "__main__":
    main()