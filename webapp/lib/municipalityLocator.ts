/**
 * Which municipality contains a coordinate — server side only.
 *
 * Geocoders name municipalities inconsistently (Photon says "Bruxelles -
 * Brussel" or a deelgemeente, PDOK used CBS spellings), and matching those
 * names needed hand-kept alias tables. Point-in-polygon against our own
 * outlines sidesteps that and works for every country the same way.
 *
 * Reads public/data/geo/municipality_polygons.geojson, written by
 * scripts/build_municipalities.py, once per server instance.
 */

import fs from 'fs';
import path from 'path';

type Ring = number[][];
type PolygonCoords = Ring[];

interface IndexedMunicipality {
  slug: string;
  name: string;
  polygons: PolygonCoords[];
  bbox: [number, number, number, number]; // minLon, minLat, maxLon, maxLat
}

let index: IndexedMunicipality[] | null = null;

function loadIndex(): IndexedMunicipality[] {
  if (index) return index;

  const file = path.join(process.cwd(), 'public', 'data', 'geo', 'municipality_polygons.geojson');
  const collection = JSON.parse(fs.readFileSync(file, 'utf8'));

  index = collection.features.map((feature: {
    properties: { slug: string; gemeente: string };
    geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: PolygonCoords | PolygonCoords[] };
  }) => {
    const polygons: PolygonCoords[] =
      feature.geometry.type === 'Polygon'
        ? [feature.geometry.coordinates as PolygonCoords]
        : (feature.geometry.coordinates as PolygonCoords[]);

    let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
    for (const polygon of polygons) {
      for (const [lon, lat] of polygon[0]) {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }

    return {
      slug: feature.properties.slug,
      name: feature.properties.gemeente,
      polygons,
      bbox: [minLon, minLat, maxLon, maxLat],
    };
  });

  return index!;
}

/** Ray casting; `ring` is [lon, lat] pairs. */
function inRing(lon: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function inPolygon(lon: number, lat: number, polygon: PolygonCoords): boolean {
  if (!inRing(lon, lat, polygon[0])) return false;
  // Holes
  return !polygon.slice(1).some((hole) => inRing(lon, lat, hole));
}

/** The municipality containing the point, or null outside the country. */
export function locateMunicipality(lat: number, lon: number): { slug: string; name: string } | null {
  for (const m of loadIndex()) {
    const [minLon, minLat, maxLon, maxLat] = m.bbox;
    if (lon < minLon || lon > maxLon || lat < minLat || lat > maxLat) continue;
    if (m.polygons.some((polygon) => inPolygon(lon, lat, polygon))) {
      return { slug: m.slug, name: m.name };
    }
  }
  return null;
}
