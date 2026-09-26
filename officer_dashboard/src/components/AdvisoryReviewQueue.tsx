import React, { useState } from 'react';
import { 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Search, 
  Calendar,
  Eye,
  Check,
  X,
  FileCheck2,
  Lock,
  AlertCircle
} from 'lucide-react';
import { AdvisoryItem } from '../types';
import { StatusBadge } from './common/StatusBadge';
import { SeverityBadge } from './common/SeverityBadge';
import { ForecastValue } from './common/ForecastValue';
import { EmptyState } from './common/EmptyState';
import { AdvisoryDetailModal } from './AdvisoryDetailModal';
import { ApprovalConfirmModal } from './ApprovalConfirmModal';
import { RejectionModal } from './RejectionModal';

interface AdvisoryReviewQueueProps {
  advisories: AdvisoryItem[];
  onApproveAdvisory: (advisoryId: number, comment: string) => Promise<void>;
  onRejectAdvisory: (advisoryId: number, reason: string) => Promise<void>;
}

export const AdvisoryReviewQueue: React.FC<AdvisoryReviewQueueProps> = ({
  advisories,
  onApproveAdvisory,
  onRejectAdvisory,
}) => {
  const [activeStatus, setActiveStatus] = useState<'ALL' | 'DRAFT' | 'APPROVED' | 'REJECTED'>('DRAFT');
  const [search, setSearch] = useState('');

  // Modals state
  const [detailAdvisory, setDetailAdvisory] = useState<AdvisoryItem | null>(null);
  const [approvalAdvisory, setApprovalAdvisory] = useState<AdvisoryItem | null>(null);
  const [rejectionAdvisory, setRejectionAdvisory] = useState<AdvisoryItem | null>(null);

  const draftCount = advisories.filter((a) => a.status === 'DRAFT').length;
  const approvedCount = advisories.filter((a) => a.status === 'APPROVED').length;
  const rejectedCount = advisories.filter((a) => a.status === 'REJECTED').length;

  const filteredAdvisories = advisories.filter((a) => {
    const matchesStatus = activeStatus === 'ALL' || a.status === activeStatus;
    const matchesSearch =
      (a.panchayat_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (a.block_name || '').toLowerCase().includes(search.toLowerCase()) ||
      (a.advisory_title || '').toLowerCase().includes(search.toLowerCase()) ||
      (a.rainfall_category || '').toLowerCase().includes(search.toLowerCase()) ||
      String(a.panchayat_id).includes(search);
    return matchesStatus && matchesSearch;
  });

  const handleOpenApproveModal = (advisory: AdvisoryItem) => {
    setDetailAdvisory(null);
    setApprovalAdvisory(advisory);
  };

  const handleOpenRejectModal = (advisory: AdvisoryItem) => {
    setDetailAdvisory(null);
    setRejectionAdvisory(advisory);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Filter and Search Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          width: '100%',
        }}
      >
        {/* Status Tabs with Horizontal Scroll Support */}
        <div style={{ maxWidth: '100%', overflowX: 'auto', paddingBottom: '2px' }}>
          <div
            style={{
              display: 'inline-flex',
              backgroundColor: 'var(--surface-subtle)',
              padding: '4px',
              borderRadius: 'var(--radius-pill)',
              border: '1px solid var(--ink-300)',
              whiteSpace: 'nowrap',
            }}
            role="tablist"
            aria-label="Advisory Review Status Tabs"
          >
            {/* DRAFT / Pending Review Tab */}
            <button
              onClick={() => setActiveStatus('DRAFT')}
              role="tab"
              aria-selected={activeStatus === 'DRAFT'}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                border: 'none',
                backgroundColor: activeStatus === 'DRAFT' ? 'var(--surface)' : 'transparent',
                color: activeStatus === 'DRAFT' ? 'var(--warning-600)' : 'var(--ink-700)',
                fontWeight: activeStatus === 'DRAFT' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: activeStatus === 'DRAFT' ? 'var(--shadow-subtle)' : 'none',
                transition: 'all 0.15s ease',
                minHeight: '36px',
              }}
            >
              <Clock size={13} />
              <span>Pending Review</span>
              <span
                style={{
                  backgroundColor: 'var(--warning-100)',
                  color: 'var(--warning-600)',
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '10px',
                  fontWeight: 700,
                }}
              >
                {draftCount}
              </span>
            </button>

            {/* APPROVED Tab */}
            <button
              onClick={() => setActiveStatus('APPROVED')}
              role="tab"
              aria-selected={activeStatus === 'APPROVED'}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                border: 'none',
                backgroundColor: activeStatus === 'APPROVED' ? 'var(--surface)' : 'transparent',
                color: activeStatus === 'APPROVED' ? 'var(--primary-700)' : 'var(--ink-700)',
                fontWeight: activeStatus === 'APPROVED' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: activeStatus === 'APPROVED' ? 'var(--shadow-subtle)' : 'none',
                transition: 'all 0.15s ease',
                minHeight: '36px',
              }}
            >
              <CheckCircle2 size={13} />
              <span>Approved</span>
              <span
                style={{
                  backgroundColor: 'var(--primary-100)',
                  color: 'var(--primary-700)',
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '10px',
                  fontWeight: 700,
                }}
              >
                {approvedCount}
              </span>
            </button>

            {/* REJECTED Tab */}
            <button
              onClick={() => setActiveStatus('REJECTED')}
              role="tab"
              aria-selected={activeStatus === 'REJECTED'}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                border: 'none',
                backgroundColor: activeStatus === 'REJECTED' ? 'var(--surface)' : 'transparent',
                color: activeStatus === 'REJECTED' ? 'var(--danger-600)' : 'var(--ink-700)',
                fontWeight: activeStatus === 'REJECTED' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: activeStatus === 'REJECTED' ? 'var(--shadow-subtle)' : 'none',
                transition: 'all 0.15s ease',
                minHeight: '36px',
              }}
            >
              <XCircle size={13} />
              <span>Rejected</span>
              <span
                style={{
                  backgroundColor: 'var(--danger-100)',
                  color: 'var(--danger-600)',
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '10px',
                  fontWeight: 700,
                }}
              >
                {rejectedCount}
              </span>
            </button>

            {/* ALL Tab */}
            <button
              onClick={() => setActiveStatus('ALL')}
              role="tab"
              aria-selected={activeStatus === 'ALL'}
              style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                border: 'none',
                backgroundColor: activeStatus === 'ALL' ? 'var(--surface)' : 'transparent',
                color: activeStatus === 'ALL' ? 'var(--ink-900)' : 'var(--ink-700)',
                fontWeight: activeStatus === 'ALL' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
                boxShadow: activeStatus === 'ALL' ? 'var(--shadow-subtle)' : 'none',
                transition: 'all 0.15s ease',
                minHeight: '36px',
              }}
            >
              <span>All ({advisories.length})</span>
            </button>
          </div>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', flex: 1, minWidth: '200px', maxWidth: '360px' }}>
          <Search
            size={15}
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--ink-500)',
            }}
          />
          <input
            type="text"
            placeholder="Search advisory, crop, village..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field"
            style={{ paddingLeft: '34px', fontSize: '13px' }}
            aria-label="Search advisories"
          />
        </div>
      </div>

      {/* Advisory Cards List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {filteredAdvisories.length === 0 ? (
          <EmptyState
            icon={FileCheck2}
            title={activeStatus === 'DRAFT' ? 'All Advisories Reviewed' : 'No Advisories in this View'}
            description={
              activeStatus === 'DRAFT'
                ? 'Great job! There are no pending draft advisories awaiting officer inspection.'
                : 'No advisory records found matching the active filter criteria or search query.'
            }
            actionText={search ? 'Clear Search' : undefined}
            onAction={search ? () => setSearch('') : undefined}
          />
        ) : (
          filteredAdvisories.map((advisory) => (
            <div
              key={advisory.id}
              className="app-card app-card-interactive"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                borderLeft:
                  advisory.status === 'APPROVED'
                    ? '4px solid var(--primary-500)'
                    : advisory.status === 'REJECTED'
                    ? '4px solid var(--danger-600)'
                    : '4px solid var(--warning-600)',
              }}
            >
              {/* Top Row: Panchayat info, Forecast Date, Status & Severity Badges */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink-900)' }}>
                    {advisory.panchayat_name} Gram Panchayat
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                    ({advisory.block_name || 'Jurisdiction'} Block • #{advisory.panchayat_id})
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--ink-500)' }}>
                    <Calendar size={13} />
                    <span>Target: <strong>{advisory.forecast_date}</strong></span>
                  </div>

                  <SeverityBadge severity={advisory.severity} size="sm" />
                  <StatusBadge status={advisory.status} size="sm" />
                </div>
              </div>

              {/* Middle Row: Downscaled Rainfall & Advisory Content Preview */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '14px',
                  backgroundColor: 'var(--surface-subtle)',
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <div style={{ flex: '1 1 240px', minWidth: 0 }}>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink-900)' }}>
                    {advisory.advisory_title}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--ink-700)', marginTop: '4px', whiteSpace: 'pre-line', lineHeight: '19px' }}>
                    {advisory.advisory_text.split('\n').slice(0, 2).join('\n')}
                    {advisory.advisory_text.split('\n').length > 2 && '...'}
                  </div>
                </div>

                {/* Downscaled Rainfall Value Tile */}
                <div style={{ textAlign: 'left', minWidth: '120px', flex: '0 0 auto' }}>
                  <div className="text-label" style={{ fontSize: '10px' }}>Downscaled Rain</div>
                  <ForecastValue rainfallMm={advisory.rainfall_mm} size="md" />
                  <div style={{ fontSize: '11px', color: 'var(--ink-500)', marginTop: '2px' }}>
                    {advisory.rainfall_category}
                  </div>
                </div>
              </div>

              {/* Bottom Row: Status Metadata & Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ fontSize: '12px', color: 'var(--ink-500)', flex: '1 1 200px' }}>
                  {advisory.status === 'APPROVED' && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--primary-700)' }}>
                      <CheckCircle2 size={14} style={{ flexShrink: 0 }} />
                      <span>
                        Verified by <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong>
                        {advisory.officer_comment && ` — "${advisory.officer_comment}"`}
                      </span>
                    </span>
                  )}

                  {advisory.status === 'REJECTED' && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--danger-600)' }}>
                      <XCircle size={14} style={{ flexShrink: 0 }} />
                      <span>
                        Rejected by <strong>{advisory.officer_id || 'DR-S-PATIL-AO'}</strong>
                        {advisory.officer_comment && ` — "${advisory.officer_comment}"`}
                      </span>
                    </span>
                  )}

                  {advisory.status === 'DRAFT' && (
                    <span style={{ color: 'var(--warning-600)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={14} style={{ flexShrink: 0 }} />
                      <span>Awaiting officer approval.</span>
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => setDetailAdvisory(advisory)}
                    className="btn-secondary"
                    style={{ padding: '8px 14px', fontSize: '12px', minHeight: '36px' }}
                    aria-label={`View full details for ${advisory.panchayat_name}`}
                  >
                    <Eye size={13} />
                    <span>View Detail</span>
                  </button>

                  {advisory.status === 'DRAFT' && (
                    <>
                      <button
                        onClick={() => handleOpenApproveModal(advisory)}
                        className="btn-primary"
                        style={{ padding: '8px 14px', fontSize: '12px', minHeight: '36px' }}
                        aria-label={`Approve advisory for ${advisory.panchayat_name}`}
                      >
                        <Check size={13} />
                        <span>Approve</span>
                      </button>

                      <button
                        onClick={() => handleOpenRejectModal(advisory)}
                        className="btn-danger"
                        style={{ padding: '8px 14px', fontSize: '12px', minHeight: '36px' }}
                        aria-label={`Reject advisory for ${advisory.panchayat_name}`}
                      >
                        <X size={13} />
                        <span>Reject</span>
                      </button>
                    </>
                  )}

                  {advisory.status === 'APPROVED' && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '11px',
                        color: 'var(--primary-700)',
                        backgroundColor: 'var(--primary-050)',
                        padding: '6px 12px',
                        borderRadius: 'var(--radius-pill)',
                        fontWeight: 600,
                      }}
                    >
                      <Lock size={12} />
                      <span>Active on App</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Advisory Detail Modal */}
      <AdvisoryDetailModal
        advisory={detailAdvisory}
        isOpen={Boolean(detailAdvisory)}
        onClose={() => setDetailAdvisory(null)}
        onRequestApprove={(adv) => handleOpenApproveModal(adv)}
        onRequestReject={(adv) => handleOpenRejectModal(adv)}
      />

      {/* Approval Confirmation Dialog */}
      <ApprovalConfirmModal
        advisory={approvalAdvisory}
        isOpen={Boolean(approvalAdvisory)}
        onClose={() => setApprovalAdvisory(null)}
        onConfirmApprove={onApproveAdvisory}
      />

      {/* Rejection Dialog with Mandatory Reason */}
      <RejectionModal
        advisory={rejectionAdvisory}
        isOpen={Boolean(rejectionAdvisory)}
        onClose={() => setRejectionAdvisory(null)}
        onConfirmReject={onRejectAdvisory}
      />
    </div>
  );
};
