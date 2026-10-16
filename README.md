# 🚲 Bike Sharing Demand Prediction

An end-to-end machine learning pipeline that predicts hourly bike rental demand for the **Capital Bikeshare** program in Washington, D.C., using historical usage patterns, weather conditions, and seasonal/temporal features.

---

## 📌 Project Overview

This project builds a modular, leakage-safe ML pipeline to forecast the total number of bike rentals (`count`) in a given hour. It benchmarks an interpretable linear baseline against a tuned ensemble model (Random Forest), following best practices for preprocessing, cross-validation, and evaluation.

---

## 📂 Repository Structure

```
.
├── data/
│   └── raw_bike_data.csv        # Raw dataset (not tracked by git — see Setup)
├── notebooks/
│   └── *.ipynb                  # Interactive EDA and experimentation
├── src/
│   ├── data.py                  # Data loading, cleaning, and feature engineering
│   └── train.py                 # Pipelines, model training, tuning, and evaluation
├── requirements.txt              # Pinned dependency versions
├── .gitignore                    # Excludes venvs, caches, and raw data
└── README.md
```

- **`data/`** — Holds raw input data locally. Raw CSVs are git-ignored to keep the repository lightweight and avoid committing large/sensitive files.
- **`notebooks/`** — Space for exploratory data analysis (EDA) and ad-hoc experimentation, kept separate from production code.
- **`src/`** — Core, reusable, importable logic. No notebook-only code lives here.

---

## ⚙️ Environment Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd <your-repo-name>
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

`requirements.txt` pins exact versions of **Pandas**, **NumPy**, **Scikit-Learn**, and visualization libraries to guarantee reproducible results across machines.

### 4. `.gitignore` coverage
The `.gitignore` is configured to strictly exclude:
- Virtual environment directories (`venv/`, `.venv/`)
- Python caches (`__pycache__/`, `*.pyc`)
- Raw CSV data files (`data/*.csv`)
- Notebook checkpoints (`.ipynb_checkpoints/`)

---

## 📥 Dataset

This project uses the **[Bike Sharing Demand](https://www.kaggle.com/c/bike-sharing-demand/data)** dataset, originally published for a Kaggle competition. It contains two years of hourly rental logs from Capital Bikeshare, combined with weather and seasonal information.

### Setup instructions
1. Download `train.csv` from the Kaggle link above.
2. Rename it to `raw_bike_data.csv`.
3. Place it inside the `data/` folder:
   ```
   data/raw_bike_data.csv
   ```

### Feature Dictionary

| Feature | Data Type | Description |
|---|---|---|
| `datetime` | String/Date | Hourly timestamp, e.g. `2011-01-01 00:00:00` |
| `season` | Integer | 1 = Spring, 2 = Summer, 3 = Fall, 4 = Winter |
| `holiday` | Integer | 1 if the day is a holiday, 0 otherwise |
| `workingday` | Integer | 1 if neither a weekend nor a holiday, 0 otherwise |
| `weather` | Integer | 1 = Clear/Few clouds, 2 = Mist/Cloudy, 3 = Light Snow/Rain, 4 = Heavy Rain/Ice/Thunderstorm |
| `temp` | Float | Core temperature (°C) |
| `atemp` | Float | "Feels like" temperature (°C) |
| `humidity` | Float | Relative humidity (%) |
| `windspeed` | Float | Wind speed |
| `casual` | Integer | Non-registered user rentals *(dropped — leakage)* |
| `registered` | Integer | Registered user rentals *(dropped — leakage)* |
| `count` | Integer | **Target variable** — total rentals in that hour |

---

## 🧹 Data Engineering & Preprocessing (`src/data.py`)

| Step | Description |
|---|---|
| **Temporal feature extraction** | Parses the raw `datetime` string into explicit `hour`, `dayofweek`, and `month` features to help models capture commuter/seasonal cycles. |
| **Sensor anomaly guardrails** | Clips continuous weather variables (`temp`, `atemp`, `humidity`, `windspeed`) at a lower bound of `0` to automatically correct implausible negative sensor readings. |
| **Leakage prevention** | Strictly drops `casual` and `registered` before the train/test split, since these two columns sum directly to the target (`count`) and would leak the answer to the model. |
| **Automated EDA** | The `perform_eda()` function prints dataset shape, central tendency statistics, and key linear correlations (e.g., temperature vs. total count) to the terminal during data loading, giving an instant sanity check on every run. |

---

## 🤖 Machine Learning Pipelines & Modeling (`src/train.py`)

| Component | Description |
|---|---|
| **`ColumnTransformer`** | Applies `StandardScaler` exclusively to continuous features (`temp`, `atemp`, `humidity`, `windspeed`), leaving categorical and temporal features (`season`, `weather`, `hour`, `dayofweek`, `month`, etc.) untouched. |
| **`Pipeline` encapsulation** | Bundles preprocessing and modeling into a single Scikit-Learn `Pipeline`, guaranteeing that scaling statistics are fit **only** on training folds — preventing leakage during cross-validation. |
| **Linear baseline** | A fast `LinearRegression` pipeline establishes an interpretable performance floor. |
| **Random Forest** | A `RandomForestRegressor` pipeline captures non-linear interactions between weather, time, and commuter behavior. |
| **Hyperparameter tuning** | `RandomizedSearchCV` efficiently searches combinations of `n_estimators` and `max_depth` using 2-fold cross-validation. |

---

## 📊 Evaluation Strategy

Both the linear baseline and the tuned Random Forest are benchmarked against a **20% holdout test set** (never seen during training or tuning), using:

- **MAE** (Mean Absolute Error) — average magnitude of prediction error, in rental counts.
- **RMSE** (Root Mean Squared Error) — penalizes larger errors more heavily than MAE.
- **R²** (Coefficient of Determination) — proportion of variance in demand explained by the model.

---

## ▶️ Usage

```bash
# Run data loading + EDA
python src/data.py

# Train, tune, and evaluate models
python src/train.py
```

Expected console output includes dataset shape/statistics during the data phase, followed by MAE, RMSE, and R² for both the linear and Random Forest models on the holdout set.

---

## 🛠️ Tech Stack

- **Python 3.x**
- **Pandas** / **NumPy** — data manipulation
- **Scikit-Learn** — pipelines, preprocessing, modeling, cross-validation
- **Matplotlib / Seaborn** (or equivalent) — visualization

---

## 📈 Potential Next Steps

- Add cyclical encoding (sine/cosine) for `hour` and `month` instead of raw integers.
- Experiment with gradient boosting models (XGBoost, LightGBM).
- Expand hyperparameter search space and increase CV folds once compute allows.
- Add a `predict.py` script for scoring new/unseen data with the saved model artifact.

---

## 📄 License

Specify your license here (e.g., MIT).
