# PKL Jurnal Generator

Script Python yang merangkum aktivitas coding harian dari beberapa project git
menjadi draf laporan jurnal PKL, menggunakan Gemini API (`gemini-2.5-flash`).

## Alur Kerja

1. **Step 0 — Git Log Hari Ini**: `git log --since="midnight" --author="USERNAME" --patch`
   di tiap project, menangkap kode yang sudah dicommit hari ini.
2. **Step 1 — Diff Stat**: `git diff --stat HEAD` untuk melihat perubahan yang
   belum dicommit.
3. **Filtering**: buang file lock/build sampah (`pnpm-lock.yaml`,
   `package-lock.json`, `yarn.lock`, folder `dist`, `.next`, `build`, dll).
4. **Step 2 — Selective Diff**: `git diff HEAD -- <file>` hanya untuk file
   kode utama (`.ts`, `.tsx`, `.py`, `.php`, dll) dari sisa hasil filter.
5. **Token Guard**: gabungkan Step 0 + Step 2, potong ke maksimal 12.000
   karakter (bisa diubah di `config.py`).
6. **AI Summarizer**: kirim ke Gemini API untuk dirangkum jadi laporan.
7. **Output**: ditampilkan di terminal & ditambahkan (append) ke file jurnal
   mingguan, terorganisir per bulan:
   ```
   jurnal-pkl/
   ├── 2026-08-agustus/
   │   ├── minggu-1.md   (tanggal 1-7)
   │   ├── minggu-2.md   (tanggal 8-14)
   │   ├── minggu-3.md   (tanggal 15-21)
   │   └── minggu-4.md   (tanggal 22-28)
   └── 2026-09-september/
       └── minggu-1.md
   ```
   Tiap file minggu berisi beberapa hari, tiap hari bisa berisi beberapa run
   (kalau script dijalankan lebih dari sekali di hari yang sama).

## Instalasi

```bash
pip install -r requirements.txt
```

## Konfigurasi

1. Copy `.env.example` jadi `.env` lalu isi:
   ```
   GEMINI_API_KEY=xxxx
   GIT_USERNAME=nama-git-kamu
   ```
   File `.env` ini otomatis kebaca lewat `python-dotenv` saat script dijalankan
   (tidak perlu `$env:...` manual). Pastikan `.env` ada di folder yang sama
   dengan `main.py`, atau di folder tempat kamu menjalankan `python main.py`.
   Alternatif: set langsung sebagai environment variable sistem/session.

2. Edit `config.py`, isi daftar `PROJECTS` sesuai path repo yang ingin discan:
   ```python
   PROJECTS = [
       {"name": "Sonora", "path": "/home/user/projects/sonora"},
       {"name": "Talos Core", "path": "/home/user/projects/talos-core"},
   ]
   ```

## Menjalankan

Sekali jalan (misalnya dipanggil manual atau lewat cron):
```bash
python main.py
```

Mode terjadwal built-in (proses tetap hidup, jalan tiap jam 17:00):
```bash
python main.py --schedule
```

## Menjadwalkan Otomatis Tiap Jam 5 Sore

### Linux / macOS (cron) — direkomendasikan
```bash
crontab -e
# Tambahkan baris berikut (sesuaikan path python & script):
0 17 * * * cd /path/to/pkl-jurnal-generator && /usr/bin/python3 main.py >> cron.log 2>&1
```

### Windows (Task Scheduler)
1. Buka Task Scheduler → Create Basic Task.
2. Trigger: Daily, jam 17:00.
3. Action: Start a program →
   - Program: `python`
   - Arguments: `main.py`
   - Start in: folder project ini.

### Alternatif: mode `--schedule` bawaan
Cocok untuk proses yang memang dibiarkan hidup terus (misal di server/VPS),
tapi kurang andal dibanding cron/Task Scheduler karena akan berhenti jika
proses/komputer restart.

## Struktur File

```
pkl-jurnal-generator/
├── config.py             # Daftar project, username git, filter, batas token
├── git_collector.py      # Step 0, Step 1, filtering, Step 2
├── context_builder.py    # Gabungkan + token guard/truncate
├── gemini_summarizer.py  # Panggil Gemini API (google-genai SDK)
├── state_store.py        # Simpan hash diff antar run (.pkl_state.json)
├── output_paths.py       # Hitung folder bulan / file minggu dari tanggal
├── main.py               # Orkestrasi + CLI + mode terjadwal
├── requirements.txt
└── .env.example
```

## Catatan Tentang Deteksi "Perubahan Hari Ini"

Untuk perubahan yang **belum dicommit**, script tidak menebak dari waktu file
(mtime) karena mtime gampang ke-refresh oleh hal lain (git checkout/pull,
sinkronisasi cloud, auto-format editor) tanpa isi file benar-benar berubah.

Sebagai gantinya, script menyimpan hash dari isi diff tiap file di
`.pkl_state.json` setiap kali dijalankan. Pada run berikutnya, file yang
diff-nya **identik** dengan run sebelumnya dianggap bukan aktivitas baru dan
tidak dilaporkan ulang — hanya file yang isinya benar-benar berubah sejak
terakhir kali script dijalankan yang masuk ke rangkuman.

Implikasinya: sebaiknya jalankan script ini **maksimal sekali sehari** (sesuai
tujuan awal, jam 17:00) supaya "sejak run terakhir" selaras dengan "hari ini".
Kalau file `.pkl_state.json` terhapus atau dipindah, run berikutnya akan
menganggap semua perubahan uncommitted yang ada sebagai "baru".