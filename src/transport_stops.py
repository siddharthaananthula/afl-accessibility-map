"""
transport_stops.py

Consolidates Public Transport Victoria GTFS stops across all modes
(train, tram, bus, coach) into a single unified GeoDataFrame.

PTV publishes GTFS as a nested zip - one folder per mode, each containing
its own google_transit.zip with the standard GTFS files inside. This
reads stops.txt from each inner zip without extracting to disk.

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

# Folder number to mode label, based on inspection of stop names in each
# folder (see inspect_gtfs.py).
MODES = {
    "1": "train",          # Metro Train
    "2": "train",          # Regional V/Line Train
    "3": "tram",           # Metro Tram
    "4": "bus",            # Metro Bus
    "5": "coach",          # Regional Coach
    "6": "bus",            # Regional Bus
}


def load_stops_from_zip(zip_path: Path) -> pd.DataFrame:
    """Read stops.txt from a GTFS zip in memory (no extraction to disk)."""
    with zipfile.ZipFile(zip_path, "r") as z:
        stops_member = next(
            (n for n in z.namelist() if n.endswith("stops.txt")), None
        )
        if stops_member is None:
            return pd.DataFrame()
        with z.open(stops_member) as f:
            return pd.read_csv(io.TextIOWrapper(f, encoding="utf-8"))


def load_all_stops() -> gpd.GeoDataFrame:
    """Iterate through mode folders, consolidate all stops."""
    all_stops = []

    for folder, mode_label in MODES.items():
        inner_zip = GTFS_DIR / folder / "google_transit.zip"
        if not inner_zip.exists():
            print(f"Skipping folder {folder}: no google_transit.zip")
            continue

        df = load_stops_from_zip(inner_zip)
        if len(df) == 0:
            continue

        cols_keep = ["stop_id", "stop_name", "stop_lat", "stop_lon"]
        df = df[[c for c in cols_keep if c in df.columns]].copy()
        df["mode"] = mode_label
        df["mode_folder"] = folder

        print(f"Folder {folder} ({mode_label}): {len(df)} stops")
        all_stops.append(df)

    if not all_stops:
        return gpd.GeoDataFrame()

    combined = pd.concat(all_stops, ignore_index=True)
    combined = combined.dropna(subset=["stop_lat", "stop_lon"])
    combined["stop_name"] = combined["stop_name"].astype(str).str.strip()

    gdf = gpd.GeoDataFrame(
        combined,
        geometry=gpd.points_from_xy(combined["stop_lon"], combined["stop_lat"]),
        crs="EPSG:4326",
    )

    # De-duplicate near-identical stops (PTV often has separate stops per
    # direction at the same location)
    gdf["_lat_r"] = gdf["stop_lat"].round(5)
    gdf["_lon_r"] = gdf["stop_lon"].round(5)
    gdf = gdf.drop_duplicates(subset=["mode", "_lat_r", "_lon_r"]).copy()
    gdf = gdf.drop(columns=["_lat_r", "_lon_r"])

    return gdf.reset_index(drop=True)


def main():
    stops = load_all_stops()
    if len(stops) == 0:
        print("No stops loaded.")
        return

    print(f"\nBy mode:")
    print(stops["mode"].value_counts().to_string())

    stops.to_file(DATA_PROCESSED / "ptv_stops.geojson", driver="GeoJSON")
    stops.drop(columns="geometry").to_csv(
        DATA_PROCESSED / "ptv_stops.csv", index=False
    )
    print(f"\n{len(stops)} unique transit stops across Victoria.")


if __name__ == "__main__":
    main()