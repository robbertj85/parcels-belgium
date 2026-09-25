import { NextRequest, NextResponse } from 'next/server';

/**
 * Geocoding API proxy for Photon (komoot), an OpenStreetMap geocoder built for
 * search-as-you-type. Works for any country; results are limited to the active
 * country profile's bounding box and country code.
 *
 * The Dutch viewer used PDOK, which only covers the Netherlands. Nominatim's
 * usage policy forbids autocomplete, hence Photon.
 *
 * The municipality is not taken from the geocoder's address fields but found
 * by point-in-polygon against our own outlines (lib/municipalityLocator), so
 * the client gets a slug it can select directly.
 *
 * Benefits of using a proxy:
 * - Hides API details from client
 * - Bypasses CSP restrictions
 * - Allows server-side rate limiting
 * - Responses are cached (next: { revalidate })
 *
 *   ?q=<text>          suggestions
 *   ?id=<lat>,<lon>    details for a suggestion (ids are coordinates)
 *   ?lat=..&lon=..     reverse geocoding
 */

import { checkRateLimit, clientIp, rateLimitHeaders } from '@/lib/rateLimit';
import { locateMunicipality } from '@/lib/municipalityLocator';
import { COUNTRY } from '@/config/country';

const RATE_LIMIT = 60; // requests per minute
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute

const PHOTON_URL = 'https://photon.komoot.io';
const CACHE_SECONDS = 24 * 60 * 60;

interface PhotonProperties {
  name?: string;
  street?: string;
  housenumber?: string;
  postcode?: string;
  city?: string;
  district?: string;
  locality?: string;
  countrycode?: string;
  type?: string;
  osm_key?: string;
  osm_value?: string;
}

interface PhotonFeature {
  geometry: { coordinates: [number, number] };
  properties: PhotonProperties;
}

function displayName(p: PhotonProperties): string {
  const streetLine = [p.street, p.housenumber].filter(Boolean).join(' ');
  const place = [p.postcode, p.city || p.district || p.locality].filter(Boolean).join(' ');
  const parts = [p.name && p.name !== p.street ? p.name : null, streetLine || null, place || null];
  return parts.filter(Boolean).join(', ');
}

function resultType(p: PhotonProperties): string {
  if (p.housenumber) return 'adres';
  if (p.type === 'street') return 'weg';
  if (['city', 'town', 'village', 'district', 'locality'].includes(p.type ?? '')) return 'plaats';
  return p.type ?? 'adres';
}

async function photon(pathAndQuery: string): Promise<PhotonFeature[]> {
  const response = await fetch(`${PHOTON_URL}${pathAndQuery}`, {
    headers: { Accept: 'application/json', 'User-Agent': `${COUNTRY.siteName} (${COUNTRY.siteUrl})` },
    next: { revalidate: CACHE_SECONDS },
  });
  if (!response.ok) {
    throw new Error(`Photon API error: ${response.status}`);
  }
  const data = await response.json();
  return (data.features ?? []).filter(
    (f: PhotonFeature) => (f.properties.countrycode ?? '').toLowerCase() === COUNTRY.geocoderCountryCodes
  );
}

/** Address details plus our municipality for a coordinate. */
function details(lat: number, lon: number, p: PhotonProperties | null) {
  const municipality = locateMunicipality(lat, lon);
  return {
    id: `${lat},${lon}`,
    displayName: p ? displayName(p) : `${lat.toFixed(5)}, ${lon.toFixed(5)}`,
    municipality: municipality?.name ?? null,
    municipalitySlug: municipality?.slug ?? null,
    street: p?.street,
    houseNumber: p?.housenumber,
    postalCode: p?.postcode,
    city: p?.city || p?.district,
    coordinates: { latitude: lat, longitude: lon },
  };
}

function jsonError(status: number, error: string, message: string) {
  return new NextResponse(JSON.stringify({ error, message }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function parseCoordinate(value: string | null): number | null {
  if (value === null) return null;
  const number = parseFloat(value);
  return Number.isFinite(number) ? number : null;
}

export async function GET(request: NextRequest) {
  try {
    const limit = checkRateLimit(
      `geocode:${clientIp(request)}`,
      RATE_LIMIT,
      RATE_LIMIT_WINDOW
    );

    if (!limit.allowed) {
      return new NextResponse(
        JSON.stringify({
          error: 'Rate limit exceeded',
          message: `Maximum ${RATE_LIMIT} requests per minute`,
        }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(limit.retryAfterSeconds),
            ...rateLimitHeaders(limit),
          },
        }
      );
    }

    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get('q');
    const id = searchParams.get('id');
    const lat = searchParams.get('lat');
    const lon = searchParams.get('lon');

    if (!query && !id && !(lat && lon)) {
      return jsonError(400, 'Missing parameter', 'Provide "q" (query), "id" (lookup), or "lat"+"lon" (reverse)');
    }

    // Reverse geocoding (and lookups: a suggestion id is its coordinate)
    if ((lat && lon) || id) {
      const [latRaw, lonRaw] = id ? id.split(',') : [lat, lon];
      const latNum = parseCoordinate(latRaw ?? null);
      const lonNum = parseCoordinate(lonRaw ?? null);
      if (latNum === null || lonNum === null) {
        return jsonError(400, 'Invalid coordinates', 'Expected "<lat>,<lon>"');
      }

      const features = await photon(`/reverse?lat=${latNum}&lon=${lonNum}&limit=1`);
      const result = details(latNum, lonNum, features[0]?.properties ?? null);

      if (!result.municipalitySlug) {
        return jsonError(404, 'Not found', `No ${COUNTRY.name} municipality at this location`);
      }
      return NextResponse.json(result);
    }

    // Suggestions (autocomplete)
    const [minLon, minLat, maxLon, maxLat] = COUNTRY.bbox;
    const features = await photon(
      `/api/?q=${encodeURIComponent(query!)}&limit=10&bbox=${minLon},${minLat},${maxLon},${maxLat}`
    );

    const results = features.map((f, rank) => {
      const [lonNum, latNum] = f.geometry.coordinates;
      return {
        id: `${latNum},${lonNum}`,
        displayName: displayName(f.properties),
        type: resultType(f.properties),
        municipality: locateMunicipality(latNum, lonNum)?.name ?? f.properties.city,
        score: features.length - rank,
      };
    });

    return NextResponse.json({ query, results });
  } catch (error) {
    console.error('Geocoding error:', error);
    return jsonError(500, 'Internal server error', 'Failed to fetch geocoding results');
  }
}
