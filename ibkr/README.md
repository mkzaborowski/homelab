# Portfel IBKR

Codziennie pobiera stan rachunku z Interactive Brokers (Flex Web Service),
zapisuje historię, buduje arkusz Excel w układzie znanym z AWP i — opcjonalnie —
wypycha go do Google Sheets. Do tego panel WWW ze statystykami portfela.

Nie wymaga TWS ani IB Gateway — Flex to zwykłe REST-owe API po tokenie.

## Co pokazuje panel

Cztery zakładki, stan zapamiętywany w `localStorage`:

**Przegląd** — NAV, zmiana dzienna, wynik otwarty, gotówka, liczba zyskownych
i stratnych spółek, koncentracja top 5 wraz z indeksem HHI, ryzyko stopów oraz
zmiany MTD / QTD / YTD i od pierwszego zrzutu. Do tego wykres NAV z przełącznikiem
zakresu (1M / 3M / 1R / wszystko), pierścień struktury portfela i słupki
najlepszych oraz najsłabszych pozycji.

**Pozycje** — tabela wg koszyków ze zwijaniem grup, sortowaniem po każdej
kolumnie, wyszukiwarką i rozbiciem na loty (transze zakupu) wraz ze stopami
i dystansem do stopa. Osobno covered calls: dni do wygaśnięcia, ITM/OTM,
pokrycie akcjami.

**Analiza** — histogram wyników, udział koszyków, kapitał wg długości trzymania,
ekspozycja walutowa, ranking największych pozycji.

**Ustawienia** — koszyki, oceny i stopy oraz log pobrań.

Ostrzeżenia (call w pieniądzu, call bez pokrycia, spółka bez stopa) trafiają
na pasek nad podsumowaniem.

Wykresy rysowane są własnym kodem w SVG — panel nie pobiera niczego z zewnątrz,
działa też w trybie ciemnym systemu.

## Czego Flex nie umie

Flex **nie udostępnia otwartych zleceń**, więc poziomów stop-loss (u Ciebie
zlecenia GTC) nie da się pobrać automatycznie. Wpisujesz je w panelu, per
ticker. Natomiast **realizacja** stopa zaciąga się sama — sprzedaż widać
w sekcji Trades.

## Konfiguracja Flex Query (raz)

Client Portal → **Reporting → Flex Queries → Activity Flex Query → +**

Zaznacz sekcje:

| Sekcja | Opcja | Po co |
|---|---|---|
| Account Information | — | waluta bazowa rachunku |
| Open Positions | **Lot** | pozycje, ceny, koszt, dane opcji |
| Trades | **Execution** | transakcje, wykrywanie realizacji stopów |
| Cash Report | **Base Currency Summary** | gotówka na rachunku |
| Net Asset Value (NAV) in Base | — | NAV do procentów i wykresu |
| Change in Dividend Accruals | — | naliczone dywidendy |

W każdej sekcji zaznacz **Select All** na liście pól — brak jednego pola
(np. `costBasisPrice`) daje raport, który parsuje się bez błędu, ale pokazuje zera.
Sekcja *Financial Instrument Information* nie jest potrzebna: opis, strike
i datę wygaśnięcia parser czyta wprost z wierszy Open Positions i Trades.

Poziomy szczegółowości są istotne. Flex potrafi zwrócić pozycje jednocześnie
jako SUMMARY i LOT, a transakcje jako ORDER i EXECUTION — zsumowanie obu
poziomów zawyżyłoby portfel dwukrotnie. Parser sam odrzuca wiersze zbiorcze
(`_bez_duplikatow`), więc nadmiarowe zaznaczenie nic nie zepsuje, ale **bez
poziomu Lot nie ma rozbicia na transze ani stopów per lot**.

Ustawienia: **Period = Last Business Day**, **Format = XML**, Date Format
`yyyy-MM-dd`. Zapisz i zanotuj **Query ID**.

Potem **Flex Web Service Configuration** → włącz, wygeneruj **token**,
ogranicz go do IP serwera (`167.233.204.214`), ważność do roku.

## Uruchomienie na serwerze

```bash
bosman new ibkr        # albo ręcznie: /opt/ibkr + docker-compose.yml
```

W `/opt/ibkr/.env` (wzór w [.env.przyklad](.env.przyklad)) uzupełnij
`IBKR_TOKEN`, `IBKR_QUERY_ID`, `PANEL_HASLO`, `SECRET_KEY`.

Domyślnie pobranie odpala się **cztery razy dziennie, pon–pt**
(`GODZINY_POBRANIA=08:30,16:00,23:10,02:30`). Przycisk „Pobierz teraz" robi to
samo ręcznie.

Uwaga na oczekiwania: Flex generuje Activity Statement **raz na dobę**, więc
częstsze pobrania nie dadzą cen śróddziennych — dają odporność na nieudany
przebieg (token, timeout, przerwa u IBKR). Zrzut jest kluczowany datą raportu,
więc powtórka tego samego dnia nadpisuje wpis, a nie dokłada drugiego.

### Dane nie opuszczają serwera

Katalog `/opt/ibkr` zawiera plik **`.bez-kopii`**, przez co `bosman backup`
pomija cały stack — ani token, ani baza portfela nie trafiają do repo
backupów. To świadoma decyzja: dane finansowe zostają na maszynie. Backup
zrobisz ręcznie, jeśli będziesz chciał:

```bash
docker run --rm -v ibkr_ibkr_dane:/d -v "$PWD":/out alpine tar czf /out/portfel.tgz -C /d .
```

## Google Sheets (opcjonalne)

1. Google Cloud → nowy projekt → włącz **Google Sheets API**
2. utwórz **konto serwisowe**, pobierz klucz JSON
3. wgraj go na serwer jako `/dane/google-sa.json` w wolumenie `ibkr_dane`
4. udostępnij swój arkusz adresowi e-mail konta serwisowego (**Edytor**)
5. ustaw `GOOGLE_SHEET_ID` w `.env` (to fragment URL-a między `/d/` a `/edit`)

Push nadpisuje zakładkę o nazwie kwartału (`Q3_2026`). Bez konfiguracji
wszystko działa dalej — po prostu bez Sheets.

## Lokalnie

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
IBKR_TOKEN=... IBKR_QUERY_ID=... .venv/bin/python zadanie.py    # jedno pobranie
PANEL_HASLO=test COOKIE_SECURE=0 .venv/bin/python app.py        # panel na :8090
```

## Pliki

| Plik | Rola |
|---|---|
| `flex.py` | klient Flex Web Service + parser XML |
| `store.py` | SQLite: zrzuty dzienne, koszyki/stopy/oceny, log przebiegów |
| `statystyki.py` | wzbogacanie pozycji, koszyki, covered calls, podsumowanie |
| `raport_excel.py` | generator arkusza (openpyxl), jeden arkusz na kwartał |
| `sheets.py` | push do Google Sheets |
| `zadanie.py` | jeden przebieg: pobierz → zapisz → Excel → Sheets |
| `app.py` | panel Flask + harmonogram |
| `widok.py` | HTML panelu |
