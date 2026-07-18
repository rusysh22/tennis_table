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

Buka `/admin/login`. Password default: `pingpong2026`.

**Ganti password sebelum situs ini publik**, dengan set environment variable `ADMIN_PASSWORD`:

```bash
# Windows PowerShell
$env:ADMIN_PASSWORD = "password-baru-yang-kuat"
python app.py
```

Dari halaman admin (`/admin`) kamu bisa:
- Klik "Kelola" pada tiap pertandingan untuk **input skor per set (live score)** — status otomatis
  jadi "Selesai" begitu satu tim mencapai 3 kemenangan set.
- **Reschedule**: ubah tanggal/jam/meja pertandingan, riwayat perubahan tersimpan dan tampil di halaman detail publik.
- Untuk laga **Final Ganda Putra**, begitu seluruh laga grup A & B selesai, juara masing-masing grup
  otomatis terdeteksi — tinggal pilih dari dropdown lalu simpan.

## Rute publik

| Rute | Isi |
|---|---|
| `/` | Beranda / infografis, hitung mundur, ringkasan |
| `/jadwal` | Jadwal lengkap + filter kategori/grup/tanggal/status |
| `/kalender` | Tampilan kalender 20–29 Juli |
| `/live` | Live score (auto-refresh tiap 15 detik) |
| `/klasemen` | Klasemen tiap grup |
| `/bracket` | Bracket final Ganda Putra + klasemen Ganda Campuran |
| `/rekap` | Rekap hasil pertandingan selesai |
| `/pertandingan/<id>` | Detail satu pertandingan |
| `/api/matches` | JSON semua pertandingan (dipakai live polling) |

## Deploy

Karena ada admin panel yang menulis ke `data/matches.json`, aplikasi ini butuh **disk yang persisten**
antar-request — cocok untuk **Render / Railway / Fly.io / VPS**, dijalankan dengan WSGI server produksi, misalnya:

```bash
pip install gunicorn
gunicorn app:app --bind 0.0.0.0:$PORT
```

**Catatan soal Vercel**: Vercel Python berjalan sebagai serverless function tanpa disk persisten —
perubahan skor lewat admin panel tidak akan tersimpan permanen di sana. Kalau kamu tetap ingin Vercel:
- Jalankan admin/update data secara lokal, lalu `git push` (Vercel akan auto-redeploy) setiap ada hasil baru, **atau**
- Ganti storage dari file JSON ke database eksternal (mis. Vercel KV / Upstash Redis) — beri tahu saya kalau mau saya siapkan versi ini.

## Data tim

Data tim & jadwal awal digenerate oleh `generate_data.py` dari data yang kamu berikan. Nomor 6 Ganda Putra
tidak ada di data sumber (loncat dari 5 ke 7), dan Ganda Campuran hanya tercatat Group A (4 tim) — sesuai
konfirmasi, hanya data yang terlihat yang dipakai. Kalau ada data tambahan/koreksi, edit `TEAMS` di
`generate_data.py` lalu jalankan ulang `python generate_data.py` (ini akan reset seluruh skor).
