"""
Quick acquisition check — confirms the DAQ is reading every channel.
Run this first when arriving at the lab, before starting any characterisation.

Usage:
    python scripts/characterisation/verify_acquisition.py [--mock] [--seconds 2]

Reports volts and pT side by side, and flags any channel sitting at the input
rail. The rail check is the one that matters: a clipped channel still reports a
mean that looks like a perfectly reasonable field value.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fieldzero.config import AppConfig
from fieldzero.datasource import MockSignal, NIDAQ
from fieldzero.reducers import channel_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DAQ acquisition")
    parser.add_argument("--mock", action="store_true", help="use MockSignal, no hardware")
    parser.add_argument("--seconds", type=float, default=2.0, help="capture duration")
    parser.add_argument("--sample-rate", type=float, default=None)
    args = parser.parse_args()

    config = AppConfig()
    if args.sample_rate is not None:
        config = config.with_sample_rate(args.sample_rate)

    # ASCII only: the default Windows console codepage mangles non-ASCII output.
    print("FieldZero - acquisition verification")
    print("=" * 68)

    if args.mock:
        source = MockSignal(config.daq)
        source.start()
    else:
        try:
            source = NIDAQ(config.daq)
        except Exception as exc:
            print(f"ERROR: could not open the NI-DAQ: {exc}")
            print("Run with --mock for an offline check.")
            return 1

    vmin, vmax = config.daq.voltage_range
    print(f"source      : {type(source).__name__}")
    print(f"sample rate : {config.daq.sample_rate:g} Hz")
    print(f"input range : {vmin:+g} .. {vmax:+g} V  ({config.daq.terminal_config})")
    print(f"sensitivity : {config.calibration.sensitivity_v_per_nT} V/nT  (UNVERIFIED)")
    print()

    try:
        time.sleep(args.seconds)  # let the ring buffer fill
        snapshot = source.get_data(int(args.seconds * config.daq.sample_rate))
    finally:
        source.close()

    if snapshot.n_samples == 0:
        print("ERROR: no samples arrived. Is the device present and wired?")
        err = source.check_error()
        if err:
            print(f"       acquisition thread died: {err!r}")
        return 1

    stats_v = channel_stats(snapshot, config.calibration, "V", config.daq.voltage_range)
    stats_pT = channel_stats(snapshot, config.calibration, "pT", config.daq.voltage_range)

    print(f"{snapshot.n_samples} samples "
          f"({snapshot.n_samples / config.daq.sample_rate:.2f} s) on "
          f"{len(snapshot.channels)} channels\n")

    header = f"{'channel':<9} {'mean (V)':>10} {'std (V)':>9} {'mean (pT)':>12} {'std (pT)':>10}   status"
    print(header)
    print("-" * len(header))

    railed = []
    for v, p in zip(stats_v, stats_pT):
        status = ""
        if v["saturated"]:
            status = f"RAILED ({v['clipped_fraction'] * 100:.0f}% of samples)"
            railed.append(v["name"])
        print(f"{v['name']:<9} {v['mean']:>10.4f} {v['std']:>9.4f} "
              f"{p['mean']:>12.1f} {p['std']:>10.1f}   {status}")

    print()
    if railed:
        print(f"WARNING: at the input rail: {', '.join(railed)}")
        print("         pT values for those channels are meaningless - the true field")
        print("         is larger than the input range can represent. Reduce the field")
        print("         or the sensor gain before trusting any number from them.")
    else:
        print("No channel is at the rail; all readings are within the input range.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
