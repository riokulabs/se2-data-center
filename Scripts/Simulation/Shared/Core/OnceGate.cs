// OnceGate: the game-free "first time per key" memory behind DcLog.Once, bounded, thread-safe. No game types here.
#nullable enable
using System;
using System.Collections.Generic;

namespace DataCenter.Shared.Core;

/// <summary>Remembers keys and answers whether a key is new, up to a fixed number of keys.</summary>
public sealed class OnceGate
{
    private readonly object _gate = new object();
    private readonly HashSet<string> _seen = new HashSet<string>(StringComparer.Ordinal);
    private readonly int _capacity;

    /// <summary>A gate that admits up to <paramref name="capacity"/> distinct keys (at least one).</summary>
    public OnceGate(int capacity)
    {
        _capacity = Math.Max(1, capacity);
    }

    /// <summary>What <see cref="Pass"/> decided for a key.</summary>
    public enum Verdict
    {
        /// <summary>The key was seen before: stay quiet.</summary>
        Seen,

        /// <summary>A new key: speak.</summary>
        First,

        /// <summary>A new key, and the gate just became full: say this once, then nothing new is admitted.</summary>
        LastBeforeFull,

        /// <summary>The gate is full: stay quiet.</summary>
        Full,
    }

    /// <summary>Records <paramref name="key"/> (null counts as the empty key) and says whether it is new.</summary>
    public Verdict Pass(string? key)
    {
        lock (_gate)
        {
            if (_seen.Count >= _capacity)
                return _seen.Contains(key ?? string.Empty) ? Verdict.Seen : Verdict.Full;

            if (!_seen.Add(key ?? string.Empty))
                return Verdict.Seen;

            return _seen.Count == _capacity ? Verdict.LastBeforeFull : Verdict.First;
        }
    }
}
