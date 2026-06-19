"""
data_collection.py

Extracts Australian Rules Football venue locations from a local Victoria
OSM PBF dump (via pyrosm). Splits Victoria into bounding-box chunks to
stay within memory limits, then de-duplicates across overlapping regions.

Output: data/raw/afl_clubs_vic.geojson and afl_clubs_vic.csv
"""

import geopandas as gpd
import pandas as pd
import requests
import warnings
from pathlib import Path
from pyrosm import OSM

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_RAW.mkdir(parents=True, exist_ok=True)

PBF_URL = "https://download.geofabrik.de/australia-oceania/australia/victoria-latest.osm.pbf"
PBF_PATH = DATA_RAW / "victoria-australia-latest.osm.pbf"

# Bounding boxes (west, south, east, north) covering Victoria in chunks.
# Splitting reduces RAM usage - each chunk loads independently.
REGIONS = {
    "Melbourne NW":          [144.4, -37.95, 144.95, -37.5],
    "Melbourne NE":          [144.95, -37.95, 145.6, -37.5],
    "Melbourne SW":          [144.4, -38.5, 144.95, -37.95],
    "Melbourne SE":          [144.95, -38.5, 145.6, -37.95],
    "Geelong & Bellarine":   [143.8, -38.6, 144.8, -38.0],
    "Western Victoria":      [140.9, -38.8, 143.9, -36.2],
    "Northern Victoria":     [143.5, -36.8, 146.5, -34.0],
    "Gippsland / East":      [145.3, -39.2, 150.1, -37.0],
}


def download_victoria_pbf():
    """Download Victoria OSM data from GeoFabrik if not already cached."""
    if PBF_PATH.exists() and PBF_PATH.stat().st_size > 100 * 1024 * 1024:
        size_mb = PBF_PATH.stat().st_size / (1024 * 1024)
        print(f"Using cached PBF: {PBF_PATH.name} ({size_mb:.1f} MB)")
        return

    print(f"Downloading {PBF_URL}")
    response = requests.get(PBF_URL, stream=True, timeout=300)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    total_mb = total / (1024 * 1024) if total else 0
    downloaded = 0

    with open(PBF_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192 * 1024):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 / total
                    mb_done = downloaded / (1024 * 1024)
                    print(f"  {mb_done:.1f} / {total_mb:.1f} MB ({pct:.1f}%)", end="\r")
    print(f"\nDownloaded: {PBF_PATH}")


def fetch_for_region(region_name: str, bbox: list) -> gpd.GeoDataFrame:
    """Filter the local PBF for one bounding-box region."""
    print(f"  {region_name}: ", end="", flush=True)
    osm = OSM(str(PBF_PATH), bounding_box=bbox)
    try:
        gdf = osm.get_pois(custom_filter={"sport": ["australian_football"]})
    except MemoryError:
        print("MemoryError, skipping")
        return gpd.GeoDataFrame()

    if gdf is None or len(gdf) == 0:
        print("0 features")
        return gpd.GeoDataFrame()

    print(f"{len(gdf)} features")
    gdf["_region"] = region_name
    return gdf


def fetch_afl_grounds_vic() -> gpd.GeoDataFrame:
    download_victoria_pbf()
    print("\nProcessing Victoria in bounding-box chunks:")

    parts = []
    for name, bbox in REGIONS.items():
        part = fetch_for_region(name, bbox)
        if len(part) > 0:
            parts.append(part)

    if not parts:
        print("No features found across any region.")
        return gpd.GeoDataFrame()

    gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)

    # Polygons -> centroid points
    gdf_projected = gdf.to_crs(epsg=3857)
    gdf_projected["geometry"] = gdf_projected.geometry.centroid
    gdf = gdf_projected.to_crs(epsg=4326)

    # Keep useful columns only
    keep_cols = [
        "name", "sport", "leisure",
        "addr:suburb", "addr:postcode", "addr:city",
        "operator", "website", "_region", "geometry",
    ]
    available = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[available].copy()

    # Drop unnamed venues
    if "name" in gdf.columns:
        gdf = gdf.dropna(subset=["name"])

    gdf["latitude"] = gdf.geometry.y
    gdf["longitude"] = gdf.geometry.x

    # De-duplicate overlapping regions by rounded coords
    gdf["_lat_r"] = gdf["latitude"].round(5)
    gdf["_lon_r"] = gdf["longitude"].round(5)
    gdf = gdf.drop_duplicates(subset=["name", "_lat_r", "_lon_r"]).copy()
    gdf = gdf.drop(columns=["_lat_r", "_lon_r"])

    return gdf.reset_index(drop=True)


def main():
    gdf = fetch_afl_grounds_vic()
    if len(gdf) == 0:
        return

    out_geojson = DATA_RAW / "afl_clubs_vic.geojson"
    out_csv = DATA_RAW / "afl_clubs_vic.csv"
    gdf.to_file(out_geojson, driver="GeoJSON")
    gdf.drop(columns="geometry").to_csv(out_csv, index=False)

    print(f"\n{len(gdf)} unique AFL venues across Victoria")
    print(f"Saved: {out_geojson.name}, {out_csv.name}")


if __name__ == "__main__":
    main()