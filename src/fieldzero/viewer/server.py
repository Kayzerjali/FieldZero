"""
Viewer server: serves the page and pushes reduced frames over one WebSocket.

The browser owns the layout and sends up a declarative list of panes. The server
holds no display state: each frame it takes one snapshot from the ring buffer,
hands it to whatever reducers the panes currently ask for, and ships the result.
One DAQ read per frame regardless of how many panes are open.

Wire format, server -> client:

    [uint32 LE header_length][header JSON, utf-8][float32 LE payload]

The header names each pane's arrays and their lengths; the payload is those
arrays concatenated in that order. Bulk numbers stay out of JSON so the browser
does zero parsing and zero DSP — it is a renderer, nothing more.
"""

from __future__ import annotations

import asyncio
import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import reducers
from ..config import AppConfig
from ..datasource import DataSource, Snapshot

STATIC_DIR = Path(__file__).parent / "static"

# Window over which the stats table is computed. Short enough to feel live, long
# enough that the mean is not dominated by a single mains cycle at 50 Hz.
STATS_WINDOW_S = 1.0

# If a client has not acknowledged anything for this long, send regardless, so a
# client that never acks degrades instead of freezing. Never reached in normal use.
STALL_RESEND_S = 3.0


@dataclass
class ViewState:
    """What the client has asked to see. Replaced wholesale on every update."""

    specs: tuple[reducers.PaneSpec, ...] = ()
    stats_units: str = "pT"


def encode_frame(header: dict[str, Any], arrays: list[np.ndarray]) -> bytes:
    """Pack a header and its float32 arrays into one binary WebSocket message."""
    blob = json.dumps(header).encode("utf-8")
    parts = [struct.pack("<I", len(blob)), blob]
    for arr in arrays:
        parts.append(np.ascontiguousarray(arr, dtype="<f4").tobytes())
    return b"".join(parts)


def _slice_snapshot(snapshot: Snapshot, n: int) -> Snapshot:
    """The newest n samples of a snapshot, keeping its channel identity intact."""
    n = min(n, snapshot.n_samples)
    if n == snapshot.n_samples:
        return snapshot
    return Snapshot(
        data=snapshot.data[:, -n:],
        channels=snapshot.channels,
        sample_rate=snapshot.sample_rate,
        t0=snapshot.t0 + (snapshot.n_samples - n) / snapshot.sample_rate,
    )


def build_frame(source: DataSource, config: AppConfig, state: ViewState) -> bytes:
    """One frame: read the ring buffer once, then fan out to every pane."""
    fs = source.sample_rate
    capacity_s = config.daq.buffer_seconds

    windows = [min(s.window_s, capacity_s) for s in state.specs]
    needed_s = max(windows + [STATS_WINDOW_S])
    snapshot = source.get_data(int(round(needed_s * fs)))

    pane_headers: list[dict[str, Any]] = []
    payload: list[np.ndarray] = []

    for spec in state.specs:
        try:
            reducer = reducers.build(spec, config.calibration, config.viewer)
            frame = reducer.compute(snapshot)
        except Exception as exc:
            # A malformed pane spec must not take down the whole viewer: report it
            # into that pane and keep the others rendering.
            pane_headers.append({
                "id": spec.id, "kind": spec.kind,
                "meta": {"error": str(exc)}, "arrays": [],
            })
            continue
        pane_headers.append(frame.header())
        payload.extend(frame.arrays.values())

    stats = reducers.channel_stats(
        _slice_snapshot(snapshot, int(round(STATS_WINDOW_S * fs))),
        config.calibration,
        state.stats_units,
        config.daq.voltage_range,
    )

    err = getattr(source, "check_error", lambda: None)()
    header = {
        "t": snapshot.t0 + snapshot.n_samples / fs,
        "panes": pane_headers,
        "stats": stats,
        "buffer_samples": snapshot.n_samples,
        "daq_error": None if err is None else f"{type(err).__name__}: {err}",
    }
    return encode_frame(header, payload)


def build_app(source: DataSource, config: AppConfig) -> FastAPI:
    app = FastAPI(title="FieldZero viewer")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/session")
    async def session() -> dict[str, Any]:
        """Everything the client needs to build its controls. Channels come from
        the same map the DAQ task was built from, so the two cannot drift."""
        return {
            "channels": [
                {"name": c.name, "sensor": c.sensor, "axis": c.axis,
                 "device_channel": c.device_channel}
                for c in source.channels
            ],
            "sample_rate": source.sample_rate,
            "voltage_range": list(config.daq.voltage_range),
            "terminal_config": config.daq.terminal_config,
            "buffer_seconds": config.daq.buffer_seconds,
            "sensitivity_v_per_nT": config.calibration.sensitivity_v_per_nT,
            "refresh_hz": config.viewer.refresh_hz,
            "default_window_s": config.viewer.default_window_s,
            "kinds": sorted(reducers.REDUCERS),
            "source": type(source).__name__,
        }

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        state = ViewState()
        period = 1.0 / config.viewer.refresh_hz

        # At most one frame is in flight. The client acknowledges each frame once
        # it has rendered it; we only send the next one on a tick where the
        # previous frame has been acknowledged.
        #
        # Some flow control is necessary. If the browser cannot drain frames as
        # fast as we produce them, the socket's write buffer fills, and uvicorn
        # pauses the transport to apply backpressure — which stops it reading
        # INCOMING data too. Pane config messages then sit behind a congested
        # output stream and take seconds to apply.
        #
        # But we must never BLOCK on the acknowledgement, which is what an earlier
        # version did. Waiting on it meant that any single late ack — a GC pause,
        # a slow render, a tab that briefly lost focus (Chrome defers work in
        # background tabs) — cost a full timeout of dead air, and the display
        # visibly froze. Skipping a tick instead costs at most one frame period.
        acked = asyncio.Event()
        acked.set()          # nothing in flight yet, so the first frame may go
        last_sent = 0.0

        async def receive() -> None:
            while True:
                msg = await socket.receive_json()
                if msg.get("ack"):
                    acked.set()
                    continue
                state.specs = tuple(
                    reducers.PaneSpec.from_dict(p) for p in msg.get("panes", [])
                )
                state.stats_units = str(msg.get("stats_units", state.stats_units))

        async def send() -> None:
            nonlocal last_sent
            # Poll faster than the frame period. If the tick equalled the period,
            # an ack arriving a hair after a tick would cost an entire extra
            # period, capping a healthy client well below refresh_hz.
            tick = period / 4

            while True:
                now = time.perf_counter()
                due = (now - last_sent) >= period
                # A client that never acks at all (a stale cached page) would
                # otherwise receive one frame and freeze. Resend after a stall so
                # it limps rather than dies. A healthy client never reaches this.
                stalled = (now - last_sent) > STALL_RESEND_S

                if (acked.is_set() and due) or stalled:
                    acked.clear()
                    last_sent = time.perf_counter()
                    await socket.send_bytes(build_frame(source, config, state))

                await asyncio.sleep(tick)

        try:
            await asyncio.gather(receive(), send())
        except (WebSocketDisconnect, RuntimeError):
            pass  # client went away mid-send; nothing to clean up

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
