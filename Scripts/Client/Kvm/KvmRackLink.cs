// KvmRackLink: what sits in front of the KVM's face. The block in the grid cell
// one step beyond the centre of the KVM's front face was, in a rack, the rack itself (its front and rear 0.25 m layers
// were occupied cells; the leaves are its subparts). Since the placement fix (2026-10-18) only the rear layer is (the
// rear stop): the front one is the slot opening, so the lookup falls back to the rack BESIDE the KVM that contains it
// (KvmRackLink.Lookup.cs). Its DoorComponent, if any, is the door the interlock waits for;
// its block definition and cell bounds give the rack kind and the KVM's slot, and so the motion path. The door counts
// only when the rack has leaves on the side the KVM faces (a rear-facing KVM in a front-door rack is
// free, as with scripts off).
//
// The rack table (kind and leaf sides by definition GUID) is KvmRackTable.cs.
//
// This file is the link's state and its view; the lookup that fills them is KvmRackLink.Lookup.cs.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...):
//   CubeBlockComponent (the KVM block)              Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/CubeBlockComponent.cs:62-64
//   CubeGridComponent, Vector3I (the cached grid and cell)   Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeGrids/CubeGridComponent.cs:1547
//   DoorComponent.DoorState (a synced property: replicated to clients); DoorState {Closing, Opening, Closed, Open}
//                                                   Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors/DoorComponent.cs:173-195, DoorState.cs:6-12
//   DoorClientComponent : DoorComponent (the client rack's door)  Game2.Client/Keen.Game2.Client.WorldObjects.CubeBlocks.Doors/DoorClientComponent.cs:11
#nullable enable
using System;
using DataCenter.Kvm.Core;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors;
using Keen.Game2.Simulation.WorldObjects.CubeGrids;
using Keen.VRage.DCS.Components;
using Keen.VRage.Library.Mathematics;

namespace DataCenter.Kvm;

/// <summary>
/// The KVM's view of the block in front of its face: the door state the interlock reads, and the rack slot that picks
/// the motion path. Client-side and read-only; call <see cref="Update"/> once per frame.
/// </summary>
public sealed partial class KvmRackLink
{
    /// <summary>Seconds between full lookups.</summary>
    public const float ResolveInterval = 0.5f;

    private readonly CubeBlockComponent _kvm;
    private CubeGridComponent? _grid;
    private Vector3I _cell;
    private Entity? _front;
    private CubeBlockComponent? _frontBlock;
    private DoorComponent? _door;
    private float _sinceResolve = float.PositiveInfinity; // the first Update resolves

    /// <summary>The state of the door in front of the face; null when the block there is no door (or there is none).</summary>
    public DoorState? FrontDoorState => _door?.DoorState;

    /// <summary>The door in front as the interlock sees it (<see cref="KvmDoorState"/>; an unknown state reads Closed).</summary>
    public KvmDoorState FrontDoor => _door?.DoorState switch
    {
        null => KvmDoorState.None,
        DoorState.Closing => KvmDoorState.Closing,
        DoorState.Opening => KvmDoorState.Opening,
        DoorState.Closed => KvmDoorState.Closed,
        DoorState.Open => KvmDoorState.Open,
        _ => KvmDoorState.Closed, // never pop through a door whose state is not known
    };

    /// <summary>The block in the cell in front of the face, or the rack that holds the KVM (found beside it), or null.</summary>
    public Entity? FrontBlock => _front;

    /// <summary>The grid cell the front block was found in: in front of the face, or beside the KVM for its rack
    /// (meaningful once resolved on a grid).</summary>
    public Vector3I FrontCell => _cell;

    /// <summary>The Data Center rack in front, by its block definition.</summary>
    public KvmRackKind RackKind { get; private set; }

    /// <summary>The KVM's slot in that rack (1-based), 0 when it is in none.</summary>
    public int Slot { get; private set; }

    /// <summary>The sides of that rack that carry door leaves (generated from dc/doors.py door_sides).</summary>
    public KvmDoorSides DoorSides { get; private set; }

    /// <summary>Which side of the rack the KVM faces: +1 its front, -1 its rear, 0 neither or no rack.</summary>
    public int FaceSide { get; private set; }

    /// <summary>The rack has a door, but no leaves on the KVM's face side: ignored, as with scripts off.</summary>
    public bool DoorOffFace { get; private set; }

    /// <summary>The motion path the slot calls for (see KvmRackSlot).</summary>
    public KvmMotionPath Path => KvmRackSlot.PathFor(RackKind, Slot);

    /// <summary>Full lookups so far (a probe counter).</summary>
    public int Resolves { get; private set; }

    /// <summary>A link for the KVM block <paramref name="kvm"/>.</summary>
    public KvmRackLink(CubeBlockComponent kvm)
    {
        _kvm = kvm ?? throw new ArgumentNullException(nameof(kvm));
    }

    /// <summary>A link for the KVM block entity <paramref name="kvmBlock"/> (it must carry a CubeBlockComponent).</summary>
    public KvmRackLink(Entity kvmBlock)
        : this(BlockOf(kvmBlock))
    {
    }

    /// <summary>Advance the link: a full lookup every <see cref="ResolveInterval"/> s, or at once when the cached block left.</summary>
    public void Update(float dt)
    {
        if (dt > 0f)
            _sinceResolve += dt;

        if (_sinceResolve >= ResolveInterval || !CacheHolds())
            Resolve();
    }

    /// <summary>Forget the cached block (the probe's fault injection; the next <see cref="Update"/> resolves again).</summary>
    internal void Forget()
    {
        Clear();
        _grid = null;
        _sinceResolve = float.PositiveInfinity;
    }

    /// <summary>Make the cache point at <paramref name="stale"/>, a block that is not in the cell (the probe's fault injection).</summary>
    internal void Poison(Entity? stale)
    {
        _front = stale;
        _frontBlock = null;
        _door = null;
        _sinceResolve = 0f; // only the per-frame check can notice
    }
}
