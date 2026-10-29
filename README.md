# JobAppAgent

**Asisten pencarian lowongan kerja berbasis Python dan Slack.** JobAppAgent mengumpulkan lowongan dari beberapa sumber publik, menyaringnya berdasarkan profil keterampilan, memeriksa tautan, lalu mengirimkan hasil yang relevan ke Slack. Bot hanya membantu menemukan peluang; bot tidak melamar pekerjaan atau menghubungi perekrut.

## Fitur

- Pencarian serentak dari Remotive, Remote OK, Jobicy, Himalayas, API Arbeitnow untuk Jerman dan Inggris, serta RSS We Work Remotely.
- Pencocokan transparan berdasarkan judul posisi, keterampilan, dan lokasi di `profile.json`.
- Pemeriksaan bahwa tautan lowongan menggunakan HTTPS dan dapat merespons.
- Penghapusan duplikasi dan penyimpanan riwayat lokal menggunakan SQLite.
- Pencarian interaktif lewat Slack Socket Mode dan notifikasi lowongan melalui GitHub Actions.
- Fallback ke Brave Search (opsional), utas “Who is Hiring” di Hacker News, dan tautan pencarian portal kerja.

## Alur pencarian

```text
Permintaan pencarian
        │
        ▼
API lowongan + RSS ──► pencocokan profil ──► pemeriksaan tautan
        │                                      │
        └── jika tidak ada hasil cocok ────────┤
                                               ▼
                                   hasil dikelompokkan per sumber
                                               │
                                               ▼
                                          Slack / CLI
```

Hasil API ditampilkan dalam kelompok berdasarkan sumber. Jika tidak ada lowongan API yang lolos penyaringan, bot mencoba Brave Search jika `BRAVE_SEARCH_API_KEY` tersedia, mencari lead komunitas di Hacker News, lalu memberikan tautan pencarian langsung ke LinkedIn, Glassdoor, Upwork, dan Freelancer.

## Sumber data dan batas kepercayaan

| Jenis | Sumber | Catatan |
|---|---|---|
| API lowongan | Remotive, Remote OK, Jobicy, Himalayas, Arbeitnow | Diambil saat pencarian; ketersediaan dan kesegaran mengikuti masing-masing penyedia. Arbeitnow mencakup lowongan remote dari Jerman dan Inggris. |
| RSS | We Work Remotely | Feed publik; tautan sumber tetap dicantumkan. |
| Web | Brave Search | Opsional dan memerlukan API key; hasil web perlu diperiksa pada situs perusahaan. |
| Forum | Hacker News “Who is Hiring” | Lead dari komentar komunitas, bukan lowongan terverifikasi. |
| Portal | LinkedIn, Glassdoor, Upwork, Freelancer | Bot memberikan tautan pencarian di portal. Bot tidak mengambil atau scrape isi portal tersebut. |

> Pemeriksaan tautan hanya memastikan halaman merespons saat diperiksa. Itu tidak membuktikan perusahaan atau lowongan masih aktif. Periksa kembali situs perusahaan sebelum melamar.

JobAppAgent tidak menggunakan scraping LinkedIn atau Glassdoor. API lowongan LinkedIn memerlukan akses partner yang disetujui; akses API Upwork memerlukan kredensial dan izin. Brave Search juga tidak wajib: biarkan `BRAVE_SEARCH_API_KEY` kosong untuk memakai API, RSS, Hacker News, dan tautan portal tanpa biaya API.

## Persiapan

- Python 3.11 atau lebih baru
- Workspace Slack dan Slack app untuk fitur bot
- GitHub repository untuk notifikasi terjadwal

## Menjalankan secara lokal

```bash
cd JobAppAgent
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Isi `.env` untuk koneksi Slack:

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C...
JOBAPP_DB_PATH=data/jobs.sqlite3
JOBAPP_PROFILE_PATH=profile.json
BRAVE_SEARCH_API_KEY=
```

Jalankan pencarian dari terminal:

```bash
python -m jobapp search --query "ai engineer"
```

## Menghubungkan Slack

1. Buat Slack app dan aktifkan **Socket Mode**.
2. Tambahkan bot scopes `chat:write`, `commands`, dan `app_mentions:read`, lalu instal app ke workspace.
3. Buat App-Level Token dengan scope `connections:write`.
4. Buat slash command `/jobs` dan aktifkan event `app_mention`.
5. Isi `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, dan `SLACK_CHANNEL_ID` di `.env`; undang bot ke channel tujuan.
6. Jalankan listener:

   ```bash
   python -m jobapp slack
   ```

Selama listener berjalan, gunakan:

```text
/jobs help
/jobs
/jobs search ai engineer
```

Listener Socket Mode harus tetap berjalan agar slash command mendapat respons. GitHub Actions menjalankan pencarian terjadwal, tetapi tidak menjaga listener interaktif tetap hidup.

## Notifikasi otomatis lewat GitHub Actions

Workflow `.github/workflows/daily-search.yml` menjalankan pencarian setiap hari pukul **08.17 WIB** dan dapat dijalankan manual melalui **Actions → Job alerts → Run workflow**.

Untuk mengaktifkannya:

1. Jadikan direktori `JobAppAgent/` sebagai root repository GitHub tersendiri, lalu push kode ke repository tersebut.
2. Di **Settings → Secrets and variables → Actions**, tambahkan:
   - Repository secret `SLACK_BOT_TOKEN`.
   - Repository variable `SLACK_CHANNEL_ID`.
3. Pastikan workflow diizinkan berjalan pada repository tersebut.

Workflow terjadwal hanya memerlukan bot token dan channel ID; `SLACK_APP_TOKEN` dipakai oleh listener Socket Mode lokal. Database workflow disimpan melalui cache GitHub Actions, yang bersifat best-effort dan bukan penyimpanan permanen.

## Menyesuaikan profil

Edit `profile.json` untuk mengatur:

- `title_keywords`: judul posisi sasaran.
- `keywords`: keterampilan dan teknologi.
- `locations`: lokasi atau cakupan remote.
- `minimum_score`: nilai minimum kecocokan.
- `require_title_match`: mewajibkan judul lowongan cocok dengan salah satu posisi sasaran.

Skor adalah pencocokan kata kunci, bukan penilaian kelayakan atau rekomendasi otomatis.

## Keamanan dan batasan

- Simpan token Slack dan Brave hanya di `.env` lokal atau GitHub Secrets. Jangan commit token, `.env`, maupun database.
- Bot hanya membaca sumber lowongan dan mengirim notifikasi; bot tidak melamar pekerjaan.
- Sebagian sumber memperbarui data secara berkala, sehingga pencarian baru tidak selalu berarti data baru saja diterbitkan.
- Tautan yang aktif belum tentu lowongannya masih dibuka atau perusahaan telah terverifikasi.
- SQLite dan cache GitHub Actions ditujukan untuk prototipe personal, bukan layanan multi-pengguna atau penyimpanan jangka panjang.
- Brave Search bersifat opsional dan menggunakan API berbayar; tanpa key, fallback web dilewati.

## Menjalankan tes

```bash
python -m unittest discover -s tests -v
```

Tes menggunakan data sintetis dan HTTP mock. Tes tersebut tidak membuktikan feed eksternal, instalasi Slack, maupun workflow GitHub berjalan live.
