"""Plan 4 Task 7: what the KVM motion previews render, and for how long (bpy-free, so the tests can read it).

Each Run is a motion sampled from the CoreTests 240 Hz trajectories (or, for the data-only path of Ruling P4-12,
kvm_motion.data_only_trajectory), with the rack door's OpenRatio on the same clock; PLAN lists the views each run
renders. dc/preview_scripts.py renders them; Tests/test_plan4_previews.py checks the videos against Run.frames.
"""
import bisect
import os

from . import dims as DM
from . import kvm_charts as KC
from . import kvm_motion as K
from . import subparts as S

FPS = 60
SLOT, TOP = 5, 8                                  # the KVM's slot; the full rack's top slot (P4-12)

class Run:
    """A motion to render: [(t, slide, fold)] at 240 Hz, a label, the door's OpenRatio over time."""

    def __init__(self, name, traj, label, door=None, slot=SLOT):
        self.name, self.traj, self.label, self.slot = name, traj, label, slot
        self.door = door or (lambda t: 1.0)
        self.duration = traj[-1][0]
        self.frames = int(round(self.duration * FPS)) + 1
        self._times = [r[0] for r in traj]
        if any(b <= a for a, b in zip(self._times, self._times[1:])):
            raise ValueError(f"{name}: trajectory sample times must strictly increase")

    def at(self, t):
        """(slide, fold) at time t, interpolated linearly in time between the bracketing samples (any spacing; the
        sample times must increase)."""
        tr = self.traj
        if t <= tr[0][0]:
            return tr[0][1], tr[0][2]
        if t >= tr[-1][0]:
            return tr[-1][1], tr[-1][2]
        i = bisect.bisect_right(self._times, t) - 1          # tr[i][0] <= t < tr[i + 1][0]
        a, b = tr[i], tr[i + 1]
        k = (t - a[0]) / (b[0] - a[0])
        return a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k


def runs():
    """Every rendered motion, by name."""
    out = {}
    for name, label in (("open", "open"), ("close", "close"), ("reverse_mid_fold", "open, switched off mid-fold"),
                        ("reverse_mid_slide", "open, switched off mid-slide")):
        out[name] = Run(name, K.load(name), label)
    path = os.path.join(K.TRAJ_DIR, "door_close_while_out.csv")
    cmd = K.first_command(path, "FastStow")
    t0 = cmd - KC.DOOR_LEAD
    out["door_close_while_out"] = Run("door_close_while_out", K.load(path),
                                      f"door closes while out: fast stow at t = {cmd:.2f} s",
                                      door=lambda t: K.door_fraction(t, t0, DM.DOOR_SECONDS))
    # P4-12: the top slot of a full rack runs the vanilla simultaneous motion (open, a hold, close)
    top = K.data_only_trajectory([(0.25, 0.0, 1.0), (0.6, 1.0, 0.0)])
    top += [(top[-1][0] + (i + 1) / 240, 0.0, 0.0) for i in range(60)]
    out["data_only_top"] = Run("data_only_top", top, "top slot: the data-only path (P4-12)", slot=TOP)
    # the data-only open in slot 5, as long as the scripted open: the left half of the side-by-side
    n = len(out["open"].traj)
    do = [(i / 240, min(1.0, i / 240 / S.POP_TIME), min(1.0, i / 240 / S.POP_TIME)) for i in range(n)]
    out["dataonly_open"] = Run("dataonly_open", do, "data-only (vanilla): slide and fold together, 1.0 s")
    return out


# which views each run renders (the brief's four in all three views; the rest where they earn their place)
PLAN = {
    "open": ("side", "3q", "first_person", "orbit"),
    "close": ("side", "3q", "first_person"),
    "door_close_while_out": ("side", "3q", "first_person", "top"),
    "reverse_mid_fold": ("side", "3q", "first_person"),
    "reverse_mid_slide": ("3q",),
    "data_only_top": ("3q", "side"),
    "dataonly_open": ("3q",),
}
