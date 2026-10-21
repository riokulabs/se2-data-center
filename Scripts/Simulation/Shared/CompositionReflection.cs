// CompositionReflection: the two engine internals composition surgery cannot do without, found once by reflection
// and kept in one singleton, so every REFLECTION access of the surgery is in this file. If a game update renames
// either, Found turns false and every edit is refused (logged) instead of failing at its first use.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   EntityCompositeDefinition.Assign(Builder), internal         REFLECTION: re-check after a game update
//                                                   VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:596-608 [2.4: 568-580]
//   PrefabDefinition._entity, private (an EntityObjectBuilder)   REFLECTION: re-check after a game update
//                                                   VRage.Core.Game/Keen.VRage.Core.Game.Definitions/PrefabDefinition.cs:221 [2.4: 219]
#nullable enable
using System;
using System.Reflection;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.DCS.ObjectBuilders;

namespace DataCenter.Shared;

/// <summary>
/// The reflection seam of <see cref="CompositionSurgery"/>: <c>EntityCompositeDefinition.Assign</c> (install a
/// rebuilt composition in place) and <c>PrefabDefinition._entity</c> (a prefab's object builders). One instance per
/// session (<see cref="Instance"/>), resolved when first used.
/// </summary>
internal sealed class CompositionReflection
{
    /// <summary>The session's handles.</summary>
    internal static readonly CompositionReflection Instance = new CompositionReflection();

    // REFLECTION: re-check after a game update (EntityCompositeDefinition.cs:596 [2.4: 568]).
    private readonly MethodInfo? _assign = DcReflection.Find(() => typeof(EntityCompositeDefinition).GetMethod(
        "Assign", BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { typeof(EntityCompositeDefinition.Builder) }, null));

    // REFLECTION: re-check after a game update (PrefabDefinition.cs:221 [2.4: 219]).
    private readonly FieldInfo? _prefabEntity = DcReflection.Find(() => typeof(PrefabDefinition).GetField(
        "_entity", BindingFlags.Instance | BindingFlags.NonPublic));

    /// <summary>Both targets were found.</summary>
    internal bool Found => _assign != null && _prefabEntity != null;

    /// <summary><c>Assign</c> was found (all a swap needs).</summary>
    internal bool CanAssign => _assign != null;

    private CompositionReflection()
    {
    }

    /// <summary>The prefab's entity object builder (its composition and object builders), or null.</summary>
    internal EntityObjectBuilder? EntityOf(PrefabDefinition prefab) => _prefabEntity?.GetValue(prefab) as EntityObjectBuilder;

    /// <summary>Installs <paramref name="builder"/>'s components in <paramref name="composition"/>, in place.</summary>
    internal void Assign(EntityCompositeDefinition composition, EntityCompositeDefinition.Builder builder)
    {
        if (_assign == null)
            throw new MissingMethodException(nameof(EntityCompositeDefinition), "Assign");

        _assign.Invoke(composition, new object[] { builder });
    }
}
