// CompositionSurgery.Add: preparing to append a component to a prefab's composition, with its object-builder slot
// (Task 8: the KVM's sequencer on its client prefab). See CompositionSurgery.cs for the class and the transaction.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   PrefabDefinition._entity (through CompositionReflection)   REFLECTION: re-check after a game update
//                                                   VRage.Core.Game/Keen.VRage.Core.Game.Definitions/PrefabDefinition.cs:221 [2.4: 219]
//   EntityObjectBuilder.Definition / ObjectBuilders (KeyedList<Guid, object?>, in composition order)
//                                                   VRage.DCS/Keen.VRage.DCS.ObjectBuilders/EntityObjectBuilder.cs:206-212
//   KeyedCollection.Keys / Add / RemoveAt (a rollback) VRage.Library/Keen.VRage.Library.Collections/KeyedCollection.cs:25, 142, 232
//   EntityBuilder.WithComponentsFrom: "Mismatch in Entity parts" unless OB count == component count
//                                                   VRage.DCS/Keen.VRage.DCS.Builders/EntityBuilder.cs:231-255
//   EntityBuilder.ResolveComponent / AssertMatch (definition and OB types must match the component)       ibid. :464-511
//   EntityBuilder.FixTags (the new component's default tags)                                              ibid. :408-411
//   DefinitionManager.GetDefinitionsOfTypeAndDescendants<T> (the caller's; a recursive read lock, so it can be
//   enumerated inside a post-processor's own pass)  VRage.Library/Keen.VRage.Library.Definitions/DefinitionManager.cs:1161, 1177
#nullable enable
using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using DataCenter.Shared.Core;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Builders;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.DCS.ObjectBuilders;
using Keen.VRage.Library.Definitions;

namespace DataCenter.Shared;

/// <remarks>This part prepares adding a component to a prefab (<see cref="PrepareAdd"/>).</remarks>
public static partial class CompositionSurgery
{
    /// <summary>
    /// Prepares appending a component of <paramref name="type"/> to <paramref name="prefab"/>'s composition, under the
    /// fixed <paramref name="componentId"/>, with its object-builder slot added to the prefab in the same position.
    /// </summary>
    /// <param name="prefab">The prefab to change. Its composition must be its own: when any other prefab uses the same
    /// composition object, the edit is refused (those prefabs would be left one object builder short).</param>
    /// <param name="componentId">A stable id for the new component. It must never change between versions: saves key
    /// component state by it.</param>
    /// <param name="type">The component type; its default tag must not be taken by another component, and its
    /// <c>[Component]</c> dependencies must already be in the composition.</param>
    /// <param name="definition">The component's definition, of exactly the type its <c>[Definition]</c> field
    /// declares, or null when it has none.</param>
    /// <param name="objectBuilder">The component's object builder, of exactly the type its <c>[Init]</c> takes, or null
    /// when it has none.</param>
    /// <param name="allPrefabs">Every loaded prefab, for the sharing check: pass the post-processor's
    /// <c>Manager.GetDefinitionsOfTypeAndDescendants&lt;PrefabDefinition&gt;()</c> (<c>DefinitionPostProcessor.cs:25</c>).
    /// Required: a script cannot reach the global manager (naming <c>DefinitionManager</c> as a generic argument is
    /// CS0012, its interfaces live in System.Xml.ReaderWriter, which mods do not reference).</param>
    /// <param name="edit">The edit to apply when the verdict is <see cref="SurgeryVerdict.Ready"/>, else null.</param>
    public static SurgeryVerdict PrepareAdd(PrefabDefinition prefab, Guid componentId, Type type, Definition? definition, object? objectBuilder,
        IEnumerable<PrefabDefinition> allPrefabs, out SurgeryEdit? edit)
    {
        edit = null;
        string what = $"add {type?.Name ?? "null"} to {Describe(prefab)}";
        try
        {
            CompositionReflection reflection = CompositionReflection.Instance;
            if (prefab == null || type == null || componentId == Guid.Empty)
                return Refuse("add-args", what, "a null prefab or type, or an empty component id");

            if (!reflection.Found)
                return Refuse("reflection", what, "EntityCompositeDefinition.Assign or PrefabDefinition._entity is gone (game update?)");

            if (!(reflection.EntityOf(prefab) is EntityObjectBuilder entity) || entity.Definition == null || entity.ObjectBuilders == null)
                return Refuse("add-entity:" + what, what, "the prefab has no entity object builder");

            EntityCompositeDefinition composition = entity.Definition;
            int n = composition.ComponentCount;
            if (composition.Types.IndexOf(type) >= 0)
                return PrepareComplete(entity, composition, componentId, objectBuilder, what, out edit);

            if (composition.Ids.IndexOf(componentId) >= 0)
                return Refuse("add-id:" + what, what, $"component id {componentId} is already used by another component");

            // One long: the prefab still holds this component's trailing slot but its composition lost the component
            // (a definition reload of the composition alone). Re-adding the component makes the two agree again.
            Span<Guid> keys = entity.ObjectBuilders.Keys;
            bool oneLong = keys.Length == n + 1 && keys[n] == componentId && SurgeryRules.SameSequence<Guid>(keys.Slice(0, n), composition.Ids);
            if (!oneLong && !SurgeryRules.SameSequence<Guid>(keys, composition.Ids))
                return Refuse("add-obs:" + what, what, $"the prefab's object builders ({entity.ObjectBuilders.Count}) do not line up with its {n} components");

            if (allPrefabs == null)
                return Refuse("add-noshare:" + what, what, "no prefab list to check that its composition is not shared");

            PrefabDefinition? sharer = SurgeryRules.FindSharer(allPrefabs, prefab, p => reflection.EntityOf(p)?.Definition, composition);
            if (sharer != null)
                return Refuse("add-shared:" + what, what, $"its composition is shared with {Describe(sharer)}, which would be left one object builder short");

            // The builder's own checks, now, instead of a "Mismatch"/"Malformation" throw when the entity is built.
            EntityBuilder.ResolveComponent(Part(type, definition, objectBuilder), EntityBuilder.ComponentMalformation.All);

            EntityCompositeDefinition.Builder original = Copy(composition, n);
            EntityCompositeDefinition.Builder builder = Copy(composition, n + 1);
            builder.Ids[n] = componentId;
            builder.Types[n] = type;
            builder.Definitions[n] = definition;
            builder.Tags[n] = ImmutableArray.Create(EntityBuilder.FixTags(type, null));
            Validate(ref builder);
            Validate(ref original);

            edit = oneLong
                ? new SurgeryEdit($"{what} (its object-builder slot was already there)",
                    () => reflection.Assign(composition, builder), () => reflection.Assign(composition, original))
                : new SurgeryEdit(what,
                    () => CommitWithSlot(reflection, entity, composition, builder, original, componentId, objectBuilder),
                    () =>
                    {
                        RemoveTrailingSlot(entity, componentId);
                        reflection.Assign(composition, original);
                    });
            return SurgeryVerdict.Ready;
        }
        catch (Exception ex)
        {
            return Refuse("add-ex:" + what, what, Unwrap(ex));
        }
    }

    /// <summary>Installs the grown composition and adds the prefab's slot; if the slot cannot be added, puts the
    /// composition back, so the OB count stays equal to the component count, and rethrows (Apply rolls back).</summary>
    private static void CommitWithSlot(CompositionReflection reflection, EntityObjectBuilder entity, EntityCompositeDefinition composition,
        EntityCompositeDefinition.Builder builder, EntityCompositeDefinition.Builder original, Guid componentId, object? objectBuilder)
    {
        reflection.Assign(composition, builder);
        try
        {
            entity.ObjectBuilders.Add(componentId, objectBuilder);
        }
        catch (Exception)
        {
            reflection.Assign(composition, original);
            throw;
        }
    }

    /// <summary>
    /// The type is already in the composition: done, unless this prefab is the one-short case (its object builders
    /// equal the composition's ids without the trailing component), which gets the missing slot.
    /// </summary>
    private static SurgeryVerdict PrepareComplete(EntityObjectBuilder entity, EntityCompositeDefinition composition,
        Guid componentId, object? objectBuilder, string what, out SurgeryEdit? edit)
    {
        edit = null;
        Span<Guid> keys = entity.ObjectBuilders.Keys;
        if (SurgeryRules.SameSequence<Guid>(keys, composition.Ids))
            return SurgeryVerdict.AlreadyDone;   // a reload, or a second post-processor pass

        int n = composition.ComponentCount;
        bool oneShort = n > 0 && composition.Ids[n - 1] == componentId
            && SurgeryRules.SameSequence<Guid>(keys, composition.Ids.RemoveAt(n - 1));
        if (!oneShort)
            return Refuse("add-inconsistent:" + what, what, $"the type is present but the prefab's {keys.Length} object builders do not match its {n} components");

        edit = new SurgeryEdit($"{what} (the missing object-builder slot for component {componentId})",
            () => entity.ObjectBuilders.Add(componentId, objectBuilder),
            () => RemoveTrailingSlot(entity, componentId));
        return SurgeryVerdict.Ready;
    }

    /// <summary>Removes the prefab's last object-builder slot when it is <paramref name="componentId"/>'s (a rollback).</summary>
    private static void RemoveTrailingSlot(EntityObjectBuilder entity, Guid componentId)
    {
        int last = entity.ObjectBuilders.Count - 1;
        if (last >= 0 && entity.ObjectBuilders.Keys[last] == componentId)
            entity.ObjectBuilders.RemoveAt(last);
    }
}
