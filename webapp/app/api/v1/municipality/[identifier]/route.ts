import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

import { checkRateLimit, clientIp, rateLimitHeaders } from '@/lib/rateLimit';
import { COUNTRY } from '@/config/country';

const RATE_LIMIT = 60; // requests per window
const RATE_LIMIT_WINDOW = 60 * 60 * 1000; // 1 hour in milliseconds

interface Municipality {
  name: string;
  slug: string;
  province: string;
  population: number;
  code: string | null;
  /** Other-language and alternative names, from scripts/build_municipalities.py. */
  aliases?: string[];
}

function normalizeIdentifier(identifier: string): string {
  return identifier.toLowerCase().trim();
}

function findMunicipalityByIdentifier(
  municipalities: Municipality[],
  identifier: string
): Municipality | null {
  const normalized = normalizeIdentifier(identifier);

  // Try exact slug match (fastest)
  let match = municipalities.find((m) => m.slug === normalized);
  if (match) return match;

  // Try alias match (e.g., "Luik" or "Lüttich" -> Liège)
  match = municipalities.find((m) =>
    (m.aliases ?? []).some((alias) => normalizeIdentifier(alias) === normalized)
  );
  if (match) return match;

  // Try official code match (NIS in Belgium, ISTAT in Italy)
  match = municipalities.find((m) => {
    if (!m.code) return false;
    const cleanCode = m.code.trim();
    return cleanCode.toLowerCase() === normalized;
  });
  if (match) return match;

  // Try municipality name match (case-insensitive)
  match = municipalities.find(
    (m) => normalizeIdentifier(m.name) === normalized
  );
  if (match) return match;

  // Try fuzzy matching: remove special characters and spaces
  // This helps with variations like "s-Hertogenbosch" vs "'s-Hertogenbosch"
  const fuzzyNormalized = normalized.replace(/[''\-\s().]/g, '');
  match = municipalities.find((m) => {
    const fuzzyName = m.name.toLowerCase().replace(/[''\-\s().]/g, '');
    const fuzzySlug = m.slug.replace(/[''\-\s().]/g, '');
    return fuzzyName === fuzzyNormalized || fuzzySlug === fuzzyNormalized;
  });
  if (match) return match;

  return null;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ identifier: string }> }
) {
  try {
    const limit = checkRateLimit(
      `api-v1-municipality:${clientIp(request)}`,
      RATE_LIMIT,
      RATE_LIMIT_WINDOW
    );

    if (!limit.allowed) {
      return new NextResponse(
        JSON.stringify({
          error: 'Rate limit exceeded',
          message: `Maximum ${RATE_LIMIT} requests per hour`,
        }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(limit.retryAfterSeconds),
            ...rateLimitHeaders(limit),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
          },
        }
      );
    }

    // Get identifier from path params
    const { identifier } = await context.params;

    if (!identifier) {
      return new NextResponse(
        JSON.stringify({
          error: 'Missing identifier',
          message: `Please provide a municipality identifier (name, slug, or ${COUNTRY.municipalityCodeLabel} code)`,
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    // Load municipalities metadata
    const municipalitiesPath = path.join(
      process.cwd(),
      'public',
      'municipalities.json'
    );

    if (!fs.existsSync(municipalitiesPath)) {
      return new NextResponse(
        JSON.stringify({
          error: 'Municipalities data not found',
        }),
        {
          status: 500,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    const municipalities: Municipality[] = JSON.parse(
      fs.readFileSync(municipalitiesPath, 'utf-8')
    );

    // Find municipality by identifier
    const municipality = findMunicipalityByIdentifier(municipalities, identifier);

    if (!municipality) {
      return new NextResponse(
        JSON.stringify({
          error: 'Municipality not found',
          message: `No municipality found for identifier: "${identifier}"`,
          hint: `Try using a municipality name, slug (e.g., "${COUNTRY.defaultMunicipalitySlug}"), or ${COUNTRY.municipalityCodeLabel} code (e.g., "${COUNTRY.municipalityCodeExample}")`,
        }),
        {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    // Skip the national row - it's not a real municipality
    if (municipality.slug === COUNTRY.nationalSlug) {
      return new NextResponse(
        JSON.stringify({
          error: 'Invalid municipality',
          message: 'National overview data is not available via the API. Please use individual municipality endpoints.',
        }),
        {
          status: 400,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    // Read the GeoJSON file
    const filePath = path.join(
      process.cwd(),
      'public',
      'data',
      `${municipality.slug}.geojson`
    );

    if (!fs.existsSync(filePath)) {
      return new NextResponse(
        JSON.stringify({
          error: 'Data not found',
          message: `Data file for municipality "${municipality.name}" does not exist`,
        }),
        {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        }
      );
    }

    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const geojson = JSON.parse(fileContent);

    // Return GeoJSON with proper headers
    return new NextResponse(JSON.stringify(geojson, null, 2), {
      headers: {
        'Content-Type': 'application/geo+json',
        'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'X-RateLimit-Limit': String(RATE_LIMIT),
        'X-Municipality-Name': municipality.name,
        'X-Municipality-Slug': municipality.slug,
        'X-Municipality-Code': municipality.code || 'N/A',
      },
    });
  } catch (error) {
    console.error('API error:', error);
    return new NextResponse(
      JSON.stringify({
        error: 'Internal server error',
        message: 'An unexpected error occurred while processing your request',
      }),
      {
        status: 500,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  }
}

// Handle OPTIONS for CORS preflight
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
    },
  });
}
