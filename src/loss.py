import numpy as np
from src.Satelite import Satellite


def _specific_attenuation_dBpkm(f_GHz: float,
                                P_hPa: float = 1013.25,
                                T_C: float = 15.0,
                                rho_g_m3: float = 7.5) -> float:
    """Total specific gaseous attenuation gamma [dB/km] (O2 + H2O). Scalar wrapper."""
    go, gw = _specific_attenuation(f_GHz, P_hPa, T_C, rho_g_m3)
    return float(go) + float(gw)
def _specific_attenuation(f_GHz: np.ndarray | float, 
                                     P_hPa: float = 1013.25, 
                                     T_C: float = 15.0, 
                                     rho_g_m3: float = 7.5) -> tuple[np.ndarray | float, np.ndarray | float]:
    """
    Oblicza jednostkowe tłumienie gazowe [dB/km] dla suchego powietrza (tlenu) i pary wodnej
    zgodnie z ITU-R P.676-11 Załącznik 2.
    """
    f = np.atleast_1d(f_GHz)
    rp = P_hPa / 1013.25
    theta = 300.0 / (T_C + 273.15)
    
    # --- 1. Tłumienie jednostkowe suchego powietrza (gamma_o) ---
    gamma_o = np.zeros_like(f, dtype=float)
    
    # Pasmo poniżej rezonansu tlenu (f <= 54 GHz)
    mask_low = f <= 54.0
    if np.any(mask_low):
        fl = f[mask_low]
        t1 = 7.27 * (theta ** 2.8) / (fl**2 + 0.351 * (rp**2) * (theta**1.2))
        t2 = 4.82 * theta / ((fl - 60.0)**2 + 2.39 * (rp**2) * theta)
        gamma_o[mask_low] = (t1 + t2) * (fl**2) * (rp**2) * 1e-3
        
    # Główny kompleks rezonansowy tlenu (54 < f <= 70 GHz) - przybliżenie gładkie piku
    mask_peak = (f > 54.0) & (f <= 70.0)
    if np.any(mask_peak):
        fp = f[mask_peak]
        gamma_o[mask_peak] = 12.0 * (rp**2) * (theta**2) * np.exp(-((fp - 60.0) / 4.5)**2)
        
    # Pasmo powyżej rezonansu tlenu (f > 70 GHz)
    mask_high = f > 70.0
    if np.any(mask_high):
        fh = f[mask_high]
        gamma_o[mask_high] = 0.4 * (rp**2) * (theta**1.5)

    # --- 2. Tłumienie jednostkowe pary wodnej (gamma_w) ---
    # Uwzględnia linie absorpcyjne 22.235 GHz, 183.31 GHz i 325.15 GHz
    term_w1 = 3.14e-2 * rp * (theta**2.5) / ((f - 22.235)**2 + 2.65 * (rp**2) * theta)
    term_w2 = 1.14e-1 * rp * (theta**2.5) / ((f - 183.31)**2 + 3.0 * (rp**2) * theta)
    term_w3 = 3.08e-1 * rp * (theta**2.5) / ((f - 325.15)**2 + 3.5 * (rp**2) * theta)
    
    gamma_w = (term_w1 + term_w2 + term_w3) * (f**2) * rho_g_m3 * 1e-4

    if gamma_o.ndim == 1 and len(gamma_o) == 1:
        return gamma_o[0], gamma_w[0]
    return gamma_o, gamma_w


def _equivalent_heights_itu_r_p676(f_GHz: np.ndarray | float, 
                                   P_hPa: float = 1013.25) -> tuple[np.ndarray | float, np.ndarray | float]:
    """
    Oblicza efektywną wysokość ekwiwalentną warstwy [km] dla tlenu (h_o) i pary wodnej (h_w)
    zgodnie z ITU-R P.676-11 Załącznik 2.
    """
    f = np.atleast_1d(f_GHz)
    rp = P_hPa / 1013.25
    
    # Wysokość ekwiwalentna tlenu
    h_o = 6.1 / (1.0 + 0.17 * (rp**-1.1))
    
    # Wysokość ekwiwalentna pary wodnej (uwzględniająca wpływ rezonansów na grubość optyczną)
    h_w0 = 1.66 * (1.0 + (1.39 * rp) / (1.0 + 3.19 * rp))
    h_w = h_w0 * (1.0 + 3.0 / ((f - 22.235)**2 + 5.0) 
                      + 1.0 / ((f - 183.31)**2 + 6.0) 
                      + 1.0 / ((f - 325.15)**2 + 4.0))
    
    # if h_o.ndim == 1 and len(h_o) == 1:
    #     return h_o[0], h_w[0]
    return h_o, h_w


def atmospheric_loss(elev_angle_deg: np.ndarray | float,
                     sat: Satellite,
                     P_hPa: float = 1013.25,
                     T_C: float = 15.0,
                     rho_g_m3: float = 7.5) -> np.ndarray:
    f_GHz = sat.frequency / 1e9
    
    # 1. Obliczenie jednostkowych współczynników tłumienia (dB/km)
    gamma_o, gamma_w = _specific_attenuation(f_GHz, P_hPa, T_C, rho_g_m3)
    
    # 2. Obliczenie wysokości ekwiwalentnych (km)
    h_o, h_w = _equivalent_heights_itu_r_p676(f_GHz, P_hPa)
    
    # 3. Tłumienie w zenicie (zenith attenuation) w dB
    A_zenith = (gamma_o * h_o) + (gamma_w * h_w)
    
    # 4. Przeliczenie na ukośną ścieżkę
    elev = np.maximum(5.0, elev_angle_deg)  # Zabezpieczenie przed osobliwością dla niskich kątów
    sin_elev = np.sin(np.radians(elev))
    
    # Tłumienie jednodrogowe (one-way) wzdłuż skośnej ścieżki
    slant_loss = A_zenith / sin_elev
    
    # Tłumienie dwudrogowe (two-way)
    total_loss_dB = 2.0 * slant_loss

    # Konwersja ze skali dB na wartość liniową (>= 1.0)
    return 10 ** (total_loss_dB / 10.0)