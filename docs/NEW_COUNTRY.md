# Een land toevoegen

De code is landonafhankelijk; alles wat per land verschilt zit in twee profielen
die elkaar spiegelen. Per land draait één repository (of fork) met één Vercel-project:
de data-bestanden in `data/` en `webapp/public/data/` zijn van één land.

## 1. Pipeline-profiel: `country_config.py`

Voeg een blok toe aan `COUNTRIES`:

| Sleutel | Wat | BE | IT |
|---|---|---|---|
| `iso2`, `iso3`, `iso_numeric` | landcodes | BE, BEL, 56 | IT, ITA, 380 |
| `national_slug` | bestandsnaam van het landelijk overzicht | `belgie` | `italia` |
| `metric_crs` | metrische projectie voor buffers en oppervlakte | 3812 (Lambert 2008) | 6875 (RDN2008 Italy zone) |
| `bbox` | (south, west, north, east) in WGS84 | | |
| `boundaries.admin_level` | OSM-niveau van gemeenten | 8 | 8 |
| `boundaries.code_tag` | OSM-tag met de officiële code | `ref:INS` | `ref:ISTAT` |
| `boundaries.fetch` | `national` (één query) of `per_region` (groot aantal gemeenten) | national | per_region |
| `boundaries.region_resolver` | `be_nis` of `spatial` (regio waarin de gemeente ligt) | be_nis | spatial |
| `carriers` | vervoerders, vaste volgorde (bepaalt de grafiekkleuren) | | |
| per vervoerder | parameters voor de fetchers (`dhl`, `dpd`, `inpost`, `gls`, `amazon`, ...) | | |

Het land kies je met `PAKKETPUNTEN_COUNTRY` (standaard `BE`). In GitHub Actions
is dat de repository-variabele `PAKKETPUNTEN_COUNTRY`.

## 2. Webapp-profiel: `webapp/config/countries.ts`

Zelfde land, zelfde `nationalSlug` en dezelfde `carriers` in dezelfde volgorde.
Verder: locale, sitenaam en -URL, standaardgemeente en kaartcentrum, naam van
de regio-laag (provincie/regione), label van de gemeentecode, de metrische
projectie (`metricCrsLabel`, gelijk aan `metric_crs` in de pipeline), `bbox` en
`geocoderCountryCodes` voor adreszoeken, de Amazon-winkel, de lijst
**moeilijk te verkrijgen netwerken** (`missingCarriers`, getoond in Over → Bronnen)
en links voor Over → Links.

Het profiel kies je met `NEXT_PUBLIC_COUNTRY` (Vercel env var; standaard `BE`).
De taal van de interface volgt uit `language`; een nieuwe taal is een extra
woordenboek in `webapp/lib/strings.ts` met dezelfde vorm als `nl`.

## 3. Vervoerders

- Vervoerders die al bestaan (DHL, DPD, InPost, GLS, Amazon, PostNL, VintedGo,
  ViaTim, bpost) nemen hun land uit het profiel. Controleer per land of de
  endpoint het land ondersteunt (zie de tabel in het plan).
- Een nieuwe vervoerder krijgt:
  1. `scripts/<vervoerder>_fetch_all.py` (kleine letters) dat
     `data/<vervoerder>_all_locations.json` schrijft via `cache_guard.safe_save`,
     in het gedeelde schema (`locatieNaam, straatNaam, straatNr, latitude,
     longitude, puntType, canPickup, canDropoff, openingstijden`). Zie
     `bpost_fetch_all.py` als voorbeeld.
  2. Een entry in `CARRIER_CATALOG` in `webapp/lib/carriers.ts` (label, huiskleur,
     logo, bron) en een logo in `webapp/public/logos/`.
  3. Een pakketautomaat-`puntType` die nog niet bestaat: toevoegen aan
     `LOCKER_TYPES` in `webapp/types/pakketpunten.ts` én `scripts/compute_statistics.py`.

`scripts/fetch_all.py` draait automatisch elke fetcher uit de lijst van het land.

Maximaal tien vervoerders per land: de grafiekkleuren zijn tien gevalideerde
tinten op volgorde (zie de toelichting boven in `webapp/lib/carriers.ts`).

## 4. Gemeenten en grenzen

```bash
PAKKETPUNTEN_COUNTRY=IT python scripts/build_municipalities.py
```

Schrijft `data/municipalities_all.json`, `data/municipality_polygons.geojson`,
`webapp/public/municipalities.json` en de webapp-kopie van de grenzen
(`webapp/public/data/geo/`, voor adreszoeken). Een ander land met eigen
naamregels krijgt een hook in `display_name()`.

## 5. Draaien

```bash
export PAKKETPUNTEN_COUNTRY=IT
python scripts/fetch_all.py              # alle caches (Amazon duurt lang)
python scripts/batch_generate.py
python scripts/create_national_overview.py
python scripts/create_provincial_boundaries.py
python scripts/compute_statistics.py
python scripts/update_totals_history.py
cd webapp && NEXT_PUBLIC_COUNTRY=IT npm run dev
```

## Nog te doen voor Italië

- `scripts/posteitaliane_fetch_all.py` (Poste Italiane: `mapcollection.poste.it/v2/map/geoListByComune`,
  20 resultaten per pagina, per comune).
- UI-teksten staan in `webapp/lib/strings.ts` (Nederlands en Italiaans; het
  profielveld `language` kiest). De Italiaanse vertaling is nog niet nagelezen
  door een moedertaalspreker.
- ~7.900 comuni: `batch_generate.py` parallel maken en letten op het aantal
  bestanden en de repo-grootte.
