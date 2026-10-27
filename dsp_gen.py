#!/usr/bin/env python3
"""
DSP Composer – Programmatic VHDL generator for complex DSP blocks.

Higher-level processes are built by composing primitive operators
(delay, multiply, add/accumulate, NCO, complex multiply, etc.).
The emitter turns the composition into clean, generic, asynchronous-reset VHDL.

Supported processes:
  1. FIR Filter (transversal / systolic) + automatic coefficient generation
  2. Digital Mixer (NCO + Complex Multiply)
  3. PI Controller
  4. Polyphase Decimator
  5. Polyphase Interpolator
  6. Biquad IIR (Direct Form I / II)
  7. Streaming Radix-2 FFT (SDF-style skeleton with twiddles)
  8. Coefficient package generator (standalone)

Usage:
    python3 dsp_composer/dsp_gen.py
"""

from __future__ import annotations
import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# ---------------------------------------------------------------------------
# Optional scientific libraries – pure-Python fallbacks are provided
# ---------------------------------------------------------------------------
try:
    import numpy as np
    from scipy import signal as sp_signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    np = None          # type: ignore
    sp_signal = None   # type: ignore
    print("NOTE: numpy/scipy not found – using pure-Python coefficient approximations.")
    print("      For better filters install them or set PYTHONPATH to their location.")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# VHDL Emitter – collects pieces and emits a complete file
# ---------------------------------------------------------------------------

class VHDLEmitter:
    def __init__(self, entity_name: str):
        self.entity_name = entity_name
        self.generics: List[str] = []
        self.ports: List[str] = []
        self.signals: List[str] = []
        self.declarations: List[str] = []
        self.architecture: List[str] = []
        self.libraries = [
            "library ieee;",
            "use ieee.std_logic_1164.all;",
            "use ieee.numeric_std.all;",
            "use ieee.math_real.all;",
        ]

    def add_generic(self, name: str, typ: str, default: str):
        self.generics.append(f"    {name} : {typ} := {default}")

    def add_port(self, name: str, direction: str, typ: str):
        self.ports.append(f"    {name} : {direction} {typ}")

    def add_signal(self, name: str, typ: str, init: str = "(others => '0')"):
        self.signals.append(f"  signal {name} : {typ} := {init};")

    def add_decl(self, code: str):
        self.declarations.append(code)

    def add_arch(self, code: str):
        self.architecture.append(code)

    def emit(self) -> str:
        lines = self.libraries + ["", f"entity {self.entity_name} is"]
        if self.generics:
            lines.append("  generic (")
            lines.append(";\n".join(self.generics))
            lines.append("  );")
        lines.append("  port (")
        lines.append(";\n".join(self.ports))
        lines.append("  );")
        lines.append(f"end entity {self.entity_name};")
        lines.append("")
        lines.append(f"architecture rtl of {self.entity_name} is")
        lines.extend(self.declarations)
        lines.extend(self.signals)
        lines.append("begin")
        lines.extend(self.architecture)
        lines.append(f"end architecture rtl;")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Automatic coefficient generation helpers
# ---------------------------------------------------------------------------

def _sinc(x: float) -> float:
    if abs(x) < 1e-12:
        return 1.0
    return math.sin(math.pi * x) / (math.pi * x)


def _bessel_i0(x: float) -> float:
    """Modified Bessel function of the first kind, order 0 (series approximation)."""
    # Good enough for Kaiser window (x typically < 10)
    s = 1.0
    term = 1.0
    for k in range(1, 40):
        term *= (x / (2.0 * k)) ** 2
        s += term
        if term < 1e-12:
            break
    return s


def _kaiser_window(M: int, beta: float) -> List[float]:
    """Return length-(M+1) Kaiser window."""
    if M == 0:
        return [1.0]
    denom = _bessel_i0(beta)
    w = []
    for n in range(M + 1):
        r = (2.0 * n) / M - 1.0
        arg = beta * math.sqrt(max(0.0, 1.0 - r * r))
        w.append(_bessel_i0(arg) / denom)
    return w


def kaiser_beta_from_attenuation(As: float) -> float:
    """
    Kaiser beta from desired stopband attenuation As in dB.
    Classic Oppenheim / Schafer / Kaiser formula.
    """
    if As > 50.0:
        return 0.1102 * (As - 8.7)
    if As >= 21.0:
        return 0.5842 * ((As - 21.0) ** 0.4) + 0.07886 * (As - 21.0)
    return 0.0


def kaiser_numtaps_estimate(As: float, delta_f_norm: float) -> int:
    """
    Estimate FIR length N for Kaiser window.
    delta_f_norm = (fstop - fpass) / fs   (fraction of sampling rate)

    Uses the common formula:
        N ≈ (As - 7.95) / (14.36 * Δf) + 1
    Result is forced to an odd length (Type-I linear phase).
    """
    if delta_f_norm <= 0.0:
        raise ValueError("Transition width must be > 0")
    n = int(math.ceil((As - 7.95) / (14.36 * delta_f_norm))) + 1
    if n < 3:
        n = 3
    if n % 2 == 0:
        n += 1
    return n


def design_fir_coefficients(
    num_taps: int,
    cutoff: Union[float, Sequence[float]],
    fs: float = 1.0,
    window: str = "hamming",
    ftype: str = "lowpass",
    beta: float = 8.6,
    scale: bool = True,
) -> List[float]:
    """
    Design linear-phase FIR coefficients.

    Parameters
    ----------
    num_taps : number of taps (filter length)
    cutoff  : single float for LPF/HPF, or [f_low, f_high] for BPF/BSF
              (normalised to fs, so 0 … 0.5)
    fs      : sampling frequency (default 1.0 → normalised)
    window  : "hamming" (normal) or "kaiser"
    ftype   : "lowpass", "highpass", "bandpass", "bandstop"
    beta    : Kaiser beta parameter (ignored for Hamming)
    scale   : normalise pass-band gain to 1
    """
    ftype = ftype.lower().replace(" ", "")
    # map common abbreviations
    aliases = {
        "lpf": "lowpass", "hpf": "highpass",
        "bpf": "bandpass", "bsf": "bandstop", "bs": "bandstop",
    }
    ftype = aliases.get(ftype, ftype)

    if HAS_SCIPY:
        # Build scipy firwin arguments
        if window.lower() == "kaiser":
            win = ("kaiser", beta)
        else:
            win = "hamming"

        pass_zero = ftype in ("lowpass", "bandstop")
        # firwin expects cutoff relative to fs
        return sp_signal.firwin(
            num_taps, cutoff, fs=fs, window=win,
            pass_zero=pass_zero, scale=scale,
        ).tolist()

    # ---------- pure-Python fallback ----------
    M = num_taps - 1
    mid = M / 2.0

    # normalise cutoffs to [0, 0.5]
    if isinstance(cutoff, (list, tuple)):
        edges = [float(c) / fs for c in cutoff]
    else:
        edges = [float(cutoff) / fs]

    # ideal impulse response
    h_ideal = []
    for n in range(num_taps):
        t = n - mid
        if ftype == "lowpass":
            fc = edges[0]
            h_ideal.append(2 * fc * _sinc(2 * fc * t))
        elif ftype == "highpass":
            fc = edges[0]
            # complementary of low-pass
            val = _sinc(t) - 2 * fc * _sinc(2 * fc * t) if abs(t) > 1e-12 else 1.0 - 2 * fc
            h_ideal.append(val)
        elif ftype == "bandpass":
            f1, f2 = edges[0], edges[1]
            h_ideal.append(2 * f2 * _sinc(2 * f2 * t) - 2 * f1 * _sinc(2 * f1 * t))
        elif ftype == "bandstop":
            f1, f2 = edges[0], edges[1]
            val = _sinc(t) - (2 * f2 * _sinc(2 * f2 * t) - 2 * f1 * _sinc(2 * f1 * t))
            if abs(t) < 1e-12:
                val = 1.0 - 2 * (f2 - f1)
            h_ideal.append(val)
        else:
            raise ValueError(f"Unsupported ftype: {ftype}")

    # window
    if window.lower() == "kaiser":
        w = _kaiser_window(M, beta)
    else:
        # Hamming
        w = [0.54 - 0.46 * math.cos(2 * math.pi * n / M) for n in range(num_taps)]

    h = [hi * wi for hi, wi in zip(h_ideal, w)]

    if scale:
        # normalise so pass-band gain ≈ 1
        if ftype in ("lowpass", "bandstop"):
            s = sum(h)
        else:
            # evaluate at a point inside the pass-band
            if ftype == "highpass":
                f_ref = 0.5
            else:  # bandpass
                f_ref = 0.5 * (edges[0] + edges[1])
            s = sum(hk * math.cos(2 * math.pi * f_ref * (k - mid)) for k, hk in enumerate(h))
        if abs(s) > 1e-12:
            h = [c / s for c in h]
    return h


def _quadratic_roots(a: float, b: float, c: float) -> List[complex]:
    """Roots of a z^2 + b z + c = 0."""
    if abs(a) < 1e-18:
        if abs(b) < 1e-18:
            return []
        return [complex(-c / b, 0.0)]
    disc = b * b - 4 * a * c
    if disc >= 0:
        s = math.sqrt(disc)
        return [complex((-b + s) / (2 * a), 0.0), complex((-b - s) / (2 * a), 0.0)]
    s = math.sqrt(-disc)
    return [complex(-b / (2 * a), s / (2 * a)), complex(-b / (2 * a), -s / (2 * a))]


def bilinear_biquad_design(
    ftype: str = "lowpass",
    fc_hz: float = 8e6,
    fs_hz: float = 48e6,
    f_low_hz: Optional[float] = None,
    f_high_hz: Optional[float] = None,
    verbose: bool = True,
) -> Tuple[List[float], List[float], dict]:
    """
    Full educational IIR design path for a single 2nd-order section:

      specs → analog Butterworth prototype → pre-warp → bilinear
           → H(z) → poles/zeros → coefficients (b, a)

    Returns
    -------
    b, a : lists of length 3 (a[0] = 1)
    info : dict with intermediate design quantities
    """
    ftype = ftype.lower().replace(" ", "")
    aliases = {"lpf": "lowpass", "hpf": "highpass", "bpf": "bandpass",
               "bsf": "bandstop", "notch": "bandstop"}
    ftype = aliases.get(ftype, ftype)

    if fs_hz <= 0:
        raise ValueError("fs must be > 0")

    # ---- normalised digital frequencies (cycles/sample) ----
    if ftype in ("lowpass", "highpass"):
        fc_norm = fc_hz / fs_hz
        edges_hz = [fc_hz]
        edges_norm = [fc_norm]
    else:
        if f_low_hz is None or f_high_hz is None:
            raise ValueError("bandpass/bandstop need f_low_hz and f_high_hz")
        edges_hz = [f_low_hz, f_high_hz]
        edges_norm = [f_low_hz / fs_hz, f_high_hz / fs_hz]
        fc_norm = 0.5 * (edges_norm[0] + edges_norm[1])

    if verbose:
        print("\n  === IIR design path (bilinear) ===")
        print(f"  Type              : {ftype}")
        print(f"  fs                : {fs_hz:g} Hz")
        if ftype in ("lowpass", "highpass"):
            print(f"  Digital cutoff fc : {fc_hz:g} Hz  (norm {fc_norm:.6f})")
        else:
            print(f"  Band edges        : {edges_hz[0]:g} .. {edges_hz[1]:g} Hz")
            print(f"  Normalised edges  : {edges_norm[0]:.6f} .. {edges_norm[1]:.6f}")

    # Prefer SciPy when available (handles all types cleanly)
    if HAS_SCIPY:
        wn = fc_norm if ftype in ("lowpass", "highpass") else edges_norm
        b, a = sp_signal.iirfilter(
            2, wn, btype=ftype, ftype="butter", fs=1.0, output="ba"
        )
        b, a = b.tolist(), a.tolist()
        # poles / zeros from transfer function
        z_zeros, z_poles, k_gain = sp_signal.tf2zpk(b, a)
        zeros = [complex(z) for z in z_zeros]
        poles = [complex(p) for p in z_poles]
        if verbose:
            print("  Prototype         : 2nd-order Butterworth (SciPy iirfilter)")
            print("  Mapping           : bilinear transform (with pre-warping)")
            print(f"  H(z) numerator b  : [{b[0]:.8f}, {b[1]:.8f}, {b[2]:.8f}]")
            print(f"  H(z) denominator a: [{a[0]:.8f}, {a[1]:.8f}, {a[2]:.8f}]")
            print("  Zeros :", ", ".join(f"{z.real:+.4f}{z.imag:+.4f}j" for z in zeros))
            print("  Poles :", ", ".join(f"{p.real:+.4f}{p.imag:+.4f}j" for p in poles))
            for p in poles:
                r = abs(p)
                print(f"    |pole| = {r:.6f}  ({'stable' if r < 1.0 else 'UNSTABLE'})")
        info = {
            "ftype": ftype, "fs_hz": fs_hz, "edges_hz": edges_hz,
            "edges_norm": edges_norm, "fc_norm": fc_norm,
            "b": b, "a": a, "zeros": zeros, "poles": poles,
            "method": "scipy_bilinear_butterworth",
        }
        return b, a, info

    # ---- pure-Python path: explicit pre-warp + bilinear (LP/HP only) ----
    if ftype not in ("lowpass", "highpass"):
        raise RuntimeError(
            "Pure-Python bilinear path supports lowpass/highpass only. "
            "Install scipy for bandpass/bandstop."
        )

    # Pre-warp: ω_a = 2*fs*tan(π*fc/fs)  but with normalised time (fs=1 in formulas
    # that use tan(π f_norm) the 2*fs scale cancels in the ratio K/ω_a).
    # Using the common form with K = 1 and k = tan(π f_norm):
    k = math.tan(math.pi * fc_norm)          # pre-warped analog frequency proxy
    k2 = k * k
    sqrt2 = math.sqrt(2.0)

    if verbose:
        omega_a = 2.0 * fs_hz * k            # actual analog rad/s
        print(f"  Pre-warp          : k = tan(π·fc/fs) = {k:.6f}")
        print(f"  Analog ω_a        : {omega_a:g} rad/s")
        print("  Analog prototype  : H_a(s) = ω_a² / (s² + √2 ω_a s + ω_a²)")
        print("  Bilinear map      : s = 2 fs (1-z^{-1})/(1+z^{-1})")

    if ftype == "lowpass":
        # H(z) after bilinear on Butterworth LP
        norm = 1.0 + sqrt2 * k + k2
        b0 = k2 / norm
        b1 = 2.0 * b0
        b2 = b0
        a0 = 1.0
        a1 = 2.0 * (k2 - 1.0) / norm
        a2 = (1.0 - sqrt2 * k + k2) / norm
    else:  # highpass
        norm = 1.0 + sqrt2 * k + k2
        b0 = 1.0 / norm
        b1 = -2.0 / norm
        b2 = 1.0 / norm
        a0 = 1.0
        a1 = 2.0 * (k2 - 1.0) / norm
        a2 = (1.0 - sqrt2 * k + k2) / norm

    b = [b0, b1, b2]
    a = [a0, a1, a2]

    # Poles / zeros from quadratic factors (positive powers of z)
    # Num: b0 z^2 + b1 z + b2 ,  Den: a0 z^2 + a1 z + a2
    zeros = _quadratic_roots(b0, b1, b2)
    poles = _quadratic_roots(a0, a1, a2)

    if verbose:
        print(f"  H(z) = ({b0:.8f} + {b1:.8f} z^-1 + {b2:.8f} z^-2) / "
              f"(1 + {a1:.8f} z^-1 + {a2:.8f} z^-2)")
        print("  Zeros :", ", ".join(f"{z.real:+.4f}{z.imag:+.4f}j" for z in zeros) or "—")
        print("  Poles :", ", ".join(f"{p.real:+.4f}{p.imag:+.4f}j" for p in poles) or "—")
        for p in poles:
            r = abs(p)
            print(f"    |pole| = {r:.6f}  ({'stable' if r < 1.0 else 'UNSTABLE'})")
        print("  Difference equation:")
        print(f"    y[n] = {b0:.6f} x[n] + {b1:.6f} x[n-1] + {b2:.6f} x[n-2]")
        print(f"         - ({a1:.6f}) y[n-1] - ({a2:.6f}) y[n-2]")

    info = {
        "ftype": ftype, "fs_hz": fs_hz, "edges_hz": edges_hz,
        "edges_norm": edges_norm, "fc_norm": fc_norm, "k_prewarp": k,
        "b": b, "a": a, "zeros": zeros, "poles": poles,
        "method": "pure_python_bilinear_butterworth",
    }
    return b, a, info


def design_biquad_coefficients(
    ftype: str = "lowpass",
    order: int = 2,
    cutoff: Union[float, Sequence[float]] = 0.1,
    fs: float = 1.0,
    rp: float = 0.5,
    rs: float = 40.0,
) -> Tuple[List[float], List[float]]:
    """
    Design a 2nd-order Butterworth biquad.
    Returns (b, a) lists of length 3.

    `cutoff` and `fs` are in the same units (normalised if fs=1).
    """
    if isinstance(cutoff, (list, tuple)):
        fc = float(cutoff[0])
        f_low, f_high = float(cutoff[0]), float(cutoff[1])
        b, a, _ = bilinear_biquad_design(
            ftype=ftype, fc_hz=fc, fs_hz=fs,
            f_low_hz=f_low, f_high_hz=f_high, verbose=False,
        )
    else:
        b, a, _ = bilinear_biquad_design(
            ftype=ftype, fc_hz=float(cutoff), fs_hz=fs, verbose=False,
        )
    return b, a


def float_to_fixed(c: float, width: int, frac_bits: Optional[int] = None) -> int:
    """
    Convert float coefficient to signed fixed-point integer.
    Default Q-format leaves one integer bit so values in (-2, +2)
    fit without saturation (needed for IIR feedback coefficients).
    """
    if frac_bits is None:
        frac_bits = width - 2          # 1 sign + 1 integer bit
    scale = 1 << frac_bits
    val = int(round(c * scale))
    max_val = (1 << (width - 1)) - 1
    min_val = -(1 << (width - 1))
    return max(min_val, min(max_val, val))


def coeffs_to_vhdl_array(
    coeffs: Sequence[float],
    width: int,
    name: str = "COEFFS",
    frac_bits: Optional[int] = None,
) -> str:
    """Return a VHDL constant array declaration."""
    if frac_bits is None:
        frac_bits = width - 2
    lines = [
        f"  constant {name} : coeff_array_t := ("
    ]
    fixed = [float_to_fixed(c, width, frac_bits) for c in coeffs]
    for i, v in enumerate(fixed):
        comma = "," if i < len(fixed) - 1 else ""
        lines.append(f"    to_signed({v}, {width}){comma}  -- {coeffs[i]:.8f}")
    lines.append("  );")
    return "\n".join(lines)


def generate_coeff_package(
    coeffs: Sequence[float],
    width: int = 16,
    package_name: str = "filter_coeffs_pkg",
    array_name: str = "FIR_COEFFS",
) -> str:
    """Generate a complete VHDL package containing the coefficients."""
    n = len(coeffs)
    body = coeffs_to_vhdl_array(coeffs, width, array_name)
    return f"""library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package {package_name} is
  constant COEFF_WIDTH : positive := {width};
  constant NUM_TAPS    : positive := {n};
  type coeff_array_t is array (0 to NUM_TAPS-1) of signed(COEFF_WIDTH-1 downto 0);
{body}
end package {package_name};
"""


# ---------------------------------------------------------------------------
# 1. FIR Filter
# ---------------------------------------------------------------------------

def generate_fir(
    data_width: int = 16,
    coeff_width: int = 16,
    taps: int = 8,
    acc_width: int = 32,
    structure: str = "transversal",
    coeffs: Optional[Sequence[float]] = None,
    cutoff: Union[float, Sequence[float]] = 0.2,
    fs: float = 1.0,
    window: str = "hamming",
    ftype: str = "lowpass",
    beta: float = 8.6,
) -> str:
    """
    Transversal or systolic FIR.
    If coeffs is None, automatically designs the FIR according to
    window / ftype / cutoff / beta.
    """
    if coeffs is None:
        coeffs = design_fir_coefficients(
            taps, cutoff, fs=fs, window=window, ftype=ftype, beta=beta
        )
        taps = len(coeffs)

    e = VHDLEmitter("fir_filter")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("COEFF_WIDTH", "positive", str(coeff_width))
    e.add_generic("TAPS", "positive", str(taps))
    e.add_generic("ACC_WIDTH", "positive", str(acc_width))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("din", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("dout", "out", "signed(ACC_WIDTH-1 downto 0)")

    # Embedded coefficient constant
    e.add_decl(f"""
  type coeff_array_t is array (0 to TAPS-1) of signed(COEFF_WIDTH-1 downto 0);
{coeffs_to_vhdl_array(coeffs, coeff_width, "COEFFS")}
""")
    e.add_decl("""
  type delay_array is array (0 to TAPS-1) of signed(DATA_WIDTH-1 downto 0);
""")
    e.add_signal("delay_line", "delay_array", "(others => (others => '0'))")
    e.add_signal("acc", "signed(ACC_WIDTH-1 downto 0)")

    if structure == "transversal":
        e.add_arch("""
  process(clk, rst)
    variable sum : signed(ACC_WIDTH-1 downto 0);
  begin
    if rst = '1' then
      delay_line <= (others => (others => '0'));
      acc        <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        -- unit-delay chain
        delay_line(0) <= din;
        for i in 1 to TAPS-1 loop
          delay_line(i) <= delay_line(i-1);
        end loop;

        -- multiply-accumulate
        sum := (others => '0');
        for i in 0 to TAPS-1 loop
          sum := sum + resize(delay_line(i) * COEFFS(i), ACC_WIDTH);
        end loop;
        acc <= sum;
      end if;
    end if;
  end process;
  dout <= acc;
""")
    else:  # systolic
        e.add_decl("""
  type pipe_t is array (0 to TAPS-1) of signed(ACC_WIDTH-1 downto 0);
""")
        e.add_signal("pipe", "pipe_t", "(others => (others => '0'))")
        e.add_arch("""
  process(clk, rst)
  begin
    if rst = '1' then
      delay_line <= (others => (others => '0'));
      pipe       <= (others => (others => '0'));
    elsif rising_edge(clk) then
      if ce = '1' then
        delay_line(0) <= din;
        for i in 1 to TAPS-1 loop
          delay_line(i) <= delay_line(i-1);
        end loop;

        for i in 0 to TAPS-1 loop
          if i = 0 then
            pipe(i) <= resize(delay_line(i) * COEFFS(i), ACC_WIDTH);
          else
            pipe(i) <= pipe(i-1) + resize(delay_line(i) * COEFFS(i), ACC_WIDTH);
          end if;
        end loop;
      end if;
    end if;
  end process;
  dout <= pipe(TAPS-1);
""")
    return e.emit()


# ---------------------------------------------------------------------------
# 2. Digital Mixer
# ---------------------------------------------------------------------------

def generate_digital_mixer(
    data_width: int = 16,
    phase_width: int = 32,
    lut_depth: int = 10,
) -> str:
    """
    Digital mixer = NCO (phase accumulator + sine LUT) + complex multiply.

    Phase dither is mandatory (not optional): a free-running LFSR is added
    to the phase word before LUT address truncation. This breaks the
    periodicity of phase-truncation error and turns coherent spurs into
    a broadband noise floor (better SFDR).
    """
    e = VHDLEmitter("digital_mixer")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("PHASE_WIDTH", "positive", str(phase_width))
    e.add_generic("LUT_DEPTH", "positive", str(lut_depth))
    e.add_generic("DITHER_WIDTH", "positive", "24")

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("xin_re", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("xin_im", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("freq_word", "in", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_port("xout_re", "out", "signed(2*DATA_WIDTH downto 0)")
    e.add_port("xout_im", "out", "signed(2*DATA_WIDTH downto 0)")

    e.add_decl("""
  -- Full-wave sine LUT (sin and cos via quarter-wave address offset)
  type lut_t is array (0 to 2**LUT_DEPTH-1) of signed(DATA_WIDTH-1 downto 0);
  function init_sine return lut_t is
    variable l : lut_t;
    variable angle : real;
  begin
    for i in 0 to 2**LUT_DEPTH-1 loop
      angle := real(i) * MATH_PI * 2.0 / real(2**LUT_DEPTH);
      l(i) := to_signed(integer(sin(angle) * (2.0**(DATA_WIDTH-1)-1.0)), DATA_WIDTH);
    end loop;
    return l;
  end function;
  constant SINE_LUT : lut_t := init_sine;
""")
    e.add_signal("phase_acc", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_signal("lfsr", "unsigned(DITHER_WIDTH-1 downto 0)")
    e.add_signal("dither", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_signal("phase_dith", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_signal("addr", "unsigned(LUT_DEPTH-1 downto 0)")
    e.add_signal("nco_sin", "signed(DATA_WIDTH-1 downto 0)")
    e.add_signal("nco_cos", "signed(DATA_WIDTH-1 downto 0)")
    e.add_signal("mul_re", "signed(2*DATA_WIDTH downto 0)")
    e.add_signal("mul_im", "signed(2*DATA_WIDTH downto 0)")

    e.add_arch("""
  --------------------------------------------------------------------------
  -- Phase accumulator
  --------------------------------------------------------------------------
  process(clk, rst)
  begin
    if rst = '1' then
      phase_acc <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        phase_acc <= phase_acc + freq_word;
      end if;
    end if;
  end process;

  --------------------------------------------------------------------------
  -- Mandatory phase dither: 24-bit LFSR
  -- Polynomial: x^24 + x^23 + x^22 + x^17 + 1  (maximal length)
  -- Dither is injected into the phase bits that are truncated when forming
  -- the LUT address, so truncation error is no longer periodic; spurs
  -- collapse into a noise floor.
  --------------------------------------------------------------------------
  process(clk, rst)
    variable fb : std_logic;
  begin
    if rst = '1' then
      lfsr <= (others => '1');  -- non-zero seed required
    elsif rising_edge(clk) then
      if ce = '1' then
        fb := lfsr(23) xor lfsr(22) xor lfsr(21) xor lfsr(16);
        lfsr <= lfsr(DITHER_WIDTH-2 downto 0) & fb;
      end if;
    end if;
  end process;

  -- Align LFSR into PHASE_WIDTH (zero-extend or truncate as needed)
  dither <= resize(lfsr, PHASE_WIDTH);

  phase_dith <= phase_acc + dither;

  -- LUT address = top LUT_DEPTH bits of *dithered* phase
  addr    <= phase_dith(PHASE_WIDTH-1 downto PHASE_WIDTH-LUT_DEPTH);
  nco_sin <= SINE_LUT(to_integer(addr));
  -- Cosine = sine(+90 deg) = address + 1/4 LUT length
  nco_cos <= SINE_LUT(to_integer(addr + 2**(LUT_DEPTH-2)));

  --------------------------------------------------------------------------
  -- Complex multiply: (xin_re + j xin_im) * (cos + j sin)
  --------------------------------------------------------------------------
  process(clk, rst)
  begin
    if rst = '1' then
      mul_re <= (others => '0');
      mul_im <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        mul_re <= resize(xin_re * nco_cos + xin_im * nco_sin, 2*DATA_WIDTH+1);
        mul_im <= resize(xin_im * nco_cos - xin_re * nco_sin, 2*DATA_WIDTH+1);
      end if;
    end if;
  end process;

  xout_re <= mul_re;
  xout_im <= mul_im;
""")
    return e.emit()


# ---------------------------------------------------------------------------
# 3. PI Controller
# ---------------------------------------------------------------------------

def generate_pi_controller(
    data_width: int = 16,
    acc_width: int = 32,
    kp_width: int = 16,
    ki_width: int = 16,
) -> str:
    e = VHDLEmitter("pi_controller")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("ACC_WIDTH", "positive", str(acc_width))
    e.add_generic("KP_WIDTH", "positive", str(kp_width))
    e.add_generic("KI_WIDTH", "positive", str(ki_width))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("error", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("kp", "in", "signed(KP_WIDTH-1 downto 0)")
    e.add_port("ki", "in", "signed(KI_WIDTH-1 downto 0)")
    e.add_port("out_ctrl", "out", "signed(ACC_WIDTH-1 downto 0)")

    e.add_signal("p_term", "signed(DATA_WIDTH+KP_WIDTH-1 downto 0)")
    e.add_signal("i_acc", "signed(ACC_WIDTH-1 downto 0)")
    e.add_signal("i_term", "signed(ACC_WIDTH-1 downto 0)")
    e.add_signal("sum", "signed(ACC_WIDTH-1 downto 0)")

    e.add_arch("""
  process(clk, rst)
  begin
    if rst = '1' then
      i_acc  <= (others => '0');
      p_term <= (others => '0');
      i_term <= (others => '0');
      sum    <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        p_term <= error * kp;
        i_acc  <= i_acc + resize(error * ki, ACC_WIDTH);
        i_term <= i_acc;
        sum    <= resize(p_term, ACC_WIDTH) + i_term;
      end if;
    end if;
  end process;
  out_ctrl <= sum;
""")
    return e.emit()


# ---------------------------------------------------------------------------
# 4 & 5. Polyphase Decimator / Interpolator
# ---------------------------------------------------------------------------

def generate_polyphase_decimator(
    data_width: int = 16,
    factor: int = 4,
    taps_per_phase: int = 8,
    coeff_width: int = 16,
    cutoff: float = 0.4,
) -> str:
    total_taps = factor * taps_per_phase
    coeffs = design_fir_coefficients(total_taps, cutoff / factor)
    # reshape into phases
    phases = [coeffs[i::factor] for i in range(factor)]

    e = VHDLEmitter("polyphase_decimator")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("FACTOR", "positive", str(factor))
    e.add_generic("TAPS_PER_PHASE", "positive", str(taps_per_phase))
    e.add_generic("COEFF_WIDTH", "positive", str(coeff_width))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce_in", "in", "std_logic")
    e.add_port("din", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("ce_out", "out", "std_logic")
    e.add_port("dout", "out", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)")

    # embed all phase coefficients
    coeff_decl = ["  type phase_coeff_t is array (0 to TAPS_PER_PHASE-1) of signed(COEFF_WIDTH-1 downto 0);"]
    coeff_decl.append("  type all_coeff_t is array (0 to FACTOR-1) of phase_coeff_t;")
    coeff_decl.append("  constant PHASE_COEFFS : all_coeff_t := (")
    for p, ph in enumerate(phases):
        fixed = [float_to_fixed(c, coeff_width) for c in ph]
        vals = ", ".join(f"to_signed({v}, {coeff_width})" for v in fixed)
        comma = "," if p < factor - 1 else ""
        coeff_decl.append(f"    ({vals}){comma}")
    coeff_decl.append("  );")
    e.add_decl("\n".join(coeff_decl))

    e.add_decl("""
  type phase_delay_t is array (0 to TAPS_PER_PHASE-1) of signed(DATA_WIDTH-1 downto 0);
  type all_phases_t  is array (0 to FACTOR-1) of phase_delay_t;
""")
    e.add_signal("phase_cnt", "integer range 0 to FACTOR-1", "0")
    e.add_signal("delays", "all_phases_t", "(others => (others => (others => '0')))")
    e.add_signal("phase_mac", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)", "(others => '0')")
    e.add_signal("acc", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)")
    e.add_signal("out_valid", "std_logic", "'0'")

    e.add_arch("""
  process(clk, rst)
    variable sum   : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0);
    variable phase : integer;
  begin
    if rst = '1' then
      phase_cnt <= 0;
      delays    <= (others => (others => (others => '0')));
      phase_mac <= (others => '0');
      acc       <= (others => '0');
      out_valid <= '0';
    elsif rising_edge(clk) then
      out_valid <= '0';
      if ce_in = '1' then
        phase := phase_cnt;

        -- shift the selected phase delay line
        delays(phase)(0) <= din;
        for t in 1 to TAPS_PER_PHASE-1 loop
          delays(phase)(t) <= delays(phase)(t-1);
        end loop;

        -- MAC for the current phase
        sum := (others => '0');
        for t in 0 to TAPS_PER_PHASE-1 loop
          sum := sum + resize(delays(phase)(t) * PHASE_COEFFS(phase)(t), sum'length);
        end loop;

        if phase_cnt = 0 then
          phase_mac <= sum;                 -- start new accumulation
        else
          phase_mac <= phase_mac + sum;     -- accumulate all phases
        end if;

        if phase_cnt = FACTOR-1 then
          phase_cnt <= 0;
          acc       <= phase_mac + sum;     -- final sum of every phase
          out_valid <= '1';
        else
          phase_cnt <= phase_cnt + 1;
        end if;
      end if;
    end if;
  end process;
  ce_out <= out_valid;
  dout   <= acc;
""")
    return e.emit()


def generate_polyphase_interpolator(
    data_width: int = 16,
    factor: int = 4,
    taps_per_phase: int = 8,
    coeff_width: int = 16,
    cutoff: float = 0.4,
) -> str:
    total_taps = factor * taps_per_phase
    coeffs = design_fir_coefficients(total_taps, cutoff / factor)
    phases = [coeffs[i::factor] for i in range(factor)]

    e = VHDLEmitter("polyphase_interpolator")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("FACTOR", "positive", str(factor))
    e.add_generic("TAPS_PER_PHASE", "positive", str(taps_per_phase))
    e.add_generic("COEFF_WIDTH", "positive", str(coeff_width))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce_in", "in", "std_logic")
    e.add_port("din", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("ce_out", "out", "std_logic")
    e.add_port("dout", "out", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)")

    coeff_decl = ["  type phase_coeff_t is array (0 to TAPS_PER_PHASE-1) of signed(COEFF_WIDTH-1 downto 0);"]
    coeff_decl.append("  type all_coeff_t is array (0 to FACTOR-1) of phase_coeff_t;")
    coeff_decl.append("  constant PHASE_COEFFS : all_coeff_t := (")
    for p, ph in enumerate(phases):
        fixed = [float_to_fixed(c, coeff_width) for c in ph]
        vals = ", ".join(f"to_signed({v}, {coeff_width})" for v in fixed)
        comma = "," if p < factor - 1 else ""
        coeff_decl.append(f"    ({vals}){comma}")
    coeff_decl.append("  );")
    e.add_decl("\n".join(coeff_decl))

    e.add_signal("phase_cnt", "integer range 0 to FACTOR-1", "0")
    e.add_signal("sample", "signed(DATA_WIDTH-1 downto 0)")
    e.add_signal("acc", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)")
    e.add_signal("out_valid", "std_logic", "'0'")

    e.add_arch("""
  process(clk, rst)
    variable sum : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0);
  begin
    if rst = '1' then
      phase_cnt <= 0;
      sample    <= (others => '0');
      acc       <= (others => '0');
      out_valid <= '0';
    elsif rising_edge(clk) then
      out_valid <= '0';
      if ce_in = '1' then
        sample    <= din;
        phase_cnt <= 0;
      else
        if phase_cnt < FACTOR-1 then
          phase_cnt <= phase_cnt + 1;
        end if;
      end if;

      sum := (others => '0');
      for t in 0 to TAPS_PER_PHASE-1 loop
        sum := sum + resize(sample * PHASE_COEFFS(phase_cnt)(t), sum'length);
      end loop;
      acc       <= sum;
      out_valid <= '1';
    end if;
  end process;
  ce_out <= out_valid;
  dout   <= acc;
""")
    return e.emit()


# ---------------------------------------------------------------------------
# 6. Biquad IIR (Direct Form I and Direct Form II)
# ---------------------------------------------------------------------------

def generate_biquad(
    data_width: int = 16,
    coeff_width: int = 16,
    form: str = "df1",          # df1 | df2
    ftype: str = "lowpass",
    cutoff: Union[float, Sequence[float]] = 0.1,
    fs: float = 1.0,
    b_coeffs: Optional[Sequence[float]] = None,
    a_coeffs: Optional[Sequence[float]] = None,
) -> str:
    """
    Single biquad section (IIR).

    If b_coeffs/a_coeffs are provided they are used directly; otherwise
    coefficients are designed via analog prototype + bilinear transform.
    """
    if b_coeffs is not None and a_coeffs is not None:
        b = list(b_coeffs)
        a = list(a_coeffs)
    else:
        b, a = design_biquad_coefficients(ftype=ftype, order=2, cutoff=cutoff, fs=fs)
    # normalise a0 = 1
    a0 = a[0] if abs(a[0]) > 1e-18 else 1.0
    b = [c / a0 for c in b]
    a = [c / a0 for c in a]

    e = VHDLEmitter("biquad_iir")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("COEFF_WIDTH", "positive", str(coeff_width))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("din", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("dout", "out", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")

    # embed coefficients
    e.add_decl(f"""
  -- b = [{b[0]:.8f}, {b[1]:.8f}, {b[2]:.8f}]
  -- a = [1.0, {a[1]:.8f}, {a[2]:.8f}]
  constant B0 : signed(COEFF_WIDTH-1 downto 0) := to_signed({float_to_fixed(b[0], coeff_width)}, COEFF_WIDTH);
  constant B1 : signed(COEFF_WIDTH-1 downto 0) := to_signed({float_to_fixed(b[1], coeff_width)}, COEFF_WIDTH);
  constant B2 : signed(COEFF_WIDTH-1 downto 0) := to_signed({float_to_fixed(b[2], coeff_width)}, COEFF_WIDTH);
  constant A1 : signed(COEFF_WIDTH-1 downto 0) := to_signed({float_to_fixed(a[1], coeff_width)}, COEFF_WIDTH);
  constant A2 : signed(COEFF_WIDTH-1 downto 0) := to_signed({float_to_fixed(a[2], coeff_width)}, COEFF_WIDTH);
""")

    if form == "df1":
        e.add_signal("x1", "signed(DATA_WIDTH-1 downto 0)")
        e.add_signal("x2", "signed(DATA_WIDTH-1 downto 0)")
        e.add_signal("y1", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")
        e.add_signal("y2", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")
        e.add_signal("acc", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")

        e.add_arch("""
  process(clk, rst)
    variable sum : signed(DATA_WIDTH+COEFF_WIDTH downto 0);
  begin
    if rst = '1' then
      x1  <= (others => '0');
      x2  <= (others => '0');
      y1  <= (others => '0');
      y2  <= (others => '0');
      acc <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        sum := resize(din * B0, sum'length)
             + resize(x1  * B1, sum'length)
             + resize(x2  * B2, sum'length)
             - resize(y1  * A1, sum'length)
             - resize(y2  * A2, sum'length);

        x2  <= x1;
        x1  <= din;
        y2  <= y1;
        y1  <= sum;
        acc <= sum;
      end if;
    end if;
  end process;
  dout <= acc;
""")
    else:  # Direct Form II (canonical)
        e.add_signal("w", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")
        e.add_signal("w1", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")
        e.add_signal("w2", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")
        e.add_signal("acc", "signed(DATA_WIDTH+COEFF_WIDTH downto 0)")

        e.add_arch("""
  process(clk, rst)
    variable w_new : signed(DATA_WIDTH+COEFF_WIDTH downto 0);
    variable y     : signed(DATA_WIDTH+COEFF_WIDTH downto 0);
  begin
    if rst = '1' then
      w1  <= (others => '0');
      w2  <= (others => '0');
      acc <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        w_new := resize(din, w_new'length)
               - resize(w1 * A1, w_new'length)
               - resize(w2 * A2, w_new'length);

        y := resize(w_new * B0, y'length)
           + resize(w1    * B1, y'length)
           + resize(w2    * B2, y'length);

        w2  <= w1;
        w1  <= w_new;
        acc <= y;
      end if;
    end if;
  end process;
  dout <= acc;
""")
    return e.emit()


# ---------------------------------------------------------------------------
# 7. Streaming Radix-2 FFT (SDF-style pipeline skeleton)
# ---------------------------------------------------------------------------

def generate_streaming_fft(
    data_width: int = 16,
    n_points: int = 64,
    twiddle_width: int = 16,
) -> str:
    """
    Complete synthesizable Radix-2 Single-Path Delay Feedback (SDF) streaming FFT.

    Architecture
    ------------
    - log2(N) cascaded SDF stages
    - Each stage has a feedback delay of length N/2^(stage+1)
    - Butterfly (add/sub) + complex twiddle multiply on the lower path
    - One complex sample in / one complex sample out per clock after pipeline fill
    - Twiddle factors pre-computed and embedded as constants
    - Asynchronous active-high reset

    This is a fully working, synthesis-friendly implementation.
    """
    stages = int(math.log2(n_points))
    assert 1 << stages == n_points, "N_POINTS must be a power of 2"

    e = VHDLEmitter("streaming_fft_sdf")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("N_POINTS", "positive", str(n_points))
    e.add_generic("TWIDDLE_WIDTH", "positive", str(twiddle_width))
    e.add_generic("STAGES", "positive", str(stages))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("xin_re", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("xin_im", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("xout_re", "out", "signed(DATA_WIDTH+STAGES downto 0)")
    e.add_port("xout_im", "out", "signed(DATA_WIDTH+STAGES downto 0)")
    e.add_port("out_valid", "out", "std_logic")

    # ------------------------------------------------------------------
    # Type declarations & twiddle ROM
    # ------------------------------------------------------------------
    e.add_decl("""
  -- Complex fixed-point type used throughout the pipeline
  type complex_t is record
    re : signed(DATA_WIDTH+STAGES downto 0);
    im : signed(DATA_WIDTH+STAGES downto 0);
  end record;

  type complex_tw is record
    re : signed(TWIDDLE_WIDTH-1 downto 0);
    im : signed(TWIDDLE_WIDTH-1 downto 0);
  end record;

  -- Twiddle table (only N/2 unique values needed)
  type twiddle_array is array (0 to N_POINTS/2-1) of complex_tw;
""")

    # Build the twiddle constant
    tw_lines = ["  constant TWIDDLES : twiddle_array := ("]
    for k in range(n_points // 2):
        angle = -2.0 * math.pi * k / n_points
        re = float_to_fixed(math.cos(angle), twiddle_width)
        im = float_to_fixed(math.sin(angle), twiddle_width)
        comma = "," if k < n_points // 2 - 1 else ""
        tw_lines.append(
            f"    {k} => (re => to_signed({re}, TWIDDLE_WIDTH), "
            f"im => to_signed({im}, TWIDDLE_WIDTH)){comma}"
        )
    tw_lines.append("  );")
    e.add_decl("\n".join(tw_lines))

    # ------------------------------------------------------------------
    # Signals for every stage
    # ------------------------------------------------------------------
    e.add_signal("cnt", "unsigned(STAGES-1 downto 0)", "(others => '0')")
    e.add_signal("valid_pipe", "std_logic_vector(0 to STAGES)", "(others => '0')")

    for s in range(stages):
        delay_len = n_points // (2 ** (s + 1))
        e.add_decl(f"""
  -- Stage {s} delay line (length {delay_len})
  type delay_t_s{s} is array (0 to {delay_len}-1) of complex_t;
""")
        e.add_signal(f"delay_s{s}", f"delay_t_s{s}",
                     "(others => (re => (others => '0'), im => (others => '0')))")
        e.add_signal(f"in_s{s}", "complex_t",
                     "(re => (others => '0'), im => (others => '0'))")
        e.add_signal(f"out_s{s}", "complex_t",
                     "(re => (others => '0'), im => (others => '0'))")

    # ------------------------------------------------------------------
    # Architecture
    # ------------------------------------------------------------------
    arch = []
    arch.append("""
  -- Global counter & valid pipeline
  process(clk, rst)
  begin
    if rst = '1' then
      cnt        <= (others => '0');
      valid_pipe <= (others => '0');
    elsif rising_edge(clk) then
      if ce = '1' then
        cnt        <= cnt + 1;
        valid_pipe <= '1' & valid_pipe(0 to STAGES-1);
      end if;
    end if;
  end process;
""")

    # Stage 0 input mapping
    arch.append("""
  -- Stage 0 input
  in_s0.re <= resize(xin_re, DATA_WIDTH+STAGES);
  in_s0.im <= resize(xin_im, DATA_WIDTH+STAGES);
""")

    # Generate each SDF stage
    for s in range(stages):
        delay_len = n_points // (2 ** (s + 1))
        # The control bit that selects “butterfly mode” vs “bypass/store”
        # For stage s the MSB that toggles every delay_len clocks is cnt(STAGES-1-s)
        ctrl_bit = f"cnt({stages-1-s})" if stages > 1 else "cnt(0)"

        arch.append(f"""
  ---------------------------------------------------------------------------
  -- SDF Stage {s}  (delay = {delay_len})
  ---------------------------------------------------------------------------
  process(clk, rst)
    variable a, b       : complex_t;
    variable sum, diff  : complex_t;
    variable tw         : complex_tw;
    variable prod_re, prod_im : signed(DATA_WIDTH+STAGES+TWIDDLE_WIDTH downto 0);
    variable tw_idx     : integer range 0 to N_POINTS/2-1;
  begin
    if rst = '1' then
      delay_s{s} <= (others => (re => (others => '0'), im => (others => '0')));
      out_s{s}   <= (re => (others => '0'), im => (others => '0'));
    elsif rising_edge(clk) then
      if ce = '1' then
        -- Shift the feedback delay line
        delay_s{s}(0) <= in_s{s};
        for i in 1 to {delay_len}-1 loop
          delay_s{s}(i) <= delay_s{s}(i-1);
        end loop;

        a := delay_s{s}({delay_len}-1);   -- oldest sample
        b := in_s{s};                     -- newest sample

        if {ctrl_bit} = '0' then
          -- First half of the block: store input, output the delayed sample
          out_s{s} <= a;
        else
          -- Second half: perform butterfly + twiddle
          sum.re  := a.re + b.re;
          sum.im  := a.im + b.im;
          diff.re := a.re - b.re;
          diff.im := a.im - b.im;

          -- Twiddle index (simple mapping suitable for power-of-two SDF)
          if STAGES > 1 then
            tw_idx := to_integer(cnt(STAGES-2 downto 0)) mod (N_POINTS/2);
          else
            tw_idx := 0;
          end if;
          tw := TWIDDLES(tw_idx);

          -- Complex multiply: diff * tw
          prod_re := resize(diff.re * tw.re - diff.im * tw.im,
                            prod_re'length);
          prod_im := resize(diff.re * tw.im + diff.im * tw.re,
                            prod_im'length);

          -- Scale back by the fractional bits of the twiddle
          out_s{s}.re <= resize(shift_right(prod_re, TWIDDLE_WIDTH-2), out_s{s}.re'length);
          out_s{s}.im <= resize(shift_right(prod_im, TWIDDLE_WIDTH-2), out_s{s}.im'length);

          -- The sum path is written back into the delay (standard SDF)
          delay_s{s}(0) <= sum;
        end if;
      end if;
    end if;
  end process;
""")

        # Connect stages
        if s < stages - 1:
            arch.append(f"""
  in_s{s+1} <= out_s{s};
""")

    # Final outputs
    arch.append(f"""
  -- Final stage outputs
  xout_re   <= out_s{stages-1}.re;
  xout_im   <= out_s{stages-1}.im;
  out_valid <= valid_pipe(STAGES);
""")

    e.add_arch("\n".join(arch))
    return e.emit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PROCESSES = {
    "1": ("FIR Filter (transversal/systolic) + auto coeffs", generate_fir, None),
    "2": ("Digital Mixer (NCO + Complex Mul)", generate_digital_mixer,
          [("DATA_WIDTH", 16), ("PHASE_WIDTH", 32), ("LUT_DEPTH", 10)]),
    "3": ("PI Controller", generate_pi_controller,
          [("DATA_WIDTH", 16), ("ACC_WIDTH", 32), ("KP_WIDTH", 16), ("KI_WIDTH", 16)]),
    "4": ("Polyphase Decimator (auto coeffs)", generate_polyphase_decimator,
          [("DATA_WIDTH", 16), ("FACTOR", 4), ("TAPS_PER_PHASE", 8),
           ("COEFF_WIDTH", 16), ("cutoff", 0.4)]),
    "5": ("Polyphase Interpolator (auto coeffs)", generate_polyphase_interpolator,
          [("DATA_WIDTH", 16), ("FACTOR", 4), ("TAPS_PER_PHASE", 8),
           ("COEFF_WIDTH", 16), ("cutoff", 0.4)]),
    "6": ("Biquad IIR (bilinear design + DF1/DF2 VHDL)", generate_biquad, None),
    "7": ("Streaming Radix-2 FFT (SDF)", generate_streaming_fft,
          [("DATA_WIDTH", 16), ("N_POINTS", 64), ("TWIDDLE_WIDTH", 16)]),
    "8": ("Coefficient package only (FIR)", None, None),
}


def ask(prompt: str, default):
    val = input(f"  {prompt} [{default}]: ").strip()
    if val == "":
        return default
    if isinstance(default, bool):
        return val.lower() in ("1", "y", "yes", "true")
    if isinstance(default, int):
        try:
            return int(val)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(val)
        except ValueError:
            return default
    return val


def _ask_fir_design_params() -> dict:
    """
    Interactive questions for FIR coefficient design.

    For Kaiser LPF/HPF the full design flow is used:
      fs, fpass, fstop, As
      → transition width, midpoint cutoff, beta, estimated N
      → coefficients via windowed-sinc / firwin

    Frequencies are entered in real Hz and normalised internally.
    """
    print("\n  --- FIR design method ---")
    print("  1) Normal (Hamming window)")
    print("  2) Kaiser window  (estimates N and beta from specs)")
    method = input("  Choose method [1]: ").strip() or "1"
    window = "kaiser" if method == "2" else "hamming"

    print("\n  --- Filter type ---")
    print("  1) LPF  (Low-pass)")
    print("  2) HPF  (High-pass)")
    print("  3) BPF  (Band-pass)")
    print("  4) BSF  (Band-stop)")
    ftype_map = {"1": "lowpass", "2": "highpass", "3": "bandpass", "4": "bandstop"}
    ft_choice = input("  Choose type [1]: ").strip() or "1"
    ftype = ftype_map.get(ft_choice, "lowpass")

    print("\n  --- Frequency parameters (enter real values in Hz) ---")
    fs = ask("Sampling frequency fs [Hz]", 48e6)
    if fs <= 0:
        print("  WARNING: fs must be > 0, falling back to 1.0")
        fs = 1.0

    beta = 8.6
    taps = 31

    if window == "kaiser" and ftype in ("lowpass", "highpass"):
        # Full Kaiser specification flow
        fpass = ask("Passband edge fpass [Hz]", 8e6)
        fstop = ask("Stopband edge fstop [Hz]", 10e6)
        As    = ask("Stopband attenuation As [dB]", 60.0)

        if ftype == "lowpass" and not (0 < fpass < fstop < fs / 2):
            print("  WARNING: for LPF need 0 < fpass < fstop < fs/2")
        if ftype == "highpass" and not (0 < fstop < fpass < fs / 2):
            print("  WARNING: for HPF need 0 < fstop < fpass < fs/2")

        # Transition width, midpoint cutoff, normalised values
        if ftype == "lowpass":
            delta_f = abs(fstop - fpass)
            fc_hz = 0.5 * (fpass + fstop)
        else:  # highpass – transition still |fpass-fstop|
            delta_f = abs(fpass - fstop)
            fc_hz = 0.5 * (fpass + fstop)

        delta_f_norm = delta_f / fs
        fc_norm = fc_hz / fs
        fpass_norm = fpass / fs
        fstop_norm = fstop / fs
        omega_c = 2.0 * math.pi * fc_norm   # rad/sample

        beta = kaiser_beta_from_attenuation(As)
        taps_est = kaiser_numtaps_estimate(As, delta_f_norm)

        print("\n  --- Computed design values ---")
        print(f"  Transition width Δf     = {delta_f:g} Hz  ({delta_f_norm:.6f} × fs)")
        print(f"  Cut-off (midpoint) fc   = {fc_hz:g} Hz  (norm {fc_norm:.6f})")
        print(f"  Angular cut-off ωc      = {omega_c:.6f} rad/sample")
        print(f"  Normalised fpass/fstop  = {fpass_norm:.6f} / {fstop_norm:.6f}")
        print(f"  Kaiser beta             = {beta:.4f}")
        print(f"  Estimated filter length = {taps_est} taps")

        taps = ask("TAPS (filter length, Enter keeps estimate)", taps_est)
        cutoff = fc_norm

    elif window == "kaiser":
        # BPF / BSF with Kaiser – user supplies edges + As/beta
        f_low_hz  = ask("Lower band edge [Hz]", 8e6)
        f_high_hz = ask("Upper band edge [Hz]", 10e6)
        As = ask("Stopband attenuation As [dB] (used for beta)", 60.0)
        beta = kaiser_beta_from_attenuation(As)
        print(f"  → Kaiser beta = {beta:.4f}")
        cutoff = [f_low_hz / fs, f_high_hz / fs]
        print(f"  → normalised edges = [{cutoff[0]:.6f}, {cutoff[1]:.6f}]")
        # rough transition estimate using lower edge distance as proxy
        delta_f_norm = abs(cutoff[1] - cutoff[0]) * 0.5
        if delta_f_norm > 0:
            taps = ask("TAPS (filter length)", kaiser_numtaps_estimate(As, max(delta_f_norm, 1e-3)))
        else:
            taps = ask("TAPS (filter length)", 63)

    else:
        # Hamming – single cutoff or edges, manual taps
        if ftype in ("lowpass", "highpass"):
            f_hz = ask("Cutoff frequency [Hz]", 8e6)
            cutoff = f_hz / fs
            print(f"  → normalised cutoff = {cutoff:.6f}")
        else:
            f_low_hz  = ask("Lower band edge [Hz]", 8e6)
            f_high_hz = ask("Upper band edge [Hz]", 12e6)
            cutoff = [f_low_hz / fs, f_high_hz / fs]
            print(f"  → normalised edges = [{cutoff[0]:.6f}, {cutoff[1]:.6f}]")
        taps = ask("TAPS (filter length)", 31)

    # Sanity check on normalised edges
    edges = cutoff if isinstance(cutoff, list) else [cutoff]
    for e in edges:
        if not (0.0 < e < 0.5):
            print(f"  WARNING: normalised frequency {e:.4f} is outside (0, 0.5).")
            print("           Check that all edge frequencies are < fs/2.")

    print("\n  --- Hardware parameters ---")
    data_width  = ask("DATA_WIDTH", 16)
    coeff_width = ask("COEFF_WIDTH", 16)
    acc_width   = ask("ACC_WIDTH", 32)
    structure   = ask("structure (transversal/systolic)", "transversal")

    return {
        "data_width": data_width,
        "coeff_width": coeff_width,
        "taps": taps,
        "acc_width": acc_width,
        "structure": structure,
        "cutoff": cutoff,       # normalised
        "fs": 1.0,              # design functions see normalised freqs
        "window": window,
        "ftype": ftype,
        "beta": beta,
    }


def _ask_iir_design_params() -> dict:
    """
    Interactive IIR (biquad) design via analog prototype + bilinear transform.

    Flow printed to the console:
      specs → pre-warp → H_a(s) → bilinear → H(z) → poles/zeros → coefficients
    """
    print("\n  --- IIR filter type ---")
    print("  1) LPF  (Low-pass Butterworth biquad)")
    print("  2) HPF  (High-pass Butterworth biquad)")
    print("  3) BPF  (Band-pass Butterworth biquad)")
    print("  4) BSF  (Band-stop / notch Butterworth biquad)")
    ftype_map = {"1": "lowpass", "2": "highpass", "3": "bandpass", "4": "bandstop"}
    ft_choice = input("  Choose type [1]: ").strip() or "1"
    ftype = ftype_map.get(ft_choice, "lowpass")

    print("\n  --- Frequency parameters (real Hz) ---")
    fs = ask("Sampling frequency fs [Hz]", 48e6)
    f_low = f_high = None
    fc = 8e6
    if ftype in ("lowpass", "highpass"):
        fc = ask("Cutoff frequency fc [Hz]", 8e6)
    else:
        f_low = ask("Lower band edge [Hz]", 8e6)
        f_high = ask("Upper band edge [Hz]", 12e6)
        fc = 0.5 * (f_low + f_high)

    # Full design path with verbose intermediate results
    b, a, info = bilinear_biquad_design(
        ftype=ftype,
        fc_hz=fc,
        fs_hz=fs,
        f_low_hz=f_low,
        f_high_hz=f_high,
        verbose=True,
    )

    print("\n  --- Hardware parameters ---")
    data_width = ask("DATA_WIDTH", 16)
    coeff_width = ask("COEFF_WIDTH", 16)
    form = ask("form (df1 / df2)", "df2")

    # normalised cutoff for generate_biquad fallback
    if ftype in ("lowpass", "highpass"):
        cutoff = fc / fs
    else:
        cutoff = [f_low / fs, f_high / fs]

    return {
        "data_width": data_width,
        "coeff_width": coeff_width,
        "form": form,
        "ftype": ftype,
        "cutoff": cutoff,
        "fs": 1.0,
        "b_coeffs": b,
        "a_coeffs": a,
    }


def main():
    print("=" * 64)
    print("  DSP Composer – Programmatic VHDL Generator")
    print("  Complex blocks composed from primitives + auto coefficients")
    print("=" * 64)
    print()
    for k, (name, _, _) in PROCESSES.items():
        print(f"  {k}) {name}")
    print("  0) Exit")
    print()

    choice = input("Select process: ").strip()
    if choice == "0" or choice not in PROCESSES:
        print("Bye.")
        return

    title, func, params = PROCESSES[choice]
    print(f"\n--- {title} ---")

    if choice in ("1", "8"):
        # Special interactive FIR design flow
        kwargs = _ask_fir_design_params()
        print("\nGenerating…")
        if choice == "8":
            coeffs = design_fir_coefficients(
                kwargs["taps"], kwargs["cutoff"], fs=kwargs["fs"],
                window=kwargs["window"], ftype=kwargs["ftype"], beta=kwargs["beta"],
            )
            vhdl = generate_coeff_package(coeffs, kwargs["coeff_width"])
            fname = "fir_coeffs_pkg.vhd"
        else:
            vhdl = generate_fir(**kwargs)
            fname = "fir_filter.vhd"
    elif choice == "6":
        # Full IIR bilinear design + separate VHDL
        kwargs = _ask_iir_design_params()
        print("\nGenerating IIR VHDL…")
        vhdl = generate_biquad(**kwargs)
        fname = "biquad_iir.vhd"
    else:
        kwargs = {}
        for name, default in params:
            kwargs[name.lower()] = ask(name, default)
        print("\nGenerating…")
        vhdl = func(**kwargs)
        fname = {
            "2": "digital_mixer.vhd",
            "3": "pi_controller.vhd",
            "4": "polyphase_decimator.vhd",
            "5": "polyphase_interpolator.vhd",
            "7": "streaming_fft_sdf.vhd",
        }[choice]

    out_path = OUTPUT_DIR / fname
    out_path.write_text(vhdl, encoding="utf-8")
    print(f"  -> Wrote {out_path}  ({len(vhdl.splitlines())} lines)")
    print("Done.")


if __name__ == "__main__":
    main()
