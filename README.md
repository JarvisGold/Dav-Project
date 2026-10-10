# Data-Driven Analysis of Urban Mobility and Environmental Sustainability in Mumbai

Semester 5 BTech Computer Engineering - Data Analytics and Visualization (DAV / MDM) mini project.

An interactive Streamlit dashboard that analyses Mumbai's air quality and, when data is available,
public-transport ridership, and explores how the two relate. The project supports
**UN Sustainable Development Goal 11: Sustainable Cities and Communities**
(in particular target 11.2 on sustainable transport systems and target 11.6 on the environmental impact of cities, including air quality).

> Important: this repository contains **no datasets and no results**. You must add real CSV files
> to the `data/` folder. Every number shown in the dashboard is computed from those files.

---

## 1. Project structure

```
mumbai_dav_project/
├── app.py                 # the Streamlit dashboard (all code, heavily commented)
├── requirements.txt       # Python packages
├── README.md              # this file
├── .streamlit/
│   └── config.toml        # light theme (white background, black text)
└── data/
    ├── README.md          # how to obtain and prepare the datasets
    ├── mumbai_air_quality.csv   # YOU add this (required)
    └── mumbai_ridership.csv     # YOU add this (optional until you find real data)
```

## 2. Setup and run

1. Install Python 3.9 or newer.
2. Open a terminal in the project folder and (recommended) create a virtual environment:

   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```

3. Install the packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Put your CSV files in the `data/` folder (see `data/README.md`).
5. Start the dashboard:

   ```bash
   streamlit run app.py
   ```

   Your browser opens at `http://localhost:8501`.

**Without the ridership file** the dashboard still works: all air-quality pages run, and the transport
and combined pages show a clear message that the second dataset is required.

## 3. Before you present: edit the configuration

The top of `app.py` has a section called *CONFIGURATION*. Update:

- `AIR_SOURCE` and `RIDERSHIP_SOURCE` - the real name of each dataset and the date you downloaded it
  (these are displayed on the Overview page).
- `RIDERSHIP_UNIT` - what one ridership value means in your file (e.g. passengers per day).
- `DAYFIRST` - `True` if dates look like 31/01/2024, `False` if they look like 01/31/2024.
- `AIR_COLUMN_ALIASES` / `RIDERSHIP_COLUMN_ALIASES` - add your column names if they are not recognised.
- `REFERENCE_LIMITS` - the optional reference lines for PM2.5 and PM10. They follow the Indian national
  24-hour standards as far as we know, but **verify them against the current CPCB notification** before quoting them.

## 4. Dashboard pages

| Page | What it shows |
|------|---------------|
| Overview | Title, description, KPI cards (average pollutant, number of records, stations, average ridership), date ranges and data sources |
| Air Quality Analysis | Trend line (daily/weekly/monthly), station comparison bar chart, summary table. Filters: date range, stations, pollutant. Only pollutants present in the file are offered |
| Public Transport Analysis | Ridership trend and comparison between transport modes (if the ridership file exists) |
| Combined Analysis | Monthly air quality vs ridership: separate trends, overlap check, scatter plot, Pearson/Spearman correlation, causation warning |
| Insights & Recommendations | Sentences generated automatically from the filtered data; follow-up suggestions; general SDG 11 directions (clearly labelled as general) |
| Optional: ML Prediction | Next-day prediction of the city-wide daily average with baselines, linear regression and random forest; MAE and RMSE |
| Data Quality & Download | Cleaning report, remaining missing values, column mapping, CSV downloads of cleaned data |

## 5. Academic write-up

### 5.1 Problem statement
Mumbai faces high traffic density and air-quality concerns. Planners need to understand how air pollution
changes over time and place, and whether public-transport usage patterns can be related to it, using open data
rather than assumptions. Data is often scattered, messy and incomplete, so a transparent analysis pipeline
and an easy-to-use dashboard are needed.

### 5.2 Objectives
1. Build a reproducible pipeline that loads, validates and cleans Mumbai air-quality data (and ridership data when available) while reporting every change.
2. Visualise air-quality trends over time and across monitoring stations with interactive filters.
3. Visualise public-transport ridership trends and compare transport modes when data allows.
4. Examine the relationship between ridership and air quality only where the data are compatible in time and place, and communicate the limits of that analysis.
5. Generate descriptive insights from the data and relate them to SDG 11.
6. (Optional) Build a simple, leakage-free prediction model with proper baselines.

### 5.3 Methodology
1. **Data collection** - download real datasets (see `data/README.md`) and record their sources.
2. **Column mapping** - column names are normalised (lower-case, symbols removed) and matched against lists of accepted names, so small naming differences do not break the app. A helpful error appears if a required column is missing.
3. **Cleaning** (counts of every step are shown in the dashboard):
   - dates that cannot be parsed are removed;
   - text entries in numeric columns and negative values are converted to *missing*;
   - rows with no valid measurement are removed;
   - exact duplicate rows are removed;
   - remaining missing values are **kept as missing** - nothing is imputed or invented.
4. **Exploratory analysis** - averages over time (daily/weekly/monthly) and per station, using Pandas and Plotly.
5. **Combined analysis** - both series are averaged per calendar month. A correlation is computed only if (a) the user confirms that the geographic coverage is comparable and (b) at least 6 months overlap. Pearson and Spearman coefficients are reported with the number of months and a causation warning.
6. **Insights** - computed directly from the filtered data (means, maxima, station and month differences, trend slope when at least 24 months exist, share of station-days above the reference value).
7. **Optional machine learning** - the daily city mean of the chosen pollutant is predicted from earlier days (lags and a rolling mean computed after shifting, plus day of week and month). The split is chronological (first 80% train, last 20% test). Two simple baselines (yesterday's value, training mean) are compared with linear regression and a random forest using MAE and RMSE.

### 5.4 Limitations
- Results depend completely on the datasets you provide; coverage, time step and quality differ between sources.
- Station measurements are point measurements and do not describe every part of Mumbai.
- Ridership data is usually city-wide or line-wide, while air quality is measured at stations, so the geographic match is imperfect. The dashboard asks you to confirm compatibility because it cannot check it automatically.
- Monthly averages hide short-term effects, and with few months the correlation is unreliable.
- **Correlation does not establish causation.** Seasons (monsoon), weather, holidays, economic activity, the COVID-19 period and many other factors affect both pollution and ridership. This project does not claim that public transport reduces or increases pollution.
- Trend slopes are descriptive (straight-line fits) and have no significance test.
- The optional model uses only past pollutant values and calendar features. It is evaluated on one chronological test period and is not an operational forecast.
- The general recommendations in the dashboard are commonly discussed policy directions; they are not findings of this dataset.

### 5.5 Alignment with UN SDG 11
- **Target 11.2** (access to safe, affordable, accessible and sustainable transport systems): ridership analysis gives a basis for discussing transport usage.
- **Target 11.6** (reduce the adverse environmental impact of cities, with attention to air quality): air-quality analysis shows where and when pollution is high in the data.

## 6. Troubleshooting

| Problem | What to do |
|---------|-----------|
| "Air-quality file not found" | Check that the file is exactly `data/mumbai_air_quality.csv` next to `app.py` |
| "Required column missing" | Rename the column in the CSV or add its name to `AIR_COLUMN_ALIASES` |
| Many rows removed for "invalid date" | Check the date format; try changing `DAYFIRST` |
| Station filter shows "Not specified" | Your file has no station column; the analysis still works for the whole file |
| Ridership pages say data is missing | Add `mumbai_ridership.csv` (see `data/README.md`) |
| ML page says not enough data | It needs at least 100 complete days after filtering |

## 7. Data and citation notes
Do not publish or submit numbers that you have not computed from a real file. Cite every dataset (organisation, dataset name, URL, download date) in your report and check each dataset's licence or terms of use.
