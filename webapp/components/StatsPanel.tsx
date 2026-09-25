'use client';

import { PakketpuntData, Filters, PakketpuntProperties, PakketpuntFeature, getPointCategory } from '@/types/pakketpunten';

import { COUNTRY } from '@/config/country';
import { t } from '@/lib/strings';
interface StatsPanelProps {
  data: PakketpuntData | null;
  filters: Filters;
}

export default function StatsPanel({ data, filters }: StatsPanelProps) {
  if (!data) {
    return null;
  }

  const isNationalView = data.metadata.slug === COUNTRY.nationalSlug;

  // Calculate filtered stats
  const points = data.features.filter(f => f.properties.type === 'pakketpunt');
  let filteredPoints = points.filter((feature) => {
    const props = feature.properties as PakketpuntProperties;
    const category = getPointCategory(props.puntType);
    return (
      filters.providers.includes(props.vervoerder) &&
      filters.pointCategories.includes(category) &&
      props.bezettingsgraad >= filters.minOccupancy &&
      props.bezettingsgraad <= filters.maxOccupancy
    );
  });

  // Apply shared locations filter if enabled
  if (filters.showOnlySharedLocations) {
    const coordGroups = new Map<string, PakketpuntFeature[]>();
    filteredPoints.forEach((feature) => {
      const coords = feature.geometry.coordinates as [number, number];
      const key = `${coords[1].toFixed(6)},${coords[0].toFixed(6)}`;
      if (!coordGroups.has(key)) {
        coordGroups.set(key, []);
      }
      coordGroups.get(key)!.push(feature as PakketpuntFeature);
    });

    const sharedPoints: PakketpuntFeature[] = [];
    coordGroups.forEach((group) => {
      if (group.length >= 2) {
        sharedPoints.push(...group);
      }
    });
    filteredPoints = sharedPoints;
  }

  const avgOccupancy =
    filteredPoints.length > 0
      ? Math.round(
          filteredPoints.reduce((sum, f) => {
            const props = f.properties as PakketpuntProperties;
            return sum + props.bezettingsgraad;
          }, 0) / filteredPoints.length
        )
      : 0;

  return (
    <div className="p-3 md:p-4 bg-card rounded-lg shadow-md space-y-3 md:space-y-4">
      <div>
        <h3 className="text-base md:text-lg font-semibold text-foreground mb-1 md:mb-2 truncate">{data.metadata.gemeente}</h3>
        <p className="text-xs text-muted-foreground">
          {t.common.updated(new Date(data.metadata.generated_at).toLocaleDateString(COUNTRY.locale))}
        </p>
        {isNationalView && (
          <p className="text-xs text-primary mt-1 font-medium">
            {t.stats.municipalitiesCount((data.metadata as any).municipalities_included)}
          </p>
        )}
      </div>

      <div className={`grid ${filters.showMockData ? 'grid-cols-2' : 'grid-cols-1'} gap-2 md:gap-4`}>
        <div className="p-2.5 md:p-3 bg-accent rounded-lg">
          <p className="text-xs text-muted-foreground font-medium">{t.stats.points}</p>
          <p className="text-xl md:text-2xl font-bold text-primary tabular-nums">
            {filteredPoints.length}
            <span className="text-xs md:text-sm font-normal text-muted-foreground"> / {points.length}</span>
          </p>
        </div>

        {filters.showMockData && (
          <div className="p-2.5 md:p-3 bg-success-muted rounded-lg">
            <p className="text-xs text-muted-foreground font-medium">{t.stats.occupancy} <span className="text-amber-700">(mock)</span></p>
            <p className="text-xl md:text-2xl font-bold text-success tabular-nums">{avgOccupancy}%</p>
          </div>
        )}
      </div>
    </div>
  );
}
