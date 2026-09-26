import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  MapPin, 
  ChevronDown, 
  ChevronRight,
  Mountain,
  Check,
  X,
  AlertCircle
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
  selectedDistrictId?: number;
  selectedBlockId?: number | null;
  onDistrictChange?: (districtId: number, districtName: string) => void;
  onBlockChange?: (blockId: number | null, blockName: string | null) => void;
  onClearSelection?: () => void;
  className?: string;
}

export const HierarchicalPanchayatSelector: React.FC<HierarchicalPanchayatSelectorProps> = ({
  onSelectPanchayat,
  selectedPanchayatId,
  selectedDistrictId = 1,
  selectedBlockId = null,
  onDistrictChange,
  onBlockChange,
  onClearSelection,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<'district' | 'block' | 'panchayat'>('panchayat');

  // Hierarchy State
  const [districts, setDistricts] = useState<DistrictItem[]>([]);
  const [blocks, setBlocks] = useState<BlockItem[]>([]);
  const [panchayats, setPanchayats] = useState<BlockPanchayatItem[]>([]);

  const [activeDistrictId, setActiveDistrictId] = useState<number>(selectedDistrictId);
  const [activeDistrictName, setActiveDistrictName] = useState<string>('Nashik');
  const [activeBlockId, setActiveBlockId] = useState<number | null>(selectedBlockId);
  const [activeBlockName, setActiveBlockName] = useState<string | null>(null);
  const [activePanchayatName, setActivePanchayatName] = useState<string | null>(null);

  // Search & Pagination State
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Loading & Error States
  const [loadingDistricts, setLoadingDistricts] = useState(false);
  const [loadingBlocks, setLoadingBlocks] = useState(false);
  const [loadingPanchayats, setLoadingPanchayats] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

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

  // 1. Load Districts on Mount
  useEffect(() => {
    let isCancelled = false;
    const fetchDistricts = async () => {
      setLoadingDistricts(true);
      try {
        const data = await ApiService.getDistricts();
        if (!isCancelled && data.length > 0) {
          setDistricts(data);
          const current = data.find((d) => d.id === activeDistrictId) || data[0];
          setActiveDistrictId(current.id);
          setActiveDistrictName(current.name);
        }
      } catch (err: any) {
        if (!isCancelled) {
          console.warn('[Selector] Failed to load districts:', err);
          setDistricts([
            { id: 1, name: 'Nashik', state: 'Maharashtra' },
            { id: 4, name: 'Pune', state: 'Maharashtra' },
          ]);
        }
      } finally {
        if (!isCancelled) setLoadingDistricts(false);
      }
    };

    fetchDistricts();
    return () => { isCancelled = true; };
  }, []);

  // 2. Load Blocks when activeDistrictId changes
  useEffect(() => {
    if (!activeDistrictId) return;
    let isCancelled = false;
    const fetchBlocks = async () => {
      setLoadingBlocks(true);
      setError(null);
      try {
        const data = await ApiService.getDistrictBlocks(activeDistrictId);
        if (!isCancelled) {
          setBlocks(data);
          if (data.length > 0 && !activeBlockId) {
            setActiveBlockId(data[0].id);
            setActiveBlockName(data[0].name);
          }
        }
      } catch (err: any) {
        if (!isCancelled) {
          console.warn('[Selector] Failed to load blocks:', err);
          setError('Failed to load blocks for this district.');
        }
      } finally {
        if (!isCancelled) setLoadingBlocks(false);
      }
    };

    fetchBlocks();
    return () => { isCancelled = true; };
  }, [activeDistrictId]);

  // 3. Load Panchayats when activeBlockId, page, or searchQuery changes
  useEffect(() => {
    if (!activeBlockId) return;
    let isCancelled = false;
    const timer = setTimeout(async () => {
      setLoadingPanchayats(true);
      setError(null);
      try {
        const res = await ApiService.getBlockPanchayats(
          activeBlockId,
          searchQuery.trim() || undefined,
          page,
          50
        );
        if (!isCancelled) {
          setPanchayats(res.items);
          setTotalPages(res.total_pages);
          setTotalCount(res.total);

          // Find active panchayat name if selected
          if (selectedPanchayatId) {
            const match = res.items.find((p) => p.id === selectedPanchayatId);
            if (match) setActivePanchayatName(match.name);
          }
        }
      } catch (err: any) {
        if (!isCancelled) {
          console.warn('[Selector] Failed to load panchayats:', err);
          setError('Failed to retrieve panchayats from database.');
        }
      } finally {
        if (!isCancelled) setLoadingPanchayats(false);
      }
    }, 250);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [activeBlockId, page, searchQuery, selectedPanchayatId]);

  const handleSelectDistrict = (district: DistrictItem) => {
    setActiveDistrictId(district.id);
    setActiveDistrictName(district.name);
    setActiveBlockId(null);
    setActiveBlockName(null);
    setActivePanchayatName(null);
    setSearchQuery('');
    setPage(1);
    setStep('block');
    onDistrictChange?.(district.id, district.name);
  };

  const handleSelectBlock = (block: BlockItem) => {
    setActiveBlockId(block.id);
    setActiveBlockName(block.name);
    setActivePanchayatName(null);
    setSearchQuery('');
    setPage(1);
    setStep('panchayat');
    onBlockChange?.(block.id, block.name);
  };

  const handleSelectPanchayat = (item: BlockPanchayatItem) => {
    setActivePanchayatName(item.name);
    setIsOpen(false);

    // Adapt to standard PanchayatItem contract
    const panchayatItem: PanchayatItem = {
      panchayat_id: item.id,
      lgd_code: item.lgd_code,
      panchayat_name: item.name,
      block_name: activeBlockName || 'Block',
      district_name: activeDistrictName,
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
      >
        <MapPin size={15} color="var(--primary-700)" style={{ flexShrink: 0 }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', minWidth: 0 }}>
          <span style={{ color: 'var(--primary-700)', fontWeight: 700, whiteSpace: 'nowrap' }}>
            {activeDistrictName}
          </span>
          <span style={{ color: 'var(--ink-300)' }}>›</span>
          <span style={{ color: 'var(--ink-700)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100px' }}>
            {activeBlockName || 'Select Block'}
          </span>
          {activePanchayatName && (
            <>
              <span style={{ color: 'var(--ink-300)' }}>›</span>
              <span style={{ color: 'var(--ink-900)', fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '120px' }}>
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
          className="app-card fade-in"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: 'clamp(300px, 90vw, 420px)',
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
                Administrative Hierarchy
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
              >
                1. {activeDistrictName}
              </button>
              <ChevronRight size={12} color="var(--ink-300)" />
              <button
                onClick={() => setStep('block')}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: step === 'block' ? 700 : 500,
                  color: step === 'block' ? 'var(--primary-700)' : 'var(--ink-700)',
                  textDecoration: step === 'block' ? 'underline' : 'none',
                  padding: '2px 4px',
                }}
              >
                2. {activeBlockName || 'Select Block'}
              </button>
              <ChevronRight size={12} color="var(--ink-300)" />
              <span
                style={{
                  fontWeight: step === 'panchayat' ? 700 : 500,
                  color: step === 'panchayat' ? 'var(--primary-700)' : 'var(--ink-500)',
                  padding: '2px 4px',
                }}
              >
                3. Panchayat
              </span>
            </div>
          </div>

          {/* STEP 1: DISTRICT SELECTION */}
          {step === 'district' && (
            <div style={{ padding: '14px', flex: 1, overflowY: 'auto' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink-700)', marginBottom: '10px' }}>
                Select Administrative District:
              </div>
              {loadingDistricts ? (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                  Loading districts...
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {districts.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => handleSelectDistrict(d)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 14px',
                        borderRadius: 'var(--radius-sm)',
                        border: d.id === activeDistrictId ? '2px solid var(--primary-500)' : '1px solid var(--ink-100)',
                        backgroundColor: d.id === activeDistrictId ? 'var(--primary-050)' : 'var(--surface)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        minHeight: '44px',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--ink-900)' }}>
                          {d.name} District
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--ink-500)' }}>
                          State: {d.state || 'Maharashtra'}
                        </div>
                      </div>
                      {d.id === activeDistrictId && <Check size={16} color="var(--primary-700)" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* STEP 2: BLOCK SELECTION */}
          {step === 'block' && (
            <div style={{ padding: '14px', flex: 1, overflowY: 'auto' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink-700)' }}>
                  Blocks in {activeDistrictName} ({blocks.length}):
                </span>
                <button
                  onClick={() => setStep('district')}
                  style={{ background: 'none', border: 'none', color: 'var(--primary-700)', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Change District
                </button>
              </div>

              {loadingBlocks ? (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                  Loading blocks...
                </div>
              ) : blocks.length === 0 ? (
                <div style={{ padding: '20px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '13px' }}>
                  No blocks found for {activeDistrictName}.
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '8px' }}>
                  {blocks.map((b) => (
                    <button
                      key={b.id}
                      onClick={() => handleSelectBlock(b)}
                      style={{
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-sm)',
                        border: b.id === activeBlockId ? '2px solid var(--primary-500)' : '1px solid var(--ink-300)',
                        backgroundColor: b.id === activeBlockId ? 'var(--primary-050)' : 'var(--surface)',
                        cursor: 'pointer',
                        textAlign: 'center',
                        fontSize: '13px',
                        fontWeight: b.id === activeBlockId ? 700 : 500,
                        color: b.id === activeBlockId ? 'var(--primary-700)' : 'var(--ink-900)',
                        minHeight: '44px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {b.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* STEP 3: PANCHAYAT SELECTION */}
          {step === 'panchayat' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              {/* Search within Block */}
              <div style={{ padding: '10px 14px', borderBottom: 'var(--border-subtle)' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={15} color="var(--ink-500)" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder={`Search ${activeBlockName || ''} Panchayats or LGD...`}
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setPage(1);
                    }}
                    className="input-field"
                    style={{ paddingLeft: '32px', fontSize: '12px', height: '36px' }}
                    autoFocus
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer' }}
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
                ) : error ? (
                  <div style={{ padding: '16px', color: 'var(--danger-600)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <AlertCircle size={15} />
                    <span>{error}</span>
                  </div>
                ) : panchayats.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--ink-500)', fontSize: '12px' }}>
                    No Gram Panchayats found in {activeBlockName}.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {panchayats.map((p) => {
                      const isSelected = p.id === selectedPanchayatId;
                      return (
                        <button
                          key={p.id}
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
                        >
                          <div>
                            <div style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink-900)' }}>
                              {p.name}
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--ink-500)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span>LGD: {p.lgd_code}</span>
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
              {totalPages > 1 && (
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
                    Page {page} of {totalPages} ({totalCount} total)
                  </span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--ink-300)',
                        backgroundColor: 'var(--surface)',
                        cursor: page <= 1 ? 'not-allowed' : 'pointer',
                        opacity: page <= 1 ? 0.5 : 1,
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                    >
                      Prev
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--ink-300)',
                        backgroundColor: 'var(--surface)',
                        cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                        opacity: page >= totalPages ? 0.5 : 1,
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
