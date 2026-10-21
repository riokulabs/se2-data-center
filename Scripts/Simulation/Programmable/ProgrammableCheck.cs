// ProgrammableCheck: with scripts on, confirms once per load that the Programmable's server prefab carries the vanilla
// InGameScriptingComponent the data ships (Ruling P4-1 = A': no injection, the component is always in the data), and
// logs the answer, so the game log shows whether the block can run a program. Read-only: it never changes a definition.
// The Route B injector this task once planned (ProgrammableInjector) is not needed under A' and does not exist.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   [DefinitionPostProcessor], SimpleDefinitionPostProcessor<T>.PostProcess(T)
//                                                   VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessorAttribute.cs:10-20,
//                                                   SimpleDefinitionPostProcessor.cs:9-23
//   Definition.Guid / DebugName                     VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343, 126
//   PrefabDefinition.Composition (=> _entity.Definition)
//                                                   VRage.Core.Game/Keen.VRage.Core.Game.Definitions/PrefabDefinition.cs:226 [2.4: 224]
//   EntityCompositeDefinition.Ids / Types / Definitions   VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:537-544 [2.4: 509-516]
//   InGameScriptingComponent                        Game2.Simulation/Keen.Game2.Simulation.Scripting/InGameScriptingComponent.cs:24
#nullable enable
using System;
using DataCenter.Shared;
using DataCenter.Shared.Core;
using Keen.Game2.Simulation.Scripting;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.Library.Definitions;

namespace DataCenter.Programmable;

/// <summary>Logs whether the Programmable's server prefab can run a program (one line per load; never changes data).</summary>
[DefinitionPostProcessor]
public sealed class ProgrammableCheck : SimpleDefinitionPostProcessor<PrefabDefinition>
{
    /// <inheritdoc/>
    public override void PostProcess(PrefabDefinition prefab)
    {
        try
        {
            if (prefab == null || prefab.Guid != DcGuids.ProgrammableServerPrefab)
                return;

            EntityCompositeDefinition? composition = prefab.Composition;
            int index = composition == null ? -1 : composition.Ids.IndexOf(DcGuids.ProgrammableScriptingComponentId);
            bool isScripting = index >= 0 && composition!.Types[index] == typeof(InGameScriptingComponent);
            Definition? bound = index >= 0 ? composition!.Definitions[index] : null;

            ScriptingVerdict verdict = ScriptingPresence.Judge(index, isScripting, bound?.Guid, DcGuids.ProgrammableScriptingDefinition);
            DcLog.Once("prog-scripting-" + verdict, ScriptingPresence.Describe(verdict, prefab.DebugName ?? prefab.Guid.ToString()));
        }
        catch (Exception ex)
        {
            DcLog.Once("prog-check-ex", $"programmable: scripting check skipped, {ex.GetType().Name}: {ex.Message}");
        }
    }
}
