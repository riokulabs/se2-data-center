"""Fracture comparison sheets (Pillow, no Blender), from the panels fracture_compare_preview.py renders.

    python3 Source/Model/fracture_compare_sheet.py

Writes preview/fracture-compare/:
  <family>.jpg          racks / servers / trays, one row per block: intact | BEFORE zones + colliders |
                        AFTER zones + colliders | after: broken off (game materials) | after: damaged model, with
                        the block's zones (label, critical, health share) from its export.json;
  vanilla_compare.jpg   vanilla SlidingDoorNarrow250 / Battery150 / WallInsertPipes, each above the block of ours it
                        compares with (frame segments; core + shell plates; cut pipes);
  contact.jpg           every panel.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "preview", "fracture-compare")
PANELS = os.path.join(ROOT, "panels")
MODELS = os.path.join(HERE, "Models")
COLS = (("intact", "intact (NonFractured)"), ("before_zones", "BEFORE: zones + colliders"),
        ("zones", "AFTER: zones + colliders"), ("broken", "after: broken off (game materials)"),
        ("damaged", "after: damaged model (Deformed)"))
ZONE_RGB = [(20, 77, 242), (26, 158, 56), (140, 46, 204), (242, 158, 15), (230, 50, 50), (20, 184, 199),
            (224, 97, 158), (158, 158, 31)]
FAMILIES = {
    "racks": ["DC_Rack42_Open", "DC_Rack24_SplitFront"],
    "servers": ["DC_Srv_Compute", "DC_Srv_Timer", "DC_Srv_KVM", "DC_Srv_UPS"],
    "trays": ["DC_Tray_StraightL_Moderate", "DC_Tray_TurnH_Full", "DC_Tray_TurnUp_Low", "DC_Tray_Cross_Full",
              "DC_Tray_Drop_Full"],
}
COMPARE = [("Vanilla_SlideDoorNarrow250", "DC_Rack42_Open"), ("Vanilla_Battery150", "DC_Srv_Compute"),
           ("Vanilla_WallInsertPipes", "DC_Tray_TurnH_Full")]
VANILLA_NOTE = {"Vanilla_SlideDoorNarrow250": "vanilla SlidingDoorNarrow250 frame: 8 convex chunks round the opening, "
                                              "7 critical; capped break faces",
                "Vanilla_Battery150": "vanilla Battery150: a critical core with shell plates carrying the terminals",
                "Vanilla_WallInsertPipes": "vanilla WallInsertPipes: pipes cut with capped break faces"}
BG = (12, 13, 16)


def font(size, bold=True):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
              "/usr/share/fonts/TTF/DejaVuSans%s.ttf" % ("-Bold" if bold else "")):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fit(path, size):
    out = Image.new("RGB", size, (30, 31, 34))
    if os.path.exists(path):
        im = Image.open(path).convert("RGB")
        im.thumbnail(size, Image.LANCZOS)
        out.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return out


def zones(name):
    p = os.path.join(MODELS, name, "export.json")
    if not os.path.exists(p):
        return [], {}
    m = json.load(open(p))
    fr = m["fractured"]
    info = {"tris": [l["tris"] for l in fr["lods"]], "dmg": [l["tris"] for l in m.get("damaged", {}).get("lods", [])],
            "dent": m.get("damaged", {}).get("dent", {}), "mid": fr.get("mid_lod", False),
            "mode": fr.get("cut_mode", "")}
    return [(z["id"], z.get("label", ""), z.get("critical", False), z.get("health_share")) for z in fr["zones"]], info


def rows_sheet(title, rows, out, cell=(520, 395)):
    """rows = [(subject, caption)]"""
    pad, head, side = 10, 46, 330
    W = side + len(COLS) * (cell[0] + pad) + pad
    H = 70 + head + len(rows) * (cell[1] + pad)
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad + 4, 16), title, fill=(240, 240, 240), font=font(30))
    for c, (_, lab) in enumerate(COLS):
        d.text((side + pad + c * (cell[0] + pad) + 6, 70 + 10), lab, fill=(210, 210, 210), font=font(20))
    for r, (subj, caption) in enumerate(rows):
        y = 70 + head + r * (cell[1] + pad)
        d.text((pad + 4, y + 6), caption, fill=(235, 235, 235), font=font(19))
        zs, info = zones(subj) if subj.startswith("DC_") else ([], {})
        yy = y + 40
        if subj.startswith("Vanilla_"):
            for line in _wrap(VANILLA_NOTE.get(subj, ""), 30):
                d.text((pad + 4, yy), line, fill=(200, 200, 200), font=font(15, False))
                yy += 20
        for k, (zid, label, crit, share) in enumerate(zs):
            d.rectangle((pad + 4, yy + 3, pad + 20, yy + 19), fill=ZONE_RGB[k % len(ZONE_RGB)])
            d.text((pad + 26, yy), zid + ("  CRITICAL" if crit else "") + (f"  {100 * share:.0f} %" if share else ""),
                   fill=(235, 235, 235), font=font(15))
            yy += 20
            for line in _wrap(label, 34):
                d.text((pad + 26, yy), line, fill=(185, 185, 185), font=font(13, False))
                yy += 17
            yy += 4
        if info:
            for line in (f"cut: {info['mode']}", f"Fractured LOD tris {info['tris']}" + (" (+ mid LOD)" if info["mid"] else ""),
                         f"Damaged LOD tris {info['dmg']}",
                         "dents mean {mean_mm} / p90 {p90_mm} / max {max_mm} mm".format(**info["dent"])
                         if info["dent"] else ""):
                for ln in _wrap(line, 38):
                    d.text((pad + 4, yy), ln, fill=(150, 160, 170), font=font(13, False))
                    yy += 17
        for c, (key, _) in enumerate(COLS):
            x = side + pad + c * (cell[0] + pad)
            sheet.paste(fit(os.path.join(PANELS, f"{subj}_{key}.png"), cell), (x, y))
    sheet.save(out, quality=90)
    print("WROTE", out)


def _wrap(text, n):
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > n and line:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


def contact(out, cell=(300, 228), cols=8):
    items = sorted(f for f in os.listdir(PANELS) if f.endswith(".png"))
    pad, head = 6, 22
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cell[0] + pad) + pad, 56 + rows * (cell[1] + head + pad)), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad + 4, 14), "Fracture refinement, every panel", fill=(240, 240, 240), font=font(24))
    f = font(12, False)
    for k, n in enumerate(items):
        x = pad + (k % cols) * (cell[0] + pad)
        y = 56 + (k // cols) * (cell[1] + head + pad)
        d.text((x + 2, y + 4), n[:-4].replace("DC_", ""), fill=(210, 210, 210), font=f)
        sheet.paste(fit(os.path.join(PANELS, n), cell), (x, y + head))
    sheet.save(out, quality=88)
    print("WROTE", out)


def main():
    for fam, names in FAMILIES.items():
        rows_sheet(f"Fracture refinement: {fam} (before / after)", [(n, n.replace("DC_", "")) for n in names],
                   os.path.join(ROOT, f"{fam}.jpg"), cell=(520, 600) if fam == "racks" else (520, 395))
    rows = []
    for v, ours in COMPARE:
        rows += [(v, v.replace("Vanilla_", "VANILLA ")), (ours, "OURS " + ours.replace("DC_", ""))]
    rows_sheet("Vanilla fracture / Deformed models (top of each pair) vs ours", rows,
               os.path.join(ROOT, "vanilla_compare.jpg"), cell=(520, 530))
    contact(os.path.join(ROOT, "contact.jpg"))


if __name__ == "__main__":
    main()
