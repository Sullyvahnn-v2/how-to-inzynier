from __future__ import annotations
import numpy as np
import matplotlib
try:
    matplotlib.use('TkAgg')
except Exception:
    pass
from src.Satelite import Satellite
from src.Scene import Scene
from src.config import Config, K_BOLTZ, C_LIGHT, SIGMA0_DB, SIGMA0_N
from src.loss import atmospheric_loss
from src.sar_mechanics import SARTrajectory, backproject, doppler_spectrum


# =============================================================================
# BACKSCATTER MODELS  --  sigma0 by land-cover class
# =============================================================================

def compute_sigma0(land_class:    np.ndarray,
                   theta_i:       np.ndarray,
                   theta_ref_deg: float = 38.0,
                   speckle:       bool  = True,
                   rng: np.random.Generator | None = None) -> np.ndarray:
    """
    Compute per-pixel sigma0 (linear, not dB).

    Angular correction (power-law cosine model):
        sigma0(theta) = sigma0(theta_ref) * [cos(theta)/cos(theta_ref)]^n

    Speckle model: fully-developed single-look speckle is exponentially
    distributed (Goodman 1976; Lee & Pottier 2009).

    Values from:
      - Sentinel-1 IW mode image statistics (ESA SNAP)
      - Ulaby et al. (1982) Microwave Remote Sensing, Vol. II, Ch. 11
      - Oh, Sarabandi & Ulaby (2004) IEEE TGRS (bare soil)
    """
    if rng is None:
        rng = np.random.default_rng(42)

    sigma0_dB = np.full(theta_i.shape, -30.0, dtype=np.float64)
    cos_ref   = np.cos(np.radians(theta_ref_deg))

    for cls, (mean_dB, std_dB) in SIGMA0_DB.items():
        mask = (land_class == cls)
        if not np.any(mask):
            continue
        n     = SIGMA0_N.get(cls, 1.5)
        noise = rng.normal(0.0, std_dB * 0.25, int(mask.sum()))
        cos_i = np.cos(theta_i[mask])
        with np.errstate(divide='ignore', invalid='ignore'):
            corr = 10 * n * np.log10(np.maximum(cos_i / cos_ref, 1e-6))
        sigma0_dB[mask] = mean_dB + noise + corr

    sigma0 = 10 ** (sigma0_dB / 10.0)
    if speckle:
        sigma0 *= rng.exponential(1.0, sigma0.shape)

    return np.maximum(sigma0, 1e-10)


# =============================================================================
# RADAR EQUATION  (Moreira et al. 2013)
# =============================================================================

def received_power(sat:     Satellite,
                   sigma0:  np.ndarray,
                   R:       np.ndarray,
                   theta_i: np.ndarray,
                   L_atm:   np.ndarray) -> np.ndarray:
    """
    Received power P_r [W].

    Moreira 2013, Eq. (22) -- distributed target:
        P_r = P_t * G^2 * lambda^2 * sigma0 * A_res
              / ((4*pi)^3 * R^4 * L_sys * L_atm)

    where  A_res = delta_r * delta_a / sin(theta_i)
    """
    A_res       = sat.range_resolution * sat.azimuth_resolution / np.sin(theta_i)
    numerator   = sat.tx_power * sat.antenna_gain**2 * sat.wavelength**2 * sigma0 * A_res
    denominator = (4 * np.pi)**3 * R**4 * sat.L_sys * L_atm
    return numerator / denominator


def noise_power(sat: Satellite) -> float:
    """P_n = k * T_sys * B  [W].  Moreira 2013, Eq. (24)."""
    return K_BOLTZ * sat.T_sys * sat.bandwidth


def snr(sat:     Satellite,
        sigma0:  np.ndarray,
        R:       np.ndarray,
        theta_i: np.ndarray,
        L_atm:   np.ndarray) -> np.ndarray:
    """SNR = P_r / P_n  (linear).  Moreira 2013, Eq. (25)."""
    return received_power(sat, sigma0, R, theta_i, L_atm) / noise_power(sat)


def nesz(sat:     Satellite,
         R:       np.ndarray,
         theta_i: np.ndarray,
         L_atm:   np.ndarray) -> np.ndarray:
    """
    Noise-Equivalent Sigma Zero.  Moreira 2013, Eq. (26):
        NESZ = (4pi)^3 * k * T_sys * B * R^3 * v_s * L_sys * L_atm
               / (P_t * G^2 * lambda^3 * c * tau_p * sin(theta_i))
    """
    num = ((4 * np.pi)**3 * K_BOLTZ * sat.T_sys * sat.bandwidth
           * R**3 * sat.velocity * sat.L_sys * L_atm)
    den = (sat.tx_power * sat.antenna_gain**2 * sat.wavelength**3
           * C_LIGHT * sat.pulse_duration * np.sin(theta_i))
    return num / den


# =============================================================================
# SAR RAYTRACER
# =============================================================================

class SARRaytracer:
    """
    SAR simulator on a DSM grid.

    run()          -- geometric/radiometric single-position simulation
    run_full_sar() -- full SAR: trajectory + coherent back-projection
    """

    def __init__(self,
                 scene:         Scene,
                 sat:           Satellite,
                 subsample:     int   = 8,
                 shadow_steps:  int   = 32,
                 incidence_ref: float = 38.0):
        self.scene         = scene
        self.sat           = sat
        self.subsample     = subsample
        self.shadow_steps  = shadow_steps
        self.incidence_ref = incidence_ref
        self.rng           = np.random.default_rng(42)

    # -------------------------------------------------------------------------
    def _downsample(self):
        s   = self.subsample
        dem = self.scene.dem[::s, ::s].copy()
        lc  = self.scene.land_cover[::s, ::s].copy()
        xs  = self.scene.x_coords[::s]
        ys  = self.scene.y_coords[::s]
        return dem, lc, xs, ys

    def _satellite_position(self, xs, ys, dem) -> np.ndarray:
        """Broadside satellite position (flat-Earth geometry)."""
        H        = self.sat.orbit_height
        theta_c  = np.radians(self.incidence_ref)
        d_ground = H * np.tan(theta_c)
        cx       = (xs[0] + xs[-1]) / 2.0
        cy       = (ys[0] + ys[-1]) / 2.0
        cz       = float(np.nanmedian(dem))
        sign     = +1.0 if self.sat.look_side == 'right' else -1.0
        return np.array([cx + sign * d_ground, cy, cz + H])

    def _geometry(self, XX, YY, ZZ, sat_pos, cell_m):
        """Slant range R and local incidence angle theta_i."""
        dx = sat_pos[0] - XX
        dy = sat_pos[1] - YY
        dz = sat_pos[2] - ZZ
        R     = np.sqrt(dx**2 + dy**2 + dz**2)
        r_hat = np.stack([dx / R, dy / R, dz / R], axis=-1)
        gy, gx = np.gradient(ZZ, cell_m, cell_m)
        nz     = np.ones_like(gx)
        nn     = np.sqrt(gx**2 + gy**2 + nz**2)
        n_hat  = np.stack([-gx / nn, -gy / nn, nz / nn], axis=-1)
        cos_t  = np.clip(np.einsum('...k,...k', r_hat, n_hat), 1e-3, 1.0)
        return R, np.arccos(cos_t)

    def _shadow_mask(self, dem, xs, ys, sat_pos) -> np.ndarray:
        """Ray-cast shadow detection."""
        nrows, ncols = dem.shape
        XX, YY   = np.meshgrid(xs, ys)
        nan_mask = np.isnan(dem)
        ZZ       = np.where(nan_mask, 0.0, dem)
        dx = sat_pos[0] - XX
        dy = sat_pos[1] - YY
        dz = sat_pos[2] - ZZ
        shadow    = np.zeros((nrows, ncols), dtype=bool)
        y_max, y_min = ys[0], ys[-1]
        x_min, x_max = xs[0], xs[-1]
        for t in np.linspace(0.05, 0.95, self.shadow_steps):
            px = XX + t * dx
            py = YY + t * dy
            pz = ZZ + t * dz
            ci = np.clip(np.round((px - x_min) / (x_max - x_min) * (ncols - 1)).astype(np.int32), 0, ncols - 1)
            ri = np.clip(np.round((y_max - py) / (y_max - y_min) * (nrows - 1)).astype(np.int32), 0, nrows - 1)
            dem_at = np.where(np.isnan(dem[ri, ci]), 0.0, dem[ri, ci])
            shadow |= dem_at > pz
        shadow |= nan_mask
        return shadow

    def _slant_range_image(self, sigma0, R, shadow, nrows, ncols):
        """Incoherent geometric slant-range projection."""
        valid = ~shadow & ~np.isnan(sigma0)
        if not np.any(valid):
            return np.full((nrows, ncols), np.nan), np.array([])
        R_min  = float(R[valid].min())
        R_max  = float(R[valid].max())
        n_bins = ncols
        bin_w  = (R_max - R_min) / n_bins
        ri, ci  = np.where(valid)
        bin_idx = np.clip(((R[ri, ci] - R_min) / bin_w).astype(np.int32), 0, n_bins - 1)
        sums    = np.zeros((nrows, n_bins))
        counts  = np.zeros((nrows, n_bins))
        np.add.at(sums,   (ri, bin_idx), sigma0[ri, ci])
        np.add.at(counts, (ri, bin_idx), 1.0)
        return np.where(counts > 0, sums / counts, np.nan), np.linspace(R_min, R_max, n_bins)

    # -------------------------------------------------------------------------
    # PHASE 1 -- geometric / radiometric
    # -------------------------------------------------------------------------

    def run(self) -> dict:
        """
        Single-position geometric/radiometric simulation.

        Implements:
          - Radar equation  (Moreira 2013, Eq. 22-26)
          - Atmospheric losses  (ITU-R P.676-12 Annex 2)
          - Backscatter sigma0  per land-cover class + angular correction
          - Terrain shadow detection via ray-casting
          - Incoherent slant-range image (geometric projection)
        """
        print("[SAR] -- Subsampling scene...")
        dem, lc, xs, ys = self._downsample()
        nrows, ncols    = dem.shape
        nan_mask        = np.isnan(dem)
        ZZ              = np.where(nan_mask, 0.0, dem)
        cell_m          = self.scene.cellsize * self.subsample
        XX, YY          = np.meshgrid(xs, ys)

        print(f"[SAR]    Grid: {nrows}x{ncols} @ {cell_m:.1f} m/px")

        sat_pos = self._satellite_position(xs, ys, ZZ)
        print(f"[SAR]    Broadside: dx={sat_pos[0]-XX.mean():.0f} m, z={sat_pos[2]/1e3:.1f} km")

        print("[SAR] -- Geometry (R, theta_i)...")
        R, theta_i = self._geometry(XX, YY, ZZ, sat_pos, cell_m)
        elev_deg   = 90.0 - np.degrees(theta_i)

        print("[SAR] -- Shadow detection...")
        shadow = self._shadow_mask(dem, xs, ys, sat_pos)
        print(f"[SAR]    Shadow: {100*shadow.mean():.1f}%")

        print("[SAR] -- Atmospheric losses (ITU-R P.676-12)...")
        L_atm = atmospheric_loss(elev_deg, self.sat)

        print("[SAR] -- Backscatter sigma0...")
        sigma0_arr           = compute_sigma0(lc, theta_i, self.incidence_ref, rng=self.rng)
        sigma0_arr[shadow]   = 0.0
        sigma0_arr[nan_mask] = np.nan

        print("[SAR] -- SNR & NESZ...")
        theta_s  = np.where(nan_mask | shadow, np.radians(self.incidence_ref), theta_i)
        R_s      = np.where(nan_mask | shadow, float(np.nanmedian(R)), R)
        s0_s     = np.where(np.isfinite(sigma0_arr) & ~shadow, sigma0_arr, 1e-10)

        snr_arr  = snr(self.sat, s0_s, R_s, theta_s, L_atm)
        nesz_arr = nesz(self.sat, R_s, theta_s, L_atm)
        snr_arr[shadow | nan_mask] = np.nan
        nesz_arr[nan_mask]         = np.nan

        print("[SAR] -- Slant-range image (incoherent)...")
        sar_img, range_ax = self._slant_range_image(sigma0_arr, R, shadow, nrows, ncols)

        print("[SAR] -- Done.")
        with np.errstate(divide='ignore', invalid='ignore'):
            return dict(
                dem=dem, land_cover=lc, xs=xs, ys=ys,
                XX=XX, YY=YY, ZZ=ZZ,
                sat_pos=sat_pos,
                theta_i=theta_i,
                theta_i_deg=np.degrees(theta_i),
                slant_range=R,
                shadow=shadow,
                sigma0=sigma0_arr,
                sigma0_dB=10*np.log10(np.where(sigma0_arr > 0, sigma0_arr, np.nan)),
                snr=snr_arr,
                snr_dB=10*np.log10(snr_arr),
                nesz=nesz_arr,
                nesz_dB=10*np.log10(nesz_arr),
                L_atm=L_atm,
                L_atm_dB=10*np.log10(L_atm),
                sar_image=sar_img,
                range_axis=range_ax,
            )

    # -------------------------------------------------------------------------
    # PHASE 2 -- full SAR (trajectory + back-projection)
    # -------------------------------------------------------------------------

    def run_full_sar(self, n_positions: int = 128) -> dict:
        """
        Full SAR image formation via coherent back-projection.

        SAR mechanics (Moreira 2013)
        ----------------------------
        (a) Satellite flies along azimuth (y-axis) at constant height H.
            Positions: sat_y(t_a) = y_0 + v_s * t_a,  t_a in [-T_int/2, T_int/2]

        (b) Synthetic aperture length:
                L_synth = lambda * R_0 / L_a                    [m]

        (c) Integration time:
                T_int = L_synth / v_s                           [s]

        (d) Range history per pixel (x, y, z) at position n:
                R_n = sqrt((x_n - x)^2 + (y_n - y)^2 + (z_n - z)^2)

        (e) Azimuth beam weight (two-way sinc^2, Moreira Eq. 2):
                w_n = sinc^2(arcsin(dy/R_n) / theta_az)
                theta_az = lambda / L_a

        (f) Distributed-target complex reflectivity (Goodman 1976):
                f(x,y) = sqrt(sigma0) * exp(j * phi_random),
                phi_random ~ Uniform[0, 2*pi)

        (g) Back-projection with differential phase (azimuth matched filter):
                I(x,y) = (1/N) * sum_n  f(x,y) * w_n * exp(-j*4*pi*(R_n - R_0)/lambda)

        Parameters
        ----------
        n_positions : aperture positions to simulate (default 128)

        Returns
        -------
        All run() fields plus:
            trajectory    : SARTrajectory
            sar_complex   : complex SAR image [nrows, ncols]
            sar_amplitude : |sar_complex|
            sar_power     : |sar_complex|^2
            sar_phase     : arg(sar_complex) [rad]
            sar_dB        : 10*log10(sar_power) [dB]
            doppler_info  : Doppler spectrum dict for scene centre
        """
        print("\n[SAR] ===== PHASE 1: geometric / radiometric =====")
        results = self.run()

        XX, YY, ZZ = results['XX'], results['YY'], results['ZZ']
        shadow     = results['shadow']
        sigma0     = results['sigma0']
        sat_pos    = results['sat_pos']

        # ── Build trajectory ──────────────────────────────────────────────────
        print("\n[SAR] ===== PHASE 2: SAR trajectory ==================")

        R_0 = float(np.nanmedian(results['slant_range'][~shadow]))

        traj = SARTrajectory(
            sat         = self.sat,
            nadir_x     = sat_pos[0],
            center_y    = sat_pos[1],
            sat_z       = sat_pos[2],
            R_0         = R_0,
            n_positions = n_positions,
        )

        print(f"[SAR]    R_0                 : {R_0/1e3:.1f} km")
        print(f"[SAR]    L_synth             : {traj.L_synth:.0f} m")
        print(f"[SAR]    T_int               : {traj.T_int:.3f} s")
        print(f"[SAR]    PRF pulses / aperture: {traj.N_pulses}")
        print(f"[SAR]    Doppler rate K_a    : {traj.K_a:.2f} Hz/s")
        print(f"[SAR]    Doppler BW B_D      : {traj.B_D:.1f} Hz")
        print(f"[SAR]    Azimuth resolution  : {self.sat.azimuth_resolution:.2f} m")
        print(f"[SAR]    Simulated positions : {n_positions}")

        # Doppler spectrum for scene centre (diagnostics)
        doppler_info = doppler_spectrum(
            traj,
            float(XX.mean()), float(YY.mean()), float(ZZ.mean())
        )

        # ── Coherent back-projection ──────────────────────────────────────────
        print("\n[SAR] ===== PHASE 3: coherent back-projection ========")

        with np.errstate(invalid='ignore'):
            sigma0_amp = np.sqrt(np.where(
                np.isfinite(sigma0) & ~shadow, sigma0, 0.0
            ))

        sar_complex = backproject(
            XX, YY, ZZ,
            sigma0_amp,
            traj,
            shadow,
            self.rng,
            verbose=True,
        )

        sar_power = np.abs(sar_complex) ** 2
        with np.errstate(divide='ignore', invalid='ignore'):
            sar_dB = 10 * np.log10(np.where(sar_power > 0, sar_power, np.nan))

        print("[SAR] ===== Done. =====================================\n")

        results.update(dict(
            trajectory   = traj,
            sar_complex  = sar_complex,
            sar_amplitude= np.abs(sar_complex),
            sar_power    = sar_power,
            sar_phase    = np.angle(sar_complex),
            sar_dB       = sar_dB,
            doppler_info = doppler_info,
        ))

        return results

# TODO: polarymetria
#TODO: testy
# TODO: rozne czestotlwosci