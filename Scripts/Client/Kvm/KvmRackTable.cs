// KvmRackTable: the Data Center racks the KVM can sit in, by block definition GUID (Plan 4 Rulings P4-6, P4-12,
// P4-13): which are full (42U) or half (24U) racks, and which of their sides carry door leaves. Every GUID and every
// side set is generated from the data into DcGuids (dc/script_guids.py; door sides from dc/doors.py door_sides), so
// the runtime cannot name a rack the package does not ship. Tests/test_kvm_runtime.py checks KindOf covers every rack.
//
// Game APIs: none (System.Guid and the generated DcGuids only).
#nullable enable
using System;
using DataCenter.Kvm.Core;
using DataCenter.Shared;

namespace DataCenter.Kvm;

/// <summary>Rack kind and leaf sides by block definition GUID.</summary>
internal static class KvmRackTable
{
    /// <summary>The rack kind of a block definition: Full for the 42U racks, Half for the 24U ones, else None.</summary>
    internal static KvmRackKind KindOf(Guid g)
    {
        if (g == DcGuids.Rack42OpenBlock || g == DcGuids.Rack42SplitFrontBlock || g == DcGuids.Rack42SplitFrontRearBlock)
            return KvmRackKind.Full;

        bool half = g == DcGuids.Rack24OpenBlock || g == DcGuids.Rack24SplitFrontBlock || g == DcGuids.Rack24SplitFrontRearBlock;
        return half ? KvmRackKind.Half : KvmRackKind.None;
    }

    /// <summary>The sides of a rack that carry door leaves; an unknown block counts as guarded on both sides.</summary>
    internal static KvmDoorSides DoorSidesOf(Guid g)
        => g == DcGuids.Rack42OpenBlock ? (KvmDoorSides)DcGuids.Rack42OpenDoorSides
            : g == DcGuids.Rack42SplitFrontBlock ? (KvmDoorSides)DcGuids.Rack42SplitFrontDoorSides
            : g == DcGuids.Rack42SplitFrontRearBlock ? (KvmDoorSides)DcGuids.Rack42SplitFrontRearDoorSides
            : g == DcGuids.Rack24OpenBlock ? (KvmDoorSides)DcGuids.Rack24OpenDoorSides
            : g == DcGuids.Rack24SplitFrontBlock ? (KvmDoorSides)DcGuids.Rack24SplitFrontDoorSides
            : g == DcGuids.Rack24SplitFrontRearBlock ? (KvmDoorSides)DcGuids.Rack24SplitFrontRearDoorSides
            : KvmDoorSides.Front | KvmDoorSides.Rear; // not reached for a known rack; unknown: both sides guarded
}
