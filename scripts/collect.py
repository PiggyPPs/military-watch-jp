import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

BASES = {
    "kadena": {"lat": 26.3519, "lon": 127.7689},
    "yokota": {"lat": 35.7485, "lon": 139.3486},
    "iwakuni": {"lat": 34.1436, "lon": 132.2356},
    "misawa": {"lat": 40.7032, "lon": 141.3686},
    "futenma": {"lat": 26.2706, "lon": 127.7556},
    "atsugi": {"lat": 35.4544, "lon": 139.4500},
}
PAD = 0.15

SUMMARY_PATH = "data/summary.json"

# 日本の主要な旅客・貨物航空会社のコールサイン接頭辞(ICAO 3レター)。
# ここに一致したものだけを「旅客便」として扱い、それ以外(軍用機・自衛隊機・
# 不明機・一致しなかった民間機なども含む)は「それ以外」として振り分ける。
# ※ 完全な判定ではなく、あくまで目安のための簡易分類。
CIVILIAN_PREFIXES = [
    "ANA", "JAL", "JTA", "SKY", "SNA", "SFJ", "ADO", "IBX", "JJP", "APJ",
    "FDA", "ORC", "AJX", "NCA", "JAC", "RAC", "GNK", "WAJ",
]
CIVILIAN_PATTERN = re.compile(r"^(" + "|".join(CIVILIAN_PREFIXES) + r")\d")


def classify(callsign):
    cs = (callsign or "").strip().upper()
    if CIVILIAN_PATTERN.match(cs):
        return "civilian"
    return "other"


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


def empty_bucket():
    return {"total": 0, "samples": 0, "max": 0, "detected_runs": 0}


def add_sample(bucket, count):
    bucket["total"] += count
    bucket["samples"] += 1
    bucket["max"] = max(bucket["max"], count)
    if count > 0:
        bucket["detected_runs"] += 1


def update_summary(summary, date_str, base_stats):
    # summary: list of {"date": "...", "bases": {name: {total, samples, max,
    #   detected_runs, civilian: {...}, other: {...}}}}
    day = None
    for entry in summary:
        if entry["date"] == date_str:
            day = entry
            break
    if day is None:
        day = {"date": date_str, "bases": {}}
        summary.append(day)

    for name, stats in base_stats.items():
        b = day["bases"].setdefault(name, empty_bucket())
        b.setdefault("civilian", empty_bucket())
        b.setdefault("other", empty_bucket())

        add_sample(b, stats["total"])
        add_sample(b["civilian"], stats["civilian"])
        add_sample(b["other"], stats["other"])

    # 古くなりすぎたデータは軽くするため、直近400日分だけ保持
    summary.sort(key=lambda e: e["date"])
    return summary[-400:]


def main():
    now = datetime.now(timezone.utc)
    record = {"timestamp": now.isoformat(), "bases": {}}
    base_stats = {}

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
                    "category": classify(s[1]),
                }
                for s in states
            ]
        except Exception as e:
            aircraft = []
            print(f"{name}: error - {e}")

        civilian_count = sum(1 for a in aircraft if a["category"] == "civilian")
        other_count = len(aircraft) - civilian_count

        record["bases"][name] = {
            "count": len(aircraft),
            "aircraft": aircraft,
        }
        base_stats[name] = {
            "total": len(aircraft),
            "civilian": civilian_count,
            "other": other_count,
        }
        time.sleep(2)

    date_str = now.strftime("%Y-%m-%d")
    os.makedirs("data", exist_ok=True)
    path = f"data/{date_str}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    summary = load_summary()
    summary = update_summary(summary, date_str, base_stats)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
