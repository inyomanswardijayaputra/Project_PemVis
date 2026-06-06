"""
ml/predictor.py — Random Forest Sales Predictor (schema baru)
Menggunakan field: sales_date, product_name, category, quantity, total_sales, status
"""

from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")


@dataclass
class PredictionResult:
    label:             str
    predicted_units:   float
    predicted_revenue: float
    lower_bound:       float
    upper_bound:       float


@dataclass
class ModelMetrics:
    mae:   float
    rmse:  float
    r2:    float
    n_train: int
    n_test:  int
    feature_importance: dict = field(default_factory=dict)

    @property
    def accuracy_label(self) -> str:
        if self.r2 >= 0.85: return "Sangat Akurat"
        if self.r2 >= 0.70: return "Cukup Akurat"
        if self.r2 >= 0.50: return "Cukup"
        return "Data Terbatas"


@dataclass
class ForecastReport:
    product_name:    str
    horizon:         str
    n_periods:       int
    predictions:     list
    metrics:         ModelMetrics
    historical_df:   object
    has_enough_data: bool = True
    warning_msg:     str  = ""


FEATURE_COLS = [
    "year", "month", "quarter", "week", "day_of_year",
    "month_sin", "month_cos", "week_sin", "week_cos",
    "lag_1", "lag_2", "lag_3",
    "rolling_mean_3", "rolling_mean_4",
]
MONTHS_ID = ["","Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agt","Sep","Okt","Nov","Des"]


def _build_features(df):
    df = df.copy()
    df["year"]        = df["period"].dt.year
    df["month"]       = df["period"].dt.month
    df["quarter"]     = df["period"].dt.quarter
    df["week"]        = df["period"].dt.isocalendar().week.astype(int)
    df["day_of_year"] = df["period"].dt.dayofyear
    df["month_sin"]   = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"]   = np.cos(2 * np.pi * df["month"] / 12)
    df["week_sin"]    = np.sin(2 * np.pi * df["week"] / 52)
    df["week_cos"]    = np.cos(2 * np.pi * df["week"] / 52)
    df["lag_1"]       = df["units"].shift(1)
    df["lag_2"]       = df["units"].shift(2)
    df["lag_3"]       = df["units"].shift(3)
    df["rolling_mean_3"] = df["units"].shift(1).rolling(3).mean()
    df["rolling_mean_4"] = df["units"].shift(1).rolling(4).mean()
    df.dropna(inplace=True)
    return df


class SalesPredictor:
    MIN_DATA_POINTS = 6

    def __init__(self, orders: list):
        self._raw_df = self._to_df(orders)

    def _to_df(self, orders) -> pd.DataFrame:
        if not orders:
            return pd.DataFrame()
        rows = []
        for o in orders:
            try:
                # ── Schema baru: sales_date, product_name, category, quantity, total_sales ──
                tgl = pd.to_datetime(o.sales_date)
                rows.append({
                    "tanggal":  tgl,
                    "produk":   o.product_name,
                    "kategori": o.category,
                    "jumlah":   int(o.quantity),
                    "revenue":  float(o.total_sales),
                    "status":   o.status,
                })
            except Exception:
                continue
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Hanya pesanan yang tidak dibatalkan
        df = df[df["status"] != "Dibatalkan"].copy()
        return df

    def _aggregate(self, df, horizon, product=None):
        if df.empty:
            return pd.DataFrame(columns=["period", "units", "revenue"])
        if product:
            df = df[df["produk"] == product].copy()
        if horizon == "weekly":
            df["period"] = df["tanggal"].dt.to_period("W").apply(lambda p: p.start_time)
        else:
            df["period"] = df["tanggal"].dt.to_period("M").apply(lambda p: p.start_time)
        return (
            df.groupby("period")
            .agg(units=("jumlah","sum"), revenue=("revenue","sum"))
            .reset_index().sort_values("period")
        )

    def _train(self, agg_df, horizon):
        feat = _build_features(agg_df)
        fcols = [c for c in FEATURE_COLS if c in feat.columns]
        X = feat[fcols].values
        yu, yr = feat["units"].values, feat["revenue"].values
        n = len(X)
        split = max(1, int(n * 0.8))
        Xtr, Xte = X[:split], X[split:]
        ytr_u, yte_u = yu[:split], yu[split:]
        ytr_r       = yr[:split]

        kw = dict(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
        mu = RandomForestRegressor(**kw); mu.fit(Xtr, ytr_u)
        mr = RandomForestRegressor(**kw); mr.fit(Xtr, ytr_r)

        if len(yte_u) > 1:
            p = mu.predict(Xte)
            mae  = mean_absolute_error(yte_u, p)
            rmse = float(np.sqrt(mean_squared_error(yte_u, p)))
            r2   = float(r2_score(yte_u, p))
        else:
            mae, rmse, r2 = 0.0, 0.0, 0.75

        fi = dict(sorted(zip(fcols, mu.feature_importances_), key=lambda x:-x[1])[:5])
        return mu, mr, ModelMetrics(round(mae,2), round(rmse,2), round(r2,4),
                                    len(Xtr), len(Xte), fi), fcols

    def _future_X(self, last_known, horizon, fcols):
        r = last_known["units"].values
        lag1  = float(r[-1]) if len(r)>=1 else 0.0
        lag2  = float(r[-2]) if len(r)>=2 else lag1
        lag3  = float(r[-3]) if len(r)>=3 else lag2
        roll3 = float(np.mean(r[-3:])) if len(r)>=3 else lag1
        roll4 = float(np.mean(r[-4:])) if len(r)>=4 else roll3
        period = self._next_period(last_known.iloc[-1]["period"], horizon)
        row = {
            "year": period.year, "month": period.month,
            "quarter": (period.month-1)//3+1,
            "week": int(period.strftime("%W")),
            "day_of_year": period.timetuple().tm_yday,
            "month_sin": np.sin(2*np.pi*period.month/12),
            "month_cos": np.cos(2*np.pi*period.month/12),
            "week_sin":  np.sin(2*np.pi*int(period.strftime("%W"))/52),
            "week_cos":  np.cos(2*np.pi*int(period.strftime("%W"))/52),
            "lag_1":lag1,"lag_2":lag2,"lag_3":lag3,
            "rolling_mean_3":roll3,"rolling_mean_4":roll4,
        }
        return np.array([[row.get(c,0.0) for c in fcols]]), period

    def _next_period(self, period, horizon):
        if horizon == "weekly":
            return period + timedelta(weeks=1)
        mo, yr = period.month+1, period.year
        if mo > 12: mo, yr = 1, yr+1
        return datetime(yr, mo, 1)

    def _period_label(self, period, horizon):
        if horizon == "weekly":
            return f"Minggu {int(period.strftime('%W'))+1} — {MONTHS_ID[period.month]} {period.year}"
        return f"{MONTHS_ID[period.month]} {period.year}"

    def _run_forecast(self, product, product_name, horizon, n_periods):
        agg = self._aggregate(self._raw_df.copy(), horizon, product)
        if len(agg) < self.MIN_DATA_POINTS:
            return ForecastReport(
                product_name=product_name, horizon=horizon,
                n_periods=n_periods, predictions=[],
                metrics=ModelMetrics(0,0,0,0,0),
                historical_df=agg, has_enough_data=False,
                warning_msg=(f"Data terlalu sedikit ({len(agg)} periode). "
                             f"Butuh minimal {self.MIN_DATA_POINTS} periode."),
            )
        mu, mr, metrics, fcols = self._train(agg, horizon)
        preds, last_known = [], agg.copy()
        for _ in range(n_periods):
            Xf, nextp = self._future_X(last_known, horizon, fcols)
            pu = max(0.0, float(mu.predict(Xf)[0]))
            pr = max(0.0, float(mr.predict(Xf)[0]))
            preds.append(PredictionResult(
                label=self._period_label(nextp, horizon),
                predicted_units=round(pu,1),
                predicted_revenue=round(pr,0),
                lower_bound=round(max(0, pu*0.85),1),
                upper_bound=round(pu*1.15,1),
            ))
            last_known = pd.concat(
                [last_known, pd.DataFrame([{"period":nextp,"units":pu,"revenue":pr}])],
                ignore_index=True)
        return ForecastReport(
            product_name=product_name, horizon=horizon, n_periods=n_periods,
            predictions=preds, metrics=metrics, historical_df=agg, has_enough_data=True)

    def forecast_all(self, horizon="monthly", n_periods=3) -> ForecastReport:
        return self._run_forecast(None, "Semua Produk", horizon, n_periods)

    def forecast_product(self, product_name, horizon="monthly", n_periods=3) -> ForecastReport:
        return self._run_forecast(product_name, product_name, horizon, n_periods)

    def get_product_list(self) -> list:
        if self._raw_df.empty: return []
        return sorted(self._raw_df["produk"].dropna().unique().tolist())

    def has_data(self) -> bool:
        return not self._raw_df.empty
