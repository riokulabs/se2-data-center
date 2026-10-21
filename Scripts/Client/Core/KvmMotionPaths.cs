// KvmMotionPaths: the two motions the scripted KVM can run, behind one interface (Plan 4 Rulings P4-3, P4-12).
//   Sequenced: KvmMotion, the spring-eased slide, beat, fold (everywhere but one slot).
//   DataOnly:  KvmLinearMotion, the data's own simultaneous linear slide and fold at the vanilla speed. It runs in the
//              top slot of a full (42U) rack, where the sequenced lid's arc would rise into Plan 3's containment rail
//              (Task 6: dc/kvm_motion.motion_path_for_slot; the clearances there model exactly this linear motion, so it
//              must stay un-eased unless the trajectories are re-dumped and the checks re-run).
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>Which motion a KVM runs (Ruling P4-12).</summary>
public enum KvmMotionPath
{
    /// <summary>The spring-eased slide, beat, fold (<see cref="KvmMotion"/>).</summary>
    Sequenced,

    /// <summary>The data's simultaneous linear motion (<see cref="KvmLinearMotion"/>): a full 42U rack's top slot.</summary>
    DataOnly,
}

/// <summary>A KVM motion: stepped once per frame toward a target, or snapped to an end pose.</summary>
public interface IKvmMotion
{
    /// <summary>The current pose.</summary>
    KvmPose Pose { get; }

    /// <summary>At rest at the target's end pose; a <see cref="Step"/> with the same target changes nothing.</summary>
    bool Settled { get; }

    /// <summary>The target of the last <see cref="Step"/> or <see cref="Snap"/>.</summary>
    KvmTarget Target { get; }

    /// <summary>Jump to an end pose at rest: out (drawer out, lid up) or stowed.</summary>
    void Snap(bool outPose);

    /// <summary>Advance by <paramref name="dt"/> seconds toward <paramref name="target"/>; a bad dt changes nothing.</summary>
    KvmPose Step(float dt, KvmTarget target);
}

/// <summary>
/// The data-only motion: slide and fold move together (slide = fold = f), linearly, a full stroke in
/// <see cref="KvmMotionTuning.DataOnlyStroke"/> seconds, which is the data's TranslationAnimation / RotationAnimation
/// pair (0.45 m at 0.45 m/s, 100 degrees at 100 degrees/s). Like vanilla it reverses on the spot. A fast stow runs at
/// the same speed: with the drawer heading home at once (no lid-first gate) it already beats the closing leaves by
/// at least 86 mm (Task 6). Allocation-free; never throws.
/// </summary>
public sealed class KvmLinearMotion : IKvmMotion
{
    private readonly KvmMotionTuning _t;
    private readonly double _rate; // stroke fraction per second
    private double _f;
    private KvmTarget _target;
    private bool _settled;

    /// <inheritdoc/>
    public KvmPose Pose => new KvmPose((float)_f, (float)_f);

    /// <inheritdoc/>
    public bool Settled => _settled;

    /// <inheritdoc/>
    public KvmTarget Target => _target;

    /// <summary>A motion at rest, stowed.</summary>
    public KvmLinearMotion(KvmMotionTuning? tuning = null)
    {
        _t = tuning ?? KvmMotionTuning.Default;
        _rate = 1.0 / _t.DataOnlyStroke;
        Snap(false);
    }

    /// <inheritdoc/>
    public void Snap(bool outPose)
    {
        _target = outPose ? KvmTarget.Out : KvmTarget.Stowed;
        _f = outPose ? 1.0 : 0.0;
        _settled = true;
    }

    /// <inheritdoc/>
    public KvmPose Step(float dt, KvmTarget target)
    {
        if (!(dt > 0f) || float.IsInfinity(dt))
            return Pose; // paused, NaN, negative or infinite: no time passes

        if (target != KvmTarget.Out && target != KvmTarget.FastStow)
            target = KvmTarget.Stowed; // an out-of-range cast is a stow: the safe direction

        if (target != _target)
        {
            _target = target;
            _settled = false;
        }

        if (_settled)
            return Pose;

        double goal = target == KvmTarget.Out ? 1.0 : 0.0;
        double step = _rate * Math.Min(dt, _t.MaxDt);
        _f = goal > _f ? Math.Min(goal, _f + step) : Math.Max(goal, _f - step);
        _settled = _f == goal;
        return Pose;
    }
}
