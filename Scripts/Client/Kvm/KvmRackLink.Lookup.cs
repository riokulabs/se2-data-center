// KvmRackLink.Lookup: how the rack link finds the block in front of the KVM's face, or (the rack's front zone is free
// cells, the slot opening) the rack beside it that holds it (see KvmRackLink.cs for what it
// exposes). The full lookup runs every ResolveInterval seconds. Every frame a cheap check (the KVM's grid, the block
// in the cached cell, that block's own CubeBlockComponent) re-resolves at once when the cached block has gone: a rack
// ground away, a grid split, or a pooled entity reused for another block (entities are stubs and get reused, so a
// held reference alone proves nothing).
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   CubeBlockComponent.Grid / AABB (inclusive cells) / BlockOrientation / Definition
//                                                   Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/CubeBlockComponent.cs:4001, 4007, 4009, 4040
//   CubeBlockComponent's default tag "GridBlockComponent"                                                  ibid. :62-64
//   CubeGridComponent.GetBlock(Vector3I)            Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeGrids/CubeGridComponent.cs:1547-1550
//   IntegerOrientation.Forward / Up                 VRage.Library/Keen.VRage.Library.Mathematics/IntegerOrientation.cs:750, 756
//   Base6Directions.GetIntVector(Direction)         VRage.Library/Keen.VRage.Library.Mathematics/Base6Directions.cs:240
//   Entity.Has<T>(out T, conditional) (by type, whatever the tag; the conditional is required for a Component type,
//   the assertion at :158)                          VRage.DCS/Keen.VRage.DCS.Components/Entity.cs:158-170 [2.4: 156-168],
//                                                   Game2.Client/.../CameraSystems/Modes/ThirdPersonCameraComponent.cs:295 (the vanilla idiom)
//   Definition.Guid, read through (Definition)(object) (comparing a CubeBlockDefinition is CS0012)
//                                                   VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343
//   A static method group converts to a cached delegate (C# 11; the game compiles with LanguageVersion.Latest)
//                                                   VRage.Scripting/Keen.VRage.Scripting.Compilation/CompilationDescriptorDefaults.cs:18
#nullable enable
using System;
using DataCenter.Kvm.Core;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors;
using Keen.Game2.Simulation.WorldObjects.CubeGrids;
using Keen.VRage.DCS.Components;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Mathematics;

namespace DataCenter.Kvm;

/// <remarks>This part resolves the front block and keeps the cache honest.</remarks>
public sealed partial class KvmRackLink
{
    /// <summary>The block in the cached cell is still the cached block, on the KVM's current grid.</summary>
    private bool CacheHolds()
    {
        CubeGridComponent? grid = _kvm.Grid;
        if (grid == null || !ReferenceEquals(grid, _grid))
            return false;

        Entity? now = grid.GetBlock(_cell);
        if (!ReferenceEquals(now, _front))
            return false;

        if (now == null)
            return true;

        return now.Has(out CubeBlockComponent? block, AnyBlock) && ReferenceEquals(block, _frontBlock);
    }

    private void Resolve()
    {
        _sinceResolve = 0f;
        Resolves++;
        Clear();

        CubeGridComponent? grid = _kvm.Grid;
        _grid = grid;
        if (grid == null)
            return; // not on a grid (a placement preview, or mid-split): no door, no rack

        BoundingBoxI box = _kvm.AABB;
        Int3 cell = KvmFrontCell.Of(ToInt3(box.Min), ToInt3(box.Max), ToInt3(_kvm.BlockOrientation.Forward.GetIntVector()));
        _cell = new Vector3I(cell.X, cell.Y, cell.Z);

        Entity? front = grid.GetBlock(_cell);
        if (!IsRack(front))
        {
            // The rack's front zone is free cells (the slot opening the block placer
            // aims through), so in front of a front-facing KVM there is no block, or one built into the opening.
            // The rack that holds the KVM is beside it (its side columns, plinth or tray): take it when its cell box
            // contains the KVM's. (A rear-facing KVM still finds the rack in front: the rear stop's cells.)
            Int3 kmin = ToInt3(box.Min), kmax = ToInt3(box.Max), fwd = ToInt3(_kvm.BlockOrientation.Forward.GetIntVector());
            for (int k = 0; k < KvmFrontCell.BesideCount; k++)
            {
                Int3 c = KvmFrontCell.Beside(kmin, kmax, fwd, k);
                var at = new Vector3I(c.X, c.Y, c.Z);
                Entity? beside = grid.GetBlock(at);
                if (!IsRack(beside) || !beside!.Has(out CubeBlockComponent? holder, AnyBlock) || holder == null)
                    continue;

                if (KvmFrontCell.Contains(ToInt3(holder.AABB.Min), ToInt3(holder.AABB.Max), kmin, kmax))
                {
                    front = beside;
                    _cell = at;
                    break;
                }
            }
        }

        _front = front;
        if (front == null)
            return;

        front.Has(out _frontBlock, AnyBlock);
        front.Has(out _door, AnyDoor);
        if (_frontBlock == null)
            return;

        Guid rackDefinition = ((Definition)(object)_frontBlock.Definition).Guid;
        RackKind = KvmRackTable.KindOf(rackDefinition);
        if (RackKind == KvmRackKind.None)
            return;

        BoundingBoxI rack = _frontBlock.AABB;
        Slot = KvmRackSlot.SlotOf(RackKind, ToInt3(rack.Min), ToInt3(rack.Max), ToInt3(_frontBlock.BlockOrientation.Up.GetIntVector()),
            ToInt3(box.Min), ToInt3(box.Max));

        // A rack's door guards only the sides its leaves are on. The data's front (+y, door side +1) is
        // the block's Forward, the same convention that makes the KVM's own Forward its face.
        DoorSides = KvmRackTable.DoorSidesOf(rackDefinition);
        FaceSide = KvmRackSlot.FaceSide(ToInt3(_kvm.BlockOrientation.Forward.GetIntVector()), ToInt3(_frontBlock.BlockOrientation.Forward.GetIntVector()));
        if (_door != null && !KvmRackSlot.DoorGuardsFace(DoorSides, FaceSide))
        {
            _door = null;
            DoorOffFace = true;
        }
    }

    private void Clear()
    {
        _front = null;
        _frontBlock = null;
        _door = null;
        RackKind = KvmRackKind.None;
        Slot = 0;
        DoorSides = KvmDoorSides.None;
        FaceSide = 0;
        DoorOffFace = false;
    }

    private static CubeBlockComponent BlockOf(Entity kvmBlock)
    {
        CubeBlockComponent? block = null;
        if (kvmBlock == null || !kvmBlock.Has(out block, AnyBlock) || block == null)
            throw new ArgumentException("the KVM entity has no CubeBlockComponent", nameof(kvmBlock));

        return block;
    }

    private static Int3 ToInt3(Vector3I v) => new Int3(v.X, v.Y, v.Z);

    /// <summary>The entity is a Data Center rack block (by its block definition, <see cref="KvmRackTable"/>).</summary>
    private static bool IsRack(Entity? e)
    {
        if (e == null || !e.Has(out CubeBlockComponent? block, AnyBlock) || block == null)
            return false;

        return KvmRackTable.KindOf(((Definition)(object)block.Definition).Guid) != KvmRackKind.None;
    }

    // Entity.Has<T> asserts "reserved for interfaces or with conditional" for a Component type passed without a
    // conditional (Entity.cs:160 [2.4: 158]; VRage.DCS is built with FEATURE_ASSERTIONS, so it fires in shipping builds). Vanilla
    // passes an always-true one (ThirdPersonCameraComponent.cs:295); these are passed as method groups, which the
    // compiler caches in a delegate of its own: no allocation per call, and no static state of ours.
    private static bool AnyBlock(CubeBlockComponent block) => true;

    private static bool AnyDoor(DoorComponent door) => true;
}
