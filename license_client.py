import os
import json
import time
import uuid
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LICENSE_FILE = os.path.join(DATA_DIR, "license.json")
INSTANCE_ID_FILE = os.path.join(DATA_DIR, "instance_id.txt")

API_BASE_URL = "https://berlanggan.web.id/v1"
TOKEN_TTL_SECONDS = 24 * 3600  # 1 hari (sesuai dokumen B8)
HEARTBEAT_INTERVAL_SECONDS = 12 * 3600  # Cek ulang setiap 12 jam jika belum expired


def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def get_machine_fingerprint():
    """Menghasilkan fingerprint stabil untuk server/instansi ini (SHA256)."""
    _ensure_data_dir()
    if not os.path.exists(INSTANCE_ID_FILE):
        raw_uuid = str(uuid.uuid4()) + "-" + str(uuid.getnode())
        with open(INSTANCE_ID_FILE, "w", encoding="utf-8") as f:
            f.write(raw_uuid)
    else:
        with open(INSTANCE_ID_FILE, "r", encoding="utf-8") as f:
            raw_uuid = f.read().strip()
    
    # Hash raw_uuid menjadi SHA-256 string yang elegan
    fp_hash = hashlib.sha256(raw_uuid.encode("utf-8")).hexdigest()
    return fp_hash


def _default_license():
    return {
        "status": "unlicensed",
        "license_key": "",
        "token": "",
        "fingerprint": get_machine_fingerprint(),
        "expires_at": "",
        "grace_days": 0,
        "entitlements": {},
        "last_validated_timestamp": 0,
        "last_message": "Lisensi belum diaktivasi. Silakan aktifkan menggunakan kunci lisensi dari Berlanggan.web.id."
    }


def get_license():
    _ensure_data_dir()
    if not os.path.exists(LICENSE_FILE):
        default_data = _default_license()
        save_license(default_data)
        return default_data
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Pastikan fingerprint terkini terisi
            if not data.get("fingerprint"):
                data["fingerprint"] = get_machine_fingerprint()
            return data
    except Exception:
        default_data = _default_license()
        return default_data


def save_license(data):
    _ensure_data_dir()
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _send_request(endpoint, payload, timeout=12):
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "RoC-Support-Desk-App/2.5 (Berlanggan-Integration)"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            body_str = resp.read().decode("utf-8")
            if body_str:
                return status_code, json.loads(body_str), None
            return status_code, {}, None
    except urllib.error.HTTPError as e:
        try:
            body_str = e.read().decode("utf-8")
            err_json = json.loads(body_str) if body_str else {}
        except Exception:
            err_json = {}
        return e.code, err_json, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return 0, {}, f"Gagal terhubung ke server Berlanggan.web.id ({e.reason}). Periksa koneksi internet."
    except Exception as e:
        return 0, {}, f"Terjadi kesalahan koneksi: {str(e)}"


def activate(license_key, machine_name="Server Turnamen Tenis Meja & Padel"):
    """
    POST /v1/activate
    Mendaftarkan instalasi ini dan menguji kunci lisensi.
    """
    clean_key = (license_key or "").strip().upper()
    if not clean_key:
        return False, "Kunci lisensi tidak boleh kosong.", "invalid_request"

    fp = get_machine_fingerprint()
    payload = {
        "license_key": clean_key,
        "fingerprint": fp,
        "machine_name": machine_name
    }

    code, resp_data, err = _send_request("activate", payload)
    if err and code != 200 and not resp_data:
        return False, f"Aktivasi gagal: {err}", "network_error"

    status = resp_data.get("status", "unknown")
    if status == "active":
        lic_data = get_license()
        lic_data.update({
            "status": "active",
            "license_key": clean_key,
            "token": resp_data.get("token", ""),
            "fingerprint": fp,
            "expires_at": resp_data.get("expires_at", ""),
            "grace_days": resp_data.get("grace_days", 3),
            "entitlements": resp_data.get("entitlements", {}),
            "last_validated_timestamp": int(time.time()),
            "last_message": "Lisensi aktif dan resmi tersambung dengan Berlanggan.web.id!"
        })
        save_license(lic_data)
        return True, "🎉 Berhasil! Lisensi Anda telah diaktivasi dan sah terdaftar di Berlanggan.web.id.", "active"
    
    elif status == "seat_full":
        max_seats = resp_data.get("message", "Batas maksimal perangkat")
        return False, f"⚠️ Gagal aktivasi: Kuota perangkat (seats) untuk lisensi ini sudah penuh! ({max_seats}). Lepas perangkat lama di dasbor Berlanggan.web.id Anda terlebih dahulu.", "seat_full"
    
    elif status in ("invalid", "revoked", "suspended", "expired"):
        messages_map = {
            "invalid": "Kunci lisensi tidak valid atau tidak ditemukan di sistem Berlanggan.web.id.",
            "revoked": "Kunci lisensi telah ditarik (revoked). Hubungi layanan pelanggan.",
            "suspended": "Langganan untuk lisensi ini ditangguhkan (suspended) karena masa grace habis atau kurang saldo. Silakan top up saldo wallet Anda di Berlanggan.web.id.",
            "expired": "Masa berlaku lisensi ini telah berakhir (expired)."
        }
        msg = messages_map.get(status, f"Status lisensi: {status}")
        return False, f"❌ Aktivasi ditolkan: {msg}", status
    
    else:
        err_msg = resp_data.get("message") or f"Respons server: {status} (HTTP {code})"
        return False, f"Gagal mengaktivasi lisensi: {err_msg}", status


def validate(force=False):
    """
    POST /v1/validate
    Heartbeat berkala ke server untuk mengecek status berlangganan & perbarui token.
    """
    lic = get_license()
    key = lic.get("license_key", "").strip()
    token = lic.get("token", "").strip()
    fp = lic.get("fingerprint", get_machine_fingerprint())

    if not key or lic.get("status") == "unlicensed":
        return lic

    now = int(time.time())
    if not force:
        # Jika belum 12 jam dari validasi terakhir dan status saat ini active/grace, lewati panggilan network
        last_val = lic.get("last_validated_timestamp", 0)
        if (now - last_val) < HEARTBEAT_INTERVAL_SECONDS and lic.get("status") in ("active", "grace"):
            return lic

    payload = {
        "license_key": key,
        "fingerprint": fp,
        "token": token
    }

    code, resp_data, err = _send_request("validate", payload, timeout=8)
    if err and not resp_data:
        # Jika gagal koneksi (offline/server gangguan), TETAP pertahankan status active/grace demi kenyamanan pelanggan (fail-open heartbeat)
        lic["last_message"] = f"Pengecekan offline / server gangguan: {err}. Mempertahankan status sementara."
        save_license(lic)
        return lic

    status = resp_data.get("status", lic.get("status"))
    if status in ("active", "grace"):
        lic.update({
            "status": status,
            "token": resp_data.get("token", token), # Sliding expiry token
            "expires_at": resp_data.get("expires_at", lic.get("expires_at")),
            "grace_days": resp_data.get("grace_days", lic.get("grace_days")),
            "entitlements": resp_data.get("entitlements", lic.get("entitlements")),
            "last_validated_timestamp": now,
            "last_message": "Validasi berhasil. Lisensi aktif." if status == "active" else "⚠️ Dalam masa tenggang (Grace Period). Harap top up saldo wallet Anda di Berlanggan.web.id agar tidak tersuspen."
        })
        save_license(lic)
    elif status in ("suspended", "revoked", "expired", "deactivated", "invalid"):
        lic.update({
            "status": status,
            "last_validated_timestamp": now,
            "last_message": f"Status berlangganan terkini dari server: {status.upper()}."
        })
        if status == "deactivated":
            lic["last_message"] = "Perangkat ini telah dilepas/deaktivasi dari dasbor. Silakan aktivasi ulang jika diperlukan."
            lic["status"] = "unlicensed"
        save_license(lic)

    return lic


def deactivate():
    """
    POST /v1/deactivate
    Melepaskan seat/perangkat ini agar lisensi bisa dipakai di mesin lain.
    """
    lic = get_license()
    key = lic.get("license_key", "").strip()
    fp = lic.get("fingerprint", get_machine_fingerprint())

    if not key or lic.get("status") == "unlicensed":
        return True, "Lisensi tidak sedang aktif di perangkat ini."

    payload = {
        "license_key": key,
        "fingerprint": fp
    }
    code, resp_data, err = _send_request("deactivate", payload)
    
    # Lepas di database lokal apa pun hasilnya (bisa jadi server offline atau sudah lepas)
    reset_data = _default_license()
    reset_data["last_message"] = "Lisensi berhasil dideativasi (seat dilepaskan dari server ini)."
    save_license(reset_data)
    
    if code == 200 and resp_data.get("status") == "deactivated":
        return True, "✅ Seat lisensi resmi dilepaskan di server Berlanggan.web.id dan sistem lokal ini."
    else:
        return True, "✅ Lisensi lokal berhasil dibersihkan. (Koneksi server eksternal: " + str(err or resp_data) + ")"


def parse_iso_date(dt_str):
    if not dt_str or not isinstance(dt_str, str):
        return None
    dt_str = dt_str.strip()
    try:
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + "+00:00"
        elif "+" not in dt_str and len(dt_str) <= 19:
            dt_str += "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def is_license_active():
    """
    Mengevaluasi apakah lisensi aktif dan masa berlaku token belum kedaluwarsa.
    Mengembalikan tuple: (is_active: bool, reason_str: str)
    """
    lic = get_license()
    status = lic.get("status", "unlicensed")
    
    if status not in ("active", "grace"):
        messages = {
            "unlicensed": "Lisensi web belum diaktifkan (Unlicensed).",
            "suspended": "Lisensi ditangguhkan (Suspended/Kurang Saldo).",
            "revoked": "Lisensi telah dicabut (Revoked).",
            "expired": "Lisensi telah kedaluwarsa (Expired)."
        }
        return False, messages.get(status, f"Status lisensi tidak aktif ({status}).")
    
    expires_str = lic.get("expires_at")
    dt = parse_iso_date(expires_str)
    if dt:
        now_utc = datetime.now(timezone.utc)
        grace_days = int(lic.get("grace_days", 0))
        # Jika melewati tanggal expired + masa grace period
        limit = dt + timedelta(days=grace_days)
        if now_utc > limit:
            # Coba validasi heartbeat sekali jika mungkin ada perpanjangan otomatis baru dari server
            lic = validate(force=False)
            if lic.get("status") not in ("active", "grace"):
                return False, f"Masa aktif lisensi telah berakhir pada {expires_str}."
            new_dt = parse_iso_date(lic.get("expires_at"))
            if new_dt and now_utc > (new_dt + timedelta(days=int(lic.get("grace_days", grace_days)))):
                return False, f"Masa aktif token lisensi Berlanggan.web.id telah melewati tanggal {lic.get('expires_at')}."
    
    return True, "Active"

