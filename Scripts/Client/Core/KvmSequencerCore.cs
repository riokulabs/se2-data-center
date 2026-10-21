// KvmSequencerCore: every decision the scripted KVM makes, game-free (Plan 4 Rulings P4-3, P4-4, P4-12; Task 8).
// The game component (Scripts/Client/Kvm/KvmSequencerComponent.cs) only reads the world into KvmInputs once per
// frame and hands the resulting pose to the part drivers; the target rule, the door interlock, the scene-entry snap
// (the load-bug fix), the path routing and the fault budget all live here, so Tests/CoreTests covers them natively.
//
// The target rule, in order (the Task 8 brief):
//   1. faulted:                                           snap to the wanted end pose every frame (data-only-like);
//   2.-4. the door interlock and Working (KvmInterlock.cs).
// Scene entry (the first KvmSpawnPolicy.SceneEntryWindow seconds after the KVM enters the scene, e.g. a world load or
// streaming in) shows the settled end pose at once instead of animating into it: the subparts arrive with the block,
// and a door that is already open counts as open long enough. Subparts that spawn later (a weld finished during
// play) start stowed, as a fresh subpart is, and animate.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>
/// The KVM's sequencer state machine. Call <see cref="EnterScene"/> when the block enters the scene,
/// <see cref="Update"/> once per frame, <see cref="PartSpawned"/> when a subpart spawns, and
/// <see cref="ReportFault"/> when the glue caught an exception. Never throws, never allocates after construction: both
/// motion paths are built up front, and a path change switches between them.
/// </summary>
public sealed class KvmSequencerCore
{
    /// <summary>Faults (caught exceptions) after which the KVM stops sequencing and snaps (Task 8 brief, step 3).</summary>
    public const int MaxFaults = 3;

    /// <summary>Normalised distance from stowed under which the KVM counts as home.</summary>
    public const float HomeEpsilon = 1e-4f;

    private readonly KvmMotionTuning _t;
    private readonly KvmMotion _sequenced;
    private readonly KvmLinearMotion _linear;
    private IKvmMotion _motion;
    private KvmMotionPath _path;
    private float _secondsInScene;
    private float _openFor;
    private int _faults;
    private bool _faulted;
    private bool _wantOut;
    private KvmTarget _target;

    /// <summary>The pose the part drivers apply.</summary>
    public KvmPose Pose => _motion.Pose;

    /// <summary>The target the rule chose in the last <see cref="Update"/>.</summary>
    public KvmTarget Target => _target;

    /// <summary>The motion path in use (it changes only when the motion is settled, or by a snap).</summary>
    public KvmMotionPath Path => _path;

    /// <summary>The motion is at rest at its target's end pose.</summary>
    public bool Settled => _motion.Settled;

    /// <summary>Stopped sequencing after <see cref="MaxFaults"/> faults: snaps to the wanted end pose every frame.</summary>
    public bool Faulted => _faulted;

    /// <summary>Faults reported so far.</summary>
    public int Faults => _faults;

    /// <summary>Seconds of game time since <see cref="EnterScene"/> (paused time does not count).</summary>
    public float SecondsInScene => _secondsInScene;

    /// <summary>Seconds the door in front has read Open.</summary>
    public float DoorOpenFor => _openFor;

    /// <summary>Inside the scene-entry window: end poses are shown at once (<see cref="KvmSpawnPolicy"/>).</summary>
    public bool InEntryWindow => KvmSpawnPolicy.ShouldSnap(_secondsInScene);

    /// <summary>Fully stowed.</summary>
    public bool AtHome
    {
        get
        {
            KvmPose p = _motion.Pose;
            return p.Slide <= HomeEpsilon && p.Fold <= HomeEpsilon;
        }
    }

    /// <summary>A sequencer at rest, stowed, at the start of its scene-entry window.</summary>
    public KvmSequencerCore(KvmMotionTuning? tuning = null, KvmMotionPath path = KvmMotionPath.Sequenced)
    {
        _t = tuning ?? KvmMotionTuning.Default;
        _sequenced = new KvmMotion(_t);
        _linear = new KvmLinearMotion(_t);
        _path = path == KvmMotionPath.DataOnly ? KvmMotionPath.DataOnly : KvmMotionPath.Sequenced;
        _motion = MotionFor(_path);
        _target = KvmTarget.Stowed;
    }

    /// <summary>The block entered the scene: a world load, streaming in, or a placement. Restarts the entry window.</summary>
    public void EnterScene() => _secondsInScene = 0f;

    /// <summary>Advance one frame of <paramref name="dt"/> game seconds (0 while paused) and return the pose to apply.</summary>
    public KvmPose Update(float dt, KvmInputs inputs)
    {
        float step = dt > 0f && !float.IsInfinity(dt) ? dt : 0f; // NaN fails the comparison
        _secondsInScene = Math.Min(_secondsInScene + step, 1e6f);
        bool entry = InEntryWindow;

        if (inputs.Door == KvmDoorState.Open)
        {
            _openFor = Math.Min(_openFor + step, 1e6f);
            if (entry)
                _openFor = Math.Max(_openFor, _t.DoorOpenDelay); // already open when the block arrived: no wait
        }
        else
        {
            _openFor = 0f;
        }

        _target = KvmInterlock.Decide(inputs.Working, inputs.Door, _openFor, _t.DoorOpenDelay, AtHome);
        _wantOut = _target == KvmTarget.Out;
        AdoptPath(inputs.Path, force: entry || _faulted);

        if (entry || _faulted)
        {
            if (!(_motion.Settled && (_motion.Target == KvmTarget.Out) == _wantOut))
                _motion.Snap(_wantOut);

            return _motion.Pose;
        }

        return _motion.Step(step, _target);
    }

    /// <summary>
    /// A subpart spawned. Inside the entry window (or faulted) it shows the wanted end pose at once; later, the
    /// motion restarts from stowed, where a fresh subpart is, and animates from there.
    /// </summary>
    public void PartSpawned()
    {
        if (_faulted || InEntryWindow)
            _motion.Snap(_wantOut);
        else if (!AtHome)
            _motion.Snap(false);
    }

    /// <summary>Counts a fault; true exactly once, when this one made the sequencer <see cref="Faulted"/>.</summary>
    public bool ReportFault()
    {
        if (_faulted)
            return false;

        _faults++;
        if (_faults < MaxFaults)
            return false;

        _faulted = true;
        return true;
    }

    /// <summary>
    /// Switches to <paramref name="path"/> without a jump: only once the current motion is settled (both paths share
    /// their end poses), or at once when <paramref name="force"/> (the caller snaps this frame anyway).
    /// </summary>
    private void AdoptPath(KvmMotionPath path, bool force)
    {
        if (path != KvmMotionPath.DataOnly)
            path = KvmMotionPath.Sequenced;

        if (path == _path || (!force && !_motion.Settled))
            return;

        bool atOut = _motion.Settled ? _motion.Target == KvmTarget.Out : _wantOut;
        _motion = MotionFor(path);
        _motion.Snap(atOut); // a snap resets every bit of a motion's state: as good as new
        _path = path;
    }

    private IKvmMotion MotionFor(KvmMotionPath path) => path == KvmMotionPath.DataOnly ? _linear : _sequenced;
}
