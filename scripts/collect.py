import json
import os
import time
import urllib.request
from datetime import datetime, timezone

BASES = {
    "kadena": {"lat": 26.3519, "lon": 127.7689},
    "yokota": {"lat": 35.7485, "lon": 139.3486},
    "iwakuni": {"lat": 34.1436, "lon": 132.2356},
    "misawa": {"lat": 40.7032, "lon": 141.3686},
}
PAD = 0.15

SUMMARY_PATH = "data/summary.json"


def fetch_box(lat, lon):
    lamin, lamax = lat - PAD, lat + PAD
    lomin, lomax = lon - PAD, lon + PAD
    url = (
        f"https://opensky-network.org/api/states/all"
        f"?lamin={lamin}&lomin={lomin}&lamax={lamax}&lomax={lomax}"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def load_summary():
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def update_summary(summary, date_str, base_counts):
    # summary: list of {"date": "...", "bases": {name: {total, samples, max, detected_runs}}}
    day = None
    for entry in summary:
        if entry["date"] == date_str:
            day = entry
            break
    if day is None:
        day = {"date": date_str, "bases": {}}
        summary.append(day)

    for name, count in base_counts.items():
        b = day["bases"].setdefault(
            name, {"total": 0, "samples": 0, "max": 0, "detected_runs": 0}
        )
        b["total"] += count
        b["samples"] += 1
        b["max"] = max(b["max"], count)
        if count > 0:
            b["detected_runs"] += 1

    # 古くなりすぎたデータは軽くするため、直近400日分だけ保持
    summary.sort(key=lambda e: e["date"])
    return summary[-400:]


def main():
    now = datetime.now(timezone.utc)
    record = {"timestamp": now.isoformat(), "bases": {}}
    base_counts = {}

    for name, pos in BASES.items():
        try:
            data = fetch_box(pos["lat"], pos["lon"])
            states = data.get("states") or []
            aircraft = [
                {
                    "icao24": s[0],
                    "callsign": (s[1] or "").strip(),
                    "country": s[2],
                    "lon": s[5],
                    "lat": s[6],
                    "alt": s[7],
                    "on_ground": s[8],
                    "speed": s[9],
                }
                for s in states
            ]
        except Exception as e:
            aircraft = []
            print(f"{name}: error - {e}")

        record["bases"][name] = {
            "count": len(aircraft),
            "aircraft": aircraft,
        }
        base_counts[name] = len(aircraft)
        time.sleep(2)

    date_str = now.strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/{date_str}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    summary = load_summary()
    summary = update_summary(summary, date_str, base_counts)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
