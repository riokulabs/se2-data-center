// KvmRackSlot: which rack slot a KVM sits in, and which motion runs there.
// The runtime twin of dc/kvm_motion.motion_path_for_slot: the data-only path exactly in the TOP slot of a
// FULL rack (the 42U racks carry the containment rail and roof over their tray band, front and back), the
// sequenced path everywhere else, the 24U half rack's top slot included. Facing plays no part.
// Tests/CoreTests dumps this rule for every rack and slot (routing.json), and Tests/test_kvm_runtime.py checks the
// dump against the Python rule, so the two cannot drift apart.
//
// It also holds the face-side rule: a rack's door guards only the side its leaves are on (front and/or
// rear, from dc/doors.py door_sides, generated into DcGuids.Rack*DoorSides), so a KVM facing a side without leaves is
// free, as it is with scripts off.
//
// Game APIs: none (game-free). The glue feeds it the cell bounds of the rack and of the KVM (CubeBlockComponent.AABB,
// inclusive), the rack's world up and forward and the KVM's world forward (block orientations as grid vectors).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>The Data Center rack a KVM sits in, by its block definition.</summary>
public enum KvmRackKind
{
    /// <summary>Not in a Data Center rack (standalone, another block in front, or not known yet).</summary>
    None,

    /// <summary>A 42U rack: 10 cells high (plinth, 8 slots, the top tray band); containment sits above it.</summary>
    Full,

    /// <summary>A 24U rack: 5 cells high (plinth, 4 slots); nothing sits above its top slot.</summary>
    Half,
}

/// <summary>The sides of a rack that carry door leaves (the bits of DcGuids.Rack*DoorSides).</summary>
[Flags]
public enum KvmDoorSides
{
    /// <summary>No leaves (an open rack).</summary>
    None = 0,

    /// <summary>Leaves on the rack's front: its block Forward (the data's +y, door side +1).</summary>
    Front = 1 << 0,

    /// <summary>Leaves on the rack's rear (door side -1).</summary>
    Rear = 1 << 1,
}

/// <summary>The rack slot rule (which motion runs where) and the face-side rule (which sides a door guards).</summary>
public static class KvmRackSlot
{
    /// <summary>The height of a rack in cells along its up axis (0 for <see cref="KvmRackKind.None"/>).</summary>
    public static int Cells(KvmRackKind kind) => kind == KvmRackKind.Full ? 10 : kind == KvmRackKind.Half ? 5 : 0;

    /// <summary>The number of server slots (one cell each, 6U), numbered 1.. from the slot above the plinth.</summary>
    public static int SlotCount(KvmRackKind kind) => kind == KvmRackKind.Full ? 8 : kind == KvmRackKind.Half ? 4 : 0;

    /// <summary>
    /// The highest slot (1-based, counted up from the plinth) that the KVM occupying cells
    /// <paramref name="kvmMin"/>..<paramref name="kvmMax"/> fills in the rack occupying
    /// <paramref name="rackMin"/>..<paramref name="rackMax"/> (inclusive, either order), whose up is
    /// <paramref name="rackUp"/>. 0 when it is in no slot: the KVM is not inside the rack's box, the rack's height does
    /// not match its kind, its up is not a unit axis, or the KVM reaches the plinth or the tray band.
    /// </summary>
    public static int SlotOf(KvmRackKind kind, Int3 rackMin, Int3 rackMax, Int3 rackUp, Int3 kvmMin, Int3 kvmMax)
    {
        int axis = UnitAxis(rackUp);
        if (axis < 0 || kind == KvmRackKind.None)
            return 0;

        for (int a = 0; a < 3; a++)
        {
            int rLo = Math.Min(Get(rackMin, a), Get(rackMax, a)), rHi = Math.Max(Get(rackMin, a), Get(rackMax, a));
            int kLo = Math.Min(Get(kvmMin, a), Get(kvmMax, a)), kHi = Math.Max(Get(kvmMin, a), Get(kvmMax, a));
            if (kLo < rLo || kHi > rHi)
                return 0;
        }

        int lo = Math.Min(Get(rackMin, axis), Get(rackMax, axis)), hi = Math.Max(Get(rackMin, axis), Get(rackMax, axis));
        if (hi - lo + 1 != Cells(kind))
            return 0;

        int kvmLo = Math.Min(Get(kvmMin, axis), Get(kvmMax, axis)), kvmHi = Math.Max(Get(kvmMin, axis), Get(kvmMax, axis));
        bool upPositive = Get(rackUp, axis) > 0;
        int bottom = upPositive ? kvmLo - lo : hi - kvmHi; // cells above the rack's floor; the plinth is 0
        int top = upPositive ? kvmHi - lo : hi - kvmLo;
        return bottom >= 1 && top <= SlotCount(kind) ? top : 0;
    }

    /// <summary>The motion for a KVM in <paramref name="slot"/> (0 = in no slot) of a <paramref name="kind"/> rack.</summary>
    public static KvmMotionPath PathFor(KvmRackKind kind, int slot)
        => kind == KvmRackKind.Full && slot == SlotCount(KvmRackKind.Full) ? KvmMotionPath.DataOnly : KvmMotionPath.Sequenced;

    /// <summary>
    /// Which side of the rack the KVM's face looks out of: +1 the rack's front (the KVM's forward is the rack's),
    /// -1 its rear (opposite), 0 neither (a sideways KVM, or a forward that is not a unit axis).
    /// </summary>
    public static int FaceSide(Int3 kvmForward, Int3 rackForward)
    {
        if (UnitAxis(kvmForward) < 0 || UnitAxis(rackForward) < 0)
            return 0;

        if (kvmForward.Equals(rackForward))
            return 1;

        return kvmForward.Equals(new Int3(-rackForward.X, -rackForward.Y, -rackForward.Z)) ? -1 : 0;
    }

    /// <summary>
    /// True when the rack's door can stand in front of a KVM face on <paramref name="faceSide"/>: the rack has leaves
    /// on that side. An unknown side (0) is guarded by any door: never pop on doubt.
    /// </summary>
    public static bool DoorGuardsFace(KvmDoorSides sides, int faceSide)
    {
        if (faceSide == 0)
            return sides != KvmDoorSides.None;

        return (sides & (faceSide > 0 ? KvmDoorSides.Front : KvmDoorSides.Rear)) != 0;
    }

    /// <summary>0, 1 or 2 for a unit vector along X, Y or Z (either sign); -1 for anything else.</summary>
    private static int UnitAxis(Int3 v)
    {
        int ax = Math.Abs(v.X), ay = Math.Abs(v.Y), az = Math.Abs(v.Z);
        if (ax == 1 && ay == 0 && az == 0)
            return 0;

        if (ax == 0 && ay == 1 && az == 0)
            return 1;

        return ax == 0 && ay == 0 && az == 1 ? 2 : -1;
    }

    private static int Get(Int3 v, int axis) => axis == 0 ? v.X : axis == 1 ? v.Y : v.Z;
}
