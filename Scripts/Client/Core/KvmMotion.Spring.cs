// KvmMotion.Spring: the closed-form damped spring behind each KVM axis, and the axis state it advances.
// Exact for any step, so the motion does not depend on the frame rate. See KvmMotion.cs.
//
// Game APIs: none (game-free; compiled by Tests/CoreTests and inside DataCenter.Client).
#nullable enable
using System;

namespace DataCenter.Kvm.Core;

/// <remarks>This part holds the spring integrator and the per-axis state.</remarks>
public sealed partial class KvmMotion
{
    /// <summary>One axis: position, velocity and the lead goal the spring chases.</summary>
    private struct Axis
    {
        public double X;
        public double V;
        public double G;

        public bool IsFinite => IsFiniteValue(X) && IsFiniteValue(V) && IsFiniteValue(G);

        public Axis(double x, double v, double g)
        {
            X = x;
            V = v;
            G = g;
        }

        /// <summary>
        /// A part resting on a stop (0 or 1) with its goal preloaded past it starts from the stop: when it is asked
        /// away from the stop, the goal is pulled back onto it. Without this the preloaded goal first has to cross
        /// back over the stop, and the part sits pressed into it for a few ms (a step-size dependent delay). At rest on
        /// a stop the net acceleration is zero either way, so the motion stays continuous.
        /// </summary>
        public void LeaveStop(double target)
        {
            if (X <= 0.0 && V <= 0.0 && G < 0.0 && target > 0.0)
                G = 0.0;
            else if (X >= 1.0 && V >= 0.0 && G > 1.0 && target < 1.0)
                G = 1.0;
        }

        /// <summary>Within eps of <paramref name="x"/> (and of the goal), with a speed under eps x omega.</summary>
        public bool Near(double x, double goal, double eps, double omega)
            => Math.Abs(X - x) <= eps && Math.Abs(V) <= eps * omega && Math.Abs(G - goal) <= eps;

        private static bool IsFiniteValue(double v) => !double.IsNaN(v) && !double.IsInfinity(v);
    }

    /// <summary>
    /// A damped spring x'' + 2 zeta omega x' + omega^2 x = omega^2 g, whose goal g eases toward the target as
    /// g' = lambda (target - g). Advanced in closed form, so one step of h equals any split of h (up to rounding).
    /// </summary>
    private readonly struct Spring
    {
        public readonly double Omega;
        private readonly double _lead;   // lambda; 0 = the goal jumps to the target
        private readonly double _gain;   // omega^2 / (lambda^2 - 2 zeta omega lambda + omega^2): the particular solution's gain
        private readonly double _sigma;  // decay rate (zeta omega)
        private readonly double _wd;     // damped frequency (zeta < 1)
        private readonly double _r1, _r2; // real roots (zeta > 1)
        private readonly int _regime;    // -1 under-, 0 critically, +1 over-damped

        public Spring(double omega, double zeta, double leadRatio)
        {
            Omega = omega;
            _sigma = zeta * omega;
            _wd = 0.0;
            _r1 = _r2 = 0.0;
            if (Math.Abs(zeta - 1.0) < 1e-4)
            {
                _regime = 0;
            }
            else if (zeta < 1.0)
            {
                _regime = -1;
                _wd = omega * Math.Sqrt(1.0 - zeta * zeta);
            }
            else
            {
                _regime = 1;
                double root = omega * Math.Sqrt(zeta * zeta - 1.0);
                _r1 = -_sigma + root;
                _r2 = -_sigma - root;
            }

            double lead = leadRatio * omega;
            double den = lead * lead - 2.0 * zeta * omega * lead + omega * omega;
            if (lead > 0.0 && Math.Abs(den) < 1e-3 * omega * omega)
            {
                // Resonance (the lead rate equals a spring root): nudge the lead off it; the feel is unchanged.
                lead *= 1.05;
                den = lead * lead - 2.0 * zeta * omega * lead + omega * omega;
            }

            _lead = lead;
            _gain = lead > 0.0 ? omega * omega / den : 0.0;
        }

        /// <summary>Advance <paramref name="a"/> by <paramref name="h"/> seconds toward <paramref name="target"/>.</summary>
        public void Advance(ref Axis a, double target, double h)
        {
            // Goal: g(t) = target + G0 e^{-lambda t}; particular solution x_p(t) = target + K e^{-lambda t}.
            double g0 = _lead > 0.0 ? a.G - target : 0.0;
            double k = _gain * g0;
            double decay = _lead > 0.0 ? Math.Exp(-_lead * h) : 0.0;

            // Homogeneous part: e = x - x_p, u = v - x_p'.
            double e = a.X - target - k;
            double u = a.V + _lead * k;
            Homogeneous(ref e, ref u, h);

            a.X = target + k * decay + e;
            a.V = -_lead * k * decay + u;
            a.G = target + g0 * decay;
        }

        private void Homogeneous(ref double e, ref double u, double h)
        {
            double w = Omega;
            if (_regime == 0)
            {
                double ex = Math.Exp(-w * h);
                double b = u + w * e;
                double e1 = (e + b * h) * ex;
                u = (u - w * b * h) * ex;
                e = e1;
            }
            else if (_regime < 0)
            {
                double ex = Math.Exp(-_sigma * h);
                double c = Math.Cos(_wd * h);
                double s = Math.Sin(_wd * h);
                double e1 = ex * (e * c + (u + _sigma * e) / _wd * s);
                u = ex * (u * c - (_sigma * u + w * w * e) / _wd * s);
                e = e1;
            }
            else
            {
                double a1 = (u - _r2 * e) / (_r1 - _r2);
                double a2 = e - a1;
                double x1 = Math.Exp(_r1 * h);
                double x2 = Math.Exp(_r2 * h);
                e = a1 * x1 + a2 * x2;
                u = a1 * _r1 * x1 + a2 * _r2 * x2;
            }
        }
    }
}
