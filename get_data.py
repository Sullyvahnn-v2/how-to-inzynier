import io

import requests
from PIL import Image


def download_nmpt_wcs(bbox, filename="nmpt_data.asc", resolution=0.5):
    """
    Pobiera dane NMPT z Geoportalu przez usługę WCS.
    bbox: krotka (x_min, y_min, x_max, y_max) w układzie EPSG:2180
    """
    base_url = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMPT/GRID1/WCS/DigitalSurfaceModel"

    params = {
        "service": "wcs",
        "request": "GetCoverage",
        "version": "1.0.0",
        "coverage": "DSM_PL-KRON86-NH",
        "format": "image/x-aaigrid",
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "resx": str(resolution),
        "resy": str(resolution),
        "crs": "EPSG:2180"
    }

    print(f"Pobieranie danych dla obszaru: {bbox}...")

    try:
        response = requests.get(base_url, params=params)
        print(response.url)
        response.raise_for_status()

        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Sukces! Dane zapisane w pliku: {filename}")
        return True
    except Exception as e:
        print(f"Błąd podczas pobierania: {e}")
        return False


def download_land_cover(bbox, filename="land_cover.png"):
    url = "https://mapy.geoportal.gov.pl/wss/service/POLSA/WCS/LandCover"
    params = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": "Land_use_classification_2023",
        "FORMAT": "GEOTIFF",
        "BBOX": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
        "CRS": "EPSG:2180",
        "WIDTH": "2000",
        "HEIGHT": "2000",
        "TRANSPARENT": "FALSE"
    }
    print(f"Pobieram mapę pokrycia")

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
    else:
        print(response.url)
        image = Image.open(io.BytesIO(response.content))
        image.save(filename)
        print(f"Pobrano mapę pokrycia: {filename}")


# Twoje współrzędne z linku
moj_bbox = (556872.31, 231721.63, 559114.66, 233084.24)

if __name__ == "__main__":
    download_nmpt_wcs(moj_bbox, "land_height.asc")
    download_land_cover(moj_bbox)