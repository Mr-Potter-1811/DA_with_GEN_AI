from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
SAMPLE_PATH = ROOT / "narrator" / "sample_output.txt"


def _fmt_num(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}" if isinstance(value, float) or not float(value).is_integer() else f"{value:,}"
    return str(value)


def generate_scr_narrative_offline(findings: dict) -> dict:
    cleaned = _fmt_num(findings["cleaned_total_revenue_inr"])
    raw = _fmt_num(findings["raw_total_revenue_inr"])
    delta = _fmt_num(findings["duplicate_reconciliation_delta_inr"])
    cod = findings["return_rate_by_payment"]["COD"]
    card = findings["return_rate_by_payment"]["CARD"]
    upi = findings["return_rate_by_payment"]["UPI"]
    risk = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    narrative = f"""Situation
Mamaearth's cleaned order data shows total revenue of ₹{cleaned}, compared with raw revenue of ₹{raw}. Returns vary materially by payment method: COD is {cod:.1f}%, versus {card:.1f}% for CARD and {upi:.1f}% for UPI.

Complication
The risk is concentrated rather than uniform. The highest-risk segment is COD in Tier-{risk['city_tier']} cities, where the return rate is {risk['return_rate_pct']:.1f}%. The reconciliation from raw to cleaned revenue is ₹{delta}; this exact difference comes from the five duplicate rows removed during cleaning, not from discount or rating imputation. In time-series reporting, January initially appears to lead at ₹{inflated['apparent_revenue_inr']:,.2f}, but that is inflated by two bulk-order outliers.

Resolution
Prioritize COD operations in Tier-{risk['city_tier']} cities, especially return-prevention and order-validation controls. Use the cleaned series for performance management: March 2026 is the true peak month at ₹{peak['revenue_inr']:,.2f}, while January's corrected revenue is ₹{inflated['corrected_revenue_inr']:,.2f}. The key operating metric is therefore the verified cleaned revenue and the concentrated COD/Tier-{risk['city_tier']} return risk, rather than the raw headline trend."""
    return {"status": "success", "narrative": narrative, "tokens": None}


def generate_scr_narrative(findings: dict) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return generate_scr_narrative_offline(findings)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),
        )
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        system_instruction = (
            "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
            "Write exactly three labeled sections: Situation, Complication, Resolution. "
            "Every number in the output must come only from the supplied findings and must appear "
            "with the same value; do not invent statistics or infer new numeric values. Keep the "
            "narrative concise and action-oriented."
        )
        # Build the user prompt from findings; do not hardcode the verified business numbers here.
        user_prompt = (
            "Create an SCR business narrative from this verified findings dictionary. "
            "Preserve all supplied values exactly when mentioned.\n\n"
            + json.dumps(findings, indent=2)
        )

        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,

                # This is a factual business report, not creative writing.
                # Gemini 3.8 Flash ignores custom temperature values,
                # so do not pass temperature here.

                # Keep reasoning efficient for this straightforward task.
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"
                ),

                # Leave room for reasoning and the complete three-section report.
                max_output_tokens=1200,
            ),
        )

        candidate = (
            response.candidates[0]
            if response.candidates
            else None
        )

        print("Gemini response text:", repr(response.text))

        if candidate:
            print("Finish reason:", candidate.finish_reason)

        if response.usage_metadata:
            print("Usage metadata:", response.usage_metadata)

        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        return {"status": "success", "narrative": response.text, "tokens": tokens}
    except Exception as err:
        return {
            "status": "error",
            "narrative": None,
            "message": f"{type(err).__name__}: {err}",
        }


def _normalize_numbers(text: str) -> str:
    return text.replace(",", "")

import re

def check_numeric_accuracy(narrative: str) -> bool:
    """Validate required values numerically, not by exact formatting."""

    # Convert number strings such as "97,358.30" and "97358.3"
    # into comparable floating-point numbers.
    number_strings = re.findall(
        r"(?<![A-Za-z0-9_])\d[\d,]*(?:\.\d+)?",
        narrative,
    )

    numbers = []
    for number_string in number_strings:
        try:
            numbers.append(float(number_string.replace(",", "")))
        except ValueError:
            continue

    def contains_number(expected: float) -> bool:
        # Small tolerance permits harmless display-rounding differences.
        return any(abs(number - expected) < 0.011 for number in numbers)

    text = narrative.lower()

    checks = {
        "97,358.30": contains_number(97358.30),
        "44.4": contains_number(44.4),
        "54.5": contains_number(54.5),
        "2,501.90": contains_number(2501.90),
        "March + 20,318.90": (
            ("march" in text or "2026-03" in text)
            and contains_number(20318.90)
        ),
    }

    for metric, passed in checks.items():
        print(
            f"Numeric accuracy - {metric}: "
            f"{'PASS' if passed else 'FAIL'}"
        )

    return all(checks.values())



def main() -> None:
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    result = generate_scr_narrative(findings)

    # Fall back if the Gemini API call itself failed.
    if result["status"] == "error":
        print(f"Gemini API error: {result['message']}")
        print("Using offline fallback.")
        result = generate_scr_narrative_offline(findings)

    narrative = result.get("narrative") or ""

    # Validate the generated narrative before saving it.
    ok = check_numeric_accuracy(narrative)

    # A successful API call can still produce an incomplete narrative.
    if not ok:
        print(
            "Generated narrative failed numeric validation. "
            "Switching to offline fallback."
        )
        result = generate_scr_narrative_offline(findings)
        narrative = result["narrative"]

    # Save the selected narrative, not the failed Gemini response.
    SAMPLE_PATH.write_text(
        narrative.rstrip() + "\n",
        encoding="utf-8",
    )

    # Validate the actual saved file, as required by the project brief.
    saved_narrative = SAMPLE_PATH.read_text(encoding="utf-8")
    print("\n" + saved_narrative)

    ok = check_numeric_accuracy(saved_narrative)
    print(f"Saved sample output to {SAMPLE_PATH}")

    if not ok:
        raise SystemExit("Numeric accuracy checklist failed.")


if __name__ == "__main__":
    main()
