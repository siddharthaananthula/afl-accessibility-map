"""
inspect_gtfs.py

One-off script used to identify which transport mode lives in each PTV
GTFS folder (the folder names 1/, 2/, 3/ etc. aren't documented, so we
inspect the stop names to infer the mode). Used during pipeline build,
kept for reference.
"""

import pandas as pd
import zipfile
import io
from pathlib import Path

GTFS_DIR = Path(__file__).parent.parent / "data" / "raw" / "gtfs_extracted"


def main():
    for folder in sorted(GTFS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        zpath = folder / "google_transit.zip"
        if not zpath.exists():
            continue

        with zipfile.ZipFile(zpath) as z:
            stops_name = [n for n in z.namelist() if n.endswith("stops.txt")][0]
            df = pd.read_csv(io.TextIOWrapper(z.open(stops_name), "utf-8"))

        print(f"\nFolder {folder.name}: {len(df):,} rows, "
              f"{df['stop_name'].nunique():,} unique names")
        for name in df["stop_name"].drop_duplicates().head(8):
            print(f"  - {name}")


if __name__ == "__main__":
    main()