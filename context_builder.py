"""
Menggabungkan hasil git_collector dari semua project menjadi satu blok teks,
lalu memotongnya agar tidak melebihi batas karakter (token guard) sebelum
dikirim ke Gemini API.
"""

from __future__ import annotations

from config import MAX_CONTEXT_CHARS
from git_collector import ProjectGitData


def build_project_section(data: ProjectGitData) -> str:
    if not data.is_git_repo:
        return f"## {data.name}\n(dilewati: {data.error})\n"

    parts = [f"## {data.name}"]

    if (data.todays_commits or "").strip():
        parts.append("### Commit hari ini (git log)")
        parts.append(data.todays_commits.strip())
    else:
        parts.append("### Commit hari ini (git log)\n(tidak ada commit baru hari ini)")

    if data.changed_files:
        parts.append("### File dengan perubahan baru (belum dicommit, sejak run terakhir)")
        parts.append("\n".join(f"- {f}" for f in data.changed_files))
        if (data.selective_diff or "").strip():
            parts.append(data.selective_diff.strip())
    else:
        parts.append("### File dengan perubahan baru (belum dicommit)\n(tidak ada perubahan baru sejak run terakhir)")

    return "\n\n".join(parts)


def build_full_context(all_data: list[ProjectGitData]) -> str:
    sections = [build_project_section(d) for d in all_data]
    return "\n\n---\n\n".join(sections)


def truncate_context(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, bool]:
    """Token guard: potong teks jika melebihi batas karakter.
    Return (teks_final, apakah_dipotong)."""
    if len(text) <= max_chars:
        return text, False

    truncated = text[:max_chars]
    truncated += "\n\n[... konteks dipotong karena melebihi batas token ...]"
    return truncated, True