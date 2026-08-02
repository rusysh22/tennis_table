# Mini-Round Table Tennis InterSport 2026

Website turnamen tenis meja internal (Ganda Putra 2 grup + Ganda Campuran 1 grup), format round robin,
final Ganda Putra mempertemukan Juara Group A vs Juara Group B. 20–29 Juli 2026, 18.00–20.00 WIB.

Dibangun dengan **Flask** + **JSON file** sebagai penyimpanan data, supaya skor, status live, dan
reschedule bisa diupdate langsung dari browser (lewat halaman admin) tanpa perlu redeploy manual.

## Menjalankan lokal

```bash
pip install -r requirements.txt
python generate_data.py   # generate data/teams.json, data/matches.json, data/config.json (sekali saja / untuk reset)
python app.py              # buka http://127.0.0.1:5000
```

## Login admin

Jalur login panitia tersedia di **`/admin/login`**. Alamat ini sengaja tidak ditautkan pada halaman
publik; bagikan hanya kepada panitia yang berwenang. Setelah login berhasil, admin diarahkan ke `/admin`.

Instalasi lokal ini membaca `.env` secara otomatis dan sudah memiliki kredensial awal berbentuk hash.
Plaintext password tidak disimpan di repository. Untuk mengganti password:

```bash
# Windows PowerShell
$hash = python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('password-baru-yang-kuat'))"
$env:ADMIN_PASSWORD_HASH = $hash
$env:SECRET_KEY = "ganti-dengan-random-secret-minimal-32-byte"
$env:SESSION_COOKIE_SECURE = "0" # hanya untuk localhost HTTP
python app.py
```

Untuk konfigurasi permanen, simpan hasil hash sebagai `ADMIN_PASSWORD_HASH` di `.env` lokal atau secret
manager platform. Jangan memakai `ADMIN_PASSWORD` plaintext untuk production.

Untuk deployment HTTPS, jangan set `SESSION_COOKIE_SECURE=0`. Salin daftar konfigurasi
dari `.env.example` ke secret/environment manager platform; jangan commit `.env`.

Dari halaman admin (`/admin`) kamu bisa:
- Buka **Mode Scorekeeper** untuk workflow ponsel: mulai pertandingan, tambah skor satu sentuhan,
  undo, konfirmasi selesai, dan koreksi hasil dengan alasan. Setiap aksi disimpan atomik dan dilindungi
  optimistic lock agar dua perangkat tidak menimpa skor diam-diam.
- Klik "Kelola" untuk input skor per game/set secara manual. Istilah, target, cap, dan validasinya mengikuti
  immutable rule profile Table Tennis, Badminton, atau Padel milik pertandingan.
- **Reschedule**: ubah tanggal/jam/meja pertandingan, riwayat perubahan tersimpan dan tampil di halaman detail publik.
- Pada stage eliminasi, peserta yang memenuhi syarat dari divisi yang sama dapat dipilih dari hasil kualifikasi.

## Rute aplikasi

| Rute | Isi |
|---|---|
| `/` | Beranda / infografis, hitung mundur, ringkasan |
| `/jadwal` | Jadwal lengkap + filter kategori/grup/tanggal/status |
| `/kalender` | Tampilan kalender 20–29 Juli |
| `/live` | Live score (auto-refresh tiap 15 detik) |
| `/klasemen` | Klasemen stage/grup dari konfigurasi divisi dan standing policy |
| `/bracket` | Kualifikasi dan stage eliminasi dari struktur kompetisi |
| `/aturan` | Profil aturan versioned dan format setiap divisi |
| `/rekap` | Rekap hasil pertandingan selesai |
| `/pertandingan/<id>` | Detail satu pertandingan |
| `/admin/login` | Gerbang autentikasi panitia turnamen |
| `/admin` | Tournament Command Center (login wajib) |
| `/api/matches` | JSON semua pertandingan (dipakai live polling) |
| `/api/v1/sports` | Daftar cabang, status aktif, dan jumlah divisi |
| `/api/v1/matches` | API pertandingan terfilter dan cursor-paginated |
| `/api/v1/matches/<id>` | Detail pertandingan normalized/legacy-compatible |
| `/api/v1/standings` | Klasemen policy-based; filter sport/division/stage/group + ETag |
| `/admin/scorekeeper` | Daftar operasional pertandingan untuk scorekeeper (login wajib) |
| `/admin/scorekeeper/<id>` | Konsol skor mobile-first dengan auto-save, undo, finish, dan koreksi |

## Interface dan design system

Seluruh halaman publik, admin, detail pertandingan, modal, dan scorekeeper memakai design system
blue–green–white dengan permukaan glass, kontras aksesibel, focus state keyboard, dan target sentuh mobile.
`static/css/style.css` tetap memuat struktur komponen lama, sedangkan `static/css/redesign.css` menjadi
lapisan visual utama sehingga perilaku turnamen tidak tercampur dengan perubahan branding. Pedoman dan
checklist visual lengkap tersedia di `docs/INTERFACE_REDESIGN.md`.

## Deploy

Karena ada admin panel yang menulis ke `data/matches.json`, aplikasi ini butuh **disk yang persisten**
antar-request — cocok untuk **Render / Railway / Fly.io / VPS**, dijalankan dengan WSGI server produksi, misalnya:

```bash
pip install gunicorn
gunicorn app:app --bind 0.0.0.0:$PORT
```

Konfigurasi production wajib: `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, dan HTTPS. Unggah media juga
memerlukan seluruh variabel S3 serta `PUBLIC_ASSET_BASE_URL` di `.env.example`. Request unggahan
dibatasi 8 MiB secara default.

## Automated tests

```bash
python -m unittest discover -v
```

Suite mencakup validasi Table Tennis, Badminton, dan Padel; tie-break dan policy klasemen; normalized
import; migration inventory; stage-driven public views; CSRF; security headers; konflik versi; serta
penolakan bentrok jadwal lapangan/peserta secara atomik. Scorekeeper diuji untuk start, point/game,
auto-complete segmen, undo, finish, correction, dan stale-version rejection.

## Status ekspansi multi-sport

Fondasi P0 dan bagian data/scoring P1 dari `MULTI_SPORT_EXPANSION_EVALUATION.md` sudah tersedia:

- Skor Table Tennis, Badminton, dan Padel divalidasi oleh domain service terpisah.
- Schema PostgreSQL normalized memakai hierarchy Tournament → Sport → Division → Stage → Group → Match.
- Importer legacy memakai UUID deterministik, checksum sumber, audit report, dan dry-run aman.
- Table Tennis aktif; Padel dan Badminton ada sebagai sport entity tetapi tetap nonaktif sampai format event dikonfirmasi.
- M01 dikarantina sebagai `suspended` saat import; perbedaan tanggal Final dilaporkan tanpa ditebak.
- Beranda menjadi event hub; klasemen, bracket, juara, rules, dan pemilihan peserta eliminasi membaca struktur
  `Division -> Stage -> Group`, bukan nama kategori atau string `FINAL` yang ditanam di template.
- Standing policy menentukan nilai menang/kalah/WO dan metadata versinya tersedia pada UI serta API standings.
- Perubahan jadwal dan peserta menolak bentrok waktu pada lapangan atau entrant yang sama di kedua backend.
- Scorekeeper mobile memakai event log append-only; skor yang di-undo mendapat reversal event, sementara
  completed game/set tetap menjadi satu-satunya sumber klasemen dan hasil publik.

Flask sekarang memiliki repository normalized yang dapat diaktifkan secara eksplisit. Default tetap
`STORAGE_BACKEND=legacy` sebagai rollback path. Saat normalized aktif, halaman publik/admin membaca dan menulis
entity PostgreSQL, navigasi dapat difilter melalui `?sport=table-tennis`, dan API `/api/v1` menyediakan filter
`sport`, `division`, `date`, `status`, cursor pagination, standings, serta ETag. Padel dan Badminton tetap nonaktif sampai
konfigurasi produk disetujui. Jangan menambahkan keduanya sebagai nilai `category` pada JSON lama.

### Dry-run dan import normalized

```bash
python manage.py plan-legacy-import

# PowerShell — setelah review report dan backup database
$env:DATABASE_URL = "postgresql://..."
python manage.py migrate-normalized
python manage.py import-legacy --apply

# Hanya setelah smoke test dan backup terverifikasi:
$env:STORAGE_BACKEND = "normalized"
$env:TOURNAMENT_SLUG = "intersport-2026"
python app.py
```

Importer menolak overwrite tournament yang sudah ada. `--replace` harus diberikan secara eksplisit dan hanya
dipakai setelah backup. Panduan lengkap ada di `docs/NORMALIZED_MIGRATION.md`. `migrate_db.py` tetap merupakan
migrator legacy `tennis.app_data`, bukan migrator normalized.

Rollback aplikasi tidak memerlukan reverse migration: hentikan write window, set
`STORAGE_BACKEND=legacy`, lalu restart. Jangan menerima write di kedua backend secara paralel.

**Catatan soal Vercel**: Vercel Python berjalan sebagai serverless function tanpa disk persisten —
perubahan skor lewat admin panel tidak akan tersimpan permanen di sana. Kalau kamu tetap ingin Vercel:
- Jalankan admin/update data secara lokal, lalu `git push` (Vercel akan auto-redeploy) setiap ada hasil baru, **atau**
- Ganti storage dari file JSON ke database eksternal (mis. Vercel KV / Upstash Redis) — beri tahu saya kalau mau saya siapkan versi ini.

## Data tim

Data tim & jadwal awal digenerate oleh `generate_data.py` dari data yang kamu berikan. Nomor 6 Ganda Putra
tidak ada di data sumber (loncat dari 5 ke 7), dan Ganda Campuran hanya tercatat Group A (4 tim) — sesuai
konfirmasi, hanya data yang terlihat yang dipakai. Kalau ada data tambahan/koreksi, edit `TEAMS` di
`generate_data.py` lalu jalankan ulang `python generate_data.py` (ini akan reset seluruh skor).
