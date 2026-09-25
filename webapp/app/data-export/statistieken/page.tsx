import fs from 'fs/promises';
import path from 'path';

import StatisticsClient, { StatisticsPayload } from '@/components/StatisticsClient';
import { HistoryData } from '@/types/history';

import { t } from '@/lib/strings';
export const metadata = {
  title: t.statistics.metaTitle,
  description: t.statistics.metaDescription,
};

async function loadJson<T>(filename: string): Promise<T | null> {
  try {
    const filePath = path.join(process.cwd(), 'public', 'data', filename);
    return JSON.parse(await fs.readFile(filePath, 'utf-8')) as T;
  } catch {
    return null;
  }
}

/**
 * Carrier names, from the history rather than the GeoJSON.
 *
 * The Data Matrix derives this from the per-municipality files and sorts
 * alphabetically; taking the union of keys across every snapshot gives the same
 * set without reading 342 files, and keeps a carrier that has since dropped to
 * zero in the list so its history stays inspectable.
 */
function providersFromHistory(history: HistoryData | null): string[] {
  const names = new Set<string>();
  history?.snapshots.forEach((snapshot) => {
    Object.keys(snapshot.totals.providers).forEach((name) => names.add(name));
  });
  return Array.from(names).sort();
}

export default async function StatisticsPage() {
  const [statistics, history] = await Promise.all([
    loadJson<StatisticsPayload>('statistics.json'),
    loadJson<HistoryData>('totals_history.json'),
  ]);

  if (!statistics) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center">
        <p className="text-sm text-muted-foreground">
          {t.statistics.noStatistics}{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">
            python scripts/compute_statistics.py
          </code>
          .
        </p>
      </div>
    );
  }

  return (
    <StatisticsClient
      statistics={statistics}
      snapshots={history?.snapshots ?? []}
      providers={providersFromHistory(history)}
    />
  );
}
