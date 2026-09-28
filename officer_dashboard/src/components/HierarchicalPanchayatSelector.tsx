import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Search, 
  MapPin, 
  ChevronDown, 
  ChevronRight,
  Mountain,
  Check,
  X,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { ApiService } from '../services/api';
import { 
  PanchayatItem, 
  DistrictItem, 
  BlockItem, 
  BlockPanchayatItem 
} from '../types';

export interface HierarchicalPanchayatSelectorProps {
  onSelectPanchayat: (panchayat: PanchayatItem) => void;
  selectedPanchayatId?: number | null;
  selectedDistrictId?: number | null;
  selectedBlockId?: number | null;
  onDistrictChange?: (districtId: number, districtName: string) => void;
  onBlockChange?: (blockId: number | null, blockName: string | null) => void;
  onClearSelection?: () => void;
  className?: string;
}

export const HierarchicalPanchayatSelector: React.FC<HierarchicalPanchayatSelectorProps> = ({
  onSelectPanchayat,
  selectedPanchayatId = null,
  selectedDistrictId = null,
  selectedBlockId = null,
  onDistrictChange,
  onBlockChange,
  onClearSelection,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<'district' | 'block' | 'panchayat'>(() => {
    if (selectedBlockId) return 'panchayat';
    if (selectedDistrictId) return 'block';
    return 'district';
  });

  // 1. District Hierarchy State
  const [districts, setDistricts] = useState<DistrictItem[]>([]);
  const [activeDistrictId, setActiveDistrictId] = useState<number | null>(selectedDistrictId);
  const [activeDistrictName, setActiveDistrictName] = useState<string>('');
  const [districtSearch, setDistrictSearch] = useState('');
  const [districtPage, setDistrictPage] = useState(1);
  const [districtTotalPages, setDistrictTotalPages] = useState(1);
  const [districtTotalCount, setDistrictTotalCount] = useState(0);
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [districtError, setDistrictError] = useState<string | null>(null);

  // 2. Block Hierarchy State
  const [blocks, setBlocks] = useState<BlockItem[]>([]);
  const [activeBlockId, setActiveBlockId] = useState<number | null>(selectedBlockId);
  const [activeBlockName, setActiveBlockName] = useState<string | null>(null);
  const [blockSearch, setBlockSearch] = useState('');
  const [blockPage, setBlockPage] = useState(1);
  const [blockTotalPages, setBlockTotalPages] = useState(1);
  const [blockTotalCount, setBlockTotalCount] = useState(0);
  const [loadingBlocks, setLoadingBlocks] = useState(false);
  const [blockError, setBlockError] = useState<string | null>(null);

  // 3. Panchayat Hierarchy State
  const [panchayats, setPanchayats] = useState<BlockPanchayatItem[]>([]);
  const [activePanchayatName, setActivePanchayatName] = useState<string | null>(null);
  const [panchayatSearch, setPanchayatSearch] = useState('');
  const [panchayatPage, setPanchayatPage] = useState(1);
  const [panchayatTotalPages, setPanchayatTotalPages] = useState(1);
  const [panchayatTotalCount, setPanchayatTotalCount] = useState(0);
  const [loadingPanchayats, setLoadingPanchayats] = useState(false);
  const [panchayatError, setPanchayatError] = useState<string | null>(null);

  // Race condition mitigation refs
  const districtReqIdRef = useRef(0);
  const blockReqIdRef = useRef(0);
  const panchayatReqIdRef = useRef(0);

  const containerRef = useRef<HTMLDivElement>(null);

  // Sync external selectedDistrictId prop if changed
  useEffect(() => {
    if (selectedDistrictId !== undefined && selectedDistrictId !== activeDistrictId) {
      setActiveDistrictId(selectedDistrictId);
      if (selectedDistrictId && !selectedBlockId) {
        setStep('block');
      }
    }
  }, [selectedDistrictId, selectedBlockId]);

  // Sync external selectedBlockId prop if changed
  useEffect(() => {
    if (selectedBlockId !== undefined && selectedBlockId !== activeBlockId) {
      setActiveBlockId(selectedBlockId);
      if (selectedBlockId) {
        setStep('panchayat');
      }
    }
  }, [selectedBlockId]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ==========================================
  // FETCH DISTRICTS (Server-Side Search & Pagination)
  // ==========================================
  const fetchDistricts = useCallback(async () => {
    const currentReqId = ++districtReqIdRef.current;
    setLoadingDistricts(true);
    setDistrictError(null);

    try {
      const res = await ApiService.getDistricts(
        districtSearch.trim() || undefined,
        districtPage,
        20
      );
      if (districtReqIdRef.current === currentReqId) {
        setDistricts(res.items);
        setDistrictTotalPages(res.total_pages);
        setDistrictTotalCount(res.total);

        // If active district not set yet, or matches existing, resolve name
        if (res.items.length > 0) {
          if (!activeDistrictId) {
            setActiveDistrictId(res.items[0].id);
            setActiveDistrictName(res.items[0].name);
            onDistrictChange?.(res.items[0].id, res.items[0].name);
          } else {
            const current = res.items.find((d) => d.id === activeDistrictId);
            if (current) {
              setActiveDistrictName(current.name);
            }
          }
        }
      }
    } catch (err: any) {
      if (districtReqIdRef.current === currentReqId) {
        console.error('[Selector] Failed to load districts:', err);
        setDistrictError(err.message || 'Failed to retrieve administrative districts.');
      }
    } finally {
      if (districtReqIdRef.current === currentReqId) {
        setLoadingDistricts(false);
      }
    }
  }, [districtSearch, districtPage, activeDistrictId, onDistrictChange]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDistricts();
    }, 250);
    return () => clearTimeout(timer);
  }, [fetchDistricts]);

  // ==========================================
  // FETCH BLOCKS (Scoped strictly to activeDistrictId)
  // ==========================================
  const fetchBlocks = useCallback(async () => {
    if (!activeDistrictId) {
      setBlocks([]);
      setBlockTotalPages(1);
      setBlockTotalCount(0);
      return;
    }

    const currentReqId = ++blockReqIdRef.current;
    setLoadingBlocks(true);
    setBlockError(null);

    try {
      const res = await ApiService.getDistrictBlocks(
        activeDistrictId,
        blockSearch.trim() || undefined,
        blockPage,
        20
      );
      if (blockReqIdRef.current === currentReqId) {
        setBlocks(res.items);
        setBlockTotalPages(res.total_pages);
        setBlockTotalCount(res.total);

        if (activeBlockId) {
          const match = res.items.find((b) => b.id === activeBlockId);
          if (match) {
            setActiveBlockName(match.name);
          }
        }
      }
    } catch (err: any) {
      if (blockReqIdRef.current === currentReqId) {
        console.error('[Selector] Failed to load blocks for district:', activeDistrictId, err);
        setBlockError(err.message || 'Failed to retrieve blocks for this district.');
      }
    } finally {
      if (blockReqIdRef.current === currentReqId) {
        setLoadingBlocks(false);
      }
    }
  }, [activeDistrictId, blockSearch, blockPage, activeBlockId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchBlocks();
    }, 250);
    return () => clearTimeout(timer);
  }, [fetchBlocks]);

  // ==========================================
  // FETCH PANCHAYATS (Scoped strictly to activeBlockId)
  // ==========================================
  const fetchPanchayats = useCallback(async () => {
    if (!activeBlockId) {
      setPanchayats([]);
      setPanchayatTotalPages(1);
      setPanchayatTotalCount(0);
      return;
    }

    const currentReqId = ++panchayatReqIdRef.current;
    setLoadingPanchayats(true);
    setPanchayatError(null);

    try {
      const res = await ApiService.getBlockPanchayats(
        activeBlockId,
        panchayatSearch.trim() || undefined,
        panchayatPage,
        50
      );
      if (panchayatReqIdRef.current === currentReqId) {
        setPanchayats(res.items);
        setPanchayatTotalPages(res.total_pages);
        setPanchayatTotalCount(res.total);

        if (selectedPanchayatId) {
          const match = res.items.find((p) => p.id === selectedPanchayatId || p.panchayat_id === selectedPanchayatId);
          if (match) {
            setActivePanchayatName(match.name || match.panchayat_name || null);
          }
        }
      }
    } catch (err: any) {
      if (panchayatReqIdRef.current === currentReqId) {
        console.error('[Selector] Failed to load panchayats for block:', activeBlockId, err);
        setPanchayatError(err.message || 'Failed to retrieve Gram Panchayats from database.');
      }
    } finally {
      if (panchayatReqIdRef.current === currentReqId) {
        setLoadingPanchayats(false);
      }
    }
  }, [activeBlockId, panchayatSearch, panchayatPage, selectedPanchayatId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchPanchayats();
    }, 250);
    return () => clearTimeout(timer);
  }, [fetchPanchayats]);

  // ==========================================
  // SELECTION HANDLERS
  // ==========================================
  const handleSelectDistrict = (district: DistrictItem) => {
    if (district.id === activeDistrictId) {
      setStep('block');
      return;
    }

    // Dependent parent change: invalidate all child selections & state
    setActiveDistrictId(district.id);
    setActiveDistrictName(district.name);

    setActiveBlockId(null);
    setActiveBlockName(null);
    setBlocks([]);
    setBlockSearch('');
    setBlockPage(1);
    setBlockError(null);

    setActivePanchayatName(null);
    setPanchayats([]);
    setPanchayatSearch('');
    setPanchayatPage(1);
    setPanchayatError(null);

    setStep('block');
    onDistrictChange?.(district.id, district.name);
    onBlockChange?.(null, null);
  };

  const handleSelectBlock = (block: BlockItem) => {
    if (block.id === activeBlockId) {
      setStep('panchayat');
      return;
    }

    // Dependent parent change: invalidate child panchayat selections
    setActiveBlockId(block.id);
    setActiveBlockName(block.name);

    setActivePanchayatName(null);
    setPanchayats([]);
    setPanchayatSearch('');
    setPanchayatPage(1);
    setPanchayatError(null);

    setStep('panchayat');
    onBlockChange?.(block.id, block.name);
  };

  const handleSelectPanchayat = (item: BlockPanchayatItem) => {
    const pName = item.name || item.panchayat_name || 'Gram Panchayat';
    setActivePanchayatName(pName);
    setIsOpen(false);

    // Adapt to standard PanchayatItem contract
    const panchayatItem: PanchayatItem = {
      panchayat_id: item.id || item.panchayat_id || 0,
      lgd_code: item.lgd_code || 0,
      panchayat_name: pName,
      block_name: activeBlockName || 'Block',
      district_name: activeDistrictName || 'District',
      latitude: item.latitude ?? 20.0,
      longitude: item.longitude ?? 74.0,
      elevation_m: item.elevation_m ?? 500.0,
    };

    onSelectPanchayat(panchayatItem);
  };

  const handleClear = () => {
    setActivePanchayatName(null);
    onClearSelection?.();
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }} className={className}>
      {/* Selector Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          borderRadius: 'var(--radius-pill)',
          backgroundColor: 'var(--surface)',
          border: '1px solid var(--primary-300)',
          boxShadow: 'var(--shadow-card)',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--ink-900)',
          transition: 'all 0.2s ease',
          minHeight: '38px',
          maxWidth: '100%',
        }}
        aria-label="Administrative Scope & Panchayat Selector"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        <MapPin size={15} color="var(--primary-700)" style={{ flexShrink: 0 }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', minWidth: 0 }}>
          <span style={{ color: 'var(--primary-700)', fontWeight: 700, whiteSpace: 'nowrap' }}>
            {activeDistrictName || 'Select District'}
          </span>
          <span style={{ color: 'var(--ink-300)' }}>›</span>
          <span 
            style={{ 
              color: activeBlockName ? 'var(--ink-700)' : 'var(--ink-400)', 
              whiteSpace: 'nowrap', 
              overflow: 'hidden', 
              textOverflow: 'ellipsis', 
              maxWidth: '100px' 
            }}
          >
            {activeBlockName || 'Select Block'}
          </span>
          {activePanchayatName && (
            <>
              <span style={{ color: 'var(--ink-300)' }}>›</span>
              <span 
                style={{ 
                  color: 'var(--ink-900)', 
                  fontWeight: 700, 
                  whiteSpace: 'nowrap', 
                  overflow: 'hidden', 
                  textOverflow: 'ellipsis', 
                  maxWidth: '120px' 
                }}
              >
                {activePanchayatName}
              </span>
            </>
          )}
        </div>

        <ChevronDown 
          size={14} 
          color="var(--ink-500)" 
          style={{ 
            transition: 'transform 0.2s ease', 
            transform: isOpen ? 'rotate(180deg)' : 'none',
            flexShrink: 0,
          }} 
        />
      </button>

      {/* Hierarchical Dropdown Panel */}
      {isOpen && (
        <div
          className="app-card fade-in hierarchy-selector-panel"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: 'clamp(290px, 92vw, 440px)',
            maxHeight: '520px',
            padding: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 100,
            boxShadow: 'var(--shadow-modal)',
            border: '1px solid var(--primary-100)',
            borderRadius: 'var(--radius-md)',
          }}
          role="dialog"
          aria-label="Panchayat Hierarchy Selector Dialog"
        >
          {/* Header & Step Navigation */}
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--surface-subtle)',
              borderBottom: 'var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: '11px', color: 'var(--ink-500)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.04em' }}>
                Administrative Scope (District › Block › Panchayat)
              </div>
              {activePanchayatName && (
                <button
                  onClick={handleClear}
                  style={{
                    fontSize: '11px',
                    color: 'var(--danger-600)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                  aria-label="Clear selected Panchayat"
                >
                  Clear Selection
                </button>
              )}
            </div>

            {/* Stepper Breadcrumbs */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={() => setStep('district')}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: step === 'district' ? 700 : 500,
                  color: step === 'district' ? 'var(--primary-700)' : 'var(--ink-700)',
                  textDecoration: step === 'district' ? 'underline' : 'none',
                  padding: '2px 4px',
                }}
                aria-label="Step 1: Select District"
              >
                1. {activeDistrictName || 'District'}
              </button>
              <ChevronRight size={12} color="var(--ink-300)" />
              <button
                onClick={() => {
                  if (activeDistrictId) setStep('block');
                }}
                disabled={!activeDistrictId}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: activeDistrictId ? 'pointer' : 'not-allowed',
                  opacity: activeDistrictId ? 1 : 0.5,
                  fontWeight: step === 'block' ? 700 : 500,
                  color: step === 'block' ? 'var(--primary-700)' : 'var(--ink-700)',
                  textDecoration: step === 'block' ? 'underline' : 'none',
                  padding: '2px 4px',
                }}
                aria-label="Step 2: Select Block"
              >
                2. {activeBlockName || 'Block'}
              </button>
              <ChevronRight size={12} color="var(--ink-300)" />
              <button
                onClick={() => {
                  if (activeBlockId) setStep('panchayat');
                }}
                disabled={!activeBlockId}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: activeBlockId ? 'pointer' : 'not-allowed',
                  opacity: activeBlockId ? 1 : 0.5,
                  fontWeight: step === 'panchayat' ? 700 : 500,
                  color: step === 'panchayat' ? 'var(--primary-700)' : 'var(--ink-700)',
                  textDecoration: step === 'panchayat' ? 'underline' : 'none',
                  padding: '2px 4px',
                }}
                aria-label="Step 3: Select Panchayat"
              >
                3. {activePanchayatName || 'Panchayat'}
              </button>
            </div>
          </div>

          {/* ======================================================== */}
          {/* STEP 1: DISTRICT SELECTION (Server-Side Search & Pagination) */}
          {/* ======================================================== */}
          {step === 'district' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              {/* Search Districts */}
              <div style={{ padding: '10px 14px', borderBottom: 'var(--border-subtle)' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={15} color="var(--ink-500)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder="Search districts by name..."
                    value={districtSearch}
                    onChange={(e) => {
                      setDistrictSearch(e.target.value);
                      setDistrictPage(1);
                    }}
                    className="input-field"
                    style={{ paddingLeft: '32px', fontSize: '12px', height: '36px', width: '100%' }}
                    aria-label="Search districts input"
                    autoFocus
                  />
                  {districtSearch && (
                    <button
                      onClick={() => {
                        setDistrictSearch('');
                        setDistrictPage(1);
                      }}
                      style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer' }}
                      aria-label="Clear district search"
                    >
                      <X size={14} color="var(--ink-500)" />
                    </button>
                  )}
                </div>
              </div>

              {/* Districts List */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px', maxHeight: '280px' }}>
                {loadingDistricts ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                    Loading districts...
                  </div>
                ) : districtError ? (
                  <div style={{ padding: '16px', color: 'var(--danger-600)', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <AlertCircle size={16} />
                      <span>{districtError}</span>
                    </div>
                    <button
                      onClick={fetchDistricts}
                      className="btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '11px' }}
                    >
                      <RefreshCw size={12} style={{ marginRight: '4px' }} /> Retry
                    </button>
                  </div>
                ) : districts.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                    No administrative districts found{districtSearch ? ` matching "${districtSearch}"` : ''}.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {districts.map((d) => {
                      const isSelected = d.id === activeDistrictId;
                      return (
                        <button
                          key={d.id}
                          onClick={() => handleSelectDistrict(d)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 14px',
                            borderRadius: 'var(--radius-sm)',
                            border: isSelected ? '2px solid var(--primary-500)' : '1px solid var(--ink-100)',
                            backgroundColor: isSelected ? 'var(--primary-050)' : 'var(--surface)',
                            cursor: 'pointer',
                            textAlign: 'left',
                            minHeight: '44px',
                          }}
                          className="app-card-interactive"
                          aria-label={`Select ${d.name} District`}
                        >
                          <div>
                            <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink-900)' }}>
                              {d.name} District
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                              State: {d.state || 'Maharashtra'}{d.code ? ` • Code: ${d.code}` : ''}
                            </div>
                          </div>
                          {isSelected && <Check size={16} color="var(--primary-700)" />}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* District Pagination Controls */}
              {districtTotalPages > 1 && (
                <div
                  style={{
                    padding: '8px 14px',
                    borderTop: 'var(--border-subtle)',
                    backgroundColor: 'var(--surface-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '11px',
                    color: 'var(--ink-700)',
                  }}
                >
                  <span>
                    Page {districtPage} of {districtTotalPages} ({districtTotalCount} total)
                  </span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      onClick={() => setDistrictPage((p) => Math.max(1, p - 1))}
                      disabled={districtPage <= 1}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--ink-300)',
                        backgroundColor: 'var(--surface)',
                        cursor: districtPage <= 1 ? 'not-allowed' : 'pointer',
                        opacity: districtPage <= 1 ? 0.5 : 1,
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                      aria-label="Previous district page"
                    >
                      Prev
                    </button>
                    <button
                      onClick={() => setDistrictPage((p) => Math.min(districtTotalPages, p + 1))}
                      disabled={districtPage >= districtTotalPages}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--ink-300)',
                        backgroundColor: 'var(--surface)',
                        cursor: districtPage >= districtTotalPages ? 'not-allowed' : 'pointer',
                        opacity: districtPage >= districtTotalPages ? 0.5 : 1,
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                      aria-label="Next district page"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* STEP 2: BLOCK SELECTION (Server-Side Search & Pagination) */}
          {/* ======================================================== */}
          {step === 'block' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              {!activeDistrictId ? (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                  Select a district to view blocks.
                </div>
              ) : (
                <>
                  {/* Search Blocks */}
                  <div style={{ padding: '10px 14px', borderBottom: 'var(--border-subtle)', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Search size={15} color="var(--ink-500)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                      <input
                        type="text"
                        placeholder={`Search blocks in ${activeDistrictName}...`}
                        value={blockSearch}
                        onChange={(e) => {
                          setBlockSearch(e.target.value);
                          setBlockPage(1);
                        }}
                        className="input-field"
                        style={{ paddingLeft: '32px', fontSize: '12px', height: '36px', width: '100%' }}
                        aria-label="Search blocks input"
                        autoFocus
                      />
                      {blockSearch && (
                        <button
                          onClick={() => {
                            setBlockSearch('');
                            setBlockPage(1);
                          }}
                          style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer' }}
                          aria-label="Clear block search"
                        >
                          <X size={14} color="var(--ink-500)" />
                        </button>
                      )}
                    </div>
                    <button
                      onClick={() => setStep('district')}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--primary-700)',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                      aria-label="Change District"
                    >
                      Change District
                    </button>
                  </div>

                  {/* Block Results Grid */}
                  <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px', maxHeight: '280px' }}>
                    {loadingBlocks ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                        Loading blocks...
                      </div>
                    ) : blockError ? (
                      <div style={{ padding: '16px', color: 'var(--danger-600)', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <AlertCircle size={16} />
                          <span>{blockError}</span>
                        </div>
                        <button
                          onClick={fetchBlocks}
                          className="btn-secondary"
                          style={{ padding: '4px 10px', fontSize: '11px' }}
                        >
                          <RefreshCw size={12} style={{ marginRight: '4px' }} /> Retry
                        </button>
                      </div>
                    ) : blocks.length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                        No blocks found in {activeDistrictName}{blockSearch ? ` matching "${blockSearch}"` : ''}.
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '8px' }}>
                        {blocks.map((b) => {
                          const isSelected = b.id === activeBlockId;
                          return (
                            <button
                              key={b.id}
                              onClick={() => handleSelectBlock(b)}
                              style={{
                                padding: '10px 12px',
                                borderRadius: 'var(--radius-sm)',
                                border: isSelected ? '2px solid var(--primary-500)' : '1px solid var(--ink-300)',
                                backgroundColor: isSelected ? 'var(--primary-050)' : 'var(--surface)',
                                cursor: 'pointer',
                                textAlign: 'center',
                                fontSize: '13px',
                                fontWeight: isSelected ? 700 : 500,
                                color: isSelected ? 'var(--primary-700)' : 'var(--ink-900)',
                                minHeight: '44px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                              className="app-card-interactive"
                              aria-label={`Select ${b.name} Block`}
                            >
                              {b.name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Block Pagination Controls */}
                  {blockTotalPages > 1 && (
                    <div
                      style={{
                        padding: '8px 14px',
                        borderTop: 'var(--border-subtle)',
                        backgroundColor: 'var(--surface-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '11px',
                        color: 'var(--ink-700)',
                      }}
                    >
                      <span>
                        Page {blockPage} of {blockTotalPages} ({blockTotalCount} total)
                      </span>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          onClick={() => setBlockPage((p) => Math.max(1, p - 1))}
                          disabled={blockPage <= 1}
                          style={{
                            padding: '4px 8px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--ink-300)',
                            backgroundColor: 'var(--surface)',
                            cursor: blockPage <= 1 ? 'not-allowed' : 'pointer',
                            opacity: blockPage <= 1 ? 0.5 : 1,
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                          aria-label="Previous block page"
                        >
                          Prev
                        </button>
                        <button
                          onClick={() => setBlockPage((p) => Math.min(blockTotalPages, p + 1))}
                          disabled={blockPage >= blockTotalPages}
                          style={{
                            padding: '4px 8px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--ink-300)',
                            backgroundColor: 'var(--surface)',
                            cursor: blockPage >= blockTotalPages ? 'not-allowed' : 'pointer',
                            opacity: blockPage >= blockTotalPages ? 0.5 : 1,
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                          aria-label="Next block page"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* STEP 3: PANCHAYAT SELECTION (Server-Side Search & Pagination) */}
          {/* ======================================================== */}
          {step === 'panchayat' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              {!activeBlockId ? (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                  Select a block to view Panchayats.
                </div>
              ) : (
                <>
                  {/* Search within Block */}
                  <div style={{ padding: '10px 14px', borderBottom: 'var(--border-subtle)' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={15} color="var(--ink-500)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                      <input
                        type="text"
                        placeholder={`Search ${activeBlockName || ''} Panchayats or LGD...`}
                        value={panchayatSearch}
                        onChange={(e) => {
                          setPanchayatSearch(e.target.value);
                          setPanchayatPage(1);
                        }}
                        className="input-field"
                        style={{ paddingLeft: '32px', fontSize: '12px', height: '36px', width: '100%' }}
                        aria-label="Search Panchayats by name or LGD code"
                        autoFocus
                      />
                      {panchayatSearch && (
                        <button
                          onClick={() => {
                            setPanchayatSearch('');
                            setPanchayatPage(1);
                          }}
                          style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer' }}
                          aria-label="Clear panchayat search"
                        >
                          <X size={14} color="var(--ink-500)" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Panchayat Results List */}
                  <div style={{ flex: 1, overflowY: 'auto', padding: '6px 10px', maxHeight: '280px' }}>
                    {loadingPanchayats ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '12px' }}>
                        Loading Panchayats...
                      </div>
                    ) : panchayatError ? (
                      <div style={{ padding: '16px', color: 'var(--danger-600)', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <AlertCircle size={16} />
                          <span>{panchayatError}</span>
                        </div>
                        <button
                          onClick={fetchPanchayats}
                          className="btn-secondary"
                          style={{ padding: '4px 10px', fontSize: '11px' }}
                        >
                          <RefreshCw size={12} style={{ marginRight: '4px' }} /> Retry
                        </button>
                      </div>
                    ) : panchayats.length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '12px' }}>
                        No Gram Panchayats found in {activeBlockName}{panchayatSearch ? ` matching "${panchayatSearch}"` : ''}.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {panchayats.map((p) => {
                          const pId = p.id || p.panchayat_id;
                          const pName = p.name || p.panchayat_name;
                          const isSelected = pId === selectedPanchayatId;
                          return (
                            <button
                              key={pId}
                              onClick={() => handleSelectPanchayat(p)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '8px 12px',
                                borderRadius: 'var(--radius-sm)',
                                border: isSelected ? '1px solid var(--primary-500)' : '1px solid transparent',
                                backgroundColor: isSelected ? 'var(--primary-050)' : 'transparent',
                                cursor: 'pointer',
                                textAlign: 'left',
                                transition: 'background-color 0.15s ease',
                                minHeight: '40px',
                              }}
                              className="app-card-interactive"
                              aria-label={`Select Gram Panchayat ${pName}`}
                            >
                              <div>
                                <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink-900)' }}>
                                  {pName}
                                </div>
                                <div style={{ fontSize: '11px', color: 'var(--ink-500)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  {p.lgd_code && <span>LGD: {p.lgd_code}</span>}
                                  {p.elevation_m != null && (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                                      <Mountain size={10} /> {Math.round(p.elevation_m)}m
                                    </span>
                                  )}
                                </div>
                              </div>
                              {isSelected && <Check size={16} color="var(--primary-700)" />}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Pagination Controls */}
                  {panchayatTotalPages > 1 && (
                    <div
                      style={{
                        padding: '8px 14px',
                        borderTop: 'var(--border-subtle)',
                        backgroundColor: 'var(--surface-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '11px',
                        color: 'var(--ink-700)',
                      }}
                    >
                      <span>
                        Page {panchayatPage} of {panchayatTotalPages} ({panchayatTotalCount} total)
                      </span>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          onClick={() => setPanchayatPage((p) => Math.max(1, p - 1))}
                          disabled={panchayatPage <= 1}
                          style={{
                            padding: '4px 8px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--ink-300)',
                            backgroundColor: 'var(--surface)',
                            cursor: panchayatPage <= 1 ? 'not-allowed' : 'pointer',
                            opacity: panchayatPage <= 1 ? 0.5 : 1,
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                          aria-label="Previous panchayat page"
                        >
                          Prev
                        </button>
                        <button
                          onClick={() => setPanchayatPage((p) => Math.min(panchayatTotalPages, p + 1))}
                          disabled={panchayatPage >= panchayatTotalPages}
                          style={{
                            padding: '4px 8px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--ink-300)',
                            backgroundColor: 'var(--surface)',
                            cursor: panchayatPage >= panchayatTotalPages ? 'not-allowed' : 'pointer',
                            opacity: panchayatPage >= panchayatTotalPages ? 0.5 : 1,
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                          aria-label="Next panchayat page"
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
