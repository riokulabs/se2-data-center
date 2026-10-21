"""Offline emulation of SE2's block placer, for a server aimed into a rack slot (placement fix, 2026-10-18).

Plain Python (no Blender). The game's placer, decompiled 4.0.0.3151 (tools/decompiled-current/Game2.Client/
Keen.Game2.Client.GameSystems.BlockPlacement.BlockPlacer/; first ported from 2.4.0.95, tools/decompiled/, whose
line numbers are in brackets where they differ), runs per frame (BlockPlacerEntityComponent.cs:1517-1551 [2.4: 1437-1471]):

1. Targeting (BlockPlacementAlignment.cs:506-575 [478-547], RaycastForPlacementTarget): a physics ray from the eye; the first
   grid body hit sets the segment end at hit + 0.25 m. On that grid the FIRST OCCUPIED CELL the eye -> end segment
   crosses (CubeGridComponent.cs:1721-1777 [1589-1645]: every block's occupied cell groups, cell boxes +-0.125 m) is the hit
   cell; the normal is the axis-snapped vector from its centre to the entry point (the face the ray entered), or
   the snapped -ray when that is perpendicular. PlacementPosition = hit cell + normal; RayPosition = that cell
   (UpdateRayPosition, :409-419 [381-391]).
2. ResetMountPoint (BlockPlacementSnapping.cs:64-68 [61-65]): the mount point is the block AABB's centre cell.
3. TrySnapPreviewToGrid (:73-173 [70-170]) with SnapSize 1 (GetBestSnapSizeIndex: the smallest block edge, 1 cell for a
   server; our PlacementDefinitions: AlignWithMountPoints true, SnapAlignment 0, AllowSquareSnapping true, read
   from Assets/DataCenter/*_PlacementDefinition.def): across the normal, the block AABB is centred on the ray cell
   (Min + (Max - Min) / 2, C# integer division), then its mount-face AABB (the block's mount cells facing the
   target, GetMountFaceAABB) is centred the same way (+ (maxOffset - minOffset) / 2); along the normal nothing.
4. TryFindPossibleBlockPlacement (:293-339 [271-317]): the mount point becomes the block's face cell toward the target
   (GetMountPointSubstitutes: Min / Pivot / Max by the sign of -normal in block space); if that placement fails
   (occupied cells or no mount point: CheckPlacementIsPossible with earlyExitSkipCollision), it scans from the
   pivot (AABB.GetCenterTruncated, ActiveBundleData.cs:195 [207]) toward that face cell, else keeps the face cell.
5. The first snap is undone and redone with the new mount point; TryFindFreePosition (:219-279 [216-256]): when the
   cells are not empty, the mount point moves to the nearest offset (perpendicular axes +-n, along +normal 0..n,
   n = the block's longest edge) whose cells are empty (ties: the enumeration order, x fastest, then y, then z).
   4.0 rewrote the scan (EnumeratePointsByDistanceMaxInclusive + an occupancy bitset, :257-266) with the same tie
   order (BoundingBoxIDistanceOrderedEnumerator.Compare: distance, then Z, Y, X) and also treats grid projections
   as occupied (not emulated: no projections here).
6. TrySnapToPrimaryMountPoint: no-op (no primary mount point dummies in this mod).
Validation (client BlockPlacementValidation.cs:190-305 [178-264], server BlockPlacementTester.cs:181-193, 429-496
[433-500]): every
new cell empty, and ANY one mount cell of the new block faces a neighbour block's cell that has a mount point in
the opposite direction (CubeBlockComponent.IsMountPointAvailable -> the definition's mount groups, per cell).

Frames: grid cells (x, y, z) as catalog.bounds, -z = Forward (the rack's front); metres in grid space, cell c
centred at 0.25 c. The rack sits at the grid origin, identity orientation.

Assumptions (stated in the report): SnapSize 1 (the default for a 1-cell edge; a player who raises the snap size
gets coarser in-plane steps), no symmetry, the placer's max build distance not limiting, no other grids. The rack
carries all its generated mount cells, inner and on its outer faces (rack_block); the physics bodies are the rack's
regular collision boxes plus a box per placed block (placed), not the precise render collider.
"""
import itertools
import math

DIRS = {"Forward": (0, 0, -1), "Backward": (0, 0, 1), "Left": (-1, 0, 0), "Right": (1, 0, 0),
        "Up": (0, 1, 0), "Down": (0, -1, 0)}
VEC2DIR = {v: k for k, v in DIRS.items()}
HALF = 0.125
CELL = 0.25
ROT_ID = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
ROT_YAW180 = ((-1, 0, 0), (0, 1, 0), (0, 0, -1))   # a server turned round (its face to the rack's rear)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def neg(a):
    return tuple(-x for x in a)


def mul(R, v):
    return tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))


def transpose(R):
    return tuple(tuple(R[j][i] for j in range(3)) for i in range(3))


def cs_div(a, b):
    """C# integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def box_cells(lo, hi):
    return {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}


def aabb(cells):
    cs = list(cells)
    return (tuple(min(c[i] for c in cs) for i in range(3)), tuple(max(c[i] for c in cs) for i in range(3)))


def slab(origin, d, lo, hi):
    """Entry parameter t >= 0 of origin + t d into the box (lo, hi), or None (0 when the origin is inside)."""
    t0, t1 = 0.0, math.inf
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if origin[i] < lo[i] or origin[i] > hi[i]:
                return None
            continue
        a, b = (lo[i] - origin[i]) / d[i], (hi[i] - origin[i]) / d[i]
        if a > b:
            a, b = b, a
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1:
            return None
    return t0


def snap_axis(v):
    """Vector3.SnappedToNearestAxis: the dominant component's unit vector."""
    i = max(range(3), key=lambda k: abs(v[k]))
    out = [0, 0, 0]
    out[i] = 1 if v[i] > 0 else -1
    return tuple(out)


class Block:
    """A placed block: cells, mount cells per GRID direction, physics boxes (grid metres)."""

    def __init__(self, name, cells, mounts, boxes):
        self.name, self.cells, self.mounts, self.boxes = name, set(cells), mounts, boxes


class Prefab:
    """A block to place: block-local cell bounds, mount directions (MountPointGeneratorSettings) and the cells that
    mount per direction (block-local), which for a server are its whole faces (build_report: coverage 1.0)."""

    def __init__(self, name, lo, hi, directions, mount_cells=None):
        self.name, self.lo, self.hi = name, tuple(lo), tuple(hi)
        self.cells = box_cells(lo, hi)
        self.directions = tuple(directions)
        if mount_cells is None:
            mount_cells = {}
            for d in directions:
                v = DIRS[d]
                ax = [i for i in range(3) if v[i]][0]
                face = hi[ax] if v[ax] > 0 else lo[ax]
                mount_cells[d] = {c for c in self.cells if c[ax] == face}
        self.mount_cells = mount_cells
        # ActiveBundleData.cs:195 (2.4: 207) Pivot = AABB.GetCenterTruncated(); ResetMountPoint: Floor(centre)
        self.pivot = tuple(cs_div(a + b, 2) for a, b in zip(lo, hi))
        self.centre = tuple(math.floor((a + b) / 2) for a, b in zip(lo, hi))


class Grid:
    def __init__(self, blocks=()):
        self.blocks = []
        self.at = {}
        for b in blocks:
            self.add(b)

    def add(self, b):
        self.blocks.append(b)
        for c in b.cells:
            assert c not in self.at, (b.name, c)
            self.at[c] = b

    def empty(self, cells):
        return all(c not in self.at for c in cells)

    def mount_ok(self, prefab, R, mounted):
        """Any of the new block's mount cells meets a neighbour's mount point in the opposite direction."""
        for d, cells in prefab.mount_cells.items():
            gd = mul(R, DIRS[d])
            opp = VEC2DIR[neg(gd)]
            for c in cells:
                g = add(mul(R, c), mounted)
                n = add(g, gd)
                b = self.at.get(n)
                if b is not None and n in b.mounts.get(opp, ()):
                    return True
        return False

    # ------------------------------------------------------------------------------------------- targeting
    def target(self, eye, d, max_dist=10.0):
        """RaycastForPlacementTarget: (hit cell, normal, placement position) or None (no physics hit / no cell)."""
        n = math.sqrt(sum(c * c for c in d))
        d = tuple(c / n for c in d)
        tp = None
        for b in self.blocks:
            for lo, hi in b.boxes:
                t = slab(eye, d, lo, hi)
                if t is not None and t <= max_dist and (tp is None or t < tp):
                    tp = t
        if tp is None:
            return None
        end = tuple(e + c * min(tp + 0.25, max_dist) for e, c in zip(eye, d))
        seg = sub(end, eye)
        best, bt = None, math.inf
        for c in self.at:
            p = tuple(CELL * v for v in c)
            t = slab(eye, seg, tuple(v - HALF for v in p), tuple(v + HALF for v in p))
            if t is not None and t <= 1.0 and t < bt:
                best, bt = c, t
        if best is None:
            return None
        hp = tuple(e + s * bt for e, s in zip(eye, seg))
        nrm = snap_axis(sub(hp, tuple(CELL * v for v in best)))
        if sum(a * b for a, b in zip(nrm, seg)) == 0:
            nrm = snap_axis(neg(seg))
        return best, nrm, add(best, nrm), bt * math.sqrt(sum(c * c for c in seg))

    # ------------------------------------------------------------------------------------------- placement
    def place(self, prefab, R, pp, normal):
        """The ghost's final cells and whether it validates: (cells, valid, mount_ok)."""
        Ri = transpose(R)
        perp = tuple(0 if v else 1 for v in normal)

        def mounted(mp, off):
            return sub(add(pp, off), mul(R, mp))

        def cells_at(mp, off):
            m = mounted(mp, off)
            return {add(mul(R, c), m) for c in prefab.cells}

        def snap(mp, off):
            bp = add(pp, off)
            lo, hi = aabb(cells_at(mp, off))
            so = tuple(bp[i] - lo[i] - cs_div(hi[i] - lo[i], 2) for i in range(3))
            face = VEC2DIR[neg(mul(Ri, normal))]   # GetMountFaceAABB: the face toward the target
            m = mounted(mp, off)
            mc = prefab.mount_cells.get(face)
            lo2, hi2 = aabb({add(mul(R, c), m) for c in mc}) if mc else (lo, hi)
            lo2, hi2 = add(lo2, so), add(hi2, so)
            mn = sub(lo2, bp)
            mx = tuple(bp[i] + 1 - hi2[i] for i in range(3))
            so = tuple(so[i] + cs_div(mx[i] - mn[i], 2) for i in range(3))
            return tuple(so[i] * perp[i] for i in range(3))

        def check(mp, off):
            cs = cells_at(mp, off)
            return self.empty(cs) and self.mount_ok(prefab, R, mounted(mp, off))

        off = (0, 0, 0)
        mp = prefab.centre
        s1 = snap(mp, off)
        off = add(off, s1)
        # TryFindPossibleBlockPlacement
        nl = neg(mul(Ri, normal))
        subst = tuple(prefab.lo[i] if nl[i] < 0 else prefab.hi[i] if nl[i] > 0 else prefab.pivot[i] for i in range(3))
        chosen = subst if check(subst, off) else None
        if chosen is None:
            p = prefab.pivot
            v = sub(p, subst)
            if abs(v[0]) > abs(v[1]):          # Vector3I.AbsMaxComponent (Vector3I.cs:2472; 2.4: 2476)
                ax = 0 if abs(v[0]) > abs(v[2]) else 2
            else:
                ax = 1 if abs(v[1]) > abs(v[2]) else 2
            step = [0, 0, 0]
            step[ax] = (v[ax] > 0) - (v[ax] < 0)
            k = 0
            while p != subst and k < 16:
                if check(p, off):
                    chosen = p
                    break
                p = sub(p, tuple(step))
                k += 1
        mp = chosen if chosen is not None else subst
        off = sub(off, s1)
        off = add(off, snap(mp, off))
        # TryFindFreePosition
        if not self.empty(cells_at(mp, off)):
            ax = [i for i in range(3) if normal[i]][0]
            p1, p2 = [tuple(1 if j == i else 0 for j in range(3)) for i in range(3) if i != ax]
            val = max(h - l + 1 for l, h in zip(prefab.lo, prefab.hi))
            a = neg(mul(Ri, tuple((p1[i] + p2[i]) * val for i in range(3))))
            b = mul(Ri, tuple((p1[i] + p2[i] + normal[i]) * val for i in range(3)))
            lo, hi = tuple(min(x, y) for x, y in zip(a, b)), tuple(max(x, y) for x, y in zip(a, b))
            best, bd = mp, math.inf
            for oz in range(lo[2], hi[2] + 1):
                for oy in range(lo[1], hi[1] + 1):
                    for ox in range(lo[0], hi[0] + 1):
                        o = (ox, oy, oz)
                        d2 = ox * ox + oy * oy + oz * oz
                        if d2 < bd and self.empty(cells_at(add(mp, o), off)):
                            best, bd = add(mp, o), d2
            mp = best
        cs = cells_at(mp, off)
        mok = self.mount_ok(prefab, R, mounted(mp, off))
        return cs, self.empty(cs) and mok, mok

    def aim(self, prefab, R, eye, look_at):
        """One frame: aim from eye at look_at. Returns None (nothing targeted) or a dict."""
        t = self.target(eye, sub(look_at, eye))
        if t is None:
            return None
        hit, nrm, pp, dist = t
        cells, valid, mok = self.place(prefab, R, pp, nrm)
        return {"hit": hit, "normal": nrm, "pp": pp, "cells": cells, "valid": valid, "mount": mok,
                "hit_block": self.at[hit].name, "dist": dist}


# ----------------------------------------------------------------------------------------------- the mod's data

def rack_block(spec, entry):
    """The rack as the grid sees it: occupied cells (the box minus build_report free_cells), EVERY mount cell
    (build_report mount_cells: the inner ones, i.e. the slot rails, floor, ceiling and the PDU column's bulkhead, AND
    the box faces: the sides, the top, the Open racks' containment rail band; final review M1, so a block mounted on
    the rack's outside is seen too) and the regular collision boxes (dc/rack.py collision(), Blender frame ->
    collision glTF (x, z, -y) -> grid metres (+ the .model shift)).
    A report without mount_cells (built before 2026-10-19) is refused: rebuild the rack (build_dc.py, headless)."""
    from . import catalog, rack
    lo, hi = catalog.bounds(spec)
    p = entry["placement"]
    if "mount_cells" not in p:
        raise KeyError(f"{spec.name}: build_report placement has no mount_cells (outer faces); rebuild the rack")
    free = {tuple(c) for c in p["free_cells"]}
    cells = box_cells(lo, hi) - free
    mounts = {d: {tuple(c) for c in cs} for d, cs in p["mount_cells"].items()}
    shift = p["shift"]
    boxes = []
    for _, a, b in rack.collision(spec)["regular"]:
        ga = (a[0], a[2], -a[1])
        gb = (b[0], b[2], -b[1])
        blo = tuple(min(x, y) + s for x, y, s in zip(ga, gb, shift))
        bhi = tuple(max(x, y) + s for x, y, s in zip(ga, gb, shift))
        boxes.append((blo, bhi))
    return Block(spec.name, cells, mounts, boxes)


def server_prefab(spec, directions):
    from . import catalog
    lo, hi = catalog.bounds(spec)
    return Prefab(spec.name, lo, hi, [d.strip() for d in directions.split(",")])


def placed(prefab, R, mounted, name=None):
    """A prefab placed at block-origin `mounted` with rotation R, as a grid Block (its body fills its cells)."""
    cells = {add(mul(R, c), mounted) for c in prefab.cells}
    mounts = {}
    for d, cs in prefab.mount_cells.items():
        gd = VEC2DIR[mul(R, DIRS[d])]
        mounts.setdefault(gd, set()).update(add(mul(R, c), mounted) for c in cs)
    lo, hi = aabb(cells)
    box = (tuple(CELL * v - HALF for v in lo), tuple(CELL * v + HALF for v in hi))
    return Block(name or prefab.name, cells, mounts, [box])


def slot_seat(slot_cells, prefab, k, n_u):
    """The seat of a server n_u slots tall whose bottom slot is k (1-based): the slot cells it fills."""
    ys = sorted({c[1] for c in slot_cells})
    want = set(ys[k - 1:k - 1 + n_u])
    return {c for c in slot_cells if c[1] in want}


def mounted_for(prefab, R, cells):
    """The block origin that puts prefab (rotation R) exactly on `cells`."""
    lo, _ = aabb(cells)
    plo, _ = aabb({mul(R, c) for c in prefab.cells})
    return sub(lo, plo)


def aim_fan(slot_cells_k, front_z, depth_rows, eye_dists=(0.8, 1.4, 2.2), eye_dx=(-0.35, 0.0, 0.35),
            eye_dy=(-0.4, 0.0, 0.5)):
    """Eye positions in front of a slot (grid metres) and look-at points spread over the slot's inside: the rear
    stop plane, the rail faces and the floor at every depth row, a 3 x 3 grid across the opening. Yields
    (eye, look_at, label)."""
    xs = sorted({c[0] for c in slot_cells_k})
    ys = sorted({c[1] for c in slot_cells_k})
    zs = sorted({c[2] for c in slot_cells_k})
    x0, x1 = CELL * xs[0] - HALF, CELL * xs[-1] + HALF
    y0, y1 = CELL * ys[0] - HALF, CELL * ys[-1] + HALF
    zf = CELL * front_z - HALF            # the rack's front plane
    looks = []
    zb = CELL * zs[-1] + HALF             # the slot's back plane
    for fx in (0.1, 0.3, 0.5, 0.7, 0.9):
        for fy in (0.15, 0.5, 0.85):
            looks.append(((x0 + fx * (x1 - x0), y0 + fy * (y1 - y0), zb + 0.001), f"back {fx:.1f},{fy:.2f}"))
    for z in depth_rows:
        zc = CELL * z
        for fy in (0.25, 0.75):
            looks.append(((x0 + 0.001 - 0.002, y0 + fy * (y1 - y0), zc), f"left rail z{z} {fy}"))
            looks.append(((x1 - 0.001 + 0.002, y0 + fy * (y1 - y0), zc), f"right rail z{z} {fy}"))
        for fx in (0.25, 0.75):
            looks.append(((x0 + fx * (x1 - x0), y0 - 0.001, zc), f"floor z{z} {fx}"))
    for dist in eye_dists:
        for dx in eye_dx:
            for dy in eye_dy:
                eye = ((x0 + x1) / 2 + dx, (y0 + y1) / 2 + 0.3 + dy, zf - dist)
                for la, lab in looks:
                    yield eye, la, f"eye d{dist} dx{dx} dy{dy} -> {lab}"
