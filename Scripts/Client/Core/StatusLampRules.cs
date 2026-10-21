// StatusLampRules: the game-free decision behind the Programmable's scripted status lamp (Plan 4 Ruling P4-7).
// Generic over the mesh-part key and the material, so Tests/CoreTests runs it with strings; the game glue
// (Scripts/Client/Programmable/ProgrammableLedInjector.cs) runs it with StringId and MaterialDefinition.
//
// Game APIs: none.
#nullable enable
using System;
using System.Collections.Generic;

namespace DataCenter.Programmable.Core;

/// <summary>What to do with a material swapper's Working mesh-part map.</summary>
public enum LampSwapVerdict
{
    /// <summary>Add the lit material under the status mesh part.</summary>
    Add,

    /// <summary>Already mapped to the lit material (a definition reload, or data that maps it itself): nothing to do.</summary>
    AlreadyMapped,

    /// <summary>The mesh part is mapped to another material: someone else owns it (data or another mod); leave it.</summary>
    Conflict,

    /// <summary>The swapper lists no model, so a mapping would never apply: the data is not what the script expects.</summary>
    NoModels,

    /// <summary>The lit material or the mesh part name is missing.</summary>
    Missing,
}

/// <summary>
/// Decides how the status lamp's mesh part joins a swapper's Working replacements, without touching the game.
/// <para>The rule is additive and conservative: it only ever adds one entry, never rewrites or removes one, so the
/// data's own mappings (and a later data change that maps the part itself) always win.</para>
/// </summary>
public static class StatusLampRules
{
    /// <summary>The verdict for adding <paramref name="part"/> -&gt; <paramref name="lit"/> to <paramref name="existing"/>.</summary>
    /// <param name="modelCount">How many models the swapper applies its replacements to.</param>
    /// <param name="existing">The swapper's current Working mesh-part map.</param>
    /// <param name="part">The status lamp's mesh part.</param>
    /// <param name="lit">The material the lamp takes while the block is Working.</param>
    /// <param name="sameMaterial">Material identity (the game compares definitions by GUID).</param>
    /// <param name="why">For every verdict but <see cref="LampSwapVerdict.Add"/> and
    /// <see cref="LampSwapVerdict.AlreadyMapped"/>: a reason fit for the log.</param>
    public static LampSwapVerdict Decide<TPart, TMaterial>(int modelCount, IEnumerable<KeyValuePair<TPart, TMaterial>>? existing,
        TPart part, TMaterial? lit, Func<TMaterial, TMaterial, bool> sameMaterial, out string? why)
        where TPart : notnull
        where TMaterial : class
    {
        why = null;
        if (part == null || lit == null || sameMaterial == null)
        {
            why = "the lit material or the status mesh part is missing";
            return LampSwapVerdict.Missing;
        }

        if (modelCount <= 0)
        {
            why = "the swapper lists no model, so a replacement would never apply";
            return LampSwapVerdict.NoModels;
        }

        if (existing != null)
        {
            foreach (KeyValuePair<TPart, TMaterial> entry in existing)
            {
                if (!EqualityComparer<TPart>.Default.Equals(entry.Key, part))
                    continue;

                if (entry.Value != null && sameMaterial(entry.Value, lit))
                    return LampSwapVerdict.AlreadyMapped;

                why = $"mesh part '{part}' is already mapped to another material; leaving that mapping alone";
                return LampSwapVerdict.Conflict;
            }
        }

        return LampSwapVerdict.Add;
    }

    /// <summary>
    /// A new map: every entry of <paramref name="existing"/>, in order, plus <paramref name="part"/> -&gt;
    /// <paramref name="lit"/>. The original is never modified (the definition may share it).
    /// </summary>
    public static Dictionary<TPart, TMaterial> With<TPart, TMaterial>(IEnumerable<KeyValuePair<TPart, TMaterial>>? existing,
        TPart part, TMaterial lit)
        where TPart : notnull
    {
        var map = new Dictionary<TPart, TMaterial>();
        if (existing != null)
        {
            foreach (KeyValuePair<TPart, TMaterial> entry in existing)
                map[entry.Key] = entry.Value;
        }

        map[part] = lit;
        return map;
    }
}
