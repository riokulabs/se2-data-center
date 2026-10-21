"""Contact sheets of a states_preview.py set (Pillow, no Blender), in the style of plan_sheets.py.

    python3 Source/Model/states_sheet.py --set=<tag> [--before=<tag>] [--by-family] [BLOCK ...]

Reads preview/dmg-build/<tag>/ (manifest.json, analogues.json, <block>/<shot>_<view>.png, <block>/info.json) and
writes preview/dmg-build/<tag>/sheets/:
  <block>.png          (default) the block's vanilla analogue rows on top, then the block: per view (front, rear)
                       one row of the 11 shots, the --before set's row above the set's row;
  family_<family>.png  (--by-family) the family's analogues on top, then every block of the family in the set.
Side columns: the per-shot pixel difference to the before row (% of pixels whose channels differ by > 8 / 255;
also printed under each thumbnail), and the FR LOD0 share of the scaffold / support / hide / stand-in triangles
(export.json fractured.role_tris over the LOD0 triangles) when those keys exist.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dc import catalog, config, state_view as SV  # noqa: E402

ROOT = os.path.join(config.PREVIEW_DIR, "dmg-build")
TW, TH = 216, 162                      # thumbnail
LABEL_W, SIDE_W, HEAD_H, ROW_PAD = 230, 250, 58, 22
BG, INK, FAINT = (247, 247, 244), (40, 42, 46), (150, 152, 156)
BEFORE_C, AFTER_C, ANA_C, HOT = (110, 112, 118), (25, 90, 180), (120, 70, 20), (200, 40, 30)
SHARE_KEYS = ("scaffold", "support", "hide", "standin")
DIFF_LEVEL = 8
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(px, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, px)
    except OSError:
        return ImageFont.load_default()


def load_set(tag):
    d = os.path.join(ROOT, tag)
    man = json.load(open(os.path.join(d, "manifest.json")))
    p = os.path.join(d, "analogues.json")
    return d, man, json.load(open(p)) if os.path.exists(p) else {}


def png(d, key, shot, view):
    p = os.path.join(d, key, f"{shot}_{view}.png")
    return Image.open(p).convert("RGB") if os.path.exists(p) else None


def diff_pct(a, b):
    """% of pixels whose largest channel difference exceeds DIFF_LEVEL (None when either image is missing)."""
    if a is None or b is None or a.size != b.size:
        return None
    x = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    return 100.0 * float((x > DIFF_LEVEL).mean())


def shares(d, key):
    p = os.path.join(d, key, "info.json")
    if not os.path.exists(p):
        return {}
    info = json.load(open(p))
    tot, rt = info.get("fr_lod0_tris"), info.get("role_tris") or {}
    return {k: rt[k] / tot for k in SHARE_KEYS if k in rt and tot}


def rows_for(key, after, before, analogue=False):
    """[(label, colour, set dir, key, view, compare-to set dir | None)] of one subject."""
    out = []
    for view in SV.VIEWS:
        if analogue:
            out.append((f"vanilla  {view}", ANA_C, after, key, view, None))
            continue
        if before:
            out.append((f"before  {view}", BEFORE_C, before, key, view, None))
        out.append((f"after  {view}" if before else view, AFTER_C, after, key, view, before))
    return out


def draw(title, groups, path):
    """groups: [(subject title, rows, share dict)]. The debris column (state_view.DEBRIS_SHOT) only when a row has
    one."""
    shots = SV.ALL_SHOTS
    if any(png(d, key, SV.DEBRIS_SHOT, view) for _, rows, _ in groups for _, _, d, key, view, _ in rows):
        shots += (SV.DEBRIS_SHOT,)
    n = len(shots)
    W = LABEL_W + n * TW + SIDE_W
    H = HEAD_H + sum(26 + len(r) * (TH + ROW_PAD) + 10 for _, r, _ in groups) + 10
    im = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(im)
    dr.text((10, 8), title, fill=INK, font=font(18, True))
    for i, s in enumerate(shots):
        dr.text((LABEL_W + i * TW + 6, 36), s, fill=INK, font=font(14, True))
    dr.text((LABEL_W + n * TW + 8, 36), "diff % / FR LOD0 share", fill=INK, font=font(13, True))
    y = HEAD_H
    for gt, rows, sh in groups:
        dr.line((0, y + 2, W, y + 2), fill=FAINT)
        dr.text((10, y + 6), gt, fill=INK, font=font(15, True))
        if sh:
            dr.text((LABEL_W + n * TW + 8, y + 6), "  ".join(f"{k} {100 * v:.0f}%" for k, v in sh.items()),
                    fill=INK, font=font(12))
        y += 26
        for label, col, d, key, view, cmp_d in rows:
            dr.text((10, y + TH // 2 - 8), label, fill=col, font=font(14, True))
            diffs = []
            for i, s in enumerate(shots):
                a = png(d, key, s, view)
                x = LABEL_W + i * TW
                if a is not None:
                    im.paste(a.resize((TW - 4, TH - 4)), (x + 2, y + 2))
                else:
                    dr.rectangle((x + 2, y + 2, x + TW - 2, y + TH - 2), outline=FAINT)
                if cmp_d:
                    pct = diff_pct(a, png(cmp_d, key, s, view))
                    diffs.append(pct)
                    if pct is not None:
                        dr.text((x + 6, y + TH + 2), f"{pct:.1f} %", fill=HOT if pct > 0.05 else FAINT,
                                font=font(12))
            if diffs:
                v = [p for p in diffs if p is not None]
                txt = f"max {max(v):.1f} %  mean {sum(v) / len(v):.1f} %" if v else "no before"
                dr.text((LABEL_W + n * TW + 8, y + TH // 2 - 8), txt, fill=INK, font=font(13))
            y += TH + ROW_PAD
        y += 10
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    print("WROTE", path)


def main(argv):
    opt = {a.split("=", 1)[0]: (a.split("=", 1) + [True])[1] for a in argv if a.startswith("--")}
    tag = opt.get("--set")
    if not tag or tag is True:
        sys.exit("states_sheet: --set=<tag> is required")
    d, man, ana = load_set(tag)
    bd = None
    if opt.get("--before"):
        bd, bman, _ = load_set(opt["--before"])
    names = [a for a in argv if not a.startswith("--")] or sorted(man)
    out = os.path.join(d, "sheets")

    def analogue_groups(fam):
        return [(f"vanilla {a}", rows_for("V_" + a, d, None, analogue=True), {})
                for a in SV.ANALOGUE[fam] if "V_" + a in ana]

    def block_group(n):
        return (n, rows_for(n, d, bd if bd and n in bman else None), shares(d, n))

    suffix = f"  (before: {opt['--before']})" if bd else ""
    if "--by-family" in opt:
        fams = {}
        for n in names:
            fams.setdefault(catalog.BY_NAME[n].family, []).append(n)
        for fam, ns in fams.items():
            draw(f"{tag}: {fam}{suffix}", analogue_groups(fam) + [block_group(n) for n in ns],
                 os.path.join(out, f"family_{fam}.png"))
    else:
        for n in names:
            draw(f"{tag}: {n}{suffix}", analogue_groups(catalog.BY_NAME[n].family) + [block_group(n)],
                 os.path.join(out, f"{n}.png"))


if __name__ == "__main__":
    main(sys.argv[1:])
