import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash, send_file
)
import boto3
import io
import uuid
from PIL import Image

import og_image
import utils

app = Flask(__name__)

SECRET_PATH = os.path.join(os.path.dirname(__file__), ".secret_key")
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    try:
        if os.path.exists(SECRET_PATH):
            with open(SECRET_PATH, "r") as f:
                app.secret_key = f.read().strip()
    except OSError:
        pass  # filesystem tidak bisa dibaca (mis. serverless) - lanjut ke fallback di bawah
if not app.secret_key:
    app.secret_key = os.urandom(24).hex()
    try:
        with open(SECRET_PATH, "w") as f:
            f.write(app.secret_key)
    except OSError:
        pass  # filesystem read-only (mis. Vercel) - key tetap dipakai, cuma tidak tersimpan
               # ke disk sehingga bisa beda tiap cold start (sesi admin akan ter-logout).
               # Set env var SECRET_KEY di hosting supaya key konsisten antar-instance.

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pingpong2026")

SUPABASE_S3_ENDPOINT = os.environ.get("SUPABASE_S3_ENDPOINT", "https://jfutygknyhqfqfyhqhvy.storage.supabase.co/storage/v1/s3")
SUPABASE_REGION = os.environ.get("SUPABASE_REGION", "ap-northeast-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")

def compress_and_upload_image(file, match_id):
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return None, "Konfigurasi S3 (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) belum diset di environment."
    try:
        img = Image.open(file)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Compress the image
        img.thumbnail((1200, 1200)) # Resize if larger than 1200px
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=75, optimize=True)
        output.seek(0)
        
        filename = f"docs/{match_id}_{uuid.uuid4().hex[:8]}.jpg"
        
        s3_client = boto3.client(
            's3',
            endpoint_url=SUPABASE_S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=SUPABASE_REGION
        )
        s3_client.upload_fileobj(
            output,
            S3_BUCKET_NAME,
            filename,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        
        file_url = f"https://jfutygknyhqfqfyhqhvy.supabase.co/storage/v1/object/public/{S3_BUCKET_NAME}/{filename}"
        return file_url, None
    except Exception as e:
        return None, str(e)

def delete_from_supabase(file_url):
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return
    try:
        prefix = f"https://jfutygknyhqfqfyhqhvy.supabase.co/storage/v1/object/public/{S3_BUCKET_NAME}/"
        if file_url.startswith(prefix):
            filename = file_url[len(prefix):]
            s3_client = boto3.client(
                's3',
                endpoint_url=SUPABASE_S3_ENDPOINT,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=SUPABASE_REGION
            )
            s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=filename)
    except Exception:
        pass

ROUND_LABELS = {1: "Babak 1", 2: "Babak 2", 3: "Babak 3", 4: "Final"}
STATUS_LABELS = {
    "scheduled": "Terjadwal",
    "live": "Live",
    "completed": "Selesai",
    "postponed": "Ditunda",
}


# ---------- helpers ----------

TBD_COLOR = "#9c9c9c"
TBD_TEXT = "#ffffff"


def enrich_match(m, teams):
    m = dict(m)
    m["team_a_label"] = utils.team_label(teams, m["team_a"])
    m["team_b_label"] = utils.team_label(teams, m["team_b"])
    m["team_a_code"] = m["team_a"] or "TBD"
    m["team_b_code"] = m["team_b"] or "TBD"
    ta = teams.get(m["team_a"], {})
    tb = teams.get(m["team_b"], {})
    m["team_a_color"] = ta.get("color", TBD_COLOR)
    m["team_a_text"] = ta.get("text", TBD_TEXT)
    m["team_b_color"] = tb.get("color", TBD_COLOR)
    m["team_b_text"] = tb.get("text", TBD_TEXT)
    m["team_a_player1"] = ta.get("player1", "TBD")
    m["team_a_player2"] = ta.get("player2", "")
    m["team_b_player1"] = tb.get("player1", "TBD")
    m["team_b_player2"] = tb.get("player2", "")
    m["date_label"] = utils.format_date_id(m["date"])
    m["status_label"] = STATUS_LABELS.get(m["status"], m["status"])
    m["is_walkover"] = bool(m.get("walkover"))
    sa, sb = utils.compute_sets_won(m["sets"]) if m["sets"] else (0, 0)
    m["sets_a"] = sa
    m["sets_b"] = sb
    m["sets_needed"] = utils.sets_needed_to_win(m)
    m["best_of_label"] = "Best of 5" if m["sets_needed"] == 3 else "Best of 3"
    
    m["winner"] = None
    if m["status"] == "completed":
        if sa > sb: m["winner"] = "a"
        elif sb > sa: m["winner"] = "b"
        
    m["comments"] = m.get("comments", [])
    
    # Voting logic
    match_dt_str = f"{m['date']} {m['time']}"
    try:
        match_dt = datetime.strptime(match_dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=7)))
        m["is_voting_open"] = utils.now_wib() < match_dt - timedelta(hours=1)
    except:
        m["is_voting_open"] = False
        
    if m["status"] == "completed":
        m["is_voting_open"] = False
        
    m["votes"] = m.get("votes", {"a": {}, "b": {}})
    total_a = sum(m["votes"]["a"].values())
    total_b = sum(m["votes"]["b"].values())
    total_votes = total_a + total_b
    
    m["vote_total_a"] = total_a
    m["vote_total_b"] = total_b
    if total_votes > 0:
        m["vote_pct_a"] = int(round((total_a / total_votes) * 100))
        m["vote_pct_b"] = 100 - m["vote_pct_a"]
    else:
        m["vote_pct_a"] = 0
        m["vote_pct_b"] = 0
        
    return m


@app.template_filter("truncate_words")
def truncate_words(text, max_words=2):
    return utils.truncate_words(text, max_words)


@app.template_filter("format_datetime_id")
def format_datetime_id(value):
    return utils.format_datetime_id(value)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def data_context():
    teams = utils.load_teams()
    matches = utils.load_matches()
    config = utils.load_config()
    return teams, matches, config


@app.context_processor
def inject_globals():
    config = utils.load_config()
    return {
        "config": config,
        "is_admin": bool(session.get("is_admin")),
        "now": utils.now_wib(),
    }


@app.teardown_appcontext
def _close_db_connection(exception=None):
    if utils.USE_DB:
        utils.close_request_connection()


# ---------- public routes ----------

@app.route("/")
def index():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]
    today = utils.now_wib().strftime("%Y-%m-%d")

    upcoming = sorted(
        [m for m in enriched if m["status"] in ("scheduled", "live") and m["date"] >= today],
        key=lambda m: (m["date"], m["time"]),
    )[:6]
    live_now = [m for m in enriched if m["status"] == "live"]
    recent = sorted(
        [m for m in enriched if m["status"] == "completed"],
        key=lambda m: (m["date"], m["time"]), reverse=True,
    )[:4]

    total_matches = len(matches)
    completed_count = sum(1 for m in matches if m["status"] == "completed")

    all_comments = []
    for m in enriched:
        if m["status"] == "completed":
            continue
        if m.get("comments"):
            for c in m["comments"]:
                all_comments.append({
                    "name": c["name"],
                    "comment": c["comment"],
                    "match_label": f"{m['team_a_code']} vs {m['team_b_code']}",
                    "at": c["at"]
                })
    all_comments.sort(key=lambda x: x["at"], reverse=True)
    recent_comments = all_comments[:15]

    return render_template(
        "index.html",
        upcoming=upcoming, live_now=live_now, recent=recent,
        total_matches=total_matches, completed_count=completed_count,
        team_count=len(teams), recent_comments=recent_comments,
    )


@app.route("/jadwal")
def jadwal():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]

    kategori = request.args.get("kategori", "")
    grup = request.args.get("grup", "")
    tanggal = request.args.get("tanggal", "")
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()

    filtered = enriched
    if kategori:
        filtered = [m for m in filtered if m["category"] == kategori]
    if grup:
        filtered = [m for m in filtered if m["group"] == grup]
    if tanggal:
        filtered = [m for m in filtered if m["date"] == tanggal]
    if status:
        filtered = [m for m in filtered if m["status"] == status]
    if q:
        needle = q.lower()
        filtered = [
            m for m in filtered
            if needle in m["team_a_code"].lower()
            or needle in m["team_b_code"].lower()
            or needle in m["team_a_player1"].lower()
            or needle in m["team_a_player2"].lower()
            or needle in m["team_b_player1"].lower()
            or needle in m["team_b_player2"].lower()
        ]

    filtered.sort(key=lambda m: (m["date"], m["time"], m["court"]))
    dates = sorted({m["date"] for m in enriched})

    return render_template(
        "jadwal.html", matches=filtered, dates=dates,
        kategori=kategori, grup=grup, tanggal=tanggal, status=status, q=q,
    )


@app.route("/kalender")
def kalender():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]

    by_date = {}
    for m in enriched:
        by_date.setdefault(m["date"], []).append(m)
    for d in by_date:
        by_date[d].sort(key=lambda m: (m["time"], m["court"]))

    start = datetime.strptime(config["start_date"], "%Y-%m-%d")
    end = datetime.strptime(config["end_date"], "%Y-%m-%d")
    days = []
    cur = start
    while cur <= end:
        key = cur.strftime("%Y-%m-%d")
        days.append({
            "date": key,
            "day_num": cur.day,
            "day_name": utils.DAY_NAMES[cur.weekday()],
            "matches": by_date.get(key, []),
            "is_buffer": key in config.get("buffer_dates", []),
            "is_weekend": cur.weekday() >= 5,
            "is_final": key == config.get("final_date"),
            "is_closing": key == config.get("closing_date"),
        })
        cur += timedelta(days=1)

    return render_template("kalender.html", days=days, month_label=f"{utils.MONTH_NAMES[start.month]} {start.year}")


@app.route("/aturan")
def aturan():
    return render_template("aturan.html")


@app.route("/klasemen")
def klasemen():
    teams, matches, config = data_context()
    groups = []
    for cat in config["categories"]:
        for g in cat["groups"]:
            rows = utils.compute_standings(matches, teams, cat["key"], g)
            groups.append({
                "category": cat["key"], "category_label": cat["label"],
                "group": g, "rows": rows,
                "champion": utils.group_champion(matches, teams, cat["key"], g),
            })
    return render_template("klasemen.html", groups=groups)


@app.route("/bracket")
def bracket():
    teams, matches, config = data_context()
    champ_a = utils.group_champion(matches, teams, "ganda_putra", "A")
    champ_b = utils.group_champion(matches, teams, "ganda_putra", "B")
    final_match = next((m for m in matches if m["group"] == "FINAL" and m["category"] == "ganda_putra"), None)
    final_enriched = enrich_match(final_match, teams) if final_match else None

    standings_a = utils.compute_standings(matches, teams, "ganda_putra", "A")
    standings_b = utils.compute_standings(matches, teams, "ganda_putra", "B")

    gc_standings = utils.compute_standings(matches, teams, "ganda_campuran", "A")
    gc_champion = utils.group_champion(matches, teams, "ganda_campuran", "A")

    return render_template(
        "bracket.html",
        champ_a=champ_a, champ_b=champ_b,
        champ_a_label=utils.team_label(teams, champ_a),
        champ_b_label=utils.team_label(teams, champ_b),
        champ_a_color=teams.get(champ_a, {}).get("color", TBD_COLOR),
        champ_b_color=teams.get(champ_b, {}).get("color", TBD_COLOR),
        champ_a_text=teams.get(champ_a, {}).get("text", TBD_TEXT),
        champ_b_text=teams.get(champ_b, {}).get("text", TBD_TEXT),
        champ_a_player1=teams.get(champ_a, {}).get("player1", ""),
        champ_a_player2=teams.get(champ_a, {}).get("player2", ""),
        champ_b_player1=teams.get(champ_b, {}).get("player1", ""),
        champ_b_player2=teams.get(champ_b, {}).get("player2", ""),
        final_match=final_enriched,
        standings_a=standings_a, standings_b=standings_b,
        gc_standings=gc_standings, gc_champion=gc_champion,
        gc_champion_label=utils.team_label(teams, gc_champion) if gc_champion else None,
    )


@app.route("/live")
def live():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]
    live_now = [m for m in enriched if m["status"] == "live"]
    today = utils.now_wib().strftime("%Y-%m-%d")
    today_matches = sorted(
        [m for m in enriched if m["date"] == today],
        key=lambda m: (m["time"], m["court"]),
    )
    return render_template("live.html", live_now=live_now, today_matches=today_matches)


@app.route("/rekap")
def rekap():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]
    completed = sorted(
        [m for m in enriched if m["status"] == "completed"],
        key=lambda m: (m["date"], m["time"]), reverse=True,
    )
    kategori = request.args.get("kategori", "")
    if kategori:
        completed = [m for m in completed if m["category"] == kategori]
    return render_template("rekap.html", matches=completed, kategori=kategori)


@app.route("/galeri")
def galeri():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]
    photos = []
    for m in enriched:
        if m.get("docs"):
            for doc in m["docs"]:
                photos.append({
                    "url": doc["url"],
                    "uploaded_at": doc.get("uploaded_at", ""),
                    "match_id": m["id"],
                    "team_a_code": m["team_a_code"],
                    "team_b_code": m["team_b_code"],
                    "category_label": m["category_label"],
                    "round_label": m["round_label"],
                    "date_label": m["date_label"],
                    "time": m["time"]
                })
    photos.sort(key=lambda p: p["uploaded_at"], reverse=True)
    return render_template("galeri.html", photos=photos)


def _match_detail_context(match_id, is_modal):
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        abort(404)
    enriched = enrich_match(m, teams)
    ctx = {
        "m": enriched,
        "share_text": utils.build_share_text(enriched),
        "is_modal": is_modal,
    }
    if session.get("is_admin"):
        ctx["raw"] = m
        ctx["teams"] = teams
        ctx["champ_a"] = utils.group_champion(matches, teams, "ganda_putra", "A")
        ctx["champ_b"] = utils.group_champion(matches, teams, "ganda_putra", "B")
    return ctx


@app.route("/pertandingan/<match_id>")
def match_detail(match_id):
    return render_template("match_detail.html", **_match_detail_context(match_id, is_modal=False))


@app.route("/pertandingan/<match_id>/fragment")
def match_fragment(match_id):
    return render_template("_match_detail_content.html", **_match_detail_context(match_id, is_modal=True))


@app.route("/pertandingan/<match_id>/komentar", methods=["POST"])
def add_comment(match_id):
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        abort(404)

    target = url_for("match_fragment", match_id=match_id) if request.form.get("modal") \
        else url_for("match_detail", match_id=match_id) + "#komentar"

    name = request.form.get("name", "").strip()
    comment = request.form.get("comment", "").strip()
    if not name or not comment:
        flash("Nama dan komentar wajib diisi.", "error")
        return redirect(target)

    # Censor bad words
    clean_name = utils.censor_text(name[:60])
    clean_comment = utils.censor_text(comment[:500])

    m.setdefault("comments", []).append({
        "name": clean_name,
        "comment": clean_comment,
        "at": utils.now_wib().isoformat(timespec="seconds"),
    })
    utils.save_matches(matches)
    flash("Komentar terkirim. Panitia akan meninjau permintaan Anda.", "success")
    return redirect(target)


@app.route("/pertandingan/<match_id>/vote", methods=["POST"])
def vote_match(match_id):
    team = request.form.get("team")
    emoji = request.form.get("emoji")
    
    valid_emojis = ["🔥", "👏", "❤️", "😲", "💪"]
    if emoji not in valid_emojis or team not in ("a", "b"):
        return jsonify({"success": False, "message": "Data tidak valid"}), 400
        
    session_key = f"vote_{match_id}"
    vote_count = session.get(session_key, 0)
    
    if vote_count >= 2:
        return jsonify({"success": False, "message": "Batas maksimum 2 vote per sesi."}), 403
        
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        return jsonify({"success": False, "message": "Pertandingan tidak ditemukan"}), 404
        
    # Check time limit
    try:
        match_dt_str = f"{m['date']} {m['time']}"
        match_dt = datetime.strptime(match_dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone(timedelta(hours=7)))
        if utils.now_wib() >= match_dt - timedelta(hours=1):
            return jsonify({"success": False, "message": "Voting ditutup 1 jam sebelum pertandingan."}), 403
    except:
        pass
        
    if "votes" not in m:
        m["votes"] = {"a": {e: 0 for e in valid_emojis}, "b": {e: 0 for e in valid_emojis}}
        
    if emoji not in m["votes"][team]:
        m["votes"][team][emoji] = 0
        
    m["votes"][team][emoji] += 1
    session[session_key] = vote_count + 1
    utils.save_matches(matches)
    
    total_a = sum(m["votes"]["a"].values())
    total_b = sum(m["votes"]["b"].values())
    total_votes = total_a + total_b
    pct_a = int(round((total_a / total_votes) * 100)) if total_votes > 0 else 0
    pct_b = 100 - pct_a if total_votes > 0 else 0
    
    return jsonify({
        "success": True,
        "new_count": m["votes"][team][emoji],
        "votes_left": 2 - (vote_count + 1),
        "pct_a": pct_a,
        "pct_b": pct_b
    })



# ---------- Share card (Open Graph) ----------

@app.route("/og/match/<match_id>.png")
def og_match_image(match_id):
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        abort(404)
    buf = og_image.generate_match_card(enrich_match(m, teams), config["tournament_short_name"])
    resp = send_file(buf, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.route("/og/default.png")
def og_default_image():
    config = utils.load_config()
    title = request.args.get("title", config["tournament_short_name"])
    subtitle = request.args.get(
        "subtitle", f'{config["start_date"]} – {config["end_date"]} · {config["venue"]}'
    )
    tag = request.args.get("tag", "ROUND ROBIN")
    buf = og_image.generate_default_card(title, subtitle, tag=tag)
    resp = send_file(buf, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


# ---------- JSON API (buat live polling) ----------

@app.route("/api/matches")
def api_matches():
    teams, matches, config = data_context()
    return jsonify([enrich_match(m, teams) for m in matches])


@app.route("/api/matches/<match_id>")
def api_match(match_id):
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        return jsonify({"error": "not found"}), 404
    return jsonify(enrich_match(m, teams))


# ---------- admin ----------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            nxt = request.args.get("next") or url_for("admin_dashboard")
            return redirect(nxt)
        flash("Password salah.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_dashboard():
    teams, matches, config = data_context()
    enriched = [enrich_match(m, teams) for m in matches]
    enriched.sort(key=lambda m: (m["date"], m["time"], m["court"]))
    counts = {
        "scheduled": sum(1 for m in matches if m["status"] == "scheduled"),
        "live": sum(1 for m in matches if m["status"] == "live"),
        "completed": sum(1 for m in matches if m["status"] == "completed"),
        "postponed": sum(1 for m in matches if m["status"] == "postponed"),
    }
    return render_template("admin/dashboard.html", matches=enriched, counts=counts)


@app.route("/admin/reset", methods=["POST"])
@login_required
def admin_reset():
    import generate_data
    utils.backup_data_files("teams.json", "matches.json")
    utils.save_json("teams.json", generate_data.TEAMS)
    utils.save_matches(generate_data.build_matches())
    flash("Semua data pertandingan telah direset ke kondisi awal. Data sebelumnya tersimpan otomatis sebagai cadangan.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/shuffle-putra", methods=["POST"])
@login_required
def admin_shuffle_putra():
    import generate_data
    utils.backup_data_files("teams.json", "matches.json")
    teams, matches, config = data_context()
    matches, teams = generate_data.shuffle_putra_groups(matches, teams)
    utils.save_json("teams.json", teams)
    utils.save_matches(matches)
    flash("Grup A dan Grup B Ganda Putra berhasil diundi ulang — lawan tanding tiap tim berubah. Skor laga Ganda Putra yang sudah diinput ikut ter-reset karena pasangannya berubah.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/shuffle-campuran", methods=["POST"])
@login_required
def admin_shuffle_campuran():
    import generate_data
    utils.backup_data_files("matches.json")
    _, matches, _ = data_context()
    matches = generate_data.shuffle_campuran_group(matches)
    utils.save_matches(matches)
    flash("Jadwal Ganda Campuran berhasil diundi ulang — urutan lawan tiap tim di tiap tanggal berubah. Skor laga Ganda Campuran yang sudah diinput ikut ter-reset karena pasangannya berubah.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/announcement", methods=["POST"])
@login_required
def admin_announcement():
    config = utils.load_config()
    config["announcement_title"] = request.form.get("announcement_title", "").strip()
    config["announcement_text"] = request.form.get("announcement_text", "").strip()
    utils.save_json("config.json", config)
    flash("Pengumuman berhasil diperbarui.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/pertandingan/<match_id>", methods=["GET", "POST"])
@login_required
def admin_edit_match(match_id):
    teams, matches, config = data_context()
    m = utils.get_match(matches, match_id)
    if not m:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_score":
            sets = []
            for i in range(1, 6):
                sa = request.form.get(f"set{i}_a", "").strip()
                sb = request.form.get(f"set{i}_b", "").strip()
                if sa != "" and sb != "":
                    try:
                        sets.append([int(sa), int(sb)])
                    except ValueError:
                        pass
            m["sets"] = sets
            requested_status = request.form.get("status", m["status"])
            m["notes"] = request.form.get("notes", m.get("notes", ""))
            m["walkover"] = False
            utils.sync_winner(m)
            if not m["winner"] and requested_status in ("live", "scheduled", "postponed"):
                m["status"] = requested_status
            utils.save_matches(matches)
            flash("Skor pertandingan tersimpan.", "success")

        elif action == "walkover":
            wo_winner = request.form.get("wo_winner")
            wo_reason = request.form.get("wo_reason", "").strip()
            if wo_winner in (m["team_a"], m["team_b"]):
                m["winner"] = wo_winner
                m["status"] = "completed"
                m["walkover"] = True
                m["notes"] = wo_reason or "Menang WO (walkover) — lawan tidak hadir/mengundurkan diri."
                utils.save_matches(matches)
                flash("Pertandingan ditandai selesai via WO.", "success")
            else:
                flash("Pilih pemenang WO terlebih dahulu.", "error")

        elif action == "set_status":
            m["status"] = request.form.get("status", m["status"])
            utils.save_matches(matches)
            flash("Status pertandingan diperbarui.", "success")

        elif action == "reschedule":
            new_date = request.form.get("new_date")
            new_time = request.form.get("new_time")
            new_court = request.form.get("new_court")
            reason = request.form.get("reason", "")
            if new_date and new_time and new_court:
                m.setdefault("reschedule_history", []).append({
                    "from_date": m["date"], "from_time": m["time"], "from_court": m["court"],
                    "to_date": new_date, "to_time": new_time, "to_court": new_court,
                    "reason": reason,
                    "at": utils.now_wib().isoformat(timespec="seconds"),
                })
                m["date"], m["time"], m["court"] = new_date, new_time, new_court
                if m["status"] == "scheduled":
                    m["status"] = "scheduled"
                utils.save_matches(matches)
                flash("Jadwal pertandingan berhasil diubah (reschedule).", "success")

        elif action == "set_teams" and m["group"] == "FINAL":
            m["team_a"] = request.form.get("team_a") or None
            m["team_b"] = request.form.get("team_b") or None
            utils.save_matches(matches)
            flash("Tim final diperbarui.", "success")
            
        elif action == "upload_doc":
            if len(m.get("docs", [])) >= 3:
                flash("Maksimal 3 foto dokumentasi per pertandingan.", "error")
            else:
                file = request.files.get("doc_file") or request.files.get("doc_file_cam")
                if file and file.filename:
                    file_url, error = compress_and_upload_image(file, match_id)
                    if error:
                        flash(f"Gagal mengunggah dokumen: {error}", "error")
                    elif file_url:
                        m.setdefault("docs", []).append({
                            "url": file_url,
                            "uploaded_at": utils.now_wib().isoformat(timespec="seconds")
                        })
                        utils.save_matches(matches)
                        flash("Dokumen berhasil diunggah dan dikompres.", "success")
                else:
                    flash("Pilih file gambar terlebih dahulu.", "error")
        
        elif action == "delete_doc":
            doc_url = request.form.get("doc_url")
            if doc_url and "docs" in m:
                m["docs"] = [d for d in m["docs"] if d.get("url") != doc_url]
                utils.save_matches(matches)
                delete_from_supabase(doc_url)
                flash("Dokumen berhasil dihapus beserta filenya di S3.", "success")

        if request.form.get("modal"):
            return redirect(url_for("match_fragment", match_id=match_id))
        return redirect(url_for("admin_edit_match", match_id=match_id))

    champ_a = utils.group_champion(matches, teams, "ganda_putra", "A")
    champ_b = utils.group_champion(matches, teams, "ganda_putra", "B")

    return render_template(
        "admin/edit_match.html", m=enrich_match(m, teams), raw=m,
        teams=teams, champ_a=champ_a, champ_b=champ_b,
    )


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
