"""
Konfigurasi utama untuk PKL Jurnal Generator.
Edit bagian PROJECTS dan GIT_USERNAME sesuai kebutuhanmu.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Cari file .env mulai dari direktori kerja saat ini ke atas, lalu load
# isinya ke environment variable proses ini. Kalau .env tidak ditemukan,
# baris ini tidak melakukan apa-apa (tidak error) — variable tetap bisa
# di-set manual lewat environment sistem.
load_dotenv()

# ---------------------------------------------------------------------------
# 1. Multi-Project Management
# ---------------------------------------------------------------------------
# Daftar semua project (repo git) yang mau discan tiap hari.
# "path" wajib berupa direktori yang merupakan git repository (punya folder .git).
PROJECTS = [
    {"name": "Project Core Talos", "path": "C:/pkl/Company-Projects/project-core-talos"}
]
# Username git kamu (harus SAMA PERSIS dengan `git config user.name` di tiap repo,
# atau bisa juga pakai email lewat --author jika author.name berbeda-beda).
GIT_USERNAME = os.environ.get("GIT_USERNAME", "USERNAME_AKU")

# ---------------------------------------------------------------------------
# 4. Filtering — file/folder yang diabaikan (lock file, build artifact, dll)
# ---------------------------------------------------------------------------
IGNORE_FILENAMES = {
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "composer.lock",
    "poetry.lock",
    "Cargo.lock",
}

IGNORE_DIR_PARTS = {
    "dist",
    "build",
    ".next",
    "node_modules",
    "vendor",
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "coverage",
}

# ---------------------------------------------------------------------------
# 5. Ekstensi file kode utama yang diambil detail diff-nya (Step 2)
# ---------------------------------------------------------------------------
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx",
    ".py",
    ".php",
    ".dart",
    ".java", ".kt",
    ".go",
    ".rb",
    ".vue",
    ".css", ".scss",
    ".html",
    ".sql",
    ".prisma"
}

# ---------------------------------------------------------------------------
# 6. Token Guard & Truncate
# ---------------------------------------------------------------------------
MAX_CONTEXT_CHARS = 12_000  # batas total karakter konteks yang dikirim ke Gemini

# ---------------------------------------------------------------------------
# 7. Gemini API
# ---------------------------------------------------------------------------
# Catatan: "gemini-2.5-flash" sudah tidak tersedia untuk API key baru (dideprecate
# lebih cepat dari jadwal resmi Google). Pakai alias "gemini-3.5-flash" yang
# otomatis mengarah ke rilis Flash terbaru, dan diberi notice 2 minggu sebelum
# ada breaking change — jadi lebih tahan lama dibanding pin ke versi spesifik.
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# 8. Output
# ---------------------------------------------------------------------------
# Struktur: <JOURNAL_BASE_DIR>/<tahun>-<bulan>-<nama_bulan>/minggu-<N>.md
# Contoh: jurnal-pkl/2026-08-agustus/minggu-3.md
JOURNAL_BASE_DIR = Path(__file__).parent / "jurnal-pkl"