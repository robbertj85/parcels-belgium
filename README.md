# Pakketpunten België

Een systeem voor het **verzamelen, analyseren en visualiseren van pakketpunten in België**:
een Python-pipeline die wekelijks de locaties van alle grote vervoerders ophaalt, en een
Next.js-webapp met een interactieve kaart per gemeente.

Afgeleid van [Pakketpunten Nederland](https://github.com/robbertj85/pakketpunten) en
**landonafhankelijk** opgezet: dezelfde code bedient met een ander landprofiel ook
Italië (in voorbereiding). Zie [docs/NEW_COUNTRY.md](docs/NEW_COUNTRY.md).

**Disclaimer** — Dit project wordt geleverd "as is" zonder garantie. Data is verzameld van publieke
bronnen en kan onnauwkeurigheden bevatten. Dit project is niet gelieerd aan de databronbedrijven.

---

## Dekking

Alle **565 Belgische gemeenten** (na de fusies van 1 januari 2025), 10 provincies plus het
Brussels Hoofdstedelijk Gewest. Stand 26 september 2026: **19.030 punten op 7.906 unieke locaties**.

| Vervoerder | Bron | Locaties |
|------------|------|----------|
| bpost | Publieke locator (pudo.bpost.be) | ~4.400 (2.950 pakjesautomaten, 800 postpunten, 650 postkantoren) |
| DHL | Publieke REST API | ~4.400 (zelfde locaties als bpost) |
| GLS | Publieke parcelshop-API | ~1.900 (950 shops, 900 lockers) |
| InPost | Publieke REST API | ~1.300 (incl. voormalige Mondial Relay-punten) |
| Vinted Go | Web scraping | ~1.300 |
| PostNL | Publieke widget-API | ~1.100 |
| DPD | Publieke REST API | ~1.000 |
| Amazon | Browser-automatisering | ~3.500 (allemaal bpost-locaties; onvolledig, zie onder) |
| ViaTim | Publieke REST API | ~140 |

**DHL, Amazon en bpost**: in België gebruiken DHL Parcel en Amazon het bpost-netwerk. Elk
DHL-punt en elk gevonden Amazon-punt is een bpost-locatie. Ze staan alle drie op de kaart,
maar de statistieken tellen ook de **unieke locaties**: ~19.000 punten op ~7.900 fysieke adressen.

Amazon geeft maximaal 20 resultaten per zoekopdracht en in 482 van de 565 gemeenten zat de
zoekopdracht aan dat maximum; het echte aantal Amazon-punten ligt dus hoger.

### Moeilijk te verkrijgen

| Netwerk | Waarom niet (volledig) opgenomen |
|---|---|
| UPS Access Point | Locator-API vereist een ontwikkelaarsaccount (OAuth); website volledig JavaScript |
| Budbee | Geen publieke locatiezoeker, niet in DPD-data, vrijwel niet in OpenStreetMap |
| Mondial Relay | Eigen API vereist handelaarsgegevens; Belgische punten staan onder InPost |
| Cubee | Geen eigen API; Cubee-kluizen die bpost of GLS bedienen staan onder die vervoerders |
| DHL Express | API-sleutel vereist; overlapt met DHL Parcel |
| FedEx / TNT | Alleen via API met sleutel; klein netwerk |
| De Buren | Enkele Belgische locaties, niet betrouwbaar per gemeente |

Webshops en winkelketens (bol, Coolblue, Zalando, Delhaize, Carrefour, Shop&Go) zijn geen
eigen netwerk: ze versturen via of bieden ruimte aan de vervoerders hierboven.

---

## Gebruik

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium                 # alleen voor Amazon

python scripts/build_municipalities.py      # gemeentelijst + grenzen (OSM)
python scripts/fetch_all.py                 # alle vervoerders (Amazon ~50 min)
python scripts/batch_generate.py
python scripts/create_national_overview.py
python scripts/create_provincial_boundaries.py
python scripts/compute_statistics.py
python scripts/update_totals_history.py

cd webapp && npm install && npm run dev     # http://localhost:3000
```

Ander land: `PAKKETPUNTEN_COUNTRY=IT` voor de pipeline en `NEXT_PUBLIC_COUNTRY=IT` voor de webapp.

## Automatisering

- **`fetch-amazon-data.yml`** — dinsdag 00:00 UTC: Amazon via Playwright
- **`update-data.yml`** — dinsdag 02:00 UTC: alle andere vervoerders, gemeentebestanden,
  landelijk overzicht, provinciegrenzen, statistieken, historie; daarna de versheidscontrole

Beide lezen de repository-variabele `PAKKETPUNTEN_COUNTRY` (standaard `BE`).

## Technische details

| Component | Technologie |
|-----------|------------|
| Pipeline | Python 3.11+, GeoPandas, Shapely, Requests, Playwright |
| Webapp | Next.js 16, TypeScript, React, Leaflet, Tailwind CSS |
| Adreszoeken | Photon (OpenStreetMap), gemeente via punt-in-polygoon |
| Grenzen | OpenStreetMap (admin_level 8, NIS-codes) |
| Projectie | WGS84 voor alle I/O, Belgian Lambert 2008 (EPSG:3812) voor afstanden |
| CI/CD | GitHub Actions; hosting op Vercel |

## Licentie

MIT-licentie voor de **broncode**, niet voor de **data**.

### Data-attributie

```
Data bronnen:
- bpost (https://www.bpost.be)
- DHL Parcel (https://www.dhlparcel.com)
- GLS (https://gls-group.com)
- InPost / Mondial Relay (https://inpost.eu)
- Vinted Go (https://vintedgo.com)
- PostNL (https://www.postnl.be)
- DPD (https://www.dpd.com)
- Amazon Hub (https://www.amazon.com.be/ulp)
- ViaTim (https://viatim.be)
- Gemeentegrenzen en adreszoeken © OpenStreetMap contributors
- Inwonertallen: Wikidata / Statbel
```
