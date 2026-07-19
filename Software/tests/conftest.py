import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fieldzero.config import Calibration, Channel, DaqConfig, ViewerConfig
from fieldzero.datasource import Snapshot

TEST_CHANNELS = (
    Channel("S1-X", "Dev1/ai0", 1, "x"),
    Channel("S1-Y", "Dev1/ai1", 1, "y"),
    Channel("S1-Z", "Dev1/ai2", 1, "z"),
)


@pytest.fixture
def calibration() -> Calibration:
    return Calibration()


@pytest.fixture
def viewer() -> ViewerConfig:
    return ViewerConfig()


@pytest.fixture
def daq() -> DaqConfig:
    return DaqConfig(channels=TEST_CHANNELS, sample_rate=1000.0)


def make_snapshot(rows, sample_rate=1000.0, channels=TEST_CHANNELS, t0=0.0) -> Snapshot:
    """Build a Snapshot from a (n_channels, n_samples) array of volts."""
    data = np.atleast_2d(np.asarray(rows, dtype=float))
    return Snapshot(
        data=data,
        channels=channels[: data.shape[0]],
        sample_rate=sample_rate,
        t0=t0,
    )
