// KvmInjectorPostProcessors: when the KVM surgery runs. A definition reload re-runs only the post-processors of the
// reloaded type (SimpleDefinitionPostProcessor.ReProcess), so there is one per type the surgery edits: the client
// prefab (the sequencer) and the compositions (the drawer and screen composites, and the prefab's own). Both run the
// same idempotent KvmInjector.Run, so either alone repairs whatever its reload restored.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   [DefinitionPostProcessor(ForceInstantiation)]   VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessorAttribute.cs:10-20
//   SimpleDefinitionPostProcessor<T>.PostProcess(T), ReProcess -> Unload + PostProcess of that type's post-processors
//                                                   VRage.Library/Keen.VRage.Library.Definitions/SimpleDefinitionPostProcessor.cs:9-32
//   DefinitionPostProcessor.Manager (protected)     VRage.Library/Keen.VRage.Library.Definitions/DefinitionPostProcessor.cs:25, 31-36
//   DefinitionManager.TryGetDefinition<T>(Guid, out T) (hard-casts, so it is asked for a plain Definition);
//   GetDefinitionsOfTypeAndDescendants<T> (a recursive read lock)   VRage.Library/Keen.VRage.Library.Definitions/DefinitionManager.cs:992-1003, 1161, 1177
//   PrefabDefinition.Composition                    VRage.Core.Game/Keen.VRage.Core.Game.Definitions/PrefabDefinition.cs:226 [2.4: 224]
#nullable enable
using System;
using DataCenter.Shared;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.Library.Definitions;

namespace DataCenter.Kvm;

/// <summary>Runs <see cref="KvmInjector"/> when the KVM's client prefab is (re)loaded.</summary>
[DefinitionPostProcessor(ForceInstantiation = true)]
public sealed class KvmPrefabInjector : SimpleDefinitionPostProcessor<PrefabDefinition>
{
    /// <inheritdoc/>
    public override void PostProcess(PrefabDefinition definition)
    {
        try
        {
            if (definition != null && definition.Guid == DcGuids.KvmClientPrefab)
                KvmInjector.Run(Lookup, () => Manager.GetDefinitionsOfTypeAndDescendants<PrefabDefinition>());
        }
        catch (Exception ex)
        {
            KvmInjector.Report("prefab", ex);
        }
    }

    private Definition? Lookup(Guid guid) => Manager.TryGetDefinition<Definition>(guid, out Definition? found) ? found : null;
}

/// <summary>Runs <see cref="KvmInjector"/> when one of the KVM's compositions is (re)loaded.</summary>
/// <remarks>
/// Not ForceInstantiation: forcing EntityCompositeDefinition into the Engine set (loaded first, no compositions of its
/// own) also instantiates vanilla's ConveyorGraphPostProcessor there, whose Validate asserts on the missing
/// ClientServerInfoPostProcessor and crashes the load (seen in game with -loadScripts). Our compositions live in our
/// own set, which instantiates this post-processor anyway.
/// </remarks>
[DefinitionPostProcessor]
public sealed class KvmCompositeInjector : SimpleDefinitionPostProcessor<EntityCompositeDefinition>
{
    /// <inheritdoc/>
    public override void PostProcess(EntityCompositeDefinition definition)
    {
        try
        {
            if (definition == null)
                return;

            Guid g = definition.Guid;
            if (g != DcGuids.KvmDrawerComposite && g != DcGuids.KvmScreenComposite && !IsKvmClientComposition(definition))
                return;

            KvmInjector.Run(Lookup, () => Manager.GetDefinitionsOfTypeAndDescendants<PrefabDefinition>());
        }
        catch (Exception ex)
        {
            KvmInjector.Report("composite", ex);
        }
    }

    private bool IsKvmClientComposition(EntityCompositeDefinition definition)
        => Lookup(DcGuids.KvmClientPrefab) is PrefabDefinition prefab && ReferenceEquals(prefab.Composition, definition);

    private Definition? Lookup(Guid guid) => Manager.TryGetDefinition<Definition>(guid, out Definition? found) ? found : null;
}
