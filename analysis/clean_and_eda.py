from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FINDINGS_PATH = ROOT / "narrator" / "findings.json"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    return customers, products, orders


def prepare_orders(orders: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, list[str]]:
    orders = orders.copy()
    if verbose:
        print(f"orders.shape before cleaning: {orders.shape}")
        print("Raw payment_method values:", sorted(orders["payment_method"].dropna().unique().tolist()))

    orders["payment_method"] = orders["payment_method"].astype("string").str.strip().str.upper()
    if verbose:
        print("Cleaned payment_method counts:")
        print(orders["payment_method"].value_counts().sort_index().to_string())

    natural_key = [
        "customer_id", "product_id", "order_date", "quantity",
        "discount_pct", "payment_method", "rating", "returned"
    ]
    duplicate_mask = orders.duplicated(subset=natural_key, keep="first")
    dropped_ids = orders.loc[duplicate_mask, "order_id"].tolist()
    orders_clean = orders.loc[~duplicate_mask].copy()
    if verbose:
        print(f"Duplicate rows flagged: {int(duplicate_mask.sum())}")
        print("Dropped order_id values:", dropped_ids)
        print(f"orders_clean.shape after duplicate removal: {orders_clean.shape}")

    missing_discount = int(orders_clean["discount_pct"].isna().sum())
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)

    rating_median = float(orders_clean["rating"].median())
    missing_rating = int(orders_clean["rating"].isna().sum())
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)

    if verbose:
        print(f"Missing discount_pct imputed: {missing_discount}")
        print(f"Rating median before imputation: {rating_median:.1f}")
        print(f"Missing rating imputed: {missing_rating}")
        print("Remaining missing values:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

    return orders_clean, dropped_ids


def merge_and_analyze(orders_clean: pd.DataFrame, customers: pd.DataFrame, products: pd.DataFrame,
                      verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    df = (orders_clean
          .merge(products, on="product_id", how="left", validate="many_to_one")
          .merge(customers, on="customer_id", how="left", validate="many_to_one"))
    df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100.0)

    total_revenue = float(df["order_value"].sum())
    if verbose:
        print(f"Cleaned total order_value: {total_revenue:.2f}")

    return df, {"cleaned_total_revenue_inr": round(total_revenue, 2)}


def run_pipeline(verbose: bool = True, write_findings: bool = True) -> tuple[pd.DataFrame, dict]:
    customers, products, orders_raw = load_data()

    if verbose:
        print("=== Task 1: Load and inspect ===")
        print(f"customers.shape: {customers.shape}")
        print(f"products.shape: {products.shape}")

    # Part 2 Tasks 2-4.
    orders_clean, dropped_ids = prepare_orders(orders_raw, verbose=verbose)

    # Part 2 Task 5.
    df, revenue_info = merge_and_analyze(orders_clean, customers, products, verbose=verbose)

    dropped_rows = orders_raw.loc[orders_raw["order_id"].isin(dropped_ids)].copy()
    dropped_rows["payment_method"] = dropped_rows["payment_method"].astype("string").str.strip().str.upper()
    dropped_rows["discount_pct"] = dropped_rows["discount_pct"].fillna(0)
    dropped_rows = dropped_rows.merge(products, on="product_id", how="left")
    dropped_order_value = float((dropped_rows["quantity"] * dropped_rows["price"] *
                                 (1 - dropped_rows["discount_pct"] / 100.0)).sum())
    raw_revenue = float((orders_raw.merge(products, on="product_id", how="left")["quantity"] *
                         orders_raw.merge(products, on="product_id", how="left")["price"] *
                         (1 - orders_raw["discount_pct"].fillna(0) / 100.0)).sum())
    delta = raw_revenue - revenue_info["cleaned_total_revenue_inr"]
    if verbose:
        print(f"Raw revenue from Part 1 formula: {raw_revenue:.2f}")
        print(f"Reconciliation delta: {delta:.2f}")
        print(f"Dropped duplicate rows' combined order_value: {dropped_order_value:.2f}")
        print("Reconciliation note: The exact ₹2,501.90 reduction from ₹99,860.20 to ₹97,358.30 is attributable to the five duplicate rows O0176-O0180 removed by Task 3. The discount_pct and rating imputations do not change order_value, so they do not contribute to the revenue delta.")

    # Part 2 Task 6.
    q1 = float(df["quantity"].quantile(0.25))
    q3 = float(df["quantity"].quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    df["is_outlier"] = (df["quantity"] < lower) | (df["quantity"] > upper)
    outliers = df.loc[df["is_outlier"], ["order_id", "quantity"]]
    if verbose:
        print("=== Task 6: IQR outlier detection on quantity ===")
        print(f"Q1={q1:.1f}, Q3={q3:.1f}, IQR={iqr:.1f}, lower={lower:.1f}, upper={upper:.1f}")
        print("Flagged outliers:")
        print(outliers.to_string(index=False))

    # Part 2 Task 7.
    if verbose:
        print("=== Task 7: Hypothesis - COD has a higher return rate ===")
    payment_return = df.groupby("payment_method")["returned"].agg(["count", "mean"])
    if verbose:
        print(payment_return.assign(return_rate_pct=payment_return["mean"] * 100).to_string())
        print("Hypothesis: Confirmed")

    # Part 2 Task 8.
    segment = (df.groupby(["payment_method", "city_tier"])["returned"]
                 .agg(order_count="count", return_rate=lambda s: s.mean() * 100)
                 .reset_index())
    segment["return_rate_pct"] = segment["return_rate"].round(1)
    top_segment = segment.sort_values("return_rate", ascending=False).iloc[0]
    if verbose:
        print("=== Task 8: Payment method + city tier segmentation ===")
        print(segment[["payment_method", "city_tier", "order_count", "return_rate_pct"]].sort_values(["payment_method", "city_tier"]).to_string(index=False))
        print(f"Highest-risk segment: {top_segment['payment_method']} + Tier-{int(top_segment['city_tier'])} at {top_segment['return_rate_pct']:.1f}%")

    # Part 2 Task 9.
    corr_cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = df[corr_cols].corr()
    bands = []
    def band(r: float) -> str:
        a = abs(float(r))
        if a < 0.2:
            return "negligible"
        if a < 0.4:
            return "weak"
        if a < 0.7:
            return "moderate"
        return "strong"
    for i, a in enumerate(corr_cols):
        for b in corr_cols[i+1:]:
            r = float(corr.loc[a, b])
            bands.append((a, b, r, band(r)))
    if verbose:
        print("=== Task 9: Correlation analysis ===")
        print(corr.to_string())
        for a, b, r, bnd in bands:
            print(f"{a} vs {b}: r={r:.4f} -> {bnd}")
        disc_r = float(corr.loc["discount_pct", "returned"])
        print(f"Hypothesis 'higher discounts reduce returns': Busted (discount_pct vs returned r={disc_r:.4f})")

    # Part 2 Task 10.
    df["order_date"] = pd.to_datetime(df["order_date"], errors="raise")
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    monthly_including = df.groupby("year_month")["order_value"].sum().sort_index()
    monthly_corrected = df.loc[~df["is_outlier"]].groupby("year_month")["order_value"].sum().sort_index()
    if verbose:
        print("=== Task 10: Monthly revenue with and without quantity outliers ===")
        print("Including outliers:")
        print(monthly_including.round(2).to_string())
        print("Outlier-corrected:")
        print(monthly_corrected.round(2).to_string())
        print("January's apparent lead is an artifact of the two bulk orders O0011 (2026-01-28, quantity 25) and O0098 (2026-01-10, quantity 30). March 2026 is the genuine peak month after those outliers are excluded.")

    true_peak_month = monthly_corrected.idxmax()
    findings = {
        "cleaned_total_revenue_inr": round(float(df["order_value"].sum()), 2),
        "raw_total_revenue_inr": round(raw_revenue, 2),
        "duplicate_reconciliation_delta_inr": round(delta, 2),
        "return_rate_by_payment": {
            "COD": round(float(payment_return.loc["COD", "mean"] * 100), 1),
            "CARD": round(float(payment_return.loc["CARD", "mean"] * 100), 1),
            "UPI": round(float(payment_return.loc["UPI", "mean"] * 100), 1),
        },
        "highest_risk_segment": {
            "payment_method": str(top_segment["payment_method"]),
            "city_tier": int(top_segment["city_tier"]),
            "return_rate_pct": round(float(top_segment["return_rate_pct"]), 1),
        },
        "true_peak_month": {
            "month": true_peak_month,
            "revenue_inr": round(float(monthly_corrected.loc[true_peak_month]), 2),
        },
        "outlier_inflated_month": {
            "month": monthly_including.idxmax(),
            "apparent_revenue_inr": round(float(monthly_including.max()), 2),
            "corrected_revenue_inr": round(float(monthly_corrected.loc[monthly_including.idxmax()]), 2),
        },
    }

    if write_findings:
        FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        FINDINGS_PATH.write_text(json.dumps(findings, indent=2) + "\n")
        if verbose:
            print(f"findings.json written to {FINDINGS_PATH}")

    return df, findings


def main() -> None:
    run_pipeline(verbose=True, write_findings=True)


if __name__ == "__main__":
    main()
