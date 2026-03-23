#!/usr/bin/env python3
"""
sync.py — Garmin Connect → garmin JSON
---------------------------------------
Fetches recent health metrics from Garmin Connect and writes to
data/garmin_daily_summary.json (Kelli) or data/garmin_elliott.json (Elliott).

Setup:
    pip install garminconnect python-dotenv

Credentials — add to .env file:
    GARMIN_EMAIL=kelli@example.com
    GARMIN_PASSWORD=kellipassword
    GARMIN_EMAIL_ELLIOTT=elliott@example.com
    GARMIN_PASSWORD_ELLIOTT=elliottpassword

Usage:
    python3 sync.py                        # Kelli, last 7 days
    python3 sync.py --user Elliott         # Elliott, last 7 days
    python3 sync.py --days 90              # Kelli, backfill 90 days
    python3 sync.py --user Elliott --days 90
    python3 sync.py --force                # re-fetch existing dates
"""

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── Third-party ────────────────────────────────────────────────────────────────
try:
    from garminconnect import Garmin, GarminConnectAuthenticationError
except ImportError:
    sys.exit("Missing dependency. Run:  pip install garminconnect python-dotenv")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── User config ────────────────────────────────────────────────────────────────
USER_CONFIG = {
    'Kelli': {
        'email_env':    'GARMIN_EMAIL',
        'password_env': 'GARMIN_PASSWORD',
        'output_file':  Path('data/garmin_daily_summary.json'),
        'token_file':   Path('.garmin_tokens.json'),
    },
    'Elliott': {
        'email_env':    'GARMIN_EMAIL_ELLIOTT',
        'password_env': 'GARMIN_PASSWORD_ELLIOTT',
        'output_file':  Path('data/garmin_elliott.json'),
        'token_file':   Path('.garmin_tokens_elliott.json'),
    },
}

RETRY_DELAY = 2
MAX_RETRIES = 3

# ── Auth ───────────────────────────────────────────────────────────────────────
def get_client(user_cfg: dict) -> Garmin:
    email    = os.environ.get(user_cfg['email_env'], '').strip()
    password = os.environ.get(user_cfg['password_env'], '').strip()

    if not email or not password:
        sys.exit(
            f"Set {user_cfg['email_env']} and {user_cfg['password_env']} "
            "in your .env file or as environment variables."
        )

    token_file = user_cfg['token_file']
    client = Garmin(email, password)

    if token_file.exists():
        try:
            client.garth.loads(token_file.read_text())
            print("✓ Logged in via cached tokens")
            return client
        except Exception:
            print("Token cache expired — logging in fresh…")

    try:
        client.login()
        token_file.write_text(client.garth.dumps())
        print("✓ Logged in, tokens cached")
    except GarminConnectAuthenticationError as e:
        sys.exit(f"Authentication failed: {e}")

    return client

# ── Fetch helpers ──────────────────────────────────────────────────────────────
def safe_get(fn, *args, label="", retries=MAX_RETRIES):
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
    ds = d.isoformat()
    record: dict = {"date": ds}

    stats = safe_get(client.get_stats, ds, label=f"stats {ds}")
    if stats:
        rhr = stats.get("restingHeartRate") or stats.get("minHeartRate")
        if rhr:
            record["restingHr"] = int(rhr)

        bb_list = safe_get(client.get_body_battery, ds, ds, label=f"body battery {ds}")
        if bb_list:
            highs = [r.get("charged") for r in bb_list if r.get("charged")]
            if highs:
                record["bodyBatteryHigh"] = int(max(highs))

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

        # Sleep duration and stages (minutes)
        total_secs = daily.get("sleepTimeSeconds")
        if total_secs:
            record["sleepDuration"] = round(total_secs / 60, 1)

        deep_secs = daily.get("deepSleepSeconds")
        if deep_secs:
            record["sleepDeep"] = round(deep_secs / 60, 1)

        rem_secs = daily.get("remSleepSeconds")
        if rem_secs:
            record["sleepRem"] = round(rem_secs / 60, 1)

    hrv = safe_get(client.get_hrv_data, ds, label=f"HRV {ds}")
    if hrv:
        summary = hrv.get("hrvSummary") or {}
        val = summary.get("lastNight") or summary.get("weeklyAvg") or hrv.get("lastNight")
        if val:
            record["hrv"] = round(float(val), 1)

    resp = safe_get(client.get_respiration_data, ds, label=f"respiration {ds}")
    if resp:
        avg_r = resp.get("avgWakingRespirationValue") or resp.get("avgSleepRespirationValue")
        if avg_r:
            record["respiration"] = round(float(avg_r), 1)

    spo2 = safe_get(client.get_spo2_data, ds, label=f"SpO2 {ds}")
    if spo2:
        reading_list = spo2.get("continuousReadingDTOList") or []
        val = (
            spo2.get("averageSpO2")
            or (reading_list[0].get("spO2Reading") if reading_list else None)
        )
        if val:
            record["pulseOx"] = round(float(val), 1)

    weight_data = safe_get(client.get_body_composition, ds, ds, label=f"weight {ds}")
    if weight_data:
        entries = weight_data.get("dateWeightList") or []
        if entries:
            kg = entries[-1].get("weight")
            if kg:
                kg_val = kg / 1000 if kg > 500 else kg
                record["weight"] = round(kg_val * 2.20462, 1)

    return record

# ── Helpers ────────────────────────────────────────────────────────────────────
def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_existing(output_file: Path) -> list:
    if output_file.exists():
        try:
            return json.loads(output_file.read_text())
        except Exception:
            pass
    return []


def save_records(records: list, output_file: Path):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(sorted(records, key=lambda r: r["date"]), indent=2)
    )

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Sync Garmin Connect → JSON")
    parser.add_argument("--user", type=str, default="Kelli",
                        choices=list(USER_CONFIG.keys()),
                        help="Which user to sync (default: Kelli)")
    parser.add_argument("--days", type=int, default=7,
                        help="How many days back to fetch (default: 7)")
    parser.add_argument("--start", type=str, default=None,
                        help="Specific start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", type=str, default=None,
                        help="Specific end date YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true",
                        help="Re-fetch dates that already exist in the JSON")
    args = parser.parse_args()

    user_cfg    = USER_CONFIG[args.user]
    output_file = user_cfg['output_file']

    end_date   = date.fromisoformat(args.end) if args.end else date.today()
    start_date = date.fromisoformat(args.start) if args.start else end_date - timedelta(days=args.days - 1)

    print(f"User: {args.user}")
    print(f"Fetching {start_date} → {end_date}  ({(end_date - start_date).days + 1} days)")

    existing     = load_existing(output_file)
    existing_map = {r["date"]: r for r in existing}
    dates_needed = [
        d for d in date_range(start_date, end_date)
        if args.force or d.isoformat() not in existing_map
    ]

    if not dates_needed:
        print("✓ Nothing to fetch — all dates already present (use --force to re-fetch)")
        return

    print(f"  {len(dates_needed)} date(s) to fetch")

    client = get_client(user_cfg)

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
        if fetched < len(dates_needed):
            time.sleep(0.5)

    save_records(list(existing_map.values()), output_file)
    print(f"\n✓ Saved {len(existing_map)} total records → {output_file}")


if __name__ == "__main__":
    main()