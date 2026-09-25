import React, { useState, useEffect, useRef } from 'react';
import { 
  Building2, 
  Search, 
  MapPin, 
  ChevronDown, 
  Sparkles, 
  Mountain,
  Check,
  X,
  Compass
} from 'lucide-react';
import { ApiService } from '../services/api';
import { PanchayatItem } from '../types';

interface DemoPanchayatSelectorProps {
  onSelectPanchayat: (panchayat: PanchayatItem) => void;
  selectedPanchayatId?: number | null;
  className?: string;
}

/**
 * Development & Demo Panchayat Selector.
 * 
 * Fetches real Gram Panchayats dynamically from `GET /api/v1/panchayats`.
 * - Zero fake data or mock records created.
 * - Read-only inspection; does not modify production database records.
 * - Distinctly separated from production authentication and user authorization.
 */
export const DemoPanchayatSelector: React.FC<DemoPanchayatSelectorProps> = ({
  onSelectPanchayat,
  selectedPanchayatId,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBlock, setSelectedBlock] = useState<string>('ALL');
  const [panchayats, setPanchayats] = useState<PanchayatItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
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

  // Fetch real Panchayats from backend when search/block filter changes
  useEffect(() => {
    let isCancelled = false;
    const fetchPanchayats = async () => {
      setLoading(true);
      setError(null);
      try {
        const block = selectedBlock === 'ALL' ? undefined : selectedBlock;
        const res = await ApiService.getPanchayats(block, searchQuery.trim() || undefined, 1, 60);
        if (!isCancelled) {
          setPanchayats(res.items);
          setTotalCount(res.total);
        }
      } catch (err: any) {
        if (!isCancelled) {
          console.warn('[Demo Selector] Failed to load panchayats from API:', err);
          setError('Backend offline or loading failed');
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    const timer = setTimeout(() => {
      fetchPanchayats();
    }, 250);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [searchQuery, selectedBlock]);

  const activePanchayat = panchayats.find((p) => p.panchayat_id === selectedPanchayatId);

  const [blocks, setBlocks] = useState<string[]>([
    'ALL',
    'Baglan',
    'Chandwad',
    'Deola',
    'Dindori',
    'Igatpuri',
    'Kalwan',
    'Malegaon',
    'Nandgaon',
    'Nashik',
    'Niphad',
    'Peint',
    'Sinnar',
    'Surgana',
    'Trimbakeshwar',
    'Yevla',
  ]);

  // Dynamically load blocks from the backend hierarchical API
  useEffect(() => {
    let isCancelled = false;
    ApiService.getDistrictBlocks(1)
      .then((blockList) => {
        if (!isCancelled && blockList && blockList.length > 0) {
          const names = blockList.map((b) => b.name).sort();
          setBlocks(['ALL', ...names]);
        }
      })
      .catch((err) => {
        console.warn('[Demo Selector] Dynamic block loading failed, using complete registry fallback:', err);
      });
    return () => {
      isCancelled = true;
    };
  }, []);

  const availableBlocks = blocks;

  return (
    <div ref={containerRef} style={{ position: 'relative' }} className={className}>
      {/* Demo Selector Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 14px',
          borderRadius: 'var(--radius-pill)',
          backgroundColor: 'var(--surface)',
          border: '1px solid var(--primary-300)',
          boxShadow: 'var(--shadow-card)',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--ink-900)',
          transition: 'all 0.2s ease',
        }}
        aria-label="Development / Demo Panchayat Selector"
        title="Development / Demo Panchayat Selector (Loads real backend data)"
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 6px',
            backgroundColor: 'var(--primary-050)',
            color: 'var(--primary-700)',
            borderRadius: 'var(--radius-pill)',
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            border: '1px solid var(--primary-200)',
          }}
        >
          <Sparkles size={11} />
          Dev Demo
        </span>

        <Building2 size={15} color="var(--primary-700)" />

        <span style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {activePanchayat ? activePanchayat.panchayat_name : 'Select Real Panchayat'}
        </span>

        <ChevronDown size={14} color="var(--ink-500)" style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: 'min(380px, calc(100vw - 24px))',
            maxWidth: 'calc(100vw - 24px)',
            maxHeight: '480px',
            backgroundColor: 'var(--surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--ink-200)',
            boxShadow: 'var(--shadow-modal)',
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'fadeIn 0.15s ease',
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--surface-subtle)',
              borderBottom: '1px solid var(--ink-200)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Compass size={16} color="var(--primary-700)" />
                <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink-900)' }}>
                  Demo Panchayat Inspector
                </span>
              </div>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  backgroundColor: 'var(--primary-100)',
                  color: 'var(--primary-700)',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-pill)',
                }}
              >
                {totalCount} Real Panchayats in DB
              </span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--ink-500)', margin: 0 }}>
              Live read-only selector querying real IMD downscaled forecasts.
            </p>
          </div>

          {/* Search Field */}
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--ink-200)' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 10px',
                backgroundColor: 'var(--surface-subtle)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--ink-300)',
              }}
            >
              <Search size={14} color="var(--ink-500)" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search village name or LGD code..."
                style={{
                  border: 'none',
                  outline: 'none',
                  backgroundColor: 'transparent',
                  fontSize: '12px',
                  width: '100%',
                  color: 'var(--ink-900)',
                }}
                autoFocus
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}
                >
                  <X size={12} color="var(--ink-500)" />
                </button>
              )}
            </div>
          </div>

          {/* Block Filter Chips */}
          <div
            style={{
              display: 'flex',
              gap: '6px',
              padding: '8px 14px',
              overflowX: 'auto',
              borderBottom: '1px solid var(--ink-200)',
              backgroundColor: 'var(--surface)',
            }}
          >
            {availableBlocks.map((block) => (
              <button
                key={block}
                onClick={() => setSelectedBlock(block)}
                style={{
                  padding: '3px 10px',
                  borderRadius: 'var(--radius-pill)',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: selectedBlock === block ? 700 : 500,
                  backgroundColor: selectedBlock === block ? 'var(--primary-700)' : 'var(--surface-subtle)',
                  color: selectedBlock === block ? 'var(--surface)' : 'var(--ink-700)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {block === 'ALL' ? 'All Blocks' : block}
              </button>
            ))}
          </div>

          {/* Panchayat List */}
          <div style={{ overflowY: 'auto', maxHeight: '280px', padding: '6px' }}>
            {loading ? (
              <div style={{ padding: '24px', textAlign: 'center', fontSize: '12px', color: 'var(--ink-500)' }}>
                Loading real Panchayats from database...
              </div>
            ) : error ? (
              <div style={{ padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--danger-600)' }}>
                {error}
              </div>
            ) : panchayats.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', fontSize: '12px', color: 'var(--ink-500)' }}>
                No Panchayats match your search.
              </div>
            ) : (
              panchayats.map((p) => {
                const isSelected = p.panchayat_id === selectedPanchayatId;
                return (
                  <div
                    key={p.panchayat_id}
                    onClick={() => {
                      onSelectPanchayat(p);
                      setIsOpen(false);
                    }}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isSelected ? 'var(--primary-050)' : 'transparent',
                      border: isSelected ? '1px solid var(--primary-200)' : '1px solid transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '8px',
                      marginBottom: '2px',
                      transition: 'background-color 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--surface-subtle)';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink-900)' }}>
                          {p.panchayat_name}
                        </span>
                        <span style={{ fontSize: '10px', color: 'var(--ink-500)', backgroundColor: 'var(--ink-100)', padding: '1px 5px', borderRadius: '4px' }}>
                          LGD: {p.lgd_code}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '3px', fontSize: '11px', color: 'var(--ink-500)' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <MapPin size={11} /> {p.block_name} Block
                        </span>
                        <span>•</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                          <Mountain size={11} /> {Math.round(p.elevation_m)}m
                        </span>
                      </div>
                    </div>

                    {isSelected && (
                      <div
                        style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--primary-700)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#FFFFFF',
                        }}
                      >
                        <Check size={12} strokeWidth={3} />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer Notice */}
          <div
            style={{
              padding: '8px 14px',
              backgroundColor: 'var(--surface-subtle)',
              borderTop: '1px solid var(--ink-200)',
              fontSize: '10px',
              color: 'var(--ink-500)',
              textAlign: 'center',
            }}
          >
            Selection loads real downscaled forecast & advisory records.
          </div>
        </div>
      )}
    </div>
  );
};
