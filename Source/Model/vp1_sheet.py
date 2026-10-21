"""Visual pass 1 contact sheets (Pillow, no Blender).

    python3 Source/Model/vp1_sheet.py audit  [set]     # per block: the audit views + vanilla + reference photos
    python3 Source/Model/vp1_sheet.py compare          # per block: before | after, view by view

Reads preview/visual-pass-1/<set>/ (rendered by DC_PREVIEW=vp1, dc/preview_vp1.py) and the private reference photos
under docs/ideas/reference/datacenter (read only; private, never copied into the mod repo). Audit sheets (with the private photos) go to docs/superpowers/sdd/data-center-core/
visual-pass-1-sheets/ (outside the mod repo); the before | after pairs to preview/visual-pass-1/after/pairs/."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
VP = os.path.join(HERE, "preview", os.environ.get("DC_VP_DIR", "visual-pass-1"))   # pass 2: DC_VP_DIR=visual-pass-2
# the audit sheets embed the private reference photos: they live in the workspace docs, never in the mod repo
SHEETS = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "docs", "superpowers", "sdd", "data-center-core",
                                       os.environ.get("DC_VP_DIR", "visual-pass-1") + "-sheets"))
REF = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "docs", "ideas", "reference", "datacenter"))
CELL = (640, 360)
RACKS = [f"DC_Rack{h}_{v}" for h in (42, 24) for v in ("Open", "SplitFront", "SplitFrontRear")]
SERVERS = ["DC_Srv_" + n for n in ("Compute", "Storage", "Switch", "Blank", "Timer", "EventCtl", "Status", "KVM",
                                   "UPS", "Programmable")]
S = "servers/"
REFS = {
    "rack": ["01-aisle-blue-waterfalls.jpg", S + "4u-rack/server-rack-row-fronts.jpg", "04-rod-hung-basket-over-racks.jpg"],
    "DC_Srv_Compute": [S + "4u-rack/hp-proliant-dl580-g7-4u-front.jpg", S + "4u-rack/nvidia-dgx-b200-hgx-10u.jpg",
                       S + "front-panel-details/dell-poweredge-2800-honeycomb-bezel.jpg"],
    "DC_Srv_Storage": [S + "4u-rack/dell-poweredge-r720xd-drive-wall.jpg", S + "4u-rack/hp-p6300-disk-array.jpg",
                       S + "4u-rack/isilon-iq3000x-storage-front.jpg"],
    "DC_Srv_Switch": [S + "network-pdu/cisco-nexus-7700-front.jpg", S + "blade-chassis/ibm-bladecenter-e-rear.jpg",
                      S + "4u-rack/toolserver-4u-rear-panel.jpg"],
    "DC_Srv_Blank": [S + "blade-chassis/cisco-ucs-5108-pair.jpg", S + "front-panel-details/dell-poweredge-2800-honeycomb-bezel.jpg",
                     S + "blade-chassis/cisco-ucs-5108-front.jpg"],
    "DC_Srv_Timer": [S + "front-panel-details/dell-poweredge-r610-lcd-fronts.jpg", S + "4u-rack/dell-poweredge-r610-r720.jpg",
                     S + "4u-rack/supermicro-x8dtu-server.jpg"],
    "DC_Srv_EventCtl": [S + "network-pdu/cisco-nexus-7700-front.jpg", S + "blade-chassis/ibm-bladecenter-e-rear.jpg",
                        S + "blade-chassis/ibm-bladecenter-s-chassis.jpg"],
    "DC_Srv_Status": [S + "front-panel-details/dell-poweredge-r610-lcd-fronts.jpg", S + "blade-chassis/hp-c7000-front-a.jpg",
                      S + "ups/mge-ups-nersc.jpg"],
    "DC_Srv_KVM": [S + "kvm/rackmount-kvm-drawer.jpg", S + "kvm/rackmount-console-open.jpg",
                   S + "4u-rack/hp-proliant-dl360-dl380-stack.jpg"],
    "DC_Srv_UPS": [S + "ups/ups-front-panel.jpg", S + "ups/mge-ups-nersc.jpg", S + "ups/apc-rack-ups-line-interactive.jpg"],
    "DC_Srv_Programmable": [S + "blade-chassis/hp-c7000-front-a.jpg", S + "blade-chassis/dell-m1000e-front.jpg",
                            S + "blade-chassis/ibm-bladecenter-front.jpg"],
}


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def fit(path, size=CELL, bg=(16, 17, 20)):
    cell = Image.new("RGB", size, bg)
    if not path or not os.path.exists(path):
        ImageDraw.Draw(cell).text((12, 12), "missing: " + os.path.basename(path or ""), fill=(200, 80, 80), font=font(16))
        return cell
    im = Image.open(path).convert("RGB")
    im.thumbnail(size, Image.LANCZOS)
    cell.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
    return cell


def tag(cell, text):
    d = ImageDraw.Draw(cell)
    f = font(18)
    w = d.textlength(text, font=f)
    d.rectangle((0, 0, w + 16, 28), fill=(0, 0, 0))
    d.text((8, 4), text, fill=(235, 235, 235), font=f)
    return cell


def grid(cells, cols, title):
    rows = (len(cells) + cols - 1) // cols
    W, H = CELL[0] * cols, CELL[1] * rows + 44
    sheet = Image.new("RGB", (W, H), (8, 8, 10))
    ImageDraw.Draw(sheet).text((12, 8), title, fill=(255, 255, 255), font=font(26))
    for i, c in enumerate(cells):
        sheet.paste(c, ((i % cols) * CELL[0], 44 + (i // cols) * CELL[1]))
    return sheet


def views(name):
    if name.startswith("DC_Rack"):
        return ["front34_1m", "front34_3m", "top34_3m", "back34_1m", "back34_3m", "vanilla"]
    return ["front34_1m", "front34_3m", "side_1m", "back34_1m", "back34_3m", "vanilla"]


def audit(set_="before"):
    src = os.path.join(VP, set_)
    os.makedirs(SHEETS, exist_ok=True)
    for name in RACKS + SERVERS:
        cells = [tag(fit(os.path.join(src, f"{name}_{v}.png")), v) for v in views(name)]
        refs = REFS.get(name) or REFS["rack"]
        cells += [tag(fit(os.path.join(REF, r)), "ref: " + os.path.basename(r)) for r in refs]
        out = os.path.join(SHEETS, f"audit_{set_}_{name}.jpg")
        grid(cells, 3, f"{name}  [{set_}]  views / vanilla / reference photos").save(out, quality=88)
        print("wrote", out)
    extra = [tag(fit(os.path.join(src, n + ".png")), n) for n in
             ("vp1_servers_in_rack_3m", "vp1_servers_in_rack_1m", "vp1_hero_aisle", "vp1_hero_aisle_wide")]
    out = os.path.join(SHEETS, f"audit_{set_}_overview.jpg")
    grid(extra, 2, f"servers in rack (3 m / 1 m) and the hero aisle  [{set_}]").save(out, quality=88)
    print("wrote", out)


def compare():
    b, a = os.path.join(VP, "before"), os.path.join(VP, "after")
    out_dir = os.path.join(VP, "after", "pairs")
    os.makedirs(out_dir, exist_ok=True)
    for name in RACKS + SERVERS:
        cells = []
        for v in views(name):
            cells += [tag(fit(os.path.join(b, f"{name}_{v}.png")), "BEFORE " + v),
                      tag(fit(os.path.join(a, f"{name}_{v}.png")), "AFTER " + v)]
        out = os.path.join(out_dir, f"pair_{name}.jpg")
        grid(cells, 4, f"{name}: before | after").save(out, quality=88)
        print("wrote", out)
    cells = []
    for n in ("vp1_servers_in_rack_3m", "vp1_servers_in_rack_1m", "vp1_hero_aisle", "vp1_hero_aisle_wide"):
        cells += [tag(fit(os.path.join(b, n + ".png")), "BEFORE " + n), tag(fit(os.path.join(a, n + ".png")), "AFTER " + n)]
    out = os.path.join(out_dir, "pair_overview.jpg")
    grid(cells, 2, "overview: before | after").save(out, quality=88)
    print("wrote", out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        audit(sys.argv[2] if len(sys.argv) > 2 else "before")
    else:
        compare()
