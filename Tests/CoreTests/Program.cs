// CoreTests: the native runner for the game-free cores (Scripts/Client/Core, Scripts/Simulation/Shared/Core), the
// pattern of an earlier prototype.
//
//   dotnet run -c Release                    run every registered test
//   dotnet run -c Release -- --dump <dir>    also let tests write their trajectories (CSV/JSON) into <dir>, for the
//                                            Python geometry checks and the motion charts
//   dotnet run -c Release -- --verbose       also print every passing check (the measured margins live in the names)
//
// Prints "OK: N checks" and exits 0, or one "FAIL: ..." line per failed check, then "FAILED: F of N checks", exit 1.
// A test that throws counts as one failed check and the run goes on. A passing dump ends by stamping the digest of
// the motion core's sources into <dir>/core_sources.sha256 (CoreSourcesDigest), which the Python freshness tests
// compare with the sources on disk (dc/kvm_motion.core_sources_digest).
#nullable enable
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;

internal static class Program
{
    /// <summary>
    /// Every test, in run order. A test is a static method that calls <see cref="Check"/>; add new ones here
    /// (the kvm.* tests cover the motion core; runtime.* the sequencer's decisions).
    /// </summary>
    private static readonly List<(string Name, Action Run)> Tests = new List<(string, Action)>
    {
        ("surgery.dependency_order", SurgeryRulesTests.DependencyOrder),
        ("surgery.retag", SurgeryRulesTests.Retag),
        ("surgery.object_builder_keys", SurgeryRulesTests.ObjectBuilderKeys),
        ("surgery.shared_composition", SurgeryRulesTests.SharedComposition),
        ("log.once_gate", SurgeryRulesTests.OnceGateBudget),
        ("surgery.combine_verdicts", SurgeryRulesTests.CombineVerdicts),
        ("status_lamp.adds_once", StatusLampRulesTests.AddsOnce),
        ("status_lamp.keeps_other_mappings", StatusLampRulesTests.KeepsOtherMappings),
        ("status_lamp.refusals", StatusLampRulesTests.Refusals),
        ("programmable.scripting_presence", ScriptingPresenceTests.Verdicts),
        ("kvm.open_sequence_order", KvmMotionTests.OpenSequenceOrder),
        ("kvm.open_settles_within", KvmMotionTests.OpenSettlesWithin),
        ("kvm.close_sequence_order", KvmMotionTests.CloseSequenceOrder),
        ("kvm.close_settles_within", KvmMotionTests.CloseSettlesWithin),
        ("kvm.fast_stow_settles_within", KvmMotionTests.FastStowSettlesWithin),
        ("kvm.fold_bounce_subtle", KvmMotionTests.FoldBounceSubtle),
        ("kvm.endpoints", KvmMotionTests.Endpoints),
        ("kvm.monotonicity", KvmMotionTests.Monotonicity),
        ("kvm.stop_landings_soft", KvmMotionTests.StopLandingsSoft),
        ("kvm.slide_hard_stops", KvmMotionTests.SlideHardStops),
        ("kvm.reversal_is_continuous", KvmMotionTests.ReversalIsContinuous),
        ("kvm.dt_independence", KvmMotionTests.DtIndependence),
        ("kvm.integrator_is_exact", KvmMotionTests.IntegratorIsExact),
        ("kvm.deterministic", KvmMotionTests.Deterministic),
        ("kvm.snap_is_immediate", KvmMotionTests.SnapIsImmediate),
        ("kvm.spawn_policy_snaps_only_on_scene_entry", KvmMotionTests.SpawnPolicySnapsOnlyOnSceneEntry),
        ("kvm.retract_waits_for_a_falling_lid", KvmMotionTests.RetractWaitsForAFallingLid),
        ("kvm.leaves_the_stop_at_once", KvmMotionTests.LeavesTheStopAtOnce),
        ("kvm.dt_zero_noop", KvmMotionTests.DtZeroNoop),
        ("kvm.nan_guard", KvmMotionTests.NanGuard),
        ("kvm.large_dt_stable", KvmMotionTests.LargeDtStable),
        ("kvm.step_allocates_nothing", KvmMotionTests.StepAllocatesNothing),
        ("kvm.tuning_sanitises", KvmMotionTests.TuningSanitises),
        ("kvm.front_cell_all_24_orientations", KvmMotionTests.FrontCellAll24Orientations),
        ("kvm.front_cell_beside_finds_the_rack", KvmMotionTests.FrontCellBesideFindsTheRack),
        ("kvm.trajectories", KvmMotionTests.Trajectories),
        ("kvm.reversal_sweep", KvmMotionTests.ReversalSweep),
        ("runtime.interlock_rules", KvmRuntimeTests.InterlockRules),
        ("runtime.door_open_delay", KvmRuntimeTests.DoorOpenDelay),
        ("runtime.fast_stow_on_closing", KvmRuntimeTests.FastStowOnClosing),
        ("runtime.entry_window_snaps", KvmRuntimeTests.EntryWindowSnaps),
        ("runtime.part_spawn_policy", KvmRuntimeTests.PartSpawnPolicy),
        ("runtime.fault_budget", KvmRuntimeTests.FaultBudget),
        ("runtime.data_only_path", KvmRuntimeTests.DataOnlyPath),
        ("runtime.path_switch", KvmRuntimeTests.PathSwitch),
        ("runtime.update_allocates_nothing", KvmRuntimeTests.UpdateAllocatesNothing),
        ("runtime.robust", KvmRuntimeTests.Robust),
        ("runtime.rack_slots", KvmRuntimeTests.RackSlots),
        ("runtime.door_face_side", KvmRuntimeTests.DoorFaceSide),
        ("runtime.routing_table", KvmRuntimeTests.RoutingTable),
    };

    private static int _checks;
    private static int _failures;
    private static string? _test;
    private static bool _verbose;

    /// <summary>The --dump directory, or null when the run does not dump.</summary>
    public static string? DumpDir { get; private set; }

    /// <summary>Records one check; a failure prints the test and check names and fails the run.</summary>
    public static void Check(bool ok, string name)
    {
        _checks++;
        if (ok)
        {
            if (_verbose)
                Console.WriteLine($"ok: {_test}: {name}");
            return;
        }

        _failures++;
        Console.WriteLine($"FAIL: {_test}: {name}");
    }

    /// <summary>Writes <paramref name="contents"/> to <c>&lt;dump dir&gt;/<paramref name="fileName"/></c> when dumping.</summary>
    public static void Dump(string fileName, string contents)
    {
        if (DumpDir == null)
            return;

        File.WriteAllText(Path.Combine(DumpDir, fileName), contents);
    }

    private static int Main(string[] args)
    {
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--dump" && i + 1 < args.Length)
            {
                DumpDir = Path.GetFullPath(args[++i]);
                Directory.CreateDirectory(DumpDir);
            }
            else if (args[i] == "--verbose")
            {
                _verbose = true;
            }
            else
            {
                Console.Error.WriteLine($"unknown argument '{args[i]}' (usage: CoreTests [--dump <dir>] [--verbose])");
                return 2;
            }
        }

        foreach ((string name, Action run) in Tests)
        {
            _test = name;
            try
            {
                run();
            }
            catch (Exception ex)
            {
                Check(false, $"threw {ex.GetType().Name}: {ex.Message}");
            }
        }

        if (_failures == 0 && DumpDir != null)
            File.WriteAllText(Path.Combine(DumpDir, SourcesStamp), CoreSourcesDigest(CoreDir(), SharedCoreDir()) + "\n");

        Console.WriteLine(_failures == 0 ? $"OK: {_checks} checks" : $"FAILED: {_failures} of {_checks} checks");
        return _failures == 0 ? 0 : 1;
    }

    /// <summary>The stamp a passing dump leaves next to its files: the core digest it was made from.</summary>
    private const string SourcesStamp = "core_sources.sha256";

    /// <summary>
    /// SHA-256 (lower-case hex) of the game-free cores: for each directory in turn, each <c>*.cs</c> in ordinal
    /// file-name order: the file name, a newline, the text with CRLF read as LF, a newline. The twin of
    /// dc/kvm_motion.core_sources_digest: the two must agree byte for byte.
    /// </summary>
    private static string CoreSourcesDigest(params string[] coreDirs)
    {
        using var sha = SHA256.Create();
        using var all = new MemoryStream();
        foreach (string coreDir in coreDirs)
        {
            var files = new List<string>(Directory.GetFiles(coreDir, "*.cs"));
            files.Sort((a, b) => string.CompareOrdinal(Path.GetFileName(a), Path.GetFileName(b)));
            foreach (string file in files)
            {
                byte[] name = Encoding.UTF8.GetBytes(Path.GetFileName(file) + "\n");
                byte[] text = File.ReadAllBytes(file);
                all.Write(name);
                for (int i = 0; i < text.Length; i++)
                {
                    if (!(text[i] == (byte)'\r' && i + 1 < text.Length && text[i + 1] == (byte)'\n'))
                        all.WriteByte(text[i]);
                }

                all.WriteByte((byte)'\n');
            }
        }

        return Convert.ToHexString(sha.ComputeHash(all.ToArray())).ToLowerInvariant();
    }

    /// <summary>Scripts/Client/Core, found from this file's own path (the runner builds from its source folder).</summary>
    private static string CoreDir([CallerFilePath] string self = "")
        => Path.GetFullPath(Path.Combine(Path.GetDirectoryName(self)!, "..", "..", "Scripts", "Client", "Core"));

    /// <summary>Scripts/Simulation/Shared/Core, the shared rules CoreTests also compiles.</summary>
    private static string SharedCoreDir([CallerFilePath] string self = "")
        => Path.GetFullPath(Path.Combine(Path.GetDirectoryName(self)!, "..", "..", "Scripts", "Simulation", "Shared", "Core"));
}
