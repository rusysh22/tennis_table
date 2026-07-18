"""
Migrasi database: membuat skema/tabel di Postgres (schema "tennis", terisolasi
dari tabel lain di database yang sama) dan mengisi data awal dari
data/teams.json, data/matches.json, data/config.json.

Aman dijalankan berulang kali (idempotent) -- CREATE TABLE IF NOT EXISTS,
dan data di-upsert (menimpa isi tabel dengan isi file lokal saat ini).

Jalankan sekali dengan DATABASE_URL di-set, contoh (PowerShell):
    $env:DATABASE_URL = "postgresql://..."; python migrate_db.py
"""
import json
import os
import sys

if not os.environ.get("DATABASE_URL"):
    sys.exit("DATABASE_URL belum di-set. Contoh: $env:DATABASE_URL = '...'; python migrate_db.py")

import utils  # noqa: E402  (import setelah cek env var supaya USE_DB kebaca benar)


def main():
    if not utils.USE_DB:
        sys.exit("utils.USE_DB bernilai False -- DATABASE_URL tidak terbaca dengan benar.")

    for name in ("teams.json", "matches.json", "config.json"):
        with open(utils._path(name), "r", encoding="utf-8") as f:
            data = json.load(f)
        utils.save_json(name, data)
        count = len(data) if isinstance(data, (list, dict)) else 1
        print(f"  {name:14s} -> tennis.app_data  ({count} entri)")

    print("Selesai. Skema tennis.app_data / tennis.app_data_backups siap, data awal sudah di-seed.")


if __name__ == "__main__":
    main()
