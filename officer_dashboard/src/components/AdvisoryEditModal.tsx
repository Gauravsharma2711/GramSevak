import React, { useState } from 'react';
import { X, Edit3, AlertTriangle, Save, Info } from 'lucide-react';
import { AdvisoryItem, OfficerEditPayload } from '../types';

interface AdvisoryEditModalProps {
  advisory: AdvisoryItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSaveEdit: (advisoryId: number, payload: OfficerEditPayload) => Promise<void>;
}

export const AdvisoryEditModal: React.FC<AdvisoryEditModalProps> = ({
  advisory,
  isOpen,
  onClose,
  onSaveEdit,
}) => {
  if (!isOpen || !advisory) return null;

  const [title, setTitle] = useState(advisory.advisory_title || '');
  const [text, setText] = useState(advisory.advisory_text || '');
  const [severity, setSeverity] = useState<string>(advisory.severity || 'MODERATE');
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !text.trim()) {
      setErrorMessage('Advisory title and guidance text are required.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await onSaveEdit(advisory.id, {
        officer_id: advisory.officer_id || 'OFFICER_REVIEWER',
        advisory_title: title.trim(),
        advisory_text: text.trim(),
        severity: severity as any,
        officer_comment: comment.trim() || undefined,
        version: advisory.version || 1,
      });
      onClose();
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to save advisory edits.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(30, 40, 35, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 60,
        padding: '20px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-advisory-title"
    >
      <div
        style={{
          backgroundColor: 'var(--surface)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-modal)',
          maxWidth: '680px',
          width: '100%',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid var(--ink-300)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: 'var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'var(--surface-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--primary-100)',
                color: 'var(--primary-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Edit3 size={18} />
            </div>
            <div>
              <h2
                id="edit-advisory-title"
                style={{ fontSize: '17px', fontWeight: 700, color: 'var(--ink-900)', margin: 0 }}
              >
                Edit Advisory Guidance
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--ink-500)', marginTop: '2px' }}>
                Panchayat: <strong>{advisory.panchayat_name || `ID ${advisory.panchayat_id}`}</strong> • Current Version: <strong>v{advisory.version || 1}</strong>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--ink-500)',
              padding: '6px',
            }}
            aria-label="Close edit modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Immutability Notice Banner */}
          <div
            style={{
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              borderRadius: 'var(--radius-sm)',
              padding: '12px 14px',
              display: 'flex',
              gap: '10px',
              fontSize: '12px',
              color: '#1E40AF',
              lineHeight: '18px',
            }}
          >
            <Info size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
            <div>
              <strong>Forecast Grounding Guarantee:</strong> You are editing advisory recommendations and wording only. The underlying downscaled rainfall (<strong>{advisory.rainfall_mm} mm</strong>) and meteorological forecast are immutable.
            </div>
          </div>

          {errorMessage && (
            <div
              style={{
                backgroundColor: 'var(--danger-50)',
                border: '1px solid var(--danger-300)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px 14px',
                display: 'flex',
                gap: '10px',
                fontSize: '12px',
                color: 'var(--danger-700)',
                lineHeight: '18px',
              }}
            >
              <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
              <div>
                <strong>Validation or Conflict Error:</strong> {errorMessage}
              </div>
            </div>
          )}

          {/* Title */}
          <div>
            <label
              htmlFor="edit-advisory-title-input"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink-800)', marginBottom: '6px' }}
            >
              Advisory Headline
            </label>
            <input
              id="edit-advisory-title-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
                fontSize: '14px',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-900)',
                outline: 'none',
              }}
              required
            />
          </div>

          {/* Severity */}
          <div>
            <label
              htmlFor="edit-advisory-severity-select"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink-800)', marginBottom: '6px' }}
            >
              Severity Level
            </label>
            <select
              id="edit-advisory-severity-select"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
                fontSize: '14px',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-900)',
                outline: 'none',
              }}
            >
              <option value="LOW">LOW</option>
              <option value="MODERATE">MODERATE</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          {/* Text / Actionable Recommendations */}
          <div>
            <label
              htmlFor="edit-advisory-text-input"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink-800)', marginBottom: '6px' }}
            >
              Agricultural Guidance & Action Points
            </label>
            <textarea
              id="edit-advisory-text-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={isSubmitting}
              rows={6}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
                fontSize: '13px',
                lineHeight: '20px',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-900)',
                outline: 'none',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
              required
            />
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '4px' }}>
              Safety note: Chemical mixing ratios, medical claims, and unfounded disease diagnoses are prohibited.
            </div>
          </div>

          {/* Officer Edit Rationale */}
          <div>
            <label
              htmlFor="edit-advisory-comment-input"
              style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink-800)', marginBottom: '6px' }}
            >
              Officer Amendment Note (Recorded in Audit Trail)
            </label>
            <input
              id="edit-advisory-comment-input"
              type="text"
              placeholder="e.g., Emphasized sugarcane drainage due to black soil saturation"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-300)',
                fontSize: '13px',
                backgroundColor: 'var(--surface)',
                color: 'var(--ink-900)',
                outline: 'none',
              }}
            />
          </div>

          {/* Modal Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '10px',
              marginTop: '10px',
              paddingTop: '16px',
              borderTop: 'var(--border-subtle)',
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="btn-secondary"
              style={{ padding: '8px 16px', fontSize: '13px' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary"
              style={{ padding: '8px 18px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Save size={15} />
              <span>{isSubmitting ? 'Saving...' : 'Save & Queue for Review'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
