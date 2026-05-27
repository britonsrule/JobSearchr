"""
Job Search Script for Jeremiah Marett
Loads all configuration from settings.json.
Can be run directly (python job_search.py) or called from app.py.
"""

import csv
import json
import os
import sys
from datetime import datetime
import pandas as pd
from jobspy import scrape_jobs

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
OUTPUT_CSV   = os.path.join(BASE_DIR, "jobs_results.csv")

DEFAULT_SETTINGS = {
    "location": "Seattle, WA",
    "hours_old": 24,
    "results_per_search": 100,
    "sites": ["indeed", "linkedin"],
    "exclude_companies": ["amazon", "aws"],
    "searches": ["Technical Program Manager", "Strategy Operations Manager technology"],
    "high_signal": ["program manager", "strategy", "operations", "analytics"],
    "med_signal": ["sql", "python", "agile"],
    "neg_signal": ["recruiter", "sales", "warehouse"]
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return {**DEFAULT_SETTINGS, **json.load(f)}
    return DEFAULT_SETTINGS

def score_job(row: pd.Series, high: list, med: list, neg: list) -> int:
    text = " ".join([
        str(row.get("title", "")),
        str(row.get("description", "")),
        str(row.get("company", "")),
    ]).lower()
    score = 0
    for kw in high: score += 10 if kw in text else 0
    for kw in med:  score += 5  if kw in text else 0
    for kw in neg:  score -= 15 if kw in text else 0
    return max(0, min(score, 100))

def run(log=None):
    """
    Run the job search.
    log: optional callable(str) for streaming output (used by Flask SSE).
         If None, prints to stdout.
    """
    def emit(msg):
        if log:
            log(msg)
        else:
            print(msg)

    cfg = load_settings()
    searches          = cfg["searches"]
    location          = cfg["location"]
    hours_old         = int(cfg["hours_old"])
    results_per       = int(cfg["results_per_search"])
    sites             = cfg["sites"]
    exclude_companies = [e.lower() for e in cfg["exclude_companies"]]
    high_signal       = cfg["high_signal"]
    med_signal        = cfg["med_signal"]
    neg_signal        = cfg["neg_signal"]

    emit(f"=== Job Search — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    emit(f"Location: {location}  |  Last {hours_old}h  |  {len(searches)} search terms")
    emit("")

    all_frames = []
    for i, term in enumerate(searches, 1):
        emit(f"[{i}/{len(searches)}] Searching: {term}...")
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location,
                results_wanted=results_per,
                hours_old=hours_old,
                country_indeed="USA",
                enforce_annual_salary=True,
            )
            if df is not None and not df.empty:
                all_frames.append(df)
                emit(f"    → {len(df)} results")
            else:
                emit(f"    → 0 results")
        except Exception as e:
            emit(f"    → Error: {e}")

    if not all_frames:
        emit("No results found across all searches.")
        return 0

    combined = pd.concat(all_frames, ignore_index=True)
    before = len(combined)
    combined.drop_duplicates(subset=["title", "company"], inplace=True)
    emit(f"")
    emit(f"Combined: {before} raw → {len(combined)} after dedup")

    mask = combined["company"].str.lower().apply(
        lambda c: not any(excl in str(c) for excl in exclude_companies)
    )
    combined = combined[mask]
    emit(f"After company exclusions: {len(combined)}")

    combined["relevance_score"] = combined.apply(
        lambda r: score_job(r, high_signal, med_signal, neg_signal), axis=1
    )
    combined.sort_values("relevance_score", ascending=False, inplace=True)

    output_cols = [
        "relevance_score", "title", "company", "location",
        "min_amount", "max_amount", "job_type", "date_posted",
        "job_url", "description"
    ]
    output_cols = [c for c in output_cols if c in combined.columns]
    combined[output_cols].to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL)

    emit(f"Saved {len(combined)} jobs → jobs_results.csv")
    emit("")
    emit("=== Top 10 by Relevance ===")
    for _, row in combined.head(10).iterrows():
        salary = ""
        if pd.notna(row.get("min_amount")) and pd.notna(row.get("max_amount")):
            salary = f"  ${int(row['min_amount']):,}–${int(row['max_amount']):,}"
        emit(f"[{int(row['relevance_score']):>3}] {row['title']} — {row['company']}{salary}")
    emit("")
    emit("DONE")
    return len(combined)

if __name__ == "__main__":
    run()
