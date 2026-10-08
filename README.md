# DSP Composer – Parameter Reference

Programmatic VHDL generator for common DSP blocks.  
Run with:

```bash
python dsp_gen.py
```

All generated files are written to the `output/` folder and use **asynchronous active-high reset**.

---

## 1. FIR Filter (transversal / systolic)

**File:** `fir_filter.vhd`

| Parameter       | Type     | Default      | Description |
|-----------------|----------|--------------|-------------|
| `DATA_WIDTH`    | positive | 16           | Bit-width of the input sample (`din`) |
| `COEFF_WIDTH`   | positive | 16           | Bit-width of each filter coefficient |
| `TAPS`          | positive | 16           | Number of filter taps (order + 1) |
| `ACC_WIDTH`     | positive | 32           | Bit-width of the accumulator / output. Should be ≥ `DATA_WIDTH + COEFF_WIDTH + log2(TAPS)` |
| `structure`     | string   | transversal  | Architecture style: `transversal` (direct-form) or `systolic` (cascaded MAC pipeline) |
| `cutoff`        | float    | 0.2          | Normalised cut-off frequency (0 … 0.5) used for automatic coefficient design |

**Notes**
- Coefficients are automatically designed as a linear-phase low-pass FIR (windowed-sinc / firwin) and embedded as VHDL constants.
- `transversal` = classic tapped-delay-line + parallel multipliers + adder tree.  
- `systolic` = registered multiply-accumulate chain (better DSP-slice mapping, higher fmax).

---

## 2. Digital Mixer (NCO + Complex Multiply)

**File:** `digital_mixer.vhd`

| Parameter       | Type     | Default | Description |
|-----------------|----------|---------|-------------|
| `DATA_WIDTH`    | positive | 16      | Bit-width of the complex input (`xin_re`, `xin_im`) and of the NCO sine/cosine |
| `PHASE_WIDTH`   | positive | 32      | Bit-width of the phase accumulator / frequency tuning word |
| `LUT_DEPTH`     | positive | 10      | log₂ of the sine LUT size (LUT has 2^LUT_DEPTH entries) |

**Notes**
- Implements a classic digital down-/up-converter mixer:  
  `out = in × e^(−jωn)` (or conjugate).
- Frequency control word (`freq_word`) is an unsigned value:  
  `f_out = freq_word / 2^PHASE_WIDTH × f_clk`.

---

## 3. PI Controller

**File:** `pi_controller.vhd`

| Parameter       | Type     | Default | Description |
|-----------------|----------|---------|-------------|
| `DATA_WIDTH`    | positive | 16      | Bit-width of the error input |
| `ACC_WIDTH`     | positive | 32      | Bit-width of the integral accumulator and of the controller output |
| `KP_WIDTH`      | positive | 16      | Bit-width of the proportional gain `kp` |
| `KI_WIDTH`      | positive | 16      | Bit-width of the integral gain `ki` |

**Notes**
- Implements the classic discrete PI law:  
  `u[n] = Kp·e[n] + Ki·∑e[k]`
- Gains are supplied externally every clock (can be constants or run-time programmable).

---

## 4. Polyphase Decimator

**File:** `polyphase_decimator.vhd`

| Parameter         | Type     | Default | Description |
|-------------------|----------|---------|-------------|
| `DATA_WIDTH`      | positive | 16      | Input sample width |
| `FACTOR`          | positive | 4       | Decimation factor M (keep 1 sample out of M) |
| `TAPS_PER_PHASE`  | positive | 8       | Number of taps in each polyphase sub-filter |
| `COEFF_WIDTH`     | positive | 16      | Coefficient bit-width |
| `cutoff`          | float    | 0.4     | Normalised cut-off **before** decimation (the generator automatically designs the prototype FIR and splits it into M phases) |

**Notes**
- Total prototype taps = `FACTOR × TAPS_PER_PHASE`.
- Anti-alias low-pass filtering is performed by the polyphase branches.

---

## 5. Polyphase Interpolator

**File:** `polyphase_interpolator.vhd`

| Parameter         | Type     | Default | Description |
|-------------------|----------|---------|-------------|
| `DATA_WIDTH`      | positive | 16      | Input sample width |
| `FACTOR`          | positive | 4       | Interpolation factor L (insert L-1 zeros) |
| `TAPS_PER_PHASE`  | positive | 8       | Taps per polyphase branch |
| `COEFF_WIDTH`     | positive | 16      | Coefficient bit-width |
| `cutoff`          | float    | 0.4     | Normalised cut-off of the prototype low-pass (anti-imaging filter) |

**Notes**
- Same coefficient-generation approach as the decimator.
- Output rate is `FACTOR` times the input rate.

---

## 6. Biquad IIR (Direct-Form I / II)

**File:** `biquad_iir.vhd`

| Parameter       | Type     | Default   | Description |
|-----------------|----------|-----------|-------------|
| `DATA_WIDTH`    | positive | 16        | Input sample width |
| `COEFF_WIDTH`   | positive | 16        | Coefficient width (Q1.14 format by default) |
| `form`          | string   | df1       | `df1` = Direct-Form I, `df2` = Direct-Form II (canonical) |
| `ftype`         | string   | lowpass   | Filter type passed to the designer (`lowpass`, `highpass`, `bandpass`, …) |
| `cutoff`        | float    | 0.1       | Normalised cut-off frequency (0 … 0.5) |

**Notes**
- Coefficients are automatically designed as a 2nd-order Butterworth section and embedded as constants.
- Direct-Form II uses fewer delay elements (canonical).
- Output width is `DATA_WIDTH + COEFF_WIDTH` to give head-room for the internal accumulations.

---

## 7. Streaming Radix-2 FFT (SDF skeleton)

**File:** `streaming_fft_sdf.vhd`

| Parameter         | Type     | Default | Description |
|-------------------|----------|---------|-------------|
| `DATA_WIDTH`      | positive | 16      | Real/imaginary input width |
| `N_POINTS`        | positive | 64      | FFT length – **must be a power of two** |
| `TWIDDLE_WIDTH`   | positive | 16      | Bit-width of the embedded twiddle factors |

**Notes**
- Single-path Delay-Feedback (SDF) style streaming architecture.
- One complex sample in / one complex sample out per clock after the pipeline fills.
- Twiddle factors are pre-computed and stored as a VHDL constant table.
- This is a working educational skeleton; a production SDF FFT would add the full feedback delay lines per stage.

---

## 8. Coefficient Package only (FIR)

**File:** `fir_coeffs_pkg.vhd`

| Parameter       | Type     | Default | Description |
|-----------------|----------|---------|-------------|
| `TAPS`          | positive | 32      | Number of coefficients to generate |
| `COEFF_WIDTH`   | positive | 16      | Bit-width of each coefficient |
| `cutoff`        | float    | 0.2     | Normalised cut-off for the low-pass design |

**Notes**
- Produces a pure VHDL package that you can `use work.fir_coeffs_pkg.all;` from any other design.
- Useful when you want to share the same coefficients among several FIR instances.

---

## Common tips

1. **Bit-width rules of thumb**
   - Accumulator / output width ≈ `DATA_WIDTH + COEFF_WIDTH + ceil(log2(TAPS))`
   - For IIR feedback coefficients leave at least one integer bit (the generator already does this).

2. **Normalised frequency**  
   All `cutoff` values are relative to the sampling frequency:  
   `0.0` = DC, `0.5` = Nyquist.

3. **Reset**  
   Every block uses an asynchronous active-high reset (`rst`).

4. **Clock enable**  
   Most blocks have a `ce` (or `ce_in`) input so they can be safely multi-rate or clock-gated.

5. **Missing numpy/scipy**  
   The generator falls back to pure-Python coefficient designs.  
   For higher-quality filters install numpy+scipy or set `PYTHONPATH` to their location.
