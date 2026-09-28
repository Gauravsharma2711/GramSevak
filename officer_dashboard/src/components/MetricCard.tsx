import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: React.ReactNode;
  trend?: {
    text: string;
    isPositive?: boolean;
    color?: string;
  };
  accentColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon,
  trend,
  accentColor = 'var(--primary-700)',
}) => {
  return (
    <div className="app-card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="text-label">{label}</span>
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--surface-subtle)',
            border: '1px solid var(--ink-100)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: accentColor,
          }}
        >
          {icon}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
        <span className="text-metric" style={{ color: 'var(--ink-900)' }}>
          {value}
        </span>
      </div>

      {trend && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: 'var(--text-secondary)' }}>
          <span
            style={{
              fontWeight: 600,
              color: trend.color || (trend.isPositive ? 'var(--primary-700)' : 'var(--danger-600)'),
            }}
          >
            {trend.text}
          </span>
          {subtext && <span style={{ color: 'var(--ink-500)' }}>• {subtext}</span>}
        </div>
      )}

      {!trend && subtext && (
        <div className="text-secondary">{subtext}</div>
      )}
    </div>
  );
};
