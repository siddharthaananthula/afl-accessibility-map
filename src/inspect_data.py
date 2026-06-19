"""
inspect_data.py

One-off exploration script used to figure out the structure of the SEIFA
Excel file and the SA2 shapefile before writing seifa_join.py. Keep for
reference / reproducibility but not part of the main pipeline.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"

SEIFA_PATH = DATA_RAW / "seifa_2021_sa2.xlsx"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"


def inspect_seifa():
    """Print first 10 rows of each SEIFA sheet to find data start row."""
    xl = pd.ExcelFile(SEIFA_PATH)
    print(f"Sheets: {xl.sheet_names}\n")

    for sheet in xl.sheet_names:
        print(f"-- {sheet} --")
        df = pd.read_excel(SEIFA_PATH, sheet_name=sheet, header=None, nrows=10)
        print(df.to_string())
        print()


def inspect_sa2_boundaries():
    """Check SA2 shapefile column names and Victoria filter."""
    gdf = gpd.read_file(SA2_SHP_PATH)
    print(f"Total SA2 polygons (national): {len(gdf)}")
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {list(gdf.columns)}")

    vic = gdf[gdf["STE_NAME21"] == "Victoria"]
    print(f"\nVictorian SA2 polygons: {len(vic)}")
    print(vic.head().to_string())


if __name__ == "__main__":
    inspect_seifa()
    inspect_sa2_boundaries()