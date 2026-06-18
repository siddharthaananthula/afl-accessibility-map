"""
underserved.py

Day 4 of the Grassroots Footy Accessibility Map.

Pivots from venue-level to AREA-level analysis. For each Victorian SA2:
  - Counts how many AFL venues fall inside it
  - Calculates venues per 10,000 residents
  - Combines with SEIFA decile to find equity gaps
  - Identifies "underserved" SA2s: significant population, few/no venues

Outputs:
  data/processed/sa2_venue_density.csv         (one row per Victorian SA2)
  data/processed/underserved_areas.csv         (top underserved SA2s)
  outputs/density_by_decile.png                (boxplot: venue rate by decile)
  outputs/seifa_vs_density_scatter.png         (SA2-level scatter)
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

# Min population to consider for "underserved" lists. Tiny SA2s with no people
# can technically have zero venues per 10k people but it's not interesting.
MIN_POP_FOR_UNDERSERVED = 5000


def load_clubs() -> gpd.GeoDataFrame:
    """Load AFL venues from Day 1."""
    return gpd.read_file(CLUBS_PATH)


def load_vic_sa2_with_seifa() -> gpd.GeoDataFrame:
    """
    Load SA2 boundaries (Vic only) and join with SEIFA decile + population.
    Re-uses logic from Day 2's seifa_join.py but as a standalone import here
    so this script can run independently.
    """
    from seifa_join import load_seifa, load_sa2_vic_boundaries
    seifa = load_seifa()
    boundaries = load_sa2_vic_boundaries()
    merged = boundaries.merge(seifa, on="sa2_code", how="left", suffixes=("", "_seifa"))
    return merged


def count_venues_per_sa2(clubs: gpd.GeoDataFrame,
                         sa2: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Spatial join AFL venues into SA2 polygons, then aggregate to one row per SA2
    with venue count.
    """
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
    """Add venues per 10,000 residents. Set to NaN where population is 0."""
    sa2 = sa2.copy()
    sa2["venues_per_10k"] = np.where(
        sa2["population"].fillna(0) > 0,
        (sa2["venue_count"] / sa2["population"]) * 10_000,
        np.nan,
    )
    return sa2


def correlation_summary(sa2: gpd.GeoDataFrame) -> dict:
    """
    Correlation between SEIFA decile and venues-per-10k.
    Restrict to SA2s with population > MIN_POP so we don't have noise from
    tiny industrial parcels.
    """
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
    """
    Find SA2s with substantial population but few/no venues.
    Sort by population (high) and venue_count (low) to find the worst gaps.
    """
    sub = sa2[
        (sa2["population"] > MIN_POP_FOR_UNDERSERVED)
        & (sa2["venue_count"] <= 1)  # 0 or 1 venue — minimal community provision
    ].copy()

    sub = sub.sort_values(["venue_count", "population"], ascending=[True, False])
    cols = ["sa2_name", "sa3_name", "region", "population", "venue_count",
            "venues_per_10k", "irsd_decile"]
    out = sub[cols].head(top_n).reset_index(drop=True)
    return out


def plot_density_by_decile(sa2: gpd.GeoDataFrame, out_path: Path):
    """Boxplot: venues per 10k residents, grouped by SEIFA decile."""
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

    ax.set_title("AFL venues per 10,000 residents, by SEIFA decile of the SA2\n"
                 "(SA2s with population > 5,000 only)",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile")
    ax.set_ylabel("Venues per 10,000 residents")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_scatter(sa2: gpd.GeoDataFrame, out_path: Path):
    """Scatter: SEIFA decile (jittered) vs venues per 10k."""
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
    ax.set_title("Each dot is a Victorian SA2 (>5k residents)\n"
                 "Venue density vs SEIFA decile",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile (1 = most disadvantaged, 10 = most advantaged)")
    ax.set_ylabel("Venues per 10,000 residents")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    print("Loading inputs...")
    clubs = load_clubs()
    sa2 = load_vic_sa2_with_seifa()
    print(f"  Venues: {len(clubs)}  |  Victorian SA2s: {len(sa2)}")

    print("\nCounting venues per SA2 (spatial join)...")
    sa2 = count_venues_per_sa2(clubs, sa2)
    sa2 = compute_density(sa2)

    # Save SA2-level table
    cols_save = ["sa2_code", "sa2_name", "sa3_name", "region",
                 "population", "venue_count", "venues_per_10k",
                 "irsd_decile", "irsd_score"]
    cols_available = [c for c in cols_save if c in sa2.columns]
    out_csv = DATA_PROCESSED / "sa2_venue_density.csv"
    sa2[cols_available].to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")

    # Stats
    corr = correlation_summary(sa2)
    print("\n" + "=" * 60)
    print("DAY 4 SUMMARY")
    print("=" * 60)
    print(f"Total Victorian SA2s analysed: {len(sa2)}")
    print(f"SA2s with population > {MIN_POP_FOR_UNDERSERVED}: "
          f"{(sa2['population'] > MIN_POP_FOR_UNDERSERVED).sum()}")
    print(f"SA2s with zero venues: {(sa2['venue_count'] == 0).sum()}")

    print(f"\nCorrelation between SEIFA decile and venues-per-10k "
          f"(n={corr['n']}):")
    if corr["pearson"] is not None:
        print(f"  Pearson r  : {corr['pearson']:+.3f}")
        print(f"  Spearman r : {corr['spearman']:+.3f}")
    else:
        print("  Insufficient data.")

    # Underserved list
    print("\nTop underserved SA2s (population > "
          f"{MIN_POP_FOR_UNDERSERVED}, 0-1 venues):")
    underserved = find_underserved(sa2, top_n=15)
    print(underserved.to_string(index=False))
    underserved_csv = DATA_PROCESSED / "underserved_areas.csv"
    underserved.to_csv(underserved_csv, index=False)
    print(f"\nSaved: {underserved_csv}")

    # Plots
    print("\nGenerating plots...")
    plot_density_by_decile(sa2, OUTPUTS / "density_by_decile.png")
    plot_scatter(sa2, OUTPUTS / "seifa_vs_density_scatter.png")


if __name__ == "__main__":
    main()