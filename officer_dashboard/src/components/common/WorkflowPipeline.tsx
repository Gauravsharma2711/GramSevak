import React, { useState } from 'react';
import { 
  Building2, 
  Cpu, 
  CloudRain, 
  FileText, 
  UserCheck, 
  CheckCircle2, 
  ArrowRight,
  ChevronDown,
  ChevronUp,
  ShieldCheck 
} from 'lucide-react';

interface WorkflowPipelineProps {
  activeStep?: number;
  initiallyExpanded?: boolean;
}

export const WorkflowPipeline: React.FC<WorkflowPipelineProps> = ({ initiallyExpanded = false }) => {
  const [isExpanded, setIsExpanded] = useState(initiallyExpanded);

  const steps = [
    {
      id: 1,
      title: 'Block Forecast',
      subtitle: 'Official IMD 25-50km',
      icon: <Building2 size={16} />,
    },
    {
      id: 2,
      title: 'ML Downscaling',
      subtitle: 'Terrain & Geo Features',
      icon: <Cpu size={16} />,
    },
    {
      id: 3,
      title: 'Panchayat Forecast',
      subtitle: 'Hyper-local 3-8km',
      icon: <CloudRain size={16} />,
    },
    {
      id: 4,
      title: 'Agro-Advisory',
      subtitle: 'Deterministic Rules',
      icon: <FileText size={16} />,
    },
    {
      id: 5,
      title: 'Officer Review',
      subtitle: 'Human-in-the-Loop',
      icon: <UserCheck size={16} />,
    },
    {
      id: 6,
      title: 'Farmer Delivery',
      subtitle: 'Approved Guidance',
      icon: <CheckCircle2 size={16} />,
    },
  ];

  return (
    <section
      className="app-card"
      style={{
        backgroundColor: 'var(--surface-subtle)',
        border: 'var(--border-subtle)',
        padding: '14px 18px',
        boxShadow: 'none',
      }}
      aria-label="GramSevak Workflow Pipeline"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={16} color="var(--primary-600)" />
          <span style={{ fontSize: '13px', fontWeight: 650, color: 'var(--ink-900)' }}>
            MoES • IMD Agromet Protocol Pipeline
          </span>
          <span style={{ fontSize: '11px', color: 'var(--ink-500)' }} className="hide-on-mobile">
            (6-stage deterministic & verified flow)
          </span>
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="btn-secondary"
          style={{
            padding: '4px 10px',
            fontSize: '11px',
            minHeight: '28px',
            gap: '4px',
            borderRadius: 'var(--radius-pill)',
          }}
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Collapse pipeline stages' : 'Expand pipeline stages'}
        >
          <span>{isExpanded ? 'Hide Pipeline Stages' : 'View Protocol Stages'}</span>
          {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      {isExpanded && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            overflowX: 'auto',
            gap: '8px',
            paddingTop: '14px',
            marginTop: '10px',
            borderTop: 'var(--border-subtle)',
          }}
          className="fade-in"
        >
        {steps.map((step, idx) => (
          <React.Fragment key={step.id}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                minWidth: '140px',
                backgroundColor: 'var(--surface-subtle)',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--ink-100)',
              }}
            >
              <div
                style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--primary-050)',
                  color: 'var(--primary-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {step.icon}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ink-900)', whiteSpace: 'nowrap' }}>
                  {step.title}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--ink-500)', whiteSpace: 'nowrap' }}>
                  {step.subtitle}
                </div>
              </div>
            </div>

            {idx < steps.length - 1 && (
              <ArrowRight size={14} color="var(--ink-300)" style={{ flexShrink: 0 }} />
            )}
          </React.Fragment>
        ))}
        </div>
      )}
    </section>
  );
};
