// DcLog: the Data Center scripts' only way to the game log. Every line carries the "[DataCenter]" prefix.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...):
//   Log.Default (null when no log singleton is registered)   VRage.Library/Keen.VRage.Library.Diagnostics/Log.cs:91-100
//   Log.Info(string) extension                              VRage.Library/Keen.VRage.Library.Diagnostics/LogExtensions.cs:79
#nullable enable
using System;
using DataCenter.Shared.Core;
using Keen.VRage.Library.Diagnostics;

namespace DataCenter.Shared;

/// <summary>
/// Logging for the Data Center scripts. It never throws: a script that faults must be able to report the fault from
/// inside its own catch block without risking a second exception, and the log may not exist yet (or any more).
/// <para>The one-time memory behind <see cref="Once"/> is session state, so it lives in the single
/// <see cref="Session"/> instance (the singleton the game's analyzer allows static state for, KN023).</para>
/// </summary>
public sealed class DcLog
{
    /// <summary>The prefix of every line, so a player's log can be searched for this mod.</summary>
    public const string Prefix = "[DataCenter] ";

    /// <summary>Distinct <see cref="Once"/> keys remembered before Once stops writing (a guard against unbounded keys).</summary>
    private const int MaxOnceKeys = 256;

    /// <summary>This game session's log memory.</summary>
    private static readonly DcLog Session = new DcLog();

    private readonly OnceGate _logged = new OnceGate(MaxOnceKeys);

    private DcLog()
    {
    }

    /// <summary>Writes <paramref name="msg"/> to the game log.</summary>
    public static void Info(string msg)
    {
        try
        {
            Log.Default?.Info(Prefix + msg);
        }
        catch (Exception)
        {
            // Logging is best effort; there is nowhere left to report a failing log.
        }
    }

    /// <summary>
    /// Writes <paramref name="msg"/> the first time <paramref name="key"/> is seen in this game session, and does
    /// nothing after that. Use a key per fault site (and per block kind), so a fault in a job that runs every frame
    /// costs one log line, not one per frame.
    /// </summary>
    public static void Once(string key, string msg)
    {
        try
        {
            OnceGate.Verdict verdict = Session._logged.Pass(key);
            if (verdict == OnceGate.Verdict.First || verdict == OnceGate.Verdict.LastBeforeFull)
                Info(msg);

            if (verdict == OnceGate.Verdict.LastBeforeFull)
                Info($"{MaxOnceKeys} distinct one-time messages logged; further new ones are suppressed this session.");
        }
        catch (Exception)
        {
            // See Info.
        }
    }
}
