// KvmInjector: the load-time surgery that turns the data-only KVM into the scripted one (Plan 4 Rulings P4-3, P4-10;
// Task 8). With scripts off this file never loads and the KVM keeps its vanilla Translation/RotationAnimation pair.
// Three edits, all client-side definitions (client entities are never saved):
//   1. KvmClientPrefab: append KvmSequencerComponent (id DcGuids.KvmSequencerComponentId, no definition, null object
//      builder) after the PowerableBlockComponent it depends on;
//   2. KvmDrawerComposite: TranslationAnimationComponent -> KvmDrawerPart, with a KvmDrawerPartDefinition built from
//      the slot's TranslationAnimationDefinition;
//   3. KvmScreenComposite: RotationAnimationComponent -> KvmScreenPart, with a KvmScreenPartDefinition likewise.
//
// All or nothing. A partial application can freeze the KVM: drivers with no sequencer rest at their spawn pose, so a
// failed (1) with a working (2) or (3) would leave a Working KVM stowed for good. So every edit is prepared (validated,
// nothing changed) first; any refusal applies none of them, and the KVM keeps the whole vanilla motion. The applied
// ones are rolled back if a later one throws (CompositionSurgery.Apply). Every edit is idempotent, so a definition
// reload, which re-runs post-processors of the reloaded type only, re-applies whatever the reload restored: hence two
// post-processors (prefabs and composites, KvmInjectorPostProcessors.cs), one routine.
//
// The remaining partial states are benign and none freezes: the vanilla parts with a sequencer (a composite reloaded
// while the prefab was not, before our composite post-processor re-runs) animate as data-only, and the sequencer only
// computes an unused pose.
//
// Game APIs (decompiled 2.4.0.95, tools/decompiled/...; "N [2.4: M]" = line N in 4.0.0.3151, tools/decompiled-current/...):
//   Definition.Guid / DebugName                     VRage.Library/Keen.VRage.Library.Definitions/Definition.cs:343, 346
//   EntityCompositeDefinition.Types / Definitions   VRage.DCS/Keen.VRage.DCS.Definitions/EntityCompositeDefinition.cs:534-546 [2.4: 506-518]
//   TranslationAnimationComponent / RotationAnimationComponent (the replaced vanilla parts; FBAC toggles them)
//                                                   VRage.Core.Game/.../RigidAnimations/TranslationAnimationComponent.cs:21, RotationAnimationComponent.cs:21,
//                                                   Game2.Simulation/Keen.Game2.Simulation.GameSystems.RigidAnimations/FunctionalBlockAnimationControllerComponent.cs:15-27
#nullable enable
using System;
using System.Collections.Generic;
using DataCenter.Shared;
using DataCenter.Shared.Core;
using Keen.VRage.Core.Game.Definitions;
using Keen.VRage.Core.Game.GameSystems.RigidAnimations;
using Keen.VRage.DCS.Definitions;
using Keen.VRage.Library.Definitions;

namespace DataCenter.Kvm;

/// <summary>What the KVM injection did this session (read by the in-game probe).</summary>
public enum KvmInjectionState
{
    /// <summary>The post-processors have not run on the KVM (scripts on, but the KVM's definitions not loaded?).</summary>
    NotRun,

    /// <summary>All three edits are in place: the KVM is scripted.</summary>
    Applied,

    /// <summary>Refused or failed (logged): the KVM keeps the whole data-only motion.</summary>
    DataOnly,
}

/// <summary>
/// The all-or-nothing KVM surgery, shared by the two post-processors. Its outcome is session state, so it lives in
/// the single <see cref="Session"/> instance (the singleton the game's analyzer allows static state for, KN023).
/// </summary>
public sealed class KvmInjector
{
    private const string What = "script the KVM";

    /// <summary>This session's injection.</summary>
    private static readonly KvmInjector Session = new KvmInjector();

    /// <summary>The outcome of the last run.</summary>
    public static KvmInjectionState State => Session._state;

    /// <summary>Runs (so far) that found something to apply; later runs find everything in place.</summary>
    public static int Applications => Session._applications;

    private KvmInjectionState _state = KvmInjectionState.NotRun;
    private int _applications;

    private KvmInjector()
    {
    }

    /// <summary>
    /// Prepares the three edits and applies them together, or none. <paramref name="lookup"/> finds a definition by
    /// GUID (the post-processor's manager); <paramref name="allPrefabs"/> lists every prefab (the sharing check).
    /// </summary>
    internal static void Run(Func<Guid, Definition?> lookup, Func<IEnumerable<PrefabDefinition>> allPrefabs)
        => Session.Inject(lookup, allPrefabs);

    /// <summary>A post-processor's own exception: logged once; the KVM keeps the data-only motion.</summary>
    internal static void Report(string site, Exception ex)
    {
        Session._state = KvmInjectionState.DataOnly;
        DcLog.Once("kvm-inject-ex:" + site, $"KVM: the {site} post-processor threw {ex.GetType().Name}: {ex.Message}; the KVM keeps the data-only motion.");
    }

    private void Inject(Func<Guid, Definition?> lookup, Func<IEnumerable<PrefabDefinition>> allPrefabs)
    {
        PrefabDefinition? prefab = lookup(DcGuids.KvmClientPrefab) as PrefabDefinition;
        EntityCompositeDefinition? drawer = lookup(DcGuids.KvmDrawerComposite) as EntityCompositeDefinition;
        EntityCompositeDefinition? screen = lookup(DcGuids.KvmScreenComposite) as EntityCompositeDefinition;
        if (prefab == null || drawer == null || screen == null)
        {
            Refuse("missing", $"the KVM's client prefab or subpart composites are not loaded (prefab {prefab != null}, drawer {drawer != null}, screen {screen != null})");
            return;
        }

        SurgeryVerdict addSequencer = CompositionSurgery.PrepareAdd(prefab, DcGuids.KvmSequencerComponentId, typeof(KvmSequencerComponent),
            null, null, allPrefabs(), out SurgeryEdit? sequencerEdit);
        SurgeryVerdict swapDrawer = PrepareDriver<TranslationAnimationDefinition>(drawer, typeof(TranslationAnimationComponent), typeof(KvmDrawerPart),
            DcGuids.KvmDrawerTranslationDef, KvmDrawerPartDefinition.From, out SurgeryEdit? drawerEdit);
        SurgeryVerdict swapScreen = PrepareDriver<RotationAnimationDefinition>(screen, typeof(RotationAnimationComponent), typeof(KvmScreenPart),
            DcGuids.KvmScreenRotationDef, KvmScreenPartDefinition.From, out SurgeryEdit? screenEdit);

        var verdicts = new List<SurgeryVerdict> { addSequencer, swapDrawer, swapScreen };
        switch (SurgeryRules.Combine(verdicts))
        {
            case SurgeryVerdict.AlreadyDone:
                _state = KvmInjectionState.Applied;
                return;

            case SurgeryVerdict.Ready:
                // Apply logs the injection in one line: "script the KVM: N edit(s): ..." (the sequencer added, the
                // drawer and screen swapped; a repair after a partial reload lists only what it restored).
                if (CompositionSurgery.Apply(new List<SurgeryEdit?> { sequencerEdit, drawerEdit, screenEdit }, What))
                {
                    _state = KvmInjectionState.Applied;
                    _applications++;
                }
                else
                {
                    _state = KvmInjectionState.DataOnly;
                }

                return;

            default:
                Refuse("refused", $"one of the three edits was refused (verdicts {string.Join(", ", verdicts)}), so none was applied");
                return;
        }
    }

    private void Refuse(string key, string why)
    {
        _state = KvmInjectionState.DataOnly;
        DcLog.Once("kvm-inject:" + key, $"KVM: {why}; it keeps the data-only motion (vanilla Translation/RotationAnimation).");
    }

    /// <summary>
    /// Prepares swapping the vanilla part <paramref name="vanillaType"/> for the driver <paramref name="driverType"/>,
    /// with the driver's own definition (Ruling P4-10) built from the slot's data definition, which must be the one the
    /// data ships (<paramref name="expected"/>). A slot already swapped prepares as AlreadyDone.
    /// </summary>
    private static SurgeryVerdict PrepareDriver<TData>(EntityCompositeDefinition composite, Type vanillaType, Type driverType, Guid expected,
        Func<TData, Definition> build, out SurgeryEdit? edit)
        where TData : Definition
    {
        edit = null;
        int index = composite.Types.IndexOf(vanillaType);
        if (index < 0)
            return CompositionSurgery.PrepareSwap(composite, vanillaType, driverType, null, out edit); // done, or refused as missing

        if (!(composite.Definitions[index] is TData data))
            return Refused("def:" + driverType.Name, $"the {vanillaType.Name} slot of '{composite.DebugName}' holds no {typeof(TData).Name}");

        if (data.Guid != expected)
            return Refused("guid:" + driverType.Name, $"the {vanillaType.Name} slot of '{composite.DebugName}' holds {data.Guid}, not the data's {expected} (another mod?)");

        return CompositionSurgery.PrepareSwap(composite, vanillaType, driverType, build(data), out edit);
    }

    private static SurgeryVerdict Refused(string key, string why)
    {
        DcLog.Once("kvm-inject:" + key, $"KVM: {why}.");
        return SurgeryVerdict.Refused;
    }
}
