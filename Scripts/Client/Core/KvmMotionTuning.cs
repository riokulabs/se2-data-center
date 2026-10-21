// KvmMotionTuning: every timing constant of the scripted KVM motion, in one place (Plan 4 Ruling P4-3).
// The data owns the geometry (0.45 m of drawer travel, a 100 degree lid fold); the script owns only the timing,
// so every value here is normalised (slide 0..1, fold 0..1) or in seconds / rad/s.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>
/// The springs, gates and limits behind <see cref="KvmMotion"/>. Immutable: build a variant with named arguments,
/// e.g. <c>new KvmMotionTuning(foldGate: 0.9f)</c>. Out-of-range or non-finite arguments fall back to the defaults,
/// so a bad tuning degrades to the shipped feel instead of producing NaN.
/// </summary>
/// <remarks>
/// <para><b>The shape of the motion.</b> Each axis is a second-order spring that chases a <i>lead goal</i>, and the
/// lead goal eases toward the commanded target at <see cref="LeadRatio"/> x the spring's omega. The lead keeps the
/// acceleration continuous: the drawer spins up instead of being kicked (a bare spring step starts at full
/// acceleration), and a reversal bends the motion instead of jolting it.</para>
/// <para><b>Hard stops.</b> Where the mechanism has a real stop (the drawer's rails at both ends, the lid resting on
/// the deck), the spring aims <see cref="StopPreload"/> beyond it, so the part arrives with a small, finite speed and
/// the stop takes it (an inelastic landing: 5 cm/s for the drawer, 16 cm/s on a fast stow). That replaces the critically
/// damped spring's long, invisible creep with a definite "home": the soft-close of a real drawer, whose last 4 cm take
/// about 0.35 s. The open lid has no stop: it settles on its detent with a ~1 % (1 degree) bounce.</para>
/// <para><b>The shipped feel (Task 7's feel review, Ruling P4-11, approved by the user):</b> the drawer peaks at
/// 0.85 m/s (2.6 m/s on a fast stow); the open settles in 2.35 s (visually done at about 1.5 s; the rest is the lid's
/// sub-degree settle), the close in 1.78 s, the fast stow in 0.60 s, still beating the closing leaves by 20.9 mm (Task 6,
/// the strict 0.2 s lead). Task 5 had tuned for 1.4 / 1.2 / 0.6 s budgets (a 1.8 m/s drawer); P4-11 put feel first.
/// Re-tuning anything here needs new motion graphs and the Task 6 clearance checks (Tests/test_kvm_sequence.py).</para>
/// </remarks>
public sealed class KvmMotionTuning
{
    /// <summary>The shipped tuning.</summary>
    public static readonly KvmMotionTuning Default = new KvmMotionTuning();

    /// <summary>Drawer spring, rad/s, critically damped. Peak speed ~1.9/s normalised (0.85 m/s of the 0.45 m stroke).</summary>
    public readonly float SlideOmega;

    /// <summary>Drawer spring during a fast stow, rad/s, critically damped (P4-4's ceiling is 20).</summary>
    public readonly float SlideOmegaFast;

    /// <summary>Lid spring while lifting, rad/s.</summary>
    public readonly float FoldOmegaOpen;

    /// <summary>Lid damping while lifting: 0.82 overshoots ~1 %, the 1 degree detent bounce.</summary>
    public readonly float FoldZetaOpen;

    /// <summary>Lid spring while closing (and while held shut), rad/s, critically damped.</summary>
    public readonly float FoldOmegaClose;

    /// <summary>Lid spring during a fast stow, rad/s, critically damped (P4-4's ceiling is 20).</summary>
    public readonly float FoldOmegaFast;

    /// <summary>The lead goal's rate as a multiple of each spring's omega (4: a ~50 ms spin-up on the drawer). 0 = no lead.</summary>
    public readonly float LeadRatio;

    /// <summary>How far beyond a hard stop the spring aims (normalised), so the part lands instead of creeping in. 0.025
    /// lands the drawer at 5 cm/s, the soft-close; 0.03 would land it at about 6 cm/s, home about 0.08 s sooner.</summary>
    public readonly float StopPreload;

    /// <summary>Normalised slide before the lid may rise: 0.91 (0.4095 m of 0.45). Task 6 measured the smallest slide at
    /// which a full lid sweep stays clear of the KVM's own upper panel as 0.8844 (dc/kvm_motion.min_safe_fold_gate);
    /// 0.91 keeps 11.5 mm of drawer travel in hand (the rule: at least 10 mm).</summary>
    public readonly float FoldGate;

    /// <summary>Seconds the lid waits after the slide passes <see cref="FoldGate"/>: the beat between slide and fold.</summary>
    public readonly float OpenBeat;

    /// <summary>The lid is flat enough for the drawer to slide in (normalised fold; 0.02 = 2 degrees).</summary>
    public readonly float RetractGate;

    /// <summary>The fast-stow version of <see cref="RetractGate"/> (0.08 = 8 degrees).</summary>
    public readonly float RetractGateFast;

    /// <summary>Seconds after the rack door reads Open before the KVM may pop (read by KvmSequencerCore).</summary>
    public readonly float DoorOpenDelay;

    /// <summary>Settle snap: within this distance of the rest pose (and this x omega in speed), snap and stop updating.</summary>
    public readonly float SnapEpsilon;

    /// <summary>The longest substep, seconds. Gates are resolved inside a substep, so this bounds gate timing error only.</summary>
    public readonly float MaxSubstep;

    /// <summary>The longest frame the motion honours, seconds; a longer hitch is treated as this (no teleport).</summary>
    public readonly float MaxDt;

    /// <summary>+1: the lid folds +100 degrees about +X, per core Task 8; flipped only by the in-game check (read by KvmScreenPart).</summary>
    public readonly int LidAxisSign;

    /// <summary>Seconds for a full stroke of the data-only path (<see cref="KvmLinearMotion"/>, Ruling P4-12): the data's
    /// POP_TIME, travel / Speed = 0.45 m / 0.45 m/s and angle / AngularSpeed = 100 / 100 degrees/s (dc/subparts.py;
    /// Tests/test_kvm_runtime.py pins it to the data).</summary>
    public readonly float DataOnlyStroke;

    /// <summary>A tuning; every argument defaults to the shipped value.</summary>
    public KvmMotionTuning(
        float slideOmega = 5.2f,
        float slideOmegaFast = 16f,
        float foldOmegaOpen = 6.5f,
        float foldZetaOpen = 0.82f,
        float foldOmegaClose = 8f,
        float foldOmegaFast = 18f,
        float leadRatio = 4f,
        float stopPreload = 0.025f,
        float foldGate = 0.91f,
        float openBeat = 0.15f,
        float retractGate = 0.02f,
        float retractGateFast = 0.08f,
        float doorOpenDelay = 0.15f,
        float snapEpsilon = 0.001f,
        float maxSubstep = 1f / 120f,
        float maxDt = 0.1f,
        int lidAxisSign = 1,
        float dataOnlyStroke = 1f)
    {
        SlideOmega = InRange(slideOmega, 0.5f, 200f, 5.2f);
        SlideOmegaFast = InRange(slideOmegaFast, 0.5f, 200f, 16f);
        FoldOmegaOpen = InRange(foldOmegaOpen, 0.5f, 200f, 6.5f);
        FoldZetaOpen = InRange(foldZetaOpen, 0.05f, 4f, 0.82f);
        FoldOmegaClose = InRange(foldOmegaClose, 0.5f, 200f, 8f);
        FoldOmegaFast = InRange(foldOmegaFast, 0.5f, 200f, 18f);
        LeadRatio = InRange(leadRatio, 0f, 100f, 4f);
        StopPreload = InRange(stopPreload, 0f, 0.25f, 0.025f);
        FoldGate = InRange(foldGate, 0f, 1f, 0.91f);
        OpenBeat = InRange(openBeat, 0f, 5f, 0.15f);
        RetractGate = InRange(retractGate, 0f, 1f, 0.02f);
        RetractGateFast = InRange(retractGateFast, 0f, 1f, 0.08f);
        DoorOpenDelay = InRange(doorOpenDelay, 0f, 10f, 0.15f);
        SnapEpsilon = InRange(snapEpsilon, 1e-6f, 0.05f, 0.001f);
        MaxSubstep = InRange(maxSubstep, 1e-4f, 0.05f, 1f / 120f);
        MaxDt = InRange(maxDt, 1e-3f, 1f, 0.1f);
        LidAxisSign = lidAxisSign < 0 ? -1 : 1;
        DataOnlyStroke = InRange(dataOnlyStroke, 0.05f, 10f, 1f);
    }

    private static float InRange(float value, float min, float max, float fallback)
        => value >= min && value <= max ? value : fallback; // NaN fails both comparisons
}
