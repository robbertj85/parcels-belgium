/**
 * The active country profile.
 *
 * Set NEXT_PUBLIC_COUNTRY at build time (Vercel project env var, or
 * `NEXT_PUBLIC_COUNTRY=IT npm run dev`). NEXT_PUBLIC_ is inlined into the client
 * bundle, so every component reads the same profile. Default: BE.
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
