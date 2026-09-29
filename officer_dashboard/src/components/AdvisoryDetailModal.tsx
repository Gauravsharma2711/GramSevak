import React from 'react';
import { 
  X, 
  MapPin, 
  Calendar, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Lock, 
  FileText, 
  TrendingUp, 
  Check, 
  X as XIcon,
  Layers,
  Sparkles,
  Edit3
} from 'lucide-react';
import { AdvisoryItem } from '../types';
import { StatusBadge } from './common/StatusBadge';
import { SeverityBadge } from './common/SeverityBadge';

interface AdvisoryDetailModalProps {
  advisory: AdvisoryItem | null;
  isOpen: boolean;
  onClose: () => void;
  onRequestApprove: (advisory: AdvisoryItem) => void;
  onRequestReject: (advisory: AdvisoryItem) => void;
  onRequestEdit?: (advisory: AdvisoryItem) => void;
}

export const AdvisoryDetailModal: React.FC<AdvisoryDetailModalProps> = ({
  advisory,
  isOpen,
  onClose,
  onRequestApprove,
  onRequestReject,
  onRequestEdit,
}) => {
  if (!isOpen || !advisory) return null;

  const blockForecastMm = advisory.block_forecast_mm || 18.5;
  const downscaledMm = advisory.rainfall_mm;
  const varianceDelta = Number((downscaledMm - blockForecastMm).toFixed(1));
  const ruleVersion = advisory.rule_version || 'v1.0.0-deterministic-agromet';
  const issueDate = advisory.forecast_issue_date || '2026-09-08';

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(30, 40, 35, 0.55)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 55,
        padding: '20px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="advisory-detail-title"
    >
      <div
        style={{
          backgroundColor: 'var(--surface)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-modal)',
          maxWidth: '740px',
          width: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid var(--ink-300)',
          animation: 'fadeIn 0.2s ease',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: 'var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'var(--surface-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor:
                  advisory.status === 'APPROVED'
                    ? 'var(--primary-100)'
                    : advisory.status === 'REJECTED'
                    ? 'var(--danger-100)'
                    : 'var(--warning-100)',
                color:
                  advisory.status === 'APPROVED'
                    ? 'var(--primary-700)'
                    : advisory.status === 'REJECTED'
                    ? 'var(--danger-600)'
                    : 'var(--warning-600)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <FileText size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2
                  id="advisory-detail-title"
                  style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink-900)' }}
                >
                  {advisory.panchayat_name} Gram Panchayat
                </h2>
                <StatusBadge status={advisory.status} size="sm" />
                <SeverityBadge severity={advisory.severity} size="sm" />
              </div>
              <p style={{ fontSize: '12px', color: 'var(--ink-500)', marginTop: '2px' }}>
                {[
                  advisory.block_name ? `${advisory.block_name} Block` : null,
                  advisory.district_name ? `${advisory.district_name} District` : null,
                  `Panchayat ID #${advisory.panchayat_id}`
                ].filter(Boolean).join(' • ')}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--ink-500)',
              padding: '4px',
            }}
            aria-label="Close detail modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div
          style={{
            padding: '24px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {/* Status Workflow Banner */}
          {advisory.status === 'DRAFT' && (
            <div
              style={{
                padding: '14px 16px',
                backgroundColor: 'var(--warning-100)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(199, 131, 24, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Clock size={20} color="var(--warning-600)" />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--warning-600)' }}>
                    Pending Extension Officer Review
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--ink-700)', marginTop: '2px' }}>
                    This advisory is a generated draft and will not reach farmers until approved.
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={() => onRequestApprove(advisory)}
                  className="btn-primary"
                  style={{ padding: '6px 14px', fontSize: '12px' }}
                >
                  <Check size={14} />
                  <span>Approve</span>
                </button>
                <button
                  onClick={() => onRequestReject(advisory)}
                  className="btn-danger"
                  style={{ padding: '6px 14px', fontSize: '12px' }}
                >
                  <XIcon size={14} />
                  <span>Reject</span>
                </button>
              </div>
            </div>
          )}

          {advisory.status === 'APPROVED' && (
            <div
              style={{
                padding: '14px 16px',
                backgroundColor: 'var(--primary-050)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--primary-100)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <CheckCircle2 size={20} color="var(--primary-700)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '6px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--primary-700)' }}>
                    ✓ Approved & Live on Farmer Mobile App
                  </span>
                  {advisory.approved_at && (
                    <span style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                      Approved at: {new Date(advisory.approved_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--ink-700)', marginTop: '4px' }}>
                  Reviewed by: <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong>
                  {advisory.officer_comment && (
                    <span style={{ fontStyle: 'italic', display: 'block', marginTop: '2px' }}>
                      "{advisory.officer_comment}"
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--ink-500)', marginTop: '6px' }}>
                  <Lock size={12} />
                  <span>Silent modifications are disabled to preserve audit integrity.</span>
                </div>
              </div>
            </div>
          )}

          {advisory.status === 'REJECTED' && (
            <div
              style={{
                padding: '14px 16px',
                backgroundColor: 'var(--danger-100)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--danger-300)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <XCircle size={20} color="var(--danger-600)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--danger-600)' }}>
                  ✗ Discarded by Reviewing Officer
                </div>
                <div style={{ fontSize: '12px', color: 'var(--ink-700)', marginTop: '4px' }}>
                  Reviewed by: <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong>
                  {advisory.officer_comment && (
                    <div style={{ marginTop: '3px', fontWeight: 600, color: 'var(--danger-600)' }}>
                      Reason: "{advisory.officer_comment}"
                    </div>
                  )}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
                  This draft is excluded from farmer services. Trigger a new downscaling inference run to produce an updated forecast.
                </div>
              </div>
            </div>
          )}

          {/* Meteorological Forecast Comparison Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
            {/* Block Baseline Card */}
            <div
              style={{
                backgroundColor: 'var(--surface-subtle)',
                padding: '16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
              }}
            >
              <div className="text-label" style={{ fontSize: '11px' }}>Official IMD Block Forecast</div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--ink-700)', marginTop: '4px' }}>
                {blockForecastMm} <span style={{ fontSize: '14px' }}>mm</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
                Baglan Block uniform 25-50km grid
              </div>
            </div>

            {/* Downscaled Prediction Card */}
            <div
              style={{
                backgroundColor: 'var(--primary-050)',
                padding: '16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--primary-100)',
              }}
            >
              <div className="text-label" style={{ fontSize: '11px', color: 'var(--primary-700)' }}>
                GramSevak Downscaled
              </div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--primary-700)', marginTop: '4px' }}>
                {downscaledMm} <span style={{ fontSize: '14px' }}>mm</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <TrendingUp size={13} />
                <span>Δ {varianceDelta >= 0 ? `+${varianceDelta}` : varianceDelta} mm difference</span>
              </div>
            </div>

            {/* Category & Severity Card */}
            <div
              style={{
                backgroundColor: 'var(--surface-subtle)',
                padding: '16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
              }}
            >
              <div className="text-label" style={{ fontSize: '11px' }}>IMD Rainfall Category</div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)', marginTop: '6px' }}>
                {advisory.rainfall_category}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
                Severity: <SeverityBadge severity={advisory.severity} size="sm" />
              </div>
            </div>
          </div>

          {/* Geospatial and Date Metadata Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              padding: '12px 16px',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--ink-300)',
              fontSize: '12px',
              color: 'var(--ink-700)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Calendar size={14} color="var(--primary-700)" />
              <span>Forecast Date: <strong>{advisory.forecast_date}</strong></span>
            </div>
            <span>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={14} color="var(--primary-700)" />
              <span>Issue Date: <strong>{issueDate}</strong></span>
            </div>
            <span>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <MapPin size={14} color="var(--primary-700)" />
              <span>Elevation: <strong>{advisory.elevation_m || 540} m</strong></span>
            </div>
            <span>•</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={14} color="var(--primary-700)" />
              <span>Rule Engine: <strong>{ruleVersion}</strong></span>
            </div>
          </div>

          {/* Agronomic Advisory Guidance Text */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={16} color="var(--primary-700)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink-900)', margin: 0 }}>
                  Agricultural Advisory Recommendation
                </h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
                <span style={{ backgroundColor: 'var(--primary-50)', color: 'var(--primary-800)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--primary-200)', fontWeight: 600 }}>
                  v{advisory.version || 1}
                </span>
                {advisory.advisory_source && (
                  <span style={{ backgroundColor: 'var(--surface-subtle)', color: 'var(--ink-700)', padding: '2px 8px', borderRadius: '4px', border: '1px solid var(--ink-300)' }}>
                    {advisory.advisory_source}
                  </span>
                )}
                {advisory.validation_status && (
                  <span style={{
                    backgroundColor: advisory.validation_status === 'VALIDATED' ? '#ECFDF5' : '#FEF2F2',
                    color: advisory.validation_status === 'VALIDATED' ? '#065F46' : '#991B1B',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    border: `1px solid ${advisory.validation_status === 'VALIDATED' ? '#A7F3D0' : '#FECACA'}`,
                    fontWeight: 600
                  }}>
                    {advisory.validation_status}
                  </span>
                )}
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--surface)',
                border: '1px solid var(--ink-300)',
                borderRadius: 'var(--radius-sm)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)' }}>
                {advisory.advisory_title}
              </div>
              <div
                style={{
                  fontSize: '13px',
                  color: 'var(--ink-700)',
                  lineHeight: '22px',
                  whiteSpace: 'pre-line',
                }}
              >
                {advisory.advisory_text}
              </div>
            </div>

            {/* If edited, show original content reference */}
            {advisory.original_content && advisory.original_content.advisory_text && (
              <details
                style={{
                  backgroundColor: 'var(--surface-subtle)',
                  border: '1px dashed var(--ink-300)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  fontSize: '12px',
                  color: 'var(--ink-600)',
                }}
              >
                <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--ink-700)' }}>
                  View Original System Generated Content (Prior to Officer Edits)
                </summary>
                <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--ink-200)' }}>
                  <div style={{ fontWeight: 600, color: 'var(--ink-800)', marginBottom: '4px' }}>
                    {advisory.original_content.advisory_title}
                  </div>
                  <div style={{ whiteSpace: 'pre-line', lineHeight: '18px' }}>
                    {advisory.original_content.advisory_text}
                  </div>
                </div>
              </details>
            )}
          </div>

          {/* Observation Note */}
          <div
            style={{
              fontSize: '12px',
              color: 'var(--ink-500)',
              backgroundColor: 'var(--surface-subtle)',
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <strong>Post-Event Verification:</strong> Ground observation stations (IMD AWS) record actual rainfall following lead-time completion for residual MAE/RMSE calibration.
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: 'var(--border-subtle)',
            backgroundColor: 'var(--surface-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <button
            onClick={onClose}
            className="btn-secondary"
            style={{ padding: '8px 16px', fontSize: '13px' }}
          >
            Close
          </button>

          {(advisory.status === 'DRAFT' || advisory.status === 'NEEDS_REVIEW' || advisory.status === 'EDITED') && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {onRequestEdit && (
                <button
                  onClick={() => onRequestEdit(advisory)}
                  className="btn-secondary"
                  style={{ padding: '8px 14px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Edit3 size={14} />
                  <span>Edit Advisory</span>
                </button>
              )}
              <button
                onClick={() => onRequestReject(advisory)}
                className="btn-danger"
                style={{ padding: '8px 14px', fontSize: '13px' }}
              >
                <XIcon size={14} />
                <span>Reject</span>
              </button>
              <button
                onClick={() => onRequestApprove(advisory)}
                className="btn-primary"
                style={{ padding: '8px 16px', fontSize: '13px' }}
              >
                <Check size={14} />
                <span>Approve for Farmers</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
