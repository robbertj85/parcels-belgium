import { promises as fs } from 'fs';
import path from 'path';
import DataMatrixClient from '@/components/DataMatrixClient';
import { HistoryData } from '@/types/history';

import { COUNTRY } from '@/config/country';
interface ProviderCounts {
  [provider: string]: number;
}

interface MunicipalityData {
  name: string;
  slug: string;
  providers: ProviderCounts;
  total: number;
}

async function getMunicipalityData(): Promise<MunicipalityData[]> {
  const dataDir = path.join(process.cwd(), 'public', 'data');
  const files = await fs.readdir(dataDir);
  const geojsonFiles = files.filter(f => f.endsWith('.geojson'));

  const municipalityData: MunicipalityData[] = [];

  for (const file of geojsonFiles) {
    try {
      const filePath = path.join(dataDir, file);
      const content = await fs.readFile(filePath, 'utf-8');
      const data = JSON.parse(content);

      // Extract pakketpunt features only
      const pakketpunten = data.features.filter(
        (f: any) => f.properties?.type === 'pakketpunt'
      );

      // Count by provider
      const providerCounts: ProviderCounts = {};
      pakketpunten.forEach((feature: any) => {
        const provider = feature.properties?.vervoerder || 'Unknown';
        providerCounts[provider] = (providerCounts[provider] || 0) + 1;
      });

      municipalityData.push({
        name: data.metadata.gemeente,
        slug: data.metadata.slug || file.replace('.geojson', ''),
        providers: providerCounts,
        total: pakketpunten.length,
      });
    } catch (error) {
      console.error(`Error reading ${file}:`, error);
    }
  }

  // Sort by municipality name, but put the national row at the top
  return municipalityData.sort((a, b) => {
    if (a.slug === COUNTRY.nationalSlug) return -1;
    if (b.slug === COUNTRY.nationalSlug) return 1;
    return a.name.localeCompare(b.name);
  });
}

async function getHistoryData(): Promise<HistoryData | null> {
  try {
    const historyPath = path.join(process.cwd(), 'public', 'data', 'totals_history.json');
    const content = await fs.readFile(historyPath, 'utf-8');
    return JSON.parse(content) as HistoryData;
  } catch (error) {
    console.error('Error reading totals_history.json:', error);
    return null;
  }
}

export default async function DataMatrixPage() {
  const [data, historyData] = await Promise.all([
    getMunicipalityData(),
    getHistoryData()
  ]);

  // Get all unique providers
  const allProviders = new Set<string>();
  data.forEach(m => {
    Object.keys(m.providers).forEach(p => allProviders.add(p));
  });
  const providers = Array.from(allProviders).sort();

  // Calculate totals per provider (excluding the national row to avoid double-counting)
  const municipalitiesOnly = data.filter(m => m.slug !== COUNTRY.nationalSlug);
  const providerTotals: ProviderCounts = {};
  providers.forEach(provider => {
    providerTotals[provider] = municipalitiesOnly.reduce((sum, m) => sum + (m.providers[provider] || 0), 0);
  });
  const grandTotal = municipalitiesOnly.reduce((sum, m) => sum + m.total, 0);

  return (
    <DataMatrixClient
      data={data}
      providers={providers}
      providerTotals={providerTotals}
      grandTotal={grandTotal}
      historyData={historyData}
    />
  );
}
