import json
import os
import urllib.request
from datetime import datetime, timezone

# 日本周辺(沖縄〜北海道)をカバーする範囲
BOUNDS = {
    "lat_min": 24.0, "lat_max": 46.0,
    "lon_min": 123.0, "lon_max": 146.0,
}

URL = "https://api.airplanes.live/v2/mil"

def fetch():
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)

def in_japan(ac):
    lat = ac.get("lat")
    lon = ac.get("lon")
    if lat is None or lon is None:
        return False
    return (BOUNDS["lat_min"] <= lat <= BOUNDS["lat_max"] and
            BOUNDS["lon_min"] <= lon <= BOUNDS["lon_max"])

def main():
    data = fetch()
    aircraft = data.get("ac", [])
    japan_aircraft = [ac for ac in aircraft if in_japan(ac)]

    now = datetime.now(timezone.utc)
    record = {
        "timestamp": now.isoformat(),
        "count": len(japan_aircraft),
        "aircraft": [
            {
                "hex": ac.get("hex"),
                "flight": (ac.get("flight") or "").strip(),
                "type": ac.get("t"),
                "lat": ac.get("lat"),
                "lon": ac.get("lon"),
                "alt": ac.get("alt_baro"),
                "speed": ac.get("gs"),
            }
            for ac in japan_aircraft
        ],
    }

    date_str = now.strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/{date_str}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
