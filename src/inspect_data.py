"""
inspect_data.py

Quick inspection of SEIFA + SA2 boundary files to understand their structure
before writing the join pipeline. Run once, then move on to seifa_join.py.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"

SEIFA_PATH = DATA_RAW / "seifa_2021_sa2.xlsx"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"


def inspect_seifa():
    """Look at all sheets in the SEIFA Excel file."""
    print("=" * 70)
    print("SEIFA EXCEL FILE")
    print("=" * 70)

    xl = pd.ExcelFile(SEIFA_PATH)
    print(f"\nSheets available: {xl.sheet_names}\n")

    # Look at each sheet's first few rows (without skipping any rows)
    for sheet in xl.sheet_names:
        print(f"--- Sheet: {sheet} ---")
        df = pd.read_excel(SEIFA_PATH, sheet_name=sheet, header=None, nrows=10)
        print(df.to_string())
        print()


def inspect_sa2_boundaries():
    """Look at the SA2 shapefile structure."""
    print("=" * 70)
    print("SA2 SHAPEFILE")
    print("=" * 70)

    gdf = gpd.read_file(SA2_SHP_PATH)
    print(f"\nTotal SA2 polygons in Australia: {len(gdf)}")
    print(f"CRS (coordinate reference system): {gdf.crs}")
    print(f"\nColumns: {list(gdf.columns)}")
    print(f"\nFirst 5 rows (Victoria filtered):")
    vic = gdf[gdf["STE_NAME21"] == "Victoria"]
    print(f"Victoria SA2 polygons: {len(vic)}")
    print(vic.head().to_string())


if __name__ == "__main__":
    inspect_seifa()
    inspect_sa2_boundaries()