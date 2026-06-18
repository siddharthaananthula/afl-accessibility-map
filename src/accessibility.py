"""
accessibility.py

Day 3 (part 2) of the Grassroots Footy Accessibility Map.

For each AFL venue, calculate:
  - Distance to nearest train station (in metres)
  - Distance to nearest tram stop (in metres)
  - Distance to nearest bus stop (in metres)
  - Composite accessibility score (0-100)

The composite score weights modes by capacity/frequency:
  - Train (highest weight): high-capacity, frequent service
  - Tram (medium):          frequent in inner Melbourne
  - Bus (lowest):           ubiquitous but lower frequency

Output:
  data/processed/clubs_with_accessibility.csv
  data/processed/clubs_full_metrics.csv   (combined with SEIFA from Day 2)
  outputs/accessibility_distribution.png
  outputs/accessibility_by_decile.png
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
STOPS_PATH = DATA_PROCESSED / "ptv_stops.geojson"
SEIFA_CSV_PATH = DATA_PROCESSED / "clubs_with_seifa.csv"

# Projected CRS for accurate metre-based distances in Victoria.
# EPSG:7855 is GDA2020 / MGA Zone 55 — covers Melbourne and most of Victoria.
METRIC_CRS = "EPSG:7855"

# Distance threshold per mode (metres) used in the composite score.
# Within this distance you score 100; beyond 2× this distance you score 0;
# in between, score decays linearly.
MODE_REACH_M = {
    "train": 800,    # 10-min walk; trains pull from a wider catchment
    "tram":  600,    # 7-8 min walk; trams are closer-spaced
    "bus":   400,    # 5-min walk; standard bus stop walkshed
}

# How much each mode contributes to the composite (must sum to 1.0).
# Trains weighted highest because of capacity/frequency.
MODE_WEIGHTS = {
    "train": 0.45,
    "tram":  0.30,
    "bus":   0.25,
}


def load_inputs():
    """Load AFL venues and PTV stops, reproject both to the same metric CRS."""
    print("Loading venues and transit stops...")
    clubs = gpd.read_file(CLUBS_PATH).to_crs(METRIC_CRS)
    stops = gpd.read_file(STOPS_PATH).to_crs(METRIC_CRS)
    print(f"  Venues: {len(clubs)}")
    print(f"  Stops:  {len(stops)} ({stops['mode'].value_counts().to_dict()})")
    return clubs, stops


def nearest_distance(clubs: gpd.GeoDataFrame,
                     stops: gpd.GeoDataFrame,
                     mode_label: str) -> pd.Series:
    """
    For each venue, return the distance to the nearest stop of a given mode.

    Uses GeoPandas' sjoin_nearest which is backed by an R-tree spatial index,
    so this scales easily to 30,000+ stops without slowing down.
    """
    mode_stops = stops[stops["mode"] == mode_label].copy()
    if len(mode_stops) == 0:
        print(f"  No stops for mode={mode_label}, returning NaN.")
        return pd.Series([np.nan] * len(clubs), index=clubs.index)

    print(f"  Computing nearest {mode_label} stop for {len(clubs)} venues "
          f"against {len(mode_stops)} {mode_label} stops...")

    joined = gpd.sjoin_nearest(
        clubs[["geometry"]].reset_index(),
        mode_stops[["geometry"]],
        distance_col="dist_m",
    )

    # If two stops are equidistant, sjoin_nearest can return >1 row per venue.
    # Take the minimum per original venue index.
    result = joined.groupby("index")["dist_m"].min()
    return result.reindex(clubs.index)


def linear_decay_score(distance_m: float, reach_m: int) -> float:
    """
    Score from 0 to 100 based on distance from nearest stop.

    - <= reach_m         : score 100
    - >= 2 * reach_m     : score 0
    - linear in between
    """
    if pd.isna(distance_m):
        return 0.0
    if distance_m <= reach_m:
        return 100.0
    if distance_m >= 2 * reach_m:
        return 0.0
    return 100.0 * (1 - (distance_m - reach_m) / reach_m)


def add_accessibility_columns(clubs: gpd.GeoDataFrame,
                              stops: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute per-mode distances, per-mode scores, and composite score."""
    out = clubs.copy()

    for mode in ["train", "tram", "bus"]:
        out[f"dist_{mode}_m"] = nearest_distance(out, stops, mode)
        out[f"score_{mode}"] = out[f"dist_{mode}_m"].apply(
            lambda d: linear_decay_score(d, MODE_REACH_M[mode])
        )

    # Composite weighted score
    out["accessibility_score"] = (
        MODE_WEIGHTS["train"] * out["score_train"]
        + MODE_WEIGHTS["tram"] * out["score_tram"]
        + MODE_WEIGHTS["bus"]  * out["score_bus"]
    ).round(1)

    return out


def merge_with_seifa(clubs_acc: gpd.GeoDataFrame) -> pd.DataFrame:
    """Bring SEIFA decile from Day 2 onto the venue records."""
    seifa = pd.read_csv(SEIFA_CSV_PATH)
    # We join on name + lat/lon to be robust. Pre-round to 5 decimals.
    seifa["_lat_r"] = seifa["latitude"].round(5)
    seifa["_lon_r"] = seifa["longitude"].round(5)

    clubs_acc = clubs_acc.copy()
    clubs_acc["_lat_r"] = clubs_acc["latitude"].round(5)
    clubs_acc["_lon_r"] = clubs_acc["longitude"].round(5)

    keep = ["name", "_lat_r", "_lon_r", "sa2_name", "sa3_name", "region",
            "irsd_decile", "irsd_score"]
    keep_existing = [c for c in keep if c in seifa.columns]
    merged = clubs_acc.merge(seifa[keep_existing], on=["name", "_lat_r", "_lon_r"],
                             how="left")
    merged = merged.drop(columns=["_lat_r", "_lon_r"])
    return merged


def plot_score_distribution(clubs: pd.DataFrame, out_path: Path):
    """Histogram of composite accessibility scores."""
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(clubs["accessibility_score"], bins=20,
            color="#1f6feb", edgecolor="white")
    ax.set_title("Distribution of accessibility scores across AFL venues",
                 fontsize=12, pad=12)
    ax.set_xlabel("Composite accessibility score (0 = remote, 100 = excellent PT)")
    ax.set_ylabel("Number of venues")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def plot_score_by_decile(clubs: pd.DataFrame, out_path: Path):
    """Boxplot: accessibility score grouped by SEIFA decile."""
    sub = clubs.dropna(subset=["irsd_decile", "accessibility_score"]).copy()
    sub["irsd_decile"] = sub["irsd_decile"].astype(int)

    fig, ax = plt.subplots(figsize=(9, 5))
    deciles = sorted(sub["irsd_decile"].unique())
    data = [sub.loc[sub["irsd_decile"] == d, "accessibility_score"] for d in deciles]

    bp = ax.boxplot(data, positions=deciles, widths=0.6, patch_artist=True,
                    medianprops={"color": "black"})
    for patch in bp["boxes"]:
        patch.set_facecolor("#1f6feb")
        patch.set_alpha(0.7)

    ax.set_title("Accessibility score by SEIFA decile of venue's surrounding area\n"
                 "(1 = most disadvantaged, 10 = most advantaged)",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile")
    ax.set_ylabel("Composite accessibility score")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  Saved: {out_path}")


def main():
    clubs, stops = load_inputs()

    print("\nCalculating distances and scores...")
    clubs_acc = add_accessibility_columns(clubs, stops)

    print("\nMerging with SEIFA results from Day 2...")
    full = merge_with_seifa(clubs_acc)

    # Save accessibility-only and combined-metrics CSVs
    acc_csv = DATA_PROCESSED / "clubs_with_accessibility.csv"
    full_csv = DATA_PROCESSED / "clubs_full_metrics.csv"
    clubs_acc.drop(columns="geometry").to_csv(acc_csv, index=False)
    full.drop(columns="geometry").to_csv(full_csv, index=False)
    print(f"Saved: {acc_csv}")
    print(f"Saved: {full_csv}")

    # Plots
    print("\nGenerating plots...")
    plot_score_distribution(full, OUTPUTS / "accessibility_distribution.png")
    plot_score_by_decile(full, OUTPUTS / "accessibility_by_decile.png")

    # Summary
    print("\n" + "=" * 60)
    print("DAY 3 SUMMARY")
    print("=" * 60)
    print(f"Venues processed: {len(full)}")
    print(f"\nDistance to nearest stop (median, metres):")
    for mode in ["train", "tram", "bus"]:
        med = full[f"dist_{mode}_m"].median()
        print(f"  {mode:5s}: {med:>8.0f} m")

    print(f"\nComposite accessibility score:")
    print(f"  Mean   : {full['accessibility_score'].mean():.1f}")
    print(f"  Median : {full['accessibility_score'].median():.1f}")
    print(f"  Min    : {full['accessibility_score'].min():.1f}")
    print(f"  Max    : {full['accessibility_score'].max():.1f}")

    # Cross-tab: mean accessibility per SEIFA decile
    sub = full.dropna(subset=["irsd_decile"])
    if len(sub) > 0:
        print(f"\nMean accessibility score by SEIFA decile:")
        by_dec = sub.groupby(sub["irsd_decile"].astype(int))["accessibility_score"].agg(["mean", "count"])
        print(by_dec.round(1).to_string())


if __name__ == "__main__":
    main()