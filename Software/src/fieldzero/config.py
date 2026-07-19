"""
Configuration for FieldZero acquisition and display.

Everything an operator may need to change lives here. The channel map is the
single source of truth for channel identity: the DAQ builds its task from it and
the viewer builds its channel selector from it, so the two cannot drift apart.
"""

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Channel:
    """One analog input: its physical DAQ terminal and what it measures."""

    name: str           # short label shown in the UI, e.g. "S1-Z"
    device_channel: str  # NI terminal, e.g. "Dev1/ai2"
    sensor: int         # which QuSpin (1 or 2)
    axis: str           # "x" | "y" | "z"


# Channel map inherited from MEG_DSP: Dev1/ai0-ai5 = 2 sensors x 3 axes.
# Adding a third sensor means appending three entries here and nothing else.
CHANNEL_MAP: tuple[Channel, ...] = (
    Channel("S1-X", "Dev1/ai0", 1, "x"),
    Channel("S1-Y", "Dev1/ai1", 1, "y"),
    Channel("S1-Z", "Dev1/ai2", 1, "z"),
    Channel("S2-X", "Dev1/ai3", 2, "x"),
    Channel("S2-Y", "Dev1/ai4", 2, "y"),
    Channel("S2-Z", "Dev1/ai5", 2, "z"),
)


@dataclass(frozen=True)
class DaqConfig:
    """
    NI-DAQ acquisition parameters.

    voltage_range and terminal_config were never set explicitly in MEG_DSP, so
    that acquisition silently ran on nidaqmx's defaults (min_val=-5.0,
    max_val=5.0, TerminalConfiguration.DEFAULT). They are stated here because
    both matter: the range sets where a channel clips, and RSE vs differential
    changes the noise floor. Confirm against the card in NI MAX.
    """

    channels: tuple[Channel, ...] = CHANNEL_MAP
    sample_rate: float = 1000.0
    voltage_range: tuple[float, float] = (-5.0, 5.0)
    terminal_config: str = "RSE"  # "RSE" | "NRSE" | "DIFF" | "DEFAULT"
    buffer_seconds: float = 60.0  # ring buffer depth; bounds the longest window
    read_chunk: int = 100         # samples per DAQ read in the acquisition thread

    @property
    def n_channels(self) -> int:
        return len(self.channels)


@dataclass(frozen=True)
class Calibration:
    """
    Volts -> field conversion.

    Acquisition always yields volts; this is applied at display time. The
    2.7 V/nT figure is inherited from MEG_DSP and is NOT verified against a
    datasheet — the QZFM generation in the lab is still unconfirmed. Until it
    is, treat volts as ground truth and pT as indicative.
    """

    sensitivity_v_per_nT: float = 2.7
    saturation_fraction: float = 0.98  # fraction of the rail that counts as clipped

    def volts_to_pT(self, volts):
        return (volts / self.sensitivity_v_per_nT) * 1000.0

    def scale(self, units: str) -> float:
        """Multiplier taking volts into `units`."""
        if units == "V":
            return 1.0
        if units == "pT":
            return 1000.0 / self.sensitivity_v_per_nT
        raise ValueError(f"unknown units {units!r} (expected 'V' or 'pT')")


@dataclass(frozen=True)
class ViewerConfig:
    """Display-side parameters. None of these touch the hardware."""

    refresh_hz: float = 20.0
    decimation_points: int = 2000  # target points per trace after min/max decimation
    default_window_s: float = 10.0
    phase_points: int = 2000       # points in a phase-plot cloud
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(frozen=True)
class AppConfig:
    daq: DaqConfig = field(default_factory=DaqConfig)
    calibration: Calibration = field(default_factory=Calibration)
    viewer: ViewerConfig = field(default_factory=ViewerConfig)

    def with_sample_rate(self, rate: float) -> "AppConfig":
        return replace(self, daq=replace(self.daq, sample_rate=rate))
