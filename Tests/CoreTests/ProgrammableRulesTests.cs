// Tests of the Programmable's game-free rules: Scripts/Client/Core/StatusLampRules.cs (the scripted status lamp)
// and Scripts/Simulation/Shared/Core/ScriptingPresence.cs (the read-only scripting check).
// Mesh parts and materials are strings here; the game's StringId and MaterialDefinition (compared by GUID) behave alike.
#nullable enable
using System;
using System.Collections.Generic;
using DataCenter.Programmable.Core;
using DataCenter.Shared.Core;

internal static class StatusLampRulesTests
{
    private const string Part = "EmissiveScriptStatus";
    private const string Green = "EmissiveGreen";

    private static void Check(bool ok, string name) => Program.Check(ok, name);

    private static readonly Func<string, string, bool> Same = (a, b) => a == b;

    private static Dictionary<string, string> Map(params (string Part, string Material)[] entries)
    {
        var d = new Dictionary<string, string>();
        foreach ((string p, string m) in entries)
            d[p] = m;
        return d;
    }

    /// <summary>The data ships an empty map over two models: the lamp is added, once.</summary>
    public static void AddsOnce()
    {
        var data = Map();
        Check(StatusLampRules.Decide(2, data, Part, Green, Same, out string? why) == LampSwapVerdict.Add && why == null,
            "an empty map over our models gets the lamp");

        Dictionary<string, string> next = StatusLampRules.With(data, Part, Green);
        Check(data.Count == 0, "the definition's own map is never modified");
        Check(next.Count == 1 && next[Part] == Green, "the new map holds the lamp");

        Check(StatusLampRules.Decide(2, next, Part, Green, Same, out why) == LampSwapVerdict.AlreadyMapped && why == null,
            "a second pass (definition reload) changes nothing");
    }

    /// <summary>Other mappings are kept as they are, in order; the rule only ever adds.</summary>
    public static void KeepsOtherMappings()
    {
        var data = Map(("EmissiveOff", Green), ("Fracture_01_Hide-EmissiveOff", Green));
        Check(StatusLampRules.Decide(1, data, Part, Green, Same, out _) == LampSwapVerdict.Add, "unrelated mappings do not block the lamp");

        Dictionary<string, string> next = StatusLampRules.With(data, Part, Green);
        var keys = new List<string>(next.Keys);
        Check(keys.Count == 3 && keys[0] == "EmissiveOff" && keys[1] == "Fracture_01_Hide-EmissiveOff" && keys[2] == Part,
            "existing entries keep their order, the lamp comes last");
        Check(next["EmissiveOff"] == Green && data.Count == 2, "existing values unchanged, original untouched");
    }

    /// <summary>Refusals: never fight another owner of the mesh part, never map into a swapper that applies nowhere.</summary>
    public static void Refusals()
    {
        var owned = Map((Part, "EmissiveRed"));
        Check(StatusLampRules.Decide(2, owned, Part, Green, Same, out string? why) == LampSwapVerdict.Conflict
              && why != null && why.Contains(Part), "a part mapped to another material is left alone, and the reason names it");

        Check(StatusLampRules.Decide(0, Map(), Part, Green, Same, out why) == LampSwapVerdict.NoModels && why != null,
            "a swapper with no model is refused");

        Check(StatusLampRules.Decide(2, Map(), Part, null, Same, out why) == LampSwapVerdict.Missing && why != null,
            "a missing lit material (not loaded) is refused");

        Check(StatusLampRules.Decide<string, string>(2, null, Part, Green, Same, out why) == LampSwapVerdict.Add,
            "a null map is treated as empty");

        Check(StatusLampRules.Decide(2, Map((Part, null!)), Part, Green, Same, out why) == LampSwapVerdict.Conflict,
            "a part mapped to a null material counts as owned, not as ours");
    }
}

/// <summary>Tests of Scripts/Simulation/Shared/Core/ScriptingPresence.cs (the Programmable's read-only scripting check).</summary>
internal static class ScriptingPresenceTests
{
    private static void Check(bool ok, string name) => Program.Check(ok, name);

    public static void Verdicts()
    {
        Guid def = Guid.NewGuid();
        Check(ScriptingPresence.Judge(5, true, def, def) == ScriptingVerdict.Present, "the data's shape is Present");
        Check(ScriptingPresence.Judge(-1, false, null, def) == ScriptingVerdict.Missing, "no id: Missing");
        Check(ScriptingPresence.Judge(5, false, def, def) == ScriptingVerdict.WrongType, "another type under the id: WrongType");
        Check(ScriptingPresence.Judge(5, true, null, def) == ScriptingVerdict.WrongDefinition, "no definition: WrongDefinition");
        Check(ScriptingPresence.Judge(5, true, Guid.NewGuid(), def) == ScriptingVerdict.WrongDefinition, "another definition: WrongDefinition");
        foreach (ScriptingVerdict v in Enum.GetValues(typeof(ScriptingVerdict)))
            Check(ScriptingPresence.Describe(v, "DC_Srv_Programmable").Contains("'DC_Srv_Programmable'"), $"the {v} line names the prefab");
        Check(ScriptingPresence.Describe(ScriptingVerdict.Present, "X").StartsWith("programmable: scripting available"),
            "the Present line is the one the in-game checklist looks for");
    }
}
