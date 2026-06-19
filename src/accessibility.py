"""
accessibility.py

For each AFL venue, calculates distance to the nearest train, tram, and
bus stop, then combines them into a weighted composite accessibility
score (0-100) using linear distance decay.

Weights: train 45%, tram 30%, bus 25% - reflecting capacity and frequency
of typical service. Per-mode reach distances are 800m / 600m / 400m
respectively (full score within reach, zero beyond 2x reach, linear in between).

Outputs:
  data/processed/clubs_with_accessibility.csv
  data/processed/clubs_full_metrics.csv  (includes SEIFA from seifa_join.py)
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

# Projected CRS for metre-based distances in Victoria (MGA Zone 55).
METRIC_CRS = "EPSG:7855"

MODE_REACH_M = {
    "train": 800,
    "tram":  600,
    "bus":   400,
}

MODE_WEIGHTS = {
    "train": 0.45,
    "tram":  0.30,
    "bus":   0.25,
}


def load_inputs():
    clubs = gpd.read_file(CLUBS_PATH).to_crs(METRIC_CRS)
    stops = gpd.read_file(STOPS_PATH).to_crs(METRIC_CRS)
    print(f"Venues: {len(clubs)}, stops: {len(stops)}")
    return clubs, stops


def nearest_distance(clubs: gpd.GeoDataFrame,
                     stops: gpd.GeoDataFrame,
                     mode_label: str) -> pd.Series:
    """Distance to nearest stop of a given mode for each venue."""
    mode_stops = stops[stops["mode"] == mode_label].copy()
    if len(mode_stops) == 0:
        return pd.Series([np.nan] * len(clubs), index=clubs.index)

    joined = gpd.sjoin_nearest(
        clubs[["geometry"]].reset_index(),
        mode_stops[["geometry"]],
        distance_col="dist_m",
    )
    # Tie-break when two stops are equidistant
    return joined.groupby("index")["dist_m"].min().reindex(clubs.index)


def linear_decay_score(distance_m: float, reach_m: int) -> float:
    """100 within reach, 0 beyond 2x reach, linear between."""
    if pd.isna(distance_m):
        return 0.0
    if distance_m <= reach_m:
        return 100.0
    if distance_m >= 2 * reach_m:
        return 0.0
    return 100.0 * (1 - (distance_m - reach_m) / reach_m)


def add_accessibility_columns(clubs: gpd.GeoDataFrame,
                              stops: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = clubs.copy()
    for mode in ["train", "tram", "bus"]:
        out[f"dist_{mode}_m"] = nearest_distance(out, stops, mode)
        out[f"score_{mode}"] = out[f"dist_{mode}_m"].apply(
            lambda d: linear_decay_score(d, MODE_REACH_M[mode])
        )

    out["accessibility_score"] = (
        MODE_WEIGHTS["train"] * out["score_train"]
        + MODE_WEIGHTS["tram"] * out["score_tram"]
        + MODE_WEIGHTS["bus"]  * out["score_bus"]
    ).round(1)
    return out


def merge_with_seifa(clubs_acc: gpd.GeoDataFrame) -> pd.DataFrame:
    """Bring SEIFA decile in via name + rounded coordinate join."""
    seifa = pd.read_csv(SEIFA_CSV_PATH)
    seifa["_lat_r"] = seifa["latitude"].round(5)
    seifa["_lon_r"] = seifa["longitude"].round(5)

    clubs_acc = clubs_acc.copy()
    clubs_acc["_lat_r"] = clubs_acc["latitude"].round(5)
    clubs_acc["_lon_r"] = clubs_acc["longitude"].round(5)

    keep = ["name", "_lat_r", "_lon_r", "sa2_name", "sa3_name", "region",
            "irsd_decile", "irsd_score"]
    keep = [c for c in keep if c in seifa.columns]
    merged = clubs_acc.merge(seifa[keep], on=["name", "_lat_r", "_lon_r"], how="left")
    return merged.drop(columns=["_lat_r", "_lon_r"])


def plot_score_distribution(clubs: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(clubs["accessibility_score"], bins=20,
            color="#1f6feb", edgecolor="white")
    ax.set_title("Distribution of composite accessibility scores",
                 fontsize=12, pad=12)
    ax.set_xlabel("Accessibility score (0 = remote, 100 = excellent PT)")
    ax.set_ylabel("Number of venues")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_score_by_decile(clubs: pd.DataFrame, out_path: Path):
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

    ax.set_title("Accessibility score by SEIFA decile of surrounding area",
                 fontsize=12, pad=12)
    ax.set_xlabel("SEIFA IRSD decile (1 = most disadvantaged)")
    ax.set_ylabel("Composite accessibility score")
    ax.set_xticks(range(1, 11))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main():
    clubs, stops = load_inputs()
    clubs_acc = add_accessibility_columns(clubs, stops)
    full = merge_with_seifa(clubs_acc)

    clubs_acc.drop(columns="geometry").to_csv(
        DATA_PROCESSED / "clubs_with_accessibility.csv", index=False
    )
    full.drop(columns="geometry").to_csv(
        DATA_PROCESSED / "clubs_full_metrics.csv", index=False
    )

    plot_score_distribution(full, OUTPUTS / "accessibility_distribution.png")
    plot_score_by_decile(full, OUTPUTS / "accessibility_by_decile.png")

    print(f"\nMedian distance to nearest stop:")
    for mode in ["train", "tram", "bus"]:
        print(f"  {mode}: {full[f'dist_{mode}_m'].median():.0f} m")
    print(f"\nComposite score - mean: {full['accessibility_score'].mean():.1f}, "
          f"median: {full['accessibility_score'].median():.1f}")

    sub = full.dropna(subset=["irsd_decile"])
    if len(sub) > 0:
        by_dec = sub.groupby(sub["irsd_decile"].astype(int))["accessibility_score"].mean()
        print(f"\nMean accessibility by SEIFA decile:")
        print(by_dec.round(1).to_string())


if __name__ == "__main__":
    main()