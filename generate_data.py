"""
Generator data turnamen tenis meja (round robin) - tim, jadwal, konfigurasi.
Jalankan sekali untuk membuat/reset data/teams.json, data/matches.json, data/config.json.
Setelah itu, data match akan diupdate langsung lewat aplikasi (admin panel), bukan script ini.
"""
import json
import os
import random

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Warna identitas per tim: dipilih & divalidasi (lightness band + chroma floor
# lolos penuh; jarak warna dioptimalkan lewat scripts/validate_palette.js dari
# skill dataviz) supaya 12 tim tetap bisa dibedakan sekilas pandang. "text" =
# warna teks dengan kontras terbaik (dihitung dari rasio WCAG) di atas warna itu.
TEAMS = {
    # Ganda Putra - Group A
    "GS": {"category": "ganda_putra", "group": "A", "player1": "Gede Surya Atmaja", "player2": "Satwika Indramantanu", "color": "#2a78d6", "text": "#ffffff"},
    "RR": {"category": "ganda_putra", "group": "A", "player1": "Rafli Ananta Zikri", "player2": "Rizki Amrizal", "color": "#008300", "text": "#ffffff"},
    "NH": {"category": "ganda_putra", "group": "A", "player1": "Novandi Nasty Sandya", "player2": "Hendra Gunawan", "color": "#e87ba4", "text": "#000000"},
    "AD": {"category": "ganda_putra", "group": "A", "player1": "Adhitya Syafta", "player2": "Dea Aditya Trimukti", "color": "#eda100", "text": "#000000"},
    # Ganda Putra - Group B
    "AJ": {"category": "ganda_putra", "group": "B", "player1": "Aji Darmadi", "player2": "Julyzar Iskandar", "color": "#1baf7a", "text": "#000000"},
    "TP": {"category": "ganda_putra", "group": "B", "player1": "Tito Alfani", "player2": "Prayogi Akbar Putra", "color": "#eb6834", "text": "#000000"},
    "MW": {"category": "ganda_putra", "group": "B", "player1": "Mohammad Saifur Rahman", "player2": "Wahyu Harja Saputra", "color": "#4a3aa7", "text": "#ffffff"},
    "DJ": {"category": "ganda_putra", "group": "B", "player1": "Daffa Indrasta R", "player2": "Joko Santoso", "color": "#e34948", "text": "#000000"},
    # Ganda Campuran - Group A
    "MM": {"category": "ganda_campuran", "group": "A", "player1": "Muhammad Rusydani Shubkhi", "player2": "Mia R Mancani P", "color": "#7ca329", "text": "#000000"},
    "TL": {"category": "ganda_campuran", "group": "A", "player1": "Tegar Perkasa Darmawan", "player2": "Linda Astriyani", "color": "#aa3bb0", "text": "#ffffff"},
    "PA": {"category": "ganda_campuran", "group": "A", "player1": "Pawestri Wulan Ramadani", "player2": "Abraham Kaawoan", "color": "#169882", "text": "#000000"},
    "NG": {"category": "ganda_campuran", "group": "A", "player1": "Nevi Setyasih", "player2": "Gomfie Sidabutar", "color": "#b15425", "text": "#ffffff"},
}

CATEGORY_LABEL = {"ganda_putra": "Ganda Putra", "ganda_campuran": "Ganda Campuran"}


def circle_rounds(codes):
    """Round robin jadwal untuk 4 tim -> 3 babak x 2 laga (metode lingkaran)."""
    t1, t2, t3, t4 = codes
    return [
        [(t1, t4), (t2, t3)],
        [(t1, t3), (t4, t2)],
        [(t1, t2), (t3, t4)],
    ]


def shuffle_putra_groups(matches, teams):
    """Undi ulang keanggotaan Grup A & Grup B Ganda Putra dari 8 tim yang ada,
    supaya lawan tanding tiap tim benar-benar berubah -- bukan cuma urutan babak
    (di round robin 4 tim, semua pasangan tetap ketemu apa pun urutannya, jadi
    yang perlu diacak adalah SIAPA masuk grup mana, bukan urutan dalam grup yang
    sama). Tanggal/jam/meja tiap slot serta laga Ganda Campuran/Final tidak disentuh.
    Skor & status laga Ganda Putra yang terdampak direset karena pasangannya berubah."""
    all_putra = [c for c, t in teams.items() if t["category"] == "ganda_putra"]
    random.shuffle(all_putra)
    new_a, new_b = all_putra[:4], all_putra[4:]

    for code in new_a:
        teams[code]["group"] = "A"
    for code in new_b:
        teams[code]["group"] = "B"

    queue_a = [pair for rnd in circle_rounds(new_a) for pair in rnd]
    queue_b = [pair for rnd in circle_rounds(new_b) for pair in rnd]

    idx_a = idx_b = 0
    for m in matches:
        if m["category"] != "ganda_putra" or m["group"] not in ("A", "B"):
            continue
        if m["group"] == "A":
            a, b = queue_a[idx_a]
            idx_a += 1
        else:
            a, b = queue_b[idx_b]
            idx_b += 1
        m["team_a"], m["team_b"] = a, b
        m["status"] = "scheduled"
        m["sets"] = []
        m["winner"] = None
        m["walkover"] = False
        m["notes"] = ""
    return matches, teams


def shuffle_campuran_group(matches):
    """Undi ulang urutan babak Ganda Campuran (cuma 1 grup, 4 tim). Beda dari
    Ganda Putra: di sini tidak ada keanggotaan grup yang bisa diacak (cuma ada
    Grup A, isinya tetap 4 tim yang sama) -- yang berubah adalah SIAPA ketemu
    SIAPA di tanggal mana (urutan babak 1/2/3), karena tiap tim tetap ketemu
    semua tim lain persis 1x apa pun urutannya. Tanggal/jam/meja tiap slot serta
    laga Ganda Putra/Final tidak disentuh. Skor & status laga Ganda Campuran
    yang terdampak direset karena pasangannya berubah."""
    codes = [c for c, t in TEAMS.items() if t["category"] == "ganda_campuran" and t["group"] == "A"]
    random.shuffle(codes)
    queue = [pair for rnd in circle_rounds(codes) for pair in rnd]

    idx = 0
    for m in matches:
        if m["category"] != "ganda_campuran":
            continue
        a, b = queue[idx]
        idx += 1
        m["team_a"], m["team_b"] = a, b
        m["status"] = "scheduled"
        m["sets"] = []
        m["winner"] = None
        m["walkover"] = False
        m["notes"] = ""
    return matches


def build_matches():
    matches = []
    mid = 1

    def add(category, group, round_no, round_label, a, b, date, time, court):
        nonlocal mid
        matches.append({
            "id": f"M{mid:02d}",
            "category": category,
            "category_label": CATEGORY_LABEL[category],
            "group": group,
            "round": round_no,
            "round_label": round_label,
            "team_a": a,
            "team_b": b,
            "date": date,
            "time": time,
            "court": court,
            "status": "scheduled",
            "sets": [],
            "winner": None,
            "walkover": False,
            "notes": "",
            "reschedule_history": [],
        })
        mid += 1

    gp_a = circle_rounds(["GS", "RR", "NH", "AD"])
    gp_b = circle_rounds(["AJ", "TP", "MW", "DJ"])
    gc_a = circle_rounds(["MM", "TL", "PA", "NG"])

    # Hanya 1 meja tersedia -> laga berurutan (bukan paralel) dalam jendela
    # 18.00-20.00 WIB, maksimal 4 slot per hari (per laga sekitar 30 menit).
    TABLE = "Meja 1"
    TIME_SLOTS = ["18:00", "18:30", "19:00", "19:30"]

    # Jadwal fase grup: 20, 21, 22, 23, 27, 28 Juli 2026.
    # - 24 (Jumat), 25 (Sabtu), 26 (Minggu) sengaja dikosongkan -- tidak ada
    #   laga di akhir pekan, dan 24 jadi hari cadangan reschedule.
    # - 23 Juli cuma 1 laga.
    # - Final digeser dari 28 ke 29 Juli (jadi satu hari dengan Penutupan)
    #   supaya seluruh fase grup (termasuk yang di 28) sudah selesai duluan
    #   sebelum Final dimainkan -- Final baru bisa ditentukan (Juara Grup A vs
    #   Juara Grup B) setelah semua laga grup rampung, jadi tidak boleh ada
    #   laga grup di tanggal yang sama atau setelah Final.
    # Ganda campuran disebar 1 laga/hari di tiap hari yang ada laga campuran
    # (tidak pernah lebih dari 1, tidak pernah kosong di hari itu) supaya tidak
    # ada hari yang isinya ganda putra semua; sisa slot per hari diisi ganda
    # putra mengikuti urutan babak masing-masing grup.
    plan = [
        ("2026-07-20", [
            ("ganda_campuran", "A", 1, gc_a[0][0]),
            ("ganda_putra", "A", 1, gp_a[0][0]),
            ("ganda_putra", "A", 1, gp_a[0][1]),
            ("ganda_putra", "B", 1, gp_b[0][0]),
        ]),
        ("2026-07-21", [
            ("ganda_campuran", "A", 1, gc_a[0][1]),
            ("ganda_putra", "B", 1, gp_b[0][1]),
            ("ganda_putra", "A", 2, gp_a[1][0]),
        ]),
        ("2026-07-22", [
            ("ganda_campuran", "A", 2, gc_a[1][0]),
            ("ganda_putra", "A", 2, gp_a[1][1]),
            ("ganda_putra", "B", 2, gp_b[1][0]),
        ]),
        ("2026-07-23", [
            ("ganda_campuran", "A", 2, gc_a[1][1]),
        ]),
        # 2026-07-24, 25, 26: sengaja dikosongkan (Jumat cadangan, Sabtu-Minggu libur)
        ("2026-07-27", [
            ("ganda_campuran", "A", 3, gc_a[2][0]),
            ("ganda_putra", "B", 2, gp_b[1][1]),
            ("ganda_putra", "A", 3, gp_a[2][0]),
        ]),
        ("2026-07-28", [
            ("ganda_campuran", "A", 3, gc_a[2][1]),
            ("ganda_putra", "A", 3, gp_a[2][1]),
            ("ganda_putra", "B", 3, gp_b[2][0]),
            ("ganda_putra", "B", 3, gp_b[2][1]),
        ]),
    ]

    round_label_map = {1: "Babak 1", 2: "Babak 2", 3: "Babak 3"}

    for date, day_matches in plan:
        for idx, (category, group, round_no, (a, b)) in enumerate(day_matches):
            add(category, group, round_no, round_label_map[round_no], a, b, date, TIME_SLOTS[idx], TABLE)

    # Grand Final Ganda Putra: Juara Group A vs Juara Group B (tim ditentukan setelah fase grup).
    # Digelar 29 Juli, sehari setelah laga grup terakhir (28 Juli) -- sekaligus jadi hari Penutupan.
    add("ganda_putra", "FINAL", 4, "Final", None, None, "2026-07-29", "18:00", "Meja 1")

    return matches


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(os.path.join(DATA_DIR, "teams.json"), "w", encoding="utf-8") as f:
        json.dump(TEAMS, f, ensure_ascii=False, indent=2)

    matches = build_matches()
    with open(os.path.join(DATA_DIR, "matches.json"), "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    config = {
        "tournament_name": "Mini-Round Table Tennis InterSport 2026",
        "tournament_short_name": "InterSport 2026",
        "start_date": "2026-07-20",
        "end_date": "2026-07-29",
        "buffer_dates": ["2026-07-24"],
        "final_date": "2026-07-29",
        "closing_date": "2026-07-29",
        "time_window": "18.00 - 20.00 WIB",
        "time_window_note": "After Office Hours",
        "venue": "Gedung Graha Mitra Lantai 2",
        "final_note": "Final Ganda Putra mempertemukan Juara Group A vs Juara Group B",
        "categories": [
            {"key": "ganda_putra", "label": "Ganda Putra", "groups": ["A", "B"], "has_final": True},
            {"key": "ganda_campuran", "label": "Ganda Campuran", "groups": ["A"], "has_final": False},
        ],
    }
    config_path = os.path.join(DATA_DIR, "config.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(TEAMS)} teams and {len(matches)} matches.")


if __name__ == "__main__":
    main()
