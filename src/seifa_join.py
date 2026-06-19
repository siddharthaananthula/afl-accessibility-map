"""
seifa_join.py

Joins ABS SEIFA 2021 IRSD (Index of Relative Socio-economic Disadvantage)
scores onto SA2 boundary polygons, then spatially joins AFL venues to
their containing SA2 to attach a SEIFA decile to each venue.

Outputs:
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

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

SEIFA_PATH = DATA_RAW / "seifa_2021_sa2.xlsx"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"
CLUBS_PATH = DATA_RAW / "afl_clubs_vic.geojson"


def load_seifa() -> pd.DataFrame:
    """
    Read SEIFA Table 2 (IRSD), skipping the metadata rows. We pull SA2
    code, name, usual resident population, IRSD score, and IRSD decile.
    """
    df = pd.read_excel(
        SEIFA_PATH,
        sheet_name="Table 2",
        header=None,
        skiprows=6,
        usecols=[0, 1, 2, 3, 6],
        names=["sa2_code", "sa2_name", "population", "irsd_score", "irsd_decile"],
    )
    df = df.dropna(subset=["sa2_code"])
    df["sa2_code"] = df["sa2_code"].astype(str).str.strip()
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    df["irsd_decile"] = pd.to_numeric(df["irsd_decile"], errors="coerce")
    df["irsd_score"] = pd.to_numeric(df["irsd_score"], errors="coerce")
    df = df.dropna(subset=["irsd_decile"])
    df["irsd_decile"] = df["irsd_decile"].astype(int)
    df["population"] = df["population"].fillna(0).astype(int)
    return df


def load_sa2_vic_boundaries() -> gpd.GeoDataFrame:
    """Load the national SA2 shapefile and filter to Victoria."""
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
    return vic


def merge_seifa_with_boundaries(
    boundaries: gpd.GeoDataFrame, seifa: pd.DataFrame
) -> gpd.GeoDataFrame:
    return boundaries.merge(seifa, on="sa2_code", how="left", suffixes=("", "_seifa"))


def spatial_join_clubs(sa2_with_seifa: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Point-in-polygon join: each AFL venue inherits its SA2's SEIFA decile."""
    clubs = gpd.read_file(CLUBS_PATH).to_crs(sa2_with_seifa.crs)
    joined = gpd.sjoin(
        clubs,
        sa2_with_seifa[["sa2_code", "sa2_name", "sa3_name", "region",
                        "irsd_decile", "irsd_score", "geometry"]],
        how="left",
        predicate="within",
    )
    return joined.drop(columns=["index_right"], errors="ignore")


def plot_distribution(clubs_seifa: gpd.GeoDataFrame) -> Path:
    """Bar chart: count of AFL venues per SEIFA decile (1-10)."""
    counts = (
        clubs_seifa["irsd_decile"]
        .dropna().astype(int)
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
    return out_path


def main():
    seifa = load_seifa()
    boundaries = load_sa2_vic_boundaries()
    sa2_with_seifa = merge_seifa_with_boundaries(boundaries, seifa)
    sa2_with_seifa.to_file(DATA_PROCESSED / "sa2_vic_with_seifa.geojson", driver="GeoJSON")

    clubs_seifa = spatial_join_clubs(sa2_with_seifa)
    clubs_seifa.drop(columns="geometry").to_csv(
        DATA_PROCESSED / "clubs_with_seifa.csv", index=False
    )

    plot_distribution(clubs_seifa)

    matched = clubs_seifa["irsd_decile"].notna().sum()
    median = clubs_seifa["irsd_decile"].median()
    bottom_3 = (clubs_seifa["irsd_decile"] <= 3).sum()
    top_3 = (clubs_seifa["irsd_decile"] >= 8).sum()

    print(f"{len(clubs_seifa)} venues processed, {matched} tagged with SEIFA decile.")
    print(f"Median decile: {median:.0f}")
    print(f"Decile 1-3:  {bottom_3} venues ({bottom_3 / matched:.1%})")
    print(f"Decile 8-10: {top_3} venues ({top_3 / matched:.1%})")


if __name__ == "__main__":
    main()