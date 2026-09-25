import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

import { COUNTRY } from '@/config/country';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const summaryPath = path.join(process.cwd(), 'public', 'data', 'summary.json');

    if (!fs.existsSync(summaryPath)) {
      return NextResponse.json(
        { error: 'Summary data not available' },
        { status: 404 }
      );
    }

    const summaryData = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));

    // Per-carrier cache freshness, lifted out of statistics.json rather than
    // read from data/*_all_locations.json: those live outside webapp/, and this
    // keeps the ~150 KB statistics file server-side instead of shipping it.
    let bronnen = null;
    try {
      const statisticsPath = path.join(process.cwd(), 'public', 'data', 'statistics.json');
      bronnen = JSON.parse(fs.readFileSync(statisticsPath, 'utf-8')).bronnen ?? null;
    } catch {
      // Statistics not generated yet; the page just omits the section.
    }

    // Extract relevant update status information
    const updateStatus = {
      last_update: summaryData.generated_at,
      total_municipalities: summaryData.total_municipalities,
      successful_municipalities: summaryData.successful,
      failed_municipalities: summaryData.failed,
      carrier_stats: summaryData.carrier_stats || {},
      bronnen,
      // Link to GitHub Actions for detailed logs
      github_actions_url: `${COUNTRY.githubUrl}/actions/workflows/update-data.yml`
    };

    return NextResponse.json(updateStatus);
  } catch (error) {
    console.error('Error reading update status:', error);
    return NextResponse.json(
      { error: 'Failed to read update status' },
      { status: 500 }
    );
  }
}
