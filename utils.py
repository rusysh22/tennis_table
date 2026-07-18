import json
import os
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_LOCK = threading.Lock()

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _path(name):
    return os.path.join(DATA_DIR, name)


def load_json(name):
    with _LOCK:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)


def save_json(name, data):
    with _LOCK:
        tmp = _path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path(name))


def load_teams():
    return load_json("teams.json")


def load_matches():
    return load_json("matches.json")


def save_matches(matches):
    save_json("matches.json", matches)


def load_config():
    return load_json("config.json")


def get_match(matches, match_id):
    for m in matches:
        if m["id"] == match_id:
            return m
    return None


def team_label(teams, code):
    if not code:
        return "TBD"
    t = teams.get(code)
    if not t:
        return code
    return f'{t["player1"]} / {t["player2"]}'


def team_short(teams, code):
    if not code:
        return "TBD"
    return code


def format_date_id(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{DAY_NAMES[d.weekday()]}, {d.day} {MONTH_NAMES[d.month]} {d.year}"


def compute_sets_won(sets):
    """sets: list of [score_a, score_b]. Returns (sets_a, sets_b)."""
    a = sum(1 for s in sets if s[0] > s[1])
    b = sum(1 for s in sets if s[1] > s[0])
    return a, b


def compute_winner(match):
    sets = match.get("sets") or []
    if not sets:
        return None
    a, b = compute_sets_won(sets)
    if a >= 3 or b >= 3:
        return match["team_a"] if a > b else match["team_b"]
    return None


def sync_winner(match):
    """Recompute winner/status from sets. Call whenever sets are updated."""
    w = compute_winner(match)
    match["winner"] = w
    if w:
        match["status"] = "completed"
    elif match["status"] == "completed":
        match["status"] = "scheduled"
    return match


def compute_standings(matches, teams, category, group):
    """Round robin standings for a category+group. Points: win=3, loss=0."""
    codes = [c for c, t in teams.items() if t["category"] == category and t["group"] == group]
    table = {
        c: {
            "code": c, "team": team_label(teams, c),
            "player1": teams[c].get("player1", ""), "player2": teams[c].get("player2", ""),
            "color": teams[c].get("color", "#9c9c9c"), "text": teams[c].get("text", "#ffffff"),
            "played": 0, "win": 0, "loss": 0,
            "set_win": 0, "set_loss": 0,
            "point_win": 0, "point_loss": 0,
            "points": 0,
        } for c in codes
    }
    relevant = [
        m for m in matches
        if m["category"] == category and m["group"] == group and m["status"] == "completed"
    ]
    for m in relevant:
        a, b = m["team_a"], m["team_b"]
        if a not in table or b not in table:
            continue
        sa, sb = compute_sets_won(m["sets"])
        pa = sum(s[0] for s in m["sets"])
        pb = sum(s[1] for s in m["sets"])
        table[a]["played"] += 1
        table[b]["played"] += 1
        table[a]["set_win"] += sa
        table[a]["set_loss"] += sb
        table[b]["set_win"] += sb
        table[b]["set_loss"] += sa
        table[a]["point_win"] += pa
        table[a]["point_loss"] += pb
        table[b]["point_win"] += pb
        table[b]["point_loss"] += pa
        if m["winner"] == a:
            table[a]["win"] += 1
            table[a]["points"] += 3
            table[b]["loss"] += 1
        elif m["winner"] == b:
            table[b]["win"] += 1
            table[b]["points"] += 3
            table[a]["loss"] += 1

    rows = list(table.values())
    for r in rows:
        r["set_diff"] = r["set_win"] - r["set_loss"]
        r["point_diff"] = r["point_win"] - r["point_loss"]
    rows.sort(key=lambda r: (-r["points"], -r["set_diff"], -r["point_diff"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def group_champion(matches, teams, category, group):
    played = [m for m in matches if m["category"] == category and m["group"] == group]
    completed = [m for m in played if m["status"] == "completed"]
    standings = compute_standings(matches, teams, category, group)
    if len(completed) < len(played) or not standings:
        return None
    return standings[0]["code"]
