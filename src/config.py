# config.py
import os

C_LIGHT  = 2.99792458e8   # speed of light  [m/s]
K_BOLTZ  = 1.380649e-23   # Boltzmann const [J/K]

sentinel1_parameters = {
    # ── Orbit ────────────────────────────────────────────────────────────────
    "orbit_height": 693000.0,        # wysokość orbity Sentinel-1 nad powierzchnią [m]
    "velocity": 7511.8,              # ground-track velocity           [m/s]
    "look_side": "right",            # Sentinel-1 operuje głównie jako right-looking

    # ── RF & waveform ──────────────────────────────────────────────────────
    "frequency": 5.405e9,            # carrier frequency (C-band)      [Hz]
    "bandwidth": 100e6,              # typowe pasmo dla trybu SM/IW     [Hz]
    "pulse_duration": 50e-6,         # pulse duration τ_p               [s]
    "prf": 1500.0,                   # pulse repetition frequency      [Hz]

    # ── Power ──────────────────────────────────────────────────────────────
    "tx_power": 4400.0,              # peak transmit power P_t          [W]

    # ── Antenna ────────────────────────────────────────────────────────────
    "antenna_length": 12.3,          # ogromna antena azymutalna L_a    [m]
    "antenna_height": 0.84,          # elevation aperture L_e           [m]
    "aperture_eff": 0.6,             # sprawność anteny η

    # ── Noise / losses ─────────────────────────────────────────────────────
    "noise_figure": 3.0,             # receiver NF                     [dB]
    "losses_system": 3.5,            # hardware / processing losses    [dB]
    "T_ref": 290.0
}

LAND_COVER_NAMES: dict[int, str] = {
    1: "Zabudowa", 2: "Grunty orne", 3: "Uprawy trwałe",
    4: "Łąki/pastwiska", 5: "Lasy iglaste", 6: "Lasy liściaste",
    7: "Wody", 8: "Mokradła", 9: "Piaski", 10: "Lasy mieszane",
}

SIGMA0_N: dict[int, float] = {
    1: 1.5, 2: 2.0, 3: 1.5, 4: 1.5,
    5: 1.0, 6: 1.0, 7: 3.0, 8: 1.5,
    9: 2.5, 10: 1.0,
}

SIGMA0_DB: dict[int, tuple[float, float]] = {
    # class : (mean σ⁰ [dB],  std σ⁰ [dB])
    1:  ( -4.0, 3.0),   # Zabudowa          – double-bounce
    2:  (-12.0, 2.5),   # Grunty orne       – surface
    3:  (-10.0, 2.0),   # Uprawy trwałe     – surface + volume
    4:  ( -9.0, 2.0),   # Łąki/pastwiska    – volume
    5:  ( -6.0, 2.0),   # Lasy iglaste      – volume
    6:  ( -7.0, 2.0),   # Lasy liściaste    – volume
    7:  (-18.0, 5.0),   # Wody              – specular / wind-driven
    8:  (-12.0, 3.0),   # Mokradła          – double-bounce + volume
    9:  (-15.0, 2.0),   # Piaski            – low-RCS surface
    10: ( -7.0, 2.0),   # Lasy mieszane     – volume
}




class Config:
    # App Settings
    APP_NAME = "Satellite Radar Simulator"
    VERSION = "1.0.0"


class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False