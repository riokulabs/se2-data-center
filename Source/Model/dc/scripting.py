"""The Programmable's in-game scripting, as DATA (Plan 4 Ruling P4-1 = Route A'; plain Python, no bpy).

The vanilla InGameScriptingComponent sits permanently in the Programmable's server composition, with this
InGameScriptingDefinition and, in the server prefab, an InGameScriptingObjectBuilder holding the starter program. The
data is the same with and without -loadScripts, so a world saves and loads identically in both modes and a player's
program text is never dropped (the reason A' beat runtime injection: docs/research/dc-scripts-save-safety.md §4).

Without -loadScripts the in-game whitelist and MetaDatas are empty (GameWhitelistProvider.cs:30,
GameCompilationDescriptor.cs:13), so Run / Check / Debug end in an ordinary compile error (§2 of the research doc):
"just won't run til keen enables it" (the user). With the switch the same block runs the program.

Engine facts (decompiled 2.4.0.95, tools/decompiled/Game2.Simulation/Keen.Game2.Simulation.Scripting/):
  InGameScriptingComponent.cs:55-60    Init(ob): Script, Running from the object builder
  InGameScriptingComponent.cs:69-75    OnAddedToScene: compiles and runs only when the saved Running is true
  InGameScriptingComponent.cs:173-191  LoadScript dereferences every definition field below unconditionally
  InGameScriptingDefinition.cs:401-457 EntryTypeName, UpdateMethodName, the three LocKeys, the limits (code defaults)
  InGameScriptingObjectBuilder.cs:562,567  Script, Running
Vanilla 2.4 ships no block with this component, so there is no definition to copy: ours is a full .def.
"""
from . import config

DEFINITION_TYPE = "Game2:Keen.Game2.Simulation.Scripting.InGameScriptingDefinitionObjectBuilder"
COMPONENT_TYPE = "Game2:Keen.Game2.Simulation.Scripting.InGameScriptingComponent"
OB_TYPE = "Game2:Keen.Game2.Simulation.Scripting.InGameScriptingObjectBuilder"
DEFINITION_FILE = f"{config.NAME}/DC_Srv_Programmable/DC_Srv_Programmable_InGameScriptingDefinition.def"
DEFINITION_KEY = "Programmable.InGameScriptingDefinition"   # asset_guids.json: the definition's GUID
COMPONENT_KEY = "Programmable.ScriptingComponentId"         # asset_guids.json: its component id in the composition

# The sandbox limits: the engine's own code defaults (InGameScriptingDefinition.cs:427-457), written out so the
# definition does not depend on a default a game update might change silently.
LIMITS = ("MaxInstructions", "MaxMethodStackSize", "MaxStackSize", "MaxAccumulatedMemory", "MaxInitMemory",
          "MaxUpdateMemory")
DEFINITION = {
    # OldScriptSignature.cs:41-60: the entry class EntryTypeName with a ctor (Entity) and a public Update()
    "EntryTypeName": "Program",
    "UpdateMethodName": "Update",
    # vanilla's own texts (GameData/Vanilla/Content/MainMenuData/Texts/*/MainGameTexts.loc-texts)
    "NoProgram": "ProgramableBlockNoProgram",
    "NoConstructor": "ProgramableBlockNoConstructor",
    "ProgramCompileSuccess": "ProgramableBlockSuccess",
    "MaxInstructions": 50000,
    "MaxMethodStackSize": 1024,
    "MaxStackSize": 1048576,
    "MaxAccumulatedMemory": 5242880,
    "MaxInitMemory": 1048576,
    "MaxUpdateMemory": 102400,
}

# The program a newly built Programmable shows in its terminal script editor. It compiles under the in-game whitelist
# (GameApp.cs:496 [2.4: 465]: VRage.DCS is admitted through typeof(Entity)) and does nothing until the player writes something.
TEMPLATE = """\
// PRG-06 script host: the Data Center programmable server.
// Write your program here, then press Check and Run in this block's terminal.
// Scripts run only when the game is started with -loadScripts; without it, Run reports a compile error.
using Keen.VRage.DCS.Components;

public class Program
{
    // This programmable server.
    private readonly Entity _block;

    // Called once when the program is started.
    public Program(Entity block)
    {
        _block = block;
    }

    // Called on every simulation update while the program runs.
    public void Update()
    {
    }
}
"""


def definition(guid):
    """The InGameScriptingDefinition's $Value (a full definition, no BaseDefinition)."""
    return dict({"Guid": guid}, **DEFINITION)


def object_builder():
    """The server prefab's InGameScriptingObjectBuilder: the starter program, not running."""
    return {"$Type": OB_TYPE, "Script": TEMPLATE, "Running": False}
