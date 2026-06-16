# Grassroots Footy Accessibility Map

**Are AFL community clubs across Victoria equally accessible across socioeconomic groups?**

A geospatial analysis mapping AFL Victoria community club locations against ABS SEIFA socioeconomic disadvantage data and Public Transport Victoria (PTV) accessibility, surfacing participation gaps and underserved postcodes for community football development.

🌐 **Live map:** _coming soon — deployed via GitHub Pages_

---

## Project Overview

This project asks a simple but important question: does access to grassroots Australian Rules Football reflect Victoria's social fabric, or are there geographic and socioeconomic gaps in where community clubs exist?

Using open data from the AFL, the Australian Bureau of Statistics, Public Transport Victoria, and OpenStreetMap, this analysis:

1. **Maps** every AFL Victoria community club across the state
2. **Joins** each club's location to ABS SEIFA disadvantage indices
3. **Scores** each club's public transport accessibility (distance to nearest stop)
4. **Identifies** underserved postcodes — areas with high participation potential but limited club access
5. **Deploys** findings as an interactive web map

---

## Why This Matters

Community football is a cornerstone of Australian community life. If access to grassroots clubs correlates with socioeconomic advantage, it raises important equity questions for the AFL's stated mission that *"everyone can love and connect with the game."*

This is an independent research analysis, not affiliated with the AFL.

---

## Tech Stack

- **Python** — analysis pipeline
- **GeoPandas, Shapely, OSMnx** — spatial data handling
- **scikit-learn** — clustering and statistical analysis
- **Folium / Leaflet.js** — interactive map
- **GitHub Pages** — static deployment

---

## Data Sources

| Dataset | Source | License |
|---------|--------|---------|
| AFL Victoria club locations | OpenStreetMap | ODbL |
| SEIFA 2021 (IRSD by SA2) | Australian Bureau of Statistics | CC BY 4.0 |
| Public Transport stops | data.vic.gov.au (PTV GTFS) | CC BY 4.0 |
| Victorian boundaries | ABS / data.vic.gov.au | CC BY 4.0 |

---

## Repository Structure

```
afl-accessibility-map/
├── src/                    # Pipeline modules
│   ├── data_collection.py  # Pull club locations from OSM
│   ├── seifa_join.py       # Spatial join with SEIFA
│   ├── accessibility.py    # PT accessibility scoring
│   └── visualisation.py    # Map generation
├── data/
│   ├── raw/                # Original downloads (gitignored)
│   └── processed/          # Cleaned datasets
├── notebooks/              # Exploratory analysis
├── docs/                   # GitHub Pages site
└── outputs/                # Final map, charts, reports
```

---

## Status

🚧 **In active development — June 2026**

- [x] Project scaffolding
- [ ] Data collection (AFL clubs)
- [ ] Geocoding pipeline
- [ ] SEIFA spatial joins
- [ ] PT accessibility scoring
- [ ] Statistical analysis
- [ ] Interactive map
- [ ] GitHub Pages deployment

---

## Author

**Siddhartha Ananthula** — Master of Data Science, RMIT University
Currently working on geospatial safety analysis at Regen Melbourne.

[LinkedIn](https://www.linkedin.com/in/siddhartha-ananthula-4778941a6)
