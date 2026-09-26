import React, { useState } from 'react';
import { Search, Mountain, MapPin, ExternalLink, Sparkles } from 'lucide-react';
import { PanchayatItem } from '../types';

interface PanchayatGridProps {
  panchayats: PanchayatItem[];
  onSelectPanchayat: (panchayat: PanchayatItem) => void;
  onGenerateForPanchayat: (panchayat: PanchayatItem) => void;
}

export const PanchayatGrid: React.FC<PanchayatGridProps> = ({
  panchayats,
  onSelectPanchayat,
  onGenerateForPanchayat,
}) => {
  const [search, setSearch] = useState('');
  const [selectedBlock, setSelectedBlock] = useState('ALL');

  const filteredPanchayats = panchayats.filter((p) => {
    const matchesSearch =
      p.panchayat_name.toLowerCase().includes(search.toLowerCase()) ||
      p.block_name.toLowerCase().includes(search.toLowerCase()) ||
      String(p.lgd_code).includes(search) ||
      String(p.panchayat_id).includes(search);
    const matchesBlock = selectedBlock === 'ALL' || p.block_name.toLowerCase() === selectedBlock.toLowerCase();
    return matchesSearch && matchesBlock;
  });

  const availableBlocks = Array.from(new Set(panchayats.map((p) => p.block_name).filter(Boolean))).sort();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header and Search Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h2 className="text-section-title">Panchayat Geospatial Registry</h2>
          <p className="text-body" style={{ fontSize: '13px', color: 'var(--ink-500)' }}>
            {panchayats.length} Gram Panchayats registered with Bhuvan DEM elevation and LGD codes.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', width: '260px' }}>
            <Search
              size={16}
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
              placeholder="Search by name, LGD..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field"
              style={{ paddingLeft: '36px' }}
            />
          </div>

          {/* Block Selector */}
          <select
            value={selectedBlock}
            onChange={(e) => setSelectedBlock(e.target.value)}
            className="input-field"
            style={{ width: '150px' }}
          >
            <option value="ALL">All Blocks</option>
            {availableBlocks.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid of Panchayat Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '16px',
        }}
      >
        {filteredPanchayats.map((p) => (
          <div
            key={p.panchayat_id}
            className="app-card app-card-interactive"
            style={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="text-label" style={{ color: 'var(--primary-700)' }}>
                  ID #{p.panchayat_id}
                </span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: 'var(--surface-subtle)',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-pill)',
                    border: '1px solid var(--ink-300)',
                    color: 'var(--ink-700)',
                  }}
                >
                  LGD: {p.lgd_code}
                </span>
              </div>

              <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--ink-900)', marginTop: '6px' }}>
                {p.panchayat_name}
              </h3>
              <div style={{ fontSize: '13px', color: 'var(--ink-500)', marginTop: '2px' }}>
                {p.block_name} Block, {p.district_name} District
              </div>
            </div>

            {/* Geographical Stats */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '8px',
                padding: '12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--surface-subtle)',
                fontSize: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--ink-700)' }}>
                <Mountain size={14} color="var(--primary-600)" />
                <span>Elev: <strong>{p.elevation_m} m</strong></span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--ink-700)' }}>
                <MapPin size={14} color="var(--primary-600)" />
                <span>Lat: <strong>{p.latitude.toFixed(3)}°</strong></span>
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => onSelectPanchayat(p)}
                className="btn-secondary"
                style={{ flex: 1, padding: '8px 12px', fontSize: '12px' }}
              >
                <ExternalLink size={13} />
                <span>Advisories</span>
              </button>

              <button
                onClick={() => onGenerateForPanchayat(p)}
                className="btn-primary"
                style={{ padding: '8px 12px', fontSize: '12px' }}
                title="Run Micro-Downscaling"
              >
                <Sparkles size={13} />
                <span>Inference</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
