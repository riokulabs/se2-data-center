// Data Center scripts: in-game probe. Sections 1-4: is the scripting switch on, did the mod's script
// assemblies load, and do the reflection targets of Scripts/Simulation/Shared/CompositionSurgery.cs still exist?
// Sections 5-6: the Programmable, server and client side, and the "[DataCenter]" lines of this session's
// log. Section 7: the scripted KVM (the injection, each KVM's sequencer, its rack link and its parts
// against their rest poses), the CompositionSurgery refusal paths (prepared only, never applied), and an opt-in
// fault-injection pass (7d; off by default, it leaves one KVM faulted until the world is reloaded).
//
// Compile it offline first, the way se-mcp compiles it (its usings and wrapper, the game's assemblies):
//   mods/DataCenter/Tests/CompileCheck/run.sh probe mods/DataCenter/Tests/InGame/probe_scripts.csx
// Run with a world loaded (read-only unless 7d is switched on):
//   tools/scripts/se2game.py exec -f mods/DataCenter/Tests/InGame/probe_scripts.csx
// or through the se2-game MCP execute_code (usings: System.Linq, System.Reflection, System.Collections.Generic).
// Then look for the "[DataCenter]" lines in the game log (CompositionSurgery and the injectors log there).
string Mark(bool ok) => ok ? "ok  " : "FAIL";
var asms = AppDomain.CurrentDomain.GetAssemblies();
Assembly Asm(string name) => asms.FirstOrDefault(a => { try { return a.GetName().Name == name; } catch { return false; } });
Type Find(string fullName) => asms.Select(a => { try { return a.GetType(fullName, false); } catch { return null; } }).FirstOrDefault(t => t != null);

// 1. The switch (GameApp.cs:330-333): without it the game never compiles Scripts/.
bool switchOn = Environment.GetCommandLineArgs().Any(a => a == "-loadScripts");
Console.WriteLine($"{Mark(switchOn)} -loadScripts on the command line");

// 2. The script assemblies (ScriptCodeProvider.cs:77, 89): "<vrgproj Name>.<Sub>".
var sim = Asm("DataCenter.Simulation");
var client = Asm("DataCenter.Client");
Console.WriteLine($"{Mark(sim != null || !switchOn)} DataCenter.Simulation loaded: {sim != null}");
Console.WriteLine($"{Mark(client != null || !switchOn)} DataCenter.Client loaded: {client != null}");

// 3. The reflection targets, read from the game itself (REFLECTION: EntityCompositeDefinition.cs:568, PrefabDefinition.cs:219).
var composite = Find("Keen.VRage.DCS.Definitions.EntityCompositeDefinition");
var builder = Find("Keen.VRage.DCS.Definitions.EntityCompositeDefinition+Builder");
var prefab = Find("Keen.VRage.Core.Game.Definitions.PrefabDefinition");
var assign = composite == null || builder == null ? null
    : composite.GetMethod("Assign", BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { builder }, null);
var entityField = prefab?.GetField("_entity", BindingFlags.Instance | BindingFlags.NonPublic);
Console.WriteLine($"{Mark(assign != null)} EntityCompositeDefinition.Assign(Builder): {assign}");
Console.WriteLine($"{Mark(entityField != null)} PrefabDefinition._entity: {entityField?.FieldType}");

// 4. The same answer from inside the mod (its static lookups ran in the script's own context).
if (sim != null)
{
    var surgery = sim.GetType("DataCenter.Shared.CompositionSurgery", false);
    object found = null;
    try { found = surgery?.GetProperty("ReflectionTargetsFound", BindingFlags.Public | BindingFlags.Static)?.GetValue(null); } catch { }
    Console.WriteLine($"{Mark(found is true)} CompositionSurgery.ReflectionTargetsFound: {found ?? "(type missing)"}");
}

// 5. The Programmable. Reflection only, every access wrapped: a missing member prints, never throws.
//    Place one DC_Srv_Programmable first; toggle it Off and On between two runs to see the lamp follow Working.
object Get(object o, string n) {
    try {
        var t = o?.GetType();
        for (; t != null; t = t.BaseType) {
            var p = t.GetProperty(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
            if (p != null) return p.GetValue(o);
            var f = t.GetField(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
            if (f != null) return f.GetValue(o);
        }
    } catch { }
    return null;
}
IEnumerable<object> Items(object o) { try { return (o as System.Collections.IEnumerable)?.Cast<object>().ToList() ?? new List<object>(); } catch { return new List<object>(); } }
string Keys(object map) => string.Join(", ", Items(map).Select(kv => $"{Get(kv, "Key")} -> {Get(kv, "Value")}"));
const string StatusPart = "EmissiveScriptStatus";     // DcGuids.ProgrammableStatusMeshPart (dc/functional.py PROG_LED)

if (client != null)
{
    object found = null;
    try { found = client.GetType("DataCenter.Programmable.ProgrammableLedInjector", false)?.GetProperty("ReflectionTargetsFound", BindingFlags.Public | BindingFlags.Static)?.GetValue(null); } catch { }
    Console.WriteLine($"{Mark(found is true)} ProgrammableLedInjector.ReflectionTargetsFound: {found ?? "(type missing)"}");
}

object app = null;
try { app = Singleton<VRageCore>.Instance.Engine.Get<GameAppComponent>(); } catch { }
foreach (var side in new[] { "ServerSession", "ClientSession" })
{
    var session = Get(app, side);
    if (session == null) { Console.WriteLine($"     {side}: none"); continue; }
    int n = 0;
    foreach (var e in Items(Get(session, "Entities")))
    {
        object cb = null;
        try { cb = ((Keen.VRage.DCS.Components.Entity)e).TryGet<CubeBlockComponent>(); } catch { }
        string def = cb == null ? null : (Get(cb, "Definition")?.ToString() ?? "");
        if (def == null || !def.Contains("DC_Srv_Programmable")) continue;
        if (++n > 3) { Console.WriteLine($"     {side}: more Programmables not shown"); break; }
        var comps = Items(Get(e, "Components")).Where(c => c != null).Select(c => c.GetType().Name).ToList();
        Console.WriteLine($"== {side} {Get(e, "DebugName") ?? e}: {comps.Count} components: {string.Join(", ", comps)}");
        bool scripting = comps.Contains("InGameScriptingComponent");
        try { scripting |= ((Keen.VRage.DCS.Components.Entity)e).TryGet(Keen.VRage.Library.Utils.StringId.Get("InGameScriptingComponent")) != null; } catch { }   // the data's tag slot
        if (side == "ServerSession")
            Console.WriteLine($"{Mark(scripting)} InGameScriptingComponent present (Route A': always, both modes)");
        else
            Console.WriteLine($"{Mark(!scripting)} no InGameScriptingComponent on the client (server-side only, no double run)");
        object working = null;
        foreach (var c in Items(Get(e, "Components")))
            if (c?.GetType().Name == "PowerableBlockComponent") working = Get(c, "Working");
        if (working != null) Console.WriteLine($"     Working: {working}");
        if (side != "ClientSession") continue;
        foreach (var c in Items(Get(e, "Components")).Where(c => c?.GetType().Name == "BlockMaterialSwapperComponent"))
        {
            var sd = Get(c, "_definition");
            var parts = Get(sd, "WorkingReplacementsMeshParts");
            bool mapped = Items(parts).Any(kv => Get(kv, "Key")?.ToString() == StatusPart);
            Console.WriteLine($"     swapper {Get(sd, "Guid")}: models {Items(Get(sd, "WorkingReplacementModels")).Count()}, mesh parts [{Keys(parts)}]");
            Console.WriteLine($"     processed: {Items(Get(sd, "ProcessedWorkingMaterialReplacements")).Count()} model(s); component's current: {Items(Get(c, "_materialReplacements")).Count()} model(s)");
            Console.WriteLine($"{Mark(mapped == switchOn)} status part '{StatusPart}' mapped to green: {mapped} (expected {switchOn}: scripts {(switchOn ? "on" : "off")})");
        }
    }
    if (n == 0) Console.WriteLine($"     {side}: no DC_Srv_Programmable placed");
}

// 7. The scripted KVM. Place KVMs in a SplitFront rack (doors closed, KVM On), in an Open rack, in
//    a 42U top slot, and one standalone. Reflection only; every access is wrapped.
bool kvmFaultPass = false;   // 7d: set true for the fault pass (faults ONE KVM until reload)
const BindingFlags Any = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
Type KT(string n) => client?.GetType(n, false);
object St(Type t, string n) { try { return t?.GetProperty(n, Any)?.GetValue(null); } catch { return null; } }
object Call(object target, Type t, string name, params object[] args) {
    var m = t?.GetMethods(Any).FirstOrDefault(x => x.Name == name && x.GetParameters().Length == args.Length);
    if (m == null) throw new MissingMethodException(t?.Name, name);
    return m.Invoke(target, args);
}
object CompOf(object entity, string typeName) => Items(Get(entity, "Components")).FirstOrDefault(c => c?.GetType().Name == typeName);
IEnumerable<object> ChildrenOf(object entity) => Items(Get(CompOf(entity, "HierarchyComponent"), "Children"));
string F(object v) => v is float f ? f.ToString("0.000") : (v?.ToString() ?? "null");

var injT = KT("DataCenter.Kvm.KvmInjector");
var seqT = KT("DataCenter.Kvm.KvmSequencerComponent");
var drawerT = KT("DataCenter.Kvm.KvmDrawerPart");
var screenT = KT("DataCenter.Kvm.KvmScreenPart");
if (switchOn && client != null)
{
    var state = St(injT, "State");
    Console.WriteLine($"{Mark(state?.ToString() == "Applied")} KvmInjector.State: {state ?? "(type missing)"}, applications {St(injT, "Applications")}");
}

// 7a. Save safety: no KVM script type on any server entity (only client prefabs are injected).
{
    var server = Get(app, "ServerSession");
    int scripted = Items(Get(server, "Entities")).Count(e => Items(Get(e, "Components")).Any(c => c?.GetType().Namespace?.StartsWith("DataCenter") == true));
    Console.WriteLine($"{Mark(scripted == 0)} server entities with a DataCenter script component: {scripted}");
}

// 7b. Each KVM on the client: the sequencer, the rack link, the parts against their rest poses.
var kvms = new List<object>();
foreach (var e in Items(Get(Get(app, "ClientSession"), "Entities")))
    if (CompOf(e, "KvmSequencerComponent") != null) kvms.Add(e);
Console.WriteLine($"     client KVMs with a sequencer: {kvms.Count}{(switchOn ? "" : " (scripts off: expected 0)")}");
Console.WriteLine($"{Mark(switchOn || kvms.Count == 0)} no sequencer without the switch");
foreach (var e in kvms.Take(8))
{
    var s = CompOf(e, "KvmSequencerComponent");
    var core = Get(s, "Core");
    var link = Get(s, "RackLink");
    object working = Get(CompOf(e, "PowerableBlockComponent"), "Working");
    var door = Get(link, "FrontDoorState");
    Console.WriteLine($"== KVM {Get(e, "DebugName") ?? e}: Working {working}, pose {Get(s, "Pose")}, target {Get(s, "Target")}, path {Get(s, "Path")}, settled {Get(core, "Settled")}, faulted {Get(s, "Faulted")} ({Get(core, "Faults")} faults)");
    Console.WriteLine($"     link: front block {Get(Get(link, "FrontBlock"), "DebugName") ?? "none"}, door {door ?? "none"}, rack {Get(link, "RackKind")}, slot {Get(link, "Slot")}, path {Get(link, "Path")}, resolves {Get(link, "Resolves")}; in scene {F(Get(core, "SecondsInScene"))} s, door open {F(Get(core, "DoorOpenFor"))} s");
    Console.WriteLine($"     face side {Get(link, "FaceSide")} (+1 the rack's front, -1 its rear), rack leaves {Get(link, "DoorSides")}, door off the face (ignored): {Get(link, "DoorOffFace")}");
    string d = door?.ToString();
    string want = d == "Closing" || d == "Closed" ? "Stowed|FastStow" : working is true && (d == null || d == "Open") ? "Out" : "Stowed";
    Console.WriteLine($"{Mark(want.Split('|').Contains(Get(s, "Target")?.ToString()))} target {Get(s, "Target")} (expected {want}: the door interlock)");
    bool topOfFull = Get(link, "RackKind")?.ToString() == "Full" && Get(link, "Slot") is int slot && slot == 8;
    Console.WriteLine($"{Mark((Get(link, "Path")?.ToString() == "DataOnly") == topOfFull)} link path {Get(link, "Path")} (data-only exactly in a 42U top slot)");

    foreach (var drawer in ChildrenOf(e))
    {
        var dp = CompOf(drawer, "KvmDrawerPart");
        var dv = CompOf(drawer, "TranslationAnimationComponent");
        if (dp == null && dv == null) continue;
        if (dp == null) { Console.WriteLine($"FAIL drawer {Get(drawer, "DebugName")}: still the vanilla TranslationAnimationComponent"); continue; }
        try
        {
            var rest = (Keen.VRage.Core.RelativeTransform)Get(dp, "Rest");
            var now = (Keen.VRage.Core.RelativeTransform)Get(CompOf(drawer, "ChildTransformComponent"), "ChildTransform");
            var pose = Get(s, "Pose");
            float slide = (float)Get(pose, "Slide"), fold = (float)Get(pose, "Fold");
            var travel = (Keen.VRage.Library.Mathematics.Vector3)Get(Get(dp, "Definition"), "Translation");
            var expect = rest.Position + travel * slide;
            float err = (now.Position - expect).Length();
            Console.WriteLine($"{Mark(err < 1e-3f)} drawer: offset {(now.Position - rest.Position)} = travel {travel} x slide {slide:0.000} (error {err * 1000:0.0} mm); sequencer {Get(dp, "Sequencer") != null}, faulted {Get(dp, "Faulted")}");
            foreach (var screen in ChildrenOf(drawer))
            {
                var sp = CompOf(screen, "KvmScreenPart");
                if (sp == null) { if (CompOf(screen, "RotationAnimationComponent") != null) Console.WriteLine("FAIL screen: still the vanilla RotationAnimationComponent"); continue; }
                var srest = (Keen.VRage.Core.RelativeTransform)Get(sp, "Rest");
                var snow = (Keen.VRage.Core.RelativeTransform)Get(CompOf(screen, "ChildTransformComponent"), "ChildTransform");
                var def = Get(sp, "Definition");
                var axis = (Keen.VRage.Library.Mathematics.Vector3)Get(def, "Axis");
                float angle = (float)Get(def, "Angle");
                var q = srest.Orientation * Keen.VRage.Library.Mathematics.Quaternion.CreateFromAxisAngle(axis, angle * fold);
                float dot = Math.Abs(q.X * snow.Orientation.X + q.Y * snow.Orientation.Y + q.Z * snow.Orientation.Z + q.W * snow.Orientation.W);
                Console.WriteLine($"{Mark(dot > 0.99999f)} screen: fold {fold:0.000} x {angle * 180 / Math.PI:0} deg about {axis} (|dot| {dot:0.000000}; LidAxisSign +1); sequencer {Get(sp, "Sequencer") != null}, faulted {Get(sp, "Faulted")}");
            }
        }
        catch (Exception ex) { Console.WriteLine($"FAIL reading the parts: {ex.GetType().Name}: {ex.Message}"); }
    }
}

// 7c. The CompositionSurgery refusal paths: PREPARED ONLY, never applied, so nothing changes.
var surgeryT = sim?.GetType("DataCenter.Shared.CompositionSurgery", false);
if (switchOn && surgeryT != null && seqT != null)
{
    var dm = Keen.VRage.Library.Utils.Singleton<Keen.VRage.Library.Definitions.DefinitionManager>.Instance;
    var guids = sim.GetType("DataCenter.Shared.DcGuids", false);
    Keen.VRage.Library.Definitions.Definition Def(string field) { try { return dm.TryGetDefinition((Guid)guids.GetField(field).GetValue(null), out Keen.VRage.Library.Definitions.Definition d) ? d : null; } catch { return null; } }
    var prefabs = dm.GetDefinitionsOfTypeAndDescendants<Keen.VRage.Core.Game.Definitions.PrefabDefinition>().ToList();
    var composites = dm.GetDefinitionsOfTypeAndDescendants<Keen.VRage.DCS.Definitions.EntityCompositeDefinition>().ToList();
    string Add(object target, Type type) { try { var a = new object[] { target, Guid.NewGuid(), type, null, null, prefabs, null }; return Call(null, surgeryT, "PrepareAdd", a)?.ToString(); } catch (Exception ex) { return "THREW " + ex.GetType().Name; } }
    string Swap(object target, Type from, Type to) { try { var a = new object[] { target, from, to, null, null }; return Call(null, surgeryT, "PrepareSwap", a)?.ToString(); } catch (Exception ex) { return "THREW " + ex.GetType().Name; } }
    var transT = typeof(Keen.VRage.Core.Game.GameSystems.RigidAnimations.TranslationAnimationComponent);
    var rotT = typeof(Keen.VRage.Core.Game.GameSystems.RigidAnimations.RotationAnimationComponent);
    var kvmPrefab = Def("KvmClientPrefab") as Keen.VRage.Core.Game.Definitions.PrefabDefinition;
    var drawerComposite = Def("KvmDrawerComposite") as Keen.VRage.DCS.Definitions.EntityCompositeDefinition;
    var drawerPrefab = prefabs.FirstOrDefault(p => { try { return ReferenceEquals(p.Composition, drawerComposite); } catch { return false; } });
    var shared = prefabs.GroupBy(p => { try { return (object)p.Composition; } catch { return null; } }).FirstOrDefault(g => g.Key != null && g.Count() > 1)?.First();
    var vanillaTranslation = composites.FirstOrDefault(c => c != drawerComposite && c.Types.Contains(transT));
    void Expect(string what, string got, string want) => Console.WriteLine($"{Mark(got == want)} surgery refusal path: {what}: {got} (expected {want})");
    Expect("add to a null prefab", Add(null, seqT), "Refused");
    Expect("add the sequencer to the KVM prefab again", Add(kvmPrefab, seqT), "AlreadyDone");
    Expect("add the sequencer where its PowerableBlockComponent is missing (the drawer subpart)", drawerPrefab == null ? "no drawer prefab" : Add(drawerPrefab, seqT), "Refused");
    Expect("add to a prefab whose composition is shared", shared == null ? "Refused (none shared)" : Add(shared, seqT), "Refused");
    // ... and refused for the right reason: the sharing check, not an earlier one
    bool sharedLogged = false;
    try
    {
        string logPath = Keen.VRage.Library.Diagnostics.Log.Default?.FileName;
        using (var fs = new System.IO.FileStream(logPath, System.IO.FileMode.Open, System.IO.FileAccess.Read, System.IO.FileShare.ReadWrite | System.IO.FileShare.Delete))
        using (var rd = new System.IO.StreamReader(fs))
            sharedLogged = rd.ReadToEnd().Contains("its composition is shared with");
    }
    catch { }
    Console.WriteLine($"{Mark(shared == null || sharedLogged)} the shared case was refused by the sharing check (log line 'its composition is shared with ...'): {sharedLogged}");
    Expect("swap the drawer again", Swap(drawerComposite, transT, drawerT), "AlreadyDone");
    Expect("swap a type the composite lacks", Swap(drawerComposite, rotT, screenT), "Refused");
    Expect("swap into a driver that takes another definition type", vanillaTranslation == null ? "Refused (no vanilla translation)" : Swap(vanillaTranslation, transT, drawerT), "Refused");
    Console.WriteLine("     (each Refused above logs one '[DataCenter] could not ...' line, listed in section 6)");
}

// 7d. Fault injection (opt-in, see kvmFaultPass): on the first KVM only, best SETTLED (switched On or Off a few seconds
//     earlier). Notes: the drawer's job is run on a scratch copy of its transform, but it does record that
//     pose as applied, so on a moving KVM the next real frame may skip one write; the sequencer's Update is called off
//     the job schedule (a benign race with the real job); and the "destroyed child" is a live child entity planted as
//     the cached rack, which exercises the same per-frame re-resolve a destroyed rack would.
if (kvmFaultPass && kvms.Count > 0)
{
    var e = kvms[0];
    var s = CompOf(e, "KvmSequencerComponent");
    var core = Get(s, "Core");
    var link = Get(s, "RackLink");
    void Tick(string what) {
        try { Call(null, seqT, "Update", s); Console.WriteLine($"ok   {what}: no exception; faults {Get(core, "Faults")}, faulted {Get(s, "Faulted")}, resolves {Get(link, "Resolves")}, front {Get(Get(link, "FrontBlock"), "DebugName") ?? "none"}"); }
        catch (Exception ex) { Console.WriteLine($"FAIL {what}: {ex.GetType().Name}: {(ex.InnerException ?? ex).Message}"); }
    }
    Console.WriteLine($"== fault pass on {Get(e, "DebugName")}: front {Get(Get(link, "FrontBlock"), "DebugName") ?? "none"}, resolves {Get(link, "Resolves")}");
    try { Call(link, link.GetType(), "Forget"); } catch (Exception ex) { Console.WriteLine($"FAIL Forget: {ex.Message}"); }
    Tick("update with the cached rack forcibly nulled (it re-resolves)");
    var child = ChildrenOf(e).FirstOrDefault();
    try { Call(link, link.GetType(), "Poison", child); } catch (Exception ex) { Console.WriteLine($"FAIL Poison: {ex.Message}"); }
    Tick("update with a stale child entity as the cached rack (the per-frame check re-resolves)");
    var part = child == null ? null : CompOf(child, "KvmDrawerPart");
    if (part != null)
    {
        try
        {
            var scratch = (Keen.VRage.Core.RelativeTransform)Get(part, "Rest");   // a copy: the entity's transform is untouched
            Call(null, drawerT, "Apply", scratch, part);
            Console.WriteLine("ok   the drawer's job on a scratch transform: no exception");
        }
        catch (Exception ex) { Console.WriteLine($"FAIL the drawer's job: {(ex.InnerException ?? ex).Message}"); }
    }
    for (int i = 0; i < 3; i++)
        try { Call(s, seqT, "Fault", "probe", new InvalidOperationException("probe fault " + (i + 1))); } catch (Exception ex) { Console.WriteLine($"FAIL Fault: {ex.Message}"); }
    Tick("update after 3 injected faults");
    var pose = Get(s, "Pose");
    bool atEnd = (float)Get(pose, "Slide") is var sl && (sl == 0f || sl == 1f) && (float)Get(pose, "Fold") == sl;
    Console.WriteLine($"{Mark(Get(s, "Faulted") is true && atEnd)} faulted: snaps to its end pose {pose} (target {Get(s, "Target")}); this KVM stays faulted until the world is reloaded");
}

// 6. Every "[DataCenter]" line of this session's log (DcLog writes them; Log.FileName, Log.cs:116).
try
{
    string path = Keen.VRage.Library.Diagnostics.Log.Default?.FileName;
    var lines = new List<string>();
    if (path != null)
        using (var fs = new System.IO.FileStream(path, System.IO.FileMode.Open, System.IO.FileAccess.Read, System.IO.FileShare.ReadWrite | System.IO.FileShare.Delete))
        using (var rd = new System.IO.StreamReader(fs))
            for (string l; (l = rd.ReadLine()) != null;)
                if (l.Contains("[DataCenter]")) lines.Add(l);
    Console.WriteLine($"     log {path}: {lines.Count} [DataCenter] line(s){(lines.Count > 60 ? ", last 60:" : "")}");
    foreach (var l in lines.Skip(Math.Max(0, lines.Count - 60))) Console.WriteLine("     | " + l);
}
catch (Exception ex) { Console.WriteLine($"FAIL reading the log: {ex.GetType().Name}: {ex.Message}"); }
