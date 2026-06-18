# Grassroots Footy Accessibility Map

> Are AFL community clubs across Victoria equally accessible across socioeconomic groups?

An independent geospatial analysis of 252 AFL community venues across Victoria, examining whether grassroots football is geographically accessible across socioeconomic groups and well-served by public transport.

🌐 **Live map:** [https://siddharthaananthula.github.io/afl-accessibility-map/](https://siddharthaananthula.github.io/afl-accessibility-map/)

---

## Key findings

**1. AFL venues are spread relatively evenly across SEIFA deciles when normalised by population.**
At the venue level, 40% of venues sit in advantaged areas (SEIFA deciles 8-10) vs 15% in disadvantaged areas (deciles 1-3). However, once you normalise by population at the SA2 level, the correlation between SEIFA decile and venues-per-10,000-residents is negligible (Pearson r = +0.08, n = 467 SA2s). The simple narrative of "more venues in richer suburbs" doesn't hold up under per-capita analysis.

**2. The real gap is geographic, not socioeconomic — 77% of populated Victorian SA2s have zero mapped AFL venues.**
Of 467 Victorian SA2s with substantial population (> 5,000 residents), 362 have no AFL venue at all. These gaps concentrate in **outer Melbourne growth corridors** — Tarneit (28k residents, 0 venues), Wollert (24k, 0), Mickleham (23k, 0), Cranbourne East (23k, 0), Bacchus Marsh (25k, 0) — spanning SEIFA deciles 2 through 9. Underservice tracks population growth, not disadvantage.

**3. Public transport access to AFL venues varies sharply by SEIFA decile.**
Composite accessibility scores (weighted across train, tram and bus stops) average 63/100 in decile 10 areas but 29-35/100 in deciles 3-7. Median venue is 1,933m from a train station and 263m from a bus stop. Inner Melbourne venues benefit from the tram network; outer venues rely on infrequent bus services.

---

## Methodology

- **AFL venues:** Extracted from OpenStreetMap (`sport=australian_football` tag) using a local OSM PBF dump from GeoFabrik. Processed in regional bounding-box chunks to manage memory. Final dataset: 252 named, unique venues across Victoria.
- **SEIFA decile:** ABS SEIFA 2021 Index of Relative Socio-economic Disadvantage (IRSD), joined to each venue via point-in-polygon spatial join against SA2 boundaries (ABS ASGS Edition 3).
- **Accessibility score:** PTV GTFS feed (train, tram, bus stops). For each venue, distance to nearest stop per mode is computed via R-tree nearest-neighbour, then scored on a linear-decay model and combined into a weighted composite (train 45%, tram 30%, bus 25%).
- **Underserved areas:** SA2s with > 5,000 residents and ≤ 1 AFL venues, ranked by population.

---

## Limitations

This is an independent analysis based on open data. Several honest caveats:

- **OpenStreetMap coverage is uneven.** Affluent, established suburbs may be more thoroughly mapped on OSM than disadvantaged or peri-urban areas. Some venues flagged here as "underserved" (e.g. Bentleigh-McKinnon, decile 9) likely reflect mapping gaps, not real infrastructure gaps. The outer-growth-corridor findings (Tarneit, Wollert, Cranbourne) are more reliable because those are recent-development areas.
- **Venue ≠ club.** Many venues host multiple clubs (junior, senior, women's). This analysis measures *physical infrastructure*, not club count.
- **SEIFA is residential, not catchment.** A venue's surrounding SEIFA reflects nearby residents, not who actually plays there.
- **Decile 1 has only 3 venues** — too small a sample for confident statements about the most-disadvantaged areas in isolation.

This project is not affiliated with the AFL, AFL Victoria, or any of the cited data providers.

---

## Tech stack

`Python` · `GeoPandas` · `Shapely` · `pyrosm` · `scikit-learn` · `Folium` / `Leaflet.js` · `Matplotlib` · `GitHub Pages`

---

## Data sources

All data is publicly available under open licences. Direct download links below were verified working in June 2026.

| Dataset | Direct download | Source page |
|---|---|---|
| AFL venue locations (Victoria OSM extract) | [`victoria-latest.osm.pbf`](https://download.geofabrik.de/australia-oceania/australia/victoria-latest.osm.pbf) (~220 MB) | [GeoFabrik Victoria](https://download.geofabrik.de/australia-oceania/australia/victoria.html) |
| SEIFA 2021 — IRSD by SA2 | [Latest release page](https://www.abs.gov.au/statistics/people/people-and-communities/socio-economic-indexes-areas-seifa-australia/latest-release) → "Statistical Area Level 2, Indexes" XLSX | [ABS SEIFA 2021](https://www.abs.gov.au/statistics/people/people-and-communities/socio-economic-indexes-areas-seifa-australia/latest-release) |
| SA2 boundary shapefile (ASGS Edition 3, GDA2020) | [`SA2_2021_AUST_SHP_GDA2020.zip`](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files/SA2_2021_AUST_SHP_GDA2020.zip) (~50 MB) | [ABS Digital Boundaries](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files) |
| Public transport stops (PTV GTFS Schedule) | [`gtfs.zip`](https://opendata.transport.vic.gov.au/dataset/3f4e292e-7f8a-4ffe-831f-1953be0fe448/resource/fb152201-859f-4882-9206-b768060b50ad/download/gtfs.zip) (~210 MB) | [data.vic.gov.au GTFS Schedule](https://discover.data.vic.gov.au/dataset/gtfs-schedule) |

**Licences:** All datasets are published under open Australian Government licences (Creative Commons Attribution 4.0 or equivalent). OSM data is © OpenStreetMap contributors under ODbL.

---

## Repository structure
afl-accessibility-map/
├── src/
│   ├── data_collection.py     # Day 1: extract AFL venues from OSM
│   ├── seifa_join.py          # Day 2: spatial join with SEIFA deciles
│   ├── transport_stops.py     # Day 3a: consolidate PTV GTFS stops
│   ├── accessibility.py       # Day 3b: per-venue accessibility scoring
│   ├── underserved.py         # Day 4: SA2-level density analysis
│   └── build_map.py           # Day 5: Folium interactive map
├── data/
│   ├── raw/                   # Source files (gitignored where heavy)
│   └── processed/             # Cleaned, joined CSVs
├── outputs/                   # Charts and PNG visualisations
└── docs/
└── index.html             # Live interactive map (deployed via Pages)

---

## Reproducing this analysis

```bash
# 1. Clone the repo
git clone https://github.com/siddharthaananthula/afl-accessibility-map.git
cd afl-accessibility-map

# 2. Create Python environment
conda create -n afl-map python=3.11 -y
conda activate afl-map
conda install -c conda-forge geopandas osmnx folium pyrosm -y
pip install -r requirements.txt

# 3. Download the four datasets (links in "Data sources" above) into data/raw/:
#    - victoria-australia-latest.osm.pbf
#    - seifa_2021_sa2.xlsx
#    - sa2_shapefile/  (extracted from the SA2 shapefile zip)
#    - gtfs_extracted/ (extracted from the PTV gtfs.zip)

# 4. Run pipeline in order (Day 1 → Day 5)
python src/data_collection.py    # Extract 252 AFL venues from OSM
python src/seifa_join.py         # Tag venues with SEIFA decile
python src/transport_stops.py    # Consolidate PTV stops
python src/accessibility.py      # Score per-venue accessibility
python src/underserved.py        # SA2-level density analysis
python src/build_map.py          # Build interactive map → docs/index.html
```


## After you save

```bash
git add README.md
git commit -m "Day 6: add direct data source download links and reproducibility steps"
git push
```

## Author

**Siddhartha Ananthula** — Master of Data Science, RMIT University.

[LinkedIn](https://www.linkedin.com/in/siddhartha-ananthula-4778941a6) · [GitHub](https://github.com/siddharthaananthula)