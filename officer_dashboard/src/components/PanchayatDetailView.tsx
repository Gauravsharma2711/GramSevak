import React from 'react';
import { 
  ArrowLeft, 
  MapPin, 
  Mountain, 
  Compass, 
  Calendar, 
  Building2, 
  Cpu, 
  CloudRain, 
  FileText, 
  ShieldCheck, 
  Clock, 
  AlertTriangle, 
  Check, 
  X,
  Info,
  Layers
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

export const PanchayatDetailView: React.FC<PanchayatDetailViewProps> = ({
  panchayat,
  advisory,
  onBack,
  onApproveAdvisory,
  onRejectAdvisory,
  onOpenGenerateModal,
}) => {
  const blockForecastMm = advisory?.block_forecast_mm ?? null;
  const downscaledMm = advisory?.rainfall_mm ?? null;
  const diff = (downscaledMm !== null && blockForecastMm !== null) ? downscaledMm - blockForecastMm : null;
  const diffFormatted = diff !== null ? (diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)) : 'N/A';

  const forecastDate = advisory?.forecast_date ?? '2026-09-09';
  const forecastIssueDate = advisory?.forecast_issue_date ?? '2026-09-08';
  const modelName = advisory?.model_name ?? 'Random Forest Regressor';
  const modelVersion = advisory?.rule_version ?? 'v1.0.0';
  const actualObservedMm = advisory?.actual_observed_rainfall_mm ?? null;
  const advisoryStatus = advisory?.status ?? 'DRAFT';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }} className="fade-in">
      {/* Top Back Navigation & Action Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <button
          onClick={onBack}
          className="btn-secondary"
          style={{ padding: '8px 16px', fontSize: '13px' }}
          aria-label="Back to overview"
        >
          <ArrowLeft size={16} />
          <span>Back to Overview</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <StatusBadge status={advisoryStatus} />
          {advisory && advisory.severity && <SeverityBadge severity={advisory.severity} />}
        </div>
      </div>

      {/* 1. Header Card: Panchayat Identity & Geographic Metadata */}
      <div
        className="app-card"
        style={{
          padding: '24px',
          background: 'linear-gradient(135deg, #FFFFFF 0%, #F5FAF7 100%)',
          border: '1px solid var(--primary-100)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: 'var(--primary-050)',
                  color: 'var(--primary-700)',
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-pill)',
                  border: '1px solid var(--primary-100)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                Gram Panchayat Profile
              </span>
              <span style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
                LGD Code: <strong>{panchayat.lgd_code}</strong> • System ID: #{panchayat.panchayat_id}
              </span>
            </div>

            <h1 className="text-page-title" style={{ fontSize: '26px' }}>
              {panchayat.panchayat_name} Gram Panchayat
            </h1>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', color: 'var(--ink-700)', marginTop: '4px' }}>
              <MapPin size={15} color="var(--primary-600)" />
              <span>{panchayat.block_name} Block, {panchayat.district_name} District, Maharashtra</span>
            </div>
          </div>

          {/* Quick Geospatial Coordinates Pill Grid */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              flexWrap: 'wrap',
              backgroundColor: 'var(--surface)',
              padding: '10px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              boxShadow: 'var(--shadow-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
              <Mountain size={16} color="var(--primary-600)" />
              <span>Elev: <strong>{panchayat.elevation_m} m</strong></span>
            </div>
            <span style={{ color: 'var(--ink-300)' }}>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
              <Compass size={16} color="var(--primary-600)" />
              <span>Lat: <strong>{panchayat.latitude.toFixed(4)}°N</strong></span>
            </div>
            <span style={{ color: 'var(--ink-300)' }}>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
              <span>Lon: <strong>{panchayat.longitude.toFixed(4)}°E</strong></span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Visual Central Technical Workflow Flow */}
      <div
        className="app-card"
        style={{
          padding: '24px',
          border: '1px solid var(--ink-300)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
        role="region"
        aria-label="Central Technical Workflow"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 className="text-section-title" style={{ fontSize: '16px' }}>
              GramSevak Central Technical Workflow
            </h2>
            <p className="text-body" style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
              From coarse numerical weather prediction to actionable human-verified advice.
            </p>
          </div>
          <span style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, backgroundColor: 'var(--primary-050)', padding: '3px 8px', borderRadius: 'var(--radius-pill)' }}>
            Zero Leakage ML Architecture
          </span>
        </div>

        {/* 4-Stage Visual Stepper */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '14px',
          }}
        >
          {/* Stage 1: Block Forecast */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--ink-100)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--ink-300)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--ink-700)',
                }}
              >
                <Building2 size={14} />
              </div>
              <span className="text-label" style={{ fontSize: '11px' }}>1. Official Block Forecast</span>
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--ink-900)' }}>
              {blockForecastMm !== null ? `${blockForecastMm.toFixed(1)} mm` : 'Pending IMD Sync'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
              IMD {panchayat.block_name} Block (25–50 km grid)
            </div>
          </div>

          {/* Stage 2: ML Downscaling Engine */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--ink-100)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--ink-300)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--primary-600)',
                }}
              >
                <Cpu size={14} />
              </div>
              <span className="text-label" style={{ fontSize: '11px', color: 'var(--primary-700)' }}>2. ML Downscaling</span>
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-900)' }}>
              {modelName}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
              Inputs: DEM Elev ({panchayat.elevation_m}m) + Coords + DOY
            </div>
          </div>

          {/* Stage 3: Micro Panchayat Forecast */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--primary-050)',
              border: '1px solid var(--primary-100)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--primary-100)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--primary-700)',
                }}
              >
                <CloudRain size={14} />
              </div>
              <span className="text-label" style={{ fontSize: '11px', color: 'var(--primary-700)' }}>3. Panchayat Forecast</span>
            </div>
            <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--primary-700)' }}>
              {downscaledMm !== null ? `${downscaledMm.toFixed(1)} mm` : 'Pending Inference'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, marginTop: '4px' }}>
              {diff !== null ? `Δ ${diffFormatted} mm variance from block` : 'Run ML Downscaling below'}
            </div>
          </div>

          {/* Stage 4: Agro-Meteorological Advisory */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--ink-100)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--ink-300)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--ink-700)',
                }}
              >
                <FileText size={14} />
              </div>
              <span className="text-label" style={{ fontSize: '11px' }}>4. Agro-Advisory</span>
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-900)' }}>
              {advisory?.rainfall_category || 'MODERATE_RAIN'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
              Status: <strong>{advisoryStatus}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Detailed Comparison & Scientific Grounding Matrix */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: '20px' }}>
        {/* Left Column: Forecast & Observation Values */}
        <div className="app-card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <h3 className="text-card-title">Forecast & Observation Metrics</h3>
            <span style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
              Target: <strong>{forecastDate}</strong>
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px' }}>
            {/* Block Baseline */}
            <div style={{ backgroundColor: 'var(--surface-subtle)', padding: '14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--ink-100)' }}>
              <div className="text-label" style={{ fontSize: '10px' }}>Official IMD Block Forecast</div>
              <div style={{ marginTop: '6px' }}>
                <ForecastValue rainfallMm={blockForecastMm} size="lg" />
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
                {panchayat.block_name} Block baseline prediction
              </div>
            </div>

            {/* Downscaled */}
            <div style={{ backgroundColor: 'var(--primary-050)', padding: '14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--primary-100)' }}>
              <div className="text-label" style={{ fontSize: '10px', color: 'var(--primary-700)' }}>GramSevak Downscaled</div>
              <div style={{ marginTop: '6px' }}>
                <ForecastValue rainfallMm={downscaledMm} size="lg" />
              </div>
              <div style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, marginTop: '4px' }}>
                {diff !== null ? `Δ ${diffFormatted} mm difference` : 'Pending ML Downscaling'}
              </div>
            </div>
          </div>

          {/* Actual Observation Reading */}
          <div
            style={{
              padding: '14px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: actualObservedMm !== null ? 'var(--surface-subtle)' : '#F8F9FA',
              border: '1px dashed var(--ink-300)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <div>
              <div className="text-label" style={{ fontSize: '10px' }}>Actual Ground Observation (IMD AWS/ARG)</div>
              {actualObservedMm !== null ? (
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink-900)', marginTop: '4px' }}>
                  {actualObservedMm.toFixed(1)} mm
                </div>
              ) : (
                <div style={{ fontSize: '12px', color: 'var(--ink-500)', fontStyle: 'italic', marginTop: '4px' }}>
                  Observation pending post-event AWS reading on {forecastDate}
                </div>
              )}
            </div>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                padding: '3px 8px',
                borderRadius: 'var(--radius-pill)',
                backgroundColor: actualObservedMm !== null ? 'var(--primary-100)' : 'var(--ink-100)',
                color: actualObservedMm !== null ? 'var(--primary-700)' : 'var(--ink-700)',
              }}
            >
              {actualObservedMm !== null ? 'Verified Ground Truth' : 'Pending Observation'}
            </span>
          </div>

          {/* Temporal Lead Days & Timestamps */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', fontSize: '12px', color: 'var(--ink-500)', paddingTop: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={13} />
              <span>Forecast Issue Date: <strong>{forecastIssueDate}</strong></span>
            </div>
            <div>
              Lead Time: <strong>1 Day (24h Accumulation)</strong>
            </div>
          </div>
        </div>

        {/* Right Column: Model Specs & Feature Physics */}
        <div className="app-card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <h3 className="text-card-title">ML Downscaling Model Specifications</h3>
            <span style={{ fontSize: '11px', color: 'var(--ink-500)', fontWeight: 600 }}>
              Version {modelVersion}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '4px' }}>
              <span style={{ color: 'var(--ink-500)' }}>Architecture:</span>
              <strong style={{ color: 'var(--ink-900)' }}>{modelName}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '4px' }}>
              <span style={{ color: 'var(--ink-500)' }}>Baseline Benchmark:</span>
              <strong style={{ color: 'var(--ink-900)' }}>Block Persistence (IMD)</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '4px' }}>
              <span style={{ color: 'var(--ink-500)' }}>Terrain Elevation:</span>
              <strong style={{ color: 'var(--ink-900)' }}>{panchayat.elevation_m}m (Bhuvan DEM)</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: '4px' }}>
              <span style={{ color: 'var(--ink-500)' }}>Evaluation Standards:</span>
              <strong style={{ color: 'var(--primary-700)' }}>MAE & RMSE vs AWS</strong>
            </div>
          </div>

          {/* Scientific Disclaimer Note */}
          <div
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--surface-subtle)',
              border: '1px solid var(--ink-100)',
              fontSize: '12px',
              color: 'var(--ink-700)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              lineHeight: '18px',
            }}
          >
            <Info size={16} color="var(--primary-600)" style={{ flexShrink: 0, marginTop: '1px' }} />
            <span>
              <strong>Physical Downscaling Context:</strong> Model adjusts rainfall according to terrain slope, elevation ridges, and distance to IMD AWS stations.
            </span>
          </div>

          {/* Trigger New Inference Button */}
          <button
            onClick={() => onOpenGenerateModal(panchayat)}
            className="btn-secondary"
            style={{ marginTop: 'auto', padding: '10px 14px', fontSize: '13px', width: '100%' }}
          >
            <Layers size={14} />
            <span>Re-run Micro Downscaling Inference</span>
          </button>
        </div>
      </div>

      {/* 4. Actionable Agro-Meteorological Advisory Section */}
      {advisory ? (
        <div
          className="app-card"
          style={{
            padding: '24px',
            borderLeft:
              advisory.status === 'APPROVED'
                ? '4px solid var(--primary-500)'
                : advisory.status === 'REJECTED'
                ? '4px solid var(--danger-600)'
                : '4px solid var(--warning-600)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShieldCheck size={20} color="var(--primary-700)" />
              <h3 className="text-section-title" style={{ fontSize: '16px' }}>
                Actionable Agro-Meteorological Advisory
              </h3>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <StatusBadge status={advisory.status} />
              <SeverityBadge severity={advisory.severity} />
            </div>
          </div>

          {/* Advisory Title & Text */}
          <div
            style={{
              backgroundColor: 'var(--surface-subtle)',
              padding: '16px 20px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--ink-300)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)' }}>
              {advisory.advisory_title}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--ink-700)', lineHeight: '22px', whiteSpace: 'pre-line' }}>
              {advisory.advisory_text}
            </div>
          </div>

          {/* Officer Verification Status Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ fontSize: '12px', color: 'var(--ink-500)' }}>
              {advisory.officer_id ? (
                <span>
                  Validated by: <strong>{advisory.officer_id}</strong>
                  {advisory.officer_comment && ` — "${advisory.officer_comment}"`}
                  {advisory.approved_at && ` at ${new Date(advisory.approved_at).toLocaleString()}`}
                </span>
              ) : (
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--warning-600)', fontWeight: 600 }}>
                  <Clock size={14} />
                  <span>Pending extension officer validation before publication to farmer application.</span>
                </span>
              )}
            </div>

            {/* Officer Action Buttons if DRAFT */}
            {advisory.status === 'DRAFT' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', width: '100%', maxWidth: '360px' }}>
                <button
                  onClick={() => onRejectAdvisory(advisory)}
                  className="btn-danger"
                  style={{ flex: 1, minWidth: '130px', padding: '10px 16px', fontSize: '13px' }}
                >
                  <X size={15} />
                  <span>Reject</span>
                </button>

                <button
                  onClick={() => onApproveAdvisory(advisory)}
                  className="btn-primary"
                  style={{ flex: 1, minWidth: '130px', padding: '10px 16px', fontSize: '13px' }}
                >
                  <Check size={15} />
                  <span>Approve</span>
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div
          className="app-card"
          style={{
            padding: '24px',
            textAlign: 'center',
            color: 'var(--ink-500)',
          }}
        >
          <AlertTriangle size={32} color="var(--warning-600)" style={{ margin: '0 auto 8px auto' }} />
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--ink-900)' }}>
            No Advisory Generated Yet for {panchayat.panchayat_name}
          </h3>
          <p style={{ fontSize: '13px', marginTop: '4px' }}>
            Execute micro-downscaling inference to formulate deterministic agricultural guidance.
          </p>
          <button
            onClick={() => onOpenGenerateModal(panchayat)}
            className="btn-primary"
            style={{ marginTop: '14px', fontSize: '13px' }}
          >
            Run ML Downscaling & Advisory Draft
          </button>
        </div>
      )}
    </div>
  );
};
