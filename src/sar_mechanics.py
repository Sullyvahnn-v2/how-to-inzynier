"""
src/sar_mechanics.py
====================
SAR image-formation mechanics based on:

  Moreira, A. et al. (2013) "A Tutorial on Synthetic Aperture Radar",
  IEEE Geoscience and Remote Sensing Magazine, 1(1), 6-43.
  DOI: 10.1109/MGRS.2013.2248301

Key equations implemented
--------------------------
  (1) Range history          R(t_a) = sqrt(R_0^2 + v_s^2 * t_a^2)
  (2) Doppler centroid       f_dc = -2*v_s*sin(theta_sq) / lambda
  (3) Doppler rate           K_a  = -2*v_s^2 / (lambda * R_0)
  (4) Azimuth beam weight    w_a  = sinc^2(psi / theta_az)          two-way
  (5) Two-way phase          phi  = -4*pi*R / lambda
  (6) Back-projection        I(x,y) = sum_n  s_n * w_n * exp(+j*4*pi*R_n/lambda)

Distributed target (speckle) model  (Goodman 1976):
  Each resolution cell has random uniform phase in [0, 2*pi).
  Amplitude = sqrt(sigma0) * exp(j * phi_random)
"""

from __future__ import annotations
import numpy as np
from src.Satelite import Satellite
from src.config import C_LIGHT


# ---------------------------------------------------------------------------
# 1.  SATELLITE TRAJECTORY
# ---------------------------------------------------------------------------

class SARTrajectory:
    """
    Linear satellite flight path used to synthesize a large aperture.

    The satellite flies in the azimuth (+y) direction at constant height.
    The scene is illuminated from the side (right-looking by default).

    Synthetic aperture theory (Moreira 2013, Eq. 7-9)
    --------------------------------------------------
    Synthetic aperture length:
        L_synth = lambda * R_0 / L_a                     [m]

    Integration (dwell) time:
        T_int = L_synth / v_s  =  lambda * R_0 / (v_s * L_a)   [s]

    Number of PRF pulses in the aperture:
        N_pulses = T_int * PRF

    Azimuth resolution after focusing:
        delta_az = L_a / 2                               [m]   (stripmap)

    Parameters
    ----------
    sat         : Satellite dataclass
    nadir_x     : x-coordinate of the satellite nadir track [m, EPSG:2180]
    center_y    : y-coordinate of the scene centre [m]
    sat_z       : satellite altitude (z) [m]
    R_0         : slant range to scene centre at broadside position [m]
    n_positions : number of aperture positions to simulate
                  (actual pulses = N_pulses; we use fewer for speed)
    """

    def __init__(self,
                 sat:          Satellite,
                 nadir_x:      float,
                 center_y:     float,
                 sat_z:        float,
                 R_0:          float,
                 n_positions:  int = 128):

        self.sat         = sat
        self.R_0         = R_0
        self.n_positions = n_positions

        # ── Aperture parameters (Moreira 2013, Sec. II) ──────────────────────
        lam              = sat.wavelength
        La               = sat.antenna_length

        self.L_synth     = lam * R_0 / La                # synthetic aperture [m]
        self.T_int       = self.L_synth / sat.velocity    # integration time   [s]
        self.N_pulses    = int(round(self.T_int * sat.prf))  # actual pulses
        self.K_a         = -2.0 * sat.velocity**2 / (lam * R_0)  # Doppler rate [Hz/s]
        self.B_D         = abs(self.K_a) * self.T_int     # Doppler bandwidth  [Hz]
        self.f_dc        = 0.0                            # zero squint assumed

        # ── Slow-time axis (azimuth time) ────────────────────────────────────
        # t_a = 0 at broadside (closest approach)
        self.t_a = np.linspace(-self.T_int / 2.0,
                                self.T_int / 2.0,
                                n_positions)  # [s]

        # ── Satellite positions  [N, 3]  (x, y, z) ───────────────────────────
        y_track = center_y + sat.velocity * self.t_a
        self._positions = np.column_stack([
            np.full(n_positions, nadir_x),
            y_track,
            np.full(n_positions, sat_z),
        ])

    # ------------------------------------------------------------------
    @property
    def positions(self) -> np.ndarray:
        """Satellite positions along the flight track  [N, 3]."""
        return self._positions

    # ------------------------------------------------------------------
    def range_history(self,
                      gx: np.ndarray | float,
                      gy: np.ndarray | float,
                      gz: np.ndarray | float) -> np.ndarray:
        """
        Instantaneous slant range from each aperture position to a target.

        Exact formula (Moreira 2013, Eq. 1 exact):
            R_n = || sat_pos_n - target ||

        Hyperbolic approximation (same paper, Eq. 1):
            R(t_a) = sqrt(R_0^2 + v_s^2 * t_a^2)

        Both are returned; exact is used in back-projection for accuracy.

        Parameters
        ----------
        gx, gy, gz : target coordinates [m]  (scalars or arrays)

        Returns
        -------
        R_exact  : [N] exact slant-range history [m]
        """
        dx = self._positions[:, 0] - gx   # [N]  or broadcast [N, ...] if arrays
        dy = self._positions[:, 1] - gy
        dz = self._positions[:, 2] - gz
        return np.sqrt(dx**2 + dy**2 + dz**2)

    # ------------------------------------------------------------------
    def doppler_history(self,
                        gx: float, gy: float, gz: float) -> np.ndarray:
        """
        Instantaneous Doppler frequency [Hz] for a point target.

        f_D(t_a) = -2/lambda * dR/dt_a
                 = -2 * v_s * (y_sat - y_tgt) / (lambda * R(t_a))

        Moreira 2013, Eq. (3).
        """
        R_h = self.range_history(gx, gy, gz)
        dy  = self._positions[:, 1] - gy
        return -2.0 * self.sat.velocity * dy / (self.sat.wavelength * R_h)

    # ------------------------------------------------------------------
    def azimuth_beam_weight(self,
                             XX: np.ndarray,
                             YY: np.ndarray,
                             ZZ: np.ndarray,
                             sat_pos: np.ndarray) -> np.ndarray:
        """
        Two-way azimuth antenna beam-pattern weight for a single aperture
        position `sat_pos` evaluated over the whole DEM grid.

        3-dB one-way beamwidth:
            theta_az = lambda / L_a   [rad]

        Azimuth squint angle to each pixel:
            psi = arctan2(y_sat - y_pixel, R_ground)

        Two-way sinc^2 pattern (Moreira 2013, Eq. 2 / Ulaby 1982 Vol. I):
            w_a = sinc^2(psi / theta_az)

        Parameters
        ----------
        XX, YY, ZZ : ground pixel meshgrids  [nrows, ncols]
        sat_pos    : satellite position  [3]

        Returns
        -------
        w_a : beam weight  [nrows, ncols],  in [0, 1]
        """
        theta_az = self.sat.wavelength / self.sat.antenna_length   # 3-dB bw [rad]

        dx = sat_pos[0] - XX
        dy = sat_pos[1] - YY
        dz = sat_pos[2] - ZZ

        R_total = np.sqrt(dx**2 + dy**2 + dz**2)
        # Squint angle in the azimuth plane
        psi = np.arcsin(np.clip(dy / R_total, -1.0, 1.0))

        u   = psi / theta_az           # normalised angle
        w_a = np.sinc(u) ** 2          # two-way sinc^2
        return w_a


# ---------------------------------------------------------------------------
# 2.  BACK-PROJECTION IMAGE FORMATION
# ---------------------------------------------------------------------------

def backproject(XX:          np.ndarray,
                YY:          np.ndarray,
                ZZ:          np.ndarray,
                sigma0_amp:  np.ndarray,
                traj:        SARTrajectory,
                shadow:      np.ndarray,
                rng:         np.random.Generator,
                verbose:     bool = True) -> np.ndarray:
    """
    Time-domain back-projection SAR image formation.

    The result is a focused, complex-valued SAR image where:
      - |I|   is the focused amplitude   (proportional to sqrt(sigma0))
      - |I|^2 is the detected intensity  (proportional to sigma0)
      - arg(I) is the interferometric phase (arbitrary for single image)

    Parameters
    ----------
    XX, YY, ZZ   : ground-pixel coordinate meshgrids  [nrows, ncols]
    sigma0_amp   : backscatter amplitude  sqrt(sigma0)  [nrows, ncols]
    traj         : SARTrajectory object
    shadow       : shadow mask (True = no illumination)  [nrows, ncols]
    rng          : random-number generator for target phase
    verbose      : print progress

    Returns
    -------
    sar_complex  : focused complex SAR image  [nrows, ncols]
    """
    nrows, ncols  = XX.shape
    sat_positions = traj.positions          # [N, 3]
    lam           = traj.sat.wavelength
    theta_az      = lam / traj.sat.antenna_length   # 3-dB azimuth beamwidth [rad]
    N             = len(sat_positions)

    # ── Complex reflectivity field (distributed-target model) ────────────────
    # Each pixel has a random phase drawn from Uniform[0, 2*pi) per Goodman 1976
    phi_rnd  = rng.uniform(0.0, 2.0 * np.pi, (nrows, ncols))
    # Suppress shadowed / NaN pixels
    amp      = np.where(shadow | ~np.isfinite(sigma0_amp), 0.0, sigma0_amp)
    reflectivity = amp * np.exp(1j * phi_rnd)   # complex reflectivity  [nrows, ncols]

    # ── Coherent accumulation (back-projection loop) ──────────────────────────
    sar_complex = np.zeros((nrows, ncols), dtype=np.complex128)
    R_ref       = traj.R_0      # reference range for differential phase

    report_every = max(1, N // 8)

    for i, sat_pos in enumerate(sat_positions):
        # -- Slant range from this aperture position to every pixel  [nrows, ncols]
        dx  = sat_pos[0] - XX
        dy  = sat_pos[1] - YY
        dz  = sat_pos[2] - ZZ
        R_n = np.sqrt(dx**2 + dy**2 + dz**2)

        # -- Two-way azimuth beam weight  (sinc^2, Moreira 2013 Eq. 2) --------
        psi_n = np.arcsin(np.clip(dy / R_n, -1.0, 1.0))   # squint angle
        u_n   = psi_n / theta_az                            # normalised
        w_n   = np.sinc(u_n) ** 2                           # two-way sinc^2

        # -- Differential range phase (azimuth matched filter) ----------------
        # phi_diff = -4*pi*(R_n - R_ref) / lambda
        # This is the phase of the azimuth chirp reference function
        phi_diff = -4.0 * np.pi * (R_n - R_ref) / lam

        # -- Coherent back-projection contribution ----------------------------
        # delta_I = reflectivity * w_n * exp(j * phi_diff)
        # [Reference: Cumming & Wong 2005, Eq. 4.5; Moreira 2013 Sec. IV-C]
        sar_complex += reflectivity * w_n * np.exp(1j * phi_diff)

        if verbose and (i + 1) % report_every == 0:
            print(f"[BP]    position {i+1:3d}/{N}  "
                  f"(y_sat = {sat_pos[1]/1e3:.2f} km)")

    # Normalise by number of positions (makes amplitude independent of N)
    sar_complex /= N

    return sar_complex


# ---------------------------------------------------------------------------
# 3.  DOPPLER SPECTRUM ANALYSIS  (diagnostic)
# ---------------------------------------------------------------------------

def doppler_spectrum(traj: SARTrajectory,
                     gx: float, gy: float, gz: float) -> dict:
    """
    Compute the Doppler frequency history and spectrum for a point target.

    Returns a dict with:
      t_a   : slow-time axis [s]
      f_D   : Doppler frequency history [Hz]
      phase : two-way phase history [rad]
      R_n   : range history [m]
    """
    R_n = traj.range_history(gx, gy, gz)
    f_D = traj.doppler_history(gx, gy, gz)
    phi = -4.0 * np.pi * R_n / traj.sat.wavelength

    # Quadratic (azimuth chirp) approximation
    # phi_quad = -4*pi*R_0/lambda  - pi*K_a*(t_a)^2
    phi_quad = (-4.0 * np.pi * traj.R_0 / traj.sat.wavelength
                - np.pi * traj.K_a * traj.t_a**2)

    return dict(
        t_a=traj.t_a,
        R_n=R_n,
        f_D=f_D,
        phase_exact=phi,
        phase_quad=phi_quad,
        K_a=traj.K_a,
        B_D=traj.B_D,
        L_synth=traj.L_synth,
        T_int=traj.T_int,
        N_pulses=traj.N_pulses,
    )
