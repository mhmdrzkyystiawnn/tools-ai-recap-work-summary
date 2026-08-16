"""
Modul untuk mengumpulkan data git dari tiap project:
- Step 0: git log commit hari ini (--since=midnight --author=... --patch)
- Step 1: git diff --stat HEAD (perubahan belum dicommit)
- Filtering: buang file lock/build/config sampah
- Step 2: git diff HEAD -- <file> untuk file kode utama saja, HANYA yang
  isinya berbeda dari hasil run terakhir (dibandingkan via hash, bukan mtime
  file -- mtime gampang ke-refresh oleh git checkout/pull, sinkronisasi cloud,
  auto-format editor, dll tanpa isi file benar-benar berubah).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import CODE_EXTENSIONS, IGNORE_DIR_PARTS, IGNORE_FILENAMES


@dataclass
class ProjectGitData:
    name: str
    path: str
    is_git_repo: bool = True
    todays_commits: str = ""       # hasil Step 0
    changed_files: list[str] = field(default_factory=list)  # file dgn diff baru (Step 1, difilter)
    selective_diff: str = ""       # hasil Step 2
    state_updates: dict[str, str] = field(default_factory=dict)  # hash diff terbaru per file
    error: str | None = None


def _run_git(path: str, args: list[str]) -> tuple[bool, str]:
    """Jalankan perintah git di direktori tertentu. Return (sukses, output)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _is_git_repo(path: str) -> bool:
    return (Path(path) / ".git").exists()


def step0_todays_commits(path: str, username: str) -> str:
    """Step 0: tangkap commit yang sudah dibuat hari ini oleh user tertentu."""
    ok, output = _run_git(
        path,
        [
            "log",
            "--since=midnight",
            f"--author={username}",
            "--patch",
            "--stat",
        ],
    )
    return output if ok else ""


def step1_diff_stat_files(path: str) -> list[str]:
    """Step 1: ambil daftar file yang berubah (belum dicommit) via git diff --stat HEAD."""
    ok, output = _run_git(path, ["diff", "--stat", "HEAD"])
    if not ok or not output.strip():
        return []

    files = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        filename = line.split("|", 1)[0].strip()
        if filename:
            files.append(filename)
    return files


def _should_ignore(filename: str) -> bool:
    base = os.path.basename(filename)
    if base in IGNORE_FILENAMES:
        return True
    parts = set(Path(filename).parts)
    if parts & IGNORE_DIR_PARTS:
        return True
    return False


def _is_code_file(filename: str) -> bool:
    return Path(filename).suffix in CODE_EXTENSIONS


def filter_files(files: list[str]) -> list[str]:
    """Buang file lock/build/config sampah, sisakan hanya file kode utama."""
    result = []
    for f in files:
        if _should_ignore(f):
            continue
        if not _is_code_file(f):
            continue
        result.append(f)
    return result


def step2_selective_diff(
    path: str, files: list[str], project_key: str, prev_state: dict[str, str]
) -> tuple[str, list[str], dict[str, str]]:
    """Step 2: ambil detail diff untuk file kode utama, tapi HANYA file yang
    isinya berbeda dari run terakhir (dibanding via hash SHA-256 dari isi diff).

    Return: (teks diff gabungan, daftar file yang benar-benar baru/berubah,
             dict update state untuk semua file yang dicek -- dipakai untuk
             menimpa state lama setelah run selesai).
    """
    chunks = []
    truly_new_files = []
    state_updates: dict[str, str] = {}

    for f in files:
        ok, output = _run_git(path, ["diff", "HEAD", "--", f])
        if not ok or not output.strip():
            continue

        diff_hash = hashlib.sha256(output.encode("utf-8")).hexdigest()
        state_key = f"{project_key}::{f}"
        state_updates[state_key] = diff_hash

        if prev_state.get(state_key) == diff_hash:
            # Diff-nya identik dengan run terakhir -> bukan perubahan baru, skip.
            continue

        truly_new_files.append(f)
        chunks.append(f"### Diff: {f}\n```diff\n{output.strip()}\n```")

    return "\n\n".join(chunks), truly_new_files, state_updates


def collect_project_data(project: dict, username: str, prev_state: dict[str, str]) -> ProjectGitData:
    """Jalankan Step 0 -> Step 1 -> Filtering -> Step 2 untuk satu project."""
    name, path = project["name"], project["path"]
    project_key = os.path.abspath(path)

    if not os.path.isdir(path):
        return ProjectGitData(name=name, path=path, is_git_repo=False,
                               error=f"Direktori tidak ditemukan: {path}")

    if not _is_git_repo(path):
        return ProjectGitData(name=name, path=path, is_git_repo=False,
                               error=f"Bukan git repository: {path}")

    data = ProjectGitData(name=name, path=path)

    # Step 0
    data.todays_commits = step0_todays_commits(path, username)

    # Step 1
    raw_changed_files = step1_diff_stat_files(path)

    # Filtering (lock/build/config sampah + hanya file kode utama)
    filtered_files = filter_files(raw_changed_files)

    # Step 2 (hanya file yang diffnya benar-benar baru dibanding run terakhir)
    if filtered_files:
        diff_text, truly_new_files, state_updates = step2_selective_diff(
            path, filtered_files, project_key, prev_state
        )
        data.selective_diff = diff_text
        data.changed_files = truly_new_files
        data.state_updates = state_updates

    return data


def collect_all_projects(
    projects: list[dict], username: str, prev_state: dict[str, str]
) -> list[ProjectGitData]:
    return [collect_project_data(p, username, prev_state) for p in projects]