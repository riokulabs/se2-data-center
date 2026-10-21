// KvmSpawnPolicy: snap or animate when the KVM's subparts spawn.
// ConditionalSubParts respawns the drawer on scene entry (world load, streaming in) and on every Functional change
// (finishing a weld). Scene entry must show the settled pose at once; a weld finished during play should animate.
//
// Game APIs: none (game-free).
#nullable enable

namespace DataCenter.Kvm.Core;

/// <summary>Whether freshly spawned subparts start at their end pose or animate into it.</summary>
public static class KvmSpawnPolicy
{
    /// <summary>Seconds after the sequencer enters the scene during which a spawn counts as part of that entry.</summary>
    public const float SceneEntryWindow = 1.0f;

    /// <summary>
    /// True: snap to the end pose (the subparts arrived with the block, e.g. a load or streaming in).
    /// False: animate (the block became Functional during play). An unknown (NaN) age animates: never a silent jump.
    /// </summary>
    public static bool ShouldSnap(float secondsSinceSequencerInScene) => secondsSinceSequencerInScene < SceneEntryWindow;
}
