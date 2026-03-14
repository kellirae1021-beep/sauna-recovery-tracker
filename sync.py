#!/usr/bin/env python3
"""
sync.py — Garmin Connect → garmin_daily_summary.json
-----------------------------------------------------
Fetches recent health metrics from Garmin Connect and merges them
into data/garmin_daily_summary.json in the format expected by the
Sauna Recovery Tracker.

Setup:
    pip install garminconnect python-dotenv

First run:
    python sync.py --days 90

Subsequent runs (cron / daily):
    python sync.py
    # defaults to last 7 days, only fills gaps

Credentials — create a .env file in the same folder:
    GARMIN_EMAIL=you@example.com
    GARMIN_PASSWORD=yourpassword

Token cache is stored in .garmin_tokens.json so you won't be
re-prompted for MFA on every run.
"""

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── Third-party ───────────────────────────────────────────────────────────────
try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
except ImportError:
    sys.exit("Missing dependency. Run:  pip install garminconnect python-dotenv")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional if env vars are set another way

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_FILE   = Path("data/garmin_daily_summary.json")
TOKEN_FILE    = Path(".garmin_tokens.json")
RETRY_DELAY   = 2      # seconds between retries on rate-limit
MAX_RETRIES   = 3

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_client() -> Garmin:
    """Return an authenticated Garmin client, using cached tokens when possible."""
    email    = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()

    if not email or not password:
        sys.exit(
            "Set GARMIN_EMAIL and GARMIN_PASSWORD in a .env file or as "
            "environment variables."
        )

    client = Garmin(email, password)

    # Try cached tokens first
    if TOKEN_FILE.exists():
        try:
            client.login(TOKEN_FILE.read_text())
            print("✓ Logged in via cached tokens")
            return client
        except Exception:
            print("Token cache expired or invalid — logging in fresh…")

    # Full login (may trigger MFA prompt in terminal)
    try:
        client.login()
        TOKEN_FILE.write_text(client.garth.dumps())
        print("✓ Logged in, tokens cached")
    except GarminConnectAuthenticationError as e:
        sys.exit(f"Authentication failed: {e}")

    return client


# ── Fetch helpers ─────────────────────────────────────────────────────────────
def safe_get(fn, *args, label="", retries=MAX_RETRIES):
    """Call a Garmin API function with retry on rate-limit / transient errors."""
    for attempt in range(retries):
        try:
            return fn(*args)
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "too many" in msg:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"  Rate limited on {label}, waiting {wait}s…")
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ⚠ Could not fetch {label}: {e}")
                return None
    return None


def fetch_day(client: Garmin, d: date) -> dict:
    """Fetch all relevant metrics for a single date and return a merged record."""
    ds = d.isoformat()
    record: dict = {"date": ds}

    # ── Stats (resting HR, average stress, body battery) ─────────────────────
    stats = safe_get(client.get_stats, ds, label=f"stats {ds}")
    if stats:
        rhr = stats.get("restingHeartRate") or stats.get("minHeartRate")
        if rhr:
            record["restingHr"] = int(rhr)

        # Body battery: Garmin returns max charged value for the day
        bb_list = safe_get(client.get_body_battery, ds, ds, label=f"body battery {ds}")
        if bb_list:
            highs = [r.get("charged") or r.get("bodyBatteryDuringSleep") for r in bb_list if r.get("charged")]
            if highs:
                record["bodyBatteryHigh"] = int(max(highs))

    # ── Sleep ─────────────────────────────────────────────────────────────────
    sleep = safe_get(client.get_sleep_data, ds, label=f"sleep {ds}")
    if sleep:
        daily = sleep.get("dailySleepDTO") or {}
        score = (
            daily.get("sleepScores", {}).get("overall", {}).get("value")
            or daily.get("sleepScore")
            or sleep.get("sleepScores", {}).get("overall", {}).get("value")
        )
        if score is not None:
            record["sleepScore"] = int(score)

    # ── HRV ───────────────────────────────────────────────────────────────────
    hrv = safe_get(client.get_hrv_data, ds, label=f"HRV {ds}")
    if hrv:
        summary = hrv.get("hrvSummary") or {}
        val = summary.get("lastNight") or summary.get("weeklyAvg") or hrv.get("lastNight")
        if val:
            record["hrv"] = round(float(val), 1)

    # ── Respiration ───────────────────────────────────────────────────────────
    resp = safe_get(client.get_respiration_data, ds, label=f"respiration {ds}")
    if resp:
        avg_r = resp.get("avgWakingRespirationValue") or resp.get("avgSleepRespirationValue")
        if avg_r:
            record["respiration"] = round(float(avg_r), 1)

    # ── Pulse Ox ──────────────────────────────────────────────────────────────
    spo2 = safe_get(client.get_spo2_data, ds, label=f"SpO2 {ds}")
    if spo2:
        val = (
            spo2.get("averageSpO2")
            or spo2.get("continuousReadingDTOList", [{}])[0].get("spO2Reading")
        )
        if val:
            record["pulseOx"] = round(float(val), 1)

    # ── Weight (manual log) ───────────────────────────────────────────────────
    weight_data = safe_get(client.get_body_composition, ds, ds, label=f"weight {ds}")
    if weight_data:
        entries = weight_data.get("dateWeightList") or []
        if entries:
            kg = entries[-1].get("weight")  # Garmin stores in grams(!) or kg
            if kg:
                # Garmin API returns grams for some endpoints, kg for others
                # Heuristic: if value > 500, it's probably grams
                kg_val = kg / 1000 if kg > 500 else kg
                lbs = round(kg_val * 2.20462, 1)
                record["weight"] = lbs

    return record


# ── Date range helpers ────────────────────────────────────────────────────────
def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_existing() -> list[dict]:
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text())
        except Exception:
            pass
    return []


def save_records(records: list[dict]):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(sorted(records, key=lambda r: r["date"]), indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Sync Garmin Connect → garmin_daily_summary.json")
    parser.add_argument("--days", type=int, default=7,
                        help="How many days back to fetch (default: 7)")
    parser.add_argument("--start", type=str, default=None,
                        help="Specific start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", type=str, default=None,
                        help="Specific end date YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch dates that already exist in the JSON")
    args = parser.parse_args()

    end_date   = date.fromisoformat(args.end) if args.end else date.today()
    start_date = date.fromisoformat(args.start) if args.start else end_date - timedelta(days=args.days - 1)

    print(f"Fetching {start_date} → {end_date}  ({(end_date - start_date).days + 1} days)")

    existing     = load_existing()
    existing_map = {r["date"]: r for r in existing}
    dates_needed = [
        d for d in date_range(start_date, end_date)
        if args.force or d.isoformat() not in existing_map
    ]

    if not dates_needed:
        print("✓ Nothing to fetch — all dates already present (use --force to re-fetch)")
        return

    print(f"  {len(dates_needed)} date(s) to fetch")

    client = get_client()

    fetched = 0
    for d in dates_needed:
        print(f"  {d.isoformat()}…", end=" ", flush=True)
        record = fetch_day(client, d)
        metrics = [k for k in record if k != "date"]
        if metrics:
            existing_map[d.isoformat()] = record
            print(f"✓  ({', '.join(metrics)})")
        else:
            print("no data")
        fetched += 1
        # Polite delay between days to avoid hammering the API
        if fetched < len(dates_needed):
            time.sleep(0.5)

    save_records(list(existing_map.values()))
    print(f"\n✓ Saved {len(existing_map)} total records → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()