"""Quick inspection: figure out which mode each PTV folder actually contains."""

import pandas as pd
import zipfile
import io
from pathlib import Path

GTFS_DIR = Path(__file__).parent.parent / "data" / "raw" / "gtfs_extracted"

for folder in sorted(GTFS_DIR.iterdir()):
    if not folder.is_dir():
        continue
    zpath = folder / "google_transit.zip"
    if not zpath.exists():
        continue

    with zipfile.ZipFile(zpath) as z:
        stops_name = [n for n in z.namelist() if n.endswith("stops.txt")][0]
        df = pd.read_csv(io.TextIOWrapper(z.open(stops_name), "utf-8"))

    print(f"\n--- Folder {folder.name} ---")
    print(f"Rows: {len(df):,}  |  Unique names: {df['stop_name'].nunique():,}")
    print("Sample names:")
    for name in df["stop_name"].drop_duplicates().head(8):
        print(f"  - {name}")