# Rekap Peserta — Interport Synergy Cup 2026

Sumber: rekap Excel per cabang olahraga (Padel, Badminton, Tenis Meja), kategori Ganda Putra / Ganda Campuran / Cadangan.
Disusun ulang dalam format tabular flat agar mudah di-import ke database (lihat [Mapping ke Skema DB](#mapping-ke-skema-db) di bagian akhir).

**Kolom:**
- `sport` — kode cabang: `padel`, `badminton`, `table_tennis`
- `category` — `ganda_putra`, `ganda_campuran`, `cadangan`
- `position` — posisi dalam entrant (mis. `pemain_1`, `pemain_putra`, `cadangan_putri`)
- `site` — site/lokasi asal peserta
- `name` — nama peserta (`null` = belum diisi panitia site)
- `nik` — NIK / employee reference (format `CTA-xx-xxx` untuk site tertentu)
- `jersey_size` — ukuran jersey
- `status` — status kelengkapan data (`Lengkap`, `Perlu Konfirmasi`, `Kosong`)
- `note` — catatan tambahan

---

## 1. Padel

### Ganda Putra
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_1 | Agustian Gozali | 22070773 | L | Lengkap |
| 2 | Babelan Patriot | pemain_2 | Rifal Fauzi | 24040953 | XXL | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_1 | Achmad Zaidan | 21070727 | XL | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_2 | Abdul Zulkifli Perangin Angin | 21040667 | XL | Lengkap |
| 5 | Jakarta Jawara | pemain_1 | Tito Alfani | 20050369 | XL | Lengkap |
| 6 | Jakarta Jawara | pemain_2 | Prayogi Akbar Putra | 19100328 | XXXL | Lengkap |
| 7 | Paser Buen Kesong | pemain_1 | Ariyanto Sandi | CTA-22-062 | XXL | Lengkap |
| 8 | Paser Buen Kesong | pemain_2 | Gerhana Budi Wijaya | CTA-26-096 | L | Lengkap |
| 9 | Surabaya Joang | pemain_1 | Gusna Arfian | 25101222 | L | Lengkap |
| 10 | Surabaya Joang | pemain_2 | Muhammad Reza Amirullah | 25091199 | S | Lengkap |

### Ganda Campuran
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_putra | Akmaluddin | 25091219 | L | Lengkap |
| 2 | Babelan Patriot | pemain_putri | Adinda Fadiah | — | L | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_putra | Dayan Naibaho | 25011017 | L | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_putri | Nadia Chita Sandra | 25071157 | L | Lengkap |
| 5 | Jakarta Jawara | pemain_putra | Dimas C Wihatmoko | 25011090 | M | Lengkap |
| 6 | Jakarta Jawara | pemain_putri | Griska Devinta Debby | 20030365 | S | Lengkap |
| 7 | Paser Buen Kesong | pemain_putra | Suharista Rio Ambowo | CTA-25-089 | 6XL | Lengkap |
| 8 | Paser Buen Kesong | pemain_putri | Septy Wahyuningsih | CTA-23-071 | XL | Lengkap |
| 9 | Surabaya Joang | pemain_putra | **Nama belum diisi** | — | S | **Kosong** |
| 10 | Surabaya Joang | pemain_putri | **Nama belum diisi** | — | XXXL | **Kosong** |

### Cadangan
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | cadangan_putra | Rendy Ramadhan Zein | 24101013 | XL | Lengkap |
| 2 | Balikpapan Marwah Warriors | cadangan_putra | Ricky Aprilyanto | 25081191 | XL | Lengkap |
| 3 | Balikpapan Marwah Warriors | cadangan_putri | Tirsa Awuy | 22110787 | L | Lengkap |
| 4 | Jakarta Jawara | cadangan_putra | Muhammad Kemal Hussein | 19100322 | XL | Lengkap |
| 5 | Jakarta Jawara | cadangan_putri | Anggun Citra Listiyani | 26041343 | XS | Lengkap |
| 6 | Paser Buen Kesong | cadangan_putra | M. Al Hafiz | CTA-18-041 | XXL | Lengkap |
| 7 | Paser Buen Kesong | cadangan_putri | Linda Rafikasari | CTA-25-091 | L | Lengkap |
| 8 | Surabaya Joang | cadangan_putri | **Nama belum diisi** | — | XXXL | **Kosong** |

---

## 2. Badminton

### Ganda Putra
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_1 | Khoirul Imam Aditya | 24081003 | XL | Lengkap |
| 2 | Babelan Patriot | pemain_2 | Chandra Herdiansyah | 24040951 | XXL | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_1 | Stenly Hendri | 25011087 | XXL | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_2 | Poniran | 25011058 | XL | Lengkap |
| 5 | Jakarta Jawara | pemain_1 | Raka Awfa Ghithraf Safari | 2041383 | L | Lengkap |
| 6 | Jakarta Jawara | pemain_2 | Adhitya Syafta | 19100294 | XXXL | Lengkap |
| 7 | Morowali Titans | pemain_1 | Rudy Indrayadi | 26011278 | L | Lengkap |
| 8 | Morowali Titans | pemain_2 | Zulfikar Ramadan | 26021338 | L | Lengkap |
| 9 | Paser Buen Kesong | pemain_1 | M. Al Hafiz | CTA-18-041 | XXL | Lengkap |
| 10 | Paser Buen Kesong | pemain_2 | Hazlan | 25041117 | L | Lengkap |
| 11 | Surabaya Joang | pemain_1 | Faizal Arief Pratama | 25091220 | M | Lengkap |
| 12 | Surabaya Joang | pemain_1 | **Nama belum diisi** | — | L | **Perlu Konfirmasi** |
| 13 | Surabaya Joang | pemain_2 | Aditya Widyo Nugroho | 25101229 | M | Lengkap |

> ⚠️ Baris 11–12 sama-sama tercatat sebagai `pemain_1` untuk Surabaya Joang — kemungkinan duplikat slot / perlu klarifikasi ke PIC site sebelum di-import sebagai entrant terpisah.

### Ganda Campuran
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_putra | Muh Yusli Bahtiar | 21030657 | XL | Lengkap |
| 2 | Babelan Patriot | pemain_putri | Adinda Fadia | — | L | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_putra | Diky Ramannda | 20060465 | L | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_putri | Tirsa Awuy | 22110787 | L | Lengkap |
| 5 | Jakarta Jawara | pemain_putra | Rizkiakbar Foresandhi | 25091194 | XXL | Lengkap |
| 6 | Jakarta Jawara | pemain_putri | Linda Astriyani | 26061392 | M | Lengkap |
| 7 | Paser Buen Kesong | pemain_putra | Abdul Rajak | 25041115 | M | Lengkap |
| 8 | Paser Buen Kesong | pemain_putri | Nourmalisa | CTA-22-060 | L | Lengkap |
| 9 | Surabaya Joang | pemain_putra | Gusna Arfian | 25101222 | L | Lengkap |
| 10 | Surabaya Joang | pemain_putri | Hilda Yustiniar | 19100315 | L | Lengkap |

### Cadangan
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | cadangan_putra | Sigit Komaroji | 24040947 | XL | Lengkap |
| 2 | Balikpapan Marwah Warriors | cadangan_putra | Dayan Naibaho | 25011017 | L | Lengkap |
| 3 | Balikpapan Marwah Warriors | cadangan_putri | Nadia Chita Sandra | 25071157 | L | Lengkap |
| 4 | Jakarta Jawara | cadangan_putra | Novandi Nasty Sandya | 26021332 | XL | Lengkap |
| 5 | Jakarta Jawara | cadangan_putri | Pawestri Wulan Ramadani | 25071150 | L | Lengkap |
| 6 | Morowali Titans | cadangan_putra | Asnawi | 24010904 | M | Lengkap |
| 7 | Paser Buen Kesong | cadangan_putra | Natalias Padatu T. | CTA-08-025 | XL | Lengkap |
| 8 | Paser Buen Kesong | cadangan_putri | Septy Wahyuningsih | CTA-23-071 | L | Lengkap |

---

## 3. Tenis Meja (Table Tennis)

### Ganda Putra
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_1 | Giyarto | 24121081 | XL | Lengkap |
| 2 | Babelan Patriot | pemain_2 | Agus Seramto | — | L | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_1 | Firmansyah | 20060470 | XL | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_2 | Endra Kurniawan | 25011032 | XXXL | Lengkap |
| 5 | Jakarta Jawara | pemain_1 | Rafli Ananta Zikri | 26051387 | S | Lengkap |
| 6 | Jakarta Jawara | pemain_2 | Rizki Amrizal | 23120891 | M | Lengkap |
| 7 | Paser Buen Kesong | pemain_1 | Mulyadi | CTA-24-076 | L | Lengkap |
| 8 | Paser Buen Kesong | pemain_2 | Natalias Padatu T. | CTA-08-025 | XL | Lengkap |
| 9 | Surabaya Joang | pemain_1 | Jannata Prijandi | 25101231 | XXXXL / XXXXXL | **Perlu Konfirmasi** |
| 10 | Surabaya Joang | pemain_2 | Dwi Widodo | 25101228 | L | Lengkap |

> ⚠️ Baris 9: ukuran jersey tertulis ganda (`XXXXL / XXXXXL`) — perlu satu nilai pasti sebelum order jersey / import ke DB.

### Ganda Campuran
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | pemain_putra | Erwin Iswanto | 24091008 | L | Lengkap |
| 2 | Babelan Patriot | pemain_putri | Hilda Husni T | — | L | Lengkap |
| 3 | Balikpapan Marwah Warriors | pemain_putra | Muttaqin | 25011039 | M | Lengkap |
| 4 | Balikpapan Marwah Warriors | pemain_putri | Oktavia Lija Setyana Situmeang | 21040676 | XXL | Lengkap |
| 5 | Jakarta Jawara | pemain_putra | Abraham Kaawoan | 25051122 | XL | Lengkap |
| 6 | Jakarta Jawara | pemain_putri | Pawestri Wulan Ramadani | 25071150 | L | Lengkap |
| 7 | Paser Buen Kesong | pemain_putra | Bayu Pratama Salesi | 26071408 | M | Lengkap |
| 8 | Paser Buen Kesong | pemain_putri | Linda Rafikasari | CTA-25-091 | L | Lengkap |

### Cadangan
| No | Site | Position | Name | NIK | Jersey | Status |
|---|---|---|---|---|---|---|
| 1 | Babelan Patriot | cadangan_putra | Subakir | 24040961 | XL | Lengkap |
| 2 | Balikpapan Marwah Warriors | cadangan_putra | Hendrik | 23090873 | XL | Lengkap |
| 3 | Balikpapan Marwah Warriors | cadangan_putri | Tirsa Awuy | 22110787 | L | Lengkap |
| 4 | Paser Buen Kesong | cadangan_putra | Hazlan | 25041117 | L | Lengkap |
| 5 | Paser Buen Kesong | cadangan_putri | Nourmalisa | CTA-22-060 | L | Lengkap |

---

## Ringkasan Jumlah

| Sport | Ganda Putra | Ganda Campuran | Cadangan | Total | Kosong/Perlu Konfirmasi |
|---|---|---|---|---|---|
| Padel | 10 | 10 | 8 | 28 | 3 |
| Badminton | 13 | 10 | 8 | 31 | 1 |
| Tenis Meja | 10 | 8 | 5 | 23 | 1 |
| **Total** | **33** | **28** | **21** | **82** | **5** |

## Data yang Perlu Ditindaklanjuti (blocker sebelum import final)

1. **Padel — Surabaya Joang**: 3 slot `Nama belum diisi` (Ganda Campuran Putra, Ganda Campuran Putri, Cadangan Putri).
2. **Badminton — Surabaya Joang**: 1 slot `Nama belum diisi` di Ganda Putra `pemain_1`, plus kemungkinan duplikat posisi dengan baris Faizal Arief Pratama — perlu klarifikasi ke PIC site.
3. **Tenis Meja — Surabaya Joang**: ukuran jersey Jannata Prijandi ganda (`XXXXL / XXXXXL`), perlu 1 nilai final.
4. Beberapa peserta tanpa NIK (mis. Adinda Fadiah/Fadia, Hilda Husni T, Agus Seramto) — kemungkinan NIK belum diinput, bukan berarti kosong secara sah. Perlu verifikasi sebelum dianggap data final.
5. Perhatikan penulisan nama yang tidak konsisten antar sheet untuk orang yang sama (kemungkinan orang yang sama tampil di lebih dari satu sport dengan ejaan berbeda), contoh:
   - `Tirsa Awuy` (Padel Cadangan Putri, Badminton Ganda Campuran Putri, Tenis Meja Cadangan Putri) — NIK konsisten `22110787`.
   - `Nourmalisa` / `CTA-22-060` muncul di Badminton Ganda Campuran & Tenis Meja Cadangan.
   - `Natalias Padatu T.` / `CTA-08-025` muncul di Badminton Cadangan & Tenis Meja Ganda Putra.
   - `Linda Rafikasari` / `CTA-25-091` muncul di Padel Cadangan & Tenis Meja Ganda Campuran.
   - `Dayan Naibaho` / `25011017` muncul di Padel Ganda Putra & Badminton Cadangan.
   - `Nadia Chita Sandra` / `25071157` muncul di Padel Ganda Campuran & Badminton Cadangan.
   - `Hazlan` / `25041117` muncul di Badminton Ganda Putra & Tenis Meja Cadangan.
   - `Septy Wahyuningsih` / `CTA-23-071` muncul di Padel Ganda Campuran & Badminton Cadangan.

   → Jika NIK sama untuk nama yang sama, ini konfirmasi bahwa 1 orang bermain di multi-cabang (normal untuk peserta lintas cabang) — pastikan skema `people` dideduplikasi berdasarkan `nik`, bukan dibuat baru per baris/per sport.

---

## Mapping ke Skema DB

Berdasarkan `migrations/0001_normalized_multisport_core.sql`, struktur target adalah:

- **`intersport.people`** — 1 baris per orang unik, dedup berdasarkan `nik` (simpan di `employee_reference` atau kolom NIK khusus). `display_name` = kolom `name`.
- **`intersport.sports`** — 3 baris tetap: `padel`, `badminton`, `table_tennis`.
- **`intersport.divisions`** — per sport, 3 division: `ganda_putra`, `ganda_campuran`, `cadangan` (entrant_type `team`, `min/max_team_size` = 2 untuk ganda, 1 untuk cadangan individual jika cadangan tidak dipasangkan).
- **`intersport.entrants`** — 1 entrant per pasangan (site + posisi 1/2), `code` bisa dibentuk dari `{site_slug}-{sport}-{category}`, `display_name` = nama site/team.
- **`intersport.entrant_members`** — relasi `entrant_id` ↔ `person_id`, `member_role` = `pemain_1`/`pemain_2`/dst dari kolom `position`, `member_order` = 1 atau 2.
- **Ukuran jersey & status kelengkapan** tidak ada kolom native di skema saat ini — simpan sementara di `entrant_members.source_metadata` (jsonb) atau `people.source_metadata`, misalnya:
  ```json
  { "jersey_size": "XL", "data_status": "Lengkap", "site": "Babelan Patriot" }
  ```
  atau tambahkan kolom baru via migration terpisah jika jersey size perlu di-query/reporting secara reguler (mis. untuk rekap pemesanan jersey ke vendor).

**Catatan import**: baris dengan `Name = "Nama belum diisi"` sebaiknya **tidak** di-insert ke `people`/`entrant_members` dulu — buat entrant dengan slot kosong (`member_order` tanpa `person_id`, atau tandai `status: pending`) supaya tidak mencemari data peserta final, lalu update begitu PIC site mengisi.
