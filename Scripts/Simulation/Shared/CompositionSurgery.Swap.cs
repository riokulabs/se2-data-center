// CompositionSurgery.Swap: preparing to replace a component's type in a composite, in place (used for the KVM's
// drawer and screen drivers in their subpart composites). See CompositionSurgery.cs for the class and the transaction.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   EntityCompositeDefinition.Assign(Builder), internal (through CompositionReflection)   REFLECTION: re-check after a game update
//                                                   VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:596-608 [2.4: 568-580]
//   EntityCompositeDefinition.ComponentCount/Ids/Types/Definitions/Tags                                   ibid. :506-518
//   EntityBuilder.ResolveComponent / AssertMatch (definition and OB types must match the component)
//                                                   VRage.DCS/Keen.VRage.DCS.Builders/EntityBuilder.cs:464-511
//   Default tags come from the base-class chain (e.g. every rigid animation is "RigidAnimationComponent"), and
//   Entity.Get<T>(tag) hard-casts the component found under the tag
//                                                   VRage.DCS/Keen.VRage.DCS.Internal/ComponentInfoIndexer.cs:97-118,
//                                                   VRage.DCS/Keen.VRage.DCS.Components/Entity.cs:121-147 [2.4: 119-145]
#nullable enable
using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using DataCenter.Shared.Core;
using Keen.VRage.DCS.Builders;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Utils;

namespace DataCenter.Shared;

/// <remarks>This part prepares swapping a component type in a composite (<see cref="PrepareSwap"/>).</remarks>
public static partial class CompositionSurgery
{
    /// <summary>
    /// Prepares replacing the component of <paramref name="oldType"/> in <paramref name="composite"/> with one of
    /// <paramref name="newType"/>: same index, same component id, so every prefab using the composite keeps a valid
    /// object-builder list.
    /// <para>Only parts without an object builder can be swapped (the composite does not own the prefabs' object
    /// builders, and they hold null for such parts). <paramref name="newType"/> must accept the slot's definition, or
    /// <paramref name="newDefinition"/> when one is given (a part with its own definition type), and its
    /// dependencies must sit earlier in the composite.</para>
    /// <para>Tags: the slot may carry only <paramref name="oldType"/>'s default tag, which becomes
    /// <paramref name="newType"/>'s. So <c>Entity.Get&lt;NewType&gt;()</c> finds the new part, and vanilla code asking for
    /// the old tag (e.g. FBAC's <c>TryGet&lt;ToggleRigidAnimationComponent&gt;</c>) finds nothing instead of a foreign
    /// type. A slot with any other tag is refused: vanilla code could <c>Get&lt;T&gt;(thatTag)</c> and hard-cast.</para>
    /// </summary>
    /// <param name="composite">The composite to change (shared by every prefab that uses it).</param>
    /// <param name="oldType">The component type to replace.</param>
    /// <param name="newType">The replacement type.</param>
    /// <param name="newDefinition">The replacement's definition, or null to keep the slot's.</param>
    /// <param name="edit">The edit to apply when the verdict is <see cref="SurgeryVerdict.Ready"/>, else null.</param>
    public static SurgeryVerdict PrepareSwap(EntityCompositeDefinition composite, Type oldType, Type newType, Definition? newDefinition,
        out SurgeryEdit? edit)
    {
        edit = null;
        string what = $"swap {oldType?.Name ?? "null"} -> {newType?.Name ?? "null"} in {Describe(composite)}";
        try
        {
            CompositionReflection reflection = CompositionReflection.Instance;
            if (composite == null || oldType == null || newType == null || oldType == newType)
                return Refuse("swap-args", what, "a null composite or type, or the same type twice");

            if (!reflection.CanAssign)
                return Refuse("reflection", what, "EntityCompositeDefinition.Assign is gone (game update?)");

            int index = composite.Types.IndexOf(oldType);
            if (index < 0)
            {
                if (composite.Types.IndexOf(newType) >= 0)
                    return SurgeryVerdict.AlreadyDone;

                return Refuse("swap-missing:" + what, what, $"no {oldType.Name} in the composite");
            }

            if (composite.Types.IndexOf(newType) >= 0)
                return Refuse("swap-both:" + what, what, $"the composite already holds a {newType.Name}");

            Definition? definition = newDefinition ?? composite.Definitions[index];
            // Both parts must be object-builder-free, and the new one must take its definition (EntityBuilder.cs:464-511).
            EntityBuilder.ResolveComponent(Part(oldType, composite.Definitions[index], null), EntityBuilder.ComponentMalformation.ObjectBuilder);
            EntityBuilder.ResolveComponent(Part(newType, definition, null), EntityBuilder.ComponentMalformation.All);

            List<StringId>? tags = SurgeryRules.Retag<StringId>(composite.Tags[index], DefaultTags(oldType), DefaultTags(newType), out string? refusal);
            if (tags == null)
                return Refuse("swap-tags:" + what, what, refusal ?? "the slot's tags cannot be moved to the new type");

            EntityCompositeDefinition.Builder original = Copy(composite, composite.ComponentCount);
            EntityCompositeDefinition.Builder builder = Copy(composite, composite.ComponentCount);
            builder.Types[index] = newType;
            builder.Definitions[index] = definition;
            builder.Tags[index] = ImmutableArray.CreateRange(tags);
            Validate(ref builder);
            Validate(ref original);

            Guid id = composite.Ids[index];
            edit = new SurgeryEdit($"{what} (component {id})",
                () => reflection.Assign(composite, builder), () => reflection.Assign(composite, original));
            return SurgeryVerdict.Ready;
        }
        catch (Exception ex)
        {
            return Refuse("swap-ex:" + what, what, Unwrap(ex));
        }
    }
}
