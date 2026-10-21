// SurgeryRules: the game-free decisions behind CompositionSurgery, so Tests/CoreTests can exercise every refusal path
// natively (the glue that reads them from the game is compile-checked by Tests/CompileCheck). No game types here.
//
// The rules restate, on plain values, what the game enforces (decompiled 2.4.0.95, tools/decompiled/...;
// "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   components are stored in dependency order, dependencies first
//       VRage.DCS/…DCS.Definitions/EntityCompositeDefinition.cs:39-70 [2.4: 38-69] (IBuildStrategy.Build, Top.Sort)
//   a prefab's object builders are matched to components by index
//       VRage.DCS/…DCS.Builders/EntityBuilder.cs:231-255
//   Entity.Get<T>(tag) hard-casts the component under the tag
//       VRage.DCS/…DCS.Components/Entity.cs:121-132 [2.4: 119-130]
#nullable enable
using System;
using System.Collections.Generic;

namespace DataCenter.Shared.Core;

/// <summary>What a prepared composition edit found.</summary>
public enum SurgeryVerdict
{
    /// <summary>Validated and ready to apply; nothing is changed yet.</summary>
    Ready,

    /// <summary>The edit is already in place (a definition reload, or a second post-processor pass).</summary>
    AlreadyDone,

    /// <summary>Refused (logged): applying it would leave a broken composition or prefab.</summary>
    Refused,
}

/// <summary>
/// Pure checks used by <c>CompositionSurgery</c> before it changes a composition. The generics carry no
/// <c>IEquatable</c> constraint on purpose: checking one against the game's <c>StringId</c> walks its interfaces into
/// System.Xml.ReaderWriter, which mods do not reference (CS0012).
/// </summary>
public static class SurgeryRules
{
    /// <summary>
    /// The first component that depends on a component at its own index or later, or -1 when the order is valid.
    /// The composition keeps the order the game sorted it into: dependencies first. Surgery never reorders (the
    /// prefabs' object builders are matched by index), so a change that needs a reorder is refused instead.
    /// </summary>
    /// <param name="count">The number of components.</param>
    /// <param name="dependencies">The indices component i depends on (the game's strong, non-self dependencies).</param>
    public static int FirstOutOfOrder(int count, Func<int, IEnumerable<int>> dependencies)
    {
        for (int i = 0; i < count; i++)
        {
            foreach (int d in dependencies(i))
            {
                if (d >= i)
                    return i;
            }
        }

        return -1;
    }

    /// <summary>
    /// The tags a swapped slot gets: the old type's default tags become the new type's. Returns null, with the reason,
    /// when the slot carries any other tag: vanilla code may <c>Get&lt;T&gt;(thatTag)</c> and would hard-cast the new
    /// type to its own. A new type without default tags (a multi-component) is refused too: its tags would have to
    /// come from data.
    /// </summary>
    public static List<TTag>? Retag<TTag>(IReadOnlyList<TTag> slotTags, IReadOnlyList<TTag>? oldDefault, IReadOnlyList<TTag>? newDefault,
        out string? refusal)
    {
        refusal = null;
        if (newDefault == null || newDefault.Count == 0)
        {
            refusal = "the new type has no default tag (a multi-component)";
            return null;
        }

        foreach (TTag tag in slotTags)
        {
            if (oldDefault == null || !Contains(oldDefault, tag))
            {
                refusal = $"the slot also carries the tag '{tag}', which vanilla code could resolve to the new type";
                return null;
            }
        }

        var result = new List<TTag>(newDefault.Count);
        foreach (TTag tag in newDefault)
        {
            if (!Contains(result, tag))
                result.Add(tag);
        }

        return result;
    }

    /// <summary>True when <paramref name="keys"/> equals <paramref name="ids"/>, element by element.</summary>
    public static bool SameSequence<TKey>(ReadOnlySpan<TKey> keys, IReadOnlyList<TKey> ids)
    {
        if (keys.Length != ids.Count)
            return false;

        for (int i = 0; i < keys.Length; i++)
        {
            if (!EqualityComparer<TKey>.Default.Equals(keys[i], ids[i]))
                return false;
        }

        return true;
    }

    /// <summary>
    /// The first item other than <paramref name="self"/> whose composition is the same object as
    /// <paramref name="composition"/>, or default when none is: a shared composition must not get a component added
    /// for one prefab only (the others would be left one object builder short).
    /// </summary>
    public static T? FindSharer<T>(IEnumerable<T> all, T self, Func<T, object?> compositionOf, object composition) where T : class
    {
        foreach (T item in all)
        {
            if (item == null || ReferenceEquals(item, self))
                continue;

            object? other;
            try
            {
                other = compositionOf(item);
            }
            catch (Exception)
            {
                continue;   // a prefab without an entity cannot share anything
            }

            if (ReferenceEquals(other, composition))
                return item;
        }

        return null;
    }

    /// <summary>
    /// The verdict of a set of edits that must apply together or not at all: Refused when any is refused (then none
    /// is applied), AlreadyDone when all are done, otherwise Ready (apply the ready ones; the done ones stay).
    /// An empty set is AlreadyDone.
    /// </summary>
    public static SurgeryVerdict Combine(IEnumerable<SurgeryVerdict> verdicts)
    {
        bool ready = false;
        foreach (SurgeryVerdict v in verdicts)
        {
            if (v != SurgeryVerdict.Ready && v != SurgeryVerdict.AlreadyDone)
                return SurgeryVerdict.Refused; // Refused, or an out-of-range value: never apply on doubt

            ready |= v == SurgeryVerdict.Ready;
        }

        return ready ? SurgeryVerdict.Ready : SurgeryVerdict.AlreadyDone;
    }

    private static bool Contains<TTag>(IReadOnlyList<TTag> list, TTag tag)
    {
        for (int i = 0; i < list.Count; i++)
        {
            if (EqualityComparer<TTag>.Default.Equals(list[i], tag))
                return true;
        }

        return false;
    }
}
