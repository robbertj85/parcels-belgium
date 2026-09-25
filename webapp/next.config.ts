import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable compression for all responses
  compress: true,

  async headers() {
    const securityHeaders = [
      {
        key: 'X-Content-Type-Options',
        value: 'nosniff',
      },
      {
        key: 'X-XSS-Protection',
        value: '1; mode=block',
      },
      {
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin',
      },
      {
        key: 'Permissions-Policy',
        // geolocation=(self): the "use my location" button in NearestPointsFinder needs it
        value: 'camera=(), microphone=(), geolocation=(self)',
      },
    ];

    return [
      {
        // Embed route: allow iframe embedding from any origin
        source: '/embed',
        headers: [
          ...securityHeaders,
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://va.vercel-scripts.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https://logo.clearbit.com https://*.tile.openstreetmap.org https://unpkg.com",
              "font-src 'self' data:",
              "connect-src 'self' https://va.vercel-scripts.com",
              "worker-src 'self' blob:",
              "child-src 'self' blob:",
              "frame-ancestors *",
            ].join('; '),
          },
        ],
      },
      {
        // All other routes: deny iframe embedding
        source: '/((?!embed).*)',
        headers: [
          ...securityHeaders,
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.redoc.ly https://va.vercel-scripts.com", // Required for Leaflet, Redocly, and Vercel Analytics
              "style-src 'self' 'unsafe-inline'", // Required for dynamic styles
              "img-src 'self' data: https://logo.clearbit.com https://*.tile.openstreetmap.org https://unpkg.com",
              "font-src 'self' data:",
              "connect-src 'self' https://va.vercel-scripts.com", // Required for Vercel Analytics
              "worker-src 'self' blob:", // Required for ReDoc search workers
              "child-src 'self' blob:", // Required for ReDoc search workers
              "frame-ancestors 'none'",
            ].join('; '),
          },
        ],
      },
      {
        // Cache GeoJSON files for 1 hour to allow updates to propagate
        source: '/data/:path*.geojson',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=3600, must-revalidate',
          },
          {
            key: 'Content-Type',
            value: 'application/geo+json',
          },
        ],
      },
      {
        // Cache municipalities.json for 1 day
        source: '/municipalities.json',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=86400, stale-while-revalidate=3600',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
