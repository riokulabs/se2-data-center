"""Damage effects (plain Python, no bpy). Which blocks spark, the vanilla 4.0 band they copy, and the
ParticleEffects-type dummies the bands bind to.

Vanilla 4.0 sources (tools/vanilla-ref = the 4.0.0.3151 Mod SDK GameData/Vanilla/Assets, read-only; the band VALUES
are read from these files at build time, never copied into this module):
  cable    CableStraight250's Structural BlockEffects Copy: one band 0 - 0.99, ElectricalDamageMedium 2113ece5 x1 on
           the ParticleEffects dummy: our 27 breakable trays that carry cables (the Empty trays and the Chute: none).
  breaker  CircuitBreaker's Structural BlockEffects Copy: the same band with ElectricalDamageSmall 617b0925 x1: the
           PDU cabinet, the 4 PDU strips and the 4 deco servers (Compute, Storage, Switch, Blank).
  cp25     ControlPanel25's BlockEffects Copy (the KVM's clone source): its band-0 Update (upper 0.99,
           ElectricalDamageSmall x0.3 instead of the 2.4 SmokeSmall: the KVM sparks like vanilla).

Where the effects play (decompiled 4.0.0.3151, tools/decompiled-current):
  * a damage band's LOOPED effect spawns once per model dummy of the band's Dummy type (BlockEffectsComponent.cs:536
    GetDummies), and each instance stops when its dummy's SupportingFracture zone is dead (:474-:496; spawned
    stopped if the zone is already dead, :557-:562);
  * the one-shot death effect (OnBlockDestroyed, BlockEffectsComponent.cs:410-:414) and the fracture effect's
    orientation (:360) take the FIRST dummy of the type (BlockEffectsComponentBase.cs:136-:143 GetDummyTransform ->
    ModelComponentDefinition.cs:435-:445 TryGetDummy: the first in Dummies order) with NO SupportingFracture check.
So the centre ParticleEffects dummy can be supported by a zone (its sparks stop when that zone falls off) and stay
the death-effect origin; the per-zone dummies follow it in the Dummies list, so they never move the death effect.
"""
import json
import os

from . import config

PARTICLE_EFFECTS_TYPE = "e9f28118-a0cf-4c6c-b6ad-2e0719e6cf5a"   # System/DummyTypes/ParticleEffects (the one constant)

SPARK_SOURCES = {
    "cable": "Blocks/CablesSet/Straight/250/CableStraight250_StructuralBlockEffectsComponentDefinition.partialdef",
    "breaker": "Blocks/SmallClutterProps/CircuitBreaker/100/CircuitBreaker_StructuralBlockEffectsComponentDefinition"
               ".partialdef",
    "cp25": "Blocks/ControlPanel/25/ControlPanel25_BlockEffectsComponentDefinition.partialdef",
}
TIMER_EFFECTS = "2cad179b-6b5b-41d9-99ea-e5e44f102485"   # Templates/Blocks/BlockEffects/Timer_BlockEffects... (3 bands)
DECO_SERVERS = ("Compute", "Storage", "Switch", "Blank")
# At most 3 ParticleEffects-type dummies (spark emitters) per block. Vanilla
# CircuitBreaker has 1; the PDU cabinet's 8 zones sparking at once read too busy.
MAX_EMITTERS = 3


def _breakable_tray(spec):
    from . import fracture
    from .tray_lanes import DENSITIES
    return spec.density in DENSITIES and spec.density != "Empty" and fracture.unfractured_reason(spec) is None


def spark_kind(spec):
    """"cable" for a breakable tray with cables, "breaker" for the PDUs and the deco servers, else None."""
    if spec.family == "tray":
        return "cable" if _breakable_tray(spec) else None
    if spec.family in ("pdu_cabinet", "pdu_strip") or (spec.family == "server" and spec.variant in DECO_SERVERS):
        return "breaker"
    return None


def vanilla_effects(kind):
    """The OnDamagedBlockParticleEffect delta of SPARK_SOURCES[kind] (vanilla 4.0, read-only)."""
    with open(os.path.join(config.VANILLA_REF, SPARK_SOURCES[kind]), encoding="utf-8-sig") as f:
        return json.load(f)["$Value"]["Manipulator"]["OnDamagedBlockParticleEffect"]


def vanilla_band(kind):
    """The band Value of that vanilla file's OnDamagedBlockParticleEffect (its one change)."""
    ch = vanilla_effects(kind)["Changed"]
    assert len(ch) == 1, (kind, ch)
    return ch[0]["Value"]


def per_zone(spec):
    """The long blocks get one spark dummy per zone: the trays, the PDU cabinet and the 42U strips."""
    return spec.family in ("tray", "pdu_cabinet") or (spec.family == "pdu_strip" and spec.name.startswith("DC_PDU_Rack42"))


def blender_to_game(p, shift):
    """Blender block frame -> the game model frame (as functional.face_to_game): (x, z, -y) + shift."""
    return (round(p[0] + shift[0], 6), round(p[2] + shift[1], 6), round(-p[1] + shift[2], 6))


def _centre(z):
    return tuple((a + b) / 2 for a, b in zip(z["lo"], z["hi"]))


def _holds(z, p, eps=1e-6):
    return all(lo - eps <= c <= hi + eps for c, lo, hi in zip(p, z["lo"], z["hi"]))


def _lead(zones):
    """The zone of a group that carries its emitter: the largest health share (ties: the earlier id)."""
    return max(zones, key=lambda z: (z.get("health_share", 0), [-ord(c) for c in z["id"]]))


def emitter_zones(zones, centre):
    """The zones (other than the centre one) that get their own spark emitter. Up to MAX_EMITTERS zones: all of them.
    More: the zones are grouped along the block's longest axis (union AABB; ties: x, y, z) into the ones wholly below
    the centre zone's AABB, the ones wholly above it and the rest (the centre group, served by the centre dummy);
    each outer group's emitter goes to its lead zone (_lead). The PDU cabinet: bottom (Fracture_01-04, lead 03),
    middle (05 / 06, the centre), top (07 / 08, lead 07); a Tee / Cross: the centre and the two arms on the long axis."""
    others = [z for z in zones if z["id"] != centre]
    if len(zones) <= MAX_EMITTERS:
        return others
    ext = [max(z["hi"][i] for z in zones) - min(z["lo"][i] for z in zones) for i in range(3)]
    a = max(range(3), key=lambda i: (ext[i], -i))
    c = next(z for z in zones if z["id"] == centre)
    below = [z for z in others if z["hi"][a] <= c["lo"][a] + 1e-6]
    above = [z for z in others if z["lo"][a] >= c["hi"][a] - 1e-6]
    return [_lead(g) for g in (below, above) if g]


def centre_zone(zones):
    """The zone whose hull AABB holds the block centre (Blender origin); of several (a seam through the centre) or
    none, the largest health share (ties: the earlier id)."""
    return _lead([z for z in zones if _holds(z, (0.0, 0.0, 0.0))] or list(zones))["id"]


def zone_dummies(fractured, shift, per_zone, prefer_role=None):
    """[(name, game position, supporting zone id)] of a spark block's ParticleEffects-type dummies: first the centre
    one ("ParticleEffects", at the block centre = shift, supported by centre_zone), then with per_zone one
    "ParticleEffects_<zone>" at the centre of the hull AABB of each emitter_zones zone (at most MAX_EMITTERS in all).
    prefer_role ("hide" for the trays, whose cables are their hide role): a per-zone dummy goes to the centre
    of the zone's box of that role (fractured["role_bounds"][zone][role], Blender [x0, y0, z0, x1, y1, z1]) when the
    zone has one, so it sparks on the cables; else to its hull AABB's centre. The centre dummy never moves."""
    zones = fractured["zones"]
    rb = fractured.get("role_bounds") or {}
    c = centre_zone(zones)
    out = [("ParticleEffects", tuple(shift), c)]

    def at(z):
        box = rb.get(z["id"], {}).get(prefer_role) if prefer_role else None
        return _centre({"lo": box[:3], "hi": box[3:]}) if box else _centre(z)

    if per_zone:
        out += [(f"ParticleEffects_{z['id']}", blender_to_game(at(z), shift), z["id"])
                for z in emitter_zones(zones, c)]
    return out
