import fs from 'fs';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';

import { checkRateLimit, clientIp, rateLimitHeaders } from '@/lib/rateLimit';

/**
 * GET /api/v1/municipalities
 *
 * Lists every municipality with its slug, official code, province, population and
 * current pakketpunt count — the index you need before you can call the
 * per-municipality endpoint, which until now could only be used by guessing
 * slugs.
 *
 * Counts come from the batch summary, including the per-carrier split, so a
 * consumer can pick the gemeenten it cares about without downloading 343
 * GeoJSON files first.
 */

const RATE_LIMIT = 60;
const RATE_WINDOW_MS = 60 * 60 * 1000;

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

interface Municipality {
  name: string;
  slug: string;
  province: string;
  population: number | null;
  code: string | null;
}

interface SummaryResult {
  slug: string;
  count: number;
  carrier_status?: Record<string, { count: number }>;
}

export async function GET(request: NextRequest) {
  const limit = checkRateLimit(
    `api-v1-list:${clientIp(request)}`,
    RATE_LIMIT,
    RATE_WINDOW_MS
  );

  if (!limit.allowed) {
    return NextResponse.json(
      { error: 'Rate limit exceeded', message: `Maximum ${RATE_LIMIT} requests per hour` },
      {
        status: 429,
        headers: {
          ...CORS_HEADERS,
          'Retry-After': String(limit.retryAfterSeconds),
          ...rateLimitHeaders(limit),
        },
      }
    );
  }

  const publicDir = path.join(process.cwd(), 'public');
  const indexPath = path.join(publicDir, 'municipalities.json');

  if (!fs.existsSync(indexPath)) {
    return NextResponse.json(
      { error: 'Municipality index not available' },
      { status: 500, headers: CORS_HEADERS }
    );
  }

  const municipalities: Municipality[] = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));

  // Point counts come from the batch summary; a missing summary is not fatal,
  // the index is still useful without them.
  const counts = new Map<string, number>();
  const carriers = new Map<string, Record<string, number>>();

  const summaryPath = path.join(publicDir, 'data', 'summary.json');
  if (fs.existsSync(summaryPath)) {
    try {
      const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));
      for (const result of (summary.results ?? []) as SummaryResult[]) {
        counts.set(result.slug, result.count);

        if (result.carrier_status) {
          const perCarrier: Record<string, number> = {};
          for (const [carrier, status] of Object.entries(result.carrier_status)) {
            perCarrier[carrier] = status.count;
          }
          carriers.set(result.slug, perCarrier);
        }
      }
    } catch {
      // Fall through with empty maps.
    }
  }

  const payload = municipalities.map((municipality) => ({
    ...municipality,
    total_points: counts.get(municipality.slug) ?? null,
    carriers: carriers.get(municipality.slug) ?? null,
    url: `/api/v1/municipality/${municipality.slug}`,
  }));

  return NextResponse.json(
    { total: payload.length, municipalities: payload },
    {
      headers: {
        ...CORS_HEADERS,
        'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
        ...rateLimitHeaders(limit),
      },
    }
  );
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: { ...CORS_HEADERS, 'Access-Control-Max-Age': '86400' },
  });
}
