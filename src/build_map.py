"""
build_map.py

Builds an interactive Folium/Leaflet map of the project's findings as a
single self-contained HTML file at docs/index.html (deployed via GitHub
Pages).

Layers:
  1. AFL venue markers, colour-coded by SEIFA decile (point-clustering enabled)
  2. SA2 polygons, choropleth-shaded by venues per 10,000 residents
  3. Top 15 underserved SA2s highlighted with red outlines
"""

import json
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from branca.colormap import LinearColormap
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

CLUBS_PATH = DATA_RAW / "afl_clubs_vic.geojson"
SA2_SHP_PATH = DATA_RAW / "sa2_shapefile" / "SA2_2021_AUST_GDA2020.shp"
FULL_METRICS_PATH = DATA_PROCESSED / "clubs_full_metrics.csv"
SA2_DENSITY_PATH = DATA_PROCESSED / "sa2_venue_density.csv"
UNDERSERVED_PATH = DATA_PROCESSED / "underserved_areas.csv"

MELBOURNE_CENTRE = [-37.81, 144.96]
DEFAULT_ZOOM = 8

# Viridis palette: dark purple (decile 1, most disadvantaged) -> bright yellow
SEIFA_COLOURS = {
    1: "#440154", 2: "#482878", 3: "#3e4a89", 4: "#31688e", 5: "#26828e",
    6: "#1f9e89", 7: "#35b779", 8: "#6ece58", 9: "#b5de2b", 10: "#fde725",
}


def load_data():
    venues = pd.read_csv(FULL_METRICS_PATH)
    sa2_density = pd.read_csv(SA2_DENSITY_PATH)
    underserved = pd.read_csv(UNDERSERVED_PATH)

    sa2 = gpd.read_file(SA2_SHP_PATH)
    sa2 = sa2[sa2["STE_NAME21"] == "Victoria"].copy()
    sa2 = sa2.rename(columns={"SA2_CODE21": "sa2_code", "SA2_NAME21": "sa2_name"})
    sa2["sa2_code"] = sa2["sa2_code"].astype(str)
    sa2_density["sa2_code"] = sa2_density["sa2_code"].astype(str)
    sa2 = sa2.merge(sa2_density, on="sa2_code", how="left", suffixes=("", "_d"))
    return venues, sa2, underserved


def venue_popup_html(row) -> str:
    name = row.get("name") or "Unnamed venue"
    suburb = row.get("sa2_name") or "—"
    decile = row.get("irsd_decile")
    decile_str = f"{int(decile)}" if pd.notna(decile) else "—"
    score = row.get("accessibility_score")
    score_str = f"{score:.1f}" if pd.notna(score) else "—"

    def fmt_dist(v):
        return f"{v:,.0f} m" if pd.notna(v) else "—"

    return f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; min-width: 220px;">
      <h4 style="margin:0 0 6px 0;">{name}</h4>
      <div style="color:#555; font-size:12px; margin-bottom:8px;">{suburb}</div>
      <table style="font-size:12px; border-collapse:collapse;">
        <tr><td><b>SEIFA decile</b></td><td>{decile_str} / 10</td></tr>
        <tr><td><b>Accessibility</b></td><td>{score_str} / 100</td></tr>
        <tr><td><b>Train (nearest)</b></td><td>{fmt_dist(row.get("dist_train_m"))}</td></tr>
        <tr><td><b>Tram (nearest)</b></td><td>{fmt_dist(row.get("dist_tram_m"))}</td></tr>
        <tr><td><b>Bus (nearest)</b></td><td>{fmt_dist(row.get("dist_bus_m"))}</td></tr>
      </table>
    </div>
    """


def build_map(venues: pd.DataFrame,
              sa2: gpd.GeoDataFrame,
              underserved: pd.DataFrame) -> folium.Map:
    m = folium.Map(
        location=MELBOURNE_CENTRE,
        zoom_start=DEFAULT_ZOOM,
        tiles="cartodbpositron",
        control_scale=True,
    )

    # SA2 venue-density choropleth
    sa2_layer = folium.FeatureGroup(name="SA2 venue density", show=False)
    max_density = sa2["venues_per_10k"].dropna().quantile(0.95)
    cmap = LinearColormap(
        ["#f7fbff", "#6baed6", "#08306b"],
        vmin=0, vmax=max(1, float(max_density)),
        caption="Venues per 10,000 residents (SA2)",
    )

    def style_sa2(feature):
        v = feature["properties"].get("venues_per_10k")
        try:
            v_num = float(v)
        except (TypeError, ValueError):
            v_num = None
        fill = cmap(v_num) if v_num is not None and v_num == v_num else "#eeeeee"
        return {
            "fillColor": fill, "color": "#888",
            "weight": 0.4, "fillOpacity": 0.55,
        }

    folium.GeoJson(
        sa2[["sa2_name", "population", "venue_count", "venues_per_10k",
             "irsd_decile", "geometry"]].fillna({"venues_per_10k": 0}),
        name="SA2 venue density",
        style_function=style_sa2,
        tooltip=folium.GeoJsonTooltip(
            fields=["sa2_name", "population", "venue_count",
                    "venues_per_10k", "irsd_decile"],
            aliases=["Area:", "Population:", "AFL venues:",
                     "Venues per 10k:", "SEIFA decile:"],
            sticky=True, labels=True, localize=True,
        ),
    ).add_to(sa2_layer)
    sa2_layer.add_to(m)
    cmap.add_to(m)

    # AFL venues, coloured by SEIFA decile
    venues_layer = folium.FeatureGroup(name="AFL venues (by SEIFA decile)", show=True)
    cluster = MarkerCluster(disableClusteringAtZoom=11).add_to(venues_layer)

    for _, row in venues.iterrows():
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
            continue
        decile = row.get("irsd_decile")
        colour = SEIFA_COLOURS.get(int(decile)) if pd.notna(decile) else "#888"
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup(venue_popup_html(row), max_width=300),
            tooltip=row.get("name", ""),
        ).add_to(cluster)
    venues_layer.add_to(m)

    # Top underserved SA2s highlighted
    underserved_layer = folium.FeatureGroup(name="Top 15 underserved areas", show=True)
    underserved_names = set(underserved["sa2_name"].astype(str))
    underserved_sa2 = sa2[sa2["sa2_name"].astype(str).isin(underserved_names)]

    for _, feat in underserved_sa2.iterrows():
        info = underserved[underserved["sa2_name"] == feat["sa2_name"]].iloc[0]
        pop = int(info["population"])
        decile = info.get("irsd_decile")
        decile_str = f"{int(decile)}" if pd.notna(decile) else "—"
        html = (
            f"<div style='font-family:Segoe UI,Arial; min-width:200px;'>"
            f"<h4 style='margin:0 0 6px 0; color:#b40000;'>{feat['sa2_name']}</h4>"
            f"<div style='font-size:12px;'>"
            f"<b>Population:</b> {pop:,}<br>"
            f"<b>AFL venues:</b> {info['venue_count']}<br>"
            f"<b>SEIFA decile:</b> {decile_str} / 10<br>"
            f"<b>Region:</b> {info['sa3_name']}"
            f"</div></div>"
        )
        folium.GeoJson(
            json.loads(gpd.GeoSeries([feat.geometry]).to_json())["features"][0],
            style_function=lambda x: {
                "color": "#b40000", "weight": 2.2,
                "fillColor": "#ff6b6b", "fillOpacity": 0.25,
            },
            tooltip=feat["sa2_name"],
            popup=folium.Popup(html, max_width=300),
        ).add_to(underserved_layer)
    underserved_layer.add_to(m)

    # SEIFA decile legend
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 12px; z-index: 9999;
                background: white; padding: 10px 12px; border: 1px solid #999;
                border-radius: 6px; font-family: Segoe UI, Arial; font-size: 12px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.15);">
      <div style="font-weight:600; margin-bottom:6px;">SEIFA decile of venue area</div>
    """
    for d in range(1, 11):
        c = SEIFA_COLOURS[d]
        label = "most disadvantaged" if d == 1 else ("most advantaged" if d == 10 else "")
        legend_html += (
            f"<div style='display:flex; align-items:center; margin:1px 0;'>"
            f"<span style='width:14px;height:14px;background:{c};display:inline-block;"
            f"border-radius:50%; margin-right:6px;'></span> Decile {d}"
            f" <span style='color:#888; margin-left:6px;'>{label}</span></div>"
        )
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    # Title overlay
    title_html = """
    <div style="position: fixed; top: 12px; left: 60px; z-index: 9999;
                background: white; padding: 10px 14px; border: 1px solid #ccc;
                border-radius: 6px; font-family: Segoe UI, Arial;
                box-shadow: 0 1px 4px rgba(0,0,0,0.15); max-width: 480px;">
      <div style="font-weight:700; font-size:15px; margin-bottom:4px;">
        Grassroots Footy Accessibility Map &mdash; Victoria
      </div>
      <div style="font-size:12px; color:#444; line-height:1.4;">
        252 AFL community venues mapped against SEIFA disadvantage and PT access.
        Click a venue or area for details. Layers toggle (top right).
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def main():
    venues, sa2, underserved = load_data()
    m = build_map(venues, sa2, underserved)
    out_path = DOCS / "index.html"
    m.save(str(out_path))
    print(f"Saved: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()