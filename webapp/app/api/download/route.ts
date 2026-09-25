import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

import { checkRateLimit, clientIp, rateLimitHeaders } from '@/lib/rateLimit';

import { t } from '@/lib/strings';
// Was 5/hour, which a single person comparing a handful of gemeenten could hit
// legitimately. 60 still stops bulk scraping; the whole dataset is a single
// GitHub clone away anyway.
const RATE_LIMIT = 60; // downloads per hour
const RATE_LIMIT_WINDOW = 60 * 60 * 1000; // 1 hour in milliseconds

function convertGeoJSONToCSV(geojson: any): string {
  const features = geojson.features.filter(
    (f: any) => f.properties.type === 'pakketpunt'
  );

  if (features.length === 0) {
    return t.map.noPointsTitle;
  }

  // CSV header
  const headers = [
    'locatieNaam',
    'straatNaam',
    'straatNr',
    'latitude',
    'longitude',
    'vervoerder',
    'puntType',
    'bezettingsgraad',
  ];

  const rows = features.map((feature: any) => {
    const props = feature.properties;
    const coords = feature.geometry.coordinates;

    return [
      props.locatieNaam || '',
      props.straatNaam || '',
      props.straatNr || '',
      coords[1], // latitude
      coords[0], // longitude
      props.vervoerder || '',
      props.puntType || '',
      props.bezettingsgraad || '',
    ]
      .map((value) => {
        // Escape CSV values
        const stringValue = String(value);
        if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
          return `"${stringValue.replace(/"/g, '""')}"`;
        }
        return stringValue;
      })
      .join(',');
  });

  return [headers.join(','), ...rows].join('\n');
}

export async function GET(request: NextRequest) {
  try {
    const limit = checkRateLimit(
      `download:${clientIp(request)}`,
      RATE_LIMIT,
      RATE_LIMIT_WINDOW
    );

    if (!limit.allowed) {
      return new NextResponse(
        `Rate limit exceeded. Maximum ${RATE_LIMIT} downloads per hour.`,
        {
          status: 429,
          headers: {
            'Retry-After': String(limit.retryAfterSeconds),
            ...rateLimitHeaders(limit),
          },
        }
      );
    }

    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const slug = searchParams.get('slug');
    const format = searchParams.get('format') as 'json' | 'csv';

    if (!slug || !format) {
      return new NextResponse('Missing slug or format parameter', { status: 400 });
    }

    if (format !== 'json' && format !== 'csv') {
      return new NextResponse('Invalid format. Use json or csv', { status: 400 });
    }

    // SECURITY: Validate slug to prevent path traversal attacks
    // Only allow lowercase letters, numbers, and hyphens
    if (!slug.match(/^[a-z0-9-]+$/)) {
      return new NextResponse('Invalid municipality slug', { status: 400 });
    }

    // Read the GeoJSON file
    const filePath = path.join(process.cwd(), 'public', 'data', `${slug}.geojson`);

    if (!fs.existsSync(filePath)) {
      return new NextResponse('Municipality not found', { status: 404 });
    }

    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const geojson = JSON.parse(fileContent);

    if (format === 'json') {
      // Return GeoJSON as-is
      return new NextResponse(fileContent, {
        headers: {
          'Content-Type': 'application/geo+json',
          'Content-Disposition': `attachment; filename="pakketpunten-${slug}.geojson"`,
        },
      });
    } else {
      // Convert to CSV
      const csv = convertGeoJSONToCSV(geojson);

      return new NextResponse(csv, {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': `attachment; filename="pakketpunten-${slug}.csv"`,
        },
      });
    }
  } catch (error) {
    console.error('Download error:', error);
    return new NextResponse('Internal server error', { status: 500 });
  }
}
