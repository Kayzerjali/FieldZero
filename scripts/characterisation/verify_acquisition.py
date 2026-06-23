"""
Quick acquisition check — confirms NI-DAQ is reading both sensors on all axes.
Run this first when arriving at the lab to verify hardware is up before starting
any characterisation measurements.

Usage:
    python scripts/characterisation/verify_acquisition.py [--mock]

    --mock    Use MockSignal (no hardware required — for offline testing)
"""

import argparse
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fieldzero.datasource import NIDAQ, MockSignal, is_saturated

N_SAMPLES = 500
SAMPLE_RATE = 1000


def main():
    parser = argparse.ArgumentParser(description="Verify NI-DAQ acquisition")
    parser.add_argument("--mock", action="store_true", help="Use MockSignal instead of hardware")
    args = parser.parse_args()

    print("FieldZero — Acquisition Verification")
    print("=" * 40)

    if args.mock:
        print("Mode: MockSignal (offline)")
        source = MockSignal(sample_rate=SAMPLE_RATE)
    else:
        print("Mode: NI-DAQ hardware")
        source = NIDAQ(sample_rate=SAMPLE_RATE, axis="all")

    stream = source.data_stream(num_samples_per_read=N_SAMPLES)
    data = None
    for chunk in stream:
        if chunk is not None:
            data = chunk
            break

    source.close()

    if data is None:
        print("ERROR: No data received from source.")
        sys.exit(1)

    print(f"\nData shape: {data.shape}  (channels × samples)")
    print(f"Sample rate: {SAMPLE_RATE} Hz,  {N_SAMPLES} samples = {N_SAMPLES/SAMPLE_RATE:.2f} s\n")

    labels = ["Sensor1-X", "Sensor1-Y", "Sensor1-Z", "Sensor2-X", "Sensor2-Y", "Sensor2-Z"]
    print(f"{'Channel':<14} {'Mean (pT)':>12} {'Std (pT)':>10} {'Min (pT)':>10} {'Max (pT)':>10}")
    print("-" * 60)
    for i, label in enumerate(labels[:data.shape[0]]):
        ch = data[i]
        print(f"{label:<14} {np.mean(ch):>12.1f} {np.std(ch):>10.1f} {np.min(ch):>10.1f} {np.max(ch):>10.1f}")

    print("\nNote: ceiling value for saturation detection must be set from M-01 measurement.")
    print("      See docs/01_characterisation.md → M-01.")


if __name__ == "__main__":
    main()
