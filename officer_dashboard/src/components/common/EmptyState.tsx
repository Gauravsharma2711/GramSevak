import React from 'react';
import { LucideIcon, FileText } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  illustration?: React.ReactNode;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = FileText,
  illustration,
  title,
  description,
  actionText,
  onAction,
}) => {
  return (
    <div
      className="app-card animate-fade-in"
      style={{
        textAlign: 'center',
        padding: '48px 24px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      role="status"
    >
      {illustration ? (
        <div style={{ marginBottom: '18px' }}>
          {illustration}
        </div>
      ) : (
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: 'var(--radius-pill)',
            backgroundColor: 'var(--primary-050)',
            color: 'var(--primary-700)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
          }}
        >
          <Icon size={28} strokeWidth={1.75} />
        </div>
      )}

      <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ink-900)', marginBottom: '6px' }}>
        {title}
      </h3>

      <p style={{ fontSize: '13px', color: 'var(--ink-500)', maxWidth: '420px', lineHeight: '20px', marginBottom: actionText ? '20px' : '0' }}>
        {description}
      </p>

      {actionText && onAction && (
        <button onClick={onAction} className="btn-primary" style={{ fontSize: '13px' }}>
          {actionText}
        </button>
      )}
    </div>
  );
};
