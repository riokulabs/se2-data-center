// KvmPose: what the KVM motion is asked to do (KvmTarget) and where it is (KvmPose, normalised), shared by both
// motion paths, the sequencer core and the game's part drivers.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>What the KVM is asked to do.</summary>
public enum KvmTarget
{
    /// <summary>Lid flat, then the drawer home.</summary>
    Stowed,

    /// <summary>Drawer out, a beat, then the lid up.</summary>
    Out,

    /// <summary>Stowed, fast: the rack door in front is closing.</summary>
    FastStow,
}

/// <summary>A normalised KVM pose (or, from <see cref="KvmMotion.Velocity"/>, its rate per second).</summary>
public struct KvmPose
{
    /// <summary>0 = home, 1 = fully out (x the data's 0.45 m travel).</summary>
    public float Slide;

    /// <summary>0 = flat, 1 = up (x the data's 100 degrees); up to ~1.02 during the detent bounce.</summary>
    public float Fold;

    /// <summary>A pose.</summary>
    public KvmPose(float slide, float fold)
    {
        Slide = slide;
        Fold = fold;
    }

    /// <inheritdoc/>
    public override string ToString() => $"(slide {Slide:0.0000}, fold {Fold:0.0000})";
}
