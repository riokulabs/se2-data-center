// Tests of the KVM motion core: Scripts/Client/Core/{KvmMotion, KvmMotionTuning, KvmFrontCell, KvmSpawnPolicy}.cs
// 60 Hz unless a test says otherwise. With --dump, kvm.trajectories writes the 240 Hz CSVs that the Python geometry
// checks (Tests/test_kvm_sequence.py) and the motion charts read.
#nullable enable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using DataCenter.Kvm.Core;

internal static class KvmMotionTests
{
    private static readonly KvmMotionTuning T = KvmMotionTuning.Default;

    // The settle budgets (feel won over the original 1.40 / 1.20 / 0.60 s targets). The feel retune slowed
    // the drawer to a 0.85 m/s peak and gave the lid weight, so the open and close take longer; the fast stow still
    // has to beat the closing rack door (Tests/test_kvm_sequence.py measures that race in geometry).
    private const double OpenBudget = 2.50, CloseBudget = 1.90, FastStowBudget = 0.65;

    /// <summary>Long enough for any uninterrupted move to settle, with a margin.</summary>
    private const double Long = 3.5;

    private static void Check(bool ok, string name) => Program.Check(ok, name);

    // ------------------------------------------------------------------ harness

    /// <summary>One frame of a run: the pose and rate after the step that ended at <see cref="Time"/>.</summary>
    private struct Sample
    {
        public double Time;
        public double Dt;
        public float Slide, Fold, SlideRate, FoldRate;
        public KvmTarget Target;
        public bool Settled;
    }

    /// <summary>
    /// Runs <paramref name="m"/> frame by frame: frame k lasts <paramref name="dtOf"/>(k) and steps toward
    /// <paramref name="targetAt"/>(its start time). Sample 0 is the starting state. Stops after
    /// <paramref name="duration"/> seconds, or <paramref name="tail"/> seconds after it settles past <paramref name="settleAfter"/>.
    /// </summary>
    private static List<Sample> Run(KvmMotion m, Func<int, double> dtOf, Func<double, KvmTarget> targetAt, double duration,
        double tail = double.NaN, double settleAfter = 0.0)
    {
        var samples = new List<Sample> { Snapshot(m, 0.0, 0.0) };
        double t = 0.0, settledAt = double.NaN;
        for (int k = 0; t < duration - 1e-9; k++)
        {
            double dt = dtOf(k);
            m.Step((float)dt, targetAt(t));
            t += dt;
            samples.Add(Snapshot(m, t, dt));
            if (!double.IsNaN(tail))
            {
                if (double.IsNaN(settledAt) && m.Settled && t >= settleAfter)
                    settledAt = t;
                if (!double.IsNaN(settledAt) && t >= settledAt + tail - 1e-9)
                    break;
            }
        }

        return samples;
    }

    private static Func<int, double> Hz(double hz) => _ => 1.0 / hz;

    private static Func<double, KvmTarget> Always(KvmTarget target) => _ => target;

    private static Func<double, KvmTarget> Flip(KvmTarget first, double at, KvmTarget then) => t => t < at - 1e-9 ? first : then;

    private static Sample Snapshot(KvmMotion m, double t, double dt) => new Sample
    {
        Time = t,
        Dt = dt,
        Slide = m.Pose.Slide,
        Fold = m.Pose.Fold,
        SlideRate = m.Velocity.Slide,
        FoldRate = m.Velocity.Fold,
        Target = m.Target,
        Settled = m.Settled,
    };

    private static KvmMotion Stowed() => new KvmMotion(T);

    private static KvmMotion Out()
    {
        var m = new KvmMotion(T);
        m.Snap(true);
        return m;
    }

    /// <summary>The first sample time at which the motion reads Settled, or +inf.</summary>
    private static double SettleTime(List<Sample> run)
    {
        for (int i = 1; i < run.Count; i++)
        {
            if (run[i].Settled)
                return run[i].Time;
        }

        return double.PositiveInfinity;
    }

    /// <summary>A seeded xorshift: the same flips on every machine and runtime.</summary>
    private sealed class Rng
    {
        private ulong _s;

        public Rng(ulong seed) => _s = seed == 0 ? 0x9E3779B97F4A7C15UL : seed;

        public double Next()
        {
            _s ^= _s << 13;
            _s ^= _s >> 7;
            _s ^= _s << 17;
            return (_s >> 11) * (1.0 / 9007199254740992.0);
        }

        public double Range(double min, double max) => min + (max - min) * Next();
    }

    /// <summary>A schedule of random targets: <paramref name="flips"/> holds of 0.02..0.9 s each, Out and Stowed alternating, with some FastStows.</summary>
    private static List<(double At, KvmTarget Target)> RandomSchedule(ulong seed, int flips)
    {
        var rng = new Rng(seed);
        var schedule = new List<(double, KvmTarget)>();
        double t = 0.0;
        KvmTarget current = KvmTarget.Stowed;
        for (int i = 0; i < flips; i++)
        {
            KvmTarget next = current == KvmTarget.Out
                ? (rng.Next() < 0.3 ? KvmTarget.FastStow : KvmTarget.Stowed)
                : KvmTarget.Out;
            schedule.Add((t, next));
            current = next;
            t += rng.Range(0.02, 0.9);
        }

        schedule.Add((t, current));
        return schedule;
    }

    private static Func<double, KvmTarget> Scheduled(List<(double At, KvmTarget Target)> schedule) => t =>
    {
        KvmTarget target = KvmTarget.Stowed;
        foreach ((double at, KvmTarget tg) in schedule)
        {
            if (at > t + 1e-9)
                break;
            target = tg;
        }

        return target;
    };

    // ------------------------------------------------------------------ sequencing

    /// <summary>From Stowed toward Out: the lid stays flat until the drawer passes the gate, and for the beat after.</summary>
    public static void OpenSequenceOrder()
    {
        List<Sample> run = Run(Stowed(), Hz(60), Always(KvmTarget.Out), Long);

        double gateAt = double.NaN; // the gate crossing, interpolated between frames
        bool flatBeforeGate = true;
        for (int i = 1; i < run.Count; i++)
        {
            if (run[i].Slide < T.FoldGate)
            {
                flatBeforeGate &= run[i].Fold == 0f;
                continue;
            }

            if (double.IsNaN(gateAt))
            {
                Sample a = run[i - 1], b = run[i];
                gateAt = a.Time + (b.Time - a.Time) * (T.FoldGate - a.Slide) / (b.Slide - a.Slide);
            }
        }

        Check(flatBeforeGate, "Fold == 0 while Slide < FoldGate");
        Check(!double.IsNaN(gateAt) && gateAt > 0.6 && gateAt < 0.9, $"the drawer passes the gate in 0.6..0.9 s (at {gateAt:0.000} s)");

        bool flatThroughBeat = true;
        double liftedAt = double.PositiveInfinity;
        foreach (Sample s in run)
        {
            if (s.Time <= gateAt + T.OpenBeat - 0.002)
                flatThroughBeat &= s.Fold == 0f;
            if (s.Fold > 0f && s.Time < liftedAt)
                liftedAt = s.Time;
        }

        Check(flatThroughBeat, "Fold == 0 for OpenBeat after the gate");
        Check(liftedAt <= gateAt + T.OpenBeat + 2.0 / 60.0,
            $"the lid lifts within two frames of the beat's end (gate {gateAt:0.000} s, lift {liftedAt:0.000} s): no dead air");

        bool slideDuringBeat = false;
        foreach (Sample s in run)
        {
            if (s.Time > gateAt && s.Time < gateAt + T.OpenBeat && s.SlideRate > 0f)
                slideDuringBeat = true;
        }

        Check(slideDuringBeat, "the drawer is still easing home during the beat (the beat overlaps the slide's tail)");
    }

    /// <summary>Settled at Out, exactly at (1, 1), by OpenBudget.</summary>
    public static void OpenSettlesWithin()
    {
        var m = Stowed();
        List<Sample> run = Run(m, Hz(60), Always(KvmTarget.Out), Long);
        double at = SettleTime(run);
        Check(at <= OpenBudget, $"settled at Out by {OpenBudget:0.00} s (at {at:0.000} s)");
        foreach (double hz in new[] { 30.0, 144.0, 240.0 })
        {
            double atHz = SettleTime(Run(Stowed(), Hz(hz), Always(KvmTarget.Out), Long));
            Check(atHz <= OpenBudget + 1e-9, $"settled at Out by {OpenBudget:0.00} s at {hz} Hz too (at {atHz:0.000} s)");
        }

        Check(m.Settled && m.Target == KvmTarget.Out && m.Pose.Slide == 1f && m.Pose.Fold == 1f, $"rests exactly at (1, 1): {m.Pose}");
        Check(m.Velocity.Slide == 0f && m.Velocity.Fold == 0f, "at rest");
    }

    /// <summary>From Out toward Stowed: the drawer stays out until the lid is within the retract gate, then moves at once.</summary>
    public static void CloseSequenceOrder()
    {
        List<Sample> run = Run(Out(), Hz(60), Always(KvmTarget.Stowed), Long);

        bool heldOut = true;
        double gateAt = double.NaN, movedAt = double.NaN;
        foreach (Sample s in run)
        {
            if (s.Fold > T.RetractGate)
                heldOut &= s.Slide == 1f;
            else if (double.IsNaN(gateAt))
                gateAt = s.Time;
            if (s.Slide < 1f && double.IsNaN(movedAt))
                movedAt = s.Time;
        }

        Check(heldOut, "Slide == 1 while Fold > RetractGate");
        Check(!double.IsNaN(movedAt) && movedAt <= gateAt + 1.0 / 60.0 + 1e-9,
            $"the drawer starts home within a frame of the gate (gate {gateAt:0.000} s, moved {movedAt:0.000} s)");
    }

    /// <summary>Settled at Stowed, exactly at (0, 0), by CloseBudget.</summary>
    public static void CloseSettlesWithin()
    {
        var m = Out();
        List<Sample> run = Run(m, Hz(60), Always(KvmTarget.Stowed), Long);
        double at = SettleTime(run);
        Check(at <= CloseBudget, $"settled at Stowed by {CloseBudget:0.00} s (at {at:0.000} s)");
        foreach (double hz in new[] { 30.0, 144.0, 240.0 })
        {
            double atHz = SettleTime(Run(Out(), Hz(hz), Always(KvmTarget.Stowed), Long));
            Check(atHz <= CloseBudget + 1e-9, $"settled at Stowed by {CloseBudget:0.00} s at {hz} Hz too (at {atHz:0.000} s)");
        }

        Check(m.Settled && m.Pose.Slide == 0f && m.Pose.Fold == 0f, $"rests exactly at (0, 0): {m.Pose}");
    }

    /// <summary>From Out, a fast stow (the door is closing) settles by FastStowBudget; the drawer still waits for the 8 degree gate.</summary>
    public static void FastStowSettlesWithin()
    {
        var m = Out();
        List<Sample> run = Run(m, Hz(60), Always(KvmTarget.FastStow), 1.0);
        double at = SettleTime(run);
        Check(at <= FastStowBudget, $"fast stow settled by {FastStowBudget:0.00} s (at {at:0.000} s)");
        Check(m.Settled && m.Target == KvmTarget.FastStow && m.Pose.Slide == 0f && m.Pose.Fold == 0f,
            $"rests at (0, 0) and keeps its FastStow target: {m.Pose} {m.Target}");

        bool heldOut = true;
        foreach (Sample s in run)
        {
            if (s.Fold > T.RetractGateFast)
                heldOut &= s.Slide == 1f;
        }

        Check(heldOut, "Slide == 1 while Fold > RetractGateFast");

        foreach (double hz in new[] { 30.0, 144.0, 240.0 })
        {
            double atHz = SettleTime(Run(Out(), Hz(hz), Always(KvmTarget.FastStow), 1.0));
            Check(atHz <= FastStowBudget + 1e-9, $"fast stow settled by {FastStowBudget:0.00} s at {hz} Hz too (at {atHz:0.000} s)");
        }

        double normal = SettleTime(Run(Out(), Hz(60), Always(KvmTarget.Stowed), Long));
        Check(at < 0.6 * normal, $"a fast stow is clearly faster than a stow ({at:0.000} s vs {normal:0.000} s)");
    }

    // ------------------------------------------------------------------ shape

    /// <summary>The lid's detent bounce is subtle: 0.5..3 % over on open; it never passes flat on close.</summary>
    public static void FoldBounceSubtle()
    {
        float max = 0f;
        foreach (Sample s in Run(Stowed(), Hz(60), Always(KvmTarget.Out), Long))
            max = Math.Max(max, s.Fold);
        Check(max >= 1.005f && max <= 1.03f, $"1.005 <= max Fold <= 1.03 on open (max {max:0.0000})");

        foreach (KvmTarget stow in new[] { KvmTarget.Stowed, KvmTarget.FastStow })
        {
            float min = float.MaxValue;
            foreach (Sample s in Run(Out(), Hz(60), Always(stow), Long))
                min = Math.Min(min, s.Fold);
            Check(min >= 0f, $"{stow}: Fold never below 0 (min {min})");
        }
    }

    /// <summary>The end poses are exact and at rest, and the motion stays there.</summary>
    public static void Endpoints()
    {
        var m = Stowed();
        Check(m.Settled && m.Target == KvmTarget.Stowed && m.Pose.Slide == 0f && m.Pose.Fold == 0f, "a new motion rests stowed");

        Run(m, Hz(60), Always(KvmTarget.Out), Long);
        KvmPose atOut = m.Pose;
        Run(m, Hz(60), Always(KvmTarget.Out), 1.0);
        Check(atOut.Slide == 1f && atOut.Fold == 1f && m.Pose.Slide == 1f && m.Pose.Fold == 1f, "Out ends at exactly (1, 1) and stays");

        Run(m, Hz(60), Always(KvmTarget.Stowed), Long);
        Check(m.Pose.Slide == 0f && m.Pose.Fold == 0f && m.Velocity.Slide == 0f && m.Velocity.Fold == 0f,
            "Stowed ends at exactly (0, 0), at rest");
    }

    /// <summary>
    /// Uninterrupted moves are monotone: the drawer never backs up; the lid rises to one peak, then settles within
    /// the bounce; on a stow both only ever go home.
    /// </summary>
    public static void Monotonicity()
    {
        foreach (double hz in new[] { 60.0, 240.0 })
        {
            List<Sample> open = Run(Stowed(), Hz(hz), Always(KvmTarget.Out), Long);
            bool slideUp = true, foldUpToPeak = true, foldAfterPeak = true;
            int peak = 0;
            for (int i = 1; i < open.Count; i++)
            {
                if (open[i].Fold > open[peak].Fold)
                    peak = i;
            }

            for (int i = 1; i < open.Count; i++)
            {
                slideUp &= open[i].Slide >= open[i - 1].Slide;
                if (i <= peak)
                    foldUpToPeak &= open[i].Fold >= open[i - 1].Fold;
                else
                    foldAfterPeak &= open[i].Fold >= 1f - T.SnapEpsilon && open[i].Fold <= open[peak].Fold;
            }

            Check(slideUp, $"{hz} Hz open: Slide never decreases");
            Check(foldUpToPeak, $"{hz} Hz open: Fold rises to its peak without a wobble");
            Check(foldAfterPeak, $"{hz} Hz open: after the peak, Fold stays in [1 - eps, peak] (one bounce, no ringing)");

            foreach (KvmTarget stow in new[] { KvmTarget.Stowed, KvmTarget.FastStow })
            {
                List<Sample> close = Run(Out(), Hz(hz), Always(stow), Long);
                bool down = true;
                for (int i = 1; i < close.Count; i++)
                    down &= close[i].Slide <= close[i - 1].Slide && close[i].Fold <= close[i - 1].Fold;
                Check(down, $"{hz} Hz {stow}: Slide and Fold never increase");
            }
        }
    }

    /// <summary>The drawer and the lid land on their stops softly (inelastic, a few cm/s), never slam.</summary>
    public static void StopLandingsSoft()
    {
        double worstSlide = 0.0, worstFold = 0.0;
        foreach ((KvmMotion m, KvmTarget target) in new[]
                 {
                     (Stowed(), KvmTarget.Out), (Out(), KvmTarget.Stowed), (Out(), KvmTarget.FastStow),
                 })
        {
            List<Sample> run = Run(m, Hz(1000), Always(target), Long);
            for (int i = 1; i < run.Count; i++)
            {
                Sample a = run[i - 1], b = run[i];
                bool slideLands = (b.Slide == 1f && a.Slide < 1f) || (b.Slide == 0f && a.Slide > 0f);
                if (slideLands)
                    worstSlide = Math.Max(worstSlide, Math.Abs(a.SlideRate) * (target == KvmTarget.FastStow ? 0.5 : 1.0));
                if (b.Fold == 0f && a.Fold > 0f)
                    worstFold = Math.Max(worstFold, Math.Abs(a.FoldRate) * (target == KvmTarget.FastStow ? 0.5 : 1.0));
            }
        }

        // Normalised: 0.25/s is 11 cm/s on the drawer and 25 degrees/s on the lid (a fast stow may land twice as hard).
        Check(worstSlide > 0.0 && worstSlide <= 0.25, $"the drawer lands at <= 0.25/s (normal; fast stow <= 0.5/s): {worstSlide:0.000}");
        Check(worstFold > 0.0 && worstFold <= 0.25, $"the lid lands at <= 0.25/s (normal; fast stow <= 0.5/s): {worstFold:0.000}");
    }

    /// <summary>The drawer never passes its rails, at any frame rate, in any sequence.</summary>
    public static void SlideHardStops()
    {
        List<(double, KvmTarget)> schedule = RandomSchedule(7, 120);
        foreach (double hz in new[] { 30.0, 60.0, 144.0, 240.0 })
        {
            bool inside = true;
            float lo = float.MaxValue, hi = float.MinValue, foldLo = float.MaxValue;
            void Scan(List<Sample> run)
            {
                foreach (Sample s in run)
                {
                    inside &= s.Slide >= 0f && s.Slide <= 1f && s.Fold >= 0f;
                    lo = Math.Min(lo, s.Slide);
                    hi = Math.Max(hi, s.Slide);
                    foldLo = Math.Min(foldLo, s.Fold);
                }
            }

            Scan(Run(Stowed(), Hz(hz), Always(KvmTarget.Out), Long));
            Scan(Run(Out(), Hz(hz), Always(KvmTarget.Stowed), Long));
            Scan(Run(Out(), Hz(hz), Always(KvmTarget.FastStow), 1.0));
            Scan(Run(Stowed(), Hz(hz), Scheduled(schedule), schedule[schedule.Count - 1].Item1 + 1.5));
            Check(inside, $"{hz} Hz: 0 <= Slide <= 1 and Fold >= 0 (slide {lo}..{hi}, fold min {foldLo})");
        }
    }

    // ------------------------------------------------------------------ continuity and frame-rate independence

    /// <summary>The fastest each axis may move, normalised per second (the springs' analytic peak plus margin).</summary>
    private const double SlideSpeedMax = 7.0, FoldSpeedMax = 8.0;

    /// <summary>An upper bound on |x''| per axis: omega^2 |g - x| + 2 zeta omega |v|, at the stiffest spring.</summary>
    private static double AccelMax(double omega, double speedMax) => omega * omega * (1.0 + 2.0 * T.StopPreload + 0.05) + 2.0 * omega * speedMax;

    /// <summary>
    /// 500 seeded random target flips (Out and Stowed alternating, about a third of the stows fast): every step is
    /// continuous in position and velocity. Checked three ways: (1) at 60 Hz, no step moves an axis faster than it can
    /// travel (a sanity bound: no step jumps); (2) at 240 Hz, velocity changes no faster than the springs can
    /// accelerate (no velocity pops); (3) the position change matches the velocity (no teleport behind a smooth rate).
    /// </summary>
    public static void ReversalIsContinuous()
    {
        List<(double, KvmTarget)> schedule = RandomSchedule(20261018, 500);
        double end = schedule[schedule.Count - 1].Item1 + 1.5;

        // (1) 60 Hz, a sanity bound only: no axis outruns its top speed (7/s, 8/s; these replaced the
        // earlier 2.5*dt / 4*dt bounds). (2) and (3) are the real continuity checks.
        List<Sample> run60 = Run(Stowed(), Hz(60), Scheduled(schedule), end);
        double worstDs = 0.0, worstDf = 0.0;
        for (int i = 1; i < run60.Count; i++)
        {
            worstDs = Math.Max(worstDs, Math.Abs(run60[i].Slide - run60[i - 1].Slide) / run60[i].Dt);
            worstDf = Math.Max(worstDf, Math.Abs(run60[i].Fold - run60[i - 1].Fold) / run60[i].Dt);
        }

        Check(worstDs <= SlideSpeedMax, $"60 Hz sanity: |dSlide| <= {SlideSpeedMax}*dt on every step (worst {worstDs:0.00}/s)");
        Check(worstDf <= FoldSpeedMax, $"60 Hz sanity: |dFold| <= {FoldSpeedMax}*dt on every step (worst {worstDf:0.00}/s)");

        // (2) and (3) at 240 Hz.
        double aSlide = AccelMax(T.SlideOmegaFast, SlideSpeedMax), aFold = AccelMax(T.FoldOmegaFast, FoldSpeedMax);
        List<Sample> run = Run(Stowed(), Hz(240), Scheduled(schedule), end);
        double worstDvs = 0.0, worstDvf = 0.0, worstXs = 0.0, worstXf = 0.0;
        float foldMax = 0f;
        bool finite = true;
        for (int i = 1; i < run.Count; i++)
        {
            Sample a = run[i - 1], b = run[i];
            double dt = b.Dt;
            finite &= !float.IsNaN(b.Slide) && !float.IsNaN(b.Fold) && !float.IsNaN(b.SlideRate) && !float.IsNaN(b.FoldRate);
            worstDvs = Math.Max(worstDvs, Math.Abs(b.SlideRate - a.SlideRate) / (aSlide * dt));
            worstDvf = Math.Max(worstDvf, Math.Abs(b.FoldRate - a.FoldRate) / (aFold * dt));
            worstXs = Math.Max(worstXs, Math.Abs(b.Slide - a.Slide - 0.5 * (a.SlideRate + b.SlideRate) * dt) / (aSlide * dt * dt / 4.0));
            worstXf = Math.Max(worstXf, Math.Abs(b.Fold - a.Fold - 0.5 * (a.FoldRate + b.FoldRate) * dt) / (aFold * dt * dt / 4.0));
            foldMax = Math.Max(foldMax, b.Fold);
        }

        Check(finite, "240 Hz: never NaN");
        Check(worstDvs <= 1.0, $"240 Hz: slide velocity continuous, |dv| <= {aSlide:0}/s^2 * dt (worst {worstDvs:0.00} of the bound)");
        Check(worstDvf <= 1.0, $"240 Hz: fold velocity continuous, |dv| <= {aFold:0}/s^2 * dt (worst {worstDvf:0.00} of the bound)");
        Check(worstXs <= 1.0, $"240 Hz: slide position follows its velocity (worst {worstXs:0.00} of the bound)");
        Check(worstXf <= 1.0, $"240 Hz: fold position follows its velocity (worst {worstXf:0.00} of the bound)");
        Check(foldMax <= 1.03f, $"240 Hz: no reversal throws the lid past the bounce (max {foldMax:0.0000})");
    }

    /// <summary>The same motion at 30, 60 and 144 Hz and at a jittery frame rate as at 240 Hz, within 0.005 (2 mm / 0.5 degree).</summary>
    public static void DtIndependence()
    {
        const double tolerance = 0.005;
        var jitter = new Rng(42);
        var irregular = new List<double>();
        for (int i = 0; i < 4000; i++)
            irregular.Add(jitter.Range(1.0 / 200.0, 1.0 / 20.0));

        var scenarios = new List<(string Name, Func<KvmMotion> Start, Func<double, KvmTarget> Target, bool Aligned)>
        {
            ("open", Stowed, Always(KvmTarget.Out), false),
            ("close", Out, Always(KvmTarget.Stowed), false),
            ("fast_stow", Out, Always(KvmTarget.FastStow), false),
            ("reverse_at_0.5s", Stowed, Flip(KvmTarget.Out, 0.5, KvmTarget.Stowed), true),
            ("reverse_at_1.0s", Stowed, Flip(KvmTarget.Out, 1.0, KvmTarget.FastStow), true),
        };

        foreach ((string name, Func<KvmMotion> start, Func<double, KvmTarget> target, bool aligned) in scenarios)
        {
            List<Sample> reference = Run(start(), Hz(240), target, 2.5);
            var rates = new List<(string, Func<int, double>)> { ("30 Hz", Hz(30)), ("60 Hz", Hz(60)), ("144 Hz", Hz(144)) };
            if (!aligned)
                rates.Add(("irregular", k => irregular[k % irregular.Count])); // a flip would land between its frames

            foreach ((string rate, Func<int, double> dtOf) in rates)
            {
                double worst = 0.0;
                foreach (Sample s in Run(start(), dtOf, target, 2.5))
                {
                    (double slide, double fold) = Interpolate(reference, s.Time);
                    worst = Math.Max(worst, Math.Max(Math.Abs(s.Slide - slide), Math.Abs(s.Fold - fold)));
                }

                Check(worst <= tolerance, $"{name} at {rate} matches 240 Hz within {tolerance} (worst {worst:0.00000})");
            }
        }
    }

    private static (double Slide, double Fold) Interpolate(List<Sample> run, double t)
    {
        int lo = 0, hi = run.Count - 1;
        if (t >= run[hi].Time)
            return (run[hi].Slide, run[hi].Fold);
        while (hi - lo > 1)
        {
            int mid = (lo + hi) / 2;
            if (run[mid].Time <= t)
                lo = mid;
            else
                hi = mid;
        }

        Sample a = run[lo], b = run[hi];
        double u = (t - a.Time) / (b.Time - a.Time);
        return (a.Slide + (b.Slide - a.Slide) * u, a.Fold + (b.Fold - a.Fold) * u);
    }

    /// <summary>
    /// The retract gate needs the lid on its way down (KvmMotion.LidClear): a stow commanded just after the lid
    /// began to lift finds it under the gate but still rising, and the drawer must stay out until the lid turns over,
    /// then retract. Checked for Stowed (2 degree gate) and FastStow (8 degrees), at 240 Hz.
    /// </summary>
    public static void RetractWaitsForAFallingLid()
    {
        foreach (KvmTarget stow in new[] { KvmTarget.Stowed, KvmTarget.FastStow })
        {
            double gate = stow == KvmTarget.FastStow ? T.RetractGateFast : T.RetractGate;
            var m = Stowed();
            double t = 0.0;
            while (!(m.Pose.Fold > gate * 0.3 && m.Pose.Fold < gate * 0.6 && m.Velocity.Fold > 0f) && t < 3.0)
            {
                m.Step(1f / 240f, KvmTarget.Out);
                t += 1.0 / 240.0;
            }

            Check(m.Pose.Slide >= T.FoldGate && m.Velocity.Fold > 0f && m.Pose.Fold < gate,
                $"{stow}: caught the lid under the gate and rising (fold {m.Pose.Fold * 100f:0.00} deg at {t:0.000} s)");

            // The drawer is still easing onto its out stop: "held out" = it never heads home (its rate stays >= 0)
            // until the lid has turned over and is under the gate.
            bool heldWhileRising = true, sawRise = false;
            double retractAt = double.NaN, turnedAt = double.NaN;
            for (int k = 0; k < 240 * 3; k++)
            {
                m.Step(1f / 240f, stow);
                t += 1.0 / 240.0;
                bool lidClear = m.Velocity.Fold <= 0f && m.Pose.Fold <= gate;
                if (m.Velocity.Fold > 0f)
                    sawRise = true;
                if (double.IsNaN(turnedAt) && lidClear)
                    turnedAt = t;
                if (double.IsNaN(retractAt) && m.Velocity.Slide < 0f)
                    retractAt = t;
                if (double.IsNaN(turnedAt))
                    heldWhileRising &= m.Velocity.Slide >= 0f;
            }

            Check(sawRise && heldWhileRising, $"{stow}: the drawer never heads home while the lid rises or is above the gate");
            Check(!double.IsNaN(retractAt) && retractAt >= turnedAt && retractAt <= turnedAt + 0.1,
                $"{stow}: the drawer retracts once the lid turns over (turned {turnedAt:0.000} s, retracts {retractAt:0.000} s)");
            Check(m.Settled && m.Pose.Slide == 0f && m.Pose.Fold == 0f, $"{stow}: and ends home ({m.Pose})");
        }
    }

    /// <summary>
    /// A part resting on its preloaded stop leaves it at once (KvmMotion.Axis.LeaveStop): from Stowed the
    /// drawer moves on the first step of any size, and the open's start does not depend on the step size; on a stow
    /// the drawer leaves its out stop within one step of the lid clearing the gate.
    /// </summary>
    public static void LeavesTheStopAtOnce()
    {
        foreach (float dt in new[] { 0.0005f, 1f / 240f, 1f / 60f })
        {
            var m = Stowed();
            m.Step(dt, KvmTarget.Out);
            Check(m.Pose.Slide > 0f && m.Velocity.Slide > 0f, $"stowed -> Out: the drawer moves on the first {dt * 1000f:0.0} ms step ({m.Pose.Slide:E2})");
        }

        var coarse = Stowed();
        coarse.Step(0.008f, KvmTarget.Out);
        var fine = Stowed();
        for (int i = 0; i < 80; i++)
            fine.Step(0.0001f, KvmTarget.Out);
        Check(Math.Abs(coarse.Pose.Slide - fine.Pose.Slide) <= 1e-6f * Math.Max(1f, fine.Pose.Slide) + 1e-8f,
            $"the first 8 ms off the stop: 1 x 8 ms == 80 x 0.1 ms ({coarse.Pose.Slide:E4} vs {fine.Pose.Slide:E4})");

        // From Out: the first step after the lid clears the 2 degree gate (and is falling) moves the drawer.
        var o = Out();
        bool cleared = false;
        bool movedNext = false;
        for (int k = 0; k < 3000 && !movedNext; k++)
        {
            o.Step(0.001f, KvmTarget.Stowed);
            if (cleared)
            {
                movedNext = o.Pose.Slide < 1f;
                break;
            }

            cleared = o.Pose.Fold <= T.RetractGate && o.Velocity.Fold <= 0f && o.Pose.Slide == 1f;
        }

        Check(cleared && movedNext, "stow: the drawer leaves its out stop within one 1 ms step of the lid clearing the gate");
    }

    /// <summary>Before any gate fires, one big step equals many small ones: the integrator is exact, not just stable.</summary>
    public static void IntegratorIsExact()
    {
        var coarse = Stowed();
        coarse.Step(0.1f, KvmTarget.Out);
        coarse.Step(0.1f, KvmTarget.Out);

        var fine = Stowed();
        for (int i = 0; i < 200; i++)
            fine.Step(0.001f, KvmTarget.Out);

        Check(Math.Abs(coarse.Pose.Slide - fine.Pose.Slide) <= 1e-5f && Math.Abs(coarse.Velocity.Slide - fine.Velocity.Slide) <= 1e-4f,
            $"2 x 0.1 s == 200 x 1 ms at 0.2 s ({coarse.Pose.Slide:0.000000} vs {fine.Pose.Slide:0.000000})");
        Check(coarse.Pose.Fold == 0f && fine.Pose.Fold == 0f, "the lid has not moved before the gate");
    }

    /// <summary>The same inputs give bit-identical poses.</summary>
    public static void Deterministic()
    {
        List<(double, KvmTarget)> schedule = RandomSchedule(99, 60);
        List<Sample> a = Run(Stowed(), Hz(60), Scheduled(schedule), 20.0);
        List<Sample> b = Run(Stowed(), Hz(60), Scheduled(schedule), 20.0);
        bool same = a.Count == b.Count;
        for (int i = 0; same && i < a.Count; i++)
            same = a[i].Slide == b[i].Slide && a[i].Fold == b[i].Fold && a[i].Settled == b[i].Settled;
        Check(same, "two runs of one schedule are bit-identical");
    }

    // ------------------------------------------------------------------ snap, spawn, bad input

    /// <summary>Snap jumps to an end pose at rest, with no motion afterwards.</summary>
    public static void SnapIsImmediate()
    {
        var m = Stowed();
        m.Step(0.2f, KvmTarget.Out); // mid-motion
        m.Snap(true);
        Check(m.Pose.Slide == 1f && m.Pose.Fold == 1f && m.Settled && m.Target == KvmTarget.Out, $"Snap(true) -> (1, 1), Settled: {m.Pose}");
        Check(m.Velocity.Slide == 0f && m.Velocity.Fold == 0f, "Snap(true) is at rest");
        m.Step(1f / 60f, KvmTarget.Out);
        Check(m.Pose.Slide == 1f && m.Pose.Fold == 1f && m.Settled, "a step after the snap stays put");

        m.Snap(false);
        Check(m.Pose.Slide == 0f && m.Pose.Fold == 0f && m.Settled && m.Target == KvmTarget.Stowed, $"Snap(false) -> (0, 0), Settled: {m.Pose}");

        // A snapped-out KVM asked to stow folds first, exactly like one that animated out.
        List<Sample> snapped = Run(Out(), Hz(60), Always(KvmTarget.Stowed), Long);
        var animated = Stowed();
        Run(animated, Hz(60), Always(KvmTarget.Out), Long);
        List<Sample> after = Run(animated, Hz(60), Always(KvmTarget.Stowed), Long);
        bool same = snapped.Count == after.Count;
        for (int i = 0; same && i < snapped.Count; i++)
            same = snapped[i].Slide == after[i].Slide && snapped[i].Fold == after[i].Fold;
        Check(same, "a snapped pose behaves exactly like a settled one");
    }

    /// <summary>A spawn within the scene-entry window snaps; a later one (a weld finished in play) animates.</summary>
    public static void SpawnPolicySnapsOnlyOnSceneEntry()
    {
        Check(KvmSpawnPolicy.ShouldSnap(0f), "ShouldSnap(0) (the same frame as the scene entry)");
        Check(KvmSpawnPolicy.ShouldSnap(0.2f), "ShouldSnap(0.2)");
        Check(KvmSpawnPolicy.ShouldSnap(0.999f), "ShouldSnap(0.999)");
        Check(!KvmSpawnPolicy.ShouldSnap(1.0f), "!ShouldSnap(1.0)");
        Check(!KvmSpawnPolicy.ShouldSnap(5f), "!ShouldSnap(5)");
        Check(!KvmSpawnPolicy.ShouldSnap(float.NaN), "!ShouldSnap(NaN): an unknown age animates");
    }

    /// <summary>dt = 0 (pause) or negative changes nothing, not even the target, and leaves no trace on the run.</summary>
    public static void DtZeroNoop()
    {
        var m = Stowed();
        var twin = Stowed();
        for (int i = 0; i < 30; i++)
        {
            m.Step(1f / 60f, KvmTarget.Out);
            twin.Step(1f / 60f, KvmTarget.Out);
        }

        KvmPose pose = m.Pose, rate = m.Velocity;
        m.Step(0f, KvmTarget.Stowed);
        m.Step(-0.5f, KvmTarget.FastStow);
        m.Step(-0f, KvmTarget.Stowed);
        Check(Same(m.Pose, pose) && Same(m.Velocity, rate) && m.Target == KvmTarget.Out && !m.Settled,
            "dt <= 0 changes no pose, rate, target or settle");

        for (int i = 0; i < 60; i++)
        {
            m.Step(1f / 60f, KvmTarget.Out);
            twin.Step(1f / 60f, KvmTarget.Out);
        }

        Check(Same(m.Pose, twin.Pose), "the run continues exactly as if the paused frames never happened");
    }

    /// <summary>NaN or infinite dt changes nothing.</summary>
    public static void NanGuard()
    {
        var m = Stowed();
        for (int i = 0; i < 40; i++)
            m.Step(1f / 60f, KvmTarget.Out);
        KvmPose pose = m.Pose, rate = m.Velocity;
        foreach (float bad in new[] { float.NaN, float.PositiveInfinity, float.NegativeInfinity })
        {
            m.Step(bad, KvmTarget.Stowed);
            Check(Same(m.Pose, pose) && Same(m.Velocity, rate) && m.Target == KvmTarget.Out, $"dt = {bad} changes nothing");
        }

        m.Step(1f / 60f, (KvmTarget)42);
        Check(m.Target == KvmTarget.Stowed && !float.IsNaN(m.Pose.Slide), "an out-of-range target is a stow");
    }

    /// <summary>Hitches of 0.5 s and 2 s stay finite and inside the stops, act as MaxDt (no teleport) and still settle.</summary>
    public static void LargeDtStable()
    {
        foreach (float dt in new[] { 0.5f, 2.0f })
        {
            foreach ((Func<KvmMotion> start, KvmTarget target) in new (Func<KvmMotion>, KvmTarget)[]
                     {
                         (Stowed, KvmTarget.Out), (Out, KvmTarget.Stowed), (Out, KvmTarget.FastStow),
                     })
            {
                var m = start();
                var reference = start();
                m.Step(dt, target);
                reference.Step(T.MaxDt, target);
                Check(Same(m.Pose, reference.Pose), $"dt {dt} toward {target}: one hitch moves as far as MaxDt ({m.Pose})");

                bool ok = true;
                int steps = 0;
                while (!m.Settled && steps < 100)
                {
                    m.Step(dt, target);
                    steps++;
                    ok &= !float.IsNaN(m.Pose.Slide) && !float.IsNaN(m.Pose.Fold)
                          && m.Pose.Slide >= 0f && m.Pose.Slide <= 1f && m.Pose.Fold >= 0f && m.Pose.Fold <= 1.03f;
                }

                Check(ok, $"dt {dt} toward {target}: finite and inside the stops");
                Check(m.Settled, $"dt {dt} toward {target}: settles ({steps} hitches)");
            }

            // A flip-flopping target under hitches.
            var flip = Stowed();
            bool fine = true;
            for (int i = 0; i < 200; i++)
            {
                flip.Step(dt, i % 3 == 0 ? KvmTarget.Out : i % 3 == 1 ? KvmTarget.FastStow : KvmTarget.Stowed);
                fine &= !float.IsNaN(flip.Pose.Slide) && flip.Pose.Slide >= 0f && flip.Pose.Slide <= 1f && flip.Pose.Fold >= 0f;
            }

            Check(fine, $"dt {dt}: flipping targets under hitches stays finite and inside the stops");
        }
    }

    /// <summary>Step allocates nothing (it runs every frame for every KVM in view).</summary>
    public static void StepAllocatesNothing()
    {
        var m = Stowed();
        m.Step(1f / 60f, KvmTarget.Out); // warm up (JIT)
        long before = GC.GetAllocatedBytesForCurrentThread();
        float sink = 0f;
        for (int i = 0; i < 20000; i++)
        {
            KvmPose p = m.Step(1f / 60f, (i / 50) % 2 == 0 ? KvmTarget.Out : KvmTarget.Stowed);
            sink += p.Slide + m.Velocity.Fold;
        }

        long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
        Check(allocated == 0 && !float.IsNaN(sink), $"20000 steps allocate nothing ({allocated} bytes)");
    }

    /// <summary>Bad tuning arguments fall back to the defaults; good ones are kept.</summary>
    public static void TuningSanitises()
    {
        var t = new KvmMotionTuning(slideOmega: float.NaN, foldGate: 2f, maxDt: -1f, snapEpsilon: float.PositiveInfinity, lidAxisSign: -7);
        Check(t.SlideOmega == T.SlideOmega && t.FoldGate == T.FoldGate && t.MaxDt == T.MaxDt && t.SnapEpsilon == T.SnapEpsilon,
            "NaN, out-of-range and infinite values fall back to the defaults");
        Check(t.LidAxisSign == -1, "any negative axis sign is -1");

        var g = new KvmMotionTuning(foldGate: 0.95f, openBeat: 0.1f);
        Check(g.FoldGate == 0.95f && g.OpenBeat == 0.1f && g.SlideOmega == T.SlideOmega, "valid values are kept, the rest default");

        // Variant tunings stay sane: no lead, an overdamped lid, a zero beat.
        foreach (KvmMotionTuning variant in new[]
                 {
                     new KvmMotionTuning(leadRatio: 0f), new KvmMotionTuning(foldZetaOpen: 1.6f),
                     new KvmMotionTuning(openBeat: 0f, stopPreload: 0f), new KvmMotionTuning(leadRatio: 1f, foldZetaOpen: 1f),
                 })
        {
            var m = new KvmMotion(variant);
            List<Sample> open = Run(m, Hz(60), Always(KvmTarget.Out), 8.0);
            List<Sample> close = Run(m, Hz(60), Always(KvmTarget.Stowed), 8.0);
            bool sane = true;
            foreach (Sample s in open)
                sane &= !float.IsNaN(s.Slide) && !float.IsNaN(s.Fold) && s.Slide >= 0f && s.Slide <= 1f && s.Fold >= 0f;
            Check(sane && open[open.Count - 1].Settled && close[close.Count - 1].Settled,
                $"lead {variant.LeadRatio}, lid zeta {variant.FoldZetaOpen}, beat {variant.OpenBeat}: sane, and settles both ways");
        }
    }

    private static bool Same(KvmPose a, KvmPose b) => a.Slide == b.Slide && a.Fold == b.Fold;

    // ------------------------------------------------------------------ front cell

    /// <summary>
    /// A 2x1x3 block at the origin under all 24 (forward, up) orientations: the front cell is outside the block, next to
    /// the centre of its forward face, rounding toward min on even widths.
    /// </summary>
    public static void FrontCellAll24Orientations()
    {
        var axes = new[] { new Int3(1, 0, 0), new Int3(-1, 0, 0), new Int3(0, 1, 0), new Int3(0, -1, 0), new Int3(0, 0, 1), new Int3(0, 0, -1) };
        var size = new Int3(2, 1, 3); // block-local extents (X, Y, Z); the block's local forward is -Z (the game's front)
        int orientations = 0;
        var seen = new HashSet<string>();
        foreach (Int3 forward in axes)
        {
            foreach (Int3 up in axes)
            {
                if (Dot(forward, up) != 0)
                    continue;

                orientations++;
                // Local axes in world: right = forward x up... the local frame is (right, up, backward) with backward = -forward.
                Int3 backward = Neg(forward);
                Int3 right = Cross(up, backward);
                Int3 world = Abs(Add(Add(Scale(right, size.X), Scale(up, size.Y)), Scale(backward, size.Z)));
                var min = new Int3(0, 0, 0);
                var max = new Int3(world.X - 1, world.Y - 1, world.Z - 1);
                seen.Add($"{forward}{up}");

                Int3 cell = KvmFrontCell.Of(min, max, forward);
                bool outside = cell.X < min.X || cell.X > max.X || cell.Y < min.Y || cell.Y > max.Y || cell.Z < min.Z || cell.Z > max.Z;
                bool adjacent = Axis(forward, cell) == (Sign(forward) > 0 ? Axis(forward, max) + 1 : Axis(forward, min) - 1);
                bool centred = true;
                foreach (Int3 across in axes)
                {
                    if (Dot(across, forward) != 0 || Sign(across) < 0)
                        continue;
                    int lo = Axis(across, min), hi = Axis(across, max);
                    centred &= Axis(across, cell) == lo + (hi - lo) / 2;
                }

                Check(outside && adjacent && centred,
                    $"forward {forward}, up {up}: AABB {min}..{max}, front cell {cell} (outside {outside}, adjacent {adjacent}, centred {centred})");
            }
        }

        Check(orientations == 24 && seen.Count == 24, $"24 distinct orientations ({orientations})");

        // The rounding rule and the edge cases, explicitly.
        Check(KvmFrontCell.Of(new Int3(0, 0, 0), new Int3(1, 0, 2), new Int3(0, 0, -1)).Equals(new Int3(0, 0, -1)),
            "width 2 rounds toward min");
        Check(KvmFrontCell.Of(new Int3(-4, -3, -2), new Int3(-1, -3, 0), new Int3(0, 1, 0)).Equals(new Int3(-3, -2, -1)),
            "negative cells round toward min too");
        Check(KvmFrontCell.Of(new Int3(1, 0, 2), new Int3(0, 0, 0), new Int3(1, 0, 0)).Equals(new Int3(2, 0, 1)), "min and max in either order");
        Check(KvmFrontCell.Of(new Int3(0, 0, 0), new Int3(1, 0, 2), new Int3(0, 0, 0)).Equals(new Int3(0, 0, 1)),
            "a zero forward gives the block's own centre cell (never a door)");
    }

    /// <summary>
    /// The rack's front zone is free cells (the slot opening), so the rack link looks BESIDE
    /// the KVM. In the full and half rack's cell layout (dc/rack.py: the box minus the slots and the slots' front row),
    /// for a KVM in every slot facing the front: the front cell is free, some Beside cell is the rack's and the rack's
    /// box contains the KVM's; facing the rear, the front cell (the rear stop's) is the rack's. Beside cells are outside
    /// the block next to a side face (never along forward), for every orientation.
    /// </summary>
    public static void FrontCellBesideFindsTheRack()
    {
        foreach (var (name, height, slots) in new[] { ("full", 10, 8), ("half", 5, 4) })
        {
            var rmin = new Int3(-1, -((height - 1) / 2), -2);
            var rmax = new Int3(2, rmin.Y + height - 1, 2);
            var free = new HashSet<Int3>();
            for (int k = 0; k < slots; k++)
                for (int x = 0; x <= 1; x++)
                    for (int z = -2; z <= 1; z++)
                        free.Add(new Int3(x, rmin.Y + 1 + k, z));
            bool Rack(Int3 c) => c.X >= rmin.X && c.X <= rmax.X && c.Y >= rmin.Y && c.Y <= rmax.Y && c.Z >= rmin.Z && c.Z <= rmax.Z && !free.Contains(c);

            for (int k = 0; k < slots; k++)
            {
                var kmin = new Int3(0, rmin.Y + 1 + k, -1);
                var kmax = new Int3(1, rmin.Y + 1 + k, 1);
                var front = new Int3(0, 0, -1);
                Check(!Rack(KvmFrontCell.Of(kmin, kmax, front)), $"{name} slot {k + 1}: the front cell is the opening");
                bool found = false;
                for (int i = 0; i < KvmFrontCell.BesideCount; i++)
                    found |= Rack(KvmFrontCell.Beside(kmin, kmax, front, i));
                Check(found && KvmFrontCell.Contains(rmin, rmax, kmin, kmax), $"{name} slot {k + 1}: the rack is beside");
                Check(Rack(KvmFrontCell.Of(kmin, kmax, new Int3(0, 0, 1))), $"{name} slot {k + 1}: rear-facing, the rear stop is in front");
            }
        }

        var axes = new[] { new Int3(1, 0, 0), new Int3(-1, 0, 0), new Int3(0, 1, 0), new Int3(0, -1, 0), new Int3(0, 0, 1), new Int3(0, 0, -1) };
        var min = new Int3(0, 0, 0);
        var max = new Int3(1, 0, 2);
        foreach (Int3 f in axes)
        {
            var seen = new HashSet<Int3>();
            for (int i = 0; i < KvmFrontCell.BesideCount; i++)
            {
                Int3 c = KvmFrontCell.Beside(min, max, f, i);
                seen.Add(c);
                bool outside = c.X < min.X || c.X > max.X || c.Y < min.Y || c.Y > max.Y || c.Z < min.Z || c.Z > max.Z;
                bool along = f.X != 0 ? c.X >= min.X && c.X <= max.X : f.Y != 0 ? c.Y >= min.Y && c.Y <= max.Y : c.Z >= min.Z && c.Z <= max.Z;
                Check(outside && along, $"beside {i} of forward {f}: {c} outside the block, within its depth");
            }

            Check(seen.Count == 4, $"forward {f}: four distinct side cells");
        }

        Check(KvmFrontCell.Contains(new Int3(2, 5, 2), new Int3(-1, -4, -2), new Int3(0, 1, -1), new Int3(1, 1, 1)), "contains, bounds in either order");
        Check(!KvmFrontCell.Contains(new Int3(-1, -4, -2), new Int3(2, 5, 2), new Int3(0, 1, -3), new Int3(1, 1, -1)), "one cell out is not contained");
    }

    private static int Dot(Int3 a, Int3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;

    private static Int3 Cross(Int3 a, Int3 b) => new Int3(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X);

    private static Int3 Neg(Int3 a) => new Int3(-a.X, -a.Y, -a.Z);

    private static Int3 Add(Int3 a, Int3 b) => new Int3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);

    private static Int3 Scale(Int3 a, int k) => new Int3(a.X * k, a.Y * k, a.Z * k);

    private static Int3 Abs(Int3 a) => new Int3(Math.Abs(a.X), Math.Abs(a.Y), Math.Abs(a.Z));

    private static int Sign(Int3 axis) => axis.X + axis.Y + axis.Z;

    /// <summary>The component of <paramref name="v"/> along the unit axis <paramref name="axis"/> (ignoring its sign).</summary>
    private static int Axis(Int3 axis, Int3 v) => axis.X != 0 ? v.X : axis.Y != 0 ? v.Y : v.Z;

    // ------------------------------------------------------------------ trajectories (--dump)

    /// <summary>
    /// The six 240 Hz trajectories of the sequenced motion, as <c>t,slide,fold,target</c> CSVs: written only with --dump,
    /// checked always (each one ends settled at the pose its last target names).
    /// </summary>
    public static void Trajectories()
    {
        var scenarios = new List<(string File, Func<KvmMotion> Start, Func<double, KvmTarget> Target, double LastEvent)>
        {
            ("open", Stowed, Always(KvmTarget.Out), 0.0),
            ("close", Out, Always(KvmTarget.Stowed), 0.0),
            ("fast_stow", Out, Always(KvmTarget.FastStow), 0.0),
            ("reverse_mid_slide", Stowed, Flip(KvmTarget.Out, 0.25, KvmTarget.Stowed), 0.25),
            ("reverse_mid_fold", Stowed, Flip(KvmTarget.Out, 1.2, KvmTarget.Stowed), 1.2),
            ("door_close_while_out", Out, Flip(KvmTarget.Out, 0.1, KvmTarget.FastStow), 0.1),
        };

        foreach ((string file, Func<KvmMotion> start, Func<double, KvmTarget> target, double lastEvent) in scenarios)
        {
            List<Sample> run = Run(start(), Hz(240), target, 4.0, tail: 0.25, settleAfter: lastEvent + 1e-6);
            Sample last = run[run.Count - 1];
            bool atOut = last.Slide == 1f && last.Fold == 1f, atHome = last.Slide == 0f && last.Fold == 0f;
            Check(last.Settled && (last.Target == KvmTarget.Out ? atOut : atHome), $"{file}: ends settled at its target ({last.Target}, slide {last.Slide}, fold {last.Fold})");

            var csv = new StringBuilder("t,slide,fold,target\n");
            foreach (Sample s in run)
            {
                csv.Append(s.Time.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                   .Append(s.Slide.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                   .Append(s.Fold.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                   .Append(TargetOf(target, s)).Append('\n');
            }

            Program.Dump(file + ".csv", csv.ToString());
        }
    }

    /// <summary>
    /// The reversal sweep for the Python swept-geometry checks: one 240 Hz run per (family, reversal instant), every
    /// 0.1 s through the whole motion, as one <c>run,t,slide,fold,target</c> CSV. The families are the four ways a
    /// command can land mid-motion:
    /// <list type="bullet">
    /// <item><c>open_stow@t</c>: opening, switched Off at t;</item>
    /// <item><c>open_fast@t</c>: opening, the rack door starts closing at t (FastStow);</item>
    /// <item><c>close_out@t</c>: closing, switched back On at t (the path bends back out);</item>
    /// <item><c>close_fast@t</c>: closing, the rack door starts closing at t.</item>
    /// </list>
    /// Each run must end settled at its last target's pose.
    /// </summary>
    public static void ReversalSweep()
    {
        var families = new List<(string Name, Func<KvmMotion> Start, KvmTarget First, KvmTarget Then, double Until)>
        {
            ("open_stow", Stowed, KvmTarget.Out, KvmTarget.Stowed, 1.60),
            ("open_fast", Stowed, KvmTarget.Out, KvmTarget.FastStow, 1.60),
            ("close_out", Out, KvmTarget.Stowed, KvmTarget.Out, 1.80),
            ("close_fast", Out, KvmTarget.Stowed, KvmTarget.FastStow, 1.80),
        };

        var csv = new StringBuilder("run,t,slide,fold,target\n");
        int runs = 0;
        foreach ((string name, Func<KvmMotion> start, KvmTarget first, KvmTarget then, double until) in families)
        {
            for (int k = 1; k * 0.1 <= until + 1e-9; k++)
            {
                double at = Math.Round(k * 0.1, 6);
                Func<double, KvmTarget> target = Flip(first, at, then);
                List<Sample> run = Run(start(), Hz(240), target, 5.0, tail: 0.05, settleAfter: at + 1e-6);
                Sample last = run[run.Count - 1];
                bool atOut = last.Slide == 1f && last.Fold == 1f, atHome = last.Slide == 0f && last.Fold == 0f;
                string id = name + "@" + at.ToString("0.0", CultureInfo.InvariantCulture);
                Check(last.Settled && (last.Target == KvmTarget.Out ? atOut : atHome), $"sweep {id}: ends settled at its target");
                foreach (Sample s in run)
                {
                    csv.Append(id).Append(',')
                       .Append(s.Time.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                       .Append(s.Slide.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                       .Append(s.Fold.ToString("0.000000", CultureInfo.InvariantCulture)).Append(',')
                       .Append(TargetOf(target, s)).Append('\n');
                }

                runs++;
            }
        }

        Check(runs == 16 + 16 + 18 + 18, $"sweep: {runs} runs");
        Program.Dump("reversal_sweep.csv", csv.ToString());
    }

    /// <summary>The target in force during the frame that ended at <paramref name="s"/> (sample 0: the first frame's).</summary>
    private static string TargetOf(Func<double, KvmTarget> target, Sample s)
        => (s.Dt > 0.0 ? s.Target : target(0.0)).ToString();
}
