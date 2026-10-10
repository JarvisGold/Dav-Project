"""
app.py
======
Data-Driven Analysis of Urban Mobility and Environmental Sustainability in Mumbai
Semester 5 BTech Computer Engineering - Data Analytics and Visualization (DAV)

Run with:  streamlit run app.py

What this app does
------------------
1. Reads CSV files from the local "data/" folder.
2. Cleans them WITHOUT inventing values (missing values stay missing).
3. Shows air-quality analysis, public-transport analysis and (only when the
   data allow it) a combined analysis.
4. Generates descriptive insights directly from the loaded data.
5. Optionally trains a small, leakage-safe regression model.

Nothing in this file contains made-up results. Every number on screen is
calculated from your CSV files.
"""

import calendar
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Mumbai Urban Mobility & Sustainability",
    layout="wide",
)

# =============================================================================
# 1. CONFIGURATION  (edit this section to match your own files)
# =============================================================================

DATA_DIR = Path(__file__).parent / "data"
AIR_FILE = DATA_DIR / "mumbai_air_quality.csv"
RIDERSHIP_FILE = DATA_DIR / "mumbai_ridership.csv"

# Describe where your data came from. These texts are shown on the dashboard.
# Replace them with the real source name and download date (do not guess).
AIR_SOURCE = "Not specified - edit AIR_SOURCE in app.py (portal/dataset name + download date)"
RIDERSHIP_SOURCE = "Not specified - edit RIDERSHIP_SOURCE in app.py (organisation/dataset name + download date)"

# Unit shown for ridership values (check what your file actually contains).
RIDERSHIP_UNIT = "passengers (as given in the dataset)"

# Indian-format dates are usually day first (e.g. 05/01/2023 = 5 January 2023).
# Set to False if your file uses month first.
DAYFIRST = True

# Column mapping: left side = name used inside this program,
# right side = column names we accept in your CSV (case, spaces and symbols
# are ignored, so "PM2.5", "pm2_5" and "PM 2.5" are all treated the same).
# If your column has a different name, simply add it to the list.
AIR_COLUMN_ALIASES = {
    "date": ["date", "datetime", "date_time", "timestamp", "from_date", "observation_date", "day"],
    "station": ["station", "station_name", "site", "site_name", "location", "monitoring_station", "area"],
    "pm25": ["pm2_5", "pm25", "pm_2_5", "pm2_5_ug_m3"],
    "pm10": ["pm10", "pm_10"],
    "no2": ["no2", "nitrogen_dioxide"],
    "so2": ["so2", "sulphur_dioxide", "sulfur_dioxide"],
    "co": ["co", "carbon_monoxide"],
    "o3": ["o3", "ozone"],
    "aqi": ["aqi", "air_quality_index"],
}
AIR_REQUIRED = ["date"]  # plus at least one pollutant column (checked in code)

RIDERSHIP_COLUMN_ALIASES = {
    "date": ["date", "month", "year_month", "period", "travel_date", "datetime", "day"],
    "ridership": [
        "ridership", "passengers", "passenger_count", "total_passengers", "daily_ridership",
        "avg_daily_ridership", "average_daily_ridership", "passengers_carried", "footfall",
        "riders", "no_of_passengers", "number_of_passengers", "daily_passengers",
    ],
    "mode": ["mode", "transport", "transport_type", "mode_of_transport", "service", "operator", "system"],
}
RIDERSHIP_REQUIRED = ["date", "ridership"]

# Display names and TYPICAL units. Units are assumptions - check your dataset.
POLLUTANT_INFO = {
    "pm25": ("PM2.5", "µg/m³"),
    "pm10": ("PM10", "µg/m³"),
    "no2": ("NO2", "µg/m³"),
    "so2": ("SO2", "µg/m³"),
    "co": ("CO", "mg/m³"),
    "o3": ("O3", "µg/m³"),
    "aqi": ("AQI", ""),
}
POLLUTANT_ORDER = ["pm25", "pm10", "no2", "so2", "co", "o3", "aqi"]

# Optional reference lines (24-hour limits, µg/m³). These follow the Indian
# National Ambient Air Quality Standards as far as we know - PLEASE VERIFY
# them against the current CPCB notification before quoting them in a report.
# Delete an entry (or the whole dictionary contents) if you do not want it.
REFERENCE_LIMITS = {"pm25": 60, "pm10": 100}

# Minimum number of overlapping months needed before we compute a correlation.
MIN_OVERLAP_MONTHS = 6

ALL_MODES = "All modes combined"

PAGES = [
    "Overview",
    "Air Quality Analysis",
    "Public Transport Analysis",
    "Combined Analysis",
    "Insights & Recommendations",
    "Optional: ML Prediction",
    "Data Quality & Download",
]


# =============================================================================
# 2. SMALL HELPER FUNCTIONS
# =============================================================================

def pollutant_label(key):
    """Return a readable label such as 'PM2.5 (µg/m³)'."""
    name, unit = POLLUTANT_INFO[key]
    return f"{name} ({unit})" if unit else name


def normalise_name(name):
    """Lower-case a column name and replace symbols/spaces with '_' ("PM2.5" -> "pm2_5")."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def find_columns(normalised_columns, aliases):
    """Match the CSV's columns to our internal names. Returns {internal_name: csv_column}."""
    mapping = {}
    for internal, accepted in aliases.items():
        candidates = [normalise_name(a) for a in accepted]
        for candidate in candidates:  # earlier aliases win
            if candidate in normalised_columns:
                mapping[internal] = candidate
                break
    return mapping


def read_csv_safely(path):
    """Read a CSV, trying UTF-8 first and then Latin-1 for older Excel exports."""
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def parse_dates(series):
    """Convert text to datetimes; unreadable values become NaT (and are reported)."""
    try:
        return pd.to_datetime(series, errors="coerce", dayfirst=DAYFIRST, format="mixed")
    except (ValueError, TypeError):  # older pandas versions do not know format="mixed"
        return pd.to_datetime(series, errors="coerce", dayfirst=DAYFIRST)


def detect_frequency(dates):
    """Guess the time step of a dataset from the median gap between dates."""
    unique = pd.Series(pd.to_datetime(dates)).dropna().drop_duplicates().sort_values()
    if len(unique) < 2:
        return "unknown"
    days = unique.diff().dropna().median().total_seconds() / 86400
    if days <= 1:
        return "daily or finer"
    if days <= 8:
        return "weekly"
    if days <= 35:
        return "monthly"
    return "less frequent than monthly"


def date_span_text(series):
    """Return 'YYYY-MM-DD to YYYY-MM-DD' for a datetime series."""
    return f"{series.min():%Y-%m-%d} to {series.max():%Y-%m-%d}"


# =============================================================================
# 3. DATA LOADING AND CLEANING
# =============================================================================

def clean_table(raw, aliases, required, numeric_keys, category_key, category_default):
    """
    Clean a raw table step by step and COUNT everything that is changed.

    Steps: rename columns -> parse dates -> convert numbers -> tidy category
    column -> remove rows without any measurement -> remove duplicate rows.
    Missing measurements are never filled in.
    """
    df = raw.copy()
    df.columns = [normalise_name(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]  # keep the first of any duplicated names

    mapping = find_columns(list(df.columns), aliases)
    report = {"Rows in raw file": int(len(raw))}
    missing_required = [k for k in required if k not in mapping]
    if missing_required:
        return {"data": None, "mapping": mapping, "missing": missing_required,
                "report": report, "found": list(df.columns), "missing_table": None}

    # Keep only the columns we understand and give them our internal names.
    df = df[list(mapping.values())].rename(columns={v: k for k, v in mapping.items()})

    # --- invalid dates --------------------------------------------------------
    df["date"] = parse_dates(df["date"])
    invalid_dates = int(df["date"].isna().sum())
    df = df.dropna(subset=["date"])
    report["Rows removed: invalid or missing date"] = invalid_dates

    # --- numeric columns ------------------------------------------------------
    numeric_present = [k for k in numeric_keys if k in df.columns]
    for key in numeric_present:
        original = df[key]
        converted = pd.to_numeric(original, errors="coerce")
        # text such as "NA" or "-" that could not be converted
        report[f"'{key}': text entries treated as missing"] = int((original.notna() & converted.isna()).sum())
        # negative concentrations / ridership are not physically valid
        negatives = converted < 0
        report[f"'{key}': negative values treated as missing"] = int(negatives.sum())
        converted[negatives] = np.nan
        df[key] = converted

    # --- category column (station / transport mode) --------------------------
    if category_key in df.columns:
        text = df[category_key].astype("string").str.strip()
        blank = text.isna() | (text == "")
        report[f"'{category_key}': blank names labelled 'Unknown'"] = int(blank.sum())
        text = text.mask(blank, "Unknown")
        df[category_key] = text.astype(str)
    else:
        report[f"'{category_key}': column not found, labelled '{category_default}'"] = 0
        df[category_key] = category_default

    # --- rows with no measurement at all -------------------------------------
    no_measure = df[numeric_present].isna().all(axis=1)
    report["Rows removed: no valid measurement"] = int(no_measure.sum())
    df = df[~no_measure]

    # --- duplicates -----------------------------------------------------------
    duplicates = int(df.duplicated().sum())
    report["Rows removed: exact duplicates"] = duplicates
    df = df.drop_duplicates()

    df = df.sort_values("date").reset_index(drop=True)
    report["Rows after cleaning"] = int(len(df))

    # Missing values that REMAIN (we keep them as missing).
    missing_table = pd.DataFrame({
        "Column": numeric_present,
        "Missing values": [int(df[c].isna().sum()) for c in numeric_present],
        "Missing (%)": [round(100 * df[c].isna().mean(), 1) if len(df) else 0.0 for c in numeric_present],
    })
    return {"data": df, "mapping": mapping, "missing": [], "report": report,
            "found": list(raw.columns), "missing_table": missing_table}


@st.cache_data(show_spinner=False)
def load_dataset(path_str, kind, file_mtime):
    """Load + clean one dataset. 'file_mtime' makes the cache refresh when the file changes."""
    raw = read_csv_safely(path_str)
    if kind == "air":
        return clean_table(raw, AIR_COLUMN_ALIASES, AIR_REQUIRED,
                           POLLUTANT_ORDER, "station", "Not specified")
    return clean_table(raw, RIDERSHIP_COLUMN_ALIASES, RIDERSHIP_REQUIRED,
                       ["ridership"], "mode", "Not specified")


def report_table(report):
    """Turn the cleaning report dictionary into a small table."""
    return pd.DataFrame({"Check": list(report.keys()), "Count": list(report.values())})


# =============================================================================
# 4. TIME-SERIES HELPERS
# =============================================================================

def time_series(df, column, freq, by_station):
    """Average a pollutant over time (D = daily, W = weekly, MS = monthly). Gaps stay as gaps."""
    keys = [pd.Grouper(key="date", freq=freq)]
    if by_station:
        keys.append("station")
    return df.groupby(keys)[column].mean().reset_index()


def daily_city_mean(df, column):
    """Average all stations for each day (every station counts equally)."""
    return df.groupby(df["date"].dt.floor("D"))[column].mean().dropna()


def ridership_totals(rid, mode):
    """Ridership per date: one mode, or the sum of all modes."""
    data = rid if mode == ALL_MODES else rid[rid["mode"] == mode]
    return data.groupby(data["date"].dt.floor("D"))["ridership"].sum(min_count=1).dropna()


def to_monthly(series):
    """Average a date-indexed series by calendar month (index becomes monthly periods)."""
    if series.empty:
        return series
    return series.groupby(series.index.to_period("M")).mean().dropna()


def yearly_trend(monthly):
    """
    Straight-line slope per year through monthly means.
    Needs at least 24 months so that one season does not dominate the result.
    """
    if len(monthly) < 24:
        return None
    x = np.array([p.ordinal for p in monthly.index], dtype=float)  # month number
    slope_per_month = np.polyfit(x, monthly.values, 1)[0]
    return slope_per_month * 12


def style_fig(fig, x_title=None, y_title=None):
    """Plain white academic chart style."""
    fig.update_layout(
        template="simple_white", paper_bgcolor="white", plot_bgcolor="white",
        font=dict(color="black", size=13), margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
    )
    if x_title:
        fig.update_xaxes(title_text=x_title)
    if y_title:
        fig.update_yaxes(title_text=y_title)
    return fig


def need_ridership_message(rid_message):
    """Standard message shown when the ridership dataset is not available."""
    st.info(
        "**Transport analysis needs the second dataset.**\n\n"
        f"{rid_message}\n\n"
        "Place a file named `mumbai_ridership.csv` in the `data/` folder. It needs a date column "
        "and a ridership column (optionally a transport-mode column). "
        "See `data/README.md` for the expected format."
    )


# =============================================================================
# 5. LOAD DATA (runs on every interaction, but results are cached)
# =============================================================================

st.sidebar.title("Mumbai Mobility & Air Quality")
page = st.sidebar.radio("Navigate", PAGES)

# ---- air quality (required) -------------------------------------------------
if not AIR_FILE.exists():
    st.title("Mumbai Urban Mobility & Environmental Sustainability")
    st.error(
        f"Air-quality file not found: `{AIR_FILE}`\n\n"
        "Create a `data/` folder next to `app.py` and place `mumbai_air_quality.csv` inside it. "
        "See `data/README.md` for how to obtain and prepare the data."
    )
    st.stop()

air_result = load_dataset(str(AIR_FILE), "air", AIR_FILE.stat().st_mtime)
if air_result["data"] is None:
    st.title("Mumbai Urban Mobility & Environmental Sustainability")
    st.error(f"Required column missing in `{AIR_FILE.name}`: **{', '.join(air_result['missing'])}**")
    st.write("Columns found in your file:", ", ".join(air_result["found"]))
    st.write("Accepted names for each required column (case and symbols are ignored):")
    for key in air_result["missing"]:
        st.write(f"- `{key}`: {', '.join(AIR_COLUMN_ALIASES[key])}")
    st.info("Rename the column in your CSV, or add its name to `AIR_COLUMN_ALIASES` in app.py.")
    st.stop()

air = air_result["data"]
available_pollutants = [k for k in POLLUTANT_ORDER if k in air.columns]
if not available_pollutants:
    st.title("Mumbai Urban Mobility & Environmental Sustainability")
    st.error("No pollutant or AQI column was recognised in the air-quality file.")
    st.write("Columns found in your file:", ", ".join(air_result["found"]))
    st.write("Accepted pollutant column names:")
    for key in POLLUTANT_ORDER:
        st.write(f"- {POLLUTANT_INFO[key][0]}: {', '.join(AIR_COLUMN_ALIASES[key])}")
    st.stop()

# ---- ridership (optional) ---------------------------------------------------
rid = None
rid_result = None
if not RIDERSHIP_FILE.exists():
    rid_message = f"`{RIDERSHIP_FILE.name}` was not found in the data folder."
else:
    rid_result = load_dataset(str(RIDERSHIP_FILE), "ridership", RIDERSHIP_FILE.stat().st_mtime)
    if rid_result["data"] is None:
        rid_message = (f"`{RIDERSHIP_FILE.name}` was found but required column(s) are missing: "
                       f"{', '.join(rid_result['missing'])}. Columns found: {', '.join(rid_result['found'])}.")
    elif rid_result["data"].empty:
        rid_message = f"`{RIDERSHIP_FILE.name}` has no valid rows after cleaning."
    else:
        rid = rid_result["data"]
        rid_message = ""

# =============================================================================
# 6. SIDEBAR FILTERS (apply to the air-quality data)
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.subheader("Air-quality filters")

min_date = air["date"].min().date()
max_date = air["date"].max().date()
date_choice = st.sidebar.date_input("Date range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date)
if isinstance(date_choice, (tuple, list)):
    if len(date_choice) == 2:
        start_date, end_date = date_choice
    elif len(date_choice) == 1:
        start_date = end_date = date_choice[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = date_choice

all_stations = sorted(air["station"].unique())
chosen_stations = st.sidebar.multiselect("Monitoring stations", all_stations, default=all_stations)

default_index = available_pollutants.index("pm25") if "pm25" in available_pollutants else 0
pollutant = st.sidebar.selectbox("Pollutant", available_pollutants, index=default_index,
                                 format_func=pollutant_label)

mask = (
    (air["date"] >= pd.Timestamp(start_date))
    & (air["date"] < pd.Timestamp(end_date) + pd.Timedelta(days=1))
    & (air["station"].isin(chosen_stations))
)
air_f = air[mask]

if air_f.empty:
    st.warning("No air-quality records match the current filters. Widen the date range or pick more stations.")
    st.stop()
if air_f[pollutant].notna().sum() == 0:
    st.warning(f"The selected filters contain no valid {pollutant_label(pollutant)} values.")
    st.stop()


# =============================================================================
# 7. PAGES
# =============================================================================

def page_overview():
    st.title("Data-Driven Analysis of Urban Mobility and Environmental Sustainability in Mumbai")
    st.write(
        "This dashboard explores Mumbai's air quality and (when available) public-transport "
        "ridership. It supports **UN Sustainable Development Goal 11: Sustainable Cities and "
        "Communities**. All numbers are computed from the CSV files in the `data/` folder."
    )

    # KPI cards ---------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Average {POLLUTANT_INFO[pollutant][0]}", f"{air_f[pollutant].mean():.1f}",
              help=f"Mean of all valid readings in the current filters. Unit: {POLLUTANT_INFO[pollutant][1] or 'index'}")
    c2.metric("Air-quality records", f"{len(air_f):,}",
              help=f"{air_f[pollutant].notna().sum():,} of these have a valid {POLLUTANT_INFO[pollutant][0]} value")
    stations_text = f"{air_f['station'].nunique()}"
    if air_f["station"].nunique() == 1 and air_f["station"].iloc[0] == "Not specified":
        stations_text = "Not given"
    c3.metric("Monitoring stations", stations_text)
    if rid is not None:
        c4.metric("Average ridership per period", f"{ridership_totals(rid, ALL_MODES).mean():,.0f}",
                  help="Mean of the per-date totals across all transport modes")
    else:
        c4.metric("Average ridership", "N/A", help="Ridership dataset not loaded")

    # Dataset information -----------------------------------------------------
    st.subheader("Datasets, date ranges and sources")
    info = [{
        "Dataset": "Air quality",
        "File": AIR_FILE.name,
        "Date range (full file)": date_span_text(air["date"]),
        "Date range (current filters)": date_span_text(air_f["date"]),
        "Time step": detect_frequency(air["date"]),
        "Source": AIR_SOURCE,
    }]
    if rid is not None:
        info.append({
            "Dataset": "Public transport ridership",
            "File": RIDERSHIP_FILE.name,
            "Date range (full file)": date_span_text(rid["date"]),
            "Date range (current filters)": "not filtered here",
            "Time step": detect_frequency(rid["date"]),
            "Source": RIDERSHIP_SOURCE,
        })
    else:
        info.append({
            "Dataset": "Public transport ridership",
            "File": RIDERSHIP_FILE.name,
            "Date range (full file)": "not loaded",
            "Date range (current filters)": "-",
            "Time step": "-",
            "Source": "-",
        })
    st.dataframe(pd.DataFrame(info), hide_index=True)

    if rid is None:
        st.info(f"Ridership data is not available yet. {rid_message} "
                "The air-quality sections work normally; transport and combined analyses will "
                "unlock once `mumbai_ridership.csv` is added.")

    st.caption("Use the sidebar to navigate and to filter air-quality data by date, station and pollutant.")


def page_air():
    label = pollutant_label(pollutant)
    st.header("Air Quality Analysis")
    st.caption(f"Showing {label}. Change date range, stations and pollutant in the sidebar.")

    # --- trend over time ------------------------------------------------------
    st.subheader(f"{POLLUTANT_INFO[pollutant][0]} over time")
    col_a, col_b = st.columns(2)
    freq_name = col_a.radio("Time aggregation", ["Daily", "Weekly", "Monthly"], horizontal=True)
    by_station = col_b.checkbox("Show each station separately", value=False)
    freq = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[freq_name]

    ts = time_series(air_f, pollutant, freq, by_station)
    fig = px.line(ts, x="date", y=pollutant, color="station" if by_station else None,
                  markers=(freq != "D"))
    if freq == "D" and pollutant in REFERENCE_LIMITS:
        fig.add_hline(y=REFERENCE_LIMITS[pollutant], line_dash="dash", line_color="black",
                      annotation_text="24-h reference value set in app.py (verify with CPCB)",
                      annotation_position="top left")
    style_fig(fig, "Date", label)
    st.plotly_chart(fig)
    st.caption(f"{freq_name} average of valid readings"
               f"{' per station' if by_station else ' across the selected stations'}. "
               "Gaps in the line mean there were no valid readings in that period.")

    # --- stations -------------------------------------------------------------
    st.subheader("Comparison across monitoring stations")
    stn = (air_f.groupby("station")[pollutant].agg(mean="mean", readings="count")
           .reset_index().dropna(subset=["mean"]).sort_values("mean", ascending=False))
    fig2 = px.bar(stn, x="station", y="mean", text=stn["mean"].round(1),
                  hover_data={"readings": True})
    style_fig(fig2, "Station", f"Average {label}")
    st.plotly_chart(fig2)
    st.caption("Stations may cover different dates, so compare them carefully. "
               "Hover over a bar to see how many valid readings it is based on.")

    # --- summary of every available pollutant ---------------------------------
    st.subheader("Summary of all available pollutants (current filters)")
    rows = []
    for key in available_pollutants:
        values = air_f[key].dropna()
        rows.append({
            "Pollutant": pollutant_label(key),
            "Valid readings": int(len(values)),
            "Mean": round(values.mean(), 2) if len(values) else None,
            "Median": round(values.median(), 2) if len(values) else None,
            "Maximum": round(values.max(), 2) if len(values) else None,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    others = [POLLUTANT_INFO[k][0] for k in POLLUTANT_ORDER if k not in available_pollutants]
    if others:
        st.caption("Not available in this dataset (so not shown): " + ", ".join(others))


def page_transport():
    st.header("Public Transport Analysis")
    if rid is None:
        need_ridership_message(rid_message)
        return

    modes = sorted(rid["mode"].unique())
    c1, c2 = st.columns(2)
    chosen_modes = c1.multiselect("Transport modes", modes, default=modes)
    r_min, r_max = rid["date"].min().date(), rid["date"].max().date()
    r_dates = c2.date_input("Date range", value=(r_min, r_max), min_value=r_min,
                            max_value=r_max, key="rid_dates")
    if isinstance(r_dates, (tuple, list)) and len(r_dates) == 2:
        r_start, r_end = r_dates
    else:
        r_start, r_end = r_min, r_max

    data = rid[(rid["mode"].isin(chosen_modes))
               & (rid["date"] >= pd.Timestamp(r_start))
               & (rid["date"] < pd.Timestamp(r_end) + pd.Timedelta(days=1))]
    if data.empty:
        st.warning("No ridership records match these filters.")
        return

    freq_label = detect_frequency(rid["date"])
    k1, k2, k3 = st.columns(3)
    k1.metric("Records", f"{len(data):,}")
    k2.metric("Average per record", f"{data['ridership'].mean():,.0f}")
    k3.metric("Time step of data", freq_label)
    st.caption(f"Ridership unit: {RIDERSHIP_UNIT}. Source: {RIDERSHIP_SOURCE}")

    # --- trend ----------------------------------------------------------------
    st.subheader("Ridership trend")
    view = st.radio("View", ["As provided", "Monthly average"], horizontal=True)
    if view == "Monthly average":
        plot_df = (data.groupby([pd.Grouper(key="date", freq="MS"), "mode"])["ridership"]
                   .mean().reset_index())
    else:
        plot_df = data
    fig = px.line(plot_df, x="date", y="ridership", color="mode", markers=True)
    style_fig(fig, "Date", f"Ridership ({RIDERSHIP_UNIT})")
    st.plotly_chart(fig)

    # --- comparison -----------------------------------------------------------
    st.subheader("Comparison of transport types")
    if data["mode"].nunique() < 2:
        st.info("Only one transport mode is selected / available, so no comparison between modes is possible.")
    else:
        avg = data.groupby("mode")["ridership"].mean().reset_index().sort_values("ridership", ascending=False)
        fig2 = px.bar(avg, x="mode", y="ridership", text=avg["ridership"].round(0))
        style_fig(fig2, "Transport mode", f"Average ridership per record ({RIDERSHIP_UNIT})")
        st.plotly_chart(fig2)
        st.warning("Check before comparing: different modes may report different things "
                   "(daily vs monthly figures, boardings vs unique passengers). "
                   "Only compare modes whose definitions and time steps match.")


def page_combined():
    st.header("Combined Analysis: Ridership vs Air Quality")
    label = pollutant_label(pollutant)

    air_monthly = to_monthly(daily_city_mean(air_f, pollutant))

    if rid is None:
        need_ridership_message(rid_message)
        st.subheader("Air-quality trend (shown on its own)")
        fig = px.line(x=air_monthly.index.to_timestamp(), y=air_monthly.values, markers=True)
        style_fig(fig, "Month", f"Monthly mean {label}")
        st.plotly_chart(fig)
        return

    mode = st.selectbox("Transport mode for comparison", [ALL_MODES] + sorted(rid["mode"].unique()))
    if mode == ALL_MODES:
        st.caption("'All modes combined' adds the modes together for each date. "
                   "This is only meaningful if every mode reports for the same dates.")
    rid_monthly = to_monthly(ridership_totals(rid, mode))
    if rid_monthly.empty:
        st.warning("No ridership data for this selection.")
        return

    # --- compatibility checks -------------------------------------------------
    joined = pd.concat([air_monthly.rename("air"), rid_monthly.rename("ridership")],
                       axis=1, join="inner").dropna()
    st.subheader("1. Are the datasets compatible?")
    st.write(
        f"- Air quality covers **{air_monthly.index.min()} to {air_monthly.index.max()}** (monthly means).\n"
        f"- Ridership covers **{rid_monthly.index.min()} to {rid_monthly.index.max()}** (monthly means).\n"
        f"- Months present in **both**: **{len(joined)}** "
        f"(at least {MIN_OVERLAP_MONTHS} are needed to compute a correlation)."
    )
    geo_ok = st.checkbox(
        "I confirm that the selected air-quality stations and the ridership data refer to "
        "comparable parts of Mumbai (geographic coverage is compatible).",
        value=False,
    )
    st.caption("The program cannot check geography automatically. For example, ridership for one "
               "Metro line may not be comparable with a station in a different part of the city.")

    # --- separate trends (always shown) ---------------------------------------
    st.subheader("2. Trends shown separately")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=(f"Monthly mean {label}", f"Monthly ridership ({mode})"))
    fig.add_trace(go.Scatter(x=air_monthly.index.to_timestamp(), y=air_monthly.values,
                             mode="lines+markers", name=POLLUTANT_INFO[pollutant][0],
                             line=dict(color="#1f4e79")), row=1, col=1)
    fig.add_trace(go.Scatter(x=rid_monthly.index.to_timestamp(), y=rid_monthly.values,
                             mode="lines+markers", name="Ridership",
                             line=dict(color="#7f7f7f")), row=2, col=1)
    style_fig(fig)
    fig.update_layout(height=520, showlegend=False)
    fig.update_yaxes(title_text=label, row=1, col=1)
    fig.update_yaxes(title_text="Ridership", row=2, col=1)
    st.plotly_chart(fig)

    # --- correlation ----------------------------------------------------------
    st.subheader("3. Correlation (only if compatible)")
    if not geo_ok:
        st.info("Tick the confirmation box above to compute the correlation. "
                "Until then only the separate trends are shown.")
        return
    if len(joined) < MIN_OVERLAP_MONTHS:
        st.warning(f"Only {len(joined)} overlapping month(s). The datasets cannot be matched reliably, "
                   "so no correlation is calculated. Obtain data covering more common months.")
        return
    if joined["air"].nunique() < 2 or joined["ridership"].nunique() < 2:
        st.warning("One of the series is constant, so a correlation cannot be calculated.")
        return

    pearson_r = joined["air"].corr(joined["ridership"])
    spearman_rho = joined["air"].corr(joined["ridership"], method="spearman")
    p_value = None
    try:
        from scipy import stats  # scipy is installed together with scikit-learn
        p_value = stats.pearsonr(joined["ridership"], joined["air"])[1]
    except Exception:  # p-value is a bonus; the correlation itself does not need scipy
        pass

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Overlapping months", len(joined))
    m2.metric("Pearson r", f"{pearson_r:.2f}")
    m3.metric("Spearman rho", f"{spearman_rho:.2f}")
    m4.metric("p-value (Pearson)", f"{p_value:.3f}" if p_value is not None else "n/a")

    plot_df = joined.copy()
    plot_df["month"] = joined.index.astype(str)
    plot_df = plot_df.reset_index(drop=True)
    fig2 = px.scatter(plot_df, x="ridership", y="air", hover_data=["month"])
    slope, intercept = np.polyfit(joined["ridership"], joined["air"], 1)
    xs = np.array([joined["ridership"].min(), joined["ridership"].max()])
    fig2.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines",
                              name="Straight-line fit", line=dict(color="black", dash="dash")))
    style_fig(fig2, f"Monthly ridership ({mode})", f"Monthly mean {label}")
    st.plotly_chart(fig2)

    strength = abs(pearson_r)
    word = "weak" if strength < 0.3 else "moderate" if strength < 0.7 else "strong"
    direction = "positive" if pearson_r > 0 else "negative"
    st.write(f"**Reading the result:** the linear relationship between monthly ridership and monthly "
             f"mean {POLLUTANT_INFO[pollutant][0]} is **{word} and {direction}** (r = {pearson_r:.2f}, "
             f"n = {len(joined)} months).")
    if len(joined) < 12:
        st.warning("Fewer than 12 months: the result is very uncertain and may mostly reflect the time of year.")

    st.error(
        "**Correlation does not establish causation.** Both pollution and ridership change with "
        "the seasons (for example the monsoon), holidays, economic activity, weather and "
        "events such as the COVID-19 period. A relationship here does not show that public "
        "transport raises or lowers pollution, and no such claim is made by this project."
    )


def build_air_insights():
    """Create descriptive sentences using ONLY the filtered data."""
    label = pollutant_label(pollutant)
    short = POLLUTANT_INFO[pollutant][0]
    out = []

    values = air_f[pollutant].dropna()
    out.append(f"The current filters contain {len(values):,} valid {short} readings from "
               f"{air_f['station'].nunique()} station(s), between {date_span_text(air_f['date'])}.")
    peak = air_f.loc[values.idxmax()]
    out.append(f"{short} averages {values.mean():.1f} (median {values.median():.1f}). The highest single "
               f"reading is {values.max():.1f} ({label}), recorded on {peak['date']:%Y-%m-%d} "
               f"at station '{peak['station']}'.")

    stations = (air_f.groupby("station")[pollutant].agg(["mean", "count"]).dropna())
    if len(stations) >= 2:
        high, low = stations["mean"].idxmax(), stations["mean"].idxmin()
        out.append(f"Station '{high}' has the highest average {short} ({stations.loc[high, 'mean']:.1f}, "
                   f"{int(stations.loc[high, 'count'])} readings) and '{low}' the lowest "
                   f"({stations.loc[low, 'mean']:.1f}, {int(stations.loc[low, 'count'])} readings). "
                   "Differences may partly reflect different monitoring periods.")

    valid = air_f.dropna(subset=[pollutant])
    by_month = valid.groupby(valid["date"].dt.month)[pollutant].mean()
    if len(by_month) >= 3:
        out.append(f"Across calendar months, the highest average {short} is in "
                   f"{calendar.month_name[int(by_month.idxmax())]} ({by_month.max():.1f}) and the lowest in "
                   f"{calendar.month_name[int(by_month.idxmin())]} ({by_month.min():.1f}). "
                   "If the data span several years, these averages mix those years together.")

    monthly = to_monthly(daily_city_mean(air_f, pollutant))
    trend = yearly_trend(monthly)
    if trend is not None:
        direction = "upward" if trend > 0 else "downward"
        out.append(f"A straight line through the monthly means has a slope of {trend:+.2f} {label} per year "
                   f"({direction}). This is descriptive only, not a statistical test.")
    else:
        out.append("Fewer than 24 months of data are available, so no long-term trend is reported "
                   "(a shorter period would mostly show seasonal changes).")

    if pollutant in REFERENCE_LIMITS:
        station_days = valid.groupby(["station", valid["date"].dt.floor("D")])[pollutant].mean().dropna()
        share = (station_days > REFERENCE_LIMITS[pollutant]).mean() * 100
        out.append(f"{share:.1f}% of the {len(station_days):,} station-days exceed the reference value of "
                   f"{REFERENCE_LIMITS[pollutant]} set in app.py for {short}.")
    return out


def build_transport_insights():
    out = []
    if rid is None:
        return ["Ridership data is not loaded, so no transport insights can be generated."]
    totals = ridership_totals(rid, ALL_MODES)
    out.append(f"The ridership file has {len(rid):,} cleaned records covering {date_span_text(rid['date'])} "
               f"(time step: {detect_frequency(rid['date'])}).")
    if rid["mode"].nunique() >= 2:
        avg = rid.groupby("mode")["ridership"].mean().sort_values(ascending=False)
        out.append(f"Highest average ridership per record: '{avg.index[0]}' ({avg.iloc[0]:,.0f}); "
                   f"lowest: '{avg.index[-1]}' ({avg.iloc[-1]:,.0f}). "
                   "Check that the modes are measured in the same way before comparing them.")
    trend = yearly_trend(to_monthly(totals))
    if trend is not None:
        out.append(f"A straight line through monthly ridership has a slope of {trend:+,.0f} per year "
                   "(descriptive only).")
    else:
        out.append("Fewer than 24 months of ridership data are available, so no long-term trend is reported.")
    return out


def page_insights():
    st.header("Insights and Recommendations")
    st.subheader("Insights generated from the data")
    st.caption("Sentences are produced automatically from the currently filtered data. Nothing is typed in by hand.")
    st.markdown("**Air quality**")
    for sentence in build_air_insights():
        st.write(f"- {sentence}")
    st.markdown("**Public transport**")
    for sentence in build_transport_insights():
        st.write(f"- {sentence}")
    st.write("- For the relationship between the two, see the *Combined Analysis* page "
             "(only available when the datasets overlap in time and place).")

    # Recommendations driven by what the data actually shows --------------------
    st.subheader("Recommendations")
    st.markdown("**Suggested follow-up based on this dataset**")
    short = POLLUTANT_INFO[pollutant][0]
    stations = air_f.groupby("station")[pollutant].mean().dropna()
    if len(stations) >= 2:
        st.write(f"- Investigate local sources (traffic corridors, construction, industry) around "
                 f"'{stations.idxmax()}', which has the highest average {short} in the current selection.")
    valid = air_f.dropna(subset=[pollutant])
    by_month = valid.groupby(valid["date"].dt.month)[pollutant].mean()
    if len(by_month) >= 3:
        st.write(f"- Plan targeted measures and public advisories for "
                 f"{calendar.month_name[int(by_month.idxmax())]}, the month with the highest average {short} in this data.")
    if rid is None:
        st.write("- Obtain a public-transport ridership dataset to test whether mobility patterns "
                 "move together with air quality.")
    st.write("- Improve data quality: more stations with continuous records make comparisons more reliable.")

    st.markdown("**General directions for sustainable urban mobility (SDG 11)**")
    st.caption("These are widely discussed policy directions, not results of this analysis. This project does not "
               "show that any of them reduces pollution in Mumbai.")
    st.write(
        "- Strengthen public transport capacity and reliability so that it is a practical alternative to private vehicles (SDG target 11.2).\n"
        "- Improve first- and last-mile links (safe footpaths, cycling lanes, feeder buses) to stations.\n"
        "- Prioritise cleaner bus and taxi fleets and reduce emissions from the most polluting vehicles.\n"
        "- Expand and publish continuous air-quality monitoring so impacts can be evaluated (SDG target 11.6).\n"
        "- Publish open, consistent ridership data so that future studies can test links between mobility and air quality."
    )


def page_ml():
    st.header("Optional: Air-Quality Prediction (Machine Learning)")
    st.write(
        "This optional extension predicts the **city-wide daily average** of the selected pollutant "
        "from its own past values. It is a simple teaching example, not an operational forecast."
    )
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import LinearRegression
    except ImportError:
        st.error("scikit-learn is not installed. Run `pip install scikit-learn` to enable this page.")
        return

    label = pollutant_label(pollutant)
    daily = daily_city_mean(air_f, pollutant).asfreq("D")  # adds empty days as NaN (NOT filled)

    # Features use ONLY information from earlier days, so there is no data leakage.
    data = pd.DataFrame({"target": daily})
    data["lag_1"] = daily.shift(1)
    data["lag_2"] = daily.shift(2)
    data["lag_3"] = daily.shift(3)
    data["lag_7"] = daily.shift(7)
    data["rolling_mean_7"] = daily.shift(1).rolling(7, min_periods=7).mean()  # shift first -> excludes today
    data["day_of_week"] = data.index.dayofweek
    data["month"] = data.index.month
    data = data.dropna()  # rows with any missing input are dropped, never invented

    MIN_ROWS = 100
    if len(data) < MIN_ROWS:
        st.info(f"Not enough usable data: {len(data)} complete days available, at least {MIN_ROWS} are needed. "
                "Widen the date range or use a dataset with a longer, more complete daily record.")
        return

    split = int(len(data) * 0.8)  # chronological split: first 80% train, last 20% test
    train, test = data.iloc[:split], data.iloc[split:]
    features = [c for c in data.columns if c != "target"]
    st.write(f"- Usable days: **{len(data)}**\n"
             f"- Training period: **{train.index.min():%Y-%m-%d} to {train.index.max():%Y-%m-%d}** ({len(train)} days)\n"
             f"- Test period: **{test.index.min():%Y-%m-%d} to {test.index.max():%Y-%m-%d}** ({len(test)} days)\n"
             f"- Target: {label}, next day value predicted from: {', '.join(features)}")

    if not st.button("Train and evaluate models"):
        return

    def metrics(actual, predicted):
        error = np.asarray(actual) - np.asarray(predicted)
        return float(np.mean(np.abs(error))), float(np.sqrt(np.mean(error ** 2)))

    with st.spinner("Training..."):
        linear = LinearRegression().fit(train[features], train["target"])
        forest = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42)
        forest.fit(train[features], train["target"])

    predictions = {
        "Baseline: yesterday's value": test["lag_1"].values,
        "Baseline: training-period mean": np.full(len(test), train["target"].mean()),
        "Linear regression": linear.predict(test[features]),
        "Random forest": forest.predict(test[features]),
    }
    rows = []
    for name, pred in predictions.items():
        mae, rmse = metrics(test["target"], pred)
        rows.append({"Model": name, "MAE": round(mae, 2), "RMSE": round(rmse, 2)})
    results = pd.DataFrame(rows)
    st.subheader("Results on the unseen test period")
    st.dataframe(results, hide_index=True)
    st.caption(f"MAE = mean absolute error, RMSE = root mean squared error; both in {label}. Lower is better.")

    base_rmse = results.loc[results["Model"] == "Baseline: yesterday's value", "RMSE"].iloc[0]
    best = results.sort_values("RMSE").iloc[0]
    if best["Model"].startswith("Baseline"):
        st.write("**Reading the result:** no machine-learning model beat the simple baselines on this test period.")
    else:
        st.write(f"**Reading the result:** '{best['Model']}' has the lowest RMSE ({best['RMSE']}) compared with "
                 f"{base_rmse} for the 'yesterday's value' baseline. One test period is not proof that it "
                 "would keep winning on new data.")

    plot_df = pd.DataFrame({
        "Actual": test["target"],
        "Random forest": predictions["Random forest"],
        "Baseline: yesterday's value": predictions["Baseline: yesterday's value"],
    }, index=test.index)
    plot_df.insert(0, "date", test.index)
    plot_df = plot_df.reset_index(drop=True)
    long_df = plot_df.melt(id_vars="date", var_name="Series", value_name="value")
    fig = px.line(long_df, x="date", y="value", color="Series")
    style_fig(fig, "Date (test period)", label)
    st.plotly_chart(fig)

    importance = pd.DataFrame({"Feature": features, "Importance": forest.feature_importances_})
    fig2 = px.bar(importance.sort_values("Importance"), x="Importance", y="Feature", orientation="h")
    style_fig(fig2, "Random-forest importance", "")
    st.plotly_chart(fig2)

    st.subheader("How leakage was prevented")
    st.write(
        "- The split is chronological (train on the past, test on the future); rows were never shuffled.\n"
        "- Every input comes from earlier days only (lags, and a rolling mean computed after shifting by one day).\n"
        "- Days with any missing input were dropped; no values were filled in.\n"
        "- Model settings were fixed in advance and were not tuned on the test period."
    )
    st.subheader("Limitations")
    st.write(
        "- Only past pollutant values and calendar features are used; weather, traffic and ridership are not.\n"
        "- The city-wide daily mean mixes stations, and the set of reporting stations may change over time.\n"
        "- If training covers less than a full year, the model has not seen every season.\n"
        "- A single chronological split gives one performance estimate; it is not a full validation.\n"
        "- The model finds statistical patterns only and says nothing about causes."
    )


def page_quality():
    st.header("Data Quality and Download")
    st.write("Every cleaning step is counted. Missing measurements are kept as missing and are never filled in.")

    st.subheader(f"Air quality - {AIR_FILE.name}")
    st.dataframe(report_table(air_result["report"]), hide_index=True)
    st.write("Column mapping used (internal name <- column in your file):")
    st.write(", ".join(f"`{k}` <- `{v}`" for k, v in air_result["mapping"].items()))
    st.write("Missing values that remain after cleaning:")
    st.dataframe(air_result["missing_table"], hide_index=True)
    st.write("Preview of cleaned data:")
    st.dataframe(air.head(20))
    d1, d2 = st.columns(2)
    d1.download_button("Download cleaned air-quality data (CSV)",
                       air.to_csv(index=False).encode("utf-8"), "cleaned_air_quality.csv", "text/csv")
    d2.download_button("Download currently filtered air-quality data (CSV)",
                       air_f.to_csv(index=False).encode("utf-8"), "filtered_air_quality.csv", "text/csv")

    st.subheader(f"Ridership - {RIDERSHIP_FILE.name}")
    if rid_result is None:
        need_ridership_message(rid_message)
    elif rid is None:
        st.warning(rid_message)
        st.write("Columns found in your file:", ", ".join(rid_result["found"]))
    else:
        st.dataframe(report_table(rid_result["report"]), hide_index=True)
        st.write("Column mapping used (internal name <- column in your file):")
        st.write(", ".join(f"`{k}` <- `{v}`" for k, v in rid_result["mapping"].items()))
        st.write("Missing values that remain after cleaning:")
        st.dataframe(rid_result["missing_table"], hide_index=True)
        st.write("Preview of cleaned data:")
        st.dataframe(rid.head(20))
        st.download_button("Download cleaned ridership data (CSV)",
                           rid.to_csv(index=False).encode("utf-8"), "cleaned_ridership.csv", "text/csv")


# =============================================================================
# 8. SHOW THE SELECTED PAGE
# =============================================================================

if page == "Overview":
    page_overview()
elif page == "Air Quality Analysis":
    page_air()
elif page == "Public Transport Analysis":
    page_transport()
elif page == "Combined Analysis":
    page_combined()
elif page == "Insights & Recommendations":
    page_insights()
elif page == "Optional: ML Prediction":
    page_ml()
else:
    page_quality()
