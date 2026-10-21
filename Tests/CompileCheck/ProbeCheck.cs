// ProbeCheck: compiles an in-game probe (a .csx run through se-mcp's execute_code, or tools/scripts/se2game.py exec)
// the way the SeMcp2 plugin compiles it, against the game's own assemblies, so a probe's compile errors show offline
// instead of at the first in-game run. Compile only: nothing is emitted or run.
//
// Mirrors the SeMcp2 plugin (Pulsar Modern's SeMcp2 Bin/plugin.dll, decompiled):
//  - Shared.Se2/ScriptDefaults.cs Usings: the default using directives, verbatim;
//  - Shared.Mcp/Compiler.cs:414 Compile: the code becomes the body of an iterator method Run() of a class __REPL__
//    (with Console bound to a writer), so local functions and variables are fine and `return` is not;
//  - Compiler.cs:242-265: Latest language version, a library, unsafe allowed, internal metadata imported and the
//    accessibility checks off (TopLevelBinderFlags.IgnoreAccessibility, an internal Roslyn option set by reflection).
// Not replicated: the plugin's extern aliases and type hiding for clashing assemblies (ScriptReferences.Collect);
// here every managed Game2 DLL is referenced as is, plus the runtime's own framework assemblies.
//
// usage: CompileCheck <modDir> probe <file.csx>      (run.sh probe <file.csx>)
// Prints "probe <file>: OK: 0 errors, N warning(s)" or each error at its line in the .csx, then FAILED; exit 0 or 1.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

internal static class ProbeCheck
{
    // ScriptDefaults.Usings, verbatim.
    private const string Usings = "using System;\nusing System.Collections;\nusing System.Collections.Generic;\nusing System.Collections.Concurrent;\nusing System.Collections.Immutable;\nusing System.Globalization;\nusing System.IO;\nusing System.Linq;\nusing System.Text;\nusing System.Text.RegularExpressions;\nusing System.Reflection;\nusing Keen.VRage.Core;\nusing Keen.VRage.Core.Game.Systems;\nusing Keen.VRage.Core.Game.Components;\nusing Keen.VRage.Library.Utils;\nusing Keen.VRage.Library.Mathematics;\nusing Keen.VRage.Library.Collections;\nusing Keen.VRage.DCS.Components;\nusing Keen.VRage.DCS.Accessors;\nusing Keen.VRage.DCS.Scenes;\nusing Keen.VRage.Render12.EngineComponents;\nusing Keen.Game2;\nusing Keen.Game2.Simulation.WorldObjects.CubeGrids;\nusing Keen.Game2.Simulation.WorldObjects.CubeBlocks;\nusing Keen.Game2.Simulation.WorldObjects.Characters;\nusing Keen.Game2.Client.GameSystems.PlayerControl;\n";

    // Compiler.Compile's wrapper around the code (the synchronous entry).
    private const string Prefix = "public class __REPL__\n{\n    static class __Out { public static global::System.IO.TextWriter W = null; }\n    static global::System.IO.TextWriter Console => __Out.W;\n    public IEnumerable<object> Run()\n    {\n";
    private const string Suffix = "        yield break;\n    }\n}";

    public static int Run(string game2, string csx)
    {
        if (!File.Exists(csx))
        {
            Console.Error.WriteLine($"probe not found: {csx}");
            return 2;
        }

        string head = Usings + Prefix;
        int offset = head.Count(c => c == '\n');
        var tree = CSharpSyntaxTree.ParseText(head + File.ReadAllText(csx) + "\n" + Suffix,
            new CSharpParseOptions(LanguageVersion.Latest), Path.GetFileName(csx));
        var compilation = CSharpCompilation.Create("__REPL__probe", new[] { tree }, References(game2), Options());

        var shown = compilation.GetDiagnostics()
            .Where(d => d.Severity == DiagnosticSeverity.Error || d.Severity == DiagnosticSeverity.Warning)
            .OrderBy(d => d.Location.SourceSpan.Start).ToList();
        int errors = 0, warnings = 0;
        foreach (var d in shown)
        {
            bool error = d.Severity == DiagnosticSeverity.Error;
            errors += error ? 1 : 0;
            warnings += error ? 0 : 1;
            var span = d.Location.GetLineSpan();
            int line = span.StartLinePosition.Line + 1 - offset;   // the line in the .csx (<= 0: the wrapper)
            Console.WriteLine($"  {Path.GetFileName(csx)}({line},{span.StartLinePosition.Character + 1}): {(error ? "error" : "warning")} {d.Id}: {d.GetMessage()}");
        }

        string name = "probe " + Path.GetFileName(csx);
        Console.WriteLine(errors == 0 ? $"{name}: OK: 0 errors, {warnings} warning(s)" : $"{name}: FAILED: {errors} error(s), {warnings} warning(s)");
        return errors == 0 ? 0 : 1;
    }

    private static CSharpCompilationOptions Options()
    {
        var options = new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary, allowUnsafe: true)
            .WithMetadataImportOptions(MetadataImportOptions.Internal);
        // TopLevelBinderFlags is internal (Compiler.cs:264-265 sets it the same way).
        var flagsType = typeof(CSharpCompilationOptions).Assembly.GetType("Microsoft.CodeAnalysis.CSharp.BinderFlags", throwOnError: true);
        var with = typeof(CSharpCompilationOptions).GetMethod("WithTopLevelBinderFlags", BindingFlags.Instance | BindingFlags.NonPublic,
            null, new[] { flagsType }, null) ?? throw new MissingMethodException(nameof(CSharpCompilationOptions), "WithTopLevelBinderFlags");
        return (CSharpCompilationOptions)with.Invoke(options, new[] { Enum.Parse(flagsType, "IgnoreAccessibility") });
    }

    /// <summary>Every managed DLL of the game, then the running runtime's framework assemblies the game does not ship.</summary>
    private static List<MetadataReference> References(string game2)
    {
        var refs = new List<MetadataReference>();
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string dll in Directory.GetFiles(game2, "*.dll").OrderBy(f => f, StringComparer.Ordinal))
        {
            if (IsManaged(dll) && names.Add(Path.GetFileNameWithoutExtension(dll)))
                refs.Add(MetadataReference.CreateFromFile(dll));
        }

        string tpa = AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") as string ?? "";
        foreach (string dll in tpa.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            if (IsManaged(dll) && names.Add(Path.GetFileNameWithoutExtension(dll)))
                refs.Add(MetadataReference.CreateFromFile(dll));
        }

        return refs;
    }

    private static bool IsManaged(string path)
    {
        try
        {
            using var stream = File.OpenRead(path);
            using var pe = new PEReader(stream);
            return pe.HasMetadata && pe.GetMetadataReader().IsAssembly;
        }
        catch (BadImageFormatException)
        {
            return false;
        }
    }
}
