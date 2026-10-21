// SwapperReflection: the three BlockMaterialSwapperDefinition internals the Programmable's status lamp needs, found
// once by reflection and kept in one singleton, so every REFLECTION access of ProgrammableLedInjector is in this
// file. If a game update renames any of them, Found turns false and the lamp stays amber (logged once).
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   BlockMaterialSwapperDefinition.WorkingReplacementsMeshParts (public get, private set)
//                                                   Game2.Client/Keen.Game2.Client.WorldObjects.CubeBlocks.Render/BlockMaterialSwapperDefinition.cs:246 [2.4: 244]
//   ... ProcessedWorkingMaterialReplacements (private set)       REFLECTION: re-check after a game update   ibid. :250
//   ... ProcessReplacements(models, pairs) (private), Init's own computation
//                                                                REFLECTION: re-check after a game update   ibid. :274-299
//   DictionaryReader<K, V>                          VRage.Library/Keen.VRage.Library.Collections.Readers/DictionaryReader.cs:14-24
#nullable enable
using System;
using System.Reflection;
using DataCenter.Shared;
using Keen.Game2.Client.WorldObjects.CubeBlocks.Render;
using Keen.VRage.Core.Render.Materials;
using Keen.VRage.Library.Collections.Readers;
using Keen.VRage.Library.Utils;

namespace DataCenter.Programmable;

/// <summary>
/// The reflection seam of <see cref="ProgrammableLedInjector"/>: the private setters of a swapper's Working mesh-part
/// map and of its processed replacements, and the swapper's own <c>ProcessReplacements</c>. One instance per session
/// (<see cref="Instance"/>), resolved when first used.
/// </summary>
internal sealed class SwapperReflection
{
    /// <summary>The session's handles.</summary>
    internal static readonly SwapperReflection Instance = new SwapperReflection();

    // REFLECTION: re-check after a game update (BlockMaterialSwapperDefinition.cs:246, 252, 284 [2.4: 244, 250, 282]).
    private readonly MethodInfo? _setMeshParts = DcReflection.Find(() => typeof(BlockMaterialSwapperDefinition)
        .GetProperty(nameof(BlockMaterialSwapperDefinition.WorkingReplacementsMeshParts), BindingFlags.Instance | BindingFlags.Public)
        ?.GetSetMethod(nonPublic: true));

    private readonly MethodInfo? _setProcessed = DcReflection.Find(() => typeof(BlockMaterialSwapperDefinition)
        .GetProperty("ProcessedWorkingMaterialReplacements", BindingFlags.Instance | BindingFlags.Public)   // by name: its type is VRage.Render's (CS0012)
        ?.GetSetMethod(nonPublic: true));

    private readonly MethodInfo? _processReplacements = DcReflection.Find(() => typeof(BlockMaterialSwapperDefinition)
        .GetMethod("ProcessReplacements", BindingFlags.Instance | BindingFlags.NonPublic));

    /// <summary>Every target was found.</summary>
    internal bool Found => _setMeshParts != null && _setProcessed != null && _processReplacements != null;

    private SwapperReflection()
    {
    }

    /// <summary>The processed replacements the swapper's Init would compute for <paramref name="pairs"/>, or null.</summary>
    internal object? Process(BlockMaterialSwapperDefinition swapper, DictionaryReader<StringId, MaterialDefinition> pairs)
        => _processReplacements!.Invoke(swapper, new object[] { swapper.WorkingReplacementModels, pairs });

    /// <summary>
    /// Sets the Working mesh-part map and the processed replacements together, or neither: if the second setter
    /// throws, the first is put back (the component reads only the processed view), and the exception is rethrown.
    /// </summary>
    internal void Install(BlockMaterialSwapperDefinition swapper, DictionaryReader<StringId, MaterialDefinition> pairs, object processed,
        DictionaryReader<StringId, MaterialDefinition> previous)
    {
        _setMeshParts!.Invoke(swapper, new object[] { pairs });
        try
        {
            _setProcessed!.Invoke(swapper, new[] { processed });
        }
        catch (Exception)
        {
            _setMeshParts.Invoke(swapper, new object[] { previous });
            throw;
        }
    }
}
