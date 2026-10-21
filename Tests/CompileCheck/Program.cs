// Offline replica of the SE2 in-game mod script compile (4.0.0.3151; first written against 2.4.0.95). See CompileCheck.csproj for what and why.
// Copied from an earlier prototype's CompileCheck (the maintainer's own code) and extended for a two-assembly mod.
//
// Mirrors, from the decompiled 4.0.0.3151 code (tools/decompiled-current/...; the VRage.Scripting files cited are
// line-identical to 2.4.0.95):
//  - SpaceEngineers2 GameApp.AddScripting (Keen.Game2/GameApp.cs:467-522): ModCompilationDescriptor for both
//    sub-projects (:475), and the whitelist anchor and MetaDatas lists (:482-521), verbatim (4.0 added ClientId);
//  - VRage.Scripting GameScriptCodeProvider.LoadProjectAssembliesAsync (Keen.VRage.Scripting.Project/
//    GameScriptCodeProvider.cs:29-57): bundle = the .vrgproj Name (:31); Simulation first; Client gets a fresh
//    descriptor plus Simulation's emitted image as a MetadataReference (:46-50);
//  - VRage.Scripting ScriptCodeProvider.LoadScriptingProjectAsync (ScriptCodeProvider.cs:64-92): every *.cs under
//    Scripts/<Sub> (:72), assembly "<Name>.<Sub>" (:77), any error diagnostic fails the load (:80-83);
//  - VRage.Scripting ScriptCompiler.CompileAsync (Keen.VRage.Scripting.Compilation/ScriptCompiler.cs:30-106):
//    pre-processors, generators, analyzers, post-processors, emit.
// Not replicated: Keen's job-scheduler hop (Parallel.MoveTo, :32) and dependency projects' images
// (LocateDependencies, ScriptCodeProvider.cs:94-105; DataCenter's only dependency is Vanilla, which has no scripts).
//
// usage: CompileCheck <modDir> <Simulation|Client|all> [dumpDir]   or   CompileCheck <modDir> probe <file.csx>
//   Simulation  compile Scripts/Simulation;
//   Client      compile Scripts/Simulation (as the reference the game gives Client), then Scripts/Client;
//   all         the same as Client: both, in the game's order;
//   probe       compile an in-game probe the way se-mcp does (ProbeCheck.cs).
// Prints "<Name>.<Sub>: OK: 0 errors, N warning(s)" per compiled project. Exit 0 only when every project compiled.
using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Diagnostics;

internal static class Program
{
    private const string Simulation = "Simulation";
    private const string Client = "Client";

    private static string _game2;

    private static int Main(string[] args)
    {
        // SE2_GAME2 (set by run.sh to the Windows path under wine) wins over the build-time path.
        _game2 = Environment.GetEnvironmentVariable("SE2_GAME2")
            ?? typeof(Program).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>().FirstOrDefault(a => a.Key == "Game2")?.Value;
        if (_game2 == null || !Directory.Exists(_game2))
        {
            Console.Error.WriteLine($"Game2 folder not found: '{_game2}'");
            return 3;
        }
        AssemblyLoadContext.Default.Resolving += (ctx, name) =>
        {
            string p = Path.Combine(_game2, name.Name + ".dll");
            return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
        };

        string modDir = args.Length > 0 ? Path.GetFullPath(args[0]) : FindModDir();
        string which = args.Length > 1 ? args[1] : "all";
        string dumpDir = args.Length > 2 ? args[2] : null;
        if (which == "probe")
            return dumpDir == null ? Usage("probe needs a .csx file") : ProbeCheck.Run(_game2, dumpDir);
        if (which != Simulation && which != Client && which != "all")
            return Usage($"unknown project '{which}': expected Simulation, Client, all or probe");
        return Run(modDir, which, dumpDir).GetAwaiter().GetResult();
    }

    private static int Usage(string error)
    {
        Console.Error.WriteLine(error);
        return 2;
    }

    private static string FindModDir()
    {
        var d = new DirectoryInfo(AppContext.BaseDirectory);
        while (d != null && !d.EnumerateFiles("*.vrgproj").Any())
            d = d.Parent;
        if (d == null)
            throw new InvalidOperationException("no *.vrgproj above " + AppContext.BaseDirectory);
        return d.FullName;
    }

    /// <summary>
    /// The project's Name and Version from its .vrgproj ($Value), the game's bundle (GameScriptCodeProvider.cs:31:
    /// Name, and Version ?? 0.0.0.0). The bundle reaches the generators as build properties.
    /// </summary>
    private static (string Name, Version Version) ProjectIdentity(string modDir)
    {
        string path = Directory.GetFiles(modDir, "*.vrgproj").Single();
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        string name = Path.GetFileNameWithoutExtension(path);
        var version = new Version(0, 0, 0, 0);
        if (doc.RootElement.TryGetProperty("$Value", out var value))
        {
            if (value.TryGetProperty("Name", out var n) && n.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(n.GetString()))
                name = n.GetString();
            if (value.TryGetProperty("Version", out var v) && v.ValueKind == JsonValueKind.String && Version.TryParse(v.GetString(), out var parsed))
                version = parsed;
        }
        return (name, version);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<int> Run(string modDir, string which, string dumpDir)
    {
        ConfigureScripting();
        var (projName, projVersion) = ProjectIdentity(modDir);

        var sim = await CompileProject(modDir, projName, projVersion, Simulation, null, dumpDir);
        if (which == Simulation)
            return sim.Ok ? 0 : 1;
        if (!sim.Ok)
        {
            // The game throws on the Simulation failure (ScriptCodeProvider.cs:80-83) and never compiles Client.
            Console.WriteLine($"{projName}.{Client}: skipped (Simulation failed)");
            return 1;
        }
        var client = await CompileProject(modDir, projName, projVersion, Client, sim.Image, dumpDir);
        return client.Ok ? 0 : 1;
    }

    /// <summary>GameApp.AddScripting (GameApp.cs:482-521 in 4.0.0.3151), the three static lists, verbatim.</summary>
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void ConfigureScripting()
    {
        Keen.Game2.Simulation.Scripting.GameWhitelistProvider<Keen.Game2.Simulation.Scripting.ModWhitelistProvider>.AllowedAssemblies = new Type[11]
        {
            typeof(int),
            typeof(Enumerable),
            typeof(ImmutableArray),
            typeof(Keen.VRage.Core.Render.MeshBuilder),
            typeof(Keen.VRage.Library.Utils.StringId),
            typeof(Keen.VRage.DCS.Components.Entity),
            typeof(Keen.VRage.Core.Game.Data.Blob),
            typeof(Keen.Game2.Simulation.UpdateTime),
            typeof(Keen.Game2.Client.Input.InputGameComponent),
            typeof(Keen.VRage.Physics.IPhysics),
            typeof(Keen.VRage.Multiplayer.ClientId),   // new in 4.0.0.3151
        };
        Keen.Game2.Simulation.Scripting.GameWhitelistProvider<Keen.Game2.Simulation.Scripting.InGameWhitelistProvider>.AllowedAssemblies = new Type[9]
        {
            typeof(int),
            typeof(Enumerable),
            typeof(Keen.VRage.Core.Render.MeshBuilder),
            typeof(Keen.VRage.Library.Utils.StringId),
            typeof(Keen.VRage.DCS.Components.Entity),
            typeof(Keen.VRage.Core.Game.Data.Blob),
            typeof(Keen.Game2.Simulation.UpdateTime),
            typeof(Keen.Game2.Client.Input.InputGameComponent),
            typeof(Keen.VRage.Physics.IPhysics),
        };
        Keen.Game2.Simulation.Scripting.GameCompilationDescriptor.MetaDatas = new Type[11]
        {
            typeof(Keen.VRage.Core.Render.MeshBuilder),
            typeof(Keen.VRage.Library.Utils.StringId),
            typeof(Keen.VRage.DCS.Components.Entity),
            typeof(Keen.VRage.Core.Game.Data.Blob),
            typeof(Keen.Game2.Simulation.UpdateTime),
            typeof(Keen.Game2.Client.Input.InputGameComponent),
            typeof(Keen.VRage.Physics.IPhysics),
            typeof(Keen.VRage.Multiplayer.ClientId),   // new in 4.0.0.3151
            typeof(System.Text.Json.JsonTokenType),
            typeof(System.Collections.Concurrent.ConcurrentDictionary<,>),
            typeof(System.Dynamic.DynamicObject),
        };
    }

    private readonly struct Result
    {
        public readonly bool Ok;
        public readonly byte[] Image;   // null when nothing was emitted
        public Result(bool ok, byte[] image) { Ok = ok; Image = image; }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task<Result> CompileProject(string modDir, string projName, Version projVersion, string sub, byte[] simulationImage, string dumpDir)
    {
        string asmName = projName + "." + sub;
        string scriptsDir = Path.Combine(modDir, "Scripts", sub);
        if (!Directory.Exists(scriptsDir))
        {
            // ScriptCodeProvider.cs:67-70: no folder, no assembly, no error.
            Console.WriteLine($"{asmName}: no {scriptsDir}, nothing to compile");
            return new Result(true, null);
        }

        // GameApp.cs:475: a fresh ModCompilationDescriptor per sub-project; GameScriptCodeProvider.cs:37, 44, 48-49.
        var descriptor = new Keen.Game2.Simulation.Scripting.ModCompilationDescriptor();
        descriptor.SetAssemblyBundle(new Keen.VRage.Library.Reflection.BundleInfo(projName, projVersion));
        if (simulationImage != null)
            descriptor.AddMetadataReference(MetadataReference.CreateFromImage(simulationImage));

        // Hidden entries are skipped by the game's reader (FileSystemExtensions.EnumerateFiles, includeHiddenEntries=false).
        var files = Directory.EnumerateFiles(scriptsDir, "*.cs", SearchOption.AllDirectories)
            .Where(f => !Path.GetRelativePath(scriptsDir, f).Split(Path.DirectorySeparatorChar, '/').Any(p => p.StartsWith('.')))
            .OrderBy(f => f, StringComparer.Ordinal).ToList();
        Console.WriteLine($"{asmName}: {files.Count} file(s) under {scriptsDir}"
            + (simulationImage != null ? $" (+ {projName}.{Simulation} image)" : ""));

        IEnumerable<CSharpSyntaxTree> trees = files.Select(f =>
            (CSharpSyntaxTree)CSharpSyntaxTree.ParseText(
                File.ReadAllText(f), descriptor.ParseOptions,
                // The game's hint name is the reader's path under Scripts/: "<Sub>/<relative path>".
                sub + "/" + Path.GetRelativePath(scriptsDir, f).Replace('\\', '/'), Encoding.UTF32));
        foreach (var pre in descriptor.PreProcessors)
            trees = pre.Process(descriptor, trees);

        var compilation = CSharpCompilation.Create(asmName, trees.ToImmutableArray(), descriptor.MetadataReferences, descriptor.CompilationOptions);
        var analyzers = descriptor.GetAnalyzers(compilation);
        var driver = CSharpGeneratorDriver.Create(
            analyzers.SourceGenerators, analyzers.AnalyzerOptions?.AdditionalFiles, descriptor.ParseOptions,
            analyzers.AnalyzerOptions?.AnalyzerConfigOptionsProvider);
        driver.RunGeneratorsAndUpdateCompilation(compilation, out var outCompilation, out var generatorDiagnostics);
        compilation = (CSharpCompilation)outCompilation;

        if (dumpDir != null)
            Dump(compilation, Path.Combine(dumpDir, sub));

        ImmutableArray<Diagnostic> diagnostics;
        if (analyzers.Analyzers.Length == 0)
            diagnostics = compilation.GetDiagnostics();
        else
            diagnostics = await compilation.WithAnalyzers(analyzers.Analyzers,
                new CompilationWithAnalyzersOptions(analyzers.AnalyzerOptions, null,
                    concurrentAnalysis: true, logAnalyzerExecutionTime: false, compilation.Options.ReportSuppressedDiagnostics, null))
                .GetAllDiagnosticsAsync();

        var all = diagnostics.Concat(generatorDiagnostics).ToList();
        bool hasErrors = all.Any(d => d.Severity == DiagnosticSeverity.Error);
        byte[] image = null;
        if (!hasErrors)
        {
            // ScriptCompiler.cs:47 then :93-106: post-processors (none for mods today), then emit, which must succeed too.
            foreach (var post in descriptor.PostProcessors)
            {
                var processed = post.Process(descriptor, compilation).ToImmutableArray();
                compilation = compilation.RemoveAllSyntaxTrees().AddSyntaxTrees(processed);
            }
            using var pe = new MemoryStream();
            using var pdb = new MemoryStream();
            var emit = compilation.Emit(pe, pdb);
            all.AddRange(emit.Diagnostics.Where(d => !all.Contains(d)));
            hasErrors = !emit.Success;
            if (emit.Success)
            {
                image = pe.ToArray();
                Console.WriteLine($"{asmName}: emitted {image.Length} bytes");
            }
        }

        // run.sh --docs (CC_DOCS=1) lists the missing-XML-doc warnings too; they are only counted otherwise.
        bool showDocs = Environment.GetEnvironmentVariable("CC_DOCS") == "1";
        int errors = 0, warnings = 0, hidden = 0;
        foreach (var d in all.OrderBy(d => d.Severity == DiagnosticSeverity.Error ? 0 : 1)
                     .ThenBy(d => d.Location.SourceTree?.FilePath).ThenBy(d => d.Location.SourceSpan.Start))
        {
            if (d.Severity == DiagnosticSeverity.Error)
                errors++;
            else if (d.Severity != DiagnosticSeverity.Warning)
                continue;
            else if (d.Id is "CS1591" or "KN035")
            {
                hidden++;   // missing XML docs: only warnings in game, and noisy here
                if (!showDocs)
                    continue;
            }
            else
                warnings++;
            Console.WriteLine("  " + d);
        }
        string tail = $"{warnings} warning(s)" + (hidden > 0 ? $" (+{hidden} doc-comment warnings not shown)" : "");
        Console.WriteLine(hasErrors
            ? $"{asmName}: FAILED: {errors} error(s), {tail}"
            : $"{asmName}: OK: 0 errors, {tail}");
        return new Result(!hasErrors, image);
    }

    private static void Dump(Compilation compilation, string dir)
    {
        Directory.CreateDirectory(dir);
        int n = 0;
        foreach (var t in compilation.SyntaxTrees)
        {
            string name = string.IsNullOrEmpty(t.FilePath) ? $"injected_{n++}.cs" : t.FilePath.Replace('/', '_').Replace('\\', '_');
            File.WriteAllText(Path.Combine(dir, name), t.ToString());
        }
    }
}
