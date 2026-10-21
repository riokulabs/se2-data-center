// API probe, Simulation side: one member per row of the Plan 4 API table that the Simulation scripts use. It is
// never loaded by the game; Tests/CompileCheck compiles it exactly as the game would (run.sh all --mod ApiProbe),
// so a game update that renames or hides one of these members fails here first, with the row named.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   InGameScriptingObjectBuilder.Script / Running       Game2.Simulation/Keen.Game2.Simulation.Scripting/InGameScriptingObjectBuilder.cs:562, 567
//   InGameScriptingComponent                             Game2.Simulation/Keen.Game2.Simulation.Scripting/InGameScriptingComponent.cs:24
//   InGameScriptingDefinition                            Game2.Simulation/Keen.Game2.Simulation.Scripting/InGameScriptingDefinition.cs:34
//   [DefinitionPostProcessor(ForceInstantiation)]        VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessorAttribute.cs:10-20
//   SimpleDefinitionPostProcessor<T>.PostProcess(T)      VRage.Library/Keen.VRage.Library.Definitions/SimpleDefinitionPostProcessor.cs:7-22
//   DefinitionPostProcessor.Manager (protected)          VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessor.cs:25, 31-36
//   DefinitionManager.TryGetDefinition<T>(Guid, out T)   VRage.Library/Keen.VRage.Library.Definitions/DefinitionManager.cs:992
//   EntityCompositeDefinition.Builder, TagIndex          VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:79-122 [2.4: 78-121]
//   EntityCompositeDefinition.Assign (internal)          ibid. :568       REFLECTION: re-check after a game update
//   PrefabDefinition._entity (private), Composition      VRage.Core.Game/Keen.VRage.Core.Game.Definitions/PrefabDefinition.cs:221, 226 [2.4: 219, 224]   REFLECTION
//   EntityObjectBuilder.Definition / ObjectBuilders      VRage.DCS/Keen.VRage.DCS.ObjectBuilders/EntityObjectBuilder.cs:206-212
//   EntityBuilder.FixTags / ResolveComponent             VRage.DCS/Keen.VRage.DCS.Builders/EntityBuilder.cs:408-411, 464-511
//   CubeBlockComponent.Definition                        Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks/CubeBlockComponent.cs:4040
//   Definition.Guid via (Definition)(object) (CS0012: CubeBlockDefinition's base is in VRage.Game, unreferenced)
//                                                        (known compile gotcha)
//   Log.Default / Info                                   VRage.Library/Keen.VRage.Library.Diagnostics/Log.cs:91, LogExtensions.cs:79
#nullable enable
using System;
using System.Collections.Immutable;
using System.Reflection;
using Keen.Game2.Simulation.Scripting;
using Keen.Game2.Simulation.WorldObjects.CubeBlocks;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Builders;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.DCS.ObjectBuilders;
using Keen.VRage.Library.Collections;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Diagnostics;
using Keen.VRage.Library.Utils;

namespace DataCenter.Probe;

/// <summary>A public Simulation type the Client probe uses, proving Client compiles against Simulation's image (P4-5).</summary>
public static class ProbeShared
{
    public const string Prefix = "[DataCenter] probe: ";

    public static void Report(string row, bool ok)
    {
        try
        {
            Log.Default?.Info(Prefix + row + (ok ? " ok" : " FAILED"));
        }
        catch (Exception)
        {
        }
    }
}

/// <summary>Programmable rows: the vanilla scripting component, its object builder and its definition lookup.</summary>
[DefinitionPostProcessor(ForceInstantiation = true)]
public class ProbeScriptingPostProcessor : SimpleDefinitionPostProcessor<PrefabDefinition>
{
    public override void PostProcess(PrefabDefinition definition)
    {
        try
        {
            // The post-processor reaches its manager through the protected DefinitionPostProcessor.Manager.
            bool found = Manager.TryGetDefinition<InGameScriptingDefinition>(Guid.Empty, out InGameScriptingDefinition? scripting);
            ProbeShared.Report("TryGetDefinition<InGameScriptingDefinition>", !found && scripting == null);
        }
        catch (Exception)
        {
            ProbeShared.Report("TryGetDefinition<InGameScriptingDefinition>", false);
        }
    }

    public static InGameScriptingObjectBuilder NewScriptingObjectBuilder()
    {
        return new InGameScriptingObjectBuilder { Script = "", Running = false };
    }

    public static Type ScriptingComponentType()
    {
        return typeof(InGameScriptingComponent);
    }
}

/// <summary>Composition-surgery rows: the builder round-trip and the two reflection targets.</summary>
public static class ProbeComposition
{
    public static EntityCompositeDefinition.Builder RoundTrip(EntityCompositeDefinition composition, Type extra)
    {
        int n = composition.ComponentCount;
        var builder = new EntityCompositeDefinition.Builder(n + 1);
        for (int i = 0; i < n; i++)
        {
            builder.Ids[i] = composition.Ids[i];
            builder.Types[i] = composition.Types[i];
            builder.Definitions[i] = composition.Definitions[i];
            builder.Tags[i] = composition.Tags[i];
        }

        builder.Ids[n] = Guid.NewGuid();
        builder.Types[n] = extra;
        builder.Definitions[n] = null;
        builder.Tags[n] = ImmutableArray.Create(EntityBuilder.FixTags(extra, null));
        builder.InvalidateTagIndex();
        _ = builder.TagIndex;
        EntityBuilder.ResolveComponent(new EntityBuilder.ComponentBuildInfo { Type = extra }, EntityBuilder.ComponentMalformation.All);
        return builder;
    }

    public static MethodInfo? AssignMethod()
    {
        return typeof(EntityCompositeDefinition).GetMethod("Assign", BindingFlags.Instance | BindingFlags.NonPublic,
            null, new[] { typeof(EntityCompositeDefinition.Builder) }, null);
    }

    public static KeyedList<Guid, object?>? PrefabObjectBuilders(PrefabDefinition prefab)
    {
        FieldInfo? field = typeof(PrefabDefinition).GetField("_entity", BindingFlags.Instance | BindingFlags.NonPublic);
        var entity = field?.GetValue(prefab) as EntityObjectBuilder;
        return entity != null && entity.Definition == prefab.Composition ? entity.ObjectBuilders : null;
    }

    public static StringId FirstTag(EntityCompositeDefinition composition)
    {
        return composition.Tags.Length > 0 && composition.Tags[0].Length > 0 ? composition.Tags[0][0] : default;
    }
}

/// <summary>Block rows: a block definition's GUID without touching CubeBlockDefinition's VRage.Game base.</summary>
public static class ProbeBlocks
{
    public static Guid BlockDefinitionGuid(CubeBlockComponent block)
    {
        return ((Definition)(object)block.Definition).Guid;
    }

    public static bool IsBlockDefinition(object? definition)
    {
        return definition is CubeBlockDefinition;
    }
}
