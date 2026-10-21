// Tests of Scripts/Simulation/Shared/Core: every refusal path CompositionSurgery takes before it changes a composition,
// and the DcLog once-budget. Tags and ids are plain strings and Guids here; the game's StringId and Guid behave alike.
#nullable enable
using System;
using System.Collections.Generic;
using DataCenter.Shared.Core;

internal static class SurgeryRulesTests
{
    private static void Check(bool ok, string name) => Program.Check(ok, name);

    /// <summary>Review I1: the composite's dependency order, dependencies first, never reordered by surgery.</summary>
    public static void DependencyOrder()
    {
        var none = new Dictionary<int, int[]>();
        IEnumerable<int> Deps(Dictionary<int, int[]> d, int i) => d.TryGetValue(i, out int[]? v) ? v : Array.Empty<int>();

        Check(SurgeryRules.FirstOutOfOrder(0, i => Deps(none, i)) == -1, "an empty composite is in order");
        Check(SurgeryRules.FirstOutOfOrder(4, i => Deps(none, i)) == -1, "no dependencies: in order");

        // 0: hierarchy, 1: block (needs 0), 2: animation (needs 1), 3: appended driver (needs 1 and 2): fine.
        var ok = new Dictionary<int, int[]> { [1] = new[] { 0 }, [2] = new[] { 1 }, [3] = new[] { 1, 2 } };
        Check(SurgeryRules.FirstOutOfOrder(4, i => Deps(ok, i)) == -1, "an appended component depending on earlier ones is in order");

        // Swap at index 1 whose new type needs the component at index 3: the game would reorder; surgery refuses.
        var late = new Dictionary<int, int[]> { [1] = new[] { 3 } };
        Check(SurgeryRules.FirstOutOfOrder(4, i => Deps(late, i)) == 1, "a dependency on a later component is out of order, reported at the dependent");

        // An existing component whose optional dependency now resolves to the appended one (index n).
        var resolvesToNew = new Dictionary<int, int[]> { [2] = new[] { 4 } };
        Check(SurgeryRules.FirstOutOfOrder(5, i => Deps(resolvesToNew, i)) == 2, "an old component that now depends on the appended one is out of order");

        // Self-dependency is excluded by the game's strategy (injectedComponent != value) but would be caught here too.
        var self = new Dictionary<int, int[]> { [0] = new[] { 0 } };
        Check(SurgeryRules.FirstOutOfOrder(1, i => Deps(self, i)) == 0, "a component cannot depend on its own index");
    }

    /// <summary>Review I2: a swapped slot may carry only the old type's default tag.</summary>
    public static void Retag()
    {
        string[] oldDefault = { "RigidAnimationComponent" };
        string[] newDefault = { "KvmDrawerPart" };

        List<string>? tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent" }, oldDefault, newDefault, out string? why);
        Check(tags != null && tags.Count == 1 && tags[0] == "KvmDrawerPart" && why == null, "the default tag moves to the new type");

        tags = SurgeryRules.Retag(Array.Empty<string>(), oldDefault, newDefault, out why);
        Check(tags != null && tags.Count == 1 && tags[0] == "KvmDrawerPart", "an untagged slot gets the new default tag");

        tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent", "DrawerAnimation" }, oldDefault, newDefault, out why);
        Check(tags == null && why != null && why.Contains("DrawerAnimation"), "an extra data tag refuses the swap and names the tag");

        tags = SurgeryRules.Retag(new[] { "SomethingElse" }, oldDefault, newDefault, out why);
        Check(tags == null && why != null, "a slot tagged only with a non-default tag is refused");

        tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent" }, null, newDefault, out why);
        Check(tags == null && why != null, "an old multi-component (no default tags) is refused when the slot has tags");

        tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent" }, oldDefault, null, out why);
        Check(tags == null && why != null && why.Contains("multi-component"), "a new multi-component is refused");

        tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent" }, oldDefault, new[] { "A", "A" }, out why);
        Check(tags != null && tags.Count == 1, "duplicate default tags collapse to one");

        tags = SurgeryRules.Retag(new[] { "RigidAnimationComponent" }, oldDefault, new[] { "RigidAnimationComponent" }, out why);
        Check(tags != null && tags.Count == 1 && tags[0] == "RigidAnimationComponent", "a new type with the same default tag keeps it");
    }

    /// <summary>The prefab's object builders must line up with the composition, id by id.</summary>
    public static void ObjectBuilderKeys()
    {
        Guid a = Guid.NewGuid(), b = Guid.NewGuid(), c = Guid.NewGuid();
        Check(SurgeryRules.SameSequence<Guid>(new[] { a, b }, new[] { a, b }), "equal keys match");
        Check(!SurgeryRules.SameSequence<Guid>(new[] { b, a }, new[] { a, b }), "the same keys in another order do not match");
        Check(!SurgeryRules.SameSequence<Guid>(new[] { a }, new[] { a, b }), "one object builder short does not match");
        Check(!SurgeryRules.SameSequence<Guid>(new[] { a, b, c }, new[] { a, b }), "one too many does not match");
        Check(SurgeryRules.SameSequence<Guid>(ReadOnlySpan<Guid>.Empty, Array.Empty<Guid>()), "empty matches empty");
    }

    private sealed class FakePrefab
    {
        public readonly string Name;
        public readonly object? Composition;
        public readonly bool Throws;

        public FakePrefab(string name, object? composition, bool throws = false)
        {
            Name = name;
            Composition = composition;
            Throws = throws;
        }

        public object? Read() => Throws ? throw new InvalidOperationException("no entity") : Composition;
    }

    /// <summary>Review I3: a composition used by another prefab is detected before anything changes.</summary>
    public static void SharedComposition()
    {
        object mine = new object(), theirs = new object();
        var self = new FakePrefab("self", mine);

        var alone = new List<FakePrefab> { self, new FakePrefab("other", theirs), new FakePrefab("empty", null) };
        Check(SurgeryRules.FindSharer(alone, self, p => p.Read(), mine) == null, "no other prefab uses the composition");

        var shared = new List<FakePrefab> { new FakePrefab("other", theirs), self, new FakePrefab("twin", mine) };
        Check(SurgeryRules.FindSharer(shared, self, p => p.Read(), mine)?.Name == "twin", "the sharing prefab is found");

        var broken = new List<FakePrefab> { new FakePrefab("broken", null, throws: true), self };
        Check(SurgeryRules.FindSharer(broken, self, p => p.Read(), mine) == null, "a prefab that cannot be read is skipped, not fatal");

        var onlySelf = new List<FakePrefab> { self };
        Check(SurgeryRules.FindSharer(onlySelf, self, p => p.Read(), mine) == null, "the prefab itself is not a sharer");

        // Equal but distinct compositions are not shared: sharing is by reference.
        var lookalike = new List<FakePrefab> { self, new FakePrefab("lookalike", "same"), };
        Check(SurgeryRules.FindSharer(lookalike, self, p => p.Read(), new string('s', 1) + "ame") == null, "sharing is by reference, not equality");
    }

    /// <summary>Review M5: the once-budget announces that it is full, once, and then stays quiet.</summary>
    public static void OnceGateBudget()
    {
        var gate = new OnceGate(3);
        Check(gate.Pass("a") == OnceGate.Verdict.First, "a new key speaks");
        Check(gate.Pass("a") == OnceGate.Verdict.Seen, "a repeated key is quiet");
        Check(gate.Pass(null) == OnceGate.Verdict.First, "null is a key like any other");
        Check(gate.Pass("") == OnceGate.Verdict.Seen, "null and empty are the same key");
        Check(gate.Pass("b") == OnceGate.Verdict.LastBeforeFull, "the key that fills the budget says so");
        Check(gate.Pass("c") == OnceGate.Verdict.Full, "after that a new key is suppressed");
        Check(gate.Pass("a") == OnceGate.Verdict.Seen, "known keys stay quiet when full");
        Check(new OnceGate(0).Pass("x") == OnceGate.Verdict.LastBeforeFull, "capacity is at least one");
    }

    /// <summary>Task 8: edits that must apply together (the KVM's sequencer and its two part drivers) or not at all.</summary>
    public static void CombineVerdicts()
    {
        const SurgeryVerdict R = SurgeryVerdict.Ready, D = SurgeryVerdict.AlreadyDone, X = SurgeryVerdict.Refused;
        Check(SurgeryRules.Combine(new[] { R, R, R }) == R, "all ready: apply");
        Check(SurgeryRules.Combine(new[] { D, D, D }) == D, "all done: nothing to do (a reload)");
        Check(SurgeryRules.Combine(new[] { D, R, D }) == R, "some done, some ready (a reload restored one target): apply the ready ones");
        Check(SurgeryRules.Combine(new[] { R, R, X }) == X, "one refused: apply none (a sequencer without parts, or parts without a sequencer)");
        Check(SurgeryRules.Combine(new[] { X, D, D }) == X, "refused beside done ones: still refused");
        Check(SurgeryRules.Combine(new[] { R, (SurgeryVerdict)9 }) == X, "an unknown verdict counts as refused");
        Check(SurgeryRules.Combine(Array.Empty<SurgeryVerdict>()) == D, "no edits: done");
    }
}
