from __future__ import annotations
import numpy as np
import matplotlib
try:
    matplotlib.use('TkAgg')
except Exception:
    pass   # fall back to whatever is available
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from src.Satelite import Satellite
from src.loss import  _specific_attenuation
from matplotlib.axes import Axes
from src.config import LAND_COVER_NAMES

_LC_COLOURS = [
    '#c83232', '#e6d282', '#b4a050', '#96dc64', '#006418',
    '#3cb43c', '#3264dc', '#784eb4', '#dcdcdc', '#648c3c',
]

_DARK_BG   = '#0d1117'
_PANEL_BG  = '#161b22'
_BORDER    = '#30363d'
_TEXT_FG   = '#e6edf3'
_TEXT_MUT  = '#8b949e'
_ACCENT    = '#58a6ff'


def _ax_style(ax: Axes, title: str) -> Axes:
    ax.set_facecolor(_PANEL_BG)
    ax.tick_params(colors=_TEXT_MUT, labelsize=7.5)
    for spine in ax.spines.values():
        spine.set_color(_BORDER)
    ax.set_title(title, color=_TEXT_FG, fontsize=8.5, pad=5, fontweight='bold')
    return ax


def _colorbar(fig, im, ax, label: str):
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(label, color=_TEXT_MUT, fontsize=7)
    cb.ax.yaxis.set_tick_params(color=_TEXT_MUT, labelsize=7)
    cb.outline.set_edgecolor(_BORDER)
    return cb


def visualize(results: dict, sat: Satellite,
              output_path: str = "sar_output.png") -> str:
    """
    Produce a 3×3 diagnostic figure:

        [DSM]          [Land cover]     [Shadow mask]
        [σ⁰ map dB]   [SNR map dB]     [Atm. loss dB]
        [SAR image  (slant-range, 2 columns wide)]   [System params]
    """
    plt.rcParams.update({
        'font.family': 'DejaVu Sans',
        'axes.edgecolor': _BORDER,
    })

    fig = plt.figure(figsize=(22, 15))
    fig.patch.set_facecolor(_DARK_BG)
    gs  = fig.add_gridspec(3, 3, hspace=0.42, wspace=0.32,
                            left=0.05, right=0.97, top=0.93, bottom=0.04)

    # ── 1. DSM ───────────────────────────────────────────────────────────────
    ax = _ax_style(fig.add_subplot(gs[0, 0]), "Numeryczny Model Powierzchni (DSM)")
    im = ax.imshow(results['dem'], cmap='terrain', origin='upper')
    _colorbar(fig, im, ax, 'Wysokość [m]')

    # ── 2. Land cover ─────────────────────────────────────────────────────────
    ax2 = _ax_style(fig.add_subplot(gs[0, 1]), "Pokrycie terenu (10 klas)")
    lc_cmap = mcolors.ListedColormap(_LC_COLOURS)
    im2 = ax2.imshow(results['land_cover'], cmap=lc_cmap,
                     vmin=0.5, vmax=10.5, origin='upper')
    cb2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04, ticks=range(1, 11))
    cb2.ax.set_yticklabels(
        [LAND_COVER_NAMES[i] for i in range(1, 11)], fontsize=5.5
    )
    cb2.ax.yaxis.set_tick_params(color=_TEXT_MUT)

    # # ── 3. Shadow ─────────────────────────────────────────────────────────────
    # ax3 = _ax_style(fig.add_subplot(gs[0, 2]), "Maska cienia SAR")
    # ax3.imshow(np.where(results['shadow'], 0, 1),
    #            cmap='gray', origin='upper', vmin=0, vmax=1)
    # ax3.legend(handles=[
    #     mpatches.Patch(color='white', label='Widoczne'),
    #     mpatches.Patch(color='black', label='Cień'),
    # ], fontsize=7, facecolor=_PANEL_BG, edgecolor=_BORDER,
    #    labelcolor=_TEXT_FG, loc='lower right')

    # ── 4. σ⁰ [dB] ────────────────────────────────────────────────────────────
    ax4   = _ax_style(fig.add_subplot(gs[1, 0]), "Rozproszenie wsteczne σ⁰ [dB]")
    s0    = results['sigma0_dB']
    valid = ~results['shadow'] & np.isfinite(s0)
    vlo, vhi = (np.percentile(s0[valid], [2, 98]) if valid.any() else (-25, 0))
    im4   = ax4.imshow(s0, cmap='plasma', origin='upper', vmin=vlo, vmax=vhi)
    _colorbar(fig, im4, ax4, 'σ⁰ [dB]')

    # ── 5. SNR [dB] ────────────────────────────────────────────────────────────
    ax5 = _ax_style(fig.add_subplot(gs[1, 1]), "Stosunek sygnał/szum SNR [dB]")
    snr_dB  = results['snr_dB']
    finite  = np.isfinite(snr_dB)
    vlo5, vhi5 = (np.percentile(snr_dB[finite], [2, 98]) if finite.any() else (-10, 20))
    im5 = ax5.imshow(snr_dB, cmap='RdYlGn', origin='upper', vmin=vlo5, vmax=vhi5)
    _colorbar(fig, im5, ax5, 'SNR [dB]')

    # ── 6. Atmospheric loss ────────────────────────────────────────────────────
    ax6 = _ax_style(fig.add_subplot(gs[1, 2]), "Straty atmosferyczne L_atm [dB]  (2-way)")
    im6 = ax6.imshow(results['L_atm_dB'], cmap='YlOrRd', origin='upper')
    _colorbar(fig, im6, ax6, 'L_atm [dB]')

    # ── 7. SAR image (slant-range) ────────────────────────────────────────────
    ax7 = _ax_style(fig.add_subplot(gs[2, :2]),
                    "Symulowany obraz SAR – geometria slant-range  (skala log)")
    sar = results['sar_image']
    with np.errstate(divide='ignore', invalid='ignore'):
        sar_log = 10 * np.log10(np.where(sar > 0, sar, np.nan))
    fin  = np.isfinite(sar_log)
    vls, vhs = (np.percentile(sar_log[fin], [1, 99]) if fin.any() else (-25, 0))
    ax7.imshow(sar_log, cmap='gray', origin='upper',
               aspect='auto', vmin=vls, vmax=vhs)
    ax7.set_xlabel('Slant Range  [bin]', color=_TEXT_MUT, fontsize=8)
    ax7.set_ylabel('Azimut  [linia]',    color=_TEXT_MUT, fontsize=8)

    # Range axis ticks in km
    if len(results['range_axis']) > 0:
        ra = results['range_axis']
        n_ticks = 6
        tick_idx = np.linspace(0, len(ra) - 1, n_ticks, dtype=int)
        ax7.set_xticks(tick_idx)
        ax7.set_xticklabels([f"{ra[i]/1e3:.0f}" for i in tick_idx], fontsize=7)
        ax7.set_xlabel('Slant Range  [km]', color=_TEXT_MUT, fontsize=8)

    # ── 8. System info panel ──────────────────────────────────────────────────
    ax8 = _ax_style(fig.add_subplot(gs[2, 2]), "Parametry systemu")
    ax8.axis('off')

    snr_med  = float(np.nanmedian(results['snr_dB' ][np.isfinite(results['snr_dB' ])]))
    nesz_med = float(np.nanmedian(results['nesz_dB'][np.isfinite(results['nesz_dB'])]))
    gamma_o, gamma_w = _specific_attenuation(sat.frequency / 1e9)
    gamma_dB = gamma_o + gamma_w
    shadow_pct = 100.0 * results['shadow'].mean()

    info = (
        "  PARAMETRY SATELITY\n"
        f"  {'─'*30}\n"
        f"  Częst.:    {sat.frequency/1e9:.3f} GHz  (C-band)\n"
        f"  λ:         {sat.wavelength*100:.2f} cm\n"
        f"  H_orbit:   {sat.orbit_height/1e3:.0f} km\n"
        f"  Moc Tx:    {sat.tx_power:.0f} W\n"
        f"  Wzmoc. G:  {sat.antenna_gain_dB:.1f} dB\n"
        f"  Pasmo B:   {sat.bandwidth/1e6:.0f} MHz\n"
        f"  τ_p:       {sat.pulse_duration*1e6:.0f} µs\n"
        f"  Antena:    {sat.antenna_length}×{sat.antenna_height} m\n"
        f"  T_sys:     {sat.T_sys:.0f} K\n"
        f"  NF:        {sat.noise_figure:.1f} dB\n"
        f"  L_sys:     {sat.losses_system:.1f} dB\n"
        f"  PRF:       {sat.prf:.0f} Hz\n"
        "\n"
        "  WYNIKI\n"
        f"  {'─'*30}\n"
        f"  δ_range:   {sat.range_resolution:.2f} m\n"
        f"  δ_azimut:  {sat.azimuth_resolution:.2f} m\n"
        f"  NESZ med:  {nesz_med:.1f} dB\n"
        f"  SNR med:   {snr_med:.1f} dB\n"
        f"  γ_gas:     {gamma_dB:.4f} dB/km\n"
        f"  Cień:      {shadow_pct:.1f} %\n"
    )
    ax8.text(0.03, 0.97, info, transform=ax8.transAxes,
             fontsize=7.8, va='top', fontfamily='monospace',
             color=_TEXT_FG,
             bbox=dict(boxstyle='round,pad=0.6', facecolor='#1c2128',
                       edgecolor=_ACCENT, alpha=0.92, linewidth=1.2))


    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    print(f"[Viz] Figure saved → {output_path}")
    plt.show()
    return output_path