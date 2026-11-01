#!/usr/bin/env python3
"""
generate_dsp_vectors.py

Generate stimulus + expected golden vectors for many DSP modules.
"""

import numpy as np
from scipy.signal import firwin, lfilter, resample_poly
import sys

# ============================================================
# Global configuration
# ============================================================
SAMPLE_RATE   = 100e6
NUM_SAMPLES   = 512
INPUT_WIDTH   = 16
OUTPUT_WIDTH  = 16

STIM_FILE     = "stimuli.txt"
EXP_FILE      = "expected.txt"

np.random.seed(42)          # reproducible results

# ============================================================
# Utility functions
# ============================================================
def quantize(x, width):
    max_val = 2**(width - 1) - 1
    return np.clip(np.round(x * max_val), -max_val-1, max_val).astype(int)

def write_vectors(stim, expected, stim_file=STIM_FILE, exp_file=EXP_FILE):
    with open(stim_file, "w") as f_stim, open(exp_file, "w") as f_exp:
        f_stim.write("# Stimulus (signed decimal)\n")
        f_exp.write("# Expected (signed decimal)\n")
        for s, e in zip(stim, expected):
            f_stim.write(f"{int(np.round(s))}\n")
            f_exp.write(f"{int(np.round(e))}\n")
    print(f"  → Wrote {len(stim)} vectors to {stim_file} and {exp_file}")

# ============================================================
# Module generators
# ============================================================
def generate_fir():
    print("\n[FIR] Kaiser window FIR")
    NUM_TAPS = 63
    CUTOFF   = 0.2
    BETA     = 8.6

    coeffs = firwin(NUM_TAPS, CUTOFF, window=('kaiser', BETA))
    t = np.arange(NUM_SAMPLES)
    stim_float = (0.5 * np.sin(2*np.pi*0.05*t) +
                  0.3 * np.sin(2*np.pi*0.17*t) +
                  0.1 * np.random.randn(NUM_SAMPLES))

    expected_float = lfilter(coeffs, 1.0, stim_float)

    write_vectors(quantize(stim_float, INPUT_WIDTH),
                  quantize(expected_float, OUTPUT_WIDTH))
    np.savetxt("fir_coefficients.txt", quantize(coeffs, 16), fmt="%d")
    print("  → fir_coefficients.txt written")

def generate_nco():
    print("\n[NCO] Numerically Controlled Oscillator")
    FREQ_HZ = 5.0e6
    PHASE_INC = int((FREQ_HZ / SAMPLE_RATE) * (2**32))

    phase = 0
    expected_i = []
    expected_q = []

    for _ in range(NUM_SAMPLES):
        phase = (phase + PHASE_INC) & 0xFFFFFFFF
        angle = phase / 2**32 * 2 * np.pi
        expected_i.append(np.cos(angle))
        expected_q.append(np.sin(angle))

    stim = [PHASE_INC] * NUM_SAMPLES
    write_vectors(stim, quantize(np.array(expected_i), OUTPUT_WIDTH))
    np.savetxt("nco_expected_q.txt", quantize(np.array(expected_q), OUTPUT_WIDTH), fmt="%d")
    print("  → nco_expected_q.txt written")

def generate_mixer():
    print("\n[Mixer] Digital Mixer (complex multiply)")
    t = np.arange(NUM_SAMPLES) / SAMPLE_RATE
    signal = 0.7 * np.exp(1j * 2*np.pi * 1.5e6 * t)
    lo     = np.exp(1j * 2*np.pi * 4.0e6 * t)

    mixed = signal * np.conj(lo)

    write_vectors(quantize(np.real(signal), INPUT_WIDTH),
                  quantize(np.real(mixed), OUTPUT_WIDTH))

def generate_decimator():
    print("\n[Decimator] FIR + Downsample")
    FACTOR = 4
    t = np.arange(NUM_SAMPLES)
    stim_float = np.sin(2*np.pi*0.03*t) + 0.15*np.random.randn(NUM_SAMPLES)

    coeffs = firwin(64, 1.0/FACTOR)
    filtered = lfilter(coeffs, 1.0, stim_float)
    expected = filtered[::FACTOR]

    write_vectors(quantize(stim_float, INPUT_WIDTH),
                  quantize(expected, OUTPUT_WIDTH))
    print(f"  → Decimation factor = {FACTOR}")

def generate_interpolator():
    print("\n[Interpolator] Upsample + FIR")
    FACTOR = 4
    t = np.arange(NUM_SAMPLES // FACTOR)
    stim_float = np.sin(2*np.pi*0.07*t)

    expected = resample_poly(stim_float, FACTOR, 1)

    write_vectors(quantize(stim_float, INPUT_WIDTH),
                  quantize(expected, OUTPUT_WIDTH))
    print(f"  → Interpolation factor = {FACTOR}")

def generate_up_conversion():
    print("\n[Up Conversion]")
    t = np.arange(NUM_SAMPLES) / SAMPLE_RATE
    bb  = 0.6 * np.exp(1j * 2*np.pi * 0.8e6 * t)
    lo  = np.exp(1j * 2*np.pi * 12e6 * t)
    up  = bb * lo

    write_vectors(quantize(np.real(bb), INPUT_WIDTH),
                  quantize(np.real(up), OUTPUT_WIDTH))

def generate_down_conversion():
    print("\n[Down Conversion]")
    t = np.arange(NUM_SAMPLES) / SAMPLE_RATE
    rf  = 0.6 * np.exp(1j * 2*np.pi * 12.7e6 * t)
    lo  = np.exp(1j * 2*np.pi * 12e6 * t)
    down = rf * np.conj(lo)

    write_vectors(quantize(np.real(rf), INPUT_WIDTH),
                  quantize(np.real(down), OUTPUT_WIDTH))

def generate_cic_decimator():
    print("\n[CIC Decimator] Simple CIC model (diff + comb)")
    FACTOR = 8
    STAGES = 3

    t = np.arange(NUM_SAMPLES)
    stim_float = np.sin(2*np.pi*0.02*t) + 0.1*np.random.randn(NUM_SAMPLES)

    # Very simple CIC-like behavior (for golden reference only)
    x = stim_float.copy()
    for _ in range(STAGES):
        x = np.cumsum(x)                    # integrator
    x = x[::FACTOR]                         # downsample
    for _ in range(STAGES):
        x = np.diff(x, prepend=0)           # comb

    write_vectors(quantize(stim_float, INPUT_WIDTH),
                  quantize(x, OUTPUT_WIDTH))
    print(f"  → CIC factor = {FACTOR}, stages = {STAGES}")

def generate_cordic():
    print("\n[CORDIC] Rotation mode (simplified)")
    # Generate angles and expected cos/sin
    angles = np.linspace(-np.pi/2, np.pi/2, NUM_SAMPLES)
    expected_cos = np.cos(angles)
    expected_sin = np.sin(angles)

    # Stimulus = angle in fixed-point (scaled)
    stim = quantize(angles / np.pi, INPUT_WIDTH)   # normalize angle

    write_vectors(stim, quantize(expected_cos, OUTPUT_WIDTH))
    np.savetxt("cordic_expected_sin.txt", quantize(expected_sin, OUTPUT_WIDTH), fmt="%d")
    print("  → cordic_expected_sin.txt written")

# ============================================================
# Menu
# ============================================================
menu = {
    "1": ("FIR (Kaiser)",           generate_fir),
    "2": ("NCO",                    generate_nco),
    "3": ("Digital Mixer",          generate_mixer),
    "4": ("Decimator",              generate_decimator),
    "5": ("Interpolator",           generate_interpolator),
    "6": ("Up Conversion",          generate_up_conversion),
    "7": ("Down Conversion",        generate_down_conversion),
    "8": ("CIC Decimator",          generate_cic_decimator),
    "9": ("CORDIC",                 generate_cordic),
    "a": ("All modules",            None),
    "q": ("Quit",                   None),
}

def main():
    while True:
        print("\n" + "="*50)
        print(" DSP Golden Vector Generator")
        print("="*50)
        for key, (name, _) in menu.items():
            print(f"  {key}. {name}")
        print("="*50)

        choice = input("Select module → ").strip().lower()

        if choice == "q":
            print("Exiting.")
            break
        elif choice == "a":
            for key in sorted(menu.keys()):
                if key in ("a", "q"):
                    continue
                func = menu[key][1]
                if func:
                    func()
            break
        elif choice in menu and menu[choice][1] is not None:
            menu[choice][1]()
            again = input("\nGenerate another? [y/N] → ").strip().lower()
            if again != "y":
                break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()