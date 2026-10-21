// DcReflection: the two helpers every reflection seam of the Data Center scripts shares (CompositionReflection here,
// SwapperReflection in DataCenter.Client): a lookup that treats any failure as "gone", and the unwrapping of a
// reflected call's exception for the log.
//
// Game APIs: none (System.Reflection only).
#nullable enable
using System;
using System.Reflection;

namespace DataCenter.Shared;

/// <summary>Reflection helpers that never throw.</summary>
public static class DcReflection
{
    /// <summary>
    /// The result of <paramref name="lookup"/>, or null when it throws (an <c>AmbiguousMatchException</c> after a game
    /// update added an overload, a type that failed to load, and friends): a target that cannot be found unambiguously
    /// is treated as gone, and each caller reports that on first use.
    /// </summary>
    public static T? Find<T>(Func<T?> lookup) where T : class
    {
        try
        {
            return lookup();
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>"Type: message" of the exception a reflected call threw (the inner one of a TargetInvocationException).</summary>
    public static string Unwrap(Exception ex)
    {
        Exception inner = ex is TargetInvocationException { InnerException: { } e } ? e : ex;
        return inner.GetType().Name + ": " + inner.Message;
    }
}
