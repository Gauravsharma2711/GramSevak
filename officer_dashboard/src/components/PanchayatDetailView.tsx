import React, { useState } from 'react';
import { 
  ArrowLeft, 
  Mountain, 
  Compass, 
  Calendar, 
  Cpu, 
  CloudRain, 
  ShieldCheck, 
  AlertTriangle, 
  Check, 
  X, 
  Layers,
  ChevronDown,
  ChevronUp,
  Droplets,
  TrendingUp,
  CheckCircle2
} from 'lucide-react';
import { AdvisoryItem, PanchayatItem } from '../types';
import { StatusBadge } from './common/StatusBadge';
import { SeverityBadge } from './common/SeverityBadge';
import { ForecastValue } from './common/ForecastValue';

interface PanchayatDetailViewProps {
  panchayat: PanchayatItem;
  advisory?: AdvisoryItem | null;
  onBack: () => void;
  onApproveAdvisory: (advisory: AdvisoryItem) => void;
  onRejectAdvisory: (advisory: AdvisoryItem) => void;
  onOpenGenerateModal: (panchayat: PanchayatItem) => void;
}

/**
 * IMD Standard Rainfall Intensity Gauge
 * Lightweight, accessible horizontal visualization of precipitation brackets
 */
const RainfallIntensityGauge: React.FC<{ rainfallMm: number | null }> = ({ rainfallMm }) => {
  if (rainfallMm === null) return null;

  const getBracket = (mm: number) => {
    if (mm < 0.1) return { label: 'Dry / Nil', color: 'var(--ink-500)', activeIdx: 0 };
    if (mm <= 2.4) return { label: 'Very Light Rain', color: 'var(--info-600)', activeIdx: 1 };
    if (mm <= 15.5) return { label: 'Light Rain', color: 'var(--primary-600)', activeIdx: 2 };
    if (mm <= 64.4) return { label: 'Moderate Rain', color: 'var(--warning-600)', activeIdx: 3 };
    if (mm <= 115.5) return { label: 'Heavy Rain', color: 'var(--danger-600)', activeIdx: 4 };
    return { label: 'Very Heavy Rain', color: 'var(--danger-600)', activeIdx: 5 };
  };

  const bracket = getBracket(rainfallMm);

  const brackets = [
    { name: 'Nil', range: '<0.1mm' },
    { name: 'V.Light', range: '0.1-2.4' },
    { name: 'Light', range: '2.5-15.5' },
    { name: 'Moderate', range: '15.6-64.4' },
    { name: 'Heavy', range: '64.5-115.5' },
    { name: 'V.Heavy', range: '>115.5' },
  ];

  return (
    <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: 'var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '11px', color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>
          IMD Rainfall Intensity Scale
        </span>
        <span style={{ fontSize: '12px', fontWeight: 700, color: bracket.color }}>
          {bracket.label} ({rainfallMm.toFixed(1)} mm)
        </span>
      </div>

      {/* Visual Segmented Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '4px',
          height: '8px',
          borderRadius: 'var(--radius-pill)',
          overflow: 'hidden',
          backgroundColor: 'var(--canvas)',
        }}
        role="progressbar"
        aria-valuenow={rainfallMm}
        aria-valuemin={0}
        aria-valuemax={120}
        aria-label={`IMD Rainfall Intensity: ${bracket.label}`}
      >
        {brackets.map((b, idx) => {
          const isActive = idx === bracket.activeIdx;
          const isPassed = idx <= bracket.activeIdx;
          return (
            <div
              key={b.name}
              title={`${b.name} (${b.range} mm)`}
              style={{
                height: '100%',
                backgroundColor: isPassed ? bracket.color : 'var(--ink-100)',
                opacity: isActive ? 1 : isPassed ? 0.75 : 0.35,
                borderRadius: '2px',
                transition: 'all 0.2s ease',
              }}
            />
          );
        })}
      </div>

      {/* Scale Labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--ink-500)', marginTop: '4px' }}>
        <span>0 mm (Nil)</span>
        <span className="hide-on-mobile">Light (15.5)</span>
        <span>Moderate (64.4)</span>
        <span>Heavy (115.5+)</span>
      </div>
    </div>
  );
};

export const PanchayatDetailView: React.FC<PanchayatDetailViewProps> = ({
  panchayat,
  advisory,
  onBack,
  onApproveAdvisory,
  onRejectAdvisory,
  onOpenGenerateModal,
}) => {
  const blockForecastMm = advisory?.block_forecast_mm ?? 18.5;
  const downscaledMm = advisory?.rainfall_mm ?? null;
  const diff = downscaledMm !== null ? downscaledMm - blockForecastMm : null;
  const diffFormatted = diff !== null ? (diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)) : 'N/A';

  const defaultDate = advisory?.forecast_date ?? '2026-09-09';
  const [selectedDate, setSelectedDate] = useState<string>(defaultDate);
  const [showTechnicalSpecs, setShowTechnicalSpecs] = useState(false);

  const forecastIssueDate = advisory?.forecast_issue_date ?? '2026-09-08';
  const modelName = advisory?.model_name ?? 'Random Forest Regressor';
  const modelVersion = advisory?.rule_version ?? 'v1.0.0';
  const actualObservedMm = advisory?.actual_observed_rainfall_mm ?? null;
  const advisoryStatus = advisory?.status ?? 'DRAFT';

  // Compact Date Timeline Options
  const availableDates = [
    { date: defaultDate, label: 'Target Forecast', isPrimary: true },
    { date: '2026-09-10', label: 'Day +2 Outlook', isPrimary: false },
    { date: '2026-09-08', label: 'Past Ground Baseline', isPrimary: false },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }} className="fade-in">
      {/* 1. Administrative Breadcrumb & Navigation Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={onBack}
            className="btn-secondary"
            style={{ padding: '6px 14px', fontSize: '13px', minHeight: '36px' }}
            aria-label="Back to overview"
          >
            <ArrowLeft size={15} />
            <span>Back</span>
          </button>

          {/* District → Block → Panchayat Hierarchy Breadcrumb */}
          <nav aria-label="Administrative Location Hierarchy" style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <span style={{ color: 'var(--ink-500)' }}>{panchayat.district_name}</span>
            <span style={{ color: 'var(--ink-300)' }}>›</span>
            <span style={{ color: 'var(--ink-500)' }}>{panchayat.block_name} Block</span>
            <span style={{ color: 'var(--ink-300)' }}>›</span>
            <strong style={{ color: 'var(--ink-900)' }}>{panchayat.panchayat_name} GP</strong>
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <StatusBadge status={advisoryStatus} />
          {advisory && advisory.severity && <SeverityBadge severity={advisory.severity} />}
        </div>
      </div>

      {/* 2. Panchayat Identity & Compact Geospatial Metadata */}
      <section
        className="app-card"
        style={{
          padding: '20px 24px',
          backgroundColor: 'var(--surface)',
          border: 'var(--border-card)',
        }}
        aria-label="Panchayat Geographic Information"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: 'var(--primary-050)',
                  color: 'var(--primary-700)',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-pill)',
                  border: '1px solid var(--primary-100)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                Gram Panchayat
              </span>
              <span style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
                LGD Code: <strong>{panchayat.lgd_code}</strong>
              </span>
            </div>

            <h1 className="text-page-title" style={{ fontSize: '22px' }}>
              {panchayat.panchayat_name}
            </h1>
          </div>

          {/* Compact Geographic Metadata Chips */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              flexWrap: 'wrap',
              backgroundColor: 'var(--surface-subtle)',
              padding: '8px 14px',
              borderRadius: 'var(--radius-sm)',
              border: 'var(--border-subtle)',
              fontSize: '12px',
              color: 'var(--ink-700)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Mountain size={14} color="var(--primary-600)" />
              <span>Elevation: <strong>{panchayat.elevation_m} m</strong></span>
            </div>
            <span style={{ color: 'var(--ink-300)' }}>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Compass size={14} color="var(--primary-600)" />
              <span>Coords: <strong>{panchayat.latitude.toFixed(3)}°N, {panchayat.longitude.toFixed(3)}°E</strong></span>
            </div>
          </div>
        </div>

        {/* Date Navigation Strip */}
        <div
          style={{
            marginTop: '16px',
            paddingTop: '14px',
            borderTop: 'var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Calendar size={14} color="var(--ink-500)" />
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-700)' }}>
              Forecast Timeline:
            </span>
          </div>

          <div
            style={{
              display: 'inline-flex',
              backgroundColor: 'var(--surface-subtle)',
              padding: '3px',
              borderRadius: 'var(--radius-pill)',
              border: 'var(--border-subtle)',
              gap: '4px',
            }}
            role="tablist"
            aria-label="Forecast date selection"
          >
            {availableDates.map((item) => {
              const isSelected = selectedDate === item.date;
              return (
                <button
                  key={item.date}
                  onClick={() => setSelectedDate(item.date)}
                  role="tab"
                  aria-selected={isSelected}
                  style={{
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-pill)',
                    backgroundColor: isSelected ? 'var(--primary-700)' : 'transparent',
                    color: isSelected ? 'var(--surface)' : 'var(--ink-700)',
                    fontSize: '11px',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {item.date} {item.isPrimary && '• Validated'}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* 3. Primary Forecast & Advisory Experience */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))',
          gap: '20px',
        }}
      >
        {/* Left Card: Micro-Downscaled Weather Details */}
        <section
          className="app-card"
          style={{
            backgroundColor: 'var(--surface)',
            border: 'var(--border-card)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
          aria-label="Panchayat Forecast Details"
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CloudRain size={16} color="var(--primary-600)" />
                <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)' }}>
                  Microclimate Rainfall Forecast
                </h2>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                Target: <strong>{selectedDate}</strong>
              </span>
            </div>

            {/* Comparison Metrics */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                marginBottom: '14px',
              }}
            >
              {/* Downscaled Prediction */}
              <div
                style={{
                  backgroundColor: 'var(--primary-050)',
                  border: '1px solid var(--primary-100)',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div className="text-label" style={{ color: 'var(--primary-700)', fontSize: '10px' }}>
                  GramSevak Downscaled
                </div>
                <div style={{ marginTop: '4px' }}>
                  <ForecastValue rainfallMm={downscaledMm} size="lg" />
                </div>
                <div style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, marginTop: '4px' }}>
                  {diff !== null ? `Δ ${diffFormatted} mm variance` : 'Pending ML Run'}
                </div>
              </div>

              {/* IMD Block Baseline */}
              <div
                style={{
                  backgroundColor: 'var(--surface-subtle)',
                  border: 'var(--border-subtle)',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div className="text-label" style={{ color: 'var(--ink-500)', fontSize: '10px' }}>
                  IMD Block Average
                </div>
                <div style={{ marginTop: '4px' }}>
                  <ForecastValue rainfallMm={blockForecastMm} size="lg" />
                </div>
                <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
                  {panchayat.block_name} Block coarse grid
                </div>
              </div>
            </div>

            {/* IMD Intensity Visual Scale */}
            <RainfallIntensityGauge rainfallMm={downscaledMm} />
          </div>

          {/* Ground Truth Telemetry Status */}
          <div
            style={{
              marginTop: '16px',
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: actualObservedMm !== null ? 'var(--primary-050)' : 'var(--surface-subtle)',
              border: 'var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '11px',
              color: 'var(--ink-700)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <TrendingUp size={14} color="var(--primary-600)" />
              <span>AWS Ground Truth:</span>
              <strong>{actualObservedMm !== null ? `${actualObservedMm.toFixed(1)} mm` : 'Pending post-event reading'}</strong>
            </div>
            <span style={{ color: 'var(--ink-500)' }}>
              Lead: 24h
            </span>
          </div>
        </section>

        {/* Right Card: Agricultural Advisory & Extension Officer Actions */}
        <section
          className="app-card"
          style={{
            backgroundColor: 'var(--surface)',
            border: 'var(--border-card)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
          aria-label="Agro-Meteorological Advisory"
        >
          {advisory ? (
            <>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ShieldCheck size={16} color="var(--primary-700)" />
                    <h2 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)' }}>
                      Agronomic Recommendation
                    </h2>
                  </div>
                  <StatusBadge status={advisory.status} size="sm" />
                </div>

                {/* Recommendation Box */}
                <div
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    border: 'var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '14px 16px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink-900)' }}>
                    {advisory.advisory_title}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--ink-700)', lineHeight: '20px', marginTop: '6px', whiteSpace: 'pre-line' }}>
                    {advisory.advisory_text}
                  </div>
                </div>

                {/* Meteorological Condition Context */}
                <div style={{ fontSize: '12px', color: 'var(--ink-700)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Droplets size={13} color="var(--primary-600)" />
                  <span>Condition Trigger: <strong>{advisory.rainfall_category}</strong> (Severity: {advisory.severity})</span>
                </div>
              </div>

              {/* Officer Verification & Approval Bar */}
              <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: 'var(--border-subtle)' }}>
                {advisory.status === 'APPROVED' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary-700)', fontSize: '12px' }}>
                    <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
                    <span>
                      Verified by <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong> • Active on Farmer App
                    </span>
                  </div>
                ) : advisory.status === 'REJECTED' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger-600)', fontSize: '12px' }}>
                    <X size={16} style={{ flexShrink: 0 }} />
                    <span>
                      Rejected by <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong>
                      {advisory.officer_comment && ` (${advisory.officer_comment})`}
                    </span>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => onApproveAdvisory(advisory)}
                      className="btn-primary"
                      style={{ flex: 1, minHeight: '36px', fontSize: '12px' }}
                    >
                      <Check size={14} />
                      <span>Approve & Publish</span>
                    </button>

                    <button
                      onClick={() => onRejectAdvisory(advisory)}
                      className="btn-danger"
                      style={{ padding: '8px 14px', minHeight: '36px', fontSize: '12px' }}
                    >
                      <X size={14} />
                      <span>Reject</span>
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Empty State if no advisory formulated yet */
            <div style={{ textAlign: 'center', padding: '24px 12px', margin: 'auto 0' }}>
              <AlertTriangle size={28} color="var(--warning-600)" style={{ margin: '0 auto 8px auto' }} />
              <h3 style={{ fontSize: '15px', fontWeight: 650, color: 'var(--ink-900)' }}>
                No Advisory Formulated Yet
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--ink-500)', marginTop: '4px', maxWidth: '300px', margin: '4px auto 14px auto' }}>
                Run ML downscaling to generate hyper-local weather predictions and draft deterministic advice.
              </p>
              <button
                onClick={() => onOpenGenerateModal(panchayat)}
                className="btn-primary"
                style={{ fontSize: '12px', padding: '8px 16px' }}
              >
                Run ML Downscaling
              </button>
            </div>
          )}
        </section>
      </div>

      {/* 4. Supporting Information: Technical Methodology & Model Specs (Quiet & Collapsible) */}
      <section
        className="app-card"
        style={{
          backgroundColor: 'var(--surface-subtle)',
          border: 'var(--border-subtle)',
          padding: '14px 18px',
          boxShadow: 'none',
        }}
        aria-label="Model Specifications"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} color="var(--primary-600)" />
            <span style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink-900)' }}>
              ML Downscaling Architecture: {modelName} ({modelVersion})
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => onOpenGenerateModal(panchayat)}
              className="btn-secondary"
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                minHeight: '28px',
                gap: '4px',
                borderRadius: 'var(--radius-pill)',
              }}
            >
              <Layers size={12} />
              <span>Re-run Inference</span>
            </button>

            <button
              onClick={() => setShowTechnicalSpecs(!showTechnicalSpecs)}
              className="btn-secondary"
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                minHeight: '28px',
                gap: '4px',
                borderRadius: 'var(--radius-pill)',
              }}
              aria-expanded={showTechnicalSpecs}
              aria-label={showTechnicalSpecs ? 'Hide model technical parameters' : 'View model technical parameters'}
            >
              <span>{showTechnicalSpecs ? 'Hide Specs' : 'View Specs'}</span>
              {showTechnicalSpecs ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          </div>
        </div>

        {showTechnicalSpecs && (
          <div
            style={{
              marginTop: '12px',
              paddingTop: '12px',
              borderTop: 'var(--border-subtle)',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '12px',
              fontSize: '12px',
              color: 'var(--ink-700)',
            }}
            className="fade-in"
          >
            <div>
              <span style={{ color: 'var(--ink-500)' }}>Features:</span>
              <div style={{ fontWeight: 600 }}>DEM Elevation ({panchayat.elevation_m}m) + Lat/Lon + DOY</div>
            </div>
            <div>
              <span style={{ color: 'var(--ink-500)' }}>Baseline Benchmark:</span>
              <div style={{ fontWeight: 600 }}>Official IMD 25–50 km NWP persistence</div>
            </div>
            <div>
              <span style={{ color: 'var(--ink-500)' }}>Issued At:</span>
              <div style={{ fontWeight: 600 }}>{forecastIssueDate} (24h lead accumulation)</div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
