"""The scripted KVM's motion as charts (stdlib SVG, no bpy, no plotting library).

  kvm_timing.svg         slide (m) and fold (deg) against t for the open, the close and the fast stow, plus the door
                         race (door_close_while_out) with the rack door's OpenRatio in its own row; the sequencer's
                         FoldGate, OpenBeat and RetractGate moments are marked.
  kvm_motion_graphs.svg  before | after the feel retune: position AND velocity of the slide (m, m/s) and of the fold
                         (deg, deg/s) for the open, the close and the fast stow.

Both read the CoreTests dumps (Source/Model/preview/scripts/traj/*.csv; the pre-retune copies in traj_before/) and the
tuning from Scripts/Client/Core/KvmMotionTuning.cs (kvm_motion.read_tuning). One y-scale per panel (small multiples,
never a dual axis); the door is a third row, not a second scale on the slide.

    python3 -m dc.kvm_charts            (from Source/Model) writes both into preview/scripts/
"""
import math
import os
from xml.sax.saxutils import escape

from . import kvm_motion as K
from . import subparts as S

OUT = os.path.join(K.MODEL_DIR, "preview", "scripts")
BEFORE_DIR = os.path.join(OUT, "traj_before")
# the shipped tuning before the feel retune (commit 2d824cc), for the "before" markers
BEFORE_TUNING = {"FoldGate": 0.91, "OpenBeat": 0.06, "RetractGate": 0.02, "RetractGateFast": 0.08}
DOOR_LEAD = 0.1          # the leaves start this long before the sequencer is told (the door's replication latency)

# reference palette: categorical slots 1-2; text and grid in ink tokens
STYLE = """
.bg { fill: #fcfcfb; }
text { font-family: system-ui, -apple-system, 'Segoe UI', 'DejaVu Sans', sans-serif; fill: #52514e; font-size: 11px; }
.title { fill: #0b0b0b; font-size: 16px; font-weight: 600; }
.sub { fill: #52514e; font-size: 12px; }
.col { fill: #0b0b0b; font-size: 13px; font-weight: 600; }
.axis { stroke: #8a8984; stroke-width: 1; fill: none; }
.grid { stroke: #e4e3df; stroke-width: 1; fill: none; }
.mark { stroke: #8a8984; stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.mlabel { fill: #6f6e69; font-size: 10px; }
.s1 { stroke: #2a78d6; stroke-width: 2; fill: none; stroke-linejoin: round; stroke-linecap: round; }
.s2 { stroke: #eb6834; stroke-width: 2; fill: none; stroke-linejoin: round; stroke-linecap: round; }
.before { stroke: #9a9993; stroke-width: 2; fill: none; stroke-dasharray: 5 3; stroke-linejoin: round; }
.sw1 { fill: #2a78d6; } .sw2 { fill: #eb6834; } .swb { fill: #9a9993; }
@media (prefers-color-scheme: dark) {
  .bg { fill: #1a1a19; } text, .sub { fill: #c3c2b7; } .title, .col { fill: #ffffff; }
  .axis, .mark { stroke: #8f8e86; } .grid { stroke: #33332f; } .mlabel { fill: #8f8e86; }
  .s1 { stroke: #3987e5; } .s2 { stroke: #d95926; } .before { stroke: #77766f; }
  .sw1 { fill: #3987e5; } .sw2 { fill: #d95926; } .swb { fill: #77766f; }
}
"""


def _nice(lo, hi, n=4):
    """Round tick values covering [lo, hi]."""
    span = max(hi - lo, 1e-9)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    a = math.floor(lo / step + 1e-9) * step
    out = []
    v = a
    while v <= hi + step * 1e-6:
        out.append(round(v, 10))
        v += step
    return out


def _fmt(v):
    return f"{v:.0f}" if abs(v) >= 10 or v == int(v) else (f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) < 1 else f"{v:.1f}")


def velocity(traj, key):
    """Central-difference rate of column key (1 slide, 2 fold) of a [(t, slide, fold)] trajectory."""
    out = []
    n = len(traj)
    for i in range(n):
        a, b = traj[max(i - 1, 0)], traj[min(i + 1, n - 1)]
        out.append((traj[i][0], (b[key] - a[key]) / (b[0] - a[0]) if b[0] > a[0] else 0.0))
    return out


def series(traj, quantity):
    """[(t, value)] of one plotted quantity of a trajectory."""
    if quantity == "slide":
        return [(t, s * S.TRAVEL) for t, s, _ in traj]
    if quantity == "fold":
        return [(t, f * S.FOLD_DEG) for t, _, f in traj]
    if quantity == "slide_v":
        return [(t, v * S.TRAVEL) for t, v in velocity(traj, 1)]
    if quantity == "fold_v":
        return [(t, v * S.FOLD_DEG) for t, v in velocity(traj, 2)]
    raise ValueError(quantity)


def moments(traj, tuning, kind):
    """[(t, label)] of the sequencer's gate moments in a trajectory."""
    out = []
    if kind == "open":
        g = next((t for t, s, _ in traj if s >= tuning["FoldGate"]), None)
        if g is not None:
            out += [(g, "FoldGate"), (g + tuning["OpenBeat"], "OpenBeat ends: lift")]
    elif kind in ("close", "fast"):
        gate = tuning["RetractGate" if kind == "close" else "RetractGateFast"]
        name = "RetractGate" if kind == "close" else "RetractGateFast"
        moved = next((t for t, s, _ in traj if s < 1.0), None)
        if moved is not None:
            out.append((moved, f"{name} ({gate * S.FOLD_DEG:.0f} deg): drawer goes"))
    return out


class Chart:
    """A grid of panels (rows x columns), each with its own y-scale; shared t per column."""

    def __init__(self, title, subtitle, cols, rows, pw=300, ph=150):
        self.title, self.subtitle, self.cols, self.rows = title, subtitle, cols, rows
        self.pw, self.ph = pw, ph
        self.ml, self.mt, self.gx, self.gy = 70, 92, 46, 40
        self.w = self.ml + len(cols) * (pw + self.gx) + 10
        self.h = self.mt + len(rows) * (ph + self.gy) + 46
        self.body = []

    def frame(self, c, r):
        return self.ml + c * (self.pw + self.gx), self.mt + r * (self.ph + self.gy)

    def panel(self, c, r, t_max, y_lo, y_hi, unit, lines, marks=(), show_col=True):
        """lines = [(css class, [(t, y)], tooltip)]."""
        x0, y0 = self.frame(c, r)
        pw, ph = self.pw, self.ph
        yt = _nice(y_lo, y_hi)
        y_lo, y_hi = min(y_lo, yt[0]), max(y_hi, yt[-1])
        xt = _nice(0.0, t_max, 5)
        t_max = max(t_max, xt[-1])
        X = lambda t: x0 + pw * t / t_max                       # noqa: E731
        Y = lambda v: y0 + ph - ph * (v - y_lo) / (y_hi - y_lo)  # noqa: E731
        b = self.body
        if r == 0 and show_col:
            b.append(f'<text class="col" x="{x0}" y="{y0 - 14}">{escape(self.cols[c])}</text>')
        for v in yt:
            b.append(f'<line class="grid" x1="{x0}" x2="{x0 + pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
            b.append(f'<text x="{x0 - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{_fmt(v)}</text>')
        for v in xt:
            b.append(f'<text x="{X(v):.1f}" y="{y0 + ph + 14}" text-anchor="middle">{_fmt(v)}</text>')
        b.append(f'<path class="axis" d="M{x0},{y0} V{y0 + ph} H{x0 + pw}"/>')
        if c == 0:
            b.append(f'<text x="{x0 - 52}" y="{y0 + ph / 2}" transform="rotate(-90 {x0 - 52} {y0 + ph / 2})" '
                     f'text-anchor="middle">{escape(self.rows[r])}</text>')
        b.append(f'<text x="{x0 + pw}" y="{y0 + ph + 28}" text-anchor="end">t (s)  {escape(unit)}</text>')
        for k, (t, label) in enumerate(marks):
            if 0 <= t <= t_max:
                b.append(f'<line class="mark" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y0}" y2="{y0 + ph}"/>')
                b.append(f'<text class="mlabel" x="{X(t) + 3:.1f}" y="{y0 + 10 + 11 * k}">{escape(label)}</text>')
        for cls, pts, tip in lines:
            pts = [p for p in pts if p[0] <= t_max + 1e-9]
            step = max(1, len(pts) // 600)
            pts = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
            d = "M" + " L".join(f"{X(t):.1f},{Y(max(min(v, y_hi), y_lo)):.1f}" for t, v in pts)
            b.append(f'<path class="{cls}" d="{d}"><title>{escape(tip)}</title></path>')

    def legend(self, items):
        x = self.ml
        y = 62
        for cls, label in items:
            self.body.append(f'<rect class="{cls}" x="{x}" y="{y - 9}" width="14" height="4" rx="2"/>')
            self.body.append(f'<text x="{x + 20}" y="{y - 4}">{escape(label)}</text>')
            x += 28 + 7 * len(label)

    def svg(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img"><title>{escape(self.title)}</title>'
                f'<style>{STYLE}</style><rect class="bg" width="100%" height="100%"/>'
                f'<text class="title" x="{self.ml}" y="26">{escape(self.title)}</text>'
                f'<text class="sub" x="{self.ml}" y="44">{escape(self.subtitle)}</text>')
        return head + "".join(self.body) + "</svg>\n"


def _end(traj):
    return traj[-1][0]


def timing_svg(path=None, traj_dir=K.TRAJ_DIR):
    """kvm_timing.svg (the shipped tuning)."""
    path = path or os.path.join(OUT, "kvm_timing.svg")
    tun = K.read_tuning()
    runs = [("open", "Open", "open"), ("close", "Close", "close"), ("fast_stow", "Fast stow", "fast"),
            ("door_close_while_out", "Door closes while out", "fast")]
    trs = {n: K.load(os.path.join(traj_dir, n + ".csv")) for n, _, _ in runs}
    ch = Chart("KVM motion timing (scripted, shipped tuning)",
               "Slide and lid fold from the CoreTests 240 Hz dumps; dashed lines are the sequencer's gates. "
               f"Door race: the leaves start {DOOR_LEAD:.1f} s before the stow command (the door's start latency).",
               [r[1] for r in runs], ["slide (m)", "lid fold (deg)", "door OpenRatio"], pw=260, ph=130)
    ch.legend([("sw1", "KVM (slide / fold)"), ("sw2", "rack door OpenRatio")])
    for c, (n, label, kind) in enumerate(runs):
        tr = trs[n]
        cmd = K.first_command(os.path.join(traj_dir, n + ".csv"), "FastStow") if n == "door_close_while_out" else 0.0
        mk = moments(tr, tun, kind)
        if n == "door_close_while_out":
            mk = [(cmd, "FastStow command")] + mk
        tm = _end(tr)
        ch.panel(c, 0, tm, 0.0, S.TRAVEL, "", [("s1", series(tr, "slide"), f"{label}: slide (m)")], mk)
        ch.panel(c, 1, tm, 0.0, 105.0, "", [("s1", series(tr, "fold"), f"{label}: fold (deg)")], mk)
        if n == "door_close_while_out":
            t0 = cmd - DOOR_LEAD
            door = [(t, K.door_fraction(t, t0, K.DM.DOOR_SECONDS)) for t, _, _ in tr]
            ch.panel(c, 2, tm, 0.0, 1.0, f"(door {K.DM.DOOR_SECONDS:.1f} s)",
                     [("s2", door, "door OpenRatio")], [(t0, "leaves start")])
            x0, y0 = ch.frame(c, 2)
            ch.body.append(f'<text x="{x0 - 40}" y="{y0 + 65}" transform="rotate(-90 {x0 - 40} {y0 + 65})" '
                           f'text-anchor="middle">door OpenRatio</text>')
    with open(path, "w") as fh:
        fh.write(ch.svg())
    return path


def graphs_svg(path=None, traj_dir=K.TRAJ_DIR, before_dir=BEFORE_DIR):
    """kvm_motion_graphs.svg: before | after the retune, position and velocity."""
    path = path or os.path.join(OUT, "kvm_motion_graphs.svg")
    tun = K.read_tuning()
    runs = [("open", "Open", "open"), ("close", "Close", "close"), ("fast_stow", "Fast stow", "fast")]
    rows = [("slide", "slide (m)"), ("slide_v", "slide speed (m/s)"), ("fold", "lid fold (deg)"),
            ("fold_v", "lid rate (deg/s)")]
    ch = Chart("KVM motion before and after the retune",
               "Dashed grey: before (drawer omega 11, lid 10 / 10); blue: after (drawer omega 5.2, lid 6.5 open / "
               "8 close, fast 16 / 18). Gate lines: after.",
               [r[1] for r in runs], [r[1] for r in rows], pw=300, ph=120)
    ch.legend([("swb", "before (2d824cc)"), ("sw1", "after (retune)")])
    for c, (n, label, kind) in enumerate(runs):
        after = K.load(os.path.join(traj_dir, n + ".csv"))
        before = K.load(os.path.join(before_dir, n + ".csv"))
        tm = max(_end(after), _end(before))
        mk = moments(after, tun, kind)
        for r, (q, rl) in enumerate(rows):
            a, b = series(after, q), series(before, q)
            vals = [v for _, v in a + b]
            lo, hi = min(0.0, min(vals)), max(vals)
            pa = max(abs(v) for _, v in a)
            pb = max(abs(v) for _, v in b)
            ch.panel(c, r, tm, lo, hi, "", [("before", b, f"before: {rl}, peak {pb:.2f}"),
                                            ("s1", a, f"after: {rl}, peak {pa:.2f}")], mk)
    with open(path, "w") as fh:
        fh.write(ch.svg())
    return path


if __name__ == "__main__":
    print(timing_svg())
    print(graphs_svg())
