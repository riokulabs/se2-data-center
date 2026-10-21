// SurgeryEdit: one validated composition edit, prepared by CompositionSurgery and not yet applied. It holds the two
// halves of a transaction: the commit, and the rollback that restores what the commit changed.
//
// Game APIs: none (the edits' closures call CompositionSurgery's, which cite theirs).
#nullable enable
using System;

namespace DataCenter.Shared;

/// <summary>
/// A validated composition edit that has not been applied yet (<see cref="CompositionSurgery.PrepareAdd"/>,
/// <see cref="CompositionSurgery.PrepareSwap"/>). Apply it, alone or together with others, with
/// <see cref="CompositionSurgery.Apply"/>; until then nothing has changed, so preparing is always safe (the in-game
/// probe prepares edits to exercise the refusals and never applies them).
/// </summary>
public sealed class SurgeryEdit
{
    private readonly Action _commit;
    private readonly Action _rollback;

    /// <summary>What the edit does, for the log.</summary>
    public string What { get; }

    internal SurgeryEdit(string what, Action commit, Action rollback)
    {
        What = what;
        _commit = commit;
        _rollback = rollback;
    }

    internal void Commit() => _commit();

    internal void Rollback() => _rollback();
}
