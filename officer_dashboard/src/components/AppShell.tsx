import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  FileCheck2, 
  CloudRain, 
  Building2, 
  History, 
  Sparkles, 
  ShieldCheck, 
  RefreshCw,
  MapPin,
  Menu,
  X,
  Compass
} from 'lucide-react';
import { DemoPanchayatSelector } from './DemoPanchayatSelector';
import { PanchayatItem } from '../types';

interface AppShellProps {
  currentTab: 'dashboard' | 'forecasts' | 'review' | 'audit' | 'panchayats';
  onSelectTab: (tab: 'dashboard' | 'forecasts' | 'review' | 'audit' | 'panchayats') => void;
  pendingCount: number;
  onOpenGenerateModal: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  forecastDate: string;
  selectedDistrictName?: string;
  selectedBlockName?: string | null;
  selectedPanchayatName?: string | null;
  headerSelectorSlot?: React.ReactNode;
  onSelectDemoPanchayat?: (panchayat: PanchayatItem) => void;
  selectedDemoPanchayatId?: number | null;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  currentTab,
  onSelectTab,
  pendingCount,
  onOpenGenerateModal,
  onRefresh,
  isRefreshing,
  forecastDate,
  selectedDistrictName = 'Nashik',
  selectedBlockName,
  selectedPanchayatName,
  headerSelectorSlot,
  onSelectDemoPanchayat,
  selectedDemoPanchayatId,
  children,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNavClick = (tab: 'dashboard' | 'forecasts' | 'review' | 'audit' | 'panchayats') => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  // Close drawer on ESC key
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  const renderNavContent = () => (
    <>
      {/* Brand Header */}
      <div
        style={{
          padding: '20px',
          borderBottom: 'var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--primary-050)',
              border: '1px solid var(--primary-100)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--primary-700)',
              flexShrink: 0,
            }}
          >
            <CloudRain size={22} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '18px', color: 'var(--primary-700)', lineHeight: '22px' }}>
              GramSevak
            </div>
            <div style={{ fontSize: '11px', color: 'var(--ink-500)', fontWeight: 500 }}>
              Officer Agro-Advisory Portal
            </div>
          </div>
        </div>

        {/* Close Button inside Mobile Drawer */}
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="btn-secondary show-on-mobile"
          style={{ padding: '6px', minHeight: '36px', borderRadius: 'var(--radius-sm)' }}
          aria-label="Close navigation menu"
        >
          <X size={18} />
        </button>
      </div>

      {/* Region Scope Jurisdiction Card */}
      <div style={{ padding: '16px 16px 8px 16px' }}>
        <div
          style={{
            backgroundColor: 'var(--surface-subtle)',
            border: '1px solid var(--ink-100)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <MapPin size={16} color="var(--primary-600)" style={{ flexShrink: 0 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '10px', color: 'var(--ink-500)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}>
              Jurisdiction Scope
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {selectedDistrictName} • {selectedBlockName ? `${selectedBlockName} Block` : 'All Blocks'}
            </div>
            {selectedPanchayatName && (
              <div style={{ fontSize: '11px', color: 'var(--primary-700)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                › {selectedPanchayatName} GP
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Navigation Items */}
      <nav style={{ flex: 1, padding: '12px', display: 'flex', flexDirection: 'column', gap: '4px', overflowY: 'auto' }}>
        <button
          onClick={() => handleNavClick('dashboard')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: currentTab === 'dashboard' ? 'var(--primary-050)' : 'transparent',
            color: currentTab === 'dashboard' ? 'var(--primary-700)' : 'var(--ink-700)',
            fontWeight: currentTab === 'dashboard' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            textAlign: 'left',
            width: '100%',
            transition: 'all 0.15s ease',
            minHeight: '44px',
          }}
          aria-current={currentTab === 'dashboard' ? 'page' : undefined}
        >
          <LayoutDashboard size={18} strokeWidth={currentTab === 'dashboard' ? 2.2 : 1.75} />
          <span>Dashboard Overview</span>
        </button>

        <button
          onClick={() => handleNavClick('forecasts')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: currentTab === 'forecasts' ? 'var(--primary-050)' : 'transparent',
            color: currentTab === 'forecasts' ? 'var(--primary-700)' : 'var(--ink-700)',
            fontWeight: currentTab === 'forecasts' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            textAlign: 'left',
            width: '100%',
            transition: 'all 0.15s ease',
            minHeight: '44px',
          }}
          aria-current={currentTab === 'forecasts' ? 'page' : undefined}
        >
          <Compass size={18} strokeWidth={currentTab === 'forecasts' ? 2.2 : 1.75} />
          <span>Panchayat Forecasts</span>
        </button>

        <button
          onClick={() => handleNavClick('review')}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 14px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: currentTab === 'review' ? 'var(--primary-050)' : 'transparent',
            color: currentTab === 'review' ? 'var(--primary-700)' : 'var(--ink-700)',
            fontWeight: currentTab === 'review' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            width: '100%',
            transition: 'all 0.15s ease',
            minHeight: '44px',
          }}
          aria-current={currentTab === 'review' ? 'page' : undefined}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <FileCheck2 size={18} strokeWidth={currentTab === 'review' ? 2.2 : 1.75} />
            <span>Advisory Review</span>
          </div>
          {pendingCount > 0 && (
            <span
              style={{
                backgroundColor: 'var(--warning-100)',
                color: 'var(--warning-600)',
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 'var(--radius-pill)',
                border: '1px solid rgba(199, 131, 24, 0.3)',
              }}
            >
              {pendingCount}
            </span>
          )}
        </button>

        <button
          onClick={() => handleNavClick('panchayats')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: currentTab === 'panchayats' ? 'var(--primary-050)' : 'transparent',
            color: currentTab === 'panchayats' ? 'var(--primary-700)' : 'var(--ink-700)',
            fontWeight: currentTab === 'panchayats' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            textAlign: 'left',
            width: '100%',
            transition: 'all 0.15s ease',
            minHeight: '44px',
          }}
          aria-current={currentTab === 'panchayats' ? 'page' : undefined}
        >
          <Building2 size={18} strokeWidth={currentTab === 'panchayats' ? 2.2 : 1.75} />
          <span>Panchayat Directory</span>
        </button>

        <button
          onClick={() => handleNavClick('audit')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 14px',
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: currentTab === 'audit' ? 'var(--primary-050)' : 'transparent',
            color: currentTab === 'audit' ? 'var(--primary-700)' : 'var(--ink-700)',
            fontWeight: currentTab === 'audit' ? 700 : 500,
            fontSize: '14px',
            cursor: 'pointer',
            textAlign: 'left',
            width: '100%',
            transition: 'all 0.15s ease',
            minHeight: '44px',
          }}
          aria-current={currentTab === 'audit' ? 'page' : undefined}
        >
          <History size={18} strokeWidth={currentTab === 'audit' ? 2.2 : 1.75} />
          <span>Approval Audit Log</span>
        </button>

        <div style={{ margin: '16px 8px 8px 8px', borderTop: 'var(--border-subtle)' }} />

        {/* Quick Action: Trigger On-Demand ML Downscaling */}
        <button
          onClick={() => {
            setMobileMenuOpen(false);
            onOpenGenerateModal();
          }}
          className="btn-secondary"
          style={{
            justifyContent: 'flex-start',
            padding: '10px 14px',
            fontSize: '13px',
            color: 'var(--primary-700)',
            borderColor: 'var(--primary-100)',
            backgroundColor: 'var(--primary-050)',
            minHeight: '44px',
          }}
        >
          <Sparkles size={16} color="var(--primary-600)" />
          <span>Run ML Downscaling</span>
        </button>
      </nav>

      {/* Officer Identity Footer */}
      <div
        style={{
          padding: '16px 20px',
          borderTop: 'var(--border-subtle)',
          backgroundColor: 'var(--surface-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: 'var(--radius-pill)',
            backgroundColor: 'var(--primary-700)',
            color: 'var(--surface)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: '13px',
            flexShrink: 0,
          }}
        >
          AO
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            Dr. S. Patil
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ink-500)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <ShieldCheck size={12} color="var(--primary-600)" />
            <span>Agromet SMS Officer</span>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <div style={{ display: 'flex', minHeight: '100vh', position: 'relative', width: '100%', overflowX: 'hidden' }}>
      {/* 1. Desktop Sidebar (>= 1024px) */}
      <aside
        className="desktop-sidebar"
        style={{
          width: '260px',
          backgroundColor: 'var(--surface)',
          borderRight: 'var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 30,
          flexShrink: 0,
        }}
        aria-label="Officer Portal Sidebar Navigation"
      >
        {renderNavContent()}
      </aside>

      {/* 2. Mobile Drawer Navigation Overlay (< 1024px) */}
      {mobileMenuOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 100,
            display: 'flex',
          }}
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation Menu"
        >
          {/* Backdrop */}
          <div
            onClick={() => setMobileMenuOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              backgroundColor: 'rgba(15, 30, 22, 0.6)',
              backdropFilter: 'blur(3px)',
            }}
          />

          {/* Slide-in Drawer Container */}
          <div
            className="slide-in-left"
            style={{
              position: 'relative',
              zIndex: 101,
              width: '280px',
              maxWidth: '85vw',
              height: '100%',
              backgroundColor: 'var(--surface)',
              boxShadow: 'var(--shadow-modal)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {renderNavContent()}
          </div>
        </div>
      )}

      {/* 3. Main Content Wrapper */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, width: '100%' }}>
        {/* Top Header Bar */}
        <header
          style={{
            minHeight: '64px',
            backgroundColor: 'var(--surface)',
            borderBottom: 'var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            padding: '10px 16px',
            position: 'sticky',
            top: 0,
            zIndex: 20,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap',
            }}
          >
            {/* Left: Hamburger & Title */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="btn-secondary header-menu-btn"
                style={{
                  padding: '8px',
                  minHeight: '38px',
                  borderRadius: 'var(--radius-sm)',
                  display: 'none',
                }}
                aria-label="Open navigation menu"
              >
                <Menu size={20} />
              </button>

              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '10px', color: 'var(--ink-500)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  MoES • IMD Agromet Protocol
                </div>
                <h1 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ink-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {currentTab === 'dashboard' && 'District Agromet Overview'}
                  {currentTab === 'forecasts' && 'Panchayat Micro-Forecasts'}
                  {currentTab === 'review' && 'Advisory Approval Queue'}
                  {currentTab === 'panchayats' && 'Panchayat Registry'}
                  {currentTab === 'audit' && 'Historical Verification Audit'}
                </h1>
              </div>
            </div>

            {/* Right: Date, Live Pill, Demo Selector, Refresh */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {/* Target Date Pill */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '5px 10px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--surface-subtle)',
                  border: '1px solid var(--ink-300)',
                  fontSize: '11px',
                  color: 'var(--ink-700)',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                }}
              >
                <span>Date: <strong>{forecastDate}</strong></span>
              </div>

              {/* Hierarchical or Demo Panchayat Selector */}
              {headerSelectorSlot ? (
                headerSelectorSlot
              ) : (
                onSelectDemoPanchayat && (
                  <DemoPanchayatSelector
                    onSelectPanchayat={onSelectDemoPanchayat}
                    selectedPanchayatId={selectedDemoPanchayatId}
                  />
                )
              )}

              {/* Refresh Button */}
              <button
                onClick={onRefresh}
                className="btn-secondary"
                style={{ padding: '6px 12px', fontSize: '12px', minHeight: '34px' }}
                title="Refresh Live Data"
                aria-label="Refresh Dashboard Data"
              >
                <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} />
                <span className="hide-on-mobile">Refresh</span>
              </button>
            </div>
          </div>
        </header>

        {/* Page Content Container */}
        <main
          style={{
            flex: 1,
            padding: 'clamp(14px, 2.5vw, 32px)',
            maxWidth: '1440px',
            width: '100%',
            margin: '0 auto',
            boxSizing: 'border-box',
          }}
          tabIndex={-1}
        >
          {children}
        </main>
      </div>
    </div>
  );
};
