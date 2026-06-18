"""
transport_stops.py

Day 3 (part 1) of the Grassroots Footy Accessibility Map.

PTV publishes GTFS data as a nested zip:
  gtfs.zip
   ├── 1/google_transit.zip   (Metro Train)
   ├── 2/google_transit.zip   (Metro Tram)
   ├── 3/google_transit.zip   (Metro Bus)
   ├── 4/google_transit.zip   (Regional Train)
   ├── 5/google_transit.zip   (Regional Coach)
   └── 6/google_transit.zip   (Regional Bus)

This script opens each inner zip, extracts the `stops.txt` file inside,
tags each stop with its transport mode, and consolidates everything into
a single GeoDataFrame of Victorian transit stops.

Output: data/processed/ptv_stops.geojson and ptv_stops.csv
"""

import pandas as pd
import geopandas as gpd
import zipfile
import io
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

GTFS_DIR = DATA_RAW / "gtfs_extracted"

# Mode folder → human-readable label
# We include all main transport modes; skip 10 (night-only) and 11 (Skybus)
# Correct mapping based on inspection of stop names:
MODES = {
    "1": "train",          # Metro Train (Flinders St, Richmond, etc.)
    "2": "train",          # Regional V/Line Train (Belgrave, Alamein, etc.)
    "3": "tram",           # Metro Tram (stops numbered #42, #43, etc.)
    "4": "bus",            # Metro Bus (street intersections, 22k stops)
    "5": "coach",          # Regional Coach
    "6": "bus",            # Regional Bus
}


def load_stops_from_zip(zip_path: Path) -> pd.DataFrame:
    """Read just stops.txt from a GTFS zip without extracting to disk."""
    with zipfile.ZipFile(zip_path, "r") as z:
        # Some PTV zips have stops at root, others have nested folder
        stops_member = None
        for name in z.namelist():
            if name.endswith("stops.txt"):
                stops_member = name
                break

        if stops_member is None:
            return pd.DataFrame()

        with z.open(stops_member) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"))

    return df


def load_all_stops() -> gpd.GeoDataFrame:
    """Iterate through PTV mode folders, consolidate all stops into one frame."""
    all_stops = []

    for folder, mode_label in MODES.items():
        inner_zip = GTFS_DIR / folder / "google_transit.zip"
        if not inner_zip.exists():
            print(f"  Skipping folder {folder} - no google_transit.zip found")
            continue

        df = load_stops_from_zip(inner_zip)
        if len(df) == 0:
            print(f"  Folder {folder} ({mode_label}): no stops found")
            continue

        # Keep only essential columns; tag with the mode
        cols_keep = ["stop_id", "stop_name", "stop_lat", "stop_lon"]
        available = [c for c in cols_keep if c in df.columns]
        df = df[available].copy()
        df["mode"] = mode_label
        df["mode_folder"] = folder

        print(f"  Folder {folder} ({mode_label}): {len(df)} stops")
        all_stops.append(df)

    if not all_stops:
        print("ERROR: no stops loaded from any folder.")
        return gpd.GeoDataFrame()

    combined = pd.concat(all_stops, ignore_index=True)
    print(f"\nTotal stops before cleaning: {len(combined)}")

    # Drop rows missing coordinates (some GTFS entries are parent station nodes
    # or have nulls)
    before = len(combined)
    combined = combined.dropna(subset=["stop_lat", "stop_lon"])
    print(f"  Dropped {before - len(combined)} stops with missing coordinates.")

    # Strip whitespace from names
    combined["stop_name"] = combined["stop_name"].astype(str).str.strip()

    # Make a GeoDataFrame in WGS84 (lat/lon)
    gdf = gpd.GeoDataFrame(
        combined,
        geometry=gpd.points_from_xy(combined["stop_lon"], combined["stop_lat"]),
        crs="EPSG:4326",
    )

    # De-duplicate near-identical stops (same coords + same mode) -
    # PTV often has separate stops per direction at the same location
    before = len(gdf)
    gdf["_lat_r"] = gdf["stop_lat"].round(5)
    gdf["_lon_r"] = gdf["stop_lon"].round(5)
    gdf = gdf.drop_duplicates(subset=["mode", "_lat_r", "_lon_r"]).copy()
    gdf = gdf.drop(columns=["_lat_r", "_lon_r"])
    print(f"  De-duplicated: {before} -> {len(gdf)}")

    return gdf.reset_index(drop=True)


def main():
    print("Loading PTV GTFS stops across all transport modes...\n")

    stops = load_all_stops()
    if len(stops) == 0:
        print("No data. Aborting.")
        return

    # Breakdown by mode
    print("\n--- Stops by mode ---")
    print(stops["mode"].value_counts().to_string())

    # Save outputs
    out_geojson = DATA_PROCESSED / "ptv_stops.geojson"
    out_csv = DATA_PROCESSED / "ptv_stops.csv"
    stops.to_file(out_geojson, driver="GeoJSON")
    stops.drop(columns="geometry").to_csv(out_csv, index=False)

    print(f"\nSaved: {out_geojson}")
    print(f"Saved: {out_csv}")
    print(f"\nTotal unique transit stops: {len(stops)}")


if __name__ == "__main__":
    main()