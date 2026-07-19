"""
Entry point:  python -m fieldzero.viewer [--mock] [--sample-rate 1000]

Sample rate is a startup parameter, deliberately. Changing it live means tearing
down and rebuilding the DAQ task, which is exactly the operation that made axis
switching unreliable in MEG_DSP. Restart the viewer to change it.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

import uvicorn

from ..config import AppConfig
from ..datasource import MockSignal, NIDAQ
from .server import build_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fieldzero.viewer")
    parser.add_argument("--mock", action="store_true",
                        help="run against MockSignal — no DAQ hardware required")
    parser.add_argument("--sample-rate", type=float, default=None,
                        help="samples/second per channel (default: 1000)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    config = AppConfig()
    if args.sample_rate is not None:
        config = config.with_sample_rate(args.sample_rate)
    host = args.host or config.viewer.host
    port = args.port or config.viewer.port

    if args.mock:
        source = MockSignal(config.daq)
        source.start()
    else:
        try:
            source = NIDAQ(config.daq)
        except Exception as exc:
            print(f"Could not open the NI-DAQ: {exc}", file=sys.stderr)
            print("Run with --mock to use the simulated source.", file=sys.stderr)
            return 1

    print(f"FieldZero viewer — source={type(source).__name__} "
          f"fs={config.daq.sample_rate:g} Hz  channels={config.daq.n_channels}")
    print(f"  http://{host}:{port}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()

    try:
        uvicorn.run(build_app(source, config), host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
