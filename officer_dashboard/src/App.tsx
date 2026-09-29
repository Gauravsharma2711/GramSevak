import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Clock, 
  CheckCircle2, 
  MapPin, 
  Calendar, 
  Compass,
  AlertTriangle
} from 'lucide-react';
import { AppShell } from './components/AppShell';
import { MetricCard } from './components/MetricCard';
import { WeatherHeroCard } from './components/WeatherHeroCard';
import { AdvisoryReviewQueue } from './components/AdvisoryReviewQueue';
import { PanchayatForecastSection } from './components/PanchayatForecastSection';
import { PanchayatGrid } from './components/PanchayatGrid';
import { AuditLogView } from './components/AuditLogView';
import { ApprovalConfirmModal } from './components/ApprovalConfirmModal';
import { RejectionModal } from './components/RejectionModal';
import { AdvisoryDetailModal } from './components/AdvisoryDetailModal';
import { ForecastGenerateModal } from './components/ForecastGenerateModal';
import { PanchayatDetailView } from './components/PanchayatDetailView';
import { WorkflowPipeline } from './components/common/WorkflowPipeline';
import { SkeletonLoader } from './components/common/SkeletonLoader';
import { ErrorState } from './components/common/ErrorState';
import { ApiService } from './services/api';
import { PanchayatItem, AdvisoryItem, DownscaledForecastDetail, OfficerEditPayload } from './types';
import { HierarchicalPanchayatSelector } from './components/HierarchicalPanchayatSelector';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'forecasts' | 'review' | 'audit' | 'panchayats'>('dashboard');
  const [panchayats, setPanchayats] = useState<PanchayatItem[]>([]);
  const [advisories, setAdvisories] = useState<AdvisoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Selected Panchayat for Detail Screen
  const [selectedPanchayatDetail, setSelectedPanchayatDetail] = useState<PanchayatItem | null>(null);

  // Modals state for review workflow
  const [selectedAdvisoryForApproval, setSelectedAdvisoryForApproval] = useState<AdvisoryItem | null>(null);
  const [selectedAdvisoryForRejection, setSelectedAdvisoryForRejection] = useState<AdvisoryItem | null>(null);
  const [selectedAdvisoryForDetail, setSelectedAdvisoryForDetail] = useState<AdvisoryItem | null>(null);

  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [preselectedPanchayatForGen, setPreselectedPanchayatForGen] = useState<PanchayatItem | null>(null);

  // Selected Jurisdiction State
  const [selectedDistrictId, setSelectedDistrictId] = useState<number | null>(null);
  const [selectedDistrictName, setSelectedDistrictName] = useState<string>('');
  const [selectedBlockId, setSelectedBlockId] = useState<number | null>(null);
  const [selectedBlockName, setSelectedBlockName] = useState<string | null>(null);

  // Notification Toast
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const forecastDate = '2026-09-09';

  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadData = async (filterBlock?: string) => {
    setError(null);
    try {
      const [panchayatRes, advisoriesRes, districtRes] = await Promise.all([
        ApiService.getPanchayats(filterBlock),
        ApiService.getOfficerAdvisories(),
        ApiService.getDistricts().catch(() => null),
      ]);
      setPanchayats(panchayatRes.items);
      setAdvisories(advisoriesRes);

      if (districtRes && districtRes.items && districtRes.items.length > 0) {
        setSelectedDistrictId((prevId) => {
          if (prevId != null) return prevId;
          const first = districtRes.items[0];
          setSelectedDistrictName(first.name);
          return first.id;
        });
      }
    } catch (err: any) {
      console.error('Error loading officer dashboard data:', err);
      setError('Unable to load latest advisory and downscaled forecast records from API.');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData(selectedBlockName || undefined);
  };

  // Submit Approval to backend
  const handleApproveAdvisory = async (advisoryId: number, comment: string) => {
    try {
      const updated = await ApiService.approveAdvisory(advisoryId, {
        officer_id: 'DR-S-PATIL-AO',
        officer_comment: comment || 'Verified against AWS ground trends. Approved for farmer distribution.',
      });
      showToast(`Advisory for ${updated.panchayat_name || 'Panchayat'} approved and published to Farmer App!`);
      await loadData();
    } catch (err: any) {
      showToast(`Approval failed: ${err.message}`, 'error');
      throw err;
    }
  };

  // Submit Rejection to backend
  const handleRejectAdvisory = async (advisoryId: number, reason: string) => {
    try {
      const updated = await ApiService.rejectAdvisory(advisoryId, {
        officer_id: 'DR-S-PATIL-AO',
        officer_comment: reason,
      });
      showToast(`Advisory for ${updated.panchayat_name || 'Panchayat'} rejected and logged in audit trail.`);
      await loadData();
    } catch (err: any) {
      showToast(`Rejection failed: ${err.message}`, 'error');
      throw err;
    }
  };

  // Submit Edit to backend
  const handleEditAdvisory = async (advisoryId: number, payload: OfficerEditPayload) => {
    try {
      const updated = await ApiService.editAdvisory(advisoryId, {
        ...payload,
        officer_id: payload.officer_id || 'DR-S-PATIL-AO',
      });
      showToast(`Advisory for ${updated.panchayat_name || 'Panchayat'} updated and queued for review.`);
      await loadData();
    } catch (err: any) {
      showToast(`Edit failed: ${err.message}`, 'error');
      throw err;
    }
  };

  // Trigger On-Demand Inference
  const handleGenerateForecast = async (
    panchayatId: number,
    targetDate: string,
    issueDate: string
  ): Promise<DownscaledForecastDetail> => {
    const res = await ApiService.generateForecast({
      panchayat_id: panchayatId,
      forecast_date: targetDate,
      forecast_issue_date: issueDate,
    });
    showToast(`Downscaled forecast generated for ${res.panchayat_name}!`);
    await loadData();
    return res;
  };

  const draftCount = advisories.filter((a) => a.status === 'DRAFT').length;
  const approvedCount = advisories.filter((a) => a.status === 'APPROVED').length;
  const totalForecastsAvailable = panchayats.length;

  const activeDetailAdvisory = selectedPanchayatDetail
    ? advisories.find((a) => a.panchayat_id === selectedPanchayatDetail.panchayat_id)
    : null;

  return (
    <AppShell
      currentTab={currentTab}
      onSelectTab={(tab) => {
        setSelectedPanchayatDetail(null);
        setCurrentTab(tab);
      }}
      pendingCount={draftCount}
      onOpenGenerateModal={() => {
        setPreselectedPanchayatForGen(null);
        setIsGenerateModalOpen(true);
      }}
      onRefresh={handleRefresh}
      isRefreshing={isRefreshing}
      forecastDate={forecastDate}
      selectedDistrictName={selectedDistrictName}
      selectedBlockName={selectedBlockName}
      selectedPanchayatName={selectedPanchayatDetail?.panchayat_name}
      headerSelectorSlot={
        <HierarchicalPanchayatSelector
          selectedDistrictId={selectedDistrictId}
          selectedBlockId={selectedBlockId}
          selectedPanchayatId={selectedPanchayatDetail?.panchayat_id}
          onDistrictChange={(id, name) => {
            setSelectedDistrictId(id);
            setSelectedDistrictName(name);
            setSelectedBlockId(null);
            setSelectedBlockName(null);
            setSelectedPanchayatDetail(null);
            loadData();
          }}
          onBlockChange={(id, name) => {
            setSelectedBlockId(id);
            setSelectedBlockName(name);
            setSelectedPanchayatDetail(null);
            loadData(name || undefined);
          }}
          onSelectPanchayat={(p) => {
            setSelectedPanchayatDetail(p);
            setSelectedDistrictName(p.district_name);
            setSelectedBlockName(p.block_name);
            showToast(`Loaded live Panchayat: ${p.panchayat_name} (${p.block_name} Block)`);
          }}
          onClearSelection={() => {
            setSelectedPanchayatDetail(null);
            setSelectedBlockId(null);
            setSelectedBlockName(null);
            loadData();
          }}
        />
      }
    >
      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: 'fixed',
            bottom: '16px',
            right: '16px',
            maxWidth: 'calc(100vw - 32px)',
            backgroundColor: toastMessage.type === 'error' ? 'var(--danger-600)' : 'var(--ink-900)',
            color: 'var(--surface)',
            padding: '10px 16px',
            borderRadius: 'var(--radius-pill)',
            boxShadow: 'var(--shadow-modal)',
            fontSize: '12px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            zIndex: 100,
            animation: 'fadeIn 0.2s ease',
          }}
          role="status"
        >
          {toastMessage.type === 'error' ? (
            <AlertTriangle size={15} color="#FFFFFF" style={{ flexShrink: 0 }} />
          ) : (
            <CheckCircle2 size={15} color="var(--primary-500)" style={{ flexShrink: 0 }} />
          )}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{toastMessage.text}</span>
        </div>
      )}

      {/* Loading State */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <SkeletonLoader type="metric" count={4} />
          <SkeletonLoader type="card" count={3} />
        </div>
      ) : error ? (
        /* Error State */
        <ErrorState
          title="Connection Error"
          message={error}
          onRetry={loadData}
        />
      ) : selectedPanchayatDetail ? (
        /* PANCHAYAT DETAIL SCREEN */
        <PanchayatDetailView
          panchayat={selectedPanchayatDetail}
          advisory={activeDetailAdvisory}
          onBack={() => setSelectedPanchayatDetail(null)}
          onApproveAdvisory={(adv) => setSelectedAdvisoryForApproval(adv)}
          onRejectAdvisory={(adv) => setSelectedAdvisoryForRejection(adv)}
          onOpenGenerateModal={(p) => {
            setPreselectedPanchayatForGen(p);
            setIsGenerateModalOpen(true);
          }}
        />
      ) : (
        /* Active Tab Content */
        <>
          {/* TAB 1: DASHBOARD OVERVIEW */}
          {currentTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }} className="fade-in">
              {/* 1. Location Context & Priority Action Banner */}
              <section aria-label="Jurisdiction Status & Operational Metrics">
                {/* Priority Operational Alert Callout */}
                {draftCount > 0 ? (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '12px',
                      backgroundColor: 'var(--warning-100)',
                      border: '1px solid rgba(199, 131, 24, 0.3)',
                      padding: '12px 18px',
                      borderRadius: 'var(--radius-md)',
                      marginBottom: '16px',
                    }}
                    role="alert"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Clock size={18} color="var(--warning-600)" style={{ flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-900)' }}>
                          {draftCount} Advisory Recommendation{draftCount > 1 ? 's' : ''} Awaiting Officer Verification
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--ink-700)', marginTop: '2px' }}>
                          Downscaled predictions generated. Human approval required before farmer mobile distribution.
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => setCurrentTab('review')}
                      className="btn-primary"
                      style={{
                        padding: '6px 14px',
                        fontSize: '12px',
                        backgroundColor: 'var(--warning-600)',
                        minHeight: '34px',
                      }}
                    >
                      Inspect Queue ({draftCount})
                    </button>
                  </div>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '12px',
                      backgroundColor: 'var(--surface)',
                      border: 'var(--border-subtle)',
                      padding: '10px 16px',
                      borderRadius: 'var(--radius-md)',
                      marginBottom: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={16} color="var(--primary-600)" />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink-900)' }}>
                        All Advisories Cleared & Active on Farmer App
                      </span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                      100% units synchronized for {forecastDate}
                    </span>
                  </div>
                )}

                {/* KPI Metrics Cards */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(160px, 100%), 1fr))',
                    gap: '14px',
                  }}
                >
                  {/* 1. District & Jurisdiction */}
                  <MetricCard
                    label="Active District"
                    value={selectedDistrictName}
                    subtext={selectedBlockName ? `${selectedBlockName} Block Jurisdiction` : 'All District Blocks'}
                    icon={<MapPin size={20} />}
                    accentColor="var(--primary-700)"
                  />

                  {/* 2. Forecast Date & Availability */}
                  <MetricCard
                    label="Forecast Date"
                    value={forecastDate}
                    subtext={`${totalForecastsAvailable} Monitored Units`}
                    icon={<Calendar size={20} />}
                    trend={{
                      text: '100% Synced',
                      isPositive: true,
                    }}
                    accentColor="var(--primary-600)"
                  />

                  {/* 3. Panchayat Count */}
                  <MetricCard
                    label="Panchayats in Scope"
                    value={panchayats.length}
                    subtext={selectedBlockName ? `Active in ${selectedBlockName} Block` : `Monitored in ${selectedDistrictName}`}
                    icon={<Building2 size={20} />}
                    accentColor="var(--primary-700)"
                  />

                  {/* 4. Advisories Pending Review */}
                  <MetricCard
                    label="Pending Review"
                    value={draftCount}
                    subtext="Officer approval needed"
                    icon={<Clock size={20} />}
                    trend={{
                      text: draftCount > 0 ? `${draftCount} Pending` : 'All Clear',
                      isPositive: draftCount === 0,
                      color: draftCount > 0 ? 'var(--warning-600)' : 'var(--primary-700)',
                    }}
                    accentColor="var(--warning-600)"
                  />

                  {/* 5. Approved Advisories */}
                  <MetricCard
                    label="Approved Advisories"
                    value={approvedCount}
                    subtext="Active on Farmer App"
                    icon={<CheckCircle2 size={20} />}
                    trend={{
                      text: 'Verified by Officer',
                      isPositive: true,
                    }}
                    accentColor="var(--primary-700)"
                  />
                </div>
              </section>

              {/* 2. Key Forecast Summary: Downscaling Variance Centerpiece */}
              <WeatherHeroCard
                advisories={advisories}
                blockName={selectedBlockName || (panchayats[0]?.block_name) || 'All Blocks'}
                onReviewClick={(advisory) => {
                  setSelectedAdvisoryForDetail(advisory);
                }}
              />

              {/* 3. Agricultural / Advisory Information: Priority Review Queue */}
              <section aria-label="Priority Advisory Review Queue">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
                  <div>
                    <h2 className="text-section-title">Priority Advisory Review Queue</h2>
                    <p className="text-body" style={{ fontSize: '13px', color: 'var(--ink-500)' }}>
                      Inspect and validate deterministic agricultural advisories before mobile delivery.
                    </p>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => setCurrentTab('forecasts')}
                      className="btn-secondary"
                      style={{ padding: '6px 12px', fontSize: '12px' }}
                    >
                      <Compass size={13} />
                      <span>All Forecasts</span>
                    </button>
                    <button
                      onClick={() => setCurrentTab('review')}
                      className="btn-primary"
                      style={{ padding: '6px 12px', fontSize: '12px' }}
                    >
                      <span>Full Queue ({advisories.length})</span>
                    </button>
                  </div>
                </div>

                <AdvisoryReviewQueue
                  advisories={advisories}
                  onApproveAdvisory={handleApproveAdvisory}
                  onRejectAdvisory={handleRejectAdvisory}
                  onEditAdvisory={handleEditAdvisory}
                />
              </section>

              {/* 4. Supporting Information: Methodology & Protocol Pipeline (Quiet / Collapsible) */}
              <WorkflowPipeline />
            </div>
          )}

          {/* TAB 2: PANCHAYAT FORECASTS SECTION */}
          {currentTab === 'forecasts' && (
            <div className="fade-in">
              <PanchayatForecastSection
                panchayats={panchayats}
                advisories={advisories}
                onReviewAdvisory={(a) => {
                  setSelectedAdvisoryForDetail(a);
                }}
                onSelectPanchayat={(p) => {
                  setSelectedPanchayatDetail(p);
                }}
                onGenerateForecast={(p) => {
                  setPreselectedPanchayatForGen(p);
                  setIsGenerateModalOpen(true);
                }}
              />
            </div>
          )}

          {/* TAB 3: ADVISORY REVIEW SECTION */}
          {currentTab === 'review' && (
            <div className="fade-in">
              <AdvisoryReviewQueue
                advisories={advisories}
                onApproveAdvisory={handleApproveAdvisory}
                onRejectAdvisory={handleRejectAdvisory}
                onEditAdvisory={handleEditAdvisory}
              />
            </div>
          )}

          {/* TAB 4: PANCHAYAT GEOSPATIAL DIRECTORY */}
          {currentTab === 'panchayats' && (
            <div className="fade-in">
              <PanchayatGrid
                panchayats={panchayats}
                onSelectPanchayat={(p) => {
                  setSelectedPanchayatDetail(p);
                }}
                onGenerateForPanchayat={(p) => {
                  setPreselectedPanchayatForGen(p);
                  setIsGenerateModalOpen(true);
                }}
              />
            </div>
          )}

          {/* TAB 5: AUDIT LOG */}
          {currentTab === 'audit' && (
            <div className="fade-in">
              <AuditLogView advisories={advisories} />
            </div>
          )}
        </>
      )}

      {/* Modal: Advisory Full Detail View */}
      <AdvisoryDetailModal
        advisory={selectedAdvisoryForDetail}
        isOpen={Boolean(selectedAdvisoryForDetail)}
        onClose={() => setSelectedAdvisoryForDetail(null)}
        onRequestApprove={(adv) => {
          setSelectedAdvisoryForDetail(null);
          setSelectedAdvisoryForApproval(adv);
        }}
        onRequestReject={(adv) => {
          setSelectedAdvisoryForDetail(null);
          setSelectedAdvisoryForRejection(adv);
        }}
      />

      {/* Modal: Advisory Approval Confirmation Dialog */}
      <ApprovalConfirmModal
        advisory={selectedAdvisoryForApproval}
        isOpen={Boolean(selectedAdvisoryForApproval)}
        onClose={() => setSelectedAdvisoryForApproval(null)}
        onConfirmApprove={handleApproveAdvisory}
      />

      {/* Modal: Advisory Rejection Dialog */}
      <RejectionModal
        advisory={selectedAdvisoryForRejection}
        isOpen={Boolean(selectedAdvisoryForRejection)}
        onClose={() => setSelectedAdvisoryForRejection(null)}
        onConfirmReject={handleRejectAdvisory}
      />

      {/* Modal: On-Demand ML Inference */}
      <ForecastGenerateModal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        panchayats={panchayats}
        preselectedPanchayat={preselectedPanchayatForGen}
        onGenerate={handleGenerateForecast}
      />
    </AppShell>
  );
};
