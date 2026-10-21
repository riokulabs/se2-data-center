"""Icon contact sheets: our build-menu icons side by side with vanilla icons (read-only), at 200 px on the dark
G-screen tone and on a light tone, plus 64 px toolbar-size rows (distinguishable at a glance?).

    python3 Source/Model/icon_sheet.py          core: the 16 rack and server icons -> preview/task-10/
    python3 Source/Model/icon_sheet.py trays    the 38 cable-tray icons, one row per menu group, against vanilla
                                                structural icons and our core icons -> preview/p2-task-9/
    python3 Source/Model/icon_sheet.py room     the 19 room-piece icons, one row per menu group, against the vanilla
                                                clone sources' icons -> preview/plan3-task-10/ (Plan 3 Task 10)
    python3 Source/Model/icon_sheet.py room_menu  the G-screen mock-ups with the room groups -> preview/plan3-task-10/
    python3 Source/Model/icon_sheet.py menu     a G-screen mock-up of the "Data Center" subcategory: every group
                                                tile in Order, its kinds by priority, each kind's sizes
                                                -> preview/p2-task-9/menu_structure.png
(needs Pillow)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dc import catalog, config  # noqa: E402

VREF = os.path.join(config.VANILLA_REF, "Blocks")
VANILLA = ("Timer/50/Timer50_Icon.png", "EventController/100/Models/EventController100_Icon.png",
           "Batteries/Battery/50/Icon/Battery50_Icon.png", "ControlPanel/25/ControlPanel25_Icon.png",
           "Walls/Inserts/Panel/WallInsertPanel_Icon.png", "Lockers/Locker/200/Locker200_Icon.png",
           "Batteries/Battery/250/Icon/Battery250_Icon.png", "LCDPanels/LCD/50/LCD50_Icon.png")
OUT = os.path.join(config.PREVIEW_DIR, "task-10", "icons_contact_sheet.png")


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def row(sheet, d, items, y, bg, label, cell=210, size=200, fg=(225, 228, 232)):
    d.rectangle((0, y, sheet.width, y + cell + 34), fill=bg)
    d.text((10, y + 4), label, font=font(15), fill=fg)
    for i, (path, cap) in enumerate(items):
        im = Image.open(path).convert("RGBA")
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        x = 10 + i * cell
        sheet.alpha_composite(im, (x, y + 24))
        d.text((x, y + 24 + size), cap[:28], font=font(11), fill=fg)


def main():
    ours = [(os.path.join(config.HERE, "UI", f"{b.name}_Icon.png"), b.name.replace("DC_", ""))
            for b in catalog.CORE_BLOCKS]
    van = [(os.path.join(VREF, p), "vanilla " + os.path.basename(p).replace("_Icon.png", "")) for p in VANILLA]
    per = 8
    cell = 210
    W = 20 + per * cell
    groups = [ours[i:i + per] for i in range(0, len(ours), per)]
    H = 40 + (len(groups) + 1) * 2 * (cell + 40) + 2 * 110
    sheet = Image.new("RGBA", (W, H), (20, 22, 26, 255))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), "Data Center icons vs vanilla (200 px, transparent PNG composited on the G-screen tone and a light "
                    "tone; last rows at 64 px toolbar size)", font=font(16), fill=(240, 240, 240))
    y = 40
    dark, light = (38, 43, 51, 255), (196, 200, 206, 255)
    for bg, fg, tone in ((dark, (225, 228, 232), "dark"), (light, (25, 28, 32), "light")):
        row(sheet, d, van, y, bg, f"VANILLA ({tone})", fg=fg)
        y += cell + 40
        for k, g in enumerate(groups):
            row(sheet, d, g, y, bg, f"OURS {k + 1}/{len(groups)} ({tone})", fg=fg)
            y += cell + 40
    # 64 px toolbar size: all 16 ours, then the vanilla row
    for items, label in ((ours, "OURS at 64 px"), (van, "VANILLA at 64 px")):
        d.rectangle((0, y, W, y + 100), fill=dark)
        d.text((10, y + 4), label, font=font(15), fill=(225, 228, 232))
        for i, (p, _) in enumerate(items):
            im = Image.open(p).convert("RGBA").resize((64, 64), Image.LANCZOS)
            sheet.alpha_composite(im, (10 + i * 80, y + 28))
        y += 110
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.convert("RGB").save(OUT)
    print("WROTE", OUT)


TRAY_VANILLA = ("Walls/Inserts/Pipes/WallInsertPipes_Icon.png", "Truss/Struts/Long/TrussFrame_Long_Icon.png",
                "Conveyors/ConveyorStraight/250/LargeConveyorStraight_Icon.png",
                "Conveyors/ConveyorCurve/200/LargeConveyorCurve_Icon.png",
                "Conveyors/ConveyorJunctionT/250/LargeConveyorJunctionT_Icon.png",
                "Catwalks/CatwalkNarrowBase/250/CatwalkNarrowBase_250_Icon.png",
                "Handrail/Straight/250/HandRailLongSection_250_Icon.png",
                "Catwalks/CatwalkCornerBase/250/CatwalkCornerBase_250_Icon.png")
TRAY_OUT = os.path.join(config.PREVIEW_DIR, "p2-task-9", "icons_contact_sheet_trays.png")


def tray_rows():
    """[(group name, [(icon path, caption)])] in menu order: per group, its kinds by priority, a kind's sizes in size
    order (the order the G-screen shows them)."""
    from dc import menu, names
    out = []
    for g, v in menu.GROUPS.items():
        if not g.startswith("tray"):
            continue
        blocks = [b for b in catalog.BLOCKS if menu.group(b) == g]
        owners = sorted({menu.kind_owner(b).name for b in blocks}, key=lambda n: menu.priority(catalog.BY_NAME[n]))
        items = []
        for o in owners:
            for b in menu.kind_blocks(catalog.BY_NAME[o]):
                cap = names.NAMES[b.name][0].replace("Cable Tray, ", "")
                items.append((os.path.join(config.HERE, "UI", f"{b.name}_Icon.png"), cap))
        out.append((v["name"], items))
    return out


def trays():
    van = [(os.path.join(VREF, p), "vanilla " + os.path.basename(p).replace("_Icon.png", "")) for p in TRAY_VANILLA]
    core = [(os.path.join(config.HERE, "UI", f"{n}_Icon.png"), n.replace("DC_", "")) for n in
            ("DC_Rack42_Open", "DC_Rack24_SplitFront", "DC_Srv_UPS", "DC_Srv_KVM", "DC_Srv_Storage")]
    rows = tray_rows()
    per, cell = 9, 210
    W = 20 + per * cell
    H = 40 + 2 * (2 + len(rows)) * (cell + 40) + (len(rows) + 1) * 110 + 20
    sheet = Image.new("RGBA", (W, H), (20, 22, 26, 255))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), "Cable-tray icons (38) vs vanilla structural icons and our core icons (200 px on the G-screen tone "
                    "and a light tone; 64 px toolbar rows at the end)", font=font(16), fill=(240, 240, 240))
    y = 40
    dark, light = (38, 43, 51, 255), (196, 200, 206, 255)
    for bg, fg, tone in ((dark, (225, 228, 232), "dark"), (light, (25, 28, 32), "light")):
        row(sheet, d, van, y, bg, f"VANILLA ({tone})", fg=fg)
        y += cell + 40
        row(sheet, d, core, y, bg, f"OURS, CORE ({tone})", fg=fg)
        y += cell + 40
        for name, items in rows:
            row(sheet, d, items, y, bg, f"{name.upper()} ({tone})", fg=fg)
            y += cell + 40
    for label, items in [(f"{n} at 64 px", it) for n, it in rows] + [("VANILLA at 64 px", van)]:
        d.rectangle((0, y, W, y + 100), fill=dark)
        d.text((10, y + 4), label, font=font(15), fill=(225, 228, 232))
        for i, (p, _) in enumerate(items):
            im = Image.open(p).convert("RGBA").resize((64, 64), Image.LANCZOS)
            sheet.alpha_composite(im, (10 + i * 80, y + 28))
        y += 110
    os.makedirs(os.path.dirname(TRAY_OUT), exist_ok=True)
    sheet.convert("RGB").save(TRAY_OUT)
    print("WROTE", TRAY_OUT)


ROOM_VANILLA = ("Catwalks/CatwalkSquareBase/250/CatwalkSquareBase_250_Icon.png",
                "Gyroscopes/Gyroscopes/250/Gyroscope250_Icon.png", "DeckPanel/250/DeckPanel250_Icon.png",
                "Doors/SlideDoorNarrow/250/NarrowSlidingDoor.png", "LCDPanels/NarrowLCD/50/NarrowLCD50_Icon.png",
                "Walls/Inserts/Panel/WallInsertPanel_Icon.png", "Batteries/Battery/250/Icon/Battery250_Icon.png",
                "LCDPanels/LCD/50/LCD50_Icon.png")
ROOM_OUT = os.path.join(config.PREVIEW_DIR, "plan3-task-10", "icons_contact_sheet_room.png")
ROOM_GROUPS = ("floor", "roompower", "contain", "signs")


def _vanilla_icon(rel):
    """A vanilla icon by its path under Blocks/, or (the file names differ from the folder names) the first
    *_Icon.png in that folder."""
    p = os.path.join(VREF, rel)
    if os.path.exists(p):
        return p
    d = os.path.dirname(p)
    hits = sorted(f for f in os.listdir(d) if f.endswith("_Icon.png")) if os.path.isdir(d) else []
    return os.path.join(d, hits[0]) if hits else None


def group_rows(keys):
    """[(group name, [(icon path, caption)])] for menu groups `keys`, in G-screen order (kinds by priority, a kind's
    sizes in size order)."""
    from dc import menu, names
    out = []
    for g in keys:
        blocks = [b for b in catalog.BLOCKS if menu.group(b) == g]
        owners = sorted({menu.kind_owner(b).name for b in blocks}, key=lambda n: menu.priority(catalog.BY_NAME[n]))
        items = [(os.path.join(config.HERE, "UI", f"{b.name}_Icon.png"), names.NAMES[b.name][0])
                 for o in owners for b in menu.kind_blocks(catalog.BY_NAME[o])]
        out.append((menu.GROUPS[g]["name"], items))
    return out


def room():
    """Plan 3 Task 10: the 19 room-piece icons, one row per menu group, against the vanilla clone sources' icons and
    our core icons, on both tones, then at 64 px."""
    van = [(p, "vanilla " + os.path.basename(p).replace("_Icon.png", "")) for p in map(_vanilla_icon, ROOM_VANILLA)
           if p]
    core = [(os.path.join(config.HERE, "UI", f"{n}_Icon.png"), n.replace("DC_", "")) for n in
            ("DC_Rack42_SplitFront", "DC_Rack24_Open", "DC_Srv_UPS", "DC_Tray_Drop_Full", "DC_TrayRods_100")]
    rows = group_rows(ROOM_GROUPS)
    per, cell = 8, 210
    W = 20 + per * cell
    H = 40 + 2 * (2 + len(rows)) * (cell + 40) + (len(rows) + 1) * 110 + 20
    sheet = Image.new("RGBA", (W, H), (20, 22, 26, 255))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), "Room-piece icons (19) vs the vanilla clone sources and our core icons (200 px on the G-screen "
                    "tone and a light tone; 64 px toolbar rows at the end)", font=font(16), fill=(240, 240, 240))
    y = 40
    dark, light = (38, 43, 51, 255), (196, 200, 206, 255)
    for bg, fg, tone in ((dark, (225, 228, 232), "dark"), (light, (25, 28, 32), "light")):
        row(sheet, d, van, y, bg, f"VANILLA ({tone})", fg=fg)
        y += cell + 40
        row(sheet, d, core, y, bg, f"OURS, CORE + TRAYS ({tone})", fg=fg)
        y += cell + 40
        for name, items in rows:
            row(sheet, d, items, y, bg, f"{name.upper()} ({tone})", fg=fg)
            y += cell + 40
    for label, items in [(f"{n} at 64 px", it) for n, it in rows] + [("VANILLA at 64 px", van)]:
        d.rectangle((0, y, W, y + 100), fill=dark)
        d.text((10, y + 4), label, font=font(15), fill=(225, 228, 232))
        for i, (p, _) in enumerate(items):
            im = Image.open(p).convert("RGBA").resize((64, 64), Image.LANCZOS)
            sheet.alpha_composite(im, (10 + i * 80, y + 28))
        y += 110
    os.makedirs(os.path.dirname(ROOM_OUT), exist_ok=True)
    sheet.convert("RGB").save(ROOM_OUT)
    print("WROTE", ROOM_OUT)


MENU_OUT = os.path.join(config.PREVIEW_DIR, "p2-task-9", "menu_structure.png")


def menu_sheet(keys=None, out=None):
    """Category > Subcategory > group tiles (by Order) > kind tiles (by OrderingPriority, owner's icon and kind name)
    > the kind's blocks as size 1..n (DisplaySize order), from dc/menu.py and dc/names.py: the staged structure.
    keys: only these groups (default all); out: the file (default MENU_OUT)."""
    from dc import menu, names
    groups = [(g, v) for g, v in menu.GROUPS.items() if keys is None or g in keys]
    kw, rowh = 150, 128
    rows = []
    for g, v in groups:
        blocks = [b for b in catalog.BLOCKS if menu.group(b) == g]
        owners = sorted({menu.kind_owner(b).name for b in blocks}, key=lambda n: menu.priority(catalog.BY_NAME[n]))
        rows.append((g, v, [catalog.BY_NAME[o] for o in owners]))
    W = 260 + 10 * kw
    H = 70 + sum(rowh + 60 + (34 if any(len(menu.kind_blocks(o)) > 1 for o in r[2]) else 0) for r in rows)
    sheet = Image.new("RGBA", (W, H), (20, 22, 26, 255))
    d = ImageDraw.Draw(sheet)
    d.text((12, 10), f"G-screen > Automation > {menu.SUBCATEGORY['name']}: group tiles in Order, kinds in "
                     "OrderingPriority, sizes in DisplaySize order", font=font(18), fill=(240, 240, 240))
    y = 50
    for g, v, owners in rows:
        multi = any(len(menu.kind_blocks(o)) > 1 for o in owners)
        h = rowh + 50 + (34 if multi else 0)
        d.rectangle((6, y, W - 6, y + h), fill=(38, 43, 51, 255), outline=(70, 78, 92, 255))
        d.text((16, y + 8), f"{v['name']}", font=font(17), fill=(250, 200, 90))
        d.text((16, y + 32), f"Order {v['order']}, {len(owners)} kinds", font=font(12), fill=(170, 176, 186))
        for i, o in enumerate(owners):
            x = 250 + i * kw
            im = Image.open(os.path.join(config.HERE, "UI", f"{o.name}_Icon.png")).convert("RGBA").resize(
                (96, 96), Image.LANCZOS)
            d.rectangle((x - 4, y + 6, x + kw - 12, y + h - 6), fill=(48, 54, 64, 255))
            sheet.alpha_composite(im, (x + (kw - 16 - 96) // 2, y + 8))
            kname = menu.kind_text(o)[0].replace("Cable Tray, ", "")
            d.text((x, y + 108), f"{menu.priority(o)}. {kname}"[:24], font=font(11), fill=(225, 228, 232))
            sizes = menu.kind_blocks(o)
            if len(sizes) > 1:
                for k, b in enumerate(sizes):
                    lab = names.NAMES[b.name][0].replace("Cable Tray, ", "").replace("Server Rack ", "")
                    lab = lab.split(" (")[0].replace("Straight ", "").replace("Hanger Rods ", "")
                    d.text((x, y + 126 + 12 * k), f"size {k + 1}: {lab}  [DS {menu.display_size(b):g}]"[:28],
                           font=font(10), fill=(160, 200, 240))
        y += h + 10
    out = out or MENU_OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.convert("RGB").save(out)
    print("WROTE", out)


def room_menu():
    """Plan 3 Task 10: the G-screen mock-up of the whole Data Center subcategory (every tile, the four room groups
    last) and of the four room groups alone."""
    menu_sheet(out=os.path.join(config.PREVIEW_DIR, "plan3-task-10", "menu_structure_all.png"))
    menu_sheet(ROOM_GROUPS, os.path.join(config.PREVIEW_DIR, "plan3-task-10", "menu_structure_room.png"))


if __name__ == "__main__":
    {"trays": trays, "menu": menu_sheet, "room": room, "room_menu": room_menu}.get(
        (sys.argv[1:] or ["core"])[0], main)()
