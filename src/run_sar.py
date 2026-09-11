# -*- coding: utf-8 -*-
"""
run_sar.py  --  entry point for the SAR satellite radar simulator.

Usage:
    python run_sar.py                        # default Sentinel-1, subsample=8
    python run_sar.py --subsample 4          # higher resolution (slower)
    python run_sar.py --n_pos 64             # fewer aperture positions (faster)
    python run_sar.py --no_sar               # skip back-projection (phase 1 only)

Data files expected in working directory:
    land_height.asc  --  DSM from Geoportal WCS (via get_data.py)
    land_cover.png   --  Land-cover raster    (via get_data.py)
"""

import argparse
import sys
import numpy as np
import matplotlib
try:
    matplotlib.use('TkAgg')
except Exception:
    pass
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

from src.Scene import load_scene
from src.Satelite import Satellite
from src.config import sentinel1_parameters, LAND_COVER_NAMES, K_BOLTZ
from src.loss import _specific_attenuation_dBpkm
from sar_simulator import SARRaytracer, noise_power


# =============================================================================
# VISUALIZATION
# =============================================================================

_BG     = '#0d1117'
_PANEL  = '#161b22'
_BORDER = '#30363d'
_FG     = '#e6edf3'
_MUTED  = '#8b949e'
_ACCENT = '#58a6ff'

_LC_COLORS = [
    '#c83232', '#e6d282', '#b4a050', '#96dc64', '#006418',
    '#3cb43c', '#3264dc', '#784eb4', '#dcdcdc', '#648c3c',
]


def _style_ax(ax, title):
    ax.set_facecolor(_PANEL)
    ax.tick_params(colors=_MUTED, labelsize=7)
    for sp in ax.spines.values():
        sp.set_color(_BORDER)
    ax.set_title(title, color=_FG, fontsize=8.5, pad=4, fontweight='bold')
    return ax


def _cbar(fig, im, ax, label):
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(label, color=_MUTED, fontsize=7)
    cb.ax.yaxis.set_tick_params(color=_MUTED, labelsize=6.5)
    cb.outline.set_edgecolor(_BORDER)
    return cb


def visualize_phase1(results: dict, sat: Satellite, out: str = 'sar_phase1.png'):
    """3x3 diagnostic figure for the geometric/radiometric simulation."""
    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig = plt.figure(figsize=(22, 15))
    fig.patch.set_facecolor(_BG)
    gs  = fig.add_gridspec(3, 3, hspace=0.42, wspace=0.32,
                           left=0.05, right=0.97, top=0.93, bottom=0.04)

    # 1 -- DSM
    ax = _style_ax(fig.add_subplot(gs[0, 0]), "Digital Surface Model (DSM)")
    im = ax.imshow(results['dem'], cmap='terrain', origin='upper')
    _cbar(fig, im, ax, 'Height [m]')

    # 2 -- land cover
    ax2 = _style_ax(fig.add_subplot(gs[0, 1]), "Land cover (10 classes)")
    lc_cmap = mcolors.ListedColormap(_LC_COLORS)
    im2 = ax2.imshow(results['land_cover'], cmap=lc_cmap,
                     vmin=0.5, vmax=10.5, origin='upper')
    cb2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04, ticks=range(1, 11))
    cb2.ax.set_yticklabels([LAND_COVER_NAMES[i] for i in range(1, 11)], fontsize=5.5)
    cb2.ax.yaxis.set_tick_params(color=_MUTED)
    cb2.outline.set_edgecolor(_BORDER)

    # 3 -- shadow
    ax3 = _style_ax(fig.add_subplot(gs[0, 2]), "SAR shadow mask")
    ax3.imshow(np.where(results['shadow'], 0, 1),
               cmap='gray', origin='upper', vmin=0, vmax=1)
    ax3.legend(handles=[
        mpatches.Patch(color='white', label='Lit'),
        mpatches.Patch(color='black', label='Shadow'),
    ], fontsize=7, facecolor=_PANEL, edgecolor=_BORDER, labelcolor=_FG, loc='lower right')

    # 4 -- sigma0
    ax4 = _style_ax(fig.add_subplot(gs[1, 0]), "Backscatter sigma0 [dB]")
    s0   = results['sigma0_dB']
    v    = ~results['shadow'] & np.isfinite(s0)
    vlo, vhi = (np.percentile(s0[v], [2, 98]) if v.any() else (-25, 0))
    im4  = ax4.imshow(s0, cmap='plasma', origin='upper', vmin=vlo, vmax=vhi)
    _cbar(fig, im4, ax4, 'sigma0 [dB]')

    # 5 -- SNR
    ax5  = _style_ax(fig.add_subplot(gs[1, 1]), "SNR [dB]")
    snr  = results['snr_dB']
    fin  = np.isfinite(snr)
    vlo5, vhi5 = (np.percentile(snr[fin], [2, 98]) if fin.any() else (-10, 20))
    im5  = ax5.imshow(snr, cmap='RdYlGn', origin='upper', vmin=vlo5, vmax=vhi5)
    _cbar(fig, im5, ax5, 'SNR [dB]')

    # 6 -- Atmospheric loss
    ax6 = _style_ax(fig.add_subplot(gs[1, 2]), "Atmospheric loss L_atm [dB] (2-way)")
    im6 = ax6.imshow(results['L_atm_dB'], cmap='YlOrRd', origin='upper')
    _cbar(fig, im6, ax6, 'L_atm [dB]')

    # 7 -- Incoherent slant-range image
    ax7 = _style_ax(fig.add_subplot(gs[2, :2]),
                    "Incoherent slant-range image (geometric projection, log scale)")
    sar = results['sar_image']
    with np.errstate(divide='ignore', invalid='ignore'):
        sar_log = 10 * np.log10(np.where(sar > 0, sar, np.nan))
    fin2 = np.isfinite(sar_log)
    vls, vhs = (np.percentile(sar_log[fin2], [1, 99]) if fin2.any() else (-25, 0))
    ax7.imshow(sar_log, cmap='gray', origin='upper', aspect='auto', vmin=vls, vmax=vhs)
    ax7.set_xlabel('Slant Range [bin]', color=_MUTED, fontsize=8)
    ax7.set_ylabel('Azimuth [line]',   color=_MUTED, fontsize=8)

    # 8 -- System parameters text box
    ax8 = _style_ax(fig.add_subplot(gs[2, 2]), "System parameters")
    ax8.axis('off')
    gamma   = _specific_attenuation_dBpkm(sat.frequency / 1e9)
    pn_dBm  = 10 * np.log10(noise_power(sat) / 1e-3)
    nesz_v  = results['nesz_dB']
    snr_v   = results['snr_dB']
    info = (
        "  SATELLITE PARAMETERS\n"
        f"  Frequency  : {sat.frequency/1e9:.3f} GHz\n"
        f"  lambda     : {sat.wavelength*100:.2f} cm\n"
        f"  H_orbit    : {sat.orbit_height/1e3:.0f} km\n"
        f"  Tx power   : {sat.tx_power:.0f} W\n"
        f"  Gain G     : {sat.antenna_gain_dB:.1f} dB\n"
        f"  Bandwidth  : {sat.bandwidth/1e6:.0f} MHz\n"
        f"  Antenna    : {sat.antenna_length}x{sat.antenna_height} m\n"
        f"  T_sys      : {sat.T_sys:.0f} K\n"
        f"  Noise P_n  : {pn_dBm:.1f} dBm\n"
        f"  NF         : {sat.noise_figure:.1f} dB\n"
        f"  L_sys      : {sat.losses_system:.1f} dB\n"
        "\n  RESULTS\n"
        f"  delta_r    : {sat.range_resolution:.2f} m\n"
        f"  delta_az   : {sat.azimuth_resolution:.2f} m\n"
        f"  NESZ (med) : {np.nanmedian(nesz_v):.1f} dB\n"
        f"  SNR  (med) : {np.nanmedian(snr_v[np.isfinite(snr_v)]):.1f} dB\n"
        f"  gamma_gas  : {gamma:.4f} dB/km\n"
        f"  Shadow     : {100*results['shadow'].mean():.1f}%\n"
    )
    ax8.text(0.03, 0.97, info, transform=ax8.transAxes,
             fontsize=7.5, va='top', fontfamily='monospace', color=_FG,
             bbox=dict(boxstyle='round,pad=0.5', fc='#1c2128', ec=_ACCENT, lw=1.2))

    fig.suptitle(
        "SAR Simulator  --  Phase 1: Geometric/Radiometric  |  Moreira 2013 + ITU-R P.676-12",
        color=_ACCENT, fontsize=12, fontweight='bold', y=0.975
    )
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=_BG)
    print(f"[Viz] Saved -> {out}")
    plt.show()


def visualize_sar_focused(results: dict, sat: Satellite, out: str = 'sar_focused.png'):
    """
    Focused SAR image figure (Phase 2 output).

    Layout
    ------
    Row 0:  [SAR amplitude dB (focused)]  [SAR phase]  [Trajectory + scene]
    """

    plt.rcParams['font.family'] = 'DejaVu Sans'
    fig   = plt.figure(figsize=(22, 16))
    fig.patch.set_facecolor(_BG)
    gs    = fig.add_gridspec(1, 2, hspace=0.44, wspace=0.32,
                             left=0.05, right=0.97, top=0.93, bottom=0.04)

    # ── Row 0: SAR focused image ──────────────────────────────────────────────
    # 1 -- focused amplitude [dB]
    ax1 = _style_ax(fig.add_subplot(gs[0, :2]),
                    "Focused SAR image -- coherent back-projection (amplitude [dB])")
    sar_dB = results['sar_dB']
    fin    = np.isfinite(sar_dB)
    vlo, vhi = (np.percentile(sar_dB[fin], [2, 98]) if fin.any() else (-60, 0))
    im1  = ax1.imshow(sar_dB, cmap='gray', origin='upper', vmin=vlo, vmax=vhi)
    _cbar(fig, im1, ax1, '[dB]')
    ax1.set_xlabel('Range [pixel]',  color=_MUTED, fontsize=8)
    ax1.set_ylabel('Azimuth [line]', color=_MUTED, fontsize=8)

    # 2 -- SAR phase
    # ax2 = _style_ax(fig.add_subplot(gs[0, 1]), "SAR phase [rad]")
    # im2 = ax2.imshow(results['sar_phase'], cmap='hsv', origin='upper',
    #                  vmin=-np.pi, vmax=np.pi)
    # _cbar(fig, im2, ax2, '[rad]')

    fig.suptitle(
        "SAR Simulator  --  Phase 2: Coherent Back-Projection  |  Moreira 2013 IEEE GRSM",
        color=_ACCENT, fontsize=12, fontweight='bold', y=0.975
    )
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=_BG)
    print(f"[Viz] Saved -> {out}")
    plt.show()


# =============================================================================
# MAIN
# =============================================================================

def print_banner(sat: Satellite) -> None:
    gamma  = _specific_attenuation_dBpkm(sat.frequency / 1e9)
    pn_dBm = 10 * np.log10(noise_power(sat) / 1e-3)
    print(
        "+--------------------------------------------------------------+\n"
        "|         SAR Satellite Radar Simulator                        |\n"
        "|  Moreira et al. (2013) + ITU-R P.676-12 + Geoportal DSM    |\n"
        "+--------------------------------------------------------------+"
    )
    print(f"  Frequency    : {sat.frequency/1e9:.3f} GHz  (lambda = {sat.wavelength*100:.2f} cm)")
    print(f"  Orbit height : {sat.orbit_height/1e3:.0f} km")
    print(f"  Velocity     : {sat.velocity:.1f} m/s")
    print(f"  Antenna      : {sat.antenna_length} x {sat.antenna_height} m")
    print(f"  Gain G       : {sat.antenna_gain_dB:.1f} dB")
    print(f"  Tx power     : {sat.tx_power:.0f} W")
    print(f"  Bandwidth    : {sat.bandwidth/1e6:.0f} MHz")
    print(f"  Range res.   : {sat.range_resolution:.2f} m")
    print(f"  Azimuth res. : {sat.azimuth_resolution:.2f} m")
    print(f"  T_sys        : {sat.T_sys:.0f} K  (NF {sat.noise_figure:.1f} dB)")
    print(f"  Noise power  : {pn_dBm:.1f} dBm")
    print(f"  Atm. atten.  : {gamma:.4f} dB/km  (one-way, C-band)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="SAR satellite radar simulator")
    parser.add_argument("--dem",       default="land_height.asc")
    parser.add_argument("--lc",        default="land_cover.png")
    parser.add_argument("--subsample", type=int,   default=8)
    parser.add_argument("--shadows",   type=int,   default=32)
    parser.add_argument("--n_pos",     type=int,   default=128,
                        help="Number of aperture positions for back-projection")
    parser.add_argument("--no_sar",    action="store_true",
                        help="Skip Phase 2 (back-projection); only run Phase 1")
    args = parser.parse_args()

    sat = Satellite(sentinel1_parameters)
    print_banner(sat)

    # Load scene
    scene = load_scene(args.dem, args.lc)

    # Run
    rt = SARRaytracer(
        scene         = scene,
        sat           = sat,
        subsample     = args.subsample,
        shadow_steps  = args.shadows,
        incidence_ref = 38.0,
    )

    if args.no_sar:
        results = rt.run()
        visualize_phase1(results, sat, 'sar_phase1.png')
    else:
        results = rt.run_full_sar(n_positions=args.n_pos)

        # Print stats
        snr_dB  = results['snr_dB']
        nesz_dB = results['nesz_dB']
        sar_dB  = results['sar_dB']
        print("-- Simulation summary -------------------------------------------")
        print(f"  Shadow           : {100*results['shadow'].mean():.1f}%")
        if np.isfinite(snr_dB).any():
            print(f"  SNR  P5/50/95    : "
                  f"{np.nanpercentile(snr_dB,5):.1f} / "
                  f"{np.nanmedian(snr_dB):.1f} / "
                  f"{np.nanpercentile(snr_dB,95):.1f} dB")
        if np.isfinite(nesz_dB).any():
            print(f"  NESZ (median)    : {np.nanmedian(nesz_dB):.1f} dB")
        if np.isfinite(sar_dB).any():
            print(f"  SAR amp P5/50/95 : "
                  f"{np.nanpercentile(sar_dB[np.isfinite(sar_dB)],5):.1f} / "
                  f"{np.nanmedian(sar_dB[np.isfinite(sar_dB)]):.1f} / "
                  f"{np.nanpercentile(sar_dB[np.isfinite(sar_dB)],95):.1f} dB")
        traj = results['trajectory']
        print(f"  L_synth          : {traj.L_synth:.0f} m")
        print(f"  T_int            : {traj.T_int:.3f} s")
        print(f"  N_pulses (real)  : {traj.N_pulses}")
        print(f"  Doppler BW B_D   : {traj.B_D:.1f} Hz")
        print(f"  Doppler rate K_a : {traj.K_a:.2f} Hz/s")

        visualize_phase1(results, sat, 'sar_phase1.png')
        visualize_sar_focused(results, sat, 'sar_focused.png')


if __name__ == "__main__":
    main()
