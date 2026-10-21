// KvmFrontCell: which grid cell sits directly in front of the KVM's face (for the door interlock).
// The rack link reads the block in that cell and, if it is a door, its state. Since the placement fix
// (2026-10-18) a rack's front zone is free cells (the slot opening), so the link also looks BESIDE the KVM (Beside,
// Contains) for the rack that holds it.
//
// Game APIs: none (game-free). The glue feeds it CubeBlockComponent.AABB (inclusive cell bounds) and the block's
// world forward from IntegerOrientation.Forward / Base6Directions.GetIntVector (see the plan's API table).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>An integer grid vector or cell.</summary>
public readonly struct Int3 : IEquatable<Int3>
{
    /// <summary>Components.</summary>
    public readonly int X, Y, Z;

    /// <summary>A vector.</summary>
    public Int3(int x, int y, int z)
    {
        X = x;
        Y = y;
        Z = z;
    }

    /// <inheritdoc/>
    public bool Equals(Int3 other) => X == other.X && Y == other.Y && Z == other.Z;

    /// <inheritdoc/>
    public override bool Equals(object? obj) => obj is Int3 other && Equals(other);

    /// <inheritdoc/>
    public override int GetHashCode() => (X * 73856093) ^ (Y * 19349663) ^ (Z * 83492791);

    /// <inheritdoc/>
    public override string ToString() => $"({X}, {Y}, {Z})";
}

/// <summary>The cell one step beyond the centre of a block's forward face.</summary>
public static class KvmFrontCell
{
    /// <summary>
    /// The cell in front of the face of the block occupying cells <paramref name="aabbMin"/>..<paramref name="aabbMax"/>
    /// (inclusive; either order) that looks along <paramref name="forward"/>. Across the face, the centre rounds toward
    /// min on even widths. A forward that is not a unit axis uses its dominant axis (ties: X, then Y); a zero forward
    /// gives the block's centre cell, which is inside the block and so never reads as a door.
    /// </summary>
    public static Int3 Of(Int3 aabbMin, Int3 aabbMax, Int3 forward)
    {
        int minX = Math.Min(aabbMin.X, aabbMax.X), maxX = Math.Max(aabbMin.X, aabbMax.X);
        int minY = Math.Min(aabbMin.Y, aabbMax.Y), maxY = Math.Max(aabbMin.Y, aabbMax.Y);
        int minZ = Math.Min(aabbMin.Z, aabbMax.Z), maxZ = Math.Max(aabbMin.Z, aabbMax.Z);

        int x = Centre(minX, maxX), y = Centre(minY, maxY), z = Centre(minZ, maxZ);
        int ax = Math.Abs(forward.X), ay = Math.Abs(forward.Y), az = Math.Abs(forward.Z);
        if (ax == 0 && ay == 0 && az == 0)
            return new Int3(x, y, z);

        if (ax >= ay && ax >= az)
            x = forward.X > 0 ? maxX + 1 : minX - 1;
        else if (ay >= az)
            y = forward.Y > 0 ? maxY + 1 : minY - 1;
        else
            z = forward.Z > 0 ? maxZ + 1 : minZ - 1;

        return new Int3(x, y, z);
    }

    /// <summary>The number of <see cref="Beside"/> cells.</summary>
    public const int BesideCount = 4;

    /// <summary>
    /// The <paramref name="k"/>-th (0..3) cell one step beyond a SIDE face of the block (the four faces across
    /// <paramref name="forward"/>, in the order -a, +a, -b, +b of the two other axes in x, y, z order), at the centre
    /// of that face (rounding toward min, as <see cref="Of"/>). In a rack these are the rack's own cells (the side
    /// columns, the plinth or tray, or the rack's cells around a neighbouring slot): the placement fix (2026-10-18)
    /// freed the rack's front zone, so the cell in front of a front-facing KVM is no longer the rack's.
    /// </summary>
    public static Int3 Beside(Int3 aabbMin, Int3 aabbMax, Int3 forward, int k)
    {
        if (k < 0 || k >= BesideCount)
            throw new ArgumentOutOfRangeException(nameof(k));

        int minX = Math.Min(aabbMin.X, aabbMax.X), maxX = Math.Max(aabbMin.X, aabbMax.X);
        int minY = Math.Min(aabbMin.Y, aabbMax.Y), maxY = Math.Max(aabbMin.Y, aabbMax.Y);
        int minZ = Math.Min(aabbMin.Z, aabbMax.Z), maxZ = Math.Max(aabbMin.Z, aabbMax.Z);
        int x = Centre(minX, maxX), y = Centre(minY, maxY), z = Centre(minZ, maxZ);

        int ax = Math.Abs(forward.X), ay = Math.Abs(forward.Y), az = Math.Abs(forward.Z);
        int along = ax >= ay && ax >= az ? 0 : ay >= az ? 1 : 2;   // Of's dominant axis (ties: X, then Y)
        int a = along == 0 ? 1 : 0;           // the first other axis
        int b = along == 2 ? 1 : 2;           // the second
        int axis = k < 2 ? a : b;
        bool plus = (k & 1) == 1;
        if (axis == 0)
            x = plus ? maxX + 1 : minX - 1;
        else if (axis == 1)
            y = plus ? maxY + 1 : minY - 1;
        else
            z = plus ? maxZ + 1 : minZ - 1;

        return new Int3(x, y, z);
    }

    /// <summary>The cell box <paramref name="innerMin"/>..<paramref name="innerMax"/> lies inside
    /// <paramref name="outerMin"/>..<paramref name="outerMax"/> (inclusive bounds, either order).</summary>
    public static bool Contains(Int3 outerMin, Int3 outerMax, Int3 innerMin, Int3 innerMax)
        => Within(outerMin.X, outerMax.X, innerMin.X, innerMax.X)
           && Within(outerMin.Y, outerMax.Y, innerMin.Y, innerMax.Y)
           && Within(outerMin.Z, outerMax.Z, innerMin.Z, innerMax.Z);

    private static bool Within(int o0, int o1, int i0, int i1)
        => Math.Min(i0, i1) >= Math.Min(o0, o1) && Math.Max(i0, i1) <= Math.Max(o0, o1);

    /// <summary>The middle cell, rounding toward min on even widths (floor, also for negative cells).</summary>
    private static int Centre(int min, int max) => min + (max - min) / 2;
}
