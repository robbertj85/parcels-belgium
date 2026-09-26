'use client';

import { useState } from 'react';
import { BASEMAPS, type BasemapId } from '@/lib/basemaps';
import { t } from '@/lib/strings';

interface BasemapPickerProps {
  value: BasemapId;
  onChange: (id: BasemapId) => void;
}

/** Map-shaped button under the zoom control; the list folds out to the left. */
export default function BasemapPicker({ value, onChange }: BasemapPickerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute right-[10px] top-[84px] z-20">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t.basemap.title}
        aria-label={t.basemap.title}
        aria-expanded={open}
        className="flex h-[34px] w-[34px] items-center justify-center rounded border-2 border-black/20 bg-white bg-clip-padding text-gray-700 hover:bg-gray-50"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="12 2 2 7 12 12 22 7 12 2" />
          <polyline points="2 17 12 22 22 17" />
          <polyline points="2 12 12 17 22 12" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-11 top-0 flex flex-col gap-1 rounded-lg border border-gray-200 bg-white/95 p-2 shadow-xl backdrop-blur">
          {BASEMAPS.map((basemap) => (
            <button
              key={basemap.id}
              type="button"
              onClick={() => {
                onChange(basemap.id);
                setOpen(false);
              }}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-left text-xs transition-colors ${
                value === basemap.id ? 'bg-blue-600 text-white' : 'text-gray-800 hover:bg-gray-100'
              }`}
            >
              {t.basemap[basemap.id]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
