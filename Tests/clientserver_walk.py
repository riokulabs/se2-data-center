"""Offline port of SE2's client/server composition walk and the validator that fails world load on it.

Shared core: no DataCenter imports (standard library plus WS/tools/scripts/block_chain.py's delta merge), so any mod's
tests can import it (another mod: put WS/mods/DataCenter/Tests on sys.path, `import clientserver_walk`). Build a
Universe from the Mod SDK's vanilla Assets plus the mod's Assets roots, optionally derive() it with in-memory
definition files (fixtures), walk() it, then validate() with a TypeIndex over the decompiled game:

    import clientserver_walk as csw
    u = csw.Universe([csw.SDK_ASSETS, mod_assets, staged_assets])      # later roots win per relative path
    w = csw.walk(u)
    errors = csw.validate(w, csw.TypeIndex())       # [] == nothing this load validator would reject
    print(csw.format_errors(errors, u))             # each error carries the walk path that reached the composite
    u2 = u.derive({"$Type": ..., "$Value": {...}})  # a fixture: same GUID replaces, new GUID adds

Game 4.0.0.3151, decompiled at WS/tools/decompiled-4.0.0.3151 (`D` below). What is ported:

1. BindingsBasedClientServerInfo.LoadCompositesFromBindings (D/VRage.Multiplayer/Keen.VRage.Multiplayer.
   ClientServerInfo/BindingsBasedClientServerInfo.cs:118-155):
   * the prefab-by-composition map is `ToDictionary(p => p.Composition.Guid)` over EVERY PrefabDefinition (:126), so
     two prefabs on one composition throw at load -> error "duplicate-composition";
   * per PrefabBinding: its ServerComposite must be an EntityCompositeDefinition, its ClientPrefab a PrefabDefinition,
     and some prefab must have the ServerComposite as its composition (the "server prefab"); otherwise the default
     _onDefinitionNotFound asserts "Definition that is linked from ... is not found" (:68-71) and :134/:151 then
     dereference null -> error "binding";
   * _serverPrefabs = every binding's server prefab, _clientPrefabs = every binding's ClientPrefab (:134-135);
   * the SERVER walk starts at each ServerComposite with its server prefab's object builders and blocks the client
     prefabs; the CLIENT walk starts at each ClientPrefab's composition with its object builders and blocks the server
     prefabs (:145-153).
2. ProcessComposition / ProcessComponent (:157-192): a composite is added to its side's set once; for each component,
   a HierarchyComponentObjectBuilder's Children are walked (child.Definition with the child's own object builders,
   :170-176), and the component's Definition is followed (FillDefinitionDependencies, :188-191). Object builders are
   matched to components by key (PrefabDefinition sorts them into composition order: D/VRage.Core.Game/.../
   PrefabDefinition.cs:258-262).
3. FillDefinitionDependencies / ProcessField (:194-270): every field-backed member of a definition is followed; a
   PrefabDefinition value is walked as a composition unless its GUID is blocked (:224-231); any other Definition is
   recursed into (:232-235); dictionary-like values' Values/Keys of PrefabDefinition are enumerated (:242-263), and
   ListDictionaryReader<EntityCompositeDefinition, PrefabDefinition> values too (:205-214).
   OVER-APPROXIMATION (conservative): the port follows EVERY definition GUID anywhere in the resolved definition body
   (keys and values, nested lists/dicts/structs), a superset of the field-backed members the game reads (the game
   does not enter lists of plain Definitions or non-definition structs). It can only add composites to a side, so it
   errs towards false failures - within what it ports. KNOWN UNDER-APPROXIMATIONS (paths the game walks that the port
   does not, so a false pass is possible only through them):
     * component Configurations (:177-187, RuntimeComponentInfo.For(type).Configurations): global game
       configurations reached through component types' [Configuration] fields, not per-definition data. A mod Override
       that made a configuration reference an unbound client prefab would be missed (a brute-force walk of every
       configuration reached no DataCenter composite at 4.0.0.3151);
     * AddComponent (:86-96): runtime additions, not data;
     * references computed in a definition's Init rather than serialised as a GUID (the chain that matters here,
       DoorPartsProvider -> ConditionalSubParts -> SubParts, is data-backed);
     * GUIDs that resolve to no loaded definition are not followed (they are counted: unresolved(w) and
       unresolved_report(w); at 4.0.0.3151 they are materials, fonts, projections and destruction layers).
4. ConveyorGraphPostProcessor.ValidateClientTypes (D/Game2.Simulation/Keen.Game2.Simulation.WorldObjects.CubeBlocks.
   ResourceDistribution.Conveyors/ConveyorGraphPostProcessor.cs:162-205, run for every composite from Validate
   :68-77): a composite in the server set may hold no client type (ComponentTypeUtility.IsClientType, D/VRage.Core.Game/
   Keen.VRage.Core.Game.RuntimeSystems.Components/ComponentTypeUtility.cs:14-22: the type's assembly has
   [assembly: ClientAssembly] or its name ends in "Client"); a composite in the client set and NOT in the server set
   (a both-sides composite is judged as server, :174) may hold no [ServerOnly] type (`type.GetCustomAttribute<
   ServerOnlyAttribute>()`, inherit: true; the attribute has no AttributeUsage, so it is inherited down the class
   chain: D/VRage.Core.Game/Keen.VRage.Core.Game.RuntimeSystems.Components/ServerOnlyAttribute.cs).
   Classification is read from the decompile (TypeIndex); a component type the decompile does not define is an
   error ("unknown-type"), never a pass.

   Also reported: "missing-definition" (a walked component's Definition is not a loaded definition) and
   "missing-composite" (a prefab or hierarchy child names no loaded composite).

Definitions are resolved the way the SDK content pipeline does: a .def is a full definition; a Copy partialdef is its
BaseDefinition (resolved recursively) with the Manipulator delta applied; Override partialdefs are applied on top of
their target (tools/scripts/block_chain.py merge, which follows VRage DeltaEncodedCollectionsHelper). A definition whose
.meta carries DefinitionFlagsMetadata "Abstract" (vanilla Templates/) is a base only: it is "not pushed to
DefinitionManager, not initialized and not validated" (D/VRage.Library/Keen.VRage.Library.Definitions/
DefinitionFlags.cs:16-22), so the walk neither starts from nor reaches it.

Component types: a composite entry's "Type" (bundle prefix dropped); a stale name is mapped through the decompile's
[NameMigration(version, old, new)] attributes (e.g. ToolDamageComponent.cs:23); "Type": null takes the component whose
[Definition] member is exactly the definition's class (EntityBuilder.ResolveComponent, D/VRage.DCS/Keen.VRage.DCS.
Builders/EntityBuilder.cs; RuntimeComponentInfo.ForDefinition -> ComponentInfoIndexer.FindComponentWithDefinitionType,
D/VRage.DCS/Keen.VRage.DCS.Internal/ComponentInfoIndexer.cs). The decompile is decompiled-current (20 assemblies) plus
<its target>-extra: the runtime assemblies decompiled-current lacks (VRage.Audio, VRage.Game.Client, VRage.Client,
VRage.AI, VRage.Water, VRage.Water.Client, VRage.Physics.Client, VRage.Input, VRage.UI, VRage.UI.Shared, VRage.Steam,
VRage.Analytics), decompiled 2026-10-20 the same way (`ilspycmd -p -r Game2/`). Without them, e.g. SpatialAudioComponent
(VRage.Audio, [assembly: ClientAssembly]) is an unknown type, and the validator fails rather than guesses.
"""
import copy
import hashlib
import json
import os
import pickle
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
WS_TOOLS = os.environ.get("SE2_TOOLS") or os.path.normpath(os.path.join(HERE, "..", "..", "..", "tools"))
DECOMPILED = os.path.join(WS_TOOLS, "decompiled-current")
# The 20 assemblies of decompiled-current plus the runtime assemblies it lacks (VRage.Audio, VRage.Game.Client, VRage.AI,
# VRage.Water*, ...), decompiled the same way (`ilspycmd -p -r Game2/`) into <decompiled-current target>-extra.
DECOMPILED_ROOTS = [DECOMPILED, os.path.realpath(DECOMPILED) + "-extra"]
SDK_ASSETS = os.environ.get("SE2_SDK_ASSETS") or os.path.expanduser(
    "~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/GameData/Vanilla/Assets")

# The vanilla root's parsed files are cached on disk (_load_root): parsing its ~19,000 definition files is ~2 s and the
# suite builds a Universe over it a dozen times. Outside the repo; DC_TEST_NO_CACHE=1 turns it off.
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "rioku-se2", "dc-tests")
_CACHE_FORMAT = 1
with open(os.path.abspath(__file__), "rb") as _fh:
    _LOADER_DIGEST = hashlib.sha256(_fh.read()).hexdigest()   # the loader's own source is part of every cache key

sys.path.insert(0, os.path.join(WS_TOOLS, "scripts"))
try:
    from block_chain import merge  # noqa: E402  (VRage delta-encoded collection merge)
finally:
    sys.path.pop(0)

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
PREFAB = "PrefabDefinition"
BINDING = "PrefabBindingDefinition"
COMPOSITE = "EntityCompositeDefinition"
DCS_COMPONENT = "Keen.VRage.DCS.Components.Component"
HIERARCHY_OB = "Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder"
LOCAL_ID_FIELD = re.compile(r"^\$?(Key|Id|\w*NodeId)$")


def short_type(t):
    """'VRage:Keen.VRage.DCS.Definitions.PrefabDefinitionObjectBuilder' -> 'PrefabDefinition'."""
    t = (t or "").split(":", 1)[-1].rsplit(".", 1)[-1]
    return t[:-len("ObjectBuilder")] if t.endswith("ObjectBuilder") else t


def full_type(t):
    """'VRage:Keen.VRage.DCS.Definitions.PrefabDefinitionObjectBuilder' -> 'Keen.VRage.DCS.Definitions.PrefabDefinition'
    (the runtime definition class; its object builder is <Class>ObjectBuilder)."""
    t = (t or "").split(":", 1)[-1]
    return t[:-len("ObjectBuilder")] if t.endswith("ObjectBuilder") else t


def _g(x):
    return x.lower() if isinstance(x, str) and GUID_RE.match(x) else None


# ------------------------------------------------------------------------------------------------- definition universe
class Universe:
    """Every definition of the load, resolved. `roots`: Assets directories, lowest priority first; a file at the same
    relative path in a later root replaces the earlier one (the staged package over the mod's Assets). `extra`:
    in-memory definition files ({"$Type", "$Value"} dicts, .def or PartialDefinitionDiff), applied last (fixtures)."""

    def __init__(self, roots=(), extra=()):
        files = {}                        # rel -> (d, error, abstract): later roots replace earlier ones per rel
        for root in roots:
            files.update(_load_root(root))
        self.entries = {}                 # guid -> (kind, type, raw, base, origin)
        self.full_types = {}              # guid -> full definition class name
        self.overrides = defaultdict(list)
        self.abstract = set()             # DefinitionFlags.Abstract: a Copy base only, never pushed or validated
        self.load_errors = []             # (code, None, guid or None, detail): "unparseable", "duplicate-guid"
        for rel, (p, d, err, abstract) in sorted(files.items()):
            if err is not None:
                # The content pipeline would fail the build on it; silently dropping it would hide its definitions
                # from the walk (a reference to them then reads as "not live" and is not followed: a false pass).
                self.load_errors.append(("unparseable", None, None, (err,)))
                continue
            self._add(d, p, abstract, check_duplicate=True)
        for i, d in enumerate(extra):
            self._add(d, f"<extra {i}>")
        self._resolved = {}

    def _add(self, d, origin, abstract=False, check_duplicate=False):
        if not isinstance(d, dict):
            return
        v = d.get("$Value")
        if not isinstance(v, dict):
            return
        kind = v.get("PartialDefinitionKind")

        def dup(g):    # two files defining one GUID: the game throws "already contained" (DefinitionLoader InitInternal)
            if check_duplicate and g in self.entries:
                self.load_errors.append(("duplicate-guid", None, g, (f"{self.entries[g][4]}", f"{origin}")))
        if kind is None:
            g = _g(v.get("Guid"))
            if g:
                dup(g)
                self.entries[g] = ("def", short_type(d.get("$Type")), v, None, origin)
                self.full_types[g] = full_type(d.get("$Type"))
                self._flag(g, abstract)
        elif kind == "Copy":
            g = _g((v.get("Manipulator") or {}).get("Guid"))
            if g:
                dup(g)
                self.entries[g] = ("copy", short_type(v.get("DefinitionType")), v["Manipulator"],
                                   _g(v.get("BaseDefinition")), origin)
                self.full_types[g] = full_type(v.get("DefinitionType"))
                self._flag(g, abstract)
        elif kind == "Override":
            base = _g(v.get("BaseDefinition"))
            if base:
                self.overrides[base].append((v.get("Manipulator") or {}, origin))
                self._resolved = {}

    def _flag(self, g, abstract):
        (self.abstract.add if abstract else self.abstract.discard)(g)
        self._resolved = {}

    def live(self, guid):
        """A definition the game pushes to the DefinitionManager (known and not Abstract: DefinitionFlags.cs:16-22,
        "not pushed to DefinitionManager, not initialized and not validated")."""
        g = _g(guid)
        return g in self.entries and g not in self.abstract

    def derive(self, *file_dicts, origin="<fixture>"):
        """A copy of this universe with in-memory definition files laid over it (a fixture: a .def replaces the
        definition with its GUID, a Copy partialdef defines one, an Override partialdef patches one). Cheap: the
        loaded files are shared, the resolution cache is not."""
        u = object.__new__(Universe)
        u.entries, u.full_types, u.abstract = dict(self.entries), dict(self.full_types), set(self.abstract)
        u.load_errors = list(self.load_errors)
        u.overrides = defaultdict(list, {k: list(v) for k, v in self.overrides.items()})
        before, n_over = dict(u.entries), {k: len(v) for k, v in u.overrides.items()}
        for d in file_dicts:
            u._add(copy.deepcopy(d), origin)
        changed = {g for g in u.entries if before.get(g) is not u.entries[g]} | \
                  {k for k, v in u.overrides.items() if len(v) != n_over.get(k, 0)}

        def stale(g, seen=()):            # g or a Copy base of it was replaced
            while g and g not in seen:
                if g in changed:
                    return True
                seen += (g,)
                e = u.entries.get(g)
                g = e[3] if e else None
            return False
        u._resolved = {g: v for g, v in self._resolved.items() if not stale(g)}
        return u

    def __contains__(self, guid):
        return _g(guid) in self.entries

    def type_of(self, guid):
        e = self.entries.get(_g(guid))
        if e is None:
            return None
        if e[0] == "copy" and not e[1]:
            return self.type_of(e[3])
        return e[1]

    def full_type_of(self, guid):
        g = _g(guid)
        e = self.entries.get(g)
        if e is None:
            return None
        if e[0] == "copy" and not self.full_types.get(g):
            return self.full_type_of(e[3])
        return self.full_types.get(g)

    def origin(self, guid):
        e = self.entries.get(_g(guid))
        return e[4] if e else None

    def resolve(self, guid, _stack=()):
        g = _g(guid)
        if g in self._resolved:
            return self._resolved[g]
        e = self.entries.get(g)
        if e is None:
            return None
        if g in _stack:
            raise ValueError(f"BaseDefinition cycle through {g}")
        kind, _, raw, base, _ = e
        if kind == "def":
            val = copy.deepcopy(raw)
        else:
            b = self.resolve(base, _stack + (g,)) if base else None
            if base and b is None:
                raise KeyError(f"{g} ({e[4]}): BaseDefinition {base} is not a known definition")
            val = merge(copy.deepcopy(b) if b is not None else None, raw)
            val["Guid"] = raw.get("Guid", g)
        for o, _ in self.overrides.get(g, []):
            val = merge(val, {k: v for k, v in o.items() if k != "Guid"})
        self._resolved[g] = val
        return val

    def guids_of_type(self, t):
        """The live definitions of a type (DefinitionManager.GetDefinitionsOfType)."""
        return sorted(g for g in self.entries if g not in self.abstract and self.type_of(g) == t)


def _read_def(p):
    """(path, parsed file, None, abstract) or (path, None, "<path>: <error>", False) for an unreadable one."""
    try:
        with open(p, encoding="utf-8-sig") as fh:
            d = json.load(fh)
    except (OSError, ValueError) as ex:
        return p, None, f"{p}: {ex}", False
    return p, d, None, _abstract(p + ".meta")


def _load_root(root):
    """rel -> _read_def(path) for every .def / .partialdef under root. The Mod SDK's vanilla root (SDK_ASSETS, which
    nothing here writes) comes from a pickle in CACHE_DIR when one exists for exactly these inputs: the key hashes the
    root as given and resolved, every file's relative path with the mtime and size of it and of its .meta (present or
    not), this module's source and the Python version, so any change to what the loader reads or how it reads it
    misses the cache. Other roots (the mod's, the staging, fixtures) are always read."""
    files = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                p = os.path.join(dp, f)
                files[os.path.relpath(p, root)] = p
    if os.environ.get("DC_TEST_NO_CACHE") == "1" or not os.path.isdir(SDK_ASSETS) \
            or os.path.realpath(root) != os.path.realpath(SDK_ASSETS):
        return {rel: _read_def(p) for rel, p in files.items()}
    h = hashlib.sha256(repr((_CACHE_FORMAT, sys.version_info[:3], root, os.path.realpath(root))).encode())
    h.update(_LOADER_DIGEST.encode())
    for rel in sorted(files):
        for q in (files[rel], files[rel] + ".meta"):
            try:
                st = os.stat(q)
                h.update(f"\0{rel}\0{q[-5:]}\0{st.st_mtime_ns}\0{st.st_size}".encode())
            except OSError:
                h.update(f"\0{rel}\0{q[-5:]}\0-".encode())
    path = os.path.join(CACHE_DIR, f"universe-{h.hexdigest()[:40]}.pickle")
    try:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    except (OSError, EOFError, pickle.UnpicklingError, ValueError, TypeError, AttributeError):
        pass
    out = {rel: _read_def(p) for rel, p in files.items()}
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(out, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)            # atomic: a parallel worker never reads a half-written cache
        for f in os.listdir(CACHE_DIR):  # keep only the current entry (a new SDK or loader leaves the old one stale)
            if f.startswith("universe-") and f.endswith(".pickle") and f != os.path.basename(path):
                os.remove(os.path.join(CACHE_DIR, f))
    except OSError:
        pass
    return out


def _abstract(meta_path):
    """The asset's DefinitionFlagsMetadata (its .meta) says Abstract (vanilla templates: "Abstract, SkipValidation")."""
    try:
        with open(meta_path, encoding="utf-8-sig", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return False
    if "DefinitionFlagsMetadata" not in txt:
        return False
    for it in (json.loads(txt).get("$Value") or {}).get("InternalItems") or []:
        if str(it.get("$Type", "")).endswith("DefinitionFlagsMetadata") and "Abstract" in str(it.get("Flags", "")):
            return True
    return False


def composition_of(prefab):
    return _g(((prefab or {}).get("_entity") or {}).get("Definition"))


def object_builders(entity):
    """{component key: object builder} of an EntityObjectBuilder ({Definition, ObjectBuilders})."""
    obs = (entity or {}).get("ObjectBuilders") or []
    if isinstance(obs, dict):            # serialised as a JSON object
        return {str(k).lower(): v for k, v in obs.items()}
    return {str(it.get("Key")).lower(): it.get("Value") for it in obs if isinstance(it, dict)}


def components(comp):
    """[(key, type, definition guid)] of a resolved EntityCompositeDefinition."""
    out = []
    for it in (comp or {}).get("Components") or []:
        v = it.get("Value") or {}
        out.append((str(it.get("Key")).lower(), v.get("Type"), _g(v.get("Definition"))))
    return out


def _children(ob):
    """The child EntityObjectBuilders of a HierarchyComponentObjectBuilder (a plain or a keyed list)."""
    out = []
    for c in (ob or {}).get("Children") or []:
        if isinstance(c, dict) and "Definition" not in c and isinstance(c.get("Value"), dict):
            c = c["Value"]
        if isinstance(c, dict):
            out.append(c)
    return out


def _guids_in(value, field=None):
    """(field, GUID) for every GUID string in a resolved definition body (keys and values, any depth), in document
    order; `field` is the nearest enclosing non-GUID dict key."""
    if isinstance(value, dict):
        for k, v in value.items():
            if _g(k):
                yield field, _g(k)
            yield from _guids_in(v, field if _g(k) else k)
    elif isinstance(value, list):
        for v in value:
            yield from _guids_in(v, field)
    elif _g(value):
        yield field, _g(value)


# ---------------------------------------------------------------------------------------------------------------- walk
class Side:
    """One side's walk state (BindingsBasedClientServerInfo's composites/definitions sets for server or client)."""

    def __init__(self, u, name, blocked):
        self.u, self.name, self.blocked = u, name, blocked
        self.composites = {}               # composite guid -> path (how it was first reached)
        self.definitions = set()
        self.unresolved = defaultdict(set)  # (referring definition type, field) -> GUIDs that are no loaded definition
        self.errors = []
        self._seen = set()                 # (composite, object builders) already walked

    def composition(self, comp_guid, obs, path):              # ProcessComposition, :157-166
        if comp_guid is None:
            self.errors.append(("missing-composite", self.name, None, path + ("<no Definition>",)))
            return
        # The game returns early once the composite is in the set (:159), so a composite reached a second time with
        # OTHER object builders does not have those builders' hierarchy children walked: which children count depends
        # on the walk order. The port walks the children of every distinct object-builder set instead (a superset of
        # any order: conservative).
        sig = (comp_guid, json.dumps(obs, sort_keys=True, default=str))
        if sig in self._seen:
            return
        self._seen.add(sig)
        if comp_guid not in self.composites:
            comp = self.u.resolve(comp_guid) if self.u.live(comp_guid) else None
            if comp is None or self.u.type_of(comp_guid) != COMPOSITE:
                self.errors.append(("missing-composite", self.name, comp_guid, path))
                return
            self.composites[comp_guid] = path
        comp = self.u.resolve(comp_guid)
        here = path + (f"composite {comp_guid}",)
        for key, typ, dfn in components(comp):                 # ProcessComponent, :168-192
            ob = obs.get(key)
            if isinstance(ob, dict) and str(ob.get("$Type", "")).split(":", 1)[-1] == HIERARCHY_OB:
                for i, child in enumerate(_children(ob)):
                    self.composition(_g(child.get("Definition")), object_builders(child),
                                     here + (f"Hierarchy child {child.get('DebugName') or i}",))
            if dfn is not None:
                if not self.u.live(dfn):       # a component definition the load cannot resolve
                    self.errors.append(("missing-definition", self.name, comp_guid,
                                        here + (f"component {key} Definition {dfn} is not a loaded definition",)))
                    continue
                self.fill(dfn, here + (f"{short_type(typ)}.Definition {dfn}",))

    def fill(self, guid, path):                                 # FillDefinitionDependencies / ProcessField
        if self.u.type_of(guid) == PREFAB:
            self.prefab(guid, path)
            return
        if guid in self.definitions or not self.u.live(guid):
            return
        self.definitions.add(guid)
        body = self.u.resolve(guid)
        for field, g in _guids_in({k: v for k, v in body.items() if k != "Guid"}):
            if g == guid:
                continue
            if not self.u.live(g):
                # Abstract templates are known, just never pushed: not "unresolved". Keyed-list Keys and node Ids are
                # local identifiers (random GUIDs), not references: a Key that IS a definition is live and followed.
                if g not in self.u and not LOCAL_ID_FIELD.match(str(field)):
                    self.unresolved[(self.u.type_of(guid), field)].add(g)
                continue
            if self.u.type_of(g) == PREFAB:
                self.prefab(g, path)
            else:
                self.fill(g, path + (f"-> {self.u.type_of(g)} {g}",))

    def prefab(self, guid, path):                               # ProcessField's PrefabDefinition branch, :224-231
        if guid in self.blocked or not self.u.live(guid):
            return
        p = self.u.resolve(guid)
        self.composition(composition_of(p), object_builders(p.get("_entity")), path + (f"prefab {guid}",))


class Walk:
    def __init__(self, u):
        self.u = u
        self.errors = list(u.load_errors)  # (code, side, guid, path)
        self.bindings = {}                 # binding guid -> (server composite, server prefab, client prefab)
        self.server = self.client = None


def walk(u):
    """LoadCompositesFromBindings (BindingsBasedClientServerInfo.cs:118-155) over the universe."""
    w = Walk(u)
    by_comp = {}
    for p in u.guids_of_type(PREFAB):                           # :126 ToDictionary (throws on a duplicate key)
        c = composition_of(u.resolve(p))
        if c in by_comp:
            w.errors.append(("duplicate-composition", None, c, (f"prefabs {by_comp[c]} and {p}",)))
        by_comp.setdefault(c, p)
    server_prefabs, client_prefabs = set(), set()
    for b in u.guids_of_type(BINDING):                          # :127-144
        v = u.resolve(b)
        sc, cp = _g(v.get("ServerComposite")), _g(v.get("ClientPrefab"))
        problems = []
        if u.type_of(sc) != COMPOSITE or not u.live(sc):
            problems.append(f"ServerComposite {sc} is not an EntityCompositeDefinition")
        if u.type_of(cp) != PREFAB or not u.live(cp):
            problems.append(f"ClientPrefab {cp} is not a PrefabDefinition")
        if sc not in by_comp:
            problems.append(f"no PrefabDefinition has the ServerComposite {sc} as its composition (no server prefab)")
        if problems:
            w.errors.append(("binding", None, b, (f"binding {b} ({u.origin(b)})",) + tuple(problems)))
            continue
        w.bindings[b] = (sc, by_comp[sc], cp)
        server_prefabs.add(by_comp[sc])
        client_prefabs.add(cp)
    w.server = Side(u, "server", client_prefabs)
    w.client = Side(u, "client", server_prefabs)
    for b, (sc, sp, cp) in sorted(w.bindings.items()):         # :145-154
        w.server.composition(sc, object_builders(u.resolve(sp).get("_entity")), (f"binding {b} server",))
        cpv = u.resolve(cp)
        w.client.composition(composition_of(cpv), object_builders(cpv.get("_entity")), (f"binding {b} client {cp}",))
    w.errors += w.server.errors + w.client.errors
    return w


def unresolved(w):
    """{(side, referring definition type, field): GUID count} of the GUIDs the walk met that resolve to no loaded
    definition (assets such as materials and fonts, or definitions a game update moved out of the SDK Assets). They
    are not followed, so a rise here is where a false pass could hide (an under-approximation, see the docstring)."""
    out = {}
    for side in (w.server, w.client):
        for (t, f), gs in side.unresolved.items():
            out[(side.name, t, f)] = len(gs)
    return out


def unresolved_report(w, limit=30):
    rows = sorted(unresolved(w).items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(n for _, n in rows)
    lines = [f"{total} unresolved GUID references (side, referring type, field):"]
    lines += [f"  {n:6d}  {s} {t}.{f}" for (s, t, f), n in rows[:limit]]
    if len(rows) > limit:
        lines.append(f"  ... {len(rows) - limit} more fields")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ type classification
CLASS_RE = re.compile(r"^(?:\s*)(?:public|internal|private|protected)?\s*(?:(?:sealed|abstract|static|partial|unsafe)\s+)*"
                      r"(class|struct|interface|record)\s+(\w+)\s*(?:<[^>{]*>)?\s*(?::\s*([^{\n]+))?", re.M)
# a [Definition] member (RuntimeComponentInfo.cs:209): the attribute, maybe more attributes, then "<mods> Type name"
DEFINITION_MEMBER_RE = re.compile(r"^\s*\[Definition\]\s*\n(?:\s*\[[^\n]*\]\s*\n)*\s*"
                                  r"(?:(?:public|private|protected|internal|new|readonly|static|required)\s+)*"
                                  r"([\w.]+(?:<[^>\n]*>)?\??)\s+\w+\s*(?:;|=|\{)", re.M)
NAME_MIGRATION_RE = re.compile(r'\[NameMigration\("[^"]*",\s*"([\w.]+)",\s*"([\w.]+)"\)\]')
SERVER_ONLY_RE = re.compile(r"^\s*\[(?:[^\]]*,\s*)?ServerOnly(?:Attribute)?\s*(?:,[^\]]*)?\]", re.M)


def _candidates(d, name):
    """C# simple-name lookup from a declaration: as written (if qualified), the declaring namespace and each enclosing
    namespace, then the file's using directives."""
    out = [name] if "." in name else []
    parts = d["ns"].split(".")
    out += [".".join(parts[:i] + [name]) for i in range(len(parts), 0, -1)]
    return out + [f"{u}.{name}" for u in d["usings"]]


class TypeIndex:
    """Component type classification from the decompiled assemblies (<Assembly>/<Namespace>/<Class>.cs).

    classify(type) -> {"type", "assembly", "client", "server_only", "file", "line", "reason"}:
      client      = the type's assembly carries [assembly: ClientAssembly] (Properties/AssemblyInfo.cs) or its name
                    ends in "Client" (ComponentTypeUtility.cs:14-22);
      server_only = [ServerOnly] on the class or on any base class (inherited; interfaces are not walked, as
                    GetCustomAttribute does not search them).
    Raises UnknownType for a type the decompile does not define (never treated as safe)."""

    NOT_ASSEMBLIES = {"sdk-pipeline"}

    def __init__(self, roots=None):
        self.roots = list(roots or DECOMPILED_ROOTS)
        missing = [r for r in self.roots if not os.path.isdir(r)]
        if missing:
            raise MissingDecompile(
                "the decompiled game is missing: " + ", ".join(missing) + ". Without it component types cannot be "
                "classified and the walk gate cannot run. decompiled-current: tools/README.md 'Decompiling the game'; "
                "the -extra tree (VRage.Audio, VRage.Game.Client, ...): the exact loop in the same section.")
        self.root = self.roots[0]
        self.by_name = defaultdict(list)          # full name -> [(assembly, path)]
        self.client_assemblies = set()
        self.migrations = {}                      # [NameMigration(version, old, new)]: old full name -> new
        for root in self.roots:
            for asm in sorted(os.listdir(root)):
                d = os.path.join(root, asm)
                if asm in self.NOT_ASSEMBLIES or not os.path.isdir(d):
                    continue
                info = os.path.join(d, "Properties", "AssemblyInfo.cs")
                attr = False
                if os.path.exists(info):
                    with open(info, encoding="utf-8", errors="replace") as fh:
                        attr = re.search(r"\[assembly:\s*ClientAssembly(?:Attribute)?\b", fh.read())
                if attr or asm.endswith("Client"):
                    self.client_assemblies.add(asm)
                for ns in os.listdir(d):
                    nd = os.path.join(d, ns)
                    if os.path.isdir(nd) and ns != "Properties":
                        for f in os.listdir(nd):
                            if f.endswith(".cs"):
                                path = os.path.join(nd, f)
                                self.by_name[f"{ns}.{f[:-3]}"].append((asm, path))
                                with open(path, encoding="utf-8", errors="replace") as fh:
                                    src = fh.read()
                                if "NameMigration(" in src:
                                    for m in NAME_MIGRATION_RE.finditer(src):
                                        old, new = m.group(1), m.group(2)
                                        if "." not in old:      # a bare name: same namespace as the new type
                                            old = f"{ns}.{old}"
                                        if "." not in new:
                                            new = f"{ns}.{new}"
                                        self.migrations[old] = new
        self._cache, self._decls, self._def_map = {}, {}, None

    def migrate(self, full):
        """The current name of a type the data may still name by an old one (VRage NameMigrationAttribute: the
        serializer maps the old name to the new type; e.g. ToolDamageComponent.cs:23)."""
        seen = set()
        while full in self.migrations and full not in seen and full not in self.by_name:
            seen.add(full)
            full = self.migrations[full]
        return full

    def _decl(self, full):
        if full not in self._decls:
            self._decls[full] = self._read_decl(full)
        return self._decls[full]

    def _read_decl(self, full):
        hits = self.by_name.get(full)
        if not hits:
            return None
        if len(hits) > 1:
            raise UnknownType(f"{full} is defined in several assemblies: {[a for a, _ in hits]}")
        asm, path = hits[0]
        with open(path, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        name = full.rsplit(".", 1)[1]
        for m in CLASS_RE.finditer(src):
            if m.group(2) == name:
                head = src[:m.start()]
                block = []                     # the attribute lines directly above the declaration
                for line in reversed(head.splitlines()):
                    if not line.strip().startswith("["):
                        break
                    block.append(line)
                attrs = "\n".join(reversed(block))
                so = SERVER_ONLY_RE.search(attrs)
                line = head.count("\n") + 1
                usings = re.findall(r"^using\s+([\w.]+)\s*;", src, re.M)
                ns = re.search(r"^namespace\s+([\w.]+)", src, re.M)
                return dict(assembly=asm, path=path, line=line, kind=m.group(1), server_only=bool(so), header=m.group(0),
                            definition_members=[x.group(1) for x in DEFINITION_MEMBER_RE.finditer(src)]
                            if "[Definition]" in src else [],
                            bases=m.group(3) or "", usings=usings, ns=ns.group(1) if ns else full.rsplit(".", 1)[0])
        raise UnknownType(f"{full}: no declaration of {name} in {path}")

    def _base(self, d):
        """The resolved full name of the declaration's base CLASS, or None (no base / external / interface)."""
        if d["kind"] != "class" or not d["bases"]:
            return None
        first = re.split(r",(?![^<]*>)", d["bases"])[0].strip()
        first = re.sub(r"<.*$", "", first).strip()
        for cand in _candidates(d, first):
            if cand in self.by_name:
                bd = self._decl(cand)
                return cand if bd and bd["kind"] == "class" else None
        return None   # a framework base (System.Object, ...): not in the decompile, carries no ServerOnly

    def _resolve_name(self, d, name):
        name = re.sub(r"<.*$", "", name.strip().rstrip("?"))
        for cand in _candidates(d, name):
            if cand in self.by_name:
                return cand
        return None

    def _own_definition_type(self, full):
        """The type of the class's own [Definition] member (RuntimeComponentInfo.cs:209-217), or None."""
        d = self._decl(full)
        for name in d["definition_members"]:
            t = self._resolve_name(d, name)
            if t:
                return t
        return None

    def is_component(self, full):
        """Derives from Keen.VRage.DCS.Components.Component (RuntimeComponentInfo.IsComponent: the indexed subtypes of
        Component, D/VRage.DCS/Properties/AssemblyInfo.cs:68)."""
        cur, seen = full, set()
        while cur and cur not in seen:
            if cur == DCS_COMPONENT:
                return cur != full
            seen.add(cur)
            try:
                cur = self._base(self._decl(cur))
            except UnknownType:
                return False
        return False

    def component_for_definition(self, definition_class):
        """RuntimeComponentInfo.ForDefinition (D/VRage.DCS/Keen.VRage.DCS.Internal/RuntimeComponentInfo.cs:278-285 ->
        ComponentInfoIndexer.FindComponentWithDefinitionType): a composite entry with "Type": null takes the type of
        the component whose [Definition] member is exactly the definition's class. Returns the component full name;
        raises UnknownType when none or several (non-abstract) components match."""
        if self._def_map is None:
            own, self._def_map = {}, defaultdict(list)
            for full, hits in self.by_name.items():
                if len(hits) != 1:
                    continue
                try:
                    d = self._decl(full)
                except UnknownType:
                    continue
                if d["kind"] != "class":
                    continue
                own[full] = d
            for full, d in own.items():
                if re.search(r"\babstract\s+class\b", d["header"]) or not self.is_component(full):
                    continue
                cur, seen, t = full, set(), None
                while cur and cur not in seen and cur in own:   # nearest [Definition] up the class chain
                    seen.add(cur)
                    t = self._own_definition_type(cur)
                    if t:
                        break
                    cur = self._base(own[cur])
                if t:
                    self._def_map[t].append(full)
        definition_class = self.migrate(definition_class)
        hits = self._def_map.get(definition_class) or []
        if len(hits) != 1:
            raise UnknownType(f"component for definition class {definition_class}: "
                              f"{'none' if not hits else 'ambiguous ' + str(sorted(hits))} in the decompile")
        return hits[0]

    def classify(self, type_string):
        if type_string in self._cache:
            return self._cache[type_string]
        full = self.migrate((type_string or "").split(":", 1)[-1])
        if not full or "`" in full or "[" in full:
            raise UnknownType(f"{type_string!r}: not a plain component type name")
        d = self._decl(full)
        if d is None:
            raise UnknownType(f"{type_string}: not defined in the decompile {self.root}")
        server_only, why, cur, seen = d["server_only"], [], d, {full}
        if server_only:
            why.append(f"[ServerOnly] on {full}")
        b = self._base(d)
        while b and b not in seen and not server_only:
            seen.add(b)
            bd = self._decl(b)
            if bd["server_only"]:
                server_only = True
                why.append(f"[ServerOnly] inherited from {b} ({os.path.relpath(bd['path'], WS_TOOLS)}:{bd['line']})")
            b = self._base(bd)
        client = d["assembly"] in self.client_assemblies
        why.insert(0, f"assembly {d['assembly']} is {'a client' if client else 'not a client'} assembly")
        r = dict(type=full, assembly=d["assembly"], client=client, server_only=server_only,
                 file=os.path.relpath(d["path"], WS_TOOLS), line=d["line"], reason="; ".join(why))
        self._cache[type_string] = r
        return r


class UnknownType(Exception):
    pass


class MissingDecompile(FileNotFoundError):
    pass


# ------------------------------------------------------------------------------------------------------------ validate
LOAD_ERRORS = ("binding", "duplicate-composition", "unparseable", "duplicate-guid")   # never filtered by `only`


def validate(w, types, only=None):
    """ConveyorGraphPostProcessor.ValidateClientTypes (:162-205) over the walk, plus the walk's own load errors.
    `only`: optional predicate on a composite GUID (limit the report to some composites; the walk stays global).
    Returns [(code, side, guid, detail)], [] when the load passes."""
    errs = [e for e in w.errors if only is None or e[2] is None or only(e[2]) or e[0] in LOAD_ERRORS]
    srv, cli = w.server.composites, w.client.composites
    for side, comps in (("server", srv), ("client", {c: p for c, p in cli.items() if c not in srv})):
        for c, path in sorted(comps.items()):
            if only is not None and not only(c):
                continue
            for key, typ, dfn in components(w.u.resolve(c)):
                try:
                    if not typ:      # "Type": null -> the component of the definition's class (EntityBuilder.cs:438-447)
                        if dfn is None or w.u.full_type_of(dfn) is None:
                            raise UnknownType(f"component {key}: neither a Type nor a known Definition ({dfn})")
                        typ = types.component_for_definition(w.u.full_type_of(dfn))
                    k = types.classify(typ)
                except UnknownType as ex:
                    errs.append(("unknown-type", side, c, (str(ex),) + path))
                    continue
                if side == "server" and k["client"]:
                    errs.append(("client-type-on-server", side, c,
                                 (f"Client component {k['type']} should not be on server compositions "
                                  f"({k['reason']})",) + path))
                if side == "client" and k["server_only"]:
                    errs.append(("server-only-on-client", side, c,
                                 (f"Server-only component {k['type']} should not be on client compositions "
                                  f"({k['reason']})",) + path))
    return errs


def format_errors(errs, u=None, limit=20):
    out = []
    for code, side, g, detail in errs[:limit]:
        where = f" [{u.origin(g)}]" if u is not None and g else ""
        out.append(f"{code} {side or ''} {g or ''}{where}\n    " + "\n    ".join(map(str, detail)))
    if len(errs) > limit:
        out.append(f"... {len(errs) - limit} more")
    return "\n".join(out)
