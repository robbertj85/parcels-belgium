/**
 * The single source of truth for carriers: order, series colours, brand chrome.
 *
 * This replaces four near-identical inline tables (Map, NearestPointsFinder and
 * the three history modals). They had drifted: GLS was drawn navy in one place
 * and yellow in another, and — worse — DHL (#FFCC00) and InPost (#FFCD00) were
 * one step apart in the green channel, which is to say identical. Both appeared
 * in the same pie and the same ten-line chart.
 *
 * ## Two kinds of colour, deliberately kept apart
 *
 * `brand` is the carrier's real livery. It is used only where a logo sits on
 * top of it — the map pins. There the logo carries identity and the colour is
 * decoration, so brand accuracy costs nothing.
 *
 * `series` is a validated categorical palette used everywhere identity comes
 * from colour alone: charts, legends and the bare circle markers the map falls
 * back to above ~3000 points. Real brand colours cannot do this job. Ten
 * liveries include three near-identical yellows and two oranges; no amount of
 * care makes them separable.
 *
 * ## How the series palette was chosen
 *
 * A fixed sequence of ten hue slots, validated with the dataviz validator
 * against the *adjacent* pairlist (the relevant one for lines, bars and
 * stacks). Carriers take slots by their position in the country's carrier list
 * (config/countries.ts), so any country with up to ten carriers uses a prefix
 * of this sequence, and a prefix of a passing adjacent sequence passes too.
 * Checked for the Belgian nine:
 *
 *   light  worst adjacent CVD ΔE 7.2 (green↔red, protan; tritan 26.6)
 *          worst adjacent normal-vision ΔE 27.6 — passes the ≥15 floor
 *   dark   worst adjacent CVD ΔE 8.6 · worst normal-vision ΔE 23.8 — all pass
 *
 * Light-mode CVD lands in the 6–8 band, which is permissible **only with
 * secondary encoding**. That is not optional here: every chart using these
 * colours must also carry a legend and direct labels.
 *
 * The order is fixed per country and follows carrier size. Do not sort it by
 * the current filter: colour must follow the carrier, never its rank, or
 * filtering repaints the survivors. The same carrier can get a different hue
 * in another country's viewer; brand colours live in CARRIER_CATALOG.
 *
 * Under the *all-pairs* gate (any two series compared directly — a pie, a
 * scatter) nine series cannot pass at all, and neither can eight. Charts of that
 * shape need a different form, not a different palette; see the market-share
 * chart, which is a ranked bar for exactly this reason.
 */

import { COUNTRY } from '@/config/country';

/** Carrier keys as they appear in `vervoerder` in the data. */
export type Carrier = string;

interface CarrierBrand {
  /** Display name. */
  label: string;
  /** Livery colour, only for use behind a logo. */
  background: string;
  /** Optional second livery colour, used as a pin border. */
  borderColor?: string;
  logoUrl: string;
  /** Where the data comes from, for the About modal and attribution. */
  source: {
    name: string;
    endpoint: string;
    method: 'Publieke API' | 'Web scraping' | 'Browser-automatisering';
    url: string;
  };
}

/**
 * Every carrier any country profile can show. Real brand liveries — map pins
 * only, where the logo carries identity. A new country's carrier gets an entry
 * here plus a logo in public/logos/.
 */
export const CARRIER_CATALOG: Record<string, CarrierBrand> = {
  bpost: {
    label: 'bpost', background: '#EF2637', logoUrl: '/logos/bpost.svg',
    source: { name: 'bpost (postkantoren, postpunten, pakjesautomaten)', endpoint: 'pudo.bpost.be/Locator', method: 'Publieke API', url: 'https://www.bpost.be' },
  },
  DHL: {
    label: 'DHL', background: '#FFCC00', borderColor: '#D40511', logoUrl: '/logos/dhl.svg',
    source: { name: 'DHL Parcel ServicePoints', endpoint: 'api-gw.dhlparcel.nl/parcel-shop-locations', method: 'Publieke API', url: 'https://www.dhlparcel.com' },
  },
  GLS: {
    label: 'GLS', background: '#FFC600', borderColor: '#003C7E', logoUrl: '/logos/gls.svg',
    source: { name: 'GLS ParcelShops & Parcel Lockers', endpoint: 'api.gls-group.net/parcel-shop-management', method: 'Publieke API', url: 'https://gls-group.com' },
  },
  InPost: {
    label: 'InPost', background: '#FFCD00', borderColor: '#3B3B3B', logoUrl: '/logos/inpost.svg',
    source: { name: 'InPost / Mondial Relay', endpoint: 'api-global-points.easypack24.net/v1/points', method: 'Publieke API', url: 'https://inpost.eu' },
  },
  VintedGo: {
    label: 'Vinted Go', background: '#09B1BA', logoUrl: '/logos/vintedgo.svg',
    source: { name: 'Vinted Go', endpoint: 'vintedgo.com/nl/carrier-locations', method: 'Web scraping', url: 'https://vintedgo.com' },
  },
  PostNL: {
    label: 'PostNL', background: '#FF6600', logoUrl: '/logos/postnl.svg',
    source: { name: 'PostNL', endpoint: 'productprijslokatie.postnl.nl/location-widget', method: 'Publieke API', url: 'https://www.postnl.be' },
  },
  DPD: {
    label: 'DPD', background: '#DC0032', logoUrl: '/logos/dpd.svg',
    source: { name: 'DPD Pickup', endpoint: 'pickup.dpd.cz/api/getAll', method: 'Publieke API', url: 'https://www.dpd.com' },
  },
  Amazon: {
    label: 'Amazon', background: '#FF9900', borderColor: '#146EB4', logoUrl: '/logos/amazon.svg',
    source: { name: 'Amazon Hub (Lockers & Counters)', endpoint: `${COUNTRY.amazonDomain}/ulp`, method: 'Browser-automatisering', url: `https://${COUNTRY.amazonDomain}/ulp` },
  },
  ViaTim: {
    label: 'ViaTim', background: '#E3007A', logoUrl: '/logos/viatim.svg',
    source: { name: 'ViaTim', endpoint: 'production.viapunt-api.viatim.nl/public/servicepoints', method: 'Publieke API', url: 'https://viatim.be' },
  },
  PosteItaliane: {
    label: 'Poste Italiane', background: '#FFD100', borderColor: '#0047BB', logoUrl: '/logos/posteitaliane.svg',
    source: { name: 'Poste Italiane (Uffici Postali, Punto Poste, Locker)', endpoint: 'mapcollection.poste.it/v2/map', method: 'Publieke API', url: 'https://www.poste.it' },
  },
};

/** Validated hue slots, light surface. */
const SERIES_SLOTS_LIGHT = [
  '#2a78d6', // blue
  '#eb6834', // orange
  '#1baf7a', // aqua
  '#4a3aa7', // violet
  '#eda100', // yellow
  '#0e8f9e', // teal
  '#e34948', // red
  '#008300', // green
  '#e87ba4', // magenta
  '#a1541f', // rust
];

/** The same ten hues stepped for a dark surface — not an automatic flip. */
const SERIES_SLOTS_DARK = [
  '#3987e5',
  '#d95926',
  '#199e70',
  '#9085e9',
  '#c98500',
  '#0f93a6',
  '#e66767',
  '#008300',
  '#d55181',
  '#c08430',
];

for (const carrier of COUNTRY.carriers) {
  if (!CARRIER_CATALOG[carrier]) {
    throw new Error(`Carrier "${carrier}" in the ${COUNTRY.code} profile is missing from CARRIER_CATALOG`);
  }
}
if (COUNTRY.carriers.length > SERIES_SLOTS_LIGHT.length) {
  // An 11th series is never a generated hue; fold small carriers into "Overig" instead.
  throw new Error(`At most ${SERIES_SLOTS_LIGHT.length} carriers per country; ${COUNTRY.code} has ${COUNTRY.carriers.length}`);
}

/** This country's carriers, in fixed order. */
export const CARRIER_ORDER: readonly Carrier[] = COUNTRY.carriers;

function bySlot(slots: string[]): Record<Carrier, string> {
  return Object.fromEntries(CARRIER_ORDER.map((carrier, i) => [carrier, slots[i]]));
}

/** Validated categorical palette, in CARRIER_ORDER. Light surface. */
export const CARRIER_SERIES_COLORS: Record<Carrier, string> = bySlot(SERIES_SLOTS_LIGHT);

/** Dark-surface counterpart of CARRIER_SERIES_COLORS. */
export const CARRIER_SERIES_COLORS_DARK: Record<Carrier, string> = bySlot(SERIES_SLOTS_DARK);

/** Display names. */
export const CARRIER_LABELS: Record<Carrier, string> = Object.fromEntries(
  Object.entries(CARRIER_CATALOG).map(([key, brand]) => [key, brand.label])
);

/** Real brand liveries for this country's carriers — map pins only. */
export const CARRIER_BRAND: Record<Carrier, CarrierBrand> = Object.fromEntries(
  CARRIER_ORDER.map((carrier) => [carrier, CARRIER_CATALOG[carrier]])
);

/** Series colour for a carrier, falling back to a neutral for unknown names. */
export function carrierColor(name: string): string {
  return CARRIER_SERIES_COLORS[name] ?? '#888888';
}

export function isKnownCarrier(name: string): name is Carrier {
  return name in CARRIER_SERIES_COLORS;
}

/**
 * Logo path for a carrier, or null when the name is not one we know.
 *
 * The history panels fall back to a colour swatch with the first two letters,
 * so a null here is a rendering choice rather than a missing asset.
 */
export function carrierLogo(name: string): string | null {
  return CARRIER_CATALOG[name]?.logoUrl ?? null;
}
