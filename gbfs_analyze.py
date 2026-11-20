#!/usr/bin/env python3
"""
Analiza zrzutów z gbfs_logger.py: jak często stacje są puste (0 rowerów), mają najwyżej
1 rower albo są przepełnione (więcej rowerów niż stojaków), w podziale na godziny
i dni robocze / weekendy.

Uwaga: w Metrorowerze (Nextbike) rower można zostawić obok stojaka, więc
num_docks_available = 0 nie oznacza, że nie da się oddać roweru. Dlatego zamiast
„pełnej stacji” liczymy przepełnienie względem pojemności z station_information.

Wynik:
  wynik/stacje_dostepnosc.csv   – jedna linia na stację: współrzędne i odsetki czasu,
                                  gotowe do wczytania w QGIS (warstwa z pliku CSV, X=lon, Y=lat)
  wynik/godziny.csv             – odsetek pustych stacji w całym systemie dla każdej godziny

Użycie:
  python3 gbfs_analyze.py --data dane --out wynik [--tz Europe/Warsaw] [--peak 7-9,15-18]
Wymaga Pythona 3.9+ (moduł zoneinfo); bez dodatkowych bibliotek.
"""
import argparse, csv, glob, gzip, json, os, collections, datetime as dt
from zoneinfo import ZoneInfo

def hours(spec):
    out = set()
    for part in spec.split(","):
        a, b = part.split("-"); out.update(range(int(a), int(b)))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="dane"); ap.add_argument("--out", default="wynik")
    ap.add_argument("--tz", default="Europe/Warsaw"); ap.add_argument("--peak", default="7-9,15-18")
    a = ap.parse_args(); tz = ZoneInfo(a.tz); peak = hours(a.peak); os.makedirs(a.out, exist_ok=True)
    # opis stacji: najnowszy plik
    info = {}
    for p in sorted(glob.glob(os.path.join(a.data, "**", "station_information_*.json.gz"), recursive=True)):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for s in json.load(f)["data"]["stations"]: info[str(s["station_id"])] = s
    # liczniki: stacja -> kategoria -> [liczba zrzutów, puste, najwyżej 1 rower, przepełnione]
    C = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))
    H = collections.defaultdict(lambda: [0, 0])          # (dzień typu, godzina) -> [zrzuty stacji, puste]
    snaps = set()
    files = sorted(glob.glob(os.path.join(a.data, "**", "station_status_*.csv.gz"), recursive=True) +
                   glob.glob(os.path.join(a.data, "**", "status_*.csv.gz"), recursive=True))
    for p in files:
        with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["snapshot_utc"] == "snapshot_utc": continue          # nagłówek powtórzony po scaleniu plików
                if r.get("is_installed") in ("False", "false", "0") or r.get("is_renting") in ("False", "false", "0"): continue
                t = dt.datetime.strptime(r["snapshot_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(tz)
                snaps.add(r["snapshot_utc"])
                kind = "weekend" if t.weekday() >= 5 else "roboczy"
                cats = ["wszystkie", kind] + ([f"szczyt_{kind}"] if t.hour in peak else []) + (["noc"] if t.hour < 5 or t.hour >= 23 else [])
                bikes = int(float(r["num_bikes_available"] or 0))
                cap = info.get(str(r["station_id"]), {}).get("capacity")
                empty = bikes == 0; low = bikes <= 1; over = cap is not None and bikes > cap
                for c in cats:
                    x = C[r["station_id"]][c]; x[0] += 1; x[1] += empty; x[2] += low; x[3] += over
                h = H[(kind, t.hour)]; h[0] += 1; h[1] += empty
    cats = ["wszystkie", "roboczy", "weekend", "szczyt_roboczy", "szczyt_weekend", "noc"]
    with open(os.path.join(a.out, "stacje_dostepnosc.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["station_id", "nazwa", "lat", "lon", "pojemnosc", "region_id"] + [f"{c}_{m}" for c in cats for m in ("zrzuty", "proc_pusta", "proc_max1", "proc_przepelniona")])
        for sid, d in sorted(C.items()):
            s = info.get(str(sid), {}); row = [sid, s.get("name", ""), s.get("lat", ""), s.get("lon", ""), s.get("capacity", ""), s.get("region_id", "")]
            for c in cats:
                n, e, lo, ov = d[c] if c in d else (0, 0, 0, 0)
                row += [n] + [round(100 * v / n, 1) if n else "" for v in (e, lo, ov)]
            w.writerow(row)
    with open(os.path.join(a.out, "godziny.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["typ_dnia", "godzina", "zrzuty_stacji", "proc_pustych"])
        for (k, hr), (n, e) in sorted(H.items()): w.writerow([k, hr, n, round(100 * e / n, 1)])
    print(f"zrzutów: {len(snaps)}, stacji: {len(C)} → {a.out}/")

if __name__ == "__main__":
    main()
