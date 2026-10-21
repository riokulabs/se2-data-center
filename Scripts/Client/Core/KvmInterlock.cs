// KvmInterlock: the door interlock and the target rule of the scripted KVM,
// with the per-frame inputs it decides from. In order (KvmSequencerCore.cs adds rule 1, the fault snap):
//   2. the door in front is Closing or Closed, KVM not home: FastStow (the race against the closing leaves);
//   3. Working, and no door in front or a door Open for DoorOpenDelay: Out;
//   4. otherwise:                                         Stowed.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client). The glue maps the game's
// DoorState onto KvmDoorState (KvmRackLink.FrontDoor).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <summary>The door in the cell in front of the KVM's face, as the interlock sees it (the game's DoorState, plus None).</summary>
public enum KvmDoorState
{
    /// <summary>No door in front (or not known): nothing to wait for.</summary>
    None,

    /// <summary>Closing: the leaves are swinging in.</summary>
    Closing,

    /// <summary>Opening: not yet clear.</summary>
    Opening,

    /// <summary>Closed.</summary>
    Closed,

    /// <summary>Fully open.</summary>
    Open,
}

/// <summary>What the world says this frame.</summary>
public readonly struct KvmInputs
{
    /// <summary>The KVM block is Working (built, unbroken, grid on, switched On).</summary>
    public readonly bool Working;

    /// <summary>The door in front of the face.</summary>
    public readonly KvmDoorState Door;

    /// <summary>The motion its rack slot calls for (see KvmRackSlot).</summary>
    public readonly KvmMotionPath Path;

    /// <summary>Inputs.</summary>
    public KvmInputs(bool working, KvmDoorState door, KvmMotionPath path)
    {
        Working = working;
        Door = door;
        Path = path;
    }

    /// <summary>The fallback when the world cannot be read: Working only, as the data-only KVM behaves.</summary>
    public static KvmInputs DataOnly(bool working) => new KvmInputs(working, KvmDoorState.None, KvmMotionPath.Sequenced);
}

/// <summary>The door interlock and target rule (rules 2 to 4 of the file header; rule 1 is the core's).</summary>
public static class KvmInterlock
{
    /// <summary>True for a door the KVM must not be out through: Closing or Closed.</summary>
    public static bool Blocks(KvmDoorState door) => door == KvmDoorState.Closing || door == KvmDoorState.Closed;

    /// <summary>
    /// The target for this frame. <paramref name="openFor"/> is how long the door has read Open (seconds);
    /// <paramref name="atHome"/> is true when the KVM is fully stowed (a closing door then needs no hurry).
    /// </summary>
    public static KvmTarget Decide(bool working, KvmDoorState door, float openFor, float openDelay, bool atHome)
    {
        if (Blocks(door))
            return atHome ? KvmTarget.Stowed : KvmTarget.FastStow;

        if (working && (door == KvmDoorState.None || (door == KvmDoorState.Open && openFor >= openDelay)))
            return KvmTarget.Out;

        return KvmTarget.Stowed;
    }
}
