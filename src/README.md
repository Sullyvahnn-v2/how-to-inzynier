# `src/` — specyfikacja techniczna (draft)

Pakiet modelu radaru SAR (Sentinel-1) do pracy inżynierskiej. Warstwa danych, parametrów systemu, strat atmosferycznych, formowania obrazu i diagnostycznej wizualizacji. Orkiestracja pipeline’u leży poza tym folderem (`run_sar.py`, `sar_simulator.py`).

Oparcie teoretyczne: Moreira et al. (2013), *A Tutorial on Synthetic Aperture Radar*; tłumienie gazowe: ITU-R P.676-11 (Załącznik 2); speckle: Goodman (1976). Dane terenowe: DSM (`.asc`) i mapa pokrycia terenu (PNG) z Geoportalu (EPSG:2180).

```
src/
  config.py          stałe fizyczne, parametry Sentinel-1, σ⁰ klas
  Scene.py           DSM + land cover
  Satelite.py        parametry i wielkości pochodne satelity
  loss.py            straty atmosferyczne (ITU-R P.676)
  sar_mechanics.py   trajektoria, back-projection, Doppler
  visualise.py       figura diagnostyczna 3×3
```

---

## `config.py`

Stałe: `C_LIGHT`, `K_BOLTZ`.

`sentinel1_parameters` — słownik konfiguracji zbliżonej do Sentinel-1A/B (orbita ~693 km, C-band 5.405 GHz, pasmo 100 MHz, PRF 1500 Hz, antena 12.3×0.84 m, moc Tx 4400 W, NF / straty systemowe).

Klasy pokrycia 1–10 (`LAND_COVER_NAMES`) oraz empiryczne `SIGMA0_DB` (średnia ± std [dB]) i wykładnik kątowy `SIGMA0_N` do korekcji cosine-power.

Klasy `Config` / `DevelopmentConfig` / `ProductionConfig` — szkielet ustawień aplikacji, nieużywany w rdzeniu symulacji.

---

## `Scene.py`

Dataclass `Scene`: siatka DSM `[m]`, klasy land cover 1–10, geometria siatki (`ncols`, `nrows`, `xllcorner`, `yllcorner`, `cellsize`). Właściwości `x_coords` / `y_coords` — środki pikseli (oś Y: wiersz 0 = północ).

- `_parse_asc` — ESRI ASCII Grid (zmienny nagłówek, `nodata` → NaN).
- `_decode_land_cover` — PNG RGB → 10 klas (najbliższy kolor legendy Geoportalu).
- `load_scene(dem_path, lc_path)` — składa `Scene` (domyślnie `land_height.asc`, `land_cover.png`).

---

## `Satelite.py`

Uwaga: nazwa pliku to `Satelite` (literówka).

Klasa `Satellite` ładuje słownik (domyślnie `sentinel1_parameters`). Wielkości pochodne:

| właściwość | znaczenie |
|---|---|
| `wavelength` | λ = c / f |
| `antenna_gain` / `_dB` | zysk z apertury i η |
| `L_sys`, `T_sys` | straty i temperatura szumów |
| `range_resolution` | δ_r = c / (2B) |
| `azimuth_resolution` | δ_a = L_a / 2 (stripmap) |

---

## `loss.py`

Jednostkowe tłumienie O₂ + H₂O oraz wysokości ekwiwalentne (ITU-R P.676-11, Annex 2).

`atmospheric_loss(elev_angle_deg, sat, …)` → **liniowe** tłumienie **dwudrogowe** (≥ 1). Kąt elewacji obcinany od dołu do 5° (uniknięcie osobliwości). Domyślna atmosfera: 1013.25 hPa, 15 °C, 7.5 g/m³ pary wodnej.

---

## `sar_mechanics.py`

**`SARTrajectory`** — lot liniowy w azymucie, right-looking, zero squint. Z R₀ i parametrów satelity: L_synth, T_int, N_pulses, K_a, B_D. `n_positions` (domyślnie 128) to podpróbkowanie apertury, nie pełna liczba impulsów PRF.

- `range_history` — dokładny slant range \(\|s_n - t\|\)
- `doppler_history` — f_D(t_a)
- `azimuth_beam_weight` — dwudrogowe sinc²

**`backproject`** — formowanie w dziedzinie czasu: pole refleksyjności (amplituda √σ⁰ × faza U[0, 2π)), cienie zerowane, spójna suma z wagą wiązki i fazą różnicową względem R₀. Wynik: obraz zespolony, normalizacja przez N pozycji.

**`doppler_spectrum`** — diagnostyka punktu: historia R, f_D, faza dokładna vs. kwadratowa.

---

## `visualise.py`

`visualize(results, sat, output_path="sar_output.png")` — ciemny dashboard 3×3: DSM, land cover, σ⁰ [dB], SNR [dB], L_atm [dB], obraz SAR w geometrii slant-range (skala log), panel parametrów. Maska cienia w kodzie jest zakomentowana.

Oczekiwane klucze `results`: `dem`, `land_cover`, `shadow`, `sigma0_dB`, `snr_dB`, `L_atm_dB`, `sar_image`, `range_axis`, `nesz_dB`.

---

## Zależności i przepływ

```
load_scene  →  Scene
sentinel1_parameters  →  Satellite
Scene + Satellite  →  (poza src: równanie radaru, NESZ, cienie)
loss.atmospheric_loss  →  L_atm
SARTrajectory + backproject  →  obraz zespolony
visualise.visualize  →  PNG
```

Importy: `from src.<moduł> import …` (pakiet wymaga katalogu nadrzędnego na `PYTHONPATH`). Zależności: NumPy, Pillow (`Scene`), Matplotlib (`visualise`).
