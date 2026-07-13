"""
End-to-end: MockSignal -> acquisition thread -> ring buffer -> reducers -> binary
wire format -> a real WebSocket client.

This is the test that would have caught the class of bug that broke MEG_DSP,
because it exercises the whole path while acquisition is genuinely running in
another thread, rather than checking each piece in isolation and hoping.

The Python client here decodes frames using the same rules as decodeFrame() in
app.js. If the wire format and the browser ever disagree, this fails.
"""

import asyncio
import json
import socket
import struct
import threading
import time

import numpy as np
import pytest
import uvicorn
import websockets

from fieldzero.config import AppConfig, DaqConfig
from fieldzero.datasource import MockSignal
from fieldzero.viewer.server import STALL_RESEND_S, build_app, encode_frame


# ----------------------------------------------------------------- wire format

def decode_frame(buf: bytes) -> dict:
    """Mirror of decodeFrame() in app.js."""
    (header_len,) = struct.unpack_from("<I", buf, 0)
    header = json.loads(buf[4 : 4 + header_len].decode("utf-8"))
    off = 4 + header_len
    for pane in header["panes"]:
        pane["data"] = {}
        for a in pane["arrays"]:
            n = a["n"]
            pane["data"][a["name"]] = np.frombuffer(buf, "<f4", count=n, offset=off)
            off += n * 4
    assert off == len(buf), "payload length disagrees with the header"
    return header


def test_encode_decode_round_trip():
    arrays = [np.arange(5, dtype=np.float32), np.linspace(0, 1, 3, dtype=np.float32)]
    header = {
        "panes": [{
            "id": "p1", "kind": "time", "meta": {},
            "arrays": [{"name": "x", "n": 5}, {"name": "S1-X", "n": 3}],
        }],
        "stats": [],
    }
    out = decode_frame(encode_frame(header, arrays))
    data = out["panes"][0]["data"]
    assert np.allclose(data["x"], arrays[0])
    assert np.allclose(data["S1-X"], arrays[1])


def test_encode_handles_zero_length_arrays():
    header = {"panes": [{"id": "p1", "kind": "spectrum", "meta": {},
                         "arrays": [{"name": "x", "n": 0}]}], "stats": []}
    out = decode_frame(encode_frame(header, [np.zeros(0, np.float32)]))
    assert out["panes"][0]["data"]["x"].size == 0


# ----------------------------------------------------------------- live server

@pytest.fixture(scope="module")
def live_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = AppConfig(daq=DaqConfig(sample_rate=1000.0))
    source = MockSignal(config.daq, seed=42)
    source.start()

    server = uvicorn.Server(uvicorn.Config(
        build_app(source, config), host="127.0.0.1", port=port, log_level="error",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started, "viewer server did not start"

    yield f"ws://127.0.0.1:{port}/ws", config

    server.should_exit = True
    thread.join(timeout=5)
    source.close()


PANES = [
    {"id": "t1", "kind": "time", "channels": ["S1-X", "S2-X"],
     "window_s": 2.0, "units": "V", "opts": {}},
    {"id": "f1", "kind": "spectrum", "channels": ["S1-X"],
     "window_s": 2.0, "units": "V", "opts": {"mode": "amplitude"}},
    {"id": "ph1", "kind": "phase", "channels": ["S1-X", "S2-X"],
     "window_s": 2.0, "units": "V", "opts": {}},
]


ACK = json.dumps({"ack": 1})


async def _recv(ws) -> dict:
    """Receive one frame and acknowledge it, as the browser client does. Without
    the ack the server holds the next frame until its timeout."""
    frame = decode_frame(await ws.recv())
    await ws.send(ACK)
    return frame


async def _collect(url: str, min_samples: int, timeout: float = 20.0) -> dict:
    """Connect, subscribe, and return the first frame with a full window buffered."""
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({"panes": PANES, "stats_units": "V"}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = await _recv(ws)
            if frame["buffer_samples"] >= min_samples and frame["panes"]:
                return frame
        raise AssertionError("buffer never filled within the timeout")


@pytest.fixture(scope="module")
def frame(live_server):
    url, _ = live_server
    return asyncio.run(_collect(url, min_samples=2000))


def test_acquisition_thread_is_alive(frame):
    assert frame["daq_error"] is None


def test_every_requested_pane_comes_back(frame):
    assert [p["id"] for p in frame["panes"]] == ["t1", "f1", "ph1"]
    assert all(not p["meta"].get("error") for p in frame["panes"])


def test_time_pane_carries_both_series_and_a_shared_x_axis(frame):
    pane = next(p for p in frame["panes"] if p["id"] == "t1")
    assert pane["meta"]["series"] == ["S1-X", "S2-X"]
    x = pane["data"]["x"]
    assert x.size == pane["data"]["S1-X"].size == pane["data"]["S2-X"].size
    assert np.all(np.diff(x) > 0)
    assert x[-1] == pytest.approx(0.0, abs=0.01)


def test_spectrum_finds_the_50_Hz_mains_tone_at_the_right_amplitude(frame):
    """
    MockSignal injects a 0.20 V, 50 Hz common-mode component. Recovering exactly
    that, through the real acquisition thread and the real wire format, is what
    makes this an end-to-end check rather than a smoke test.
    """
    pane = next(p for p in frame["panes"] if p["id"] == "f1")
    freqs = pane["data"]["x"]
    mag = pane["data"]["S1-X"]

    band = (freqs > 5) & (freqs < 500)      # exclude the DC offset, which is larger
    peak = int(np.argmax(np.where(band, mag, 0)))
    assert freqs[peak] == pytest.approx(50.0, abs=0.5)
    assert mag[peak] == pytest.approx(0.20, rel=0.10)


def test_spectrum_still_shows_the_dc_offset(frame):
    pane = next(p for p in frame["panes"] if p["id"] == "f1")
    # S1-X carries a 1.8 V DC offset — the residual-field analogue, and the whole
    # reason the DC bin is not zeroed.
    assert pane["data"]["S1-X"][0] == pytest.approx(1.8, rel=0.05)


def test_phase_pane_sees_the_common_mode_correlation(frame):
    pane = next(p for p in frame["panes"] if p["id"] == "ph1")
    # S1-X and S2-X share the mains component and differ only by independent
    # noise, so they must come back strongly correlated with a slope near 1.
    assert pane["meta"]["r"] > 0.9
    assert pane["meta"]["slope"] == pytest.approx(1.0, abs=0.15)
    assert pane["data"]["x"].size == pane["data"]["y"].size > 0


def test_stats_flag_the_railed_channel_and_only_that_one(frame):
    stats = {s["name"]: s for s in frame["stats"]}
    assert stats["S1-Z"]["saturated"] is True     # driven to 6 V against a 5 V rail
    assert stats["S1-X"]["saturated"] is False
    assert stats["S2-X"]["saturated"] is False


def test_stats_report_the_dc_offsets_the_mock_was_given(frame):
    stats = {s["name"]: s for s in frame["stats"]}
    assert stats["S1-X"]["mean"] == pytest.approx(1.8, abs=0.05)
    assert stats["S2-X"]["mean"] == pytest.approx(1.6, abs=0.05)
    assert stats["S1-Z"]["mean"] == pytest.approx(5.0, abs=0.05)  # clipped at the rail


def test_a_bad_pane_spec_does_not_take_down_the_other_panes(live_server):
    """One malformed pane must render an error into itself and leave the rest live."""
    url, _ = live_server

    async def go():
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({
                "panes": [
                    {"id": "good", "kind": "time", "channels": ["S1-X"],
                     "window_s": 1.0, "units": "V", "opts": {}},
                    {"id": "bad", "kind": "spectrum", "channels": ["S1-X"],
                     "window_s": 1.0, "units": "V", "opts": {"mode": "bogus"}},
                ],
                "stats_units": "V",
            }))
            for _ in range(40):
                f = await _recv(ws)
                if len(f["panes"]) == 2:
                    return f
            raise AssertionError("no frame with both panes arrived")

    f = asyncio.run(go())
    panes = {p["id"]: p for p in f["panes"]}
    assert "error" in panes["bad"]["meta"]
    assert not panes["good"]["meta"].get("error")
    assert panes["good"]["data"]["S1-X"].size > 0


def test_a_pane_config_change_applies_within_a_few_frames(live_server):
    """
    Regression test for a bug that made the UI feel broken.

    The server used to push frames at a fixed rate regardless of whether the
    client could keep up. An undecimated spectrum is ~140 kB per frame; at 20 Hz
    that outruns the browser, the socket's write buffer fills, and uvicorn pauses
    the transport to apply backpressure — which also stops it READING. Incoming
    pane-config messages then queued behind the congested output and took seconds
    to apply, so toggling a control appeared to do nothing.

    Frames are now acknowledged, so the server can never outrun the client and a
    config change must land almost immediately.
    """
    url, _ = live_server

    def spec(remove_dc: bool) -> str:
        return json.dumps({
            "panes": [{"id": "f1", "kind": "spectrum", "channels": ["S1-X"],
                       "window_s": 10.0, "units": "V",
                       "opts": {"mode": "asd", "remove_dc": remove_dc}}],
            "stats_units": "V",
        })

    async def go() -> int:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(spec(False))
            for _ in range(20):
                f = await _recv(ws)
                if f["panes"] and f["panes"][0]["meta"].get("remove_dc") is False:
                    break
            else:
                raise AssertionError("initial spec never applied")

            await ws.send(spec(True))
            for i in range(1, 30):
                f = await _recv(ws)
                if f["panes"] and f["panes"][0]["meta"].get("remove_dc") is True:
                    return i
            raise AssertionError("the config change never applied")

    frames = asyncio.run(go())
    assert frames <= 3, f"config change took {frames} frames to apply"


def test_an_acking_client_gets_close_to_the_configured_frame_rate(live_server):
    """A client that keeps up should run near refresh_hz, not at some fraction of it."""
    url, config = live_server

    async def go() -> float:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"panes": PANES, "stats_units": "V"}))
            await _recv(ws)                      # discard the first
            started = time.perf_counter()
            for _ in range(20):
                await _recv(ws)
            return 20 / (time.perf_counter() - started)

    fps = asyncio.run(go())
    assert fps > 0.6 * config.viewer.refresh_hz, f"only achieved {fps:.1f} fps"


def test_a_slow_client_is_not_punished_with_a_multi_second_stall(live_server):
    """
    Regression test for the bug that made the viewer feel laggy.

    The server used to BLOCK waiting for each frame's acknowledgement, with a
    long timeout. Any client that was merely slow — a GC pause, a heavy render, a
    tab Chrome had backgrounded — therefore paid the entire timeout as dead air
    on every frame, and the plots visibly froze.

    A client that acks late must simply get a lower frame rate, with the delay
    bounded by roughly one frame period, not by a timeout.
    """
    url, config = live_server
    period = 1.0 / config.viewer.refresh_hz
    slow_render = 0.10                      # a client taking 100 ms per frame

    async def go() -> list[float]:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"panes": PANES, "stats_units": "V"}))
            await ws.recv()
            await ws.send(ACK)

            gaps = []
            for _ in range(8):
                started = time.perf_counter()
                await ws.recv()
                gaps.append(time.perf_counter() - started)
                await asyncio.sleep(slow_render)   # deliberately slow to render
                await ws.send(ACK)
            return gaps

    gaps = asyncio.run(go())
    worst = max(gaps)
    # The server should be waiting for us, not timing out: each frame should
    # arrive within about one tick of our ack, never seconds later.
    assert worst < slow_render + 5 * period, f"worst inter-frame gap was {worst:.2f}s"


def test_a_client_that_never_acks_still_receives_frames(live_server):
    """A stale cached page must degrade, not freeze at a single frame."""
    url, _ = live_server

    async def go() -> int:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps({"panes": PANES, "stats_units": "V"}))
            seen = 0
            try:
                for _ in range(3):
                    await asyncio.wait_for(ws.recv(), timeout=STALL_RESEND_S + 2.0)
                    seen += 1
            except asyncio.TimeoutError:
                pass
            return seen

    assert asyncio.run(go()) >= 2


def test_session_endpoint_matches_the_daq_channel_map(live_server):
    """The UI builds its channel picker from this; if it drifts from the map the
    DAQ task was built from, a pane would silently plot the wrong sensor."""
    import urllib.request

    url, config = live_server
    http = url.replace("ws://", "http://").replace("/ws", "/api/session")
    with urllib.request.urlopen(http) as r:
        session = json.load(r)

    assert [c["name"] for c in session["channels"]] == [c.name for c in config.daq.channels]
    assert [c["device_channel"] for c in session["channels"]] == [
        c.device_channel for c in config.daq.channels
    ]
    assert session["sample_rate"] == 1000.0
    assert session["voltage_range"] == [-5.0, 5.0]
    assert sorted(session["kinds"]) == ["phase", "spectrum", "time"]
