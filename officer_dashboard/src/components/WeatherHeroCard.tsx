import React from 'react';
import { CloudRain, TrendingUp, Compass, Mountain, CheckCircle2 } from 'lucide-react';
import { AdvisoryItem } from '../types';
import { TopographyDownscalingIllustration, WeatherStateIllustration } from './illustrations/AgriculturalIllustrations';

interface WeatherHeroCardProps {
  advisories: AdvisoryItem[];
  onReviewClick: (advisory: AdvisoryItem) => void;
  blockName?: string;
  blockForecastMm?: number;
}

export const WeatherHeroCard: React.FC<WeatherHeroCardProps> = ({
  advisories,
  onReviewClick,
  blockName = 'Baglan',
  blockForecastMm: explicitBlockMm,
}) => {
  // Find highest rainfall and lowest rainfall to show spatial downscaling variation
  const validAdvisories = advisories.filter((a) => a.rainfall_mm !== undefined);
  const maxRain = validAdvisories.reduce((prev, curr) => (curr.rainfall_mm > prev.rainfall_mm ? curr : prev), validAdvisories[0] || {});
  const minRain = validAdvisories.reduce((prev, curr) => (curr.rainfall_mm < prev.rainfall_mm ? curr : prev), validAdvisories[0] || {});
  
  // Calculate dynamic block forecast baseline from advisory records if not explicitly passed
  const avgMm = validAdvisories.length > 0
    ? validAdvisories.reduce((sum, a) => sum + a.rainfall_mm, 0) / validAdvisories.length
    : 18.5;
  const blockForecastMm = explicitBlockMm ?? (validAdvisories[0]?.block_forecast_mm ?? Number(avgMm.toFixed(1)));

  return (
    <section
      className="app-card"
      style={{
        backgroundColor: 'var(--surface)',
        border: 'var(--border-card)',
        padding: '24px',
        position: 'relative',
      }}
      aria-label="Downscaled Micro-Climate Summary"
    >
      {/* Section Header: Context & Benchmark */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '3px 9px',
                borderRadius: 'var(--radius-pill)',
                backgroundColor: 'var(--primary-050)',
                color: 'var(--primary-700)',
                border: '1px solid var(--primary-100)',
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.02em',
              }}
            >
              <CloudRain size={13} />
              Panchayat Micro-Climate Comparison
            </span>
            <span style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
              Forecast Date: <strong>2026-09-09</strong>
            </span>
          </div>
          <h2 className="text-page-title">
            Spatial Downscaling vs IMD Block Baseline
          </h2>
        </div>

        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--ink-700)',
            backgroundColor: 'var(--surface-subtle)',
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
            border: 'var(--border-subtle)',
          }}
        >
          <CheckCircle2 size={15} color="var(--primary-600)" />
          <span>IMD Block Average: <strong>{blockForecastMm} mm</strong></span>
        </div>
      </div>

      {/* Grid: IMD Baseline vs High Elevation vs Plains */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(260px, 100%), 1fr))',
          gap: '16px',
        }}
      >
        {/* 1. Official IMD Block Level Baseline */}
        <div
          className="interactive-hover"
          style={{
            backgroundColor: 'var(--surface-subtle)',
            borderRadius: 'var(--radius-md)',
            border: 'var(--border-subtle)',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div className="text-label" style={{ color: 'var(--ink-500)', marginBottom: '4px' }}>
              Reference Baseline
            </div>
            <div style={{ fontSize: 'var(--text-section-title)', fontWeight: 650, color: 'var(--ink-900)' }}>
              {blockName} Block (Coarse IMD)
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '2px' }}>
              Standard 25–50 km NWP model output
            </div>
          </div>

          <div style={{ margin: '14px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="text-metric" style={{ color: 'var(--ink-700)' }}>
                {blockForecastMm} <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--ink-500)' }}>mm</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--ink-500)', marginTop: '4px' }}>
                Uniform across whole block
              </div>
            </div>
            <WeatherStateIllustration rainfallMm={blockForecastMm} size={46} />
          </div>

          <div style={{ marginTop: '8px' }}>
            <TopographyDownscalingIllustration width={220} height={70} style={{ width: '100%', height: 'auto', display: 'block' } as React.CSSProperties} />
          </div>
        </div>

        {/* 2. High Elevation Panchayat (Mulher) */}
        {maxRain.panchayat_name && (
          <div
            className="interactive-hover"
            style={{
              backgroundColor: 'var(--surface)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid rgba(201, 75, 67, 0.25)',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              boxShadow: 'var(--shadow-subtle)',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span className="text-label" style={{ color: 'var(--danger-600)' }}>
                  High-Elevation Microclimate
                </span>
                <span className="status-chip status-chip-draft" style={{ fontSize: '10px', padding: '2px 6px' }}>
                  {maxRain.status}
                </span>
              </div>
              <div style={{ fontSize: 'var(--text-section-title)', fontWeight: 650, color: 'var(--ink-900)' }}>
                {maxRain.panchayat_name} Gram Panchayat
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '2px' }}>
                Orographic uplift zone (Steep gradient)
              </div>
            </div>

            <div style={{ margin: '14px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div className="text-metric" style={{ color: 'var(--danger-600)' }}>
                  {maxRain.rainfall_mm} <span style={{ fontSize: '13px', fontWeight: 500 }}>mm</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--ink-700)', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                    <Mountain size={13} color="var(--ink-500)" />
                    <strong>{maxRain.elevation_m}m</strong>
                  </span>
                  <span style={{ color: 'var(--danger-600)', fontWeight: 600 }}>
                    (+{(maxRain.rainfall_mm - blockForecastMm).toFixed(1)} mm delta)
                  </span>
                </div>
              </div>
              <WeatherStateIllustration rainfallMm={maxRain.rainfall_mm} size={46} />
            </div>

            <button
              onClick={() => onReviewClick(maxRain)}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '8px 14px',
                fontSize: '12px',
                backgroundColor: 'var(--danger-600)',
              }}
            >
              Inspect High-Rain Advisory
            </button>
          </div>
        )}

        {/* 3. Low Rainfall / Plain Panchayat (Dhandri) */}
        {minRain.panchayat_name && (
          <div
            className="interactive-hover"
            style={{
              backgroundColor: 'var(--surface)',
              borderRadius: 'var(--radius-md)',
              border: 'var(--border-card)',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span className="text-label" style={{ color: 'var(--primary-700)' }}>
                  Valley & Plains Microclimate
                </span>
                <span className="status-chip status-chip-approved" style={{ fontSize: '10px', padding: '2px 6px' }}>
                  {minRain.status}
                </span>
              </div>
              <div style={{ fontSize: 'var(--text-section-title)', fontWeight: 650, color: 'var(--ink-900)' }}>
                {minRain.panchayat_name} Gram Panchayat
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '2px' }}>
                Leeward agricultural flatland
              </div>
            </div>

            <div style={{ margin: '14px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div className="text-metric" style={{ color: 'var(--primary-700)' }}>
                  {minRain.rainfall_mm} <span style={{ fontSize: '13px', fontWeight: 500 }}>mm</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--ink-700)', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                    <Compass size={13} color="var(--ink-500)" />
                    <strong>{minRain.elevation_m}m</strong>
                  </span>
                  <span style={{ color: 'var(--primary-700)', fontWeight: 600 }}>
                    ({(minRain.rainfall_mm - blockForecastMm).toFixed(1)} mm delta)
                  </span>
                </div>
              </div>
              <WeatherStateIllustration rainfallMm={minRain.rainfall_mm} size={46} />
            </div>

            <button
              onClick={() => onReviewClick(minRain)}
              className="btn-secondary"
              style={{
                width: '100%',
                padding: '8px 14px',
                fontSize: '12px',
              }}
            >
              View Verified Guidance
            </button>
          </div>
        )}
      </div>


      {/* Downscaling Explanation Note: Grounded & Calm */}
      <div
        style={{
          marginTop: '18px',
          paddingTop: '14px',
          borderTop: 'var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '10px',
          fontSize: '12px',
          color: 'var(--ink-700)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <TrendingUp size={15} color="var(--primary-600)" />
          <span>
            <strong>Spatial Spread Detected:</strong> ML models capture <strong>{(maxRain.rainfall_mm - minRain.rainfall_mm).toFixed(1)} mm</strong> rainfall variation across {blockName} block.
          </span>
        </div>
        <div style={{ color: 'var(--ink-500)' }}>
          Benchmarked against IMD AWS / ARG telemetry
        </div>
      </div>
    </section>
  );
};
