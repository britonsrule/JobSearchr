"""
Job Search Script
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

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
OUTPUT_CSV    = os.path.join(BASE_DIR, "jobs_results.csv")

DEFAULT_SETTINGS = {
    "location": "Remote",
    "hours_old": 24,
    "results_per_search": 100,
    "sites": ["indeed", "linkedin"],
    "exclude_companies": ["amazon", "aws"],
    "searches": {
        "Technical Program Manager": [
            "Technical Program Manager", "Senior Program Manager",
        ],
        "Business Operations": [
            "Business Operations Manager", "Strategy Operations Manager technology",
        ],
    },
    "high_signal": ["program manager", "strategy", "operations", "analytics"],
    "med_signal": ["sql", "python", "agile"],
    "neg_signal": ["recruiter", "sales", "warehouse"],
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
    # small bonus: jobs surfaced by more than one job group are more likely a fit
    match_count = row.get("match_count", 1)
    if match_count and match_count > 1:
        score += 5 * (match_count - 1)
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
    searches          = cfg["searches"]          # dict: job -> [terms]
    location          = cfg["location"]
    hours_old         = int(cfg["hours_old"])
    results_per       = int(cfg["results_per_search"])
    sites             = cfg["sites"]
    exclude_companies = [e.lower() for e in cfg["exclude_companies"]]
    high_signal       = cfg["high_signal"]
    med_signal        = cfg["med_signal"]
    neg_signal        = cfg["neg_signal"]

    # Support both the new nested dict {job: [terms]} and a legacy flat list.
    if isinstance(searches, dict):
        pairs = [(job, term) for job, terms in searches.items() for term in terms]
    else:
        pairs = [("Uncategorized", term) for term in searches]

    emit(f"=== Job Search — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    emit(f"Location: {location}  |  Last {hours_old}h  |  "
         f"{len(searches) if isinstance(searches, dict) else 1} job groups, "
         f"{len(pairs)} search terms")
    emit("")

    all_frames = []
    for i, (job, term) in enumerate(pairs, 1):
        emit(f"[{i}/{len(pairs)}] {job}: {term}...")
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
                df["search_job"]  = job
                df["search_term"] = term
                all_frames.append(df)
                emit(f"    → {len(df)} results")
            else:
                emit("    → 0 results")
        except Exception as e:
            emit(f"    → Error: {e}")

    if not all_frames:
        emit("No results found across all searches.")
        return 0

    combined = pd.concat(all_frames, ignore_index=True)
    before = len(combined)

    # Dedup key: prefer job_url when present, else fall back to title+company.
    if "job_url" in combined.columns and combined["job_url"].notna().any():
        key = "job_url"
        combined[key] = combined[key].fillna(
            combined["title"].astype(str) + "|" + combined["company"].astype(str)
        )
    else:
        key = "_tc_key"
        combined[key] = (combined["title"].astype(str) + "|"
                         + combined["company"].astype(str))

    # Preserve every job group that surfaced each unique posting before dedup.
    job_map = combined.groupby(key)["search_job"].apply(
        lambda s: sorted(set(s))
    ).to_dict()

    combined = combined.drop_duplicates(subset=[key]).copy()
    combined["matched_jobs"] = combined[key].map(job_map)
    combined["match_count"]  = combined["matched_jobs"].apply(len)
    emit("")
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
        "relevance_score", "match_count", "matched_jobs",
        "title", "company", "location",
        "min_amount", "max_amount", "job_type", "date_posted",
        "job_url", "description",
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
