# Data folder

Put your CSV files here. The app looks for exactly these two names:

| File | Required? |
|------|-----------|
| `mumbai_air_quality.csv` | Yes |
| `mumbai_ridership.csv` | Optional (the dashboard works without it) |

No real data is included in this project. The tables below only show the **shape** a file should have;
the values are placeholders (`...`), not data.

---

## 1. Air-quality file

### Where to look
Availability and download options change over time, so check each site yourself:

- **CPCB** (Central Pollution Control Board, India) - the CAAQMS / air-quality data portal on `cpcb.nic.in`. It provides data for monitoring stations in Mumbai (station-wise downloads).
- **MPCB** (Maharashtra Pollution Control Board) - state-level air-quality information.
- **OpenAQ** (`openaq.org`) - open aggregator of air-quality measurements, which may include Mumbai stations.
- **Open Government Data Platform India** (`data.gov.in`) - search for air-quality datasets.
- **Kaggle** (`kaggle.com`) - search for Indian city air-quality datasets (these are re-uploads of official data; read the description and licence, and cite the original source if stated).

Always note: the organisation, dataset name, URL, download date and licence. Put them in `AIR_SOURCE` in `app.py` and in your report.

### Expected columns
One row = one measurement of one station for one date (or date-time). Pollutants are separate columns ("wide" format).

| Column (any accepted name) | Meaning | Needed? |
|----------------------------|---------|---------|
| `date` (also `datetime`, `timestamp`, `from_date`, ...) | Date or date-time of the reading | **Yes** |
| `station` (also `station_name`, `site`, `location`, ...) | Monitoring station name | No (if missing, one "Not specified" station is used) |
| `PM2.5` (also `pm25`, `pm2_5`) | Fine particles | At least one pollutant or AQI column is needed |
| `PM10` | Coarse particles | Optional |
| `NO2`, `SO2`, `CO`, `O3` | Other gases | Optional |
| `AQI` | Air Quality Index | Optional |

Case, spaces and symbols are ignored when matching names. If your column is called something else,
add it to `AIR_COLUMN_ALIASES` in `app.py`.

Format example (placeholders only):

```
Date,Station,PM2.5,PM10,NO2
...,...,...,...,...
```

### Preparing the file
- Save as CSV (UTF-8). Keep one header row.
- Leave unknown values **empty** (or write `NA`). Do not fill them with zeros or averages; the app counts and reports missing values.
- If you combine several station files, add a `station` column so that you can tell them apart.
- If your dates are like `31-01-2024`, keep `DAYFIRST = True` in `app.py`.
- If your data is in "long" format (one column `pollutant` and one column `value`), pivot it so that each pollutant has its own column.

---

## 2. Ridership file (optional until obtained)

### Where to look
Public ridership figures are not always published in a clean, downloadable form, so you may need to search and compare sources:

- **Mumbai Metro Rail Corporation / Mumbai Metro One (MMOPL) / MMRDA** - ridership statistics or annual reports.
- **BEST Undertaking** - published statistics on passenger traffic of its bus services.
- **Indian Railways / Mumbai suburban railway authorities** - passenger statistics, if available for your purpose.
- **Open Government Data Platform India** (`data.gov.in`) - search for Mumbai transport datasets.
- Research papers or reports that publish tables (copy the table into a CSV and cite the paper).

If no digital file exists, you may type values from an official published table into a CSV, but only the numbers actually printed there, and cite the table.

### Expected columns

| Column (any accepted name) | Meaning | Needed? |
|----------------------------|---------|---------|
| `date` (also `month`, `period`, `travel_date`, ...) | Day or month of the figure | **Yes** |
| `ridership` (also `passengers`, `daily_ridership`, `average_daily_ridership`, ...) | Number of passengers | **Yes** |
| `mode` (also `transport`, `transport_type`, `service`, `operator`) | e.g. the name of the system (Metro, BEST bus, ...) | No (if missing, "Not specified" is used) |

Format example (placeholders only):

```
date,mode,ridership
...,...,...
```

### Things to decide before comparing with air quality
- **Time step:** daily, monthly or yearly? The combined analysis uses calendar-month averages, so you need at least 6 months that overlap with the air-quality data (more is better; 12 or more is preferable).
- **Meaning of the number:** boardings per day, total per month, unique riders? Write it in `RIDERSHIP_UNIT`.
- **Geography:** does the ridership cover the whole city, one line, or one corridor? Pick air-quality stations that are reasonably comparable, and confirm this on the Combined Analysis page.
- **Same definition across modes** if you want to compare modes.

---

## 3. After adding files
Restart or refresh the app. Open **Data Quality & Download** to see exactly how many rows were removed or left missing, and which column names were matched.
