"""Plan 3 Task 6 contact sheet, fan GIF, frame strip and speed graph (Pillow, no Blender).

    python3 Source/Model/p3t6_sheet.py

Reads preview/p3-task-6/ (dc/preview_p3t6.py, p3t6_fracture.py) and writes there:
  crac_fans.gif        the anim/fan_NNN.png sequence at 25 fps (off, spin-up, running, coast-down)
  crac_fans_strip.png  eight frames of it side by side, each captioned with its time, speed and lamp state
  crac_fans_graph.png  the InfiniteRotation speed profile (anim/profile.csv) with the RUN lamp's state
  contact.jpg          every render, grouped (hero, fans, close-ups, fracture, paints, room, vanilla)."""
import csv
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "preview", "p3-task-6")
ANIM = os.path.join(ROOT, "anim")
ORDER = ("crac_3q", "crac_front", "crac_back", "crac_left", "crac_right", "crac_top", "crac_human", "crac_lods",
         "crac_fans", "crac_fan", "closeup", "fracture/DC_CRAC", "fracture/Vanilla", "paints", "room_150_cold",
         "room_150_hot", "room_100", "room_200", "vanilla")


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _fit(path, size):
    im = Image.open(path).convert("RGB")
    im.thumbnail(size, Image.LANCZOS)
    out = Image.new("RGB", size, (18, 19, 22))
    out.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return out


def _profile():
    p = os.path.join(ANIM, "profile.csv")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]


def anim():
    frames = sorted(f for f in os.listdir(ANIM) if f.startswith("fan_") and f.endswith(".png")) \
        if os.path.isdir(ANIM) else []
    if not frames:
        print("no anim frames")
        return
    prof = _profile()
    ims = [Image.open(os.path.join(ANIM, f)).convert("RGB").resize((480, 480), Image.LANCZOS) for f in frames]
    f = _font(18)
    for im, r in zip(ims, prof):
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 480, 30), fill=(12, 12, 14))
        d.text((10, 5), f"t {r['t']:.2f} s   {r['omega_deg_s']:.0f} deg/s   {'RUN' if r['working'] else 'OFF'}",
               fill=(120, 255, 140) if r["working"] else (200, 200, 200), font=f)
    pal = [im.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for im in ims]
    pal[0].save(os.path.join(ROOT, "crac_fans.gif"), save_all=True, append_images=pal[1:], duration=40, loop=0,
                optimize=True)
    pick = [int(round(t * 25)) for t in (0.2, 0.8, 1.4, 2.6, 3.6, 4.6, 6.0, 7.6)]
    pick = [min(p, len(ims) - 1) for p in pick]
    strip = Image.new("RGB", (8 * 300, 300), (12, 12, 14))
    for i, k in enumerate(pick):
        strip.paste(ims[k].resize((300, 300), Image.LANCZOS), (300 * i, 0))
    strip.save(os.path.join(ROOT, "crac_fans_strip.png"))
    # the speed graph
    W, Hh, m = 1200, 520, 70
    g = Image.new("RGB", (W, Hh), (18, 19, 22))
    d = ImageDraw.Draw(g)
    T = prof[-1]["t"]

    def X(t):
        return m + (W - 2 * m) * t / T

    def Y(w):
        return Hh - m - (Hh - 2 * m) * w / 650.0
    for w in (0, 150, 300, 450, 600):
        d.line((m, Y(w), W - m, Y(w)), fill=(50, 52, 58))
        d.text((10, Y(w) - 9), f"{w}", fill=(170, 170, 170), font=_font(15))
    for t in range(0, int(T) + 1):
        d.line((X(t), Hh - m, X(t), Hh - m + 6), fill=(170, 170, 170))
        d.text((X(t) - 5, Hh - m + 10), f"{t}", fill=(170, 170, 170), font=_font(15))
    for a, b in zip(prof, prof[1:]):
        if a["working"]:
            d.rectangle((X(a["t"]), Hh - m + 28, X(b["t"]), Hh - m + 40), fill=(80, 220, 110))
        d.line((X(a["t"]), Y(a["omega_deg_s"]), X(b["t"]), Y(b["omega_deg_s"])), fill=(255, 196, 40), width=4)
    d.text((m, 18), "CracFan InfiniteRotation: 600 deg/s, +300 deg/s^2 (2 s soft start), -150 deg/s^2 (4 s coast)",
           fill=(235, 235, 235), font=_font(20))
    d.text((W - m - 330, Hh - 32), "time (s)     green bar: Working / RUN lit", fill=(170, 170, 170), font=_font(15))
    g.save(os.path.join(ROOT, "crac_fans_graph.png"))
    print("gif / strip / graph ->", ROOT)


def _key(n):
    return (next((i for i, p in enumerate(ORDER) if n.startswith(p)), len(ORDER)), n)


def contact():
    names = [n for n in os.listdir(ROOT) if n.endswith(".png")]
    fr = os.path.join(ROOT, "fracture")
    if os.path.isdir(fr):
        names += [f"fracture/{n}" for n in os.listdir(fr) if n.endswith(".png")]
    names.sort(key=_key)
    cols, cw, ch = 5, 520, 340
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 34) + 60), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), f"Plan 3 Task 6: in-row cooler DC_CRAC ({len(names)} renders)", fill=(240, 240, 240),
           font=_font(30))
    f = _font(17)
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * (cw + 8), 60 + (i // cols) * (ch + 34)
        sheet.paste(_fit(os.path.join(ROOT, n), (cw, ch)), (x, y + 26))
        d.text((x + 2, y + 4), n[:-4], fill=(230, 230, 230), font=f)
    path = os.path.join(ROOT, "contact.jpg")
    sheet.save(path, quality=86)
    print("contact ->", path)


if __name__ == "__main__":
    anim()
    contact()
