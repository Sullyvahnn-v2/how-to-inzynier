import numpy as np
import matplotlib.pyplot as plt

data = np.loadtxt('land_height.asc', skiprows=6)
land_cover_img = plt.imread('land_cover.png')

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# --- Pierwszy wykres: NMPT ---
im1 = ax1.imshow(data, cmap='viridis')
ax1.set_title("NMPT - Widok z góry\n(budynki i drzewa)")
fig.colorbar(im1, ax=ax1, label="Wysokość n.p.m. [m]")

# --- Drugi wykres: Land Cover ---
ax2.imshow(land_cover_img)
ax2.set_title("Pokrycie terenu")
ax2.axis('off')

plt.tight_layout()
plt.show()

"""
1	Tereny zabudowane	Kolor czerwony/bordowy
2	Grunty orne	Kolor żółty/beżowy
3	Uprawy trwałe	Jasny brąz / oliwkowy
4	Pastwiska i łąki	Jasnozielony
5	Lasy iglaste	Ciemnozielony
6	Lasy liściaste	Soczysty zielony
7	Wody powierzchniowe	Niebieski
8	Mokradła	Fioletowy / ciemny niebieski
9	Tereny piaszczyste	Jasnoszary / biały
10	Lasy mieszane	Średni zielony
"""