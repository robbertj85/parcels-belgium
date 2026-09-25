'use client';

import { useState, useEffect, useRef } from 'react';

import { COUNTRY } from '@/config/country';
import { CARRIER_CATALOG, CARRIER_LABELS, CARRIER_ORDER } from '@/lib/carriers';
import { t } from '@/lib/strings';
interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AboutModal({ isOpen, onClose }: AboutModalProps) {
  const [activeTab, setActiveTab] = useState<'about' | 'sources' | 'usage' | 'links'>('about');
  const contentRef = useRef<HTMLDivElement>(null);

  // Reset scroll position when tab changes
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = 0;
    }
  }, [activeTab]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="bg-card rounded-t-xl sm:rounded-lg shadow-xl w-full sm:max-w-3xl max-h-[70vh] sm:max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-border flex justify-between items-center bg-card flex-shrink-0">
          <h2 className="text-xl sm:text-2xl font-bold text-foreground">{t.about.title}</h2>
          <button
            onClick={onClose}
            className="p-2 -mr-2 text-subtle-foreground hover:text-muted-foreground hover:bg-secondary rounded-full transition"
            aria-label={t.common.close}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs - scrollable on mobile */}
        <div className="flex border-b border-border px-2 sm:px-6 overflow-x-auto scrollbar-hide bg-card flex-shrink-0">
          <button
            onClick={() => setActiveTab('about')}
            className={`py-3 px-3 sm:px-4 font-medium text-xs sm:text-sm border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'about'
                ? 'border-primary text-primary'
                : 'border-transparent text-subtle-foreground hover:text-muted-foreground'
            }`}
          >
            {t.about.tabAbout}
          </button>
          <button
            onClick={() => setActiveTab('sources')}
            className={`py-3 px-3 sm:px-4 font-medium text-xs sm:text-sm border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'sources'
                ? 'border-primary text-primary'
                : 'border-transparent text-subtle-foreground hover:text-muted-foreground'
            }`}
          >
            {t.about.tabSources}
          </button>
          <button
            onClick={() => setActiveTab('usage')}
            className={`py-3 px-3 sm:px-4 font-medium text-xs sm:text-sm border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'usage'
                ? 'border-primary text-primary'
                : 'border-transparent text-subtle-foreground hover:text-muted-foreground'
            }`}
          >
            {t.about.tabUsage}
          </button>
          <button
            onClick={() => setActiveTab('links')}
            className={`py-3 px-3 sm:px-4 font-medium text-xs sm:text-sm border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'links'
                ? 'border-primary text-primary'
                : 'border-transparent text-subtle-foreground hover:text-muted-foreground'
            }`}
          >
            {t.about.tabLinks}
          </button>
        </div>

        {/* Content */}
        <div ref={contentRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-3 sm:py-4">
          {activeTab === 'about' && (
            <div className="space-y-4">
              <section>
                <h3 className="text-lg font-semibold text-foreground mb-2">{COUNTRY.siteName}</h3>
                <p className="text-muted-foreground text-sm leading-relaxed mb-3">
                  {t.about.intro}
                </p>
                <p className="text-muted-foreground text-sm leading-relaxed">
                  {t.about.audience}
                </p>
              </section>

              <section>
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.featuresTitle}</h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                  <li>{t.about.featureMap}</li>
                  <li>{t.about.featureFiltering}</li>
                  <li>{t.about.featureCoverage}</li>
                  <li>{t.about.featureStats}</li>
                  <li>{t.about.featureResponsive}</li>
                  <li>{t.about.featureExport}</li>
                </ul>
              </section>

              <section>
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.ackTitle}</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {t.about.ackDerivedFrom}{' '}
                  {COUNTRY.sisterSites.map((site, i) => (
                    <span key={site.url}>
                      {i > 0 && t.about.ackJoin}
                      <a href={site.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{site.label}</a>
                    </span>
                  ))}
                  {t.about.ackMiddle}<strong>{t.about.ackOrg}</strong>{t.about.ackEnd}
                </p>
              </section>

              <section>
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.openSourceTitle}</h4>
                <p className="text-sm text-muted-foreground leading-relaxed mb-2">
                  {t.about.openSourceBody}
                </p>
                <a
                  href={COUNTRY.githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-sm text-primary hover:text-primary font-medium"
                >
                  <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                  </svg>
                  {t.about.githubRepo}
                </a>
              </section>
            </div>
          )}

          {activeTab === 'sources' && (
            <div className="space-y-4">
              <section>
                <h3 className="text-lg font-semibold text-foreground mb-3">{t.about.sourcesTitle}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {t.about.sourcesIntro}
                </p>
              </section>

              <div className="space-y-3">
                {CARRIER_ORDER.map((carrier) => {
                  const brand = CARRIER_CATALOG[carrier];
                  return (
                    <DataSourceCard
                      key={carrier}
                      name={brand.source.name}
                      endpoint={brand.source.endpoint}
                      type={t.about.methods[brand.source.method]}
                      url={brand.source.url}
                      color={brand.borderColor ?? brand.background}
                    />
                  );
                })}
              </div>

              <section className="border-t pt-4 mt-4">
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.missingTitle}</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  {t.about.missingIntro}
                </p>
                <ul className="text-sm text-muted-foreground space-y-2">
                  {COUNTRY.missingCarriers.map((missing) => (
                    <li key={missing.name}>
                      <strong className="text-foreground">{missing.name}:</strong> {missing.reason}
                    </li>
                  ))}
                </ul>
              </section>

              <section className="border-t pt-4 mt-4">
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.additionalSourcesTitle}</h4>
                <ul className="text-sm text-muted-foreground space-y-2">
                  <li>
                    <strong>{t.about.addressSearchLabel}</strong> Photon (komoot)
                    <span className="text-subtle-foreground ml-2">© OpenStreetMap contributors</span>
                  </li>
                  <li>
                    <strong>{t.about.boundariesLabel}</strong> {t.about.boundariesSource}
                    <span className="text-subtle-foreground ml-2">© OpenStreetMap contributors</span>
                  </li>
                  <li>
                    <strong>{t.about.basemapLabel}</strong> {t.about.basemapSource}
                    <span className="text-subtle-foreground ml-2">© OpenStreetMap contributors</span>
                  </li>
                </ul>
              </section>

              <section className="bg-accent border border-primary/30 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-accent-foreground mb-2">{t.about.updateFrequencyTitle}</h4>
                <p className="text-sm text-primary mb-3">
                  {t.about.updateFrequencyBody}
                </p>
                <a
                  href="/data-export"
                  className="inline-flex items-center text-sm text-primary hover:text-accent-foreground font-medium"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  {t.about.updateStatusLink}
                </a>
              </section>
            </div>
          )}

          {activeTab === 'usage' && (
            <div className="space-y-4">
              <section>
                <h3 className="text-lg font-semibold text-foreground mb-3">{t.about.termsTitle}</h3>
                <p className="text-sm text-muted-foreground mb-3">
                  {t.about.termsBody}
                </p>
              </section>

              <section>
                <h4 className="text-md font-semibold text-foreground mb-3">{t.about.policiesTitle}</h4>
                <div className="space-y-2 text-sm text-muted-foreground">
                  {(['Publieke API', 'Web scraping', 'Browser-automatisering'] as const).map((method) => {
                    const carriers = CARRIER_ORDER.filter((c) => CARRIER_CATALOG[c].source.method === method);
                    if (carriers.length === 0) return null;
                    const note = t.about.methodNotes[method];
                    return (
                      <p key={method}>
                        <strong>{carriers.map((c) => CARRIER_LABELS[c]).join(', ')}:</strong> {note}
                      </p>
                    );
                  })}
                  <p><strong>{t.about.policyGeneralLabel}</strong> {t.about.policyGeneralBody}</p>
                </div>
              </section>

              <section className="border-t pt-4 mt-4">
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.attributionTitle}</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  {t.about.attributionIntro}
                </p>
                <div className="bg-muted border border-border rounded p-3 text-xs font-mono">
                  <pre className="whitespace-pre-wrap text-foreground">
{`${t.about.attributionSources}
${CARRIER_ORDER.map((c) => `- ${CARRIER_CATALOG[c].source.name} (${CARRIER_CATALOG[c].source.url})`).join('\n')}
- ${t.about.attributionBoundaries}

Project: ${COUNTRY.siteName}
Repository: ${COUNTRY.githubUrl.replace('https://', '')}
License: MIT`}
                  </pre>
                </div>
              </section>

              <section className="bg-muted border border-input rounded-lg p-4">
                <h4 className="text-sm font-semibold text-foreground mb-2">{t.about.disclaimerTitle}</h4>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {t.about.disclaimerBody}
                </p>
              </section>

              <section className="border-t pt-4 mt-4">
                <h4 className="text-md font-semibold text-foreground mb-2">{t.about.moreInfoTitle}</h4>
                <p className="text-sm text-muted-foreground mb-2">
                  {t.about.moreInfoBody}
                </p>
                <a
                  href={COUNTRY.githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-sm text-primary hover:text-primary font-medium"
                >
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                  </svg>
                  {t.about.githubRepo}
                </a>
              </section>
            </div>
          )}

          {activeTab === 'links' && (
            <div className="space-y-4">
              <section>
                <h3 className="text-lg font-semibold text-foreground mb-3">{t.about.externalTitle}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {t.about.externalIntro}
                </p>
              </section>

              <div className="space-y-3">
                {COUNTRY.aboutLinks.map((link) => (
                  <div key={link.url} className="border border-border rounded-lg p-4 hover:border-primary/50 transition">
                    <h4 className="font-semibold text-foreground mb-2">{link.title}</h4>
                    <p className="text-sm text-muted-foreground mb-3">{link.description}</p>
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center text-sm text-primary hover:text-primary font-medium"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      {t.about.open}
                    </a>
                  </div>
                ))}

                <div className="border border-border rounded-lg p-4 hover:border-green-300 transition">
                  <h4 className="font-semibold text-foreground mb-2">A Greener Last Mile: Carbon Emission Impact of Pickup Points</h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    {t.about.study1Body}
                  </p>
                  <a
                    href="https://www.sciencedirect.com/science/article/pii/S1364032123004872"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-sm text-success hover:text-success font-medium"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    {t.about.study1Link}
                  </a>
                  <p className="text-xs text-subtle-foreground mt-2">{t.about.study1Meta}</p>
                </div>

                <div className="border border-border rounded-lg p-4 hover:border-purple-300 transition">
                  <h4 className="font-semibold text-foreground mb-2">Drivers of Consumers' Adoption of Parcel Lockers</h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    {t.about.study2Body}
                  </p>
                  <a
                    href="https://www.sciencedirect.com/science/article/pii/S259019822600031X"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-sm text-purple-600 hover:text-purple-800 font-medium"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    {t.about.study2Link}
                  </a>
                  <p className="text-xs text-subtle-foreground mt-2">{t.about.study2Meta}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-t border-border bg-muted">
          <button
            onClick={onClose}
            className="w-full px-4 py-3 sm:py-2 bg-primary text-white rounded-lg hover:bg-primary/90 active:bg-primary/80 transition font-medium text-base sm:text-sm"
          >
            {t.common.close}
          </button>
        </div>
      </div>
    </div>
  );
}

// Helper component for data source cards
function DataSourceCard({
  name,
  endpoint,
  type,
  url,
  color
}: {
  name: string;
  endpoint: string;
  type: string;
  url: string;
  color: string;
}) {
  return (
    <div className="border border-border rounded-lg p-3 hover:border-input transition">
      <div className="flex items-start">
        <div
          className="w-4 h-4 rounded-full mt-0.5 mr-3 flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <div className="flex-1 min-w-0">
          <h5 className="font-semibold text-sm text-foreground">{name}</h5>
          <p className="text-xs text-muted-foreground mt-1">
            <span className="font-medium">{t.popup.type}</span> {type}
          </p>
          <p className="text-xs text-subtle-foreground mt-0.5 font-mono break-all">
            {endpoint}
          </p>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:text-primary mt-1 inline-block"
          >
            {url} ↗
          </a>
        </div>
      </div>
    </div>
  );
}

// Helper component for usage items
function UsageItem({ allowed, children }: { allowed: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-start text-sm">
      <span className={`mr-2 mt-0.5 ${allowed ? 'text-success' : 'text-destructive'}`}>
        {allowed ? '✓' : '✗'}
      </span>
      <span className={allowed ? 'text-muted-foreground' : 'text-muted-foreground'}>{children}</span>
    </div>
  );
}
