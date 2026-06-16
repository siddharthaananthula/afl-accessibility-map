"""
data_collection.py

Day 1 of the Grassroots Footy Accessibility Map.

Collects Australian Rules Football grounds across Victoria using OpenStreetMap
via the OSMnx library. OSM tags many community football ovals with
`sport=australian_football` or `leisure=pitch` + `sport=australian_football`,
which gives us a clean, programmatic way to get statewide coverage without
scraping any official site.

Output: data/raw/afl_clubs_vic.geojson and afl_clubs_vic.csv
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_RAW.mkdir(parents=True, exist_ok=True)


def fetch_afl_grounds_vic() -> gpd.GeoDataFrame:
    """
    Query OpenStreetMap for all Australian Rules Football grounds in Victoria.
    """
    print("Querying OpenStreetMap for Australian Rules Football venues in Victoria...")
    print("(This may take 1-3 minutes - OSMnx is querying the Overpass API)")

    tags = {
        "sport": "australian_football",
        "leisure": ["pitch", "sports_centre", "stadium"],
    }

    place = "Victoria, Australia"
    gdf = ox.features_from_place(place, tags=tags)

    if "sport" in gdf.columns:
        gdf = gdf[gdf["sport"].astype(str).str.contains("australian", case=False, na=False)]
    else:
        print("WARNING: no 'sport' tag in returned features. Check query.")
        return gpd.GeoDataFrame()

    # Convert polygons to centroids so every row is a point
    gdf = gdf.to_crs(epsg=3857)
    gdf["geometry"] = gdf.geometry.centroid
    gdf = gdf.to_crs(epsg=4326)

    keep_cols = ["name", "sport", "leisure", "addr:suburb", "addr:postcode", "geometry"]
    available = [c for c in keep_cols if c in gdf.columns]
    gdf = gdf[available].copy()

    if "name" in gdf.columns:
        before = len(gdf)
        gdf = gdf.dropna(subset=["name"])
        print(f"  Dropped {before - len(gdf)} unnamed venues.")

    gdf["latitude"] = gdf.geometry.y
    gdf["longitude"] = gdf.geometry.x
    gdf = gdf.reset_index(drop=True)

    print(f"Found {len(gdf)} Australian Rules Football venues in Victoria.")
    return gdf


def main():
    gdf = fetch_afl_grounds_vic()

    if len(gdf) == 0:
        print("No data returned. Aborting.")
        return

    out_geojson = DATA_RAW / "afl_clubs_vic.geojson"
    out_csv = DATA_RAW / "afl_clubs_vic.csv"

    gdf.to_file(out_geojson, driver="GeoJSON")
    gdf.drop(columns="geometry").to_csv(out_csv, index=False)

    print(f"\nSaved: {out_geojson}")
    print(f"Saved: {out_csv}")
    print(f"\nPreview:")
    print(gdf.head(10))


if __name__ == "__main__":
    main()
