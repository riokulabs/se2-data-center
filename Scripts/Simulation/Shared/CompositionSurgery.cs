// CompositionSurgery: load-time edits of an entity composition (add a component, swap a component's type), the
// injection pattern of an earlier prototype made general,
// validated up front and transactional: an edit is prepared (validated, nothing changed), then a set of edits is
// applied together, all or nothing (used for the KVM's sequencer and its two part drivers). Callers are
// [DefinitionPostProcessor]s. The decisions themselves are the game-free Core/SurgeryRules.cs (unit-tested in
// Tests/CoreTests); the surgery reads the game's state into them.
//
// The class is split by responsibility: this file applies prepared edits and holds the shared validation;
// CompositionSurgery.Add.cs prepares adding a component to a prefab, CompositionSurgery.Swap.cs swapping a type in a
// composite; CompositionReflection.cs holds the two reflection targets.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   EntityCompositeDefinition.Builder (Ids/Types/Definitions/Tags, TagIndex, InvalidateTagIndex)
//                                                   VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:79-122 [2.4: 78-121]
//   Builder.TagIndex -> CompileTagIndex, throws on a conflicting tag                                       ibid. :92, 178-192
//   IBuildStrategy.Build: the composite's own init sorts components dependencies-first                    ibid. :38-69, 558-564
//   EntityCompositeDefinition.ComponentCount/Ids/Types/Definitions/Tags                                   ibid. :506-518
//   EntityCompositeDependencyOrderBuildStrategy.IterateDependencies: "Unsatisfied" / "Malformed dependency"
//                                                   VRage.DCS/Keen.VRage.DCS.Builders/EntityCompositeDependencyOrderBuildStrategy.cs:13-40
//   ImmutableSingleton<T>.Instance                  VRage.Library/Keen.VRage.Library.Utils/ImmutableSingleton.cs:14
//   EntityBuilder.ComponentBuildInfo                VRage.DCS/Keen.VRage.DCS.Builders/EntityBuilder.cs:29-50
//   EntityBuilder.FixTags (a component's default tags; throws for multi-components)                       ibid. :408-411
//   Definition.Guid / DebugName (auto-properties)   VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343, 346
#nullable enable
using System;
using System.Collections.Generic;
using DataCenter.Shared.Core;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Builders;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Utils;

namespace DataCenter.Shared;

/// <summary>
/// Edits entity compositions while definitions load, so that a scripted behaviour exists only where the scripts run.
/// <para>Every edit is first <i>prepared</i>: validated with the game's own rules (the part's definition and
/// object-builder types, <c>EntityBuilder.ResolveComponent</c>; the tag table; the dependency checks and order the
/// composite's init would apply, <c>EntityCompositeDependencyOrderBuildStrategy</c>) while nothing changes. Surgery
/// never reorders components (prefab object builders are matched by index), so a change that would need a reorder is
/// refused. Prepared edits are then applied together by <see cref="Apply"/>, which rolls the applied ones back if a
/// later one throws. A refusal is logged once; nothing throws, so a game update that renames a reflection target
/// leaves the block data-only.</para>
/// <para>Every edit is idempotent (a definition reload runs post-processors again, <c>SimpleDefinitionPostProcessor.cs:25-32</c>):
/// an edit already in place prepares as <see cref="SurgeryVerdict.AlreadyDone"/>.</para>
/// </summary>
public static partial class CompositionSurgery
{
    /// <summary>True when both reflection targets were found (a probe for the in-game check).</summary>
    public static bool ReflectionTargetsFound => CompositionReflection.Instance.Found;

    /// <summary>
    /// Applies prepared edits in order, all or nothing: if one throws, the ones already applied are rolled back in
    /// reverse. Null entries (AlreadyDone verdicts) are skipped. Never throws.
    /// </summary>
    /// <param name="edits">The prepared edits, in the order to apply them.</param>
    /// <param name="what">What the edits do together, for the log.</param>
    /// <returns>True when every edit was applied (logged in one line); false when one failed (logged, rolled back).</returns>
    public static bool Apply(List<SurgeryEdit?> edits, string what)
    {
        var applied = new List<SurgeryEdit>();
        SurgeryEdit? current = null;
        try
        {
            foreach (SurgeryEdit? edit in edits)
            {
                if (edit == null)
                    continue;

                current = edit;
                edit.Commit();
                applied.Add(edit);
            }
        }
        catch (Exception ex)
        {
            RollBack(applied, what, $"{current?.What ?? "an edit"} failed ({Unwrap(ex)})");
            return false;
        }

        if (applied.Count > 0)
            DcLog.Info($"{what}: {Summary(applied)}"); // one line per injection, whatever its edit count

        return true;
    }

    /// <summary><see cref="PrepareAdd"/> and <see cref="Apply"/> in one step.</summary>
    /// <returns>True when the component (or a missing object-builder slot for it) was added; false when it was already
    /// complete or anything was wrong (logged).</returns>
    public static bool AddComponent(PrefabDefinition prefab, Guid componentId, Type type, Definition? definition, object? objectBuilder,
        IEnumerable<PrefabDefinition> allPrefabs)
    {
        return PrepareAdd(prefab, componentId, type, definition, objectBuilder, allPrefabs, out SurgeryEdit? edit) == SurgeryVerdict.Ready
            && Apply(new List<SurgeryEdit?> { edit }, "add a component");
    }

    /// <summary><see cref="PrepareSwap"/> (keeping the slot's definition) and <see cref="Apply"/> in one step.</summary>
    /// <returns>True when the type was swapped; false when it already was, or anything was wrong (logged).</returns>
    public static bool SwapComponentType(EntityCompositeDefinition composite, Type oldType, Type newType)
    {
        return PrepareSwap(composite, oldType, newType, null, out SurgeryEdit? edit) == SurgeryVerdict.Ready
            && Apply(new List<SurgeryEdit?> { edit }, "swap a component type");
    }

    /// <summary>Rolls <paramref name="applied"/> back in reverse after <paramref name="failure"/>; logs the outcome.</summary>
    private static void RollBack(List<SurgeryEdit> applied, string what, string failure)
    {
        for (int i = applied.Count - 1; i >= 0; i--)
        {
            try
            {
                applied[i].Rollback();
            }
            catch (Exception rollbackFailure)
            {
                DcLog.Info($"could not {what}: {failure}, and rolling back '{applied[i].What}' FAILED too ({Unwrap(rollbackFailure)}): the block may not spawn");
                return;
            }
        }

        DcLog.Once("surgery:apply:" + what, $"could not {what}: {failure}; {applied.Count} applied edit(s) rolled back. The block keeps its data-only behaviour.");
    }

    /// <summary>"N edit(s): first; second; ..." for the log.</summary>
    private static string Summary(List<SurgeryEdit> edits)
        => $"{edits.Count} edit(s): {string.Join("; ", edits.ConvertAll(e => e.What))}";

    /// <summary>A copy of the composition into a builder of <paramref name="count"/> slots (count &gt;= ComponentCount).</summary>
    private static EntityCompositeDefinition.Builder Copy(EntityCompositeDefinition composition, int count)
    {
        var builder = new EntityCompositeDefinition.Builder(count);
        for (int i = 0; i < composition.ComponentCount; i++)
        {
            builder.Ids[i] = composition.Ids[i];
            builder.Types[i] = composition.Types[i];
            builder.Definitions[i] = composition.Definitions[i];
            builder.Tags[i] = composition.Tags[i];
        }

        return builder;
    }

    /// <summary>
    /// The checks the composite's own init applies, on the finished builder, before anything changes: the tag table
    /// (throws on a conflict) and every component's dependencies (the game's strategy throws on an unsatisfied or
    /// malformed one), which must all sit at lower indices, since surgery does not reorder.
    /// </summary>
    private static void Validate(ref EntityCompositeDefinition.Builder builder)
    {
        builder.InvalidateTagIndex();
        _ = builder.TagIndex;   // cached in the builder; Assign keeps it (EntityCompositeDefinition.cs:598 [2.4: 570])
        EntityCompositeDependencyOrderBuildStrategy strategy = ImmutableSingleton<EntityCompositeDependencyOrderBuildStrategy>.Instance;
        EntityCompositeDefinition.Builder snapshot = builder;
        int late = SurgeryRules.FirstOutOfOrder(builder.ComponentCount, i => new List<int>(strategy.IterateDependencies(i, snapshot)));
        if (late >= 0)
            throw new InvalidOperationException($"{builder.Types[late]?.Name} would depend on a component after it (the game would have to reorder)");
    }

    /// <summary>The type's default tags, or null for a multi-component (EntityBuilder.FixTags throws for those).</summary>
    private static StringId[]? DefaultTags(Type type)
    {
        try
        {
            return EntityBuilder.FixTags(type, null);
        }
        catch (ArgumentException)
        {
            return null;
        }
    }

    private static EntityBuilder.ComponentBuildInfo Part(Type type, object? definition, object? objectBuilder)
    {
        return new EntityBuilder.ComponentBuildInfo
        {
            Type = type,
            ComponentId = Guid.Empty,
            Tags = null,
            Definition = definition,
            ObjectBuilder = objectBuilder,
        };
    }

    private static SurgeryVerdict Refuse(string key, string what, string why)
    {
        DcLog.Once("surgery:" + key, $"could not {what}: {why}. The block keeps its data-only behaviour.");
        return SurgeryVerdict.Refused;
    }

    private static string Unwrap(Exception ex) => DcReflection.Unwrap(ex);

    /// <summary>A definition's name and GUID for the log. Both are auto-properties (Definition.cs:343, 346), so reading
    /// them cannot throw, even on a half-loaded definition.</summary>
    private static string Describe(object? definition)
        => definition is Definition d ? $"'{d.DebugName}' ({d.Guid})" : "(null)";
}
