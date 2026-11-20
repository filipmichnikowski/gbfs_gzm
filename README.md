# Zapis GBFS – Metrorower (Share4Equity)

Skrypty zapisują co kilka minut stan stacji systemu rowerów publicznych z publicznego GBFS
i liczą, jak często stacje są puste, prawie puste albo przepełnione. Domyślnie: Metrorower w GZM
(`https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_zz/gbfs.json`). Inny system z katalogu
MobilityData (np. Veturilo: `nextbike_vw`, MEVO: `https://gbfs.urbansharing.com/rowermevo.pl/gbfs.json`)
podaje się opcją `--feed`.

Potrzebny jest tylko Python 3.9+ (bez dodatkowych bibliotek).

## Pliki

- `gbfs_logger.py` – jeden zrzut przy każdym uruchomieniu (albo `--loop 10`: co 10 minut).
- `gbfs_analyze.py` – analiza zebranych zrzutów.
- `.github/workflows/gbfs.yml` – uruchamianie co 10 minut w GitHub Actions.
- `pl.share4equity.gbfs.plist` – uruchamianie co 10 minut na Macu (launchd).

## Sposób 1 (polecany): GitHub Actions – bez własnego komputera

1. Załóż na GitHubie nowe repozytorium **publiczne** (w publicznym minuty Actions są bez limitu;
   w prywatnym zrzut co 10 minut przekroczy darmowe 2000 minut miesięcznie – wtedy ustaw `*/30`).
   Dane GBFS są publiczne, więc publiczne repozytorium nie ujawnia niczego nowego.
2. Wgraj do niego wszystkie pliki z tego folderu, zachowując folder `.github/workflows`.
3. W repozytorium: Settings → Actions → General → Workflow permissions → „Read and write permissions”.
4. W zakładce Actions uruchom „Zrzut GBFS Metrorower” ręcznie (Run workflow) i sprawdź,
   czy w folderze `dane` pojawił się pierwszy plik.
5. Potem zrzuty idą same. GitHub bywa spóźniony o kilka minut i czasem pomija uruchomienie –
   analiza liczy odsetki z tego, co zebrano, więc nie szkodzi.

Dane trafiają do `dane/RRRR-MM-DD/status_GGMMSS.csv.gz` (osobny plik na zrzut, żeby repozytorium
nie puchło) oraz `dane/station_information_RRRR-MM-DD.json.gz` (raz na dobę: nazwy, współrzędne,
pojemność stacji).

## Sposób 2: komputer, który jest stale włączony

Linux (cron, co 10 minut):

    */10 * * * * cd /ścieżka/gbfs && /usr/bin/python3 gbfs_logger.py --out dane >> dane/log.txt 2>&1

Mac (launchd): w pliku `pl.share4equity.gbfs.plist` wpisz ścieżki zamiast `/ŚCIEŻKA/DO/`, skopiuj go do
`~/Library/LaunchAgents/` i wykonaj `launchctl load ~/Library/LaunchAgents/pl.share4equity.gbfs.plist`.
Uwaga: uśpiony Mac nie zbiera danych.

Albo po prostu w terminalu: `python3 gbfs_logger.py --loop 10` (działa, dopóki terminal jest otwarty).

## Analiza

Po kilku tygodniach:

    python3 gbfs_analyze.py --data dane --out wynik

- `wynik/stacje_dostepnosc.csv` – dla każdej stacji: numer, współrzędne, pojemność, obszar i odsetek zrzutów,
  w których była pusta (0 rowerów), miała najwyżej 1 rower albo była przepełniona (więcej rowerów niż
  stojaków – w Metrorowerze rower można zostawić obok stojaka): ogółem, w dni robocze, w weekendy,
  w szczycie (domyślnie 7–9 i 15–18, zmiana: `--peak 6-9,14-18`) i w nocy (23–5).
  W QGIS: Warstwa → Dodaj warstwę → Tekst rozdzielany (CSV), X = lon, Y = lat, EPSG:4326.
- `wynik/godziny.csv` – odsetek pustych stacji w całym systemie dla każdej godziny.

Pomijane są stacje wyłączone (`is_installed` lub `is_renting` = false).

## Do czego to służy w narzędziowniku

Wskaźnik „Dostępność w czasie i niezawodność” i ścieżka „Kto ma dostęp, a kto nie?”: gdzie i kiedy
rower nie jest dostępny, w porównaniu z danymi o mieszkańcach (spis 2021 w siatce 1 km²).
Polski odpowiednik przykładu z Nowego Jorku (NYC Comptroller 2023) w karcie wyzwania „Dostęp zależy od pory”.

## Uwagi

- Przed publikacją wyników sprawdź licencję danych w `system_information` (pole `license_url`
  lub warunki na stronie operatora).
- Skrypt nie zbiera przejazdów – GBFS ich nie zawiera. Zmiany liczby rowerów na stacji między
  zrzutami pozwalają je tylko szacować.
- Pierwszy zrzut wypisuje liczbę stacji; rozmiar plików da się sprawdzić po dniu zbierania.
