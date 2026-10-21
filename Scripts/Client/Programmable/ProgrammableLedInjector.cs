// ProgrammableLedInjector: with scripts on, the Programmable's script-status lamp (and its LCD status bar) turn green
// while the block is Working; with scripts off this file never loads and the data keeps them amber.
//
// How: the Programmable's client composition carries a vanilla BlockMaterialSwapperComponent whose definition (ours,
// DcGuids.ProgrammableSwapper) lists our two models and maps no mesh part. At definition load this post-processor
// adds DcGuids.ProgrammableStatusMeshPart -> EmissiveGreen to it, and the vanilla component does the rest: it applies
// the replacements when the block starts Working and drops them when it stops (DisabledTag), as on the door racks.
// Only a client definition changes; nothing reaches an entity's saved state. The decision is the game-free
// Core/StatusLampRules.cs (Tests/CoreTests); this file reads the game's state into it and writes the result back.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   [DefinitionPostProcessor(ForceInstantiation)]   VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessorAttribute.cs:10-20
//   SimpleDefinitionPostProcessor<T>.PostProcess(T), ReProcess -> Unload + PostProcess (a reload runs it again)
//                                                   VRage.Library/Keen.VRage.Library.Definitions/SimpleDefinitionPostProcessor.cs:9-32
//   DefinitionPostProcessor.Manager (protected)     VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessor.cs:25, 31-36
//   DefinitionManager.TryGetDefinition<T>(Guid, out T) (hard-casts, so it is asked for a plain Definition)
//                                                   VRage.Library/Keen.VRage.Library.Definitions/DefinitionManager.cs:992-1003
//   Definition.Guid / DebugName                     VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343, 346
//   MaterialDefinition                              VRage.Core/Keen.VRage.Core.Render.Materials/MaterialDefinition.cs:35
//   StringId.Get(string)                            VRage.Library/Keen.VRage.Library.Utils/StringId.cs:158
//   DictionaryReader<K, V> (implicit from Dictionary), HashSetReader<T>.Count
//                                                   VRage.Library/Keen.VRage.Library.Collections.Readers/DictionaryReader.cs:14-24, 63; HashSetReader.cs:13-23
//   BlockMaterialSwapperDefinition.WorkingReplacementModels / WorkingReplacementsMeshParts (public get)
//                                                   Game2.Client/Keen.Game2.Client.WorldObjects.CubeBlocks.Render/BlockMaterialSwapperDefinition.cs:241, 246 [2.4: 239, 244]
//   ... the private setters and ProcessReplacements: SwapperReflection.cs   REFLECTION: re-check after a game update
//   BlockMaterialSwapperComponent: reads ProcessedWorkingMaterialReplacements at [Init]; applies them on
//   WhenStartWorking, removes them while DisabledTag/StagingTag   Game2.Client/.../Render/BlockMaterialSwapperComponent.cs:57-94
//   WhenStartWorking + WhenStopWorking = DisabledTag/StagingTag added or removed
//                                                   Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/WorkingAttributes.cs:13-37
#nullable enable
using System;
using System.Collections.Generic;
using DataCenter.Programmable.Core;
using DataCenter.Shared;
using Keen.Game2.Client.WorldObjects.CubeBlocks.Render;
using Keen.VRage.Core.Render.Materials;
using Keen.VRage.Library.Collections.Readers;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Utils;

namespace DataCenter.Programmable;

/// <summary>
/// Maps the Programmable's status lamp to EmissiveGreen in its material swapper's Working replacements.
/// Touches only the swapper definition <see cref="DcGuids.ProgrammableSwapper"/>; any surprise leaves it as the data
/// shipped it (amber in every state) and logs once.
/// </summary>
/// <remarks>Not ForceInstantiation: forcing a definition type into a set that has none (the Engine set) also wakes vanilla's
/// post-processors for that type there; see KvmCompositeInjector. Our swapper's own set instantiates this anyway.</remarks>
[DefinitionPostProcessor]
public sealed class ProgrammableLedInjector : SimpleDefinitionPostProcessor<BlockMaterialSwapperDefinition>
{
    private const string What = "programmable status lamp";

    /// <summary>True when every reflection target was found (a probe for the in-game check).</summary>
    public static bool ReflectionTargetsFound => SwapperReflection.Instance.Found;

    /// <inheritdoc/>
    public override void PostProcess(BlockMaterialSwapperDefinition definition)
    {
        try
        {
            if (definition == null || definition.Guid != DcGuids.ProgrammableSwapper)
                return;

            Apply(definition);
        }
        catch (Exception ex)
        {
            DcLog.Once("led-ex", $"{What}: left amber, unexpected {DcReflection.Unwrap(ex)}");
        }
    }

    private void Apply(BlockMaterialSwapperDefinition swapper)
    {
        SwapperReflection reflection = SwapperReflection.Instance;
        if (!reflection.Found)
        {
            DcLog.Once("led-reflection", $"{What}: left amber, BlockMaterialSwapperDefinition's setters or ProcessReplacements are gone (game update?)");
            return;
        }

        MaterialDefinition? green = Manager.TryGetDefinition<Definition>(DcGuids.EmissiveGreenMaterial, out Definition? found)
            ? found as MaterialDefinition
            : null;
        StringId part = StringId.Get(DcGuids.ProgrammableStatusMeshPart);
        DictionaryReader<StringId, MaterialDefinition> existing = swapper.WorkingReplacementsMeshParts;

        LampSwapVerdict verdict = StatusLampRules.Decide(swapper.WorkingReplacementModels.Count, existing, part, green,
            (a, b) => a.Guid == b.Guid, out string? why);
        if (verdict == LampSwapVerdict.AlreadyMapped)
            return;

        if (verdict != LampSwapVerdict.Add)
        {
            DcLog.Once("led-" + verdict, $"{What}: left amber, {why}");
            return;
        }

        // Compute first, then assign: if the game's own processing throws, the definition is still untouched.
        DictionaryReader<StringId, MaterialDefinition> pairs = StatusLampRules.With(existing, part, green!);
        object? processed = reflection.Process(swapper, pairs);
        if (processed == null)
        {
            DcLog.Once("led-processed", $"{What}: left amber, ProcessReplacements returned nothing");
            return;
        }

        reflection.Install(swapper, pairs, processed, existing);
        DcLog.Info($"{What}: '{DcGuids.ProgrammableStatusMeshPart}' -> EmissiveGreen while Working, on {swapper.WorkingReplacementModels.Count} model(s) of '{swapper.DebugName}'");
    }
}
