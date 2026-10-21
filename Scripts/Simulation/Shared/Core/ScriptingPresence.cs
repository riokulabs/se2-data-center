// ScriptingPresence: the game-free verdict on whether a prefab carries the scripting component the way the data
// ships it (Plan 4 Ruling P4-1 = A': the Programmable's InGameScriptingComponent lives permanently in its data).
// Tests/CoreTests runs it; Scripts/Simulation/Programmable/ProgrammableCheck.cs feeds it the game's composition.
//
// Game APIs: none.
#nullable enable
using System;

namespace DataCenter.Shared.Core;

/// <summary>What a read-only look at a prefab's scripting slot found.</summary>
public enum ScriptingVerdict
{
    /// <summary>The component sits under its id, of the scripting type, bound to the expected definition.</summary>
    Present,

    /// <summary>No component under the id: the data (or another mod) removed it; the block cannot run a program.</summary>
    Missing,

    /// <summary>Something else sits under the id.</summary>
    WrongType,

    /// <summary>The scripting component is bound to no definition, or to another one than the data's.</summary>
    WrongDefinition,
}

/// <summary>Reads the result of one prefab's scripting-slot lookup into a verdict and a log line.</summary>
public static class ScriptingPresence
{
    /// <param name="index">The component id's index in the composition, or -1.</param>
    /// <param name="isScriptingType">Whether the component type at <paramref name="index"/> is the scripting component.</param>
    /// <param name="definition">The GUID of the definition bound at <paramref name="index"/>, or null when none.</param>
    /// <param name="expectedDefinition">The data's scripting definition.</param>
    public static ScriptingVerdict Judge(int index, bool isScriptingType, Guid? definition, Guid expectedDefinition)
    {
        if (index < 0)
            return ScriptingVerdict.Missing;

        if (!isScriptingType)
            return ScriptingVerdict.WrongType;

        return definition == expectedDefinition ? ScriptingVerdict.Present : ScriptingVerdict.WrongDefinition;
    }

    /// <summary>A log line for <paramref name="verdict"/> on the prefab called <paramref name="name"/>.</summary>
    public static string Describe(ScriptingVerdict verdict, string name)
    {
        switch (verdict)
        {
            case ScriptingVerdict.Present:
                return $"programmable: scripting available on '{name}' (component in data, Route A')";

            case ScriptingVerdict.Missing:
                return $"programmable: '{name}' has no scripting component; its Run cannot work (data changed by another mod?)";

            case ScriptingVerdict.WrongType:
                return $"programmable: '{name}' holds another component under the scripting id; its Run cannot work";

            default:
                return $"programmable: '{name}' scripting component is bound to an unexpected definition; limits and entry point may differ";
        }
    }
}
