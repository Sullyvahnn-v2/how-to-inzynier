from __future__ import annotations
import numpy as np
from PIL import Image
import matplotlib
try:
    matplotlib.use('TkAgg')
except Exception:
    pass   # fall back to whatever is available
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Scene:
    """Stores the Digital Surface Model and land-cover class grid."""
    dem:         np.ndarray   # [nrows, ncols]  elevation [m]
    land_cover:  np.ndarray   # [nrows, ncols]  class 1-10
    ncols:       int
    nrows:       int
    xllcorner:   float        # left edge  [m, EPSG:2180]
    yllcorner:   float        # bottom edge [m]
    cellsize:    float        # pixel size  [m]

    @property
    def x_coords(self) -> np.ndarray:
        """Column centre x-coordinates (increasing East)."""
        return self.xllcorner + (np.arange(self.ncols) + 0.5) * self.cellsize

    @property
    def y_coords(self) -> np.ndarray:
        """Row centre y-coordinates (row-0 = North → decreasing)."""
        return self.yllcorner + (self.nrows - 0.5 - np.arange(self.nrows)) * self.cellsize


def _parse_asc(filepath: str | Path) -> tuple[dict, np.ndarray]:
    """
    Parse an ESRI ASCII Grid (.asc) file.

    Handles variable header length and alternative key names used by
    different WCS providers
    """
    header: dict = {}
    data_lines: list[str] = []
    in_header = True

    with open(filepath, 'r') as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            # Header lines: first token is a non-numeric keyword
            if in_header:
                try:
                    float(parts[0])
                    # First token is a number → we've entered the data block
                    in_header = False
                    data_lines.append(line)
                except (ValueError, IndexError):
                    if len(parts) >= 2:
                        header[parts[0].lower()] = parts[1]
            else:
                data_lines.append(line)

    print(f"[Scene] ASC header keys: {list(header.keys())}")

    # Normalise cell size: accept 'cellsize', 'dx', 'dy'
    if 'cellsize' not in header:
        for alt in ('dx', 'dy', 'cell_size', 'step'):
            if alt in header:
                header['cellsize'] = header[alt]
                break
        else:
            raise KeyError(
                f"Cannot find cell size in ASC header. Keys found: {list(header.keys())}"
            )

    # Convert numeric values
    for k in header:
        try:
            header[k] = float(header[k])
        except ValueError:
            pass

    # Build 2-D array from the data lines we already buffered
    import io
    data = np.loadtxt(io.StringIO('\n'.join(data_lines)))

    nodata = float(header.get('nodata_value', -9999.0))
    data[data == nodata] = np.nan

    # Ensure ncols/nrows are in header (infer from data if missing)
    if 'ncols' not in header:
        header['ncols'] = float(data.shape[1])
    if 'nrows' not in header:
        header['nrows'] = float(data.shape[0])
    if 'xllcorner' not in header:
        header['xllcorner'] = float(header.get('xllcenter', 0.0))
    if 'yllcorner' not in header:
        header['yllcorner'] = float(header.get('yllcenter', 0.0))

    return header, data



def _decode_land_cover(img_rgb: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """
    Match each pixel of the land-cover PNG to one of 10 Geoportal classes
    using nearest-colour assignment in RGB space.
    """
    # Representative RGB for each class (hand-picked from Geoportal legend)
    CLASS_COLOURS: dict[int, tuple] = {
        1:  (200,  50,  50),   # Zabudowa          – czerwony
        2:  (230, 210, 130),   # Grunty orne       – żółty
        3:  (180, 160,  80),   # Uprawy trwałe     – oliwkowy
        4:  (150, 220, 100),   # Łąki/pastwiska    – jasno-zielony
        5:  (  0, 100,  30),   # Lasy iglaste      – ciemno-zielony
        6:  ( 60, 180,  60),   # Lasy liściaste    – zielony
        7:  ( 50, 100, 220),   # Wody              – niebieski
        8:  (120,  80, 180),   # Mokradła          – fioletowy
        9:  (220, 220, 220),   # Piaski            – szary
        10: (100, 140,  60),   # Lasy mieszane     – średni zielony
    }

    img = Image.fromarray(img_rgb).resize(
        (shape[1], shape[0]), Image.Resampling.NEAREST
    )
    rgb = np.array(img, dtype=np.float32)[:, :, :3]  # [H, W, 3]

    classes   = np.ones(shape[:2], dtype=np.uint8)
    best_dist = np.full(shape[:2], np.inf, dtype=np.float32)

    for cls, col in CLASS_COLOURS.items():
        ref  = np.array(col, dtype=np.float32)
        dist = np.sqrt(((rgb - ref) ** 2).sum(axis=2))
        mask = dist < best_dist
        classes[mask]   = cls
        best_dist[mask] = dist[mask]

    return classes


def load_scene(dem_path: str = "land_height.asc",
               lc_path:  str = "land_cover.png") -> Scene:
    """Load DSM and land-cover from Geoportal-downloaded files."""
    print(f"[Scene] Loading DEM   -> {dem_path}")
    hdr, dem = _parse_asc(dem_path)

    print(f"[Scene] Loading land cover -> {lc_path}")
    lc_img = np.array(Image.open(lc_path).convert('RGB'))
    land_cover = _decode_land_cover(lc_img, dem.shape)

    sc = Scene(
        dem=dem, land_cover=land_cover,
        ncols=int(hdr['ncols']), nrows=int(hdr['nrows']),
        xllcorner=hdr['xllcorner'], yllcorner=hdr['yllcorner'],
        cellsize=hdr['cellsize'],
u    )
    print(f"[Scene] Grid {sc.nrows}x{sc.ncols} @ {sc.cellsize} m/px | "
          f"Z: {np.nanmin(dem):.1f}-{np.nanmax(dem):.1f} m")
    return sc