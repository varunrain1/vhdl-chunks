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
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy import signal as sp_signal

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

def design_fir_coefficients(
    num_taps: int,
    cutoff: float | Sequence[float],
    fs: float = 1.0,
    window: str = "hamming",
    pass_zero: bool | str = True,
    scale: bool = True,
) -> np.ndarray:
    """Design FIR coefficients with scipy and return float64 array."""
    return sp_signal.firwin(
        num_taps,
        cutoff,
        fs=fs,
        window=window,
        pass_zero=pass_zero,
        scale=scale,
    )


def design_biquad_coefficients(
    ftype: str = "lowpass",
    order: int = 2,
    cutoff: float | Sequence[float] = 0.1,
    fs: float = 1.0,
    rp: float = 0.5,
    rs: float = 40.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Design a single biquad (or cascade of them).
    Returns (b, a) where both are length-3 for a pure 2nd-order section.
    For higher order we return the SOS matrix.
    """
    if order == 2:
        b, a = sp_signal.iirfilter(
            2, cutoff, btype=ftype, ftype="butter", fs=fs, output="ba"
        )
        return b, a
    else:
        sos = sp_signal.iirfilter(
            order, cutoff, btype=ftype, ftype="butter", fs=fs, output="sos"
        )
        return sos, None


def float_to_fixed(c: float, width: int, frac_bits: Optional[int] = None) -> int:
    """Convert float coefficient to signed fixed-point integer."""
    if frac_bits is None:
        frac_bits = width - 1
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
        frac_bits = width - 1
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
    cutoff: float = 0.2,
    fs: float = 1.0,
) -> str:
    """
    Transversal or systolic FIR.
    If coeffs is None, automatically designs a low-pass FIR with firwin.
    """
    if coeffs is None:
        coeffs = design_fir_coefficients(taps, cutoff, fs=fs)
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
    e = VHDLEmitter("digital_mixer")
    e.add_generic("DATA_WIDTH", "positive", str(data_width))
    e.add_generic("PHASE_WIDTH", "positive", str(phase_width))
    e.add_generic("LUT_DEPTH", "positive", str(lut_depth))

    e.add_port("clk", "in", "std_logic")
    e.add_port("rst", "in", "std_logic")
    e.add_port("ce", "in", "std_logic")
    e.add_port("xin_re", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("xin_im", "in", "signed(DATA_WIDTH-1 downto 0)")
    e.add_port("freq_word", "in", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_port("xout_re", "out", "signed(2*DATA_WIDTH downto 0)")
    e.add_port("xout_im", "out", "signed(2*DATA_WIDTH downto 0)")

    e.add_decl("""
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
    e.add_signal("phase", "unsigned(PHASE_WIDTH-1 downto 0)")
    e.add_signal("addr", "unsigned(LUT_DEPTH-1 downto 0)")
    e.add_signal("nco_sin", "signed(DATA_WIDTH-1 downto 0)")
    e.add_signal("nco_cos", "signed(DATA_WIDTH-1 downto 0)")
    e.add_signal("mul_re", "signed(2*DATA_WIDTH downto 0)")
    e.add_signal("mul_im", "signed(2*DATA_WIDTH downto 0)")

    e.add_arch("""
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

  phase   <= phase_acc;
  addr    <= phase(PHASE_WIDTH-1 downto PHASE_WIDTH-LUT_DEPTH);
  nco_sin <= SINE_LUT(to_integer(addr));
  nco_cos <= SINE_LUT(to_integer(addr + 2**(LUT_DEPTH-2)));

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
    e.add_signal("acc", "signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0)")
    e.add_signal("out_valid", "std_logic", "'0'")

    e.add_arch("""
  process(clk, rst)
    variable sum : signed(DATA_WIDTH+COEFF_WIDTH+4 downto 0);
    variable phase : integer;
  begin
    if rst = '1' then
      phase_cnt <= 0;
      delays    <= (others => (others => (others => '0')));
      acc       <= (others => '0');
      out_valid <= '0';
    elsif rising_edge(clk) then
      out_valid <= '0';
      if ce_in = '1' then
        phase := phase_cnt;
        delays(phase)(0) <= din;
        for t in 1 to TAPS_PER_PHASE-1 loop
          delays(phase)(t) <= delays(phase)(t-1);
        end loop;

        sum := (others => '0');
        for t in 0 to TAPS_PER_PHASE-1 loop
          sum := sum + resize(delays(phase)(t) * PHASE_COEFFS(phase)(t), sum'length);
        end loop;

        if phase_cnt = FACTOR-1 then
          phase_cnt <= 0;
          acc       <= sum;
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
    cutoff: float = 0.1,
    fs: float = 1.0,
) -> str:
    """
    Single biquad section.
    Coefficients automatically designed with scipy (Butterworth).
    """
    b, a = design_biquad_coefficients(ftype=ftype, order=2, cutoff=cutoff, fs=fs)
    # normalise a0 = 1
    b = b / a[0]
    a = a / a[0]

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
    Single-path Delay Feedback (SDF) style streaming FFT skeleton.
    One sample in / one sample out per clock after pipeline fill.
    Twiddle factors are pre-computed and embedded.
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

    # Pre-compute twiddles for every stage
    twiddle_decl = [
        "  type complex_tw is record",
        "    re : signed(TWIDDLE_WIDTH-1 downto 0);",
        "    im : signed(TWIDDLE_WIDTH-1 downto 0);",
        "  end record;",
        f"  type twiddle_array is array (0 to N_POINTS/2-1) of complex_tw;",
    ]
    # For simplicity we embed one table; real SDF uses stage-specific tables
    twiddles = []
    for k in range(n_points // 2):
        angle = -2.0 * math.pi * k / n_points
        re = float_to_fixed(math.cos(angle), twiddle_width)
        im = float_to_fixed(math.sin(angle), twiddle_width)
        twiddles.append(f"(re => to_signed({re}, TWIDDLE_WIDTH), im => to_signed({im}, TWIDDLE_WIDTH))")
    twiddle_decl.append("  constant TWIDDLES : twiddle_array := (")
    twiddle_decl.append("    " + ",\n    ".join(twiddles))
    twiddle_decl.append("  );")
    e.add_decl("\n".join(twiddle_decl))

    e.add_decl("""
  type complex_t is record
    re : signed(DATA_WIDTH+STAGES downto 0);
    im : signed(DATA_WIDTH+STAGES downto 0);
  end record;
""")
    e.add_signal("cnt", "unsigned(STAGES-1 downto 0)", "(others => '0')")
    e.add_signal("valid_sr", "std_logic_vector(STAGES downto 0)", "(others => '0')")

    # Simple pipeline of butterflies (educational SDF approximation)
    for s in range(stages):
        e.add_signal(f"s{s}_re", f"signed(DATA_WIDTH+STAGES downto 0)")
        e.add_signal(f"s{s}_im", f"signed(DATA_WIDTH+STAGES downto 0)")

    e.add_arch("""
  process(clk, rst)
    variable a_re, a_im, b_re, b_im : signed(DATA_WIDTH+STAGES downto 0);
    variable t_re, t_im : signed(DATA_WIDTH+STAGES downto 0);
    variable tw_idx : integer;
  begin
    if rst = '1' then
      cnt      <= (others => '0');
      valid_sr <= (others => '0');
""")
    for s in range(stages):
        e.add_arch(f"      s{s}_re <= (others => '0');\n      s{s}_im <= (others => '0');")
    e.add_arch("""
    elsif rising_edge(clk) then
      if ce = '1' then
        cnt      <= cnt + 1;
        valid_sr <= valid_sr(STAGES-1 downto 0) & '1';

        -- Stage 0 input
        s0_re <= resize(xin_re, DATA_WIDTH+STAGES);
        s0_im <= resize(xin_im, DATA_WIDTH+STAGES);
""")
    # Generate remaining stages
    for s in range(1, stages):
        e.add_arch(f"""
        -- Butterfly stage {s}
        -- (simplified – real SDF uses feedback delay of N/2^s)
        a_re := s{s-1}_re;
        a_im := s{s-1}_im;
        -- placeholder partner sample (in a full SDF this comes from a delay line)
        b_re := s{s-1}_re;  -- replace with delayed sample
        b_im := s{s-1}_im;
        t_re := a_re + b_re;
        t_im := a_im + b_im;
        s{s}_re <= t_re;
        s{s}_im <= t_im;
""")
    e.add_arch(f"""
      end if;
    end if;
  end process;

  xout_re   <= s{stages-1}_re;
  xout_im   <= s{stages-1}_im;
  out_valid <= valid_sr(STAGES);
""")
    return e.emit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PROCESSES = {
    "1": ("FIR Filter (transversal/systolic) + auto coeffs", generate_fir,
          [("DATA_WIDTH", 16), ("COEFF_WIDTH", 16), ("TAPS", 16),
           ("ACC_WIDTH", 32), ("structure", "transversal"), ("cutoff", 0.2)]),
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
    "6": ("Biquad IIR (DF1/DF2) + auto coeffs", generate_biquad,
          [("DATA_WIDTH", 16), ("COEFF_WIDTH", 16), ("form", "df1"),
           ("ftype", "lowpass"), ("cutoff", 0.1)]),
    "7": ("Streaming Radix-2 FFT (SDF skeleton)", generate_streaming_fft,
          [("DATA_WIDTH", 16), ("N_POINTS", 64), ("TWIDDLE_WIDTH", 16)]),
    "8": ("Coefficient package only (FIR)", None,  # special handling
          [("TAPS", 32), ("COEFF_WIDTH", 16), ("cutoff", 0.2)]),
}


def ask(prompt: str, default):
    val = input(f"  {prompt} [{default}]: ").strip()
    if val == "":
        return default
    if isinstance(default, (int, float)):
        try:
            return type(default)(val)
        except ValueError:
            return default
    return val


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
    kwargs = {}
    for name, default in params:
        kwargs[name.lower()] = ask(name, default)

    print("\nGenerating…")

    if choice == "8":
        # standalone coefficient package
        taps = kwargs["taps"]
        width = kwargs["coeff_width"]
        cutoff = kwargs["cutoff"]
        coeffs = design_fir_coefficients(taps, cutoff)
        vhdl = generate_coeff_package(coeffs, width)
        fname = "fir_coeffs_pkg.vhd"
    else:
        # map CLI keys to function argument names
        if choice == "1":
            kwargs["structure"] = kwargs.get("structure", "transversal")
        vhdl = func(**kwargs)
        fname = {
            "1": "fir_filter.vhd",
            "2": "digital_mixer.vhd",
            "3": "pi_controller.vhd",
            "4": "polyphase_decimator.vhd",
            "5": "polyphase_interpolator.vhd",
            "6": "biquad_iir.vhd",
            "7": "streaming_fft_sdf.vhd",
        }[choice]

    out_path = OUTPUT_DIR / fname
    out_path.write_text(vhdl)
    print(f"  → Wrote {out_path}  ({len(vhdl.splitlines())} lines)")
    print("Done.")


if __name__ == "__main__":
    main()
