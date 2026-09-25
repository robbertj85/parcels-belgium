'use client';

import { useState } from 'react';
import TrendIndicator from './TrendIndicator';
import MunicipalityHistoryModal from './MunicipalityHistoryModal';
import ProviderHistoryModal from './ProviderHistoryModal';
import TotalOverviewModal from './TotalOverviewModal';
import { HistoryData, MunicipalityHistoryEntry, HistorySnapshot } from '@/types/history';

import { COUNTRY } from '@/config/country';
import { t } from '@/lib/strings';
interface ProviderCounts {
  [provider: string]: number;
}

interface MunicipalityData {
  name: string;
  slug: string;
  providers: ProviderCounts;
  total: number;
}

interface DataMatrixClientProps {
  data: MunicipalityData[];
  providers: string[];
  providerTotals: ProviderCounts;
  grandTotal: number;
  historyData: HistoryData | null;
}

export default function DataMatrixClient({
  data,
  providers,
  providerTotals,
  grandTotal,
  historyData
}: DataMatrixClientProps) {
  const [selectedMunicipality, setSelectedMunicipality] = useState<{
    name: string;
    slug: string;
    history: MunicipalityHistoryEntry[];
  } | null>(null);

  const [selectedProvider, setSelectedProvider] = useState<{
    name: string;
    snapshots: HistorySnapshot[];
  } | null>(null);

  const [showTotalOverview, setShowTotalOverview] = useState(false);

  // Get trend data
  const trend = historyData?.trend;
  const snapshots = historyData?.snapshots || [];
  const latestSnapshot = snapshots[snapshots.length - 1];
  const previousSnapshot = snapshots[snapshots.length - 2];

  // Calculate municipality-level trends
  const getMunicipalityTrend = (slug: string): number | null => {
    if (!historyData?.municipalities[slug]) return null;
    const history = historyData.municipalities[slug].history;
    if (history.length < 2) return null;
    const latest = history[history.length - 1];
    const previous = history[history.length - 2];
    return latest.total - previous.total;
  };

  const handleMunicipalityClick = (municipality: MunicipalityData) => {
    const history = historyData?.municipalities[municipality.slug]?.history || [];
    if (history.length > 0) {
      setSelectedMunicipality({
        name: municipality.name,
        slug: municipality.slug,
        history
      });
    }
  };

  const handleProviderClick = (providerName: string) => {
    if (snapshots.length > 0) {
      setSelectedProvider({
        name: providerName,
        snapshots: snapshots
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Stats with Trends */}
      <div className="bg-card rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-foreground">{t.matrix.overviewTitle}</h2>
          {latestSnapshot && (
            <span className="text-xs text-subtle-foreground">
              {t.matrix.lastUpdate(new Date(latestSnapshot.date).toLocaleDateString(COUNTRY.locale))}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-4 bg-accent rounded-lg">
            <div className="text-2xl font-bold text-accent-foreground">{data.length}</div>
            <div className="text-sm text-primary">{t.matrix.locations}</div>
          </div>
          <div
            className="group text-center p-4 bg-success-muted rounded-lg cursor-pointer hover:bg-success-muted hover:shadow-md transition-all"
            onClick={() => snapshots.length > 0 && setShowTotalOverview(true)}
          >
            <div className="text-2xl font-bold text-success">{grandTotal.toLocaleString(COUNTRY.locale)}</div>
            <div className="text-sm text-success">{t.matrix.totalPoints}</div>
            {trend && (
              <div className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <TrendIndicator change={trend.change.total} label={t.matrix.trendWeekLabel} />
              </div>
            )}
          </div>
          {providers.map(provider => (
            <div
              key={provider}
              className="group text-center p-4 bg-muted rounded-lg cursor-pointer hover:bg-secondary hover:shadow-md transition-all"
              onClick={() => handleProviderClick(provider)}
            >
              <div className="text-2xl font-bold text-foreground">{providerTotals[provider].toLocaleString(COUNTRY.locale)}</div>
              <div className="text-sm text-muted-foreground">{provider}</div>
              {trend?.change.providers[provider] !== undefined && (
                <div className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <TrendIndicator change={trend.change.providers[provider]} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Historical trend summary - visible on hover */}
        {snapshots.length > 1 && (
          <div className="group mt-4 pt-4 border-t border-border cursor-default">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between text-sm gap-2">
              <span className="text-muted-foreground">
                {t.matrix.trendSummary(snapshots.length, snapshots[0].week_label)}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-foreground font-medium">
                  {snapshots[0].totals.total.toLocaleString(COUNTRY.locale)} → {latestSnapshot?.totals.total.toLocaleString(COUNTRY.locale)}
                </span>
                {latestSnapshot && (
                  <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                    <TrendIndicator
                      change={latestSnapshot.totals.total - snapshots[0].totals.total}
                      label={t.matrix.trendTotalLabel}
                    />
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Data Matrix Table */}
      <div className="bg-card rounded-lg shadow-md overflow-hidden">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-bold text-foreground">{t.matrix.tableTitle}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t.matrix.tableHint}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted border-b border-border">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider sticky left-0 bg-muted z-10">
                  {t.matrix.colMunicipality}
                </th>
                <th className="px-1 py-3 bg-muted w-8">
                  <span className="sr-only">{t.matrix.dashboard}</span>
                </th>
                {providers.map(provider => (
                  <th
                    key={provider}
                    className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-secondary transition-colors"
                    onClick={() => handleProviderClick(provider)}
                  >
                    {provider}
                  </th>
                ))}
                <th className="px-4 py-3 text-center text-xs font-semibold text-foreground uppercase tracking-wider bg-secondary">
                  {t.matrix.total}
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {t.matrix.trend}
                </th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {data.map((municipality) => {
                const trend = getMunicipalityTrend(municipality.slug);
                const hasHistory = (historyData?.municipalities[municipality.slug]?.history.length || 0) > 0;

                return (
                  <tr
                    key={municipality.slug}
                    className={`hover:bg-muted ${municipality.slug === COUNTRY.nationalSlug ? 'bg-accent font-semibold' : ''} ${hasHistory ? 'cursor-pointer' : ''}`}
                    onClick={() => hasHistory && handleMunicipalityClick(municipality)}
                  >
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-foreground sticky left-0 z-10 ${municipality.slug === COUNTRY.nationalSlug ? 'bg-accent' : 'bg-card hover:bg-muted'}`}>
                      {municipality.name}
                      {municipality.slug === COUNTRY.nationalSlug && (
                        <span className="ml-2 text-xs text-primary">{t.matrix.nationalTag}</span>
                      )}
                    </td>
                    <td className={`px-1 py-4 text-center ${municipality.slug === COUNTRY.nationalSlug ? 'bg-accent' : ''}`}>
                      {hasHistory && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleMunicipalityClick(municipality);
                          }}
                          className="p-1 text-subtle-foreground hover:text-primary hover:bg-accent rounded transition-colors"
                          title={t.matrix.dashboardFor(municipality.name)}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                        </button>
                      )}
                    </td>
                    {providers.map(provider => {
                      const count = municipality.providers[provider] || 0;
                      return (
                        <td key={provider} className="px-4 py-4 text-center text-sm">
                          {count > 0 ? (
                            <span className="text-foreground">{count}</span>
                          ) : (
                            <span className="text-subtle-foreground">-</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-4 py-4 text-center text-sm font-semibold text-foreground bg-muted">
                      {municipality.total}
                    </td>
                    <td className="px-4 py-4 text-center">
                      {trend !== null ? (
                        <TrendIndicator change={trend} />
                      ) : (
                        <span className="text-subtle-foreground">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}

              {/* Totals Row */}
              <tr className="bg-secondary font-semibold border-t-2 border-input">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground sticky left-0 bg-secondary z-10">
                  {t.matrix.totalRow}
                </td>
                <td className="px-1 py-4 bg-secondary"></td>
                {providers.map(provider => (
                  <td key={provider} className="px-4 py-4 text-center text-sm text-foreground">
                    {providerTotals[provider].toLocaleString(COUNTRY.locale)}
                  </td>
                ))}
                <td className="px-4 py-4 text-center text-sm text-foreground bg-border">
                  {grandTotal.toLocaleString(COUNTRY.locale)}
                </td>
                <td className="px-4 py-4 text-center">
                  {trend && <TrendIndicator change={trend.change.total} />}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-card rounded-lg shadow-md p-6">
        <h3 className="font-semibold text-foreground mb-3">{t.matrix.legendTitle}</h3>
        <ul className="text-sm text-muted-foreground space-y-2">
          <li className="flex items-center">
            <span className="w-4 h-4 bg-accent border border-primary/30 rounded mr-2"></span>
            <strong className="mr-1">{COUNTRY.nationalShortLabel}</strong> - {t.matrix.legendNational}
          </li>
          <li className="flex items-center">
            <span className="text-primary mr-2 cursor-pointer">↗</span>
            <strong className="mr-1">{t.matrix.legendRowsTitle}</strong> - {t.matrix.legendRows}
          </li>
          <li className="flex items-center">
            <span className="text-success mr-2 cursor-pointer">📊</span>
            <strong className="mr-1">{t.matrix.totalPoints}</strong> - {t.matrix.legendTotal}
          </li>
          <li className="flex items-center">
            <span className="text-primary mr-2 cursor-pointer">📈</span>
            <strong className="mr-1">{t.matrix.legendCarriersTitle}</strong> - {t.matrix.legendCarriers}
          </li>
          <li className="flex items-center">
            <TrendIndicator change={5} />
            <span className="ml-2"><strong className="mr-1">{t.matrix.trend}</strong> - {t.matrix.legendTrend}</span>
          </li>
          <li className="flex items-center">
            <span className="text-subtle-foreground mr-2">-</span>
            {t.matrix.legendDash}
          </li>
        </ul>
      </div>

      {/* Municipality History Modal */}
      {selectedMunicipality && (
        <MunicipalityHistoryModal
          isOpen={true}
          onClose={() => setSelectedMunicipality(null)}
          municipalityName={selectedMunicipality.name}
          municipalitySlug={selectedMunicipality.slug}
          history={selectedMunicipality.history}
        />
      )}

      {/* Provider History Modal */}
      {selectedProvider && (
        <ProviderHistoryModal
          isOpen={true}
          onClose={() => setSelectedProvider(null)}
          providerName={selectedProvider.name}
          snapshots={selectedProvider.snapshots}
        />
      )}

      {/* Total Overview Modal */}
      {showTotalOverview && (
        <TotalOverviewModal
          isOpen={true}
          onClose={() => setShowTotalOverview(false)}
          snapshots={snapshots}
          providers={providers}
        />
      )}
    </div>
  );
}
