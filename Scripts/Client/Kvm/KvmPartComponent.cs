// KvmPartComponent: the base of the KVM's subpart drivers. With scripts on,
// KvmInjector swaps the drawer's TranslationAnimationComponent for KvmDrawerPart and the screen's
// RotationAnimationComponent for KvmScreenPart (KvmPartDrivers.cs), at the same composite index with the same
// component id and the same (null) object builder. Each driver writes an absolute pose every frame: its rest
// transform (captured when it spawns) moved by the sequencer's pose.
//
// Fallbacks: a part that finds no sequencer above it writes its rest pose once and keeps looking (every 30 frames);
// one that faulted MaxFaults times writes its rest pose once and then leaves the transform alone. Neither throws out
// of its job. The only allocation on the job's path is the fault log line, at most MaxFaults times per part.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   IInSceneListener.OnAddedToScene / OnBeforeRemovedFromScene   VRage.Core.Game/Keen.VRage.Core.Game.Systems/IInSceneListener.cs
//   ChildTransformComponent.ChildTransform (the spawn pose)      VRage.Core.Game/Keen.VRage.Core.Game.Components/ChildTransformComponent.cs:12-21
//   Entity.TryGet<T> (by default tag)                             VRage.DCS/Keen.VRage.DCS.Components/Entity.cs:135 [2.4: 133]
//   EntityParentFunctions.GetClosestParentWith<T>                 VRage.Core.Game/Keen.VRage.Core.Game.Data/EntityParentFunctions.cs:44-51
//   HierarchyComponent: ParentData is set before the scene add   VRage.Core.Game/Keen.VRage.Core.Game.Components/HierarchyComponent.cs:134-139
//   ConditionalSubPartsComponent: the drawer is a child of the block (HierarchyComponent.AddChild), the screen a child
//   of the drawer                                                 Game2.Client/Keen.Game2.Client.WorldObjects.CubeBlocks.Effects/ConditionalSubPartsComponent.cs:178-215
//   RelativeTransform                                             VRage.Core/Keen.VRage.Core/RelativeTransform.cs:610, 615
#nullable enable
using System;
using DataCenter.Kvm.Core;
using DataCenter.Shared;
using Keen.VRage.Core;
using Keen.VRage.Core.Game.Components;
using Keen.VRage.Core.Game.Data;
using Keen.VRage.Core.Game.Systems;
using Keen.VRage.DCS.Components;

namespace DataCenter.Kvm;

/// <summary>
/// A KVM subpart driver: captures its rest transform when it spawns, tells the sequencer, and every frame writes
/// rest moved by the sequencer's pose. Faults are counted; at <see cref="KvmSequencerCore.MaxFaults"/> the part writes
/// its rest pose once and stops.
/// </summary>
public abstract partial class KvmPartComponent : Component, IInSceneListener
{
    /// <summary>Frames between lookups while no sequencer is found (one should be from the spawn on: ParentData is set
    /// before the scene add, HierarchyComponent.cs:134-139; this only keeps a surprise from freezing the part).</summary>
    private const int LookupEvery = 30;

    private KvmSequencerComponent? _sequencer;
    private RelativeTransform _rest;
    private KvmPose _applied;
    private int _faults;
    private bool _hasRest;
    private bool _hasApplied;
    private int _lookupIn;
    private bool _faulted;
    private bool _restWritten;

    /// <summary>The spawn transform the pose is applied to (meaningful once <see cref="HasRest"/>).</summary>
    public RelativeTransform Rest => _rest;

    /// <summary>The rest transform has been captured.</summary>
    public bool HasRest => _hasRest;

    /// <summary>The sequencer driving this part, or null (then the part rests).</summary>
    public KvmSequencerComponent? Sequencer => _sequencer;

    /// <summary>Stopped after <see cref="KvmSequencerCore.MaxFaults"/> faults.</summary>
    public bool Faulted => _faulted;

    /// <summary>Faults counted so far.</summary>
    public int Faults => _faults;

    /// <summary>The pose last written to the transform.</summary>
    public KvmPose AppliedPose => _applied;

    void IInSceneListener.OnAddedToScene()
    {
        try
        {
            // A fresh subpart sits at its dummy: the rest pose. Only the first time: an entity that leaves the scene
            // and comes back (streaming) still holds the last pose this part wrote, which is not a rest pose.
            ChildTransformComponent? child = _hasRest ? null : Entity.TryGet<ChildTransformComponent>();
            if (child != null)
            {
                _rest = child.ChildTransform;
                _hasRest = true;
            }

            _sequencer = FindSequencer();
            _lookupIn = LookupEvery;
            _sequencer?.NotifyPartSpawned();
        }
        catch (Exception ex)
        {
            Fault("spawn", ex);
        }
    }

    void IInSceneListener.OnBeforeRemovedFromScene()
    {
        _sequencer = null;
        _lookupIn = 0;
        _hasApplied = false;
    }

    /// <summary>
    /// Writes the pose for this frame into <paramref name="transform"/>; called by the part's rigid job, which catches
    /// whatever this throws and counts it as a fault (<see cref="Fault"/>).
    /// </summary>
    protected void Drive(ref RelativeTransform transform)
    {
        if (_faulted)
        {
            WriteRestOnce(ref transform);
            return;
        }

        if (!_hasRest)
        {
            _rest = transform; // no ChildTransformComponent at spawn: the first transform the job sees is the rest
            _hasRest = true;
        }

        if (_sequencer == null && --_lookupIn <= 0)
        {
            _sequencer = FindSequencer();
            _lookupIn = LookupEvery;
            if (_sequencer != null)
                _restWritten = false;
        }

        KvmSequencerComponent? sequencer = _sequencer;
        if (sequencer == null)
        {
            WriteRestOnce(ref transform); // and keep looking, every LookupEvery frames
            return;
        }

        KvmPose pose = sequencer.Pose;
        if (_hasApplied && pose.Slide == _applied.Slide && pose.Fold == _applied.Fold)
            return; // nothing moved: leave the transform as it is

        Pose(ref transform, in _rest, pose, sequencer.Tuning);
        _applied = pose;
        _hasApplied = true;
    }

    /// <summary>Counts a fault of this part (logged once per part kind and site); at the budget the part rests.</summary>
    protected void Fault(string site, Exception ex)
    {
        string kind = GetType().Name;
        DcLog.Once($"kvm-part:{kind}:{site}", $"KVM {kind}: {site} threw {ex.GetType().Name}: {ex.Message}");
        if (_faulted || ++_faults < KvmSequencerCore.MaxFaults)
            return;

        _faulted = true;
        DcLog.Once($"kvm-part:{kind}:faulted", $"KVM {kind}: {KvmSequencerCore.MaxFaults} faults: this part now rests at its spawn pose.");
    }

    /// <summary>The part's pose: <paramref name="rest"/> moved by <paramref name="pose"/>.</summary>
    protected abstract void Pose(ref RelativeTransform transform, in RelativeTransform rest, KvmPose pose, KvmMotionTuning tuning);

    private void WriteRestOnce(ref RelativeTransform transform)
    {
        if (_restWritten || !_hasRest)
            return;

        transform = _rest;
        _restWritten = true;
    }

    private KvmSequencerComponent? FindSequencer()
    {
        (Entity, KvmSequencerComponent)? found = Entity.GetClosestParentWith<KvmSequencerComponent>();
        return found?.Item2;
    }
}
