"""
append_to_laporan.py

Scan SEMUA file minggu-*.md di folder jurnal-pkl/ (lintas bulan), bandingkan
dengan tanggal yang sudah ada di tabel kegiatan pada laporan BAB IV (.docx),
lalu tambahkan baris untuk SETIAP HARI KERJA (Senin-Sabtu, Minggu di-skip)
dalam rentang tanggal. Kalau datanya tidak ditemukan di jurnal (generator
belum jalan hari itu), baris tetap dibuat dengan Kegiatan = "Input manual"
supaya tabelnya lengkap tanpa bolong tanggal.

Cara pakai:
    python append_to_laporan.py --jurnal-root jurnal-pkl/ --docx "13. BAB IV.docx"

    --dari / --sampai opsional, format "29 Juni 2026". Default --dari: hari
      setelah tanggal terakhir yang sudah ada di tabel. Default --sampai: hari ini.
    --divisi default "IT" untuk semua baris baru; edit manual di Word untuk
      hari yang WFH (generator tidak selalu tahu ini).
    Hasil ditulis ke file baru "<nama>_updated.docx" (tidak menimpa file asli),
    kecuali --in-place diberikan.
"""

import argparse
import copy
import datetime
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

# ---------------------------------------------------------------------------
# 1. Parsing tanggal Indonesia & entri markdown
# ---------------------------------------------------------------------------

INDO_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
}


INDO_MONTHS_REV = {v: k.capitalize() for k, v in INDO_MONTHS.items()}
INDO_DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def parse_indo_date(tanggal_str: str) -> datetime.date:
    """'17 September 2026' -> date(2026, 9, 17). Exit kalau format tak dikenal (CLI args)."""
    d = try_parse_indo_date(tanggal_str)
    if d is None:
        sys.exit(f"Tidak bisa parse tanggal: '{tanggal_str}'. Cek format di sumbernya.")
    return d


def try_parse_indo_date(tanggal_str: str):
    """Versi non-fatal: None kalau gagal parse (dipakai saat scan markdown)."""
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", tanggal_str.strip())
    if not m or m.group(2).lower() not in INDO_MONTHS:
        return None
    day, month_name, year = m.groups()
    return datetime.date(int(year), INDO_MONTHS[month_name.lower()], int(day))


def format_indo_date(d: datetime.date) -> str:
    """date(2026, 6, 29) -> '29 Juni 2026'."""
    return f"{d.day} {INDO_MONTHS_REV[d.month]} {d.year}"


def indo_day_name(d: datetime.date) -> str:
    """date.weekday(): Senin=0 ... Minggu=6."""
    return INDO_DAYS[d.weekday()]


# Anchor utama: heading ini SELALU ada & konsisten di tiap entri harian
# ("# Hari ke-18 (18 Agustus 2026)"), walau format baris "Hari/Tanggal:" di
# dalamnya suka beda-beda antar hari (kadang "Tanggal:", kadang "Hari, Tanggal:",
# kadang ada embel-embel tambahan). Jangan andalkan baris metadata itu untuk tanggal.
ENTRY_HEADING_RE = re.compile(r"^#\s*Hari\s*ke-\d+\s*\(([^)]+)\)", re.MULTILINE)

# Fallback: kalau entri pertama di suatu file tidak punya heading "Hari ke-N"
# (mis. judul generik "# Laporan Jurnal Harian PKL"), pakai baris metadata ini.
META_DATE_RE = re.compile(
    r"^\*\*(?:Hari/Tanggal|Hari\s*,\s*Tanggal|Tanggal)\s*:\*\*\s*(?:[A-Za-z]+\s*,\s*)?(.+)",
    re.MULTILINE,
)

# Heading Ringkasan suka ada embel-embel ("Ringkasan Progres Hari Ini"), jadi
# jangan syaratkan akhir baris persis setelah "Progres".
RINGKASAN_HEADING_RE = re.compile(r"^##\s*Ringkasan Progres.*$", re.MULTILINE)


# Judul bullet fitur ("*   **Validasi Target Booking (Invariant):** Menambahkan...")
# HARUS diawali penanda bullet (* atau -), supaya baris metadata non-bullet seperti
# "**Hari/Tanggal:** ..." atau "**Peran:** ..." tidak ikut ke-anggap sebagai fitur.
# Judul section header ("**Backend (API):**" lalu ganti baris ke sub-bullet, tanpa
# teks di baris yang sama) otomatis ke-skip karena butuh teks setelah titik dua.
FEATURE_BULLET_RE = re.compile(
    r"^[ \t]*[*\-][ \t]+\*\*([^*\n:]{3,100}):\*\*[ \t]+\S", re.MULTILINE
)
# Label-label ini SERING muncul dalam bentuk bullet berjudul-bold tapi bukan nama
# fitur (cuma metadata/daftar file/kesimpulan) -> jangan ikut masuk ringkasan.
# Kalau generator-mu pakai label lain yang juga perlu di-exclude, tambahin di sini.
FEATURE_LABEL_BLACKLIST = {
    "file yang diubah", "file & modul utama yang disentuh",
    "file/modul utama yang disentuh", "tujuan perubahan", "perubahan & tujuan",
    "status", "keterangan",
}


def extract_kegiatan_ringkas(blok: str, ringkasan_fallback: str) -> str:
    """Ambil judul-judul bold di bullet fitur (gaya singkat, mirip isian manual).
    Kalau tidak ada satupun ketemu (mis. hari itu formatnya narasi biasa),
    fallback ke kalimat pertama Ringkasan Progres, dipotong kalau kepanjangan."""
    titles = []
    for m in FEATURE_BULLET_RE.finditer(blok):
        title = m.group(1).strip()
        if title.lower() not in FEATURE_LABEL_BLACKLIST and title not in titles:
            titles.append(title)

    if titles:
        return ", ".join(titles)

    kalimat_pertama = re.split(r"(?<=[.!?])\s", ringkasan_fallback.strip(), maxsplit=1)[0]
    if len(kalimat_pertama) > 180:
        kalimat_pertama = kalimat_pertama[:177].rstrip() + "..."
    return kalimat_pertama


def parse_all_entries(md_text: str) -> list[dict]:
    """Ambil SEMUA entri (tanggal + ringkasan kegiatan) dalam satu file md."""
    boundaries = []
    for m in ENTRY_HEADING_RE.finditer(md_text):
        boundaries.append((m.start(), m.end(), m.group(1)))
    for m in META_DATE_RE.finditer(md_text):
        boundaries.append((m.start(), m.end(), m.group(1)))
    boundaries.sort(key=lambda b: b[0])

    entries = []
    for i, (_, blok_start, date_str) in enumerate(boundaries):
        date = try_parse_indo_date(date_str)
        if date is None:
            continue  # bukan baris tanggal beneran (mis. heading generik) -> lewati

        blok_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(md_text)
        blok = md_text[blok_start:blok_end]

        heading_match = RINGKASAN_HEADING_RE.search(blok)
        if not heading_match:
            continue  # blok ini belum sampai bagian Ringkasan -> lewati, bukan fatal

        setelah_heading = blok[heading_match.end():].strip()
        akhir = re.search(r"\n---|\n#", "\n" + setelah_heading)
        ringkasan_penuh = (
            setelah_heading[: akhir.start()].strip() if akhir else setelah_heading.strip()
        )
        kegiatan = extract_kegiatan_ringkas(blok, ringkasan_penuh)
        entries.append(
            {"date": date, "hari": indo_day_name(date), "tanggal": format_indo_date(date),
             "kegiatan": kegiatan}
        )
    return entries


def collect_entries_from_folder(root: Path) -> dict:
    """Glob semua *.md di bawah root, gabungkan jadi {date: entry}."""
    by_date = {}
    for md_file in sorted(root.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for entry in parse_all_entries(text):
            by_date[entry["date"]] = entry  # file lebih baru menang kalau duplikat
    return by_date


# ---------------------------------------------------------------------------
# 2. Menulis ke tabel di docx
# ---------------------------------------------------------------------------

def find_target_table(doc: Document):
    """Cari tabel yang header-nya persis: Hari, Tanggal | Kegiatan | Divisi."""
    for table in doc.tables:
        header_cells = [c.text.strip() for c in table.rows[0].cells]
        if header_cells[:3] == ["Hari, Tanggal", "Kegiatan", "Divisi"]:
            return table
    sys.exit(
        "Tidak menemukan tabel dengan header 'Hari, Tanggal / Kegiatan / Divisi'. "
        "Cek nama header di docx atau sesuaikan find_target_table()."
    )


def get_reference_font(table):
    """Ambil font (nama & ukuran) dari baris data PERTAMA (baris asli, belum
    pernah disentuh script ini) supaya semua baris baru konsisten — tidak ikut
    format run tertentu di baris terakhir yang bisa saja kebetulan italic/bold."""
    ref_run = table.rows[1].cells[1].paragraphs[0].runs[0]
    name = ref_run.font.name or "Times New Roman"
    size = ref_run.font.size  # bisa None kalau ukurannya cuma ikut style, itu wajar
    return name, size


def apply_font(run, font_name, font_size, bold=False, italic=False):
    """Set font secara eksplisit -> baris baru tidak pernah ikut-ikutan format
    (bold/italic/font lain) yang kebetulan menempel di run yang di-copy."""
    run.font.name = font_name
    if font_size is not None:
        run.font.size = font_size
    run.bold = bold
    run.italic = italic


def set_two_line_cell(cell, line1: str, line2: str, font_name, font_size):
    """Isi cell 'Hari, Tanggal' (2 baris: nama hari + tanggal), format eksplisit."""
    values = [line1, line2]
    if len(cell.paragraphs) >= 2:
        for para, value in zip(cell.paragraphs, values):
            for run in list(para.runs):
                run.text = ""
            run = para.runs[0] if para.runs else para.add_run()
            run.text = value
            apply_font(run, font_name, font_size)
        for extra_para in cell.paragraphs[2:]:
            extra_para.clear()
    else:
        para = cell.paragraphs[0]
        for run in list(para.runs):
            run.text = ""
        first_run = para.runs[0] if para.runs else para.add_run()
        first_run.text = line1
        apply_font(first_run, font_name, font_size)
        first_run.add_break()
        second_run = para.add_run()
        second_run.text = line2
        apply_font(second_run, font_name, font_size)


def set_plain_cell(cell, value: str, font_name, font_size):
    para = cell.paragraphs[0]
    for run in list(para.runs):
        run.text = ""
    run = para.runs[0] if para.runs else para.add_run()
    run.text = value
    apply_font(run, font_name, font_size)
    for extra_para in cell.paragraphs[1:]:
        extra_para.clear()


MD_INLINE_RE = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")


def set_kegiatan_cell(cell, text: str, font_name, font_size):
    """Isi cell 'Kegiatan', dukung **bold** dan *italic* sederhana dari markdown.
    Font, bold, dan italic SELALU di-set eksplisit per segmen -> tidak ada
    formatting yang 'nempel' tanpa sengaja dari isi sebelumnya."""
    para = cell.paragraphs[0]
    for run in list(para.runs):
        run.text = ""

    parts = [p for p in MD_INLINE_RE.split(text) if p]
    existing_runs = list(para.runs)
    for i, part in enumerate(parts):
        bold = italic = False
        content = part
        if part.startswith("**") and part.endswith("**"):
            bold, content = True, part[2:-2]
        elif part.startswith("*") and part.endswith("*"):
            italic, content = True, part[1:-1]

        run = existing_runs[i] if i < len(existing_runs) else para.add_run()
        run.text = content
        apply_font(run, font_name, font_size, bold=bold, italic=italic)

    # buang run sisa template yang tidak terpakai (kosong tapi biar bersih di XML)
    for extra_run in existing_runs[len(parts):]:
        extra_run._element.getparent().remove(extra_run._element)

    for extra_para in cell.paragraphs[1:]:
        extra_para.clear()


def append_row(table, hari: str, tanggal: str, kegiatan: str, divisi: str, font_name, font_size):
    template_row = table.rows[-1]  # baris terakhir jadi acuan STRUKTUR (border, lebar kolom)
    new_tr = copy.deepcopy(template_row._tr)
    table._tbl.append(new_tr)

    # ambil ulang objek Row dari tr yang baru di-append
    from docx.table import _Row

    new_row = _Row(new_tr, table)

    set_two_line_cell(new_row.cells[0], hari + ",", tanggal, font_name, font_size)
    set_kegiatan_cell(new_row.cells[1], kegiatan, font_name, font_size)
    set_plain_cell(new_row.cells[2], divisi, font_name, font_size)


def get_existing_dates(table) -> set:
    """Baca tanggal yang sudah ada di tabel (baris ke-2 tiap cell kolom 0)."""
    existing = set()
    for row in table.rows[1:]:
        cell_text = row.cells[0].text.strip()
        lines = [l.strip().rstrip(",") for l in cell_text.splitlines() if l.strip()]
        if len(lines) >= 2:
            try:
                existing.add(parse_indo_date(lines[1]))
            except SystemExit:
                continue  # baris header/format lain -> lewati, bukan fatal
    return existing


# ---------------------------------------------------------------------------
# 3. Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--jurnal-root", required=True, type=Path,
        help="Folder jurnal-pkl/ (di-scan rekursif untuk semua minggu-*.md)"
    )
    ap.add_argument("--docx", required=True, type=Path, help="Path ke laporan BAB IV.docx")
    ap.add_argument("--divisi", default="IT", help="Divisi default utk baris baru (default: IT)")
    ap.add_argument(
        "--dari", default=None,
        help="Mulai dari tanggal ini, format '29 Juni 2026' (default: hari setelah "
             "tanggal terakhir di tabel)"
    )
    ap.add_argument(
        "--sampai", default=None,
        help="Isi sampai tanggal ini, format '25 September 2026' (default: hari ini)"
    )
    ap.add_argument(
        "--in-place", action="store_true", help="Timpa file docx asli alih-alih buat file baru"
    )
    args = ap.parse_args()

    doc = Document(args.docx)
    table = find_target_table(doc)

    existing_dates = get_existing_dates(table)
    font_name, font_size = get_reference_font(table)
    if args.dari:
        start = parse_indo_date(args.dari)
    elif existing_dates:
        start = max(existing_dates) + datetime.timedelta(days=1)
    else:
        sys.exit("Tabel belum ada baris data — pakai --dari untuk tentukan tanggal mulai.")
    end = parse_indo_date(args.sampai) if args.sampai else datetime.date.today()

    entries_by_date = collect_entries_from_folder(args.jurnal_root)

    ditambahkan, input_manual = [], []
    d = start
    while d <= end:
        if d.weekday() == 6 or d in existing_dates:  # skip Minggu & tanggal yang sudah ada
            d += datetime.timedelta(days=1)
            continue

        entry = entries_by_date.get(d)
        if entry is None:
            hari, tanggal_str, kegiatan = indo_day_name(d), format_indo_date(d), "Input manual"
            input_manual.append(d)
        else:
            hari, tanggal_str, kegiatan = entry["hari"], entry["tanggal"], entry["kegiatan"]

        append_row(table, hari, tanggal_str, kegiatan, args.divisi, font_name, font_size)
        ditambahkan.append(d)
        d += datetime.timedelta(days=1)

    out_path = args.docx if args.in_place else args.docx.with_name(args.docx.stem + "_updated.docx")
    doc.save(out_path)

    print(f"[OK] {len(ditambahkan)} baris ditambahkan ({start} s.d. {end}), Minggu di-skip.")
    print(f"[OK] Disimpan ke: {out_path}")
    if input_manual:
        print(f"\n[PERLU DIISI MANUAL] {len(input_manual)} baris ditulis 'Input manual':")
        for d in input_manual:
            print(f"  - {indo_day_name(d)}, {format_indo_date(d)}")


if __name__ == "__main__":
    main()