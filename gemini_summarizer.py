"""
Mengirim konteks git (commit log + diff) ke Gemini API untuk dirangkum
menjadi draf laporan jurnal PKL harian.

Menggunakan SDK resmi terbaru: google-genai
    pip install google-genai
"""

from __future__ import annotations

import datetime

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

SYSTEM_INSTRUCTION = """\
Kamu adalah asisten yang membantu menyusun draf laporan jurnal harian PKL (Praktik Kerja Lapangan)
untuk seorang developer. Tugasmu: rangkum aktivitas coding hari ini berdasarkan data git log dan
git diff yang diberikan.

Aturan penulisan:
- Gunakan bahasa Indonesia yang singkat, teknis, dan profesional (gaya laporan resmi ke pembimbing).
- Kelompokkan berdasarkan nama project.
- Untuk tiap project, jelaskan secara ringkas: fitur/perubahan apa yang dikerjakan, file/modul utama
  yang tersentuh, dan tujuannya (jika bisa disimpulkan dari kode).
- Jangan menyalin mentah-mentah isi diff; ubah menjadi kalimat naratif yang mudah dibaca pembimbing.
- Jika ada project tanpa aktivitas, sebutkan singkat "tidak ada aktivitas" tanpa perlu detail.
- Tutup dengan 1-2 kalimat ringkasan keseluruhan progres hari ini.
- Format output dalam Markdown, siap tempel ke jurnal PKL.
"""


def build_user_prompt(context: str) -> str:
    today = datetime.date.today().strftime("%d %B %Y")
    return f"""\
Tanggal: {today}

Berikut data git (commit log hari ini + diff perubahan yang belum dicommit) dari beberapa project:

{context}

Buatkan draf laporan jurnal PKL harian berdasarkan data di atas, ikuti aturan penulisan yang sudah ditentukan.
"""


def summarize(context: str) -> str:
    """Kirim context ke Gemini dan kembalikan teks rangkuman laporan jurnal."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY belum di-set. Set environment variable GEMINI_API_KEY terlebih dahulu."
        )

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_user_prompt(context),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        ),
    )

    return response.text.strip()