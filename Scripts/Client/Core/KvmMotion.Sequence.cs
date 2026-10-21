// KvmMotion.Sequence: the sequencing rules of the KVM motion: the drawer leads on the way
// out, the lid on the way back; the fold gate and the beat between slide and fold; the retract gate a stow waits for;
// the hard stops at the drawer's rails and under the lid. See KvmMotion.cs for the stepping.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <remarks>This part holds the sequencing rules: one substep of each target, its gates and its hard stops.</remarks>
public sealed partial class KvmMotion
{
    /// <summary>Out: the drawer leads; the lid follows the gate and the beat, switching mid-substep at the exact lift time.</summary>
    private void SubstepOut(double h)
    {
        double s0 = _s.X;
        _s.LeaveStop(1.0 + _preload);
        _slide.Advance(ref _s, 1.0 + _preload, h);
        ClampSlide();
        TickLiftClock(s0, h);

        // The part of this substep before the lid may lift (0 once it may, h while the beat is still running).
        double rest = _liftClock < _t.OpenBeat ? h : Clamp(h - (_liftClock - _t.OpenBeat), 0.0, h);
        if (rest > 0.0)
        {
            _foldClose.Advance(ref _f, -_preload, rest); // held flat (or still closing, after a reversal)
            ClampFold();
        }

        if (h - rest > 0.0)
        {
            _f.LeaveStop(1.0);
            _foldOpen.Advance(ref _f, 1.0, h - rest);
            ClampFold();
        }
    }

    /// <summary>Stow: the lid leads; the drawer holds out until the lid passes the retract gate, switching mid-substep.</summary>
    private void SubstepStow(double h, bool fast)
    {
        double gate = fast ? _t.RetractGateFast : _t.RetractGate;
        double f0 = _f.X;
        bool clearBefore = LidClear(gate);
        (fast ? _foldFast : _foldClose).Advance(ref _f, -_preload, h);
        ClampFold();

        double hold = 0.0; // the part of this substep the drawer still holds out
        if (!_retracting)
        {
            // The lid must be under the gate AND on its way down (its lead goal too): a lid caught just after it
            // started to lift is still rising by momentum, and a drawer retracting under it would drive it into the
            // KVM's own upper panel. So the drawer waits for the lid to turn over (the open_fast@1.0 motion graph
            // showed it).
            if (LidClear(gate))
            {
                _retracting = true;
                // clear from the start: no hold; a downward crossing: its linear time inside the substep; a lid that
                // turned over below the gate inside the substep: the substep's end (at most MaxSubstep late, never early)
                hold = clearBefore ? 0.0 : f0 > gate ? h * (f0 - gate) / (f0 - _f.X) : h;
            }
            else
            {
                hold = h;
            }
        }

        double s0 = _s.X;
        Spring slide = fast ? _slideFast : _slide;
        if (hold > 0.0)
        {
            slide.Advance(ref _s, 1.0 + _preload, hold);
            ClampSlide();
        }

        if (h - hold > 0.0)
        {
            _s.LeaveStop(-_preload);
            slide.Advance(ref _s, -_preload, h - hold);
            ClampSlide();
        }

        TickLiftClock(s0, h); // kept running so a reversal to Out with the drawer still out lifts at once
    }

    /// <summary>The lid is under <paramref name="gate"/> and not rising: its position, its rate and its lead goal.</summary>
    private bool LidClear(double gate) => _f.X <= gate && _f.V <= 0.0 && _f.G <= gate;

    /// <summary>Counts the time past the fold gate, crediting a crossing inside the substep with only the part after it.</summary>
    private void TickLiftClock(double s0, double h)
    {
        double gate = _t.FoldGate;
        double s1 = _s.X;
        if (s1 < gate)
        {
            _liftClock = 0.0;
            return;
        }

        double credit = s0 >= gate || s1 <= s0 ? h : h * (s1 - gate) / (s1 - s0);
        _liftClock = Math.Min(_liftClock + credit, LiftClockCap);
    }

    /// <summary>The drawer's rails: an inelastic stop at each end.</summary>
    private void ClampSlide()
    {
        if (_s.X > 1.0)
        {
            _s.X = 1.0;
            if (_s.V > 0.0)
                _s.V = 0.0;
        }
        else if (_s.X < 0.0)
        {
            _s.X = 0.0;
            if (_s.V < 0.0)
                _s.V = 0.0;
        }
    }

    /// <summary>The deck under the lid: an inelastic stop at flat. Open, the lid has only its detent spring.</summary>
    private void ClampFold()
    {
        if (_f.X < 0.0)
        {
            _f.X = 0.0;
            if (_f.V < 0.0)
                _f.V = 0.0;
        }
    }

    private static double Clamp(double v, double min, double max) => v < min ? min : v > max ? max : v;
}
