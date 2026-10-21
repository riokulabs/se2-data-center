// KvmMotion: the game-free spring sequencer behind the scripted KVM.
//   Out:      the drawer slides out; once it passes the fold gate, a beat; then the lid lifts and settles on its detent.
//   Stowed:   the lid folds flat first; once it is within the retract gate, the drawer slides home.
//   FastStow: the same as Stowed with stiffer springs and a looser gate: the race against a closing rack door.
// Interruptible anywhere: a new target keeps position, velocity and the lead goal, so a reversal bends the motion.
// Every axis is integrated in closed form (exact for any step), so the result does not depend on the frame rate;
// substeps only resolve the gates, and gate crossings are split inside the substep.
//
// The class is split by responsibility: this file steps the motion and settles it; KvmMotion.Sequence.cs holds the
// sequencing rules (the gates, the beat, the hard stops); KvmMotion.Spring.cs the closed-form spring and its axis
// state. The pose and target types are KvmPose.cs.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>
/// The KVM's drawer-and-lid motion. Call <see cref="Step"/> once per frame with the frame's dt and the wanted target;
/// apply <see cref="Pose"/> to the subparts. Allocation-free; never throws; a bad dt (0, negative, NaN, infinite)
/// changes nothing.
/// </summary>
public sealed partial class KvmMotion : IKvmMotion
{
    private readonly KvmMotionTuning _t;
    private readonly Spring _slide, _slideFast, _foldOpen, _foldClose, _foldFast;
    private readonly double _preload;

    private Axis _s; // the drawer
    private Axis _f; // the lid
    private KvmTarget _target;
    private bool _settled;

    /// <summary>Seconds the drawer has been past the fold gate (capped once the lid may lift).</summary>
    private double _liftClock;

    /// <summary>The stow has passed its retract gate: the drawer heads home and stays heading home until the target is Out.</summary>
    private bool _retracting;

    /// <summary>The tuning in use.</summary>
    public KvmMotionTuning Tuning => _t;

    /// <summary>The current pose.</summary>
    public KvmPose Pose => new KvmPose((float)_s.X, (float)_f.X);

    /// <summary>The current rate of the pose, normalised units per second.</summary>
    public KvmPose Velocity => new KvmPose((float)_s.V, (float)_f.V);

    /// <summary>At rest at the target's end pose; <see cref="Step"/> with the same target is free.</summary>
    public bool Settled => _settled;

    /// <summary>The target of the last <see cref="Step"/> (or <see cref="Snap"/>).</summary>
    public KvmTarget Target => _target;

    /// <summary>Any value at or past OpenBeat means "the lid may lift"; the cap keeps the clock bounded and above OpenBeat + one substep.</summary>
    private double LiftClockCap => _t.OpenBeat + 1.0;

    /// <summary>A motion at rest, stowed.</summary>
    public KvmMotion(KvmMotionTuning? tuning = null)
    {
        _t = tuning ?? KvmMotionTuning.Default;
        _preload = _t.StopPreload;
        _slide = new Spring(_t.SlideOmega, 1.0, _t.LeadRatio);
        _slideFast = new Spring(_t.SlideOmegaFast, 1.0, _t.LeadRatio);
        _foldOpen = new Spring(_t.FoldOmegaOpen, _t.FoldZetaOpen, _t.LeadRatio);
        _foldClose = new Spring(_t.FoldOmegaClose, 1.0, _t.LeadRatio);
        _foldFast = new Spring(_t.FoldOmegaFast, 1.0, _t.LeadRatio);
        Snap(false);
    }

    /// <summary>Jump to an end pose at rest: out (drawer out, lid up) or stowed. For subparts that spawn into a scene.</summary>
    public void Snap(bool outPose)
    {
        _target = outPose ? KvmTarget.Out : KvmTarget.Stowed;
        double slideGoal = outPose ? 1.0 + _preload : -_preload;
        double foldGoal = outPose ? 1.0 : -_preload;
        _s = new Axis(outPose ? 1.0 : 0.0, 0.0, slideGoal);
        _f = new Axis(outPose ? 1.0 : 0.0, 0.0, foldGoal);
        _liftClock = outPose ? LiftClockCap : 0.0;
        _retracting = !outPose;
        _settled = true;
    }

    /// <summary>Advance by <paramref name="dt"/> seconds toward <paramref name="target"/> and return the new pose.</summary>
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
            if (target == KvmTarget.Out)
                _retracting = false;
        }

        if (_settled)
            return Pose;

        double total = Math.Min(dt, _t.MaxDt);
        int n = Math.Max(1, (int)Math.Ceiling(total / _t.MaxSubstep - 1e-9));
        double h = total / n;
        for (int i = 0; i < n; i++)
        {
            if (_target == KvmTarget.Out)
                SubstepOut(h);
            else
                SubstepStow(h, _target == KvmTarget.FastStow);
        }

        if (!_s.IsFinite || !_f.IsFinite)
            Snap(_target == KvmTarget.Out); // cannot happen with a sane tuning; never hand NaN to a transform
        else
            TrySettle();

        return Pose;
    }

    /// <summary>Snaps to the end pose once both axes are within <see cref="KvmMotionTuning.SnapEpsilon"/> of it, at rest.</summary>
    private void TrySettle()
    {
        double eps = _t.SnapEpsilon;
        if (_target == KvmTarget.Out)
        {
            if (_liftClock >= _t.OpenBeat
                && _s.Near(1.0, 1.0 + _preload, eps, _slide.Omega)
                && _f.Near(1.0, 1.0, eps, _foldOpen.Omega))
                Snap(true);
        }
        else
        {
            Spring slide = _target == KvmTarget.FastStow ? _slideFast : _slide;
            Spring fold = _target == KvmTarget.FastStow ? _foldFast : _foldClose;
            if (_retracting
                && _s.Near(0.0, -_preload, eps, slide.Omega)
                && _f.Near(0.0, -_preload, eps, fold.Omega))
            {
                KvmTarget keep = _target;
                Snap(false);
                _target = keep; // FastStow stays FastStow: the caller's target, not the pose, names it
            }
        }
    }
}
