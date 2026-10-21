// KvmSequencerComponent: the scripted KVM's brain, a client-only component on the KVM block's client entity.
// KvmInjector adds it to the KVM's client prefab at load, with scripts on only;
// client entities are never saved, so a world never holds this type (the save-safety rule).
//
// Once per frame, before the rigid animations prepare, it reads the world (Working, the door in front, the rack slot)
// into the game-free KvmSequencerCore, which owns every decision (Core/KvmSequencerCore.cs, Tests/CoreTests); the
// part drivers (KvmPartDrivers.cs) then apply its pose in OnUpdateRigidAnimation. Nothing it does reaches the
// server: each client animates its own copy from replicated state (Working, DoorState).
//
// Multiplayer with mixed script settings: the server never runs this (client entities only), and nothing here is
// replicated. A client with scripts sees the sequenced, door-aware motion; a client without sees the data-only vanilla
// motion of the same block, and a dedicated server is unaffected either way. The two views can differ for a moment
// (e.g. the scripted KVM waits for the door, the vanilla one pokes through it), which is cosmetic: the KVM has no
// collision on its subparts and no gameplay effect.
//
// Defensive: every entry point catches; a fault is logged once per site; at MaxFaults the core stops sequencing and
// snaps to the wanted end pose every frame (the data-only look). If the world cannot be read at all, the inputs fall
// back to Working only, the data-only behaviour.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...):
//   [Component] PowerableBlockComponent (a FunctionalBlockComponent, a CubeBlockComponent); Working (synced)
//                                                   Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/PowerableBlockComponent.cs:41,
//                                                   FunctionalBlockComponent.cs:36, 366
//   [Service] IGameTime.DeltaTime (zero while paused)  VRage.Core.Game/Keen.VRage.Core.Game.GameSystems.GameTimes/IGameTime.cs:12-24
//   IInSceneListener.OnAddedToScene / OnBeforeRemovedFromScene   VRage.Core.Game/Keen.VRage.Core.Game.Systems/IInSceneListener.cs
//   JobGroup, [After] / [Before]; OnStartRigidAnimation -> OnPrepareRigidAnimation -> OnUpdateRigidAnimation
//                                                   VRage.Core.Game/.../RigidAnimations/OnStartRigidAnimation.cs, OnPrepareRigidAnimation.cs:8-10,
//                                                   OnUpdateRigidAnimation.cs:8-10
#nullable enable
using System;
using DataCenter.Kvm.Core;
using DataCenter.Shared;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks;
using Keen.VRage.Core.Game.GameSystems.GameTimes;
using Keen.VRage.Core.Game.GameSystems.RigidAnimations;
using Keen.VRage.Core.Game.Systems;
using Keen.VRage.DCS.Annotations;
using Keen.VRage.DCS.Components;
using Keen.VRage.Library.Reflection.DependencyInjections;

namespace DataCenter.Kvm;

/// <summary>
/// Sequences the KVM's drawer and screen: slide, a beat, fold; fold first on the way back; a fast stow when the rack
/// door in front starts closing; the settled pose at once when the block enters the scene.
/// </summary>
public sealed partial class KvmSequencerComponent : Component, IInSceneListener
{
    [Component]
    private PowerableBlockComponent _block = null!;

    [Service]
    private IGameTime _time = null!;

    private readonly KvmSequencerCore _core = new KvmSequencerCore(KvmMotionTuning.Default);
    private KvmRackLink? _link;
    private bool _inScene;
    private bool _worldUnreadable;

    /// <summary>The pose the part drivers apply this frame.</summary>
    public KvmPose Pose => _core.Pose;

    /// <summary>The target the rule chose this frame.</summary>
    public KvmTarget Target => _core.Target;

    /// <summary>The motion path in use (see KvmRackSlot).</summary>
    public KvmMotionPath Path => _core.Path;

    /// <summary>Stopped sequencing after <see cref="KvmSequencerCore.MaxFaults"/> faults; snaps to its end pose.</summary>
    public bool Faulted => _core.Faulted;

    /// <summary>The motion tuning (the parts read the lid's axis sign from it).</summary>
    public KvmMotionTuning Tuning => KvmMotionTuning.Default;

    /// <summary>The door and rack view, or null before the block entered the scene.</summary>
    public KvmRackLink? RackLink => _link;

    /// <summary>The decision core (read by the in-game probe).</summary>
    internal KvmSequencerCore Core => _core;

    void IInSceneListener.OnAddedToScene()
    {
        try
        {
            _inScene = true;
            _core.EnterScene();
            _link = new KvmRackLink(_block);
        }
        catch (Exception ex)
        {
            Fault("scene", ex);
        }
    }

    void IInSceneListener.OnBeforeRemovedFromScene()
    {
        _inScene = false;
        _link = null;
    }

    /// <summary>A subpart spawned (called by the part drivers): snap inside the scene-entry window, else restart stowed.</summary>
    public void NotifyPartSpawned()
    {
        try
        {
            _core.PartSpawned();
        }
        catch (Exception ex)
        {
            Fault("spawn", ex);
        }
    }

    /// <summary>The sequencer's frame: after the rigid animations start, before they prepare and update.</summary>
    [After(typeof(OnStartRigidAnimation))]
    [Before(typeof(OnPrepareRigidAnimation))]
    public class KvmSequenceUpdate : JobGroup
    {
    }

    [KvmSequenceUpdate]
    [MustHave(typeof(KvmSequencerComponent))]
    private static void Update(KvmSequencerComponent s)
    {
        try
        {
            s.Tick();
        }
        catch (Exception ex)
        {
            s.Fault("update", ex);
        }
    }

    private void Tick()
    {
        if (!_inScene)
            return;

        float dt = (float)_time.DeltaTime.TotalSeconds;
        KvmInputs inputs;
        if (_worldUnreadable)
        {
            inputs = KvmInputs.DataOnly(WorkingOrFalse());
        }
        else
        {
            try
            {
                inputs = ReadWorld(dt);
            }
            catch (Exception ex)
            {
                Fault("read", ex);
                _worldUnreadable = _core.Faulted; // once faulted, stop paying for an exception per frame
                inputs = KvmInputs.DataOnly(WorkingOrFalse());
            }
        }

        _core.Update(dt, inputs);
    }

    /// <remarks>
    /// Runs inside the <see cref="KvmSequenceUpdate"/> job and reads OTHER entities, undeclared to the scheduler: the
    /// grid's block map and the rack's DoorComponent (KvmRackLink). No vanilla job in this window writes either (the
    /// door's state changes in DoorUpdateSystem's groups, the grid's map on block add/remove), so the reads are
    /// stable; re-check that if a game update moves those systems.
    /// </remarks>
    private KvmInputs ReadWorld(float dt)
    {
        bool working = _block.Working;
        KvmRackLink link = _link ??= new KvmRackLink(_block); // made at the scene add; here only if that failed
        link.Update(dt);
        return new KvmInputs(working, link.FrontDoor, link.Path);
    }

    /// <summary>Working, read without a way to throw: the getter returns a field (FunctionalBlockComponent.cs:366), so
    /// only a missing block component could fail, and that reads as not Working.</summary>
    private bool WorkingOrFalse() => _block is { } block && block.Working;

    private void Fault(string site, Exception ex)
    {
        DcLog.Once("kvm-sequencer:" + site, $"KVM sequencer: {site} threw {ex.GetType().Name}: {ex.Message}");
        if (_core.ReportFault())
            DcLog.Once("kvm-sequencer:faulted", $"KVM sequencer: {KvmSequencerCore.MaxFaults} faults: this KVM stops sequencing and shows its end pose (the data-only look).");
    }
}
