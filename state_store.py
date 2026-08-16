"""
State tracker -- I/O untuk file `.pkl_jurnal_state.json`.

File ini menyimpan hash dari isi diff tiap file (key: "project_path::filename")
dari run sebelumnya, di folder script ini sendiri (BUKAN di repo project kamu,
jadi tidak akan tercampur/tercommit ke project manapun).

Kenapa perlu ini: mtime file TIDAK bisa diandalkan untuk menandai "diubah
hari ini" -- git checkout/pull, sync tool (OneDrive/Dropbox), atau ekstensi
editor bisa menyentuh mtime tanpa isi file benar-benar berubah. Dengan
membandingkan HASH isi diff terhadap run sebelumnya (logic ada di
git_collector.py), kita tahu persis apakah ada perubahan BARU sejak terakhir
script dijalankan -- terlepas dari mtime.

Konsekuensi: perubahan uncommitted yang SAMA PERSIS dan sudah pernah
dilaporkan di run sebelumnya tidak akan dilaporkan lagi (hash-nya tidak
berubah). Begitu file diedit lagi, hash berubah, otomatis muncul lagi.
"""

from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / ".pkl_jurnal_state.json"


def load_state() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")