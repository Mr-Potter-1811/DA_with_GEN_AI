from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from clean_and_eda import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "visualizations"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, _ = run_pipeline(verbose=False, write_findings=True)

    # Return-rate chart: cleaned payment methods, descending.
    payment_rates = (df.groupby("payment_method")["returned"].mean() * 100).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(payment_rates.index, payment_rates.values)
    for bar, value in zip(bars, payment_rates.values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1, f"{value:.1f}%", ha="center", va="bottom")
    card_rate = payment_rates.loc["CARD"]
    ax.set_title(f"COD Returns at {payment_rates.loc['COD']:.1f}% - {payment_rates.loc['COD'] / card_rate:.0f}x Card")
    ax.set_xlabel("Payment Method")
    ax.set_ylabel("Return Rate (%)")
    ax.set_ylim(0, max(payment_rates.values) + 10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "return_rate_by_payment.png", dpi=160)
    plt.close(fig)

    # Outlier-corrected monthly revenue line chart.
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)
    corrected = df.loc[~df["is_outlier"]].groupby("year_month")["order_value"].sum().sort_index()
    peak = corrected.idxmax()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(corrected.index, corrected.values, marker="o")
    ax.set_title(f"Outlier-Corrected Monthly Revenue - Peak: {peak}")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue (INR)")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "monthly_revenue_trend.png", dpi=160)
    plt.close(fig)

    print(f"Saved {OUT_DIR / 'return_rate_by_payment.png'}")
    print(f"Saved {OUT_DIR / 'monthly_revenue_trend.png'}")


if __name__ == "__main__":
    main()
