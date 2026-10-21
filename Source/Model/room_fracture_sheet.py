"""Room fracture refinement sheets (Pillow, no Blender), from the panels room_fracture_preview.py renders.

    python3 Source/Model/room_fracture_sheet.py

Writes preview/room-fracture/ (git-ignored, like every preview):
  floor.jpg / roof.jpg   one row per block: intact | BEFORE (layer split) zones + colliders | AFTER (in plane) zones +
                         colliders | after: broken off | after: damaged model, with the zones from export.json;
  contact.jpg            every panel.
The layout is fracture_compare_sheet.py's.
"""
import os

import fracture_compare_sheet as S

S.ROOT = os.path.join(S.HERE, "preview", "room-fracture")
S.PANELS = os.path.join(S.ROOT, "panels")
S.COLS = (("intact", "intact (NonFractured)"), ("before_zones", "BEFORE: layer split, zones + colliders"),
          ("zones", "AFTER: in-plane zones + colliders"), ("broken", "after: broken off (game materials)"),
          ("damaged", "after: damaged model (Deformed)"))
FAMILIES = {"floor": ["DC_Floor_Solid_050", "DC_Floor_Perf_050", "DC_Floor_Solid_100", "DC_Floor_Perf_100"],
            "roof": ["DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200"]}


def main():
    for fam, names in FAMILIES.items():
        S.rows_sheet(f"Room: {fam} fracture refinement (before / after)",
                     [(n, n.replace("DC_", "")) for n in names], os.path.join(S.ROOT, f"{fam}.jpg"))
    S.contact(os.path.join(S.ROOT, "contact.jpg"))


if __name__ == "__main__":
    main()
