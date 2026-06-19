"""
underserved.py

Pivots from venue-level to SA2-level analysis. For each Victorian SA2,
counts AFL venues, computes venues per 10,000 residents, and combines
with SEIFA decile to surface underserved areas: populated SA2s with few
or no venues.

Outputs:
  data/processed/sa2_venue_density.csv
  data/processed/underserved_areas.csv
  outputs/density_by_decile.png
  outputs/seifa_vs_density_scatter.png
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
plt.rcParams["figure.dpi"] = 110

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

CLUBS_PATH = DATA_RAW / "afl_clubs_vic.geojson"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"
FULL_METRICS_PATH = DATA_PROCESSED / "clubs_full_metrics.csv"

# Minimum population threshold to consider an SA2 "populated" for the
# purposes of the underserved list. Avoids noise from tiny industrial
# parcels and similar zero-population polygons.
MIN_POP_FOR_UNDERSERVED = 5000


def load_clubs() -> gpd.GeoDataFrame:
    return gpd.read_file(CLUBS_PATH)


def load_vic_sa2_with_seifa() -> gpd.GeoDataFrame:
    """Reuse load functions from seifa_join so logic stays consistent."""
    from seifa_join import load_seifa, load_sa2_vic_boundaries
    seifa = load_seifa()
    boundaries = load_sa2_vic_boundaries()
    return boundaries.merge(seifa, on="sa2_code", how="left", suffixes=("", "_seifa"))


def count_venues_per_sa2(clubs: gpd.GeoDataFrame,
                         sa2: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    clubs = clubs.to_crs(sa2.crs)
    joined = gpd.sjoin(
        clubs[["name", "geometry"]],
        sa2[["sa2_code", "geometry"]],
        how="inner",
        predicate="within",
    )
    counts = joined.groupby("sa2_code").size().rename("venue_count")
    out = sa2.merge(counts, on="sa2_code", how="left")
    out["venue_count"] = out["venue_count"].fillna(0).astype(int)
    return out


def compute_density(sa2: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    sa2 = sa2.copy()
    sa2["venues_per_10k"] = np.where(
        sa2["population"].fillna(0) > 0,
        (sa2["venue_count"] / sa2["population"]) * 10_000,
        np.nan,
    )
    return sa2


def correlation_summary(sa2: gpd.GeoDataFrame) -> dict:
    sub = sa2[
        (sa2["population"] > MIN_POP_FOR_UNDERSERVED)
        & (sa2["irsd_decile"].notna())
        & (sa2["venues_per_10k"].notna())
    ]
    if len(sub) < 10:
        return {"n": len(sub), "pearson": None, "spearman": None}
    pearson = sub[["irsd_decile", "venues_per_10k"]].corr().iloc[0, 1]
    spearman = sub[["irsd_decile", "venues_per_10k"]].corr(method="spearman").iloc[0, 1]
    return {"n": len(sub), "pearson": pearson, "spearman": spearman}


def find_underserved(sa2: gpd.GeoDataFrame, top_n: int = 15) -> pd.DataFrame:
    """SA2s with substantial population but 0 or 1 venues, sorted by pop."""
    sub = sa2[
        (sa2["population"] > MIN_POP_FOR_UNDERSERVED)
        & (sa2["venue_count"] <= 1)
    ].copy()
    sub = sub.sort_values(["venue_count", "population"], ascending=[True, False])
    cols = ["sa2_name", "sa3_name", "region", "population", "venue_count",
            "venues_per_10k", "irsd_decile"]
    return sub[cols].head(top_n).reset_index(drop=True)


def plot_density_by_decile(sa2: gpd.GeoDataFrame, out_path: Path):
    sub = sa2[
        (sa2["population"] > MIN_POP_FOR_UNDERSERVED)
        & (sa2["irsd_decile"].notna())
    ].copy()
    sub["irsd_decile"] = sub["irsd_decile"].astype(int)
    sub["venues_per_10k"] = sub["venues_per_10k"].fillna(0)

    fig, ax = plt.subplots(figsize=(9, 5))
    deciles = sorted(sub["irsd_decile"].unique())
    data = [sub.loc[sub["irsd_decile"] == d, "venues_per_10k"] for d in deciles]

    bp = ax.boxplot(data, positions=deciles, widths=0.6, patch_artist=True,
                    medianprops={"color": "black"}, showfliers=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#1f6feb")
        patch.set_alpha(0.7)

    ax.set_title("AFL venues per 10,000 residents, by SEIFA decile of the SA2",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile")
    ax.set_ylabel("Venues per 10,000 residents")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_scatter(sa2: gpd.GeoDataFrame, out_path: Path):
    sub = sa2[
        (sa2["population"] > MIN_POP_FOR_UNDERSERVED)
        & (sa2["irsd_decile"].notna())
    ].copy()
    sub["irsd_decile"] = sub["irsd_decile"].astype(int)
    sub["venues_per_10k"] = sub["venues_per_10k"].fillna(0)

    np.random.seed(0)
    jitter = np.random.uniform(-0.18, 0.18, size=len(sub))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(sub["irsd_decile"] + jitter, sub["venues_per_10k"],
               alpha=0.55, s=24, color="#1f6feb")
    ax.set_title("SA2-level venue density vs SEIFA decile",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile (1 = most disadvantaged, 10 = most advantaged)")
    ax.set_ylabel("Venues per 10,000 residents")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main():
    clubs = load_clubs()
    sa2 = load_vic_sa2_with_seifa()
    sa2 = count_venues_per_sa2(clubs, sa2)
    sa2 = compute_density(sa2)

    cols_save = ["sa2_code", "sa2_name", "sa3_name", "region",
                 "population", "venue_count", "venues_per_10k",
                 "irsd_decile", "irsd_score"]
    cols_save = [c for c in cols_save if c in sa2.columns]
    sa2[cols_save].to_csv(DATA_PROCESSED / "sa2_venue_density.csv", index=False)

    corr = correlation_summary(sa2)
    underserved = find_underserved(sa2, top_n=15)
    underserved.to_csv(DATA_PROCESSED / "underserved_areas.csv", index=False)

    plot_density_by_decile(sa2, OUTPUTS / "density_by_decile.png")
    plot_scatter(sa2, OUTPUTS / "seifa_vs_density_scatter.png")

    print(f"Victorian SA2s: {len(sa2)}")
    print(f"Populated SA2s (>{MIN_POP_FOR_UNDERSERVED}): "
          f"{(sa2['population'] > MIN_POP_FOR_UNDERSERVED).sum()}")
    print(f"SA2s with zero venues: {(sa2['venue_count'] == 0).sum()}")
    if corr["pearson"] is not None:
        print(f"\nSEIFA decile vs venues-per-10k (n={corr['n']}):")
        print(f"  Pearson r  : {corr['pearson']:+.3f}")
        print(f"  Spearman r : {corr['spearman']:+.3f}")
    print(f"\nTop underserved SA2s:")
    print(underserved.to_string(index=False))


if __name__ == "__main__":
    main()