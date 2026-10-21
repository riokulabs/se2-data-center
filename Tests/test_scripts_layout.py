"""Plan 4 Task 1: the shape and hygiene of the mod's C# scripts (Scripts/).

The game compiles every *.cs under Scripts/<Simulation|Client>/ when it is started with -loadScripts
(VRage.Scripting ScriptCodeProvider.cs:64-92); without the switch the folder is ignored. These checks are the
static half of "a script must never crash the game": layout, the game-free core, and the defensive lint.
The compile itself is Tests/CompileCheck/run.sh; the core's behaviour is Tests/CoreTests.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.scripts   # the whole module is about Scripts/

MOD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(MOD, "Scripts")
# The game-free cores: compiled natively by Tests/CoreTests, and by the game into the script assemblies.
CORES = (os.path.join(SCRIPTS, "Client", "Core"), os.path.join(SCRIPTS, "Simulation", "Shared", "Core"))
CORE_TESTS = os.path.join(MOD, "Tests", "CoreTests")
SE2MOD = os.path.normpath(os.path.join(MOD, "..", "..", "tools", "scripts", "se2mod.py"))

NAMESPACE_RE = re.compile(r"^\s*namespace\s+DataCenter\.[A-Za-z_][\w.]*\s*[;{]", re.MULTILINE)
# A job group is a class deriving from JobGroup; vanilla's are all named On<Something> (OnUpdateRigidAnimation, ...).
JOB_GROUP_DECL_RE = re.compile(r"\bclass\s+(\w+)\s*:\s*(?:[\w.]+\.)?JobGroup\b")
VANILLA_JOB_GROUP_RE = re.compile(r"^On[A-Z]\w*$")
# One attribute section, [A][B(x)] or [A, B]; the names are what matters.
ATTR_NAME_RE = re.compile(r"(?:\[|,)\s*(?:[\w.]+\.)?(\w+)\s*(?=[\](,])")
# A method header: attributes, modifiers, a return type, a name and a parameter list, then its body.
METHOD_RE = re.compile(r"((?:\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]\s*)*)"
                       r"((?:(?:public|private|protected|internal|static|override|virtual|sealed|unsafe|new)\s+)+)"
                       r"[\w<>\[\],.?\s]+?\s(\w+)\s*\([^;{]*?\)\s*\{")


def _cs_files(root):
    out = []
    for dp, _, fs in os.walk(root):
        out += [os.path.join(dp, f) for f in fs if f.endswith(".cs")]
    return sorted(out)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _rel(path):
    return os.path.relpath(path, MOD)


def test_scripts_tree():
    assert os.path.isdir(SCRIPTS), "Scripts/ is missing"
    assert sorted(os.listdir(SCRIPTS)) == ["Client", "Simulation"], \
        f"Scripts/ must hold only Simulation/ and Client/ (the game's scripting sub-projects), got {os.listdir(SCRIPTS)}"
    metas = [_rel(os.path.join(dp, f)) for dp, _, fs in os.walk(SCRIPTS) for f in fs if f.endswith(".meta")]
    assert not metas, f"Scripts/ is not content and must carry no .meta files: {metas}"
    files = _cs_files(SCRIPTS)
    assert files, "Scripts/ holds no .cs file"
    bad = [_rel(f) for f in files if not NAMESPACE_RE.search(_read(f))]
    assert not bad, f"every script must declare a DataCenter.* namespace: {bad}"


def test_core_is_game_free():
    # The cores are compiled natively by Tests/CoreTests with no game DLLs; a Keen reference would break that.
    bad = [_rel(f) for core in CORES for f in _cs_files(core) if "Keen." in _read(f)]
    assert not bad, f"the game-free cores must not reference the game (Keen.*): {bad}"


def _body(text, open_brace):
    """The text of the block that starts at text[open_brace] == '{' (brace matching; strings rarely hold braces)."""
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace:i + 1]
    return text[open_brace:]


def undefended_entry_points(text, job_groups):
    """Names of the jobs and post-processor bodies in `text` whose body has no catch (Exception ...).

    A job is a method carrying a job-group attribute (a declared JobGroup subclass, or vanilla's On<Something>);
    a post-processor body is an override of PostProcess / ReProcess / Unload. An exception escaping either is fatal
    (a job) or fails the definition load (a post-processor)."""
    out = []
    for m in METHOD_RE.finditer(text):
        attrs, modifiers, name = m.group(1), m.group(2), m.group(3)
        attr_names = set(ATTR_NAME_RE.findall(attrs))
        is_job = "static" in modifiers.split() and any(a in job_groups or VANILLA_JOB_GROUP_RE.match(a) for a in attr_names)
        is_post = "override" in modifiers.split() and name in ("PostProcess", "ReProcess", "Unload")
        if (is_job or is_post) and "catch (Exception" not in _body(text, m.end() - 1):
            out.append(name)
    return out


def _job_groups(files):
    return {g for f in files for g in JOB_GROUP_DECL_RE.findall(_read(f))}


def test_lint_finds_unguarded_entry_points():
    """The defensive lint itself: per method, not per file."""
    groups = {"KvmSequenceUpdate"}
    guarded = "try { X(); } catch (Exception ex) { Log(ex); }"
    text = f"""
    public sealed class A : SimpleDefinitionPostProcessor<PrefabDefinition>
    {{
        public override void PostProcess(PrefabDefinition d) {{ {guarded} }}
        public override void Unload() {{ X(); }}
    }}
    public class B : Component
    {{
        [OnUpdateRigidAnimation][MustHave(typeof(B))]
        private static void Apply(ref RelativeTransform t, B p) {{ {guarded} }}
        [OnUpdateRigidAnimation]
        private static void Bare(ref RelativeTransform t, B p) {{ if (p != null) {{ t.Position += p.V; }} }}
        [KvmSequenceUpdate, MustHave(typeof(B))]
        static void Update(B s) {{ s.Step(); }}
        [Obsolete] private static void Helper() {{ X(); }}
        public void NotAJob() {{ X(); }}
    }}"""
    assert sorted(undefended_entry_points(text, groups)) == ["Bare", "Unload", "Update"]


def test_scripts_defensive_lint():
    # An exception escaping a post-processor fails the definition load; one escaping a job is fatal.
    files = _cs_files(SCRIPTS)
    groups = _job_groups(files)
    undefended = [f"{_rel(f)}:{name}" for f in files for name in undefended_entry_points(_read(f), groups)]
    assert not undefended, f"every job and post-processor body must catch (Exception ...): {undefended}"
    # System.Text.Json is referenced but not whitelisted for mods: VRS1001 at load (GameApp.cs:508-521 [2.4: 477-489]).
    json = [_rel(f) for f in _cs_files(SCRIPTS) if "System.Text.Json" in _read(f)]
    assert not json, f"System.Text.Json is banned in mod scripts: {json}"


def test_route_recorded():
    """Ruling P4-1: the Programmable route is recorded in config and NOTES (Route A': the component lives in the data)."""
    sys.path.insert(0, os.path.join(MOD, "Source", "Model"))
    try:
        from dc import config
    finally:
        sys.path.pop(0)
    assert config.PROGRAMMABLE_ROUTE in ("B", "A'")


def test_core_tests_pass(core_tests_lock):
    """Tests/CoreTests: the game-free cores' unit tests (native dotnet, no game DLLs). Under the CoreTests build lock
    (Tests/conftest.py): a parallel worker may be dumping the trajectories from the same project."""
    if not shutil.which("dotnet"):
        pytest.skip("the dotnet SDK is not installed")
    with core_tests_lock():
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", CORE_TESTS], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=600)
    assert r.returncode == 0 and "OK: " in r.stdout, r.stdout[-4000:]


def _game_running():
    if not shutil.which("pgrep"):
        return False
    return subprocess.run(["pgrep", "-x", "Modern.bin"], stdout=subprocess.DEVNULL).returncode == 0


@pytest.mark.sdkbuild
def test_build_hides_scripts():
    """se2mod.py build moves Scripts/ aside for the SDK builder (it compiles scripts against VRage.* only) and back.

    Opt-in (DC_SDK_BUILD=1): a real SDK build takes minutes and rewrites Content/."""
    if os.environ.get("DC_SDK_BUILD") != "1":
        pytest.skip("opt-in: set DC_SDK_BUILD=1 to run the real SDK build")
    if _game_running():
        pytest.skip("the game is running (pgrep -x Modern.bin): build only with the game closed")
    if os.path.basename(MOD) != "DataCenter":
        # se2mod.py resolves mods/<name>; from a worktree it would build the main checkout, not this tree.
        pytest.skip(f"not the mods/DataCenter checkout ({os.path.basename(MOD)}): the controller builds after merging")
    r = subprocess.run([sys.executable, SE2MOD, "build", "DataCenter"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=3600)
    assert r.returncode == 0, r.stdout[-4000:]
    assert os.path.isdir(SCRIPTS), "Scripts/ was not restored after the build"
    assert not os.path.exists(os.path.join(MOD, ".Scripts.hidden-for-build")), "the hidden Scripts/ copy was left behind"


# Entity.Has<T>(out T, conditional = null) asserts "reserved for interfaces or with conditional" when T is a Component
# type and no conditional is passed (VRage.DCS Entity.cs:160 [2.4: 158]; the assembly is built with FEATURE_ASSERTIONS, so it fires
# in shipping builds: an exception, or an assertion report at exit). Our scripts only ever ask for components, so every
# Has(out ...) must pass the conditional, as vanilla does (ThirdPersonCameraComponent.cs:295).
HAS_OUT_RE = re.compile(r"\.Has\s*(?:<[^<>()]*>)?\s*\(\s*out\b")


def bare_has_calls(text):
    """Line numbers of `.Has(out x)` calls in `text` that pass no second argument (the conditional). Line comments
    are ignored (headers cite the API).

    The scan walks the call's first argument, `out <declaration>`, to the first top-level comma (a conditional
    follows) or the closing parenthesis (none does). A declaration holds no comparison, so every `<` in it opens a
    type argument list, and the commas inside one (`Dictionary<A, B>`) separate type arguments, not call arguments."""
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    out = []
    for m in HAS_OUT_RE.finditer(text):
        depth, angles, i, conditional = 1, 0, m.end(), False
        while i < len(text) and depth:
            c = text[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "<":
                angles += 1
            elif c == ">" and angles:
                angles -= 1
            elif c == "," and depth == 1 and not angles:
                conditional = True
                break
            i += 1
        if not conditional:
            out.append(text.count("\n", 0, m.start()) + 1)
    return out


def test_has_lint_bites():
    text = """
    a.Has(out CubeBlockComponent? block);
    b.Has(out _door, AnyDoor);
    c.Has<DoorComponent>(out var d);
    e.Has(out _x, (DoorComponent x) => x.Enabled && Check(x, 1));
    if (f.Has(out g) && h) { }
    // a comment citing Entity.Has(out T) is not a call
    i.Has(out Dictionary<A, B> map);
    j.Has(out Dictionary<A, List<B>>? map, AnyMap);
    k.Has(out Map<A, Map<B, C>> map, (Map<A, Map<B, C>> x) => x.Count < 3);
    l.Has(out x, y => y.Count < 3);
    """
    # the generic commas (lines 8-10) are type arguments: line 8 has no conditional, lines 9 and 10 do
    assert bare_has_calls(text) == [2, 4, 6, 8]


def test_no_bare_entity_has():
    bad = [f"{_rel(f)}:{n}" for f in _cs_files(SCRIPTS) for n in bare_has_calls(_read(f))]
    assert not bad, f"Entity.Has(out T) on a Component type needs a conditional (Entity.cs:160 [2.4: 158] asserts): {bad}"


FORCED_PP_RE = re.compile(
    r"\[DefinitionPostProcessor\([^\]]*ForceInstantiation\s*=\s*true[^\]]*\)\]\s*"
    r"(?:///[^\n]*\n\s*|\[[^\]]*\]\s*)*"
    r"public\s+(?:sealed\s+)?class\s+\w+\s*:\s*\w+<\s*(\w+)\s*>")
# Forcing a type into the Engine set wakes vanilla's post-processors for that type there. PrefabDefinition is proven safe
# (in an earlier prototype); EntityCompositeDefinition crashed the load (ConveyorGraphPostProcessor needs ClientServerInfo).
FORCE_SAFE_TYPES = {"PrefabDefinition"}


def forced_post_processor_types(text):
    return [m.group(1) for m in FORCED_PP_RE.finditer(text)]


def test_forced_lint_bites():
    text = """
    [DefinitionPostProcessor(ForceInstantiation = true)]
    public sealed class A : SimpleDefinitionPostProcessor<EntityCompositeDefinition> { }
    [DefinitionPostProcessor]
    public sealed class B : SimpleDefinitionPostProcessor<BlockMaterialSwapperDefinition> { }
    [DefinitionPostProcessor(false, ForceInstantiation = true)]
    public class C : SimpleDefinitionPostProcessor<PrefabDefinition> { }
    """
    assert forced_post_processor_types(text) == ["EntityCompositeDefinition", "PrefabDefinition"]


def test_no_unsafe_forced_post_processors():
    bad = [f"{_rel(f)}: {t}" for f in _cs_files(SCRIPTS) for t in forced_post_processor_types(_read(f))
           if t not in FORCE_SAFE_TYPES]
    assert not bad, f"ForceInstantiation on these types crashes the Engine set load: {bad}"
