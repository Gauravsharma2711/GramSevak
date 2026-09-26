import React from 'react';

interface ForecastValueProps {
  rainfallMm?: number | null;
  blockForecastMm?: number | null;
  size?: 'sm' | 'md' | 'lg';
  showDifference?: boolean;
}

export const ForecastValue: React.FC<ForecastValueProps> = ({
  rainfallMm,
  blockForecastMm,
  size = 'md',
  showDifference = false,
}) => {
  if (rainfallMm === null || rainfallMm === undefined) {
    const fontSize = size === 'lg' ? '22px' : size === 'md' ? '16px' : '13px';
    return (
      <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        <span style={{ fontSize, fontWeight: 600, color: 'var(--ink-500)', lineHeight: 1.1 }}>
          — <span style={{ fontSize: '12px', fontWeight: 400 }}>mm (Pending)</span>
        </span>
      </div>
    );
  }

  const isHeavy = rainfallMm >= 64.5;
  const isModerate = rainfallMm >= 7.6 && rainfallMm < 64.5;

  const color = isHeavy
    ? 'var(--danger-600)'
    : isModerate
    ? 'var(--primary-700)'
    : 'var(--ink-900)';

  const fontSize = size === 'lg' ? '28px' : size === 'md' ? '18px' : '14px';
  const unitSize = size === 'lg' ? '14px' : size === 'md' ? '12px' : '11px';

  const diff = (blockForecastMm !== undefined && blockForecastMm !== null) ? rainfallMm - blockForecastMm : null;
  const diffFormatted = diff !== null ? (diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)) : null;

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-start' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '3px' }}>
        <span style={{ fontSize, fontWeight: 700, color, lineHeight: 1.1 }}>
          {rainfallMm.toFixed(1)}
        </span>
        <span style={{ fontSize: unitSize, fontWeight: 500, color: 'var(--ink-500)' }}>
          mm
        </span>
      </div>

      {showDifference && diff !== null && blockForecastMm !== null && (
        <span
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: Math.abs(diff) > 10 ? 'var(--warning-600)' : 'var(--ink-500)',
            marginTop: '2px',
          }}
        >
          Δ {diffFormatted} mm vs Block ({blockForecastMm}mm)
        </span>
      )}
    </div>
  );
};
