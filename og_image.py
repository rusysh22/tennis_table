"""
Generator gambar share card (Open Graph) dinamis -- dipakai supaya link yang
di-share ke WhatsApp/Facebook (Meta) dan Microsoft Teams menampilkan preview
kartu dengan info pertandingan (bukan cuma judul polos), lewat og:image.

Tidak ada dependency eksternal selain Pillow (sudah ada di requirements.txt).
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

import utils

FONT_PATH = os.path.join(os.path.dirname(__file__), "static", "fonts", "PlusJakartaSans.ttf")

CARD_W, CARD_H = 1200, 630

BLUE_900 = (0x0C, 0x2A, 0x3D)
BLUE_700 = (0x03, 0x69, 0xA1)
BLUE_500 = (0x0E, 0xA5, 0xE9)
GREEN_600 = (0x05, 0x96, 0x69)
GREEN_400 = (0x34, 0xD3, 0x99)
WHITE = (0xF7, 0xFE, 0xFC)
INK = (0x0A, 0x1F, 0x1C)

GRAD_STOPS = [(0.0, BLUE_900), (0.30, BLUE_700), (0.62, GREEN_600), (1.0, GREEN_400)]

_FONT_CACHE = {}


def _font(size, weight=700):
    key = (size, weight)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(FONT_PATH, size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        _FONT_CACHE[key] = f
    return f


def _hex_to_rgb(h):
    h = (h or "#9c9c9c").lstrip("#")
    if len(h) != 6:
        return (0x9C, 0x9C, 0x9C)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lerp_color(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def _color_at(t, stops):
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            local_t = (t - p0) / (p1 - p0) if p1 > p0 else 0
            return _lerp_color(c0, c1, local_t)
    return stops[-1][1]


def _diagonal_gradient(w, h, stops):
    """Gradient 135deg murah: dihitung di grid kecil lalu di-resize (bilinear)
    supaya halus tanpa iterasi per-pixel penuh (756rb px) yang lambat."""
    small_w, small_h = max(2, w // 12), max(2, h // 12)
    small = Image.new("RGB", (small_w, small_h))
    px = small.load()
    for y in range(small_h):
        for x in range(small_w):
            t = (x / (small_w - 1) + y / (small_h - 1)) / 2
            px[x, y] = _color_at(t, stops)
    return small.resize((w, h), Image.BILINEAR)


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered(draw, cx, y, text, font, fill):
    w, h = _text_size(draw, text, font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return w, h


def _draw_pill(draw, cx, y, text, font, bg, fg, pad_x=20, pad_y=10):
    """Pill terpusat horizontal di cx. Return (x0, y0, x1, y1)."""
    w, h = _text_size(draw, text, font)
    x0, x1 = cx - w / 2 - pad_x, cx + w / 2 + pad_x
    y1 = y + h + pad_y * 2
    radius = (y1 - y) / 2
    draw.rounded_rectangle([x0, y, x1, y1], radius=radius, fill=bg)
    draw.text((cx - w / 2, y + pad_y - 2), text, font=font, fill=fg)
    return x0, y, x1, y1


def _team_chip(draw, x_center, y, code, color_hex, text_hex, font):
    """Chip kode tim (mis. 'MM') dengan warna tim, terpusat di x_center."""
    w, h = _text_size(draw, code, font)
    pad_x, pad_y = 22, 12
    x0, x1 = x_center - w / 2 - pad_x, x_center + w / 2 + pad_x
    y1 = y + h + pad_y * 2
    draw.rounded_rectangle([x0, y, x1, y1], radius=12, fill=_hex_to_rgb(color_hex))
    draw.text((x_center - w / 2, y + pad_y - 2), code, font=font, fill=_hex_to_rgb(text_hex))
    return y1


def generate_match_card(m, tournament_name):
    """m: dict hasil enrich_match() dari app.py."""
    img = _diagonal_gradient(CARD_W, CARD_H, GRAD_STOPS)
    draw = ImageDraw.Draw(img)
    cx = CARD_W // 2

    f_tag = _font(24, 700)
    f_h1 = _font(44, 800)
    f_sub = _font(24, 500)
    f_chip = _font(30, 800)
    f_name = _font(22, 600)
    f_score = _font(84, 800)
    f_vs = _font(30, 700)
    f_meta = _font(22, 600)
    f_footer = _font(22, 700)

    # baris 1: badge kategori + status
    cat_label = m["category_label"].upper()
    status_label = m["status_label"].upper()
    w1, h1 = _text_size(draw, cat_label, f_tag)
    w2, h2 = _text_size(draw, status_label, f_tag)
    pad, gap = 20, 16
    total_w = (w1 + pad * 2) + gap + (w2 + pad * 2)
    start_x = cx - total_w / 2
    y0 = 46
    _draw_pill(draw, start_x + (w1 + pad * 2) / 2, y0, cat_label, f_tag, (255, 255, 255, 235), BLUE_700, pad_x=pad)
    _draw_pill(draw, start_x + (w1 + pad * 2) + gap + (w2 + pad * 2) / 2, y0, status_label, f_tag,
               (223, 245, 225) if m["status"] == "completed" else (238, 240, 255),
               (23, 92, 44) if m["status"] == "completed" else (58, 63, 168), pad_x=pad)

    # baris 2: Group X . Babak Y
    title = f'{"Group " + m["group"] + " · " if m["group"] != "FINAL" else ""}{m["round_label"]}'
    _draw_centered(draw, cx, 118, title, f_h1, WHITE)

    # baris 3: Best of N
    _draw_centered(draw, cx, 180, m["best_of_label"], f_sub, (255, 255, 255))

    # baris tim: kiri (A) - tengah (skor/vs) - kanan (B)
    row_y = 270
    left_cx, right_cx = 260, CARD_W - 260

    chip_bottom = _team_chip(draw, left_cx, row_y, m["team_a_code"], m["team_a_color"], m["team_a_text"], f_chip)
    _draw_centered(draw, left_cx, chip_bottom + 18, utils.truncate_words(m["team_a_player1"], 2), f_name, WHITE)
    _draw_centered(draw, left_cx, chip_bottom + 50, utils.truncate_words(m["team_a_player2"], 2), f_name, WHITE)

    _team_chip(draw, right_cx, row_y, m["team_b_code"], m["team_b_color"], m["team_b_text"], f_chip)
    _draw_centered(draw, right_cx, chip_bottom + 18, utils.truncate_words(m["team_b_player1"], 2), f_name, WHITE)
    _draw_centered(draw, right_cx, chip_bottom + 50, utils.truncate_words(m["team_b_player2"], 2), f_name, WHITE)

    if m["status"] in ("completed", "live"):
        score_text = f'{m["sets_a"]} : {m["sets_b"]}'
        _draw_centered(draw, cx, row_y - 6, score_text, f_score, WHITE)
    else:
        _draw_pill(draw, cx, row_y + 30, "VS", f_vs, (255, 255, 255, 220), GREEN_600, pad_x=22)

    # meta: tanggal . jam . meja
    meta = f'{m["date_label"]}    {m["time"]} WIB    {m["court"]}'
    _draw_centered(draw, cx, 470, meta, f_meta, WHITE)

    # footer
    draw.line([(cx - 120, 540), (cx + 120, 540)], fill=(255, 255, 255, 120), width=2)
    _draw_centered(draw, cx, 560, tournament_name, f_footer, WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_default_card(title, subtitle, tag="ROUND ROBIN"):
    img = _diagonal_gradient(CARD_W, CARD_H, GRAD_STOPS)
    draw = ImageDraw.Draw(img)
    cx = CARD_W // 2

    f_tag = _font(24, 700)
    f_title = _font(58, 800)
    f_sub = _font(28, 500)

    _draw_pill(draw, cx, 210, tag.upper(), f_tag, (255, 255, 255, 235), BLUE_700, pad_x=22)

    # judul bisa 2 baris kalau kepanjangan (dibagi per kata secara kasar)
    words = title.split()
    line1, line2 = title, ""
    if len(" ".join(words)) > 22 and len(words) > 1:
        mid = len(words) // 2
        line1, line2 = " ".join(words[:mid + (len(words) % 2)]), " ".join(words[mid + (len(words) % 2):])

    if line2:
        _draw_centered(draw, cx, 290, line1, f_title, WHITE)
        _draw_centered(draw, cx, 356, line2, f_title, WHITE)
        sub_y = 440
    else:
        _draw_centered(draw, cx, 320, line1, f_title, WHITE)
        sub_y = 400

    _draw_centered(draw, cx, sub_y, subtitle, f_sub, (255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
