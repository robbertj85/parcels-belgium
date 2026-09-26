/**
 * The active country profile.
 *
 * Set by next.config.ts from config/active-country (committed, one line: BE or
 * IT), overridable with NEXT_PUBLIC_COUNTRY (e.g. `NEXT_PUBLIC_COUNTRY=IT npm
 * run dev`). It is inlined into the client bundle, so every component reads
 * the same profile.
 */

import { COUNTRIES, type CountryProfile } from './countries';

const code = (process.env.NEXT_PUBLIC_COUNTRY || 'BE').toUpperCase();

if (!COUNTRIES[code]) {
  throw new Error(`Unknown NEXT_PUBLIC_COUNTRY "${code}"; known: ${Object.keys(COUNTRIES).join(', ')}`);
}

export const COUNTRY: CountryProfile = COUNTRIES[code];

export function isNationalSlug(slug: string | null | undefined): boolean {
  return slug === COUNTRY.nationalSlug || slug === COUNTRY.nationalUrlAlias;
}
