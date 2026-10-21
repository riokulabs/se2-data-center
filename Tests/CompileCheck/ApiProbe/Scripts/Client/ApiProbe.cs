// API probe, Client side: one member per game API that the Client scripts (the KVM sequencer,
// its part drivers and the rack-door link) use. Never loaded by the game; Tests/CompileCheck compiles it against the
// probe's Simulation image, as GameScriptCodeProvider.cs:46-50 does, with the game's generators and analyzers.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   DoorComponent.DoorState / DoorOpeningData.OpenRatio  Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors/DoorComponent.cs:30-34, 173, 175
//   DoorState {Closing, Opening, Closed, Open}           Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors/DoorState.cs:6-12
//   DoorClientComponent : DoorComponent                  Game2.Client/Keen.Game2.Client.WorldObjects.CubeBlocks.Doors/DoorClientComponent.cs:11
//   CubeBlockComponent.Grid / AABB / BlockOrientation    Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/CubeBlockComponent.cs:4001, 4007, 4009
//   CubeGridComponent.GetBlock(Vector3I)                 Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeGrids/CubeGridComponent.cs:1547
//   IntegerOrientation.Forward                           VRage.Library/Keen.VRage.Library.Mathematics/IntegerOrientation.cs:750
//   Base6Directions.GetIntVector(Direction)              VRage.Library/Keen.VRage.Library.Mathematics/Base6Directions.cs:240
//   PowerableBlockComponent.Enabled                      Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/PowerableBlockComponent.cs:257
//   FunctionalBlockComponent.Functional / Working        Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/FunctionalBlockComponent.cs:343, 366
//   ChildTransformComponent.ChildTransform (get/set)     VRage.Core.Game/Keen.VRage.Core.Game.Components/ChildTransformComponent.cs:12-21
//   HierarchyComponent.Parent / Children                 VRage.Core.Game/Keen.VRage.Core.Game.Components/HierarchyComponent.cs:33, 45
//   Entity.TryGet<T>                                     VRage.DCS/Keen.VRage.DCS.Components/Entity.cs:135 [2.4: 133]
//   [Service] IGameTime.DeltaTime                        VRage.Core.Game/Keen.VRage.Core.Game.GameSystems.GameTimes/IGameTime.cs:12-24
//   [Definition] TranslationAnimationDefinition          VRage.Core.Game/Keen.VRage.Core.Game.GameSystems.RigidAnimations/TranslationAnimationComponent.cs:34-35
//   OnUpdateRigidAnimation (after OnPrepareRigidAnimation, before RenderSubmissionBegin) and the rigid job shape
//                                                        VRage.Core.Game/.../RigidAnimations/OnUpdateRigidAnimation.cs:8-10, TranslationAnimationComponent.cs:73-87
//   RelativeTransform.Position                           VRage.Core/Keen.VRage.Core/RelativeTransform.cs:610
//   JobGroup, [Before]                                   VRage.DCS/Keen.VRage.DCS.Annotations/JobGroup.cs, BeforeAttribute.cs:14-17
#nullable enable
using System;
using DataCenter.Probe;
using Keen.Game2.Client.WorldObjects.CubeBlocks.Doors;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors;
using Keen.Game2.Simulation.WorldObjects.CubeGrids;
using Keen.VRage.Core;
using Keen.VRage.Core.Game.Components;
using Keen.VRage.Core.Game.GameSystems.GameTimes;
using Keen.VRage.Core.Game.GameSystems.RigidAnimations;
using Keen.VRage.DCS.Annotations;
using Keen.VRage.DCS.Components;
using Keen.VRage.Library.Mathematics;
using Keen.VRage.Library.Reflection.DependencyInjections;

namespace DataCenter.Probe.Client;

/// <summary>Door rows: the state the KVM interlock reads from the rack door in front of it.</summary>
public static class ProbeDoors
{
    public static bool IsOpen(DoorComponent door)
    {
        return door.DoorState == DoorState.Open && door.DoorOpeningData.OpenRatio >= 1f;
    }

    public static bool IsClosingOrClosed(DoorComponent door)
    {
        return door.DoorState is DoorState.Closing or DoorState.Closed;
    }

    public static Type ClientDoorType()
    {
        return typeof(DoorClientComponent);
    }
}

/// <summary>Grid rows: from a block to the block in the cell in front of its face.</summary>
public static class ProbeGrid
{
    public static Entity? BlockInFront(CubeBlockComponent block)
    {
        CubeGridComponent grid = block.Grid;
        if (grid == null)
            return null;

        Vector3I forward = block.BlockOrientation.Forward.GetIntVector();
        Vector3I cell = block.AABB.Min + forward;
        return grid.GetBlock(cell);
    }

    public static bool Working(Entity block)
    {
        PowerableBlockComponent? powerable = block.TryGet<PowerableBlockComponent>();
        FunctionalBlockComponent? functional = block.TryGet<FunctionalBlockComponent>();
        return (powerable?.Enabled ?? false) && (functional?.Working ?? false) && (functional?.Functional ?? false);
    }
}

/// <summary>Part rows: a client component on a subpart, driven by a rigid-animation job.</summary>
public partial class KvmProbePart : Component
{
    /// <summary>The vanilla definition stays the data's: travel and speed come from TranslationAnimationDefinition.</summary>
    [Definition]
    public readonly TranslationAnimationDefinition Definition = null!;

    [Service]
    private IGameTime _time = null!;

    public float Seconds => (float)_time.DeltaTime.TotalSeconds;

    /// <summary>Runs before vanilla rigid animations prepare, e.g. to read door state once per frame.</summary>
    [Before(typeof(OnPrepareRigidAnimation))]
    public class ProbePrepare : JobGroup
    {
    }

    [ProbePrepare]
    private static void Prepare(KvmProbePart part)
    {
        try
        {
            Entity? parent = part.Entity.TryGet<HierarchyComponent>()?.Parent;
            int children = parent?.TryGet<HierarchyComponent>()?.Children?.Count ?? 0;
            ProbeShared.Report("hierarchy", children >= 0);
        }
        catch (Exception)
        {
            ProbeShared.Report("hierarchy", false);
        }
    }

    [OnUpdateRigidAnimation]
    private static void Animate(ref RelativeTransform transform, KvmProbePart part)
    {
        try
        {
            transform.Position += part.Definition.Translation * Math.Min(part.Seconds, 0.1f);
        }
        catch (Exception)
        {
            ProbeShared.Report("rigid job", false);
        }
    }

    public static void Pose(Entity subpart, RelativeTransform pose)
    {
        ChildTransformComponent? child = subpart.TryGet<ChildTransformComponent>();
        if (child != null)
            child.ChildTransform = pose;
    }
}
