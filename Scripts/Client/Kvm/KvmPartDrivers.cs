// KvmPartDrivers: the KVM's two subpart drivers (Plan 4 Rulings P4-3, P4-10; Task 8): the drawer slides, the screen
// folds, each from its rest transform by the sequencer's pose (KvmPartComponent.cs), every frame in the rigid
// animation update, where the vanilla Translation/RotationAnimation they replace ran.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...):
//   [Definition] field: the composite slot's definition, of exactly the declared type
//                                                                VRage.DCS/Keen.VRage.DCS.Internal/RuntimeComponentInfo.cs:209-217,
//                                                                VRage.DCS/Keen.VRage.DCS.Builders/EntityBuilder.cs:464-511 (AssertMatch)
//   OnUpdateRigidAnimation (after OnPrepareRigidAnimation, before RenderSubmissionBegin); the rigid job shape
//                                                                VRage.Core.Game/.../RigidAnimations/OnUpdateRigidAnimation.cs:8-10, TranslationAnimationComponent.cs:73-87
//   RelativeTransform.Position / Orientation                     VRage.Core/Keen.VRage.Core/RelativeTransform.cs:610, 615
//   Rotation post-multiplied as vanilla does (transform.Orientation *= q)
//                                                                VRage.Core.Game/.../RigidAnimations/RotationAnimationComponent.cs:98, InfiniteRotationAnimationComponent.cs:110-111
//   Quaternion.CreateFromAxisAngle                               VRage.Library/Keen.VRage.Library.Mathematics/Quaternion.cs:1237
#nullable enable
using System;
using DataCenter.Kvm.Core;
using Keen.VRage.Core;
using Keen.VRage.Core.Game.GameSystems.RigidAnimations;
using Keen.VRage.DCS.Annotations;
using Keen.VRage.DCS.Components;
using Keen.VRage.Library.Mathematics;

namespace DataCenter.Kvm;

/// <summary>The drawer: slides <c>Translation x Slide</c> from its rest position.</summary>
public sealed partial class KvmDrawerPart : KvmPartComponent
{
    /// <summary>The data's travel (P4-10: our own definition type).</summary>
    [Definition]
    public readonly KvmDrawerPartDefinition Definition = null!;

    [OnUpdateRigidAnimation]
    [MustHave(typeof(KvmDrawerPart))]
    private static void Apply(ref RelativeTransform transform, KvmDrawerPart part)
    {
        try
        {
            part.Drive(ref transform);
        }
        catch (Exception ex)
        {
            part.Fault("job", ex);
        }
    }

    /// <inheritdoc/>
    protected override void Pose(ref RelativeTransform transform, in RelativeTransform rest, KvmPose pose, KvmMotionTuning tuning)
    {
        transform.Position = rest.Position + Definition.Translation * pose.Slide;
        transform.Orientation = rest.Orientation;
    }
}

/// <summary>The screen: folds <c>Angle x Fold</c> about its hinge axis from its rest orientation.</summary>
public sealed partial class KvmScreenPart : KvmPartComponent
{
    /// <summary>The data's fold (P4-10: our own definition type).</summary>
    [Definition]
    public readonly KvmScreenPartDefinition Definition = null!;

    [OnUpdateRigidAnimation]
    [MustHave(typeof(KvmScreenPart))]
    private static void Apply(ref RelativeTransform transform, KvmScreenPart part)
    {
        try
        {
            part.Drive(ref transform);
        }
        catch (Exception ex)
        {
            part.Fault("job", ex);
        }
    }

    /// <inheritdoc/>
    protected override void Pose(ref RelativeTransform transform, in RelativeTransform rest, KvmPose pose, KvmMotionTuning tuning)
    {
        Quaternion fold = Quaternion.CreateFromAxisAngle(Definition.Axis * tuning.LidAxisSign, Definition.Angle * pose.Fold);
        transform.Position = rest.Position;
        transform.Orientation = rest.Orientation * fold; // post-multiplied, as vanilla's rotation animations do
    }
}
