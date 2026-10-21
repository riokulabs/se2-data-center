// KvmPartDefinitions: the definitions of the KVM's two subpart drivers (our own definition types). Each copies
// the data's geometry (travel (0, 0, -0.45), fold 100 degrees about +X) at load from the vanilla definition it
// replaces, so the data keeps owning the geometry. They are our own types because no driver may share a definition
// type with a vanilla component: an untyped composite entry of another mod resolves its component by definition
// type, and two components declaring TranslationAnimationDefinition would make that an "Ambiguous match".
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...):
//   Definition (public parameterless ctor; Guid / DebugName)     VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343, 346, 489
//   [Serialize] (the Library generator makes every Definition subclass serializable)
//                                                                VRage.Library/Keen.VRage.Library.Serialization/SerializeAttribute.cs
//   TranslationAnimationDefinition.Translation / Speed           VRage.Core.Game/Keen.VRage.Core.Game.GameSystems.RigidAnimations/TranslationAnimationDefinition.cs:194, 200
//   RotationAnimationDefinition.RotationAxis / AngularSpeed / RotationAngle (degrees)
//                                                                VRage.Core.Game/.../RigidAnimations/RotationAnimationDefinition.cs:216, 222, 228
//   ... and why the type must be our own: FindComponentWithDefinitionType throws "Ambiguous match"
//                                                                VRage.DCS/Keen.VRage.DCS.Internal/ComponentInfoIndexer.cs:75-90
//   MathHelper.ToRadians                                         VRage.Library/Keen.VRage.Library.Mathematics/MathHelper.cs:56
#nullable enable
using DataCenter.Shared;
using Keen.VRage.Core.Game.GameSystems.RigidAnimations;
using Keen.VRage.Library.Definitions;
using Keen.VRage.Library.Mathematics;
using Keen.VRage.Library.Serialization;

namespace DataCenter.Kvm;

/// <summary>
/// The drawer driver's definition: the data's travel, copied at load from the drawer's vanilla
/// <see cref="TranslationAnimationDefinition"/> (<see cref="DcGuids.KvmDrawerTranslationDef"/>). Built in code by
/// <see cref="KvmInjector"/>, never loaded from data, so it exists only where the scripts run. It is a full
/// serializable definition type only because the game's generator makes every Definition subclass one; its object
/// builder is never used.
/// </summary>
[Serialize]
public sealed partial class KvmDrawerPartDefinition : Definition
{
    /// <summary>Full travel in the parent's frame (the data: (0, 0, -0.45) m, out of the block's front).</summary>
    public Vector3 Translation { get; private set; }

    /// <summary>The data's definition this one was built from.</summary>
    [NoSerialize]
    public TranslationAnimationDefinition? Data { get; private set; }

    /// <summary>An empty definition (the generator's requirement; use <see cref="From"/>).</summary>
    public KvmDrawerPartDefinition()
    {
    }

    /// <summary>The driver's definition for the data's <paramref name="data"/>.</summary>
    public static KvmDrawerPartDefinition From(TranslationAnimationDefinition data)
        => new KvmDrawerPartDefinition { Translation = data.Translation, Data = data };
}

/// <summary>
/// The screen driver's definition: the data's fold, copied at load from the screen's vanilla
/// <see cref="RotationAnimationDefinition"/> (<see cref="DcGuids.KvmScreenRotationDef"/>). See
/// <see cref="KvmDrawerPartDefinition"/>.
/// </summary>
[Serialize]
public sealed partial class KvmScreenPartDefinition : Definition
{
    /// <summary>The hinge axis in the parent's frame, unit length (the data: +X).</summary>
    public Vector3 Axis { get; private set; }

    /// <summary>The full fold, radians (the data: 100 degrees).</summary>
    public float Angle { get; private set; }

    /// <summary>The data's definition this one was built from.</summary>
    [NoSerialize]
    public RotationAnimationDefinition? Data { get; private set; }

    /// <summary>An empty definition (the generator's requirement; use <see cref="From"/>).</summary>
    public KvmScreenPartDefinition()
    {
    }

    /// <summary>The driver's definition for the data's <paramref name="data"/>.</summary>
    public static KvmScreenPartDefinition From(RotationAnimationDefinition data)
    {
        Vector3 axis = data.RotationAxis;
        float length = axis.Length();
        return new KvmScreenPartDefinition
        {
            Axis = length > 1e-6f ? axis / length : new Vector3(1f, 0f, 0f),
            Angle = MathHelper.ToRadians(data.RotationAngle),
            Data = data,
        };
    }
}
