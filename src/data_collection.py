"""
data_collection.py

Day 1 of the Grassroots Footy Accessibility Map.

Reads AFL grounds from a local Victoria (Australia) OSM PBF, using bounding-box
chunks to stay within memory limits on standard laptops.

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
# Splitting reduces RAM pressure: each chunk loads independently.
REGIONS = {
    # Greater Melbourne split into 4 quadrants to avoid memory issues
    "Melbourne NW":          [144.4, -37.95, 144.95, -37.5],
    "Melbourne NE":          [144.95, -37.95, 145.6, -37.5],
    "Melbourne SW":          [144.4, -38.5, 144.95, -37.95],
    "Melbourne SE":          [144.95, -38.5, 145.6, -37.95],
    # Rest of Victoria
    "Geelong & Bellarine":   [143.8, -38.6, 144.8, -38.0],
    "Western Victoria":      [140.9, -38.8, 143.9, -36.2],
    "Northern Victoria":     [143.5, -36.8, 146.5, -34.0],
    "Gippsland / East":      [145.3, -39.2, 150.1, -37.0],
}

def download_victoria_pbf():
    """Download Victoria (Australia) OSM data from GeoFabrik if not cached."""
    if PBF_PATH.exists() and PBF_PATH.stat().st_size > 100 * 1024 * 1024:
        size_mb = PBF_PATH.stat().st_size / (1024 * 1024)
        print(f"  Using cached file: {PBF_PATH.name} ({size_mb:.1f} MB)")
        return

    print(f"  Downloading from: {PBF_URL}")
    print(f"  Approximately 220 MB, 5-15 minutes...")

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
                    print(f"    {mb_done:.1f} / {total_mb:.1f} MB ({pct:.1f}%)", end="\r")

    print(f"\n  Download complete: {PBF_PATH}")


def fetch_for_region(region_name: str, bbox: list) -> gpd.GeoDataFrame:
    """Filter the local PBF for one bounding-box region."""
    print(f"  -> {region_name} ...", end=" ", flush=True)
    osm = OSM(str(PBF_PATH), bounding_box=bbox)
    try:
        gdf = osm.get_pois(custom_filter={"sport": ["australian_football"]})
    except MemoryError:
        print("MemoryError — region too large, skipping.")
        return gpd.GeoDataFrame()

    if gdf is None or len(gdf) == 0:
        print("0 venues")
        return gpd.GeoDataFrame()

    print(f"{len(gdf)} raw features")
    gdf["_region"] = region_name
    return gdf


def fetch_afl_grounds_vic() -> gpd.GeoDataFrame:
    print("Step 1: Ensuring Victoria OSM data is available...")
    download_victoria_pbf()

    print("\nStep 2: Parsing OSM file region-by-region for AFL venues...")
    print("(Splitting Victoria into 5 bounding boxes to manage memory.)")

    parts = []
    for name, bbox in REGIONS.items():
        part = fetch_for_region(name, bbox)
        if len(part) > 0:
            parts.append(part)

    if not parts:
        print("\nWARNING: no AFL venues found across any region.")
        return gpd.GeoDataFrame()

    gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)
    print(f"\nCombined raw count (with overlaps): {len(gdf)}")

    # Convert any polygons to centroid points
    gdf_projected = gdf.to_crs(epsg=3857)
    gdf_projected["geometry"] = gdf_projected.geometry.centroid
    gdf = gdf_projected.to_crs(epsg=4326)

    # Keep only useful columns
    keep_cols = [
        "name", "sport", "leisure",
        "addr:suburb", "addr:postcode", "addr:city",
        "operator", "website", "_region", "geometry",
    ]
    available = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[available].copy()

    # Drop unnamed venues
    if "name" in gdf.columns:
        before = len(gdf)
        gdf = gdf.dropna(subset=["name"])
        print(f"Dropped {before - len(gdf)} unnamed venues.")

    # Add lat/lon columns
    gdf["latitude"] = gdf.geometry.y
    gdf["longitude"] = gdf.geometry.x

    # De-duplicate venues that appear in multiple overlapping bounding boxes
    # (round coordinates so very-near-identical points collapse)
    before = len(gdf)
    gdf["_lat_r"] = gdf["latitude"].round(5)
    gdf["_lon_r"] = gdf["longitude"].round(5)
    gdf = gdf.drop_duplicates(subset=["name", "_lat_r", "_lon_r"]).copy()
    gdf = gdf.drop(columns=["_lat_r", "_lon_r"])
    print(f"De-duplicated overlapping regions: {before} -> {len(gdf)}")

    gdf = gdf.reset_index(drop=True)
    print(f"\nFinal count: {len(gdf)} unique Australian Rules Football venues in Victoria.")
    return gdf


def main():
    gdf = fetch_afl_grounds_vic()

    if len(gdf) == 0:
        print("\nNo data returned. Aborting.")
        return

    out_geojson = DATA_RAW / "afl_clubs_vic.geojson"
    out_csv = DATA_RAW / "afl_clubs_vic.csv"

    gdf.to_file(out_geojson, driver="GeoJSON")
    gdf.drop(columns="geometry").to_csv(out_csv, index=False)

    print(f"\nSaved: {out_geojson}")
    print(f"Saved: {out_csv}")
    print(f"\n--- Preview (first 10 venues) ---")
    cols_preview = [c for c in ["name", "addr:suburb", "_region", "latitude", "longitude"] if c in gdf.columns]
    print(gdf[cols_preview].head(10).to_string())


if __name__ == "__main__":
    main()