from __future__ import annotations
import numpy as np
import matplotlib
try:
    matplotlib.use('TkAgg')
except Exception:
    pass   # fall back to whatever is available
from dataclasses import dataclass
from src.config import Config, C_LIGHT, K_BOLTZ
from src.config import sentinel1_parameters

@dataclass
class Satellite:
    """
    SAR satellite system parameters.

    Defaults match the Sentinel-1A/B IW stripmap configuration:
      ESA Sentinel-1 Product Specification, ESA-EOPG-CSCOP-TN-0002 r3.
    """
    def __init__(self, config: dict = sentinel1_parameters):
        # Jeśli config nie zostanie przekazany, inicjalizuje pusty słownik
        if config is None:
            config = {}

        # ── Orbit ──────────────────────────────────────────────────────────────
        self.orbit_height: float = float(config.get("orbit_height", 693000.0))    # [m]
        self.velocity: float = float(config.get("velocity", 7511.8))              # [m/s]
        self.look_side: str = str(config.get("look_side", "right"))               # 'left' or 'right'

        # ── RF & waveform ──────────────────────────────────────────────────────
        self.frequency: float = float(config.get("frequency", 5.405e9))          # [Hz]
        self.bandwidth: float = float(config.get("bandwidth", 100e6))            # [Hz]
        self.pulse_duration: float = float(config.get("pulse_duration", 50e-6))  # [s]
        self.prf: float = float(config.get("prf", 1500.0))                        # [Hz]

        # ── Power ──────────────────────────────────────────────────────────────
        self.tx_power: float = float(config.get("tx_power", 4400.0))              # [W]

        # ── Antenna ────────────────────────────────────────────────────────────
        self.antenna_length: float = float(config.get("antenna_length", 12.3))    # [m]
        self.antenna_height: float = float(config.get("antenna_height", 0.84))    # [m]
        self.aperture_eff: float = float(config.get("aperture_eff", 0.6))         # η

        # ── Noise / losses ─────────────────────────────────────────────────────
        self.noise_figure: float = float(config.get("noise_figure", 3.0))         # [dB]
        self.losses_system: float = float(config.get("losses_system", 3.5))       # [dB]
        self.T_ref: float = float(config.get("T_ref", 290.0))

    # ── Derived ────────────────────────────────────────────────────────────
    @property
    def wavelength(self) -> float:
        """Carrier wavelength λ [m]."""
        return C_LIGHT / self.frequency

    @property
    def antenna_gain(self) -> float:
        """Peak two-way antenna gain G (linear)."""
        G_dB = self.antenna_gain_dB
        return 10 ** (G_dB / 10)

    @property
    def antenna_gain_dB(self) -> float:
        """Peak antenna gain G [dB]."""
        A = self.antenna_length * self.antenna_height
        G = self.aperture_eff * 4 * np.pi * A / self.wavelength ** 2
        return 10 * np.log10(G)

    @property
    def L_sys(self) -> float:
        """System losses L_sys (linear)."""
        return 10 ** (self.losses_system / 10)

    @property
    def T_sys(self) -> float:
        """System noise temperature T_sys [K]."""
        NF = 10 ** (self.noise_figure / 10)
        return self.T_ref * NF

    @property
    def range_resolution(self) -> float:
        """Slant-range resolution δ_r = c / (2·B) [m]."""
        return C_LIGHT / (2 * self.bandwidth)

    @property
    def azimuth_resolution(self) -> float:
        """Stripmap azimuth resolution δ_a = L_a / 2 [m]."""
        return self.antenna_length / 2