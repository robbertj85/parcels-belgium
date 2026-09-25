'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { t } from '@/lib/strings';

export default function DataExportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const isDownloads = pathname === '/data-export';
  const isMatrix = pathname === '/data-export/matrix';
  const isStatistics = pathname === '/data-export/statistieken';
  const isUpdates = pathname === '/data-export/updates';

  return (
    <div className="min-h-screen bg-muted">
      {/* Header */}
      <header className="bg-card shadow-sm">
        <div className="max-w-[1600px] mx-auto px-4 py-4">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{t.dataExport.layoutTitle}</h1>
              <p className="text-sm text-muted-foreground">
                {t.dataExport.layoutSubtitle}
              </p>
            </div>
            <Link
              href="/"
              className="px-4 py-2 text-sm font-medium text-primary hover:text-primary"
            >
              ← {t.dataExport.backToMap}
            </Link>
          </div>

          {/* Tab Navigation */}
          <nav className="flex gap-2 border-b border-border">
            <Link
              href="/data-export"
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
                isDownloads
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-input'
              }`}
            >
              <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {t.dataExport.tabDownloads}
            </Link>
            <Link
              href="/data-export/matrix"
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
                isMatrix
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-input'
              }`}
            >
              <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {t.dataExport.tabMatrix}
            </Link>
            <Link
              href="/data-export/statistieken"
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
                isStatistics
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-input'
              }`}
            >
              <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              {t.dataExport.tabStatistics}
            </Link>
            <Link
              href="/data-export/updates"
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
                isUpdates
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-input'
              }`}
            >
              <svg className="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {t.dataExport.tabUpdates}
            </Link>
          </nav>
        </div>
      </header>

      {/* Page Content */}
      <main className="max-w-[1600px] mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  );
}
