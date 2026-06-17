"""
seifa_join.py

Day 2 of the Grassroots Footy Accessibility Map.

Joins three datasets:
  1. SA2 boundary polygons (geometry of every Victorian suburb-sized area)
  2. SEIFA 2021 IRSD scores (disadvantage decile per SA2)
  3. Our 252 AFL venues from Day 1

For each AFL venue, finds which SA2 polygon contains it (point-in-polygon)
and tags it with that SA2's SEIFA decile.

Output:
  data/processed/sa2_vic_with_seifa.geojson
  data/processed/clubs_with_seifa.csv
  outputs/seifa_distribution.png
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
plt.rcParams["figure.dpi"] = 110

# Project paths
ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

# Input files
SEIFA_PATH = DATA_RAW / "seifa_2021_sa2.xlsx"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"
CLUBS_PATH = DATA_RAW / "afl_clubs_vic.geojson"


def load_seifa() -> pd.DataFrame:
    """
    Load SEIFA Table 2 (IRSD - Index of Relative Socio-economic Disadvantage).
    Data starts at row 6 (0-indexed). We want SA2 code, name, and decile.
    """
    print("Loading SEIFA IRSD data...")

    df = pd.read_excel(
        SEIFA_PATH,
        sheet_name="Table 2",
        header=None,
        skiprows=6,           # skip header rows
        usecols=[0, 1, 3, 6], # 9-digit code, name, score, decile (within Australia)
        names=["sa2_code", "sa2_name", "irsd_score", "irsd_decile"],
    )

    # Drop the trailing footnote rows that have NaN codes
    df = df.dropna(subset=["sa2_code"])
    df["sa2_code"] = df["sa2_code"].astype(str).str.strip()

    # Decile and score should be numeric; coerce stray strings to NaN
    df["irsd_decile"] = pd.to_numeric(df["irsd_decile"], errors="coerce")
    df["irsd_score"] = pd.to_numeric(df["irsd_score"], errors="coerce")

    # Drop areas with no decile (e.g. industrial zones, port areas)
    df = df.dropna(subset=["irsd_decile"])
    df["irsd_decile"] = df["irsd_decile"].astype(int)

    print(f"  {len(df)} SA2 areas with SEIFA scores (national).")
    return df


def load_sa2_vic_boundaries() -> gpd.GeoDataFrame:
    """Load SA2 shapefile, filter to Victoria, keep essential columns."""
    print("Loading SA2 boundary polygons...")
    gdf = gpd.read_file(SA2_SHP_PATH)

    vic = gdf[gdf["STE_NAME21"] == "Victoria"].copy()
    vic = vic[["SA2_CODE21", "SA2_NAME21", "SA3_NAME21", "GCC_NAME21", "geometry"]]
    vic = vic.rename(columns={
        "SA2_CODE21": "sa2_code",
        "SA2_NAME21": "sa2_name",
        "SA3_NAME21": "sa3_name",
        "GCC_NAME21": "region",
    })
    vic["sa2_code"] = vic["sa2_code"].astype(str).str.strip()
    print(f"  {len(vic)} Victorian SA2 polygons.")
    return vic


def merge_seifa_with_boundaries(
    boundaries: gpd.GeoDataFrame, seifa: pd.DataFrame
) -> gpd.GeoDataFrame:
    """Attach SEIFA decile + score to each SA2 polygon by SA2 code."""
    print("Merging SEIFA scores onto SA2 boundaries...")
    merged = boundaries.merge(seifa, on="sa2_code", how="left", suffixes=("", "_seifa"))
    n_with = merged["irsd_decile"].notna().sum()
    n_without = merged["irsd_decile"].isna().sum()
    print(f"  Matched: {n_with}  |  Unmatched: {n_without}")
    return merged


def spatial_join_clubs(
    sa2_with_seifa: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Read AFL venues, ensure same CRS as SA2 boundaries, and do a point-in-polygon
    spatial join so each venue gets its containing SA2's SEIFA decile.
    """
    print("Loading AFL venues from Day 1...")
    clubs = gpd.read_file(CLUBS_PATH)
    print(f"  {len(clubs)} venues.")

    # Reproject clubs to match the SA2 CRS (EPSG:7844)
    clubs = clubs.to_crs(sa2_with_seifa.crs)

    print("Performing point-in-polygon spatial join...")
    joined = gpd.sjoin(
        clubs,
        sa2_with_seifa[["sa2_code", "sa2_name", "sa3_name", "region",
                        "irsd_decile", "irsd_score", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined.drop(columns=["index_right"], errors="ignore")
    n_matched = joined["irsd_decile"].notna().sum()
    print(f"  Venues matched to a SEIFA decile: {n_matched} / {len(joined)}")
    return joined


def plot_distribution(clubs_seifa: gpd.GeoDataFrame) -> Path:
    """Bar chart: how many AFL venues fall in each SEIFA decile (1-10)."""
    print("Plotting decile distribution...")

    counts = (
        clubs_seifa["irsd_decile"]
        .dropna()
        .astype(int)
        .value_counts()
        .reindex(range(1, 11), fill_value=0)
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(counts.index, counts.values, color="#1f6feb", edgecolor="white")
    ax.set_title(
        "AFL community venues across Victoria, by SEIFA decile\n"
        "(1 = most disadvantaged, 10 = most advantaged)",
        fontsize=12, pad=12,
    )
    ax.set_xlabel("SEIFA IRSD decile")
    ax.set_ylabel("Number of AFL venues")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, value in zip(bars, counts.values):
        if value > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.3,
                    str(value), ha="center", fontsize=9)

    fig.tight_layout()
    out_path = OUTPUTS / "seifa_distribution.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved: {out_path}")
    return out_path


def main():
    # 1. Load both data sources
    seifa = load_seifa()
    boundaries = load_sa2_vic_boundaries()

    # 2. Merge them so each polygon has its decile
    sa2_with_seifa = merge_seifa_with_boundaries(boundaries, seifa)

    # 3. Save enriched polygons for use later (mapping in Day 5)
    out_geo = DATA_PROCESSED / "sa2_vic_with_seifa.geojson"
    sa2_with_seifa.to_file(out_geo, driver="GeoJSON")
    print(f"Saved: {out_geo}")

    # 4. Spatial join: tag each AFL venue with its SA2's decile
    clubs_seifa = spatial_join_clubs(sa2_with_seifa)

    # 5. Save the enriched club list
    out_csv = DATA_PROCESSED / "clubs_with_seifa.csv"
    clubs_seifa.drop(columns="geometry").to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")

    # 6. Plot the distribution - our first finding
    plot_distribution(clubs_seifa)

    # 7. Print summary statistics
    print("\n" + "=" * 60)
    print("DAY 2 SUMMARY")
    print("=" * 60)
    print(f"AFL venues processed: {len(clubs_seifa)}")
    matched = clubs_seifa["irsd_decile"].notna().sum()
    print(f"Successfully tagged with a SEIFA decile: {matched}")

    if matched > 0:
        median = clubs_seifa["irsd_decile"].median()
        bottom_3 = (clubs_seifa["irsd_decile"] <= 3).sum()
        top_3 = (clubs_seifa["irsd_decile"] >= 8).sum()
        print(f"Median decile of AFL venue locations: {median:.0f}")
        print(f"Venues in most-disadvantaged deciles (1-3): {bottom_3}"
              f" ({bottom_3 / matched:.1%})")
        print(f"Venues in most-advantaged deciles (8-10): {top_3}"
              f" ({top_3 / matched:.1%})")


if __name__ == "__main__":
    main()