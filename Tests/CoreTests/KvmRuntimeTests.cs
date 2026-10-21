// Tests of the KVM runtime decisions: Scripts/Client/Core/{KvmSequencerCore, KvmMotionPaths,
// KvmRackSlot}.cs. The game glue (Scripts/Client/Kvm) only reads the world into KvmInputs, so the target rule, the
// door interlock, the scene-entry snap, the path routing and the fault budget are all covered here.
// With --dump, runtime.routing_table writes routing.json, which Tests/test_kvm_runtime.py checks against
// dc/kvm_motion.motion_path_for_slot, and runtime.data_only_path writes data_only_open.csv for the same check.
#nullable enable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using DataCenter.Kvm.Core;

internal static class KvmRuntimeTests
{
    private const float Dt = 1f / 60f;
    private static readonly KvmMotionTuning T = KvmMotionTuning.Default;

    private static void Check(bool ok, string name) => Program.Check(ok, name);

    private static KvmInputs In(bool working, KvmDoorState door = KvmDoorState.None, KvmMotionPath path = KvmMotionPath.Sequenced)
        => new KvmInputs(working, door, path);

    /// <summary>A core past its entry window, settled stowed (the state of a KVM that has been in the world a while).</summary>
    private static KvmSequencerCore Settled(KvmMotionPath path = KvmMotionPath.Sequenced, bool working = false, KvmDoorState door = KvmDoorState.None)
    {
        var c = new KvmSequencerCore(T, path);
        c.EnterScene();
        Run(c, KvmSpawnPolicy.SceneEntryWindow + 0.1f, In(working, door, path));
        return c;
    }

    private static void Run(KvmSequencerCore c, float seconds, KvmInputs inputs)
    {
        for (float t = 0f; t < seconds; t += Dt)
            c.Update(Dt, inputs);
    }

    private static float RunUntilSettled(KvmSequencerCore c, KvmInputs inputs, float max = 5f)
    {
        float t = 0f;
        while (t < max)
        {
            c.Update(Dt, inputs);
            t += Dt;
            if (c.Settled)
                return t;
        }

        return float.PositiveInfinity;
    }

    private static bool IsOut(KvmPose p) => p.Slide == 1f && p.Fold == 1f;

    private static bool IsHome(KvmPose p) => p.Slide == 0f && p.Fold == 0f;

    private static bool Finite(KvmPose p) => !float.IsNaN(p.Slide) && !float.IsNaN(p.Fold) && !float.IsInfinity(p.Slide) && !float.IsInfinity(p.Fold);

    // ------------------------------------------------------------------ the target rule

    /// <summary>Rules 2 to 4, exhaustively: every door state x Working x home.</summary>
    public static void InterlockRules()
    {
        float delay = T.DoorOpenDelay;
        foreach (bool working in new[] { false, true })
        foreach (bool home in new[] { false, true })
        {
            string w = $"working={working} home={home}";
            Check(KvmInterlock.Decide(working, KvmDoorState.Closing, 10f, delay, home) == (home ? KvmTarget.Stowed : KvmTarget.FastStow),
                $"{w}: a closing door fast-stows a KVM that is not home, and keeps a home one stowed");
            Check(KvmInterlock.Decide(working, KvmDoorState.Closed, 10f, delay, home) == (home ? KvmTarget.Stowed : KvmTarget.FastStow),
                $"{w}: a closed door: the same (it closed faster than the client saw it close)");
            Check(KvmInterlock.Decide(working, KvmDoorState.Opening, 10f, delay, home) == KvmTarget.Stowed,
                $"{w}: an opening door is not clear yet: stowed");
            Check(KvmInterlock.Decide(working, KvmDoorState.None, 0f, delay, home) == (working ? KvmTarget.Out : KvmTarget.Stowed),
                $"{w}: no door: Out exactly when Working");
            Check(KvmInterlock.Decide(working, KvmDoorState.Open, delay, delay, home) == (working ? KvmTarget.Out : KvmTarget.Stowed),
                $"{w}: a door open for the delay: Out exactly when Working");
            Check(KvmInterlock.Decide(working, KvmDoorState.Open, delay * 0.99f, delay, home) == KvmTarget.Stowed,
                $"{w}: a door open for less than the delay: still stowed");
        }

        Check(KvmInterlock.Blocks(KvmDoorState.Closing) && KvmInterlock.Blocks(KvmDoorState.Closed)
            && !KvmInterlock.Blocks(KvmDoorState.Open) && !KvmInterlock.Blocks(KvmDoorState.Opening) && !KvmInterlock.Blocks(KvmDoorState.None),
            "only Closing and Closed block");
        Check(KvmInterlock.Decide(true, (KvmDoorState)99, 10f, delay, false) == KvmTarget.Stowed, "an unknown door state never pops the KVM");
    }

    /// <summary>The door opens: the KVM waits DoorOpenDelay after Open, then pops; Opening alone never pops it.</summary>
    public static void DoorOpenDelay()
    {
        KvmSequencerCore c = Settled(working: true, door: KvmDoorState.Closed);
        Check(IsHome(c.Pose) && c.Target == KvmTarget.Stowed, "On behind a closed door: stowed");

        Run(c, 1.0f, In(true, KvmDoorState.Opening));
        Check(IsHome(c.Pose) && c.Target == KvmTarget.Stowed, "the door Opening for 1 s: still stowed");

        float t = 0f;
        while (c.Target != KvmTarget.Out && t < 2f)
        {
            c.Update(Dt, In(true, KvmDoorState.Open));
            t += Dt;
        }

        Check(Math.Abs(t - T.DoorOpenDelay) <= Dt + 1e-4f, $"Out {t:0.000} s after the door reads Open (delay {T.DoorOpenDelay} s)");
        Check(c.Pose.Slide > 0f && c.Pose.Slide < 0.1f, "and it starts sliding from home, not jumping");

        float settled = RunUntilSettled(c, In(true, KvmDoorState.Open));
        Check(IsOut(c.Pose) && settled < 2.6f, $"then it settles out ({settled:0.00} s)");

        Run(c, 0.1f, In(true, KvmDoorState.Opening));
        Check(c.DoorOpenFor == 0f, "the open timer resets once the door stops reading Open");
    }

    /// <summary>A door that starts closing while the KVM is out fast-stows it; once home it is a plain stow.</summary>
    public static void FastStowOnClosing()
    {
        KvmSequencerCore c = Settled(working: true);
        RunUntilSettled(c, In(true));
        Check(IsOut(c.Pose), "On with no door: out");

        c.Update(Dt, In(true, KvmDoorState.Closing));
        Check(c.Target == KvmTarget.FastStow, "the door starts closing: FastStow at once");

        float t = Dt;
        while (!c.AtHome && t < 2f)
        {
            c.Update(Dt, In(true, KvmDoorState.Closing));
            t += Dt;
        }

        Check(c.AtHome && t <= 0.65f, $"home in {t:0.000} s (the fast-stow budget is 0.65 s)");
        c.Update(Dt, In(true, KvmDoorState.Closing));
        Check(c.Target == KvmTarget.Stowed, "home behind a still-closing door: plain Stowed");
        Run(c, 1f, In(true, KvmDoorState.Closed));
        Check(c.AtHome && c.Target == KvmTarget.Stowed && c.Settled, "closed: stowed and settled");

        // The same race on the data-only path (the 42U top slot): the drawer heads home at once, at the vanilla speed.
        KvmSequencerCore d = Settled(KvmMotionPath.DataOnly, working: true);
        RunUntilSettled(d, In(true, KvmDoorState.None, KvmMotionPath.DataOnly));
        Check(IsOut(d.Pose), "data-only path: out");
        d.Update(Dt, In(true, KvmDoorState.Closing, KvmMotionPath.DataOnly));
        Check(d.Target == KvmTarget.FastStow && d.Pose.Slide < 1f && d.Pose.Slide == d.Pose.Fold,
            "data-only path: a closing door moves it home on the first frame, slide and fold together");
    }

    // ------------------------------------------------------------------ scene entry (the load bug, Q1)

    /// <summary>Review Focus 3: a load shows the settled pose at once (out with no door or an open one; stowed behind a closed one).</summary>
    public static void EntryWindowSnaps()
    {
        foreach (KvmMotionPath path in new[] { KvmMotionPath.Sequenced, KvmMotionPath.DataOnly })
        {
            string p = path.ToString();
            var c = new KvmSequencerCore(T, path);
            c.EnterScene();
            c.PartSpawned();
            c.Update(Dt, In(true, KvmDoorState.None, path));
            Check(IsOut(c.Pose) && c.Settled, $"{p}: loaded On, no door: out on the first frame");

            c = new KvmSequencerCore(T, path);
            c.EnterScene();
            c.Update(Dt, In(true, KvmDoorState.Open, path));
            Check(IsOut(c.Pose), $"{p}: loaded On behind an open door: out on the first frame (no DoorOpenDelay wait)");

            c = new KvmSequencerCore(T, path);
            c.EnterScene();
            c.Update(Dt, In(true, KvmDoorState.Closed, path));
            Check(IsHome(c.Pose), $"{p}: loaded On behind a closed door: stowed");

            c = new KvmSequencerCore(T, path);
            c.EnterScene();
            c.Update(Dt, In(false, KvmDoorState.None, path));
            Check(IsHome(c.Pose), $"{p}: loaded Off: stowed");

            // The rack streams in a few frames after the KVM: the late answer still snaps, never animates.
            c = new KvmSequencerCore(T, path);
            c.EnterScene();
            Run(c, 0.2f, In(true, KvmDoorState.None, path));
            c.Update(Dt, In(true, KvmDoorState.Closed, path));
            Check(IsHome(c.Pose), $"{p}: a closed door found 0.2 s into the window: snapped home");
            Run(c, 0.2f, In(true, KvmDoorState.Open, path));
            Check(IsOut(c.Pose), $"{p}: ... and opened inside the window: snapped out");
        }

        // Spawned before the sequencer's own OnAddedToScene (the order of the composition's scene listeners).
        var early = new KvmSequencerCore(T);
        early.PartSpawned();
        early.EnterScene();
        early.Update(Dt, In(true));
        Check(IsOut(early.Pose), "subparts that spawn before EnterScene still snap on the first frame");

        // Paused at load (dt = 0): the window does not run out, the pose still shows at once.
        var paused = new KvmSequencerCore(T);
        paused.EnterScene();
        for (int i = 0; i < 600; i++)
            paused.Update(0f, In(true));
        Check(IsOut(paused.Pose) && paused.InEntryWindow, "paused at load: out, and still inside the window");

        // After the window, a toggle animates.
        KvmSequencerCore later = Settled();
        later.Update(Dt, In(true));
        Check(later.Pose.Slide > 0f && later.Pose.Slide < 0.05f && later.Pose.Fold == 0f, "switched On after the window: it animates, starting with the slide");
    }

    /// <summary>Subparts spawned during play (a weld finished) start stowed and animate; inside the window they
    /// snap.</summary>
    public static void PartSpawnPolicy()
    {
        KvmSequencerCore c = Settled(working: true);
        RunUntilSettled(c, In(true));
        Check(IsOut(c.Pose), "out");

        c.PartSpawned(); // e.g. ground below Functional and welded back: fresh subparts, at rest
        Check(IsHome(c.Pose), "fresh subparts during play: the motion restarts from stowed");
        c.Update(Dt, In(true));
        Check(c.Pose.Slide > 0f && c.Pose.Slide < 0.05f, "and animates out from there");

        KvmSequencerCore home = Settled();
        home.PartSpawned();
        Check(IsHome(home.Pose) && home.Settled, "a spawn while stowed changes nothing");

        var entry = new KvmSequencerCore(T);
        entry.EnterScene();
        entry.Update(Dt, In(true));
        entry.PartSpawned();
        Check(IsOut(entry.Pose), "a spawn inside the window shows the wanted end pose");
    }

    // ------------------------------------------------------------------ faults (rule 1)

    /// <summary>Three faults stop the sequencing; a faulted KVM snaps to the wanted end pose every frame.</summary>
    public static void FaultBudget()
    {
        KvmSequencerCore c = Settled();
        Check(!c.ReportFault() && !c.ReportFault() && !c.Faulted, "two faults: still sequencing");
        Check(c.ReportFault() && c.Faulted, "the third fault: Faulted (reported once)");
        Check(!c.ReportFault() && c.Faults == KvmSequencerCore.MaxFaults, "further faults are not reported again or counted");

        c.Update(Dt, In(true));
        Check(IsOut(c.Pose), "faulted, Working: out at once (the data-only end pose)");
        c.Update(Dt, In(false));
        Check(IsHome(c.Pose), "faulted, Off: stowed at once");
        c.Update(Dt, In(true, KvmDoorState.Closed));
        Check(IsHome(c.Pose), "faulted behind a closed door: stowed (the door is still honoured while it can be read)");
        c.Update(Dt, KvmInputs.DataOnly(true));
        Check(IsOut(c.Pose), "faulted with the world unreadable (the data-only fallback inputs): out while Working");
        c.PartSpawned();
        Check(IsOut(c.Pose), "faulted: a spawn shows the end pose too");
    }

    // ------------------------------------------------------------------ the data-only path

    /// <summary>The data-only motion is the data's own: slide = fold, linear, a stroke in DataOnlyStroke s, reversing on the spot.</summary>
    public static void DataOnlyPath()
    {
        var m = new KvmLinearMotion(T);
        Check(IsHome(m.Pose) && m.Settled && m.Target == KvmTarget.Stowed, "starts stowed and settled");

        var csv = new StringBuilder("t,slide,fold,target\n");
        const float hz = 240f;
        double t = 0;
        bool linear = true;
        csv.Append("0.000000,0.000000,0.000000,Out\n");
        while (!m.Settled || m.Target != KvmTarget.Out)
        {
            KvmPose p = m.Step(1f / hz, KvmTarget.Out);
            t += 1.0 / hz;
            linear &= p.Slide == p.Fold && Math.Abs(p.Slide - Math.Min(1.0, t / T.DataOnlyStroke)) < 1e-4;
            csv.Append(string.Format(CultureInfo.InvariantCulture, "{0:0.000000},{1:0.000000},{2:0.000000},Out\n", t, p.Slide, p.Fold));
            if (t > 3)
                break;
        }

        Program.Dump("data_only_open.csv", csv.ToString());
        Check(linear, "slide = fold = t / stroke at every 240 Hz frame");
        Check(Math.Abs(t - T.DataOnlyStroke) < 1.0 / hz + 1e-6, $"a full stroke in {t:0.000} s (DataOnlyStroke {T.DataOnlyStroke} s)");

        m.Step(0.5f, KvmTarget.Stowed);
        KvmPose mid = m.Pose;
        m.Step(Dt, KvmTarget.Out);
        Check(Math.Abs(m.Pose.Slide - (mid.Slide + Dt / T.DataOnlyStroke)) < 1e-5, "a reversal turns on the spot (vanilla's play-back)");

        KvmPose before = m.Pose;
        m.Step(0f, KvmTarget.Stowed);
        m.Step(float.NaN, KvmTarget.Stowed);
        m.Step(-1f, KvmTarget.Stowed);
        m.Step(float.PositiveInfinity, KvmTarget.Stowed);
        Check(m.Pose.Slide == before.Slide && m.Target == KvmTarget.Out, "dt 0, NaN, negative, infinite: nothing changes, not even the target");

        m.Snap(false);
        m.Step(10f, KvmTarget.Out);
        Check(Math.Abs(m.Pose.Slide - T.MaxDt / T.DataOnlyStroke) < 1e-5, "a 10 s hitch moves only MaxDt worth");

        m.Step(Dt, (KvmTarget)42);
        Check(m.Target == KvmTarget.Stowed, "an out-of-range target is a stow");

        m.Snap(true);
        m.Step(Dt, KvmTarget.FastStow);
        Check(Math.Abs(m.Pose.Slide - (1f - Dt / T.DataOnlyStroke)) < 1e-5, "a fast stow runs at the same, vanilla, speed");
    }

    /// <summary>The path changes without a jump: at once inside the window, otherwise only once the motion is settled.</summary>
    public static void PathSwitch()
    {
        KvmSequencerCore c = Settled();
        for (int i = 0; i < 30; i++)
            c.Update(Dt, In(true));
        KvmPose moving = c.Pose;
        Check(!c.Settled && moving.Slide > 0f, "moving out on the sequenced path");

        c.Update(Dt, In(true, KvmDoorState.None, KvmMotionPath.DataOnly));
        Check(c.Path == KvmMotionPath.Sequenced && c.Pose.Slide >= moving.Slide, "a path change mid-move waits (no jump)");

        RunUntilSettled(c, In(true, KvmDoorState.None, KvmMotionPath.DataOnly));
        c.Update(Dt, In(true, KvmDoorState.None, KvmMotionPath.DataOnly));
        Check(c.Path == KvmMotionPath.DataOnly && IsOut(c.Pose), "settled out: the data-only path takes over at the same pose");

        c.Update(Dt, In(false, KvmDoorState.None, KvmMotionPath.DataOnly));
        Check(c.Pose.Slide == c.Pose.Fold && c.Pose.Slide < 1f, "and stows on it: slide and fold together");

        var e = new KvmSequencerCore(T, KvmMotionPath.Sequenced);
        e.EnterScene();
        e.Update(Dt, In(true, KvmDoorState.None, KvmMotionPath.DataOnly));
        Check(e.Path == KvmMotionPath.DataOnly && IsOut(e.Pose), "inside the window the path switches at once (the pose snaps anyway)");

        var bad = new KvmSequencerCore(T, (KvmMotionPath)7);
        Check(bad.Path == KvmMotionPath.Sequenced, "an out-of-range path is the sequenced one");
    }

    /// <summary>
    /// The sequencer's frame runs inside a game job, so it must not allocate: not on a target change, not on a door
    /// flicker, and not on a path change (both motions are built up front; a switch snaps the one it switches to).
    /// </summary>
    public static void UpdateAllocatesNothing()
    {
        var c = new KvmSequencerCore(T);
        c.Update(Dt, In(true)); // warm up (JIT)
        var doors = new[] { KvmDoorState.None, KvmDoorState.Open, KvmDoorState.Closing, KvmDoorState.Closed, KvmDoorState.Opening };
        int switches = 0;
        KvmMotionPath last = c.Path;
        float sink = 0f;
        long before = GC.GetAllocatedBytesForCurrentThread();
        for (int i = 0; i < 20000; i++)
        {
            bool working = (i / 400) % 2 == 0;
            KvmDoorState door = doors[(i / 170) % doors.Length];
            KvmMotionPath path = (i / 900) % 2 == 0 ? KvmMotionPath.Sequenced : KvmMotionPath.DataOnly;
            KvmPose p = c.Update(Dt, new KvmInputs(working, door, path));
            if (i % 2500 == 0)
                c.PartSpawned();
            switches += c.Path != last ? 1 : 0;
            last = c.Path;
            sink += p.Slide + p.Fold;
        }

        long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
        Check(switches >= 4, $"the run switches paths ({switches} switches)");
        Check(allocated == 0 && !float.IsNaN(sink), $"20000 frames with flicker and path switches allocate nothing ({allocated} bytes)");
    }

    /// <summary>Review Focus 5 for the core: no NaN and no motion past the stops under any dt and any input flicker.</summary>
    public static void Robust()
    {
        var rng = new Random(8);
        var doors = new[] { KvmDoorState.None, KvmDoorState.Closing, KvmDoorState.Opening, KvmDoorState.Closed, KvmDoorState.Open };
        bool ok = true;
        foreach (KvmMotionPath path in new[] { KvmMotionPath.Sequenced, KvmMotionPath.DataOnly })
        {
            var c = new KvmSequencerCore(T, path);
            c.EnterScene();
            for (int i = 0; i < 20000; i++)
            {
                float dt = (rng.Next(20)) switch
                {
                    0 => 0f,
                    1 => float.NaN,
                    2 => -0.5f,
                    3 => 5f,
                    4 => float.PositiveInfinity,
                    _ => (float)(rng.NextDouble() * 0.05),
                };
                var inputs = new KvmInputs(rng.Next(2) == 0, doors[rng.Next(doors.Length)],
                    rng.Next(50) == 0 ? (KvmMotionPath)(1 - (int)path) : path);
                KvmPose p = c.Update(dt, inputs);
                if (rng.Next(500) == 0)
                    c.PartSpawned();
                ok &= Finite(p) && p.Slide >= 0f && p.Slide <= 1f && p.Fold >= 0f && p.Fold <= 1.03f;
            }
        }

        Check(ok, "20000 random frames per path (bad dts, flickering doors and Working, path flips, spawns): finite and within the stops");
    }

    // ------------------------------------------------------------------ the rack slot rule

    /// <summary>
    /// Every slot of both rack kinds, in all 24 rack orientations: the KVM's highest slot from its cell bounds, the
    /// plinth and the tray band refused, a KVM outside the rack or a rack of the wrong height refused.
    /// </summary>
    public static void RackSlots()
    {
        var axes = new[] { new Int3(1, 0, 0), new Int3(-1, 0, 0), new Int3(0, 1, 0), new Int3(0, -1, 0), new Int3(0, 0, 1), new Int3(0, 0, -1) };
        int orientations = 0;
        bool all = true;
        foreach (Int3 up in axes)
        foreach (Int3 fwd in axes)
        {
            if (Dot(up, fwd) != 0)
                continue;
            orientations++;
            Int3 right = Cross(fwd, up), back = Neg(fwd);
            Int3 origin = new Int3(7, -3, 11);
            foreach (KvmRackKind kind in new[] { KvmRackKind.Full, KvmRackKind.Half })
            {
                int h = KvmRackSlot.Cells(kind);
                (Int3 rMin, Int3 rMax) = Box(origin, right, up, back, 0, 3, 0, h - 1, 0, 4);
                for (int cell = 0; cell < h; cell++)
                {
                    (Int3 kMin, Int3 kMax) = Box(origin, right, up, back, 1, 2, cell, cell, 1, 3); // 2x1x3, centred
                    int slot = KvmRackSlot.SlotOf(kind, rMin, rMax, up, kMin, kMax);
                    int expect = cell >= 1 && cell <= KvmRackSlot.SlotCount(kind) ? cell : 0;
                    all &= slot == expect;
                    // ... and with the bounds handed over in the other order
                    all &= KvmRackSlot.SlotOf(kind, rMax, rMin, up, kMax, kMin) == expect;
                }
            }
        }

        Check(orientations == 24, "24 rack orientations");
        Check(all, "every cell of both rack kinds in every orientation: its slot (1..n above the plinth), 0 on the plinth and the tray band");

        Int3 u = new Int3(0, 1, 0);
        (Int3 a, Int3 b) = (new Int3(0, 0, 0), new Int3(3, 9, 4));
        Check(KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, u, new Int3(1, 8, 1), new Int3(2, 8, 3)) == 8, "a 42U top slot is slot 8");
        Check(KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, u, new Int3(1, 7, 1), new Int3(2, 8, 3)) == 8, "a 12U server in slots 7-8 reports its top slot");
        Check(KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, u, new Int3(1, 8, 4), new Int3(2, 8, 6)) == 0, "a KVM sticking out of the rack's box: no slot");
        Check(KvmRackSlot.SlotOf(KvmRackKind.Half, a, b, u, new Int3(1, 4, 1), new Int3(2, 4, 3)) == 0, "a 10-cell rack reported as a half rack: no slot");
        Check(KvmRackSlot.SlotOf(KvmRackKind.None, a, b, u, new Int3(1, 4, 1), new Int3(2, 4, 3)) == 0, "no rack: no slot");
        Check(KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, new Int3(0, 2, 0), new Int3(1, 4, 1), new Int3(2, 4, 3)) == 0
            && KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, new Int3(0, 0, 0), new Int3(1, 4, 1), new Int3(2, 4, 3)) == 0
            && KvmRackSlot.SlotOf(KvmRackKind.Full, a, b, new Int3(1, 1, 0), new Int3(1, 4, 1), new Int3(2, 4, 3)) == 0,
            "an up that is not a unit axis: no slot");

        Check(KvmRackSlot.PathFor(KvmRackKind.Full, 8) == KvmMotionPath.DataOnly, "42U top slot: data-only");
        bool rest = true;
        for (int s = 0; s <= 8; s++)
        {
            rest &= s == 8 || KvmRackSlot.PathFor(KvmRackKind.Full, s) == KvmMotionPath.Sequenced;
            rest &= KvmRackSlot.PathFor(KvmRackKind.Half, s) == KvmMotionPath.Sequenced;
            rest &= KvmRackSlot.PathFor(KvmRackKind.None, s) == KvmMotionPath.Sequenced;
        }

        Check(rest, "every other slot, the 24U top slot included, and no rack: sequenced");
    }

    /// <summary>
    /// The door guards only the face side it has leaves on. Front- and rear-facing KVMs in SplitFront
    /// (front leaves) and SplitFrontRear (both) racks, in all 24 rack orientations, end to end through the interlock:
    /// the door the link hands the core is the rack's when it guards the face, None otherwise.
    /// </summary>
    public static void DoorFaceSide()
    {
        var axes = new[] { new Int3(1, 0, 0), new Int3(-1, 0, 0), new Int3(0, 1, 0), new Int3(0, -1, 0), new Int3(0, 0, 1), new Int3(0, 0, -1) };
        const KvmDoorSides splitFront = KvmDoorSides.Front, splitFrontRear = KvmDoorSides.Front | KvmDoorSides.Rear;
        bool faces = true, guards = true, endToEnd = true;
        int orientations = 0;
        foreach (Int3 up in axes)
        foreach (Int3 fwd in axes)
        {
            if (Dot(up, fwd) != 0)
                continue;
            orientations++;
            Int3 back = Neg(fwd), side = Cross(fwd, up);
            faces &= KvmRackSlot.FaceSide(fwd, fwd) == 1 && KvmRackSlot.FaceSide(back, fwd) == -1
                && KvmRackSlot.FaceSide(side, fwd) == 0 && KvmRackSlot.FaceSide(up, fwd) == 0;

            foreach ((KvmDoorSides sides, string rack) in new[] { (splitFront, "SplitFront"), (splitFrontRear, "SplitFrontRear") })
            foreach (Int3 kvm in new[] { fwd, back })
            {
                int face = KvmRackSlot.FaceSide(kvm, fwd);
                bool guarded = KvmRackSlot.DoorGuardsFace(sides, face);
                bool leavesOnFace = kvm.Equals(fwd) || sides == splitFrontRear; // the data: front leaves, plus rear ones
                guards &= guarded == leavesOnFace;

                // the link's answer behind closed doors, through the core: stowed when guarded, out when free
                KvmSequencerCore c = Settled();
                c.Update(Dt, In(true, guarded ? KvmDoorState.Closed : KvmDoorState.None));
                endToEnd &= c.Target == (leavesOnFace ? KvmTarget.Stowed : KvmTarget.Out);
            }
        }

        Check(orientations == 24, "24 rack orientations");
        Check(faces, "the face side: +1 with the rack's forward, -1 against it, 0 sideways");
        Check(guards, "SplitFront guards only a front-facing KVM; SplitFrontRear guards both");
        Check(endToEnd, "behind closed doors: front-facing stays stowed in both racks; rear-facing deploys in SplitFront, stays stowed in SplitFrontRear");
        Check(!KvmRackSlot.DoorGuardsFace(KvmDoorSides.None, 1) && !KvmRackSlot.DoorGuardsFace(KvmDoorSides.None, -1),
            "an open rack (no leaves) guards nothing");
        Check(KvmRackSlot.DoorGuardsFace(splitFront, 0) && KvmRackSlot.DoorGuardsFace(splitFrontRear, 0),
            "an unknown face side (sideways) is guarded by any door: never pop on doubt");
        Check(KvmRackSlot.FaceSide(new Int3(0, 0, 0), new Int3(0, 0, 1)) == 0 && KvmRackSlot.FaceSide(new Int3(0, 0, 2), new Int3(0, 0, 2)) == 0,
            "a forward that is not a unit axis: face side unknown");
    }

    /// <summary>The rule as a table, for Tests/test_kvm_runtime.py to hold against dc/kvm_motion.motion_path_for_slot.</summary>
    public static void RoutingTable()
    {
        var json = new StringBuilder("{\n");
        KvmRackKind[] kinds = { KvmRackKind.Full, KvmRackKind.Half };
        for (int k = 0; k < kinds.Length; k++)
        {
            KvmRackKind kind = kinds[k];
            json.Append($"  \"{kind}\": {{\"cells\": {KvmRackSlot.Cells(kind)}, \"slots\": {{");
            for (int s = 1; s <= KvmRackSlot.SlotCount(kind); s++)
                json.Append($"{(s > 1 ? ", " : "")}\"{s}\": \"{(KvmRackSlot.PathFor(kind, s) == KvmMotionPath.DataOnly ? "data_only" : "sequenced")}\"");
            json.Append(k + 1 < kinds.Length ? "}},\n" : "}}\n");
        }

        json.Append("}\n");
        Program.Dump("routing.json", json.ToString());
        Check(KvmRackSlot.SlotCount(KvmRackKind.Full) == KvmRackSlot.Cells(KvmRackKind.Full) - 2
            && KvmRackSlot.SlotCount(KvmRackKind.Half) == KvmRackSlot.Cells(KvmRackKind.Half) - 1,
            "full rack: plinth + slots + tray band; half rack: plinth + slots");
    }

    private static int Dot(Int3 a, Int3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;

    private static Int3 Cross(Int3 a, Int3 b) => new Int3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);

    private static Int3 Neg(Int3 a) => new Int3(-a.X, -a.Y, -a.Z);

    /// <summary>The grid bounds of the local cell box [x0..x1] x [y0..y1] x [z0..z1] under the axes (right, up, back).</summary>
    private static (Int3 Min, Int3 Max) Box(Int3 o, Int3 r, Int3 u, Int3 b, int x0, int x1, int y0, int y1, int z0, int z1)
    {
        var pts = new List<Int3>();
        foreach (int x in new[] { x0, x1 })
        foreach (int y in new[] { y0, y1 })
        foreach (int z in new[] { z0, z1 })
            pts.Add(new Int3(o.X + x * r.X + y * u.X + z * b.X, o.Y + x * r.Y + y * u.Y + z * b.Y, o.Z + x * r.Z + y * u.Z + z * b.Z));

        Int3 min = pts[0], max = pts[0];
        foreach (Int3 p in pts)
        {
            min = new Int3(Math.Min(min.X, p.X), Math.Min(min.Y, p.Y), Math.Min(min.Z, p.Z));
            max = new Int3(Math.Max(max.X, p.X), Math.Max(max.Y, p.Y), Math.Max(max.Z, p.Z));
        }

        return (min, max);
    }
}
