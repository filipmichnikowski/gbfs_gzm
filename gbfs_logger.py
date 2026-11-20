#!/usr/bin/env python3
"""
Zapis stanu systemu SM z publicznego GBFS (np. Metrorower w GZM).

Każde uruchomienie pobiera aktualny stan stacji (station_status) i dopisuje go
do dziennego pliku CSV skompresowanego gzipem. Raz na dobę zapisuje też opis
stacji (station_information: nazwy, współrzędne, pojemność). Działa na samej
bibliotece standardowej Pythona 3.8+.

Użycie:
  python3 gbfs_logger.py                      # jeden zrzut (do cron / GitHub Actions)
  python3 gbfs_logger.py --loop 10            # zrzut co 10 minut, aż do przerwania
  python3 gbfs_logger.py --feed URL --out DIR # inny system / inny katalog
  python3 gbfs_logger.py --layout snapshot    # osobny plik na każdy zrzut (dla GitHub Actions)

Domyślnie: Metrorower GZM (nextbike_zz), katalog ./dane.
"""
import argparse, csv, datetime as dt, gzip, io, json, os, sys, time, urllib.request, urllib.error

DEFAULT_FEED = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_zz/gbfs.json"
UA = "Share4Equity-GBFS-logger/1.0 (research, UAM Poznan)"
STATUS_COLS = ["snapshot_utc", "last_reported", "station_id", "num_bikes_available",
               "num_docks_available", "num_bikes_disabled", "num_docks_disabled",
               "is_installed", "is_renting", "is_returning", "vehicle_types_available"]

def get_json(url, timeout=30, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e; time.sleep(5 * (i + 1))
    raise RuntimeError(f"nie udało się pobrać {url}: {last!r}")

def feed_urls(discovery, lang=None):
    j = get_json(discovery)
    data = j.get("data", {})
    if "feeds" in data:                       # GBFS 3.x
        feeds = data["feeds"]
    else:                                     # GBFS 2.x: {"pl": {"feeds": [...]}, ...}
        key = lang if lang in data else next(iter(data))
        feeds = data[key]["feeds"]
    return {f["name"]: f["url"] for f in feeds}

def append_csv_gz(path, header, rows):
    new = not os.path.exists(path)
    buf = io.StringIO(); w = csv.writer(buf)
    if new: w.writerow(header)
    w.writerows(rows)
    with gzip.open(path, "at", encoding="utf-8", newline="") as f:   # każde dopisanie to osobny człon gzip – czytelny normalnie
        f.write(buf.getvalue())

def snapshot(feed, out, lang=None, layout="daily", log=print):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ"); day = now.strftime("%Y-%m-%d")
    urls = feed_urls(feed, lang)
    os.makedirs(out, exist_ok=True)
    # 1) stan stacji
    if "station_status" not in urls:
        raise RuntimeError("w GBFS brak station_status – system bez stacji? (zob. README)")
    st = get_json(urls["station_status"])
    stations = st["data"]["stations"]
    rows = []
    for s in stations:
        vt = s.get("vehicle_types_available")
        rows.append([stamp, s.get("last_reported"), s.get("station_id"),
                     s.get("num_bikes_available", s.get("num_vehicles_available")),
                     s.get("num_docks_available"), s.get("num_bikes_disabled"), s.get("num_docks_disabled"),
                     s.get("is_installed"), s.get("is_renting"), s.get("is_returning"),
                     json.dumps(vt, ensure_ascii=False, separators=(",", ":")) if vt else ""])
    if layout == "snapshot":                  # osobny mały plik na każdy zrzut (dobre dla repozytorium git)
        os.makedirs(os.path.join(out, day), exist_ok=True)
        append_csv_gz(os.path.join(out, day, f"status_{now.strftime('%H%M%S')}.csv.gz"), STATUS_COLS, rows)
    else:                                     # jeden plik dziennie, dopisywany (dobre dla dysku lokalnego)
        append_csv_gz(os.path.join(out, f"station_status_{day}.csv.gz"), STATUS_COLS, rows)
    # 2) opis stacji – raz na dobę
    info_path = os.path.join(out, f"station_information_{day}.json.gz")
    if "station_information" in urls and not os.path.exists(info_path):
        info = get_json(urls["station_information"])
        with gzip.open(info_path, "wt", encoding="utf-8") as f: json.dump(info, f, ensure_ascii=False)
    # 3) wolne pojazdy poza stacjami (jeśli system je publikuje) – tylko liczba w danej chwili
    fb_name = "vehicle_status" if "vehicle_status" in urls else ("free_bike_status" if "free_bike_status" in urls else None)
    n_free = ""
    if fb_name:
        fb = get_json(urls[fb_name]); lst = fb["data"].get("vehicles", fb["data"].get("bikes", []))
        n_free = sum(1 for b in lst if not b.get("station_id"))
    if layout != "snapshot":
      append_csv_gz(os.path.join(out, "log.csv.gz"), ["snapshot_utc", "stations", "bikes_available_total", "free_floating_vehicles"],
                    [[stamp, len(stations), sum((s.get("num_bikes_available") or 0) for s in stations), n_free]])
    log(f"{stamp} OK: {len(stations)} stacji")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", default=os.environ.get("GBFS_FEED", DEFAULT_FEED), help="adres gbfs.json")
    ap.add_argument("--out", default=os.environ.get("GBFS_OUT", "dane"), help="katalog na dane")
    ap.add_argument("--lang", default="pl", help="język feedu GBFS 2.x (domyślnie pl, jeśli jest)")
    ap.add_argument("--loop", type=float, default=0, help="odstęp w minutach; 0 = jeden zrzut")
    ap.add_argument("--layout", choices=["daily", "snapshot"], default=os.environ.get("GBFS_LAYOUT", "daily"),
                    help="daily: jeden plik na dobę (lokalnie); snapshot: plik na każdy zrzut (GitHub)")
    a = ap.parse_args()
    if not a.loop:
        snapshot(a.feed, a.out, a.lang, a.layout); return
    while True:
        t0 = time.time()
        try: snapshot(a.feed, a.out, a.lang, a.layout)
        except Exception as e: print(f"BŁĄD: {e}", file=sys.stderr)
        time.sleep(max(5, a.loop * 60 - (time.time() - t0)))

if __name__ == "__main__":
    main()
