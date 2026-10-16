import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'var(--accent-primary)', glow = 'var(--accent-glow)' }) {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '1.4rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1.25rem',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 'var(--radius-md)',
          background: `radial-gradient(circle at top left, ${color}33, ${color}11)`,
          border: `1px solid ${color}44`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: `0 0 15px ${glow}`,
        }}
      >
        <Icon size={26} color={color} />
      </div>

      <div>
        <span style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
          {title}
        </span>
        <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.2, margin: '0.2rem 0' }}>
          {value}
        </div>
        {subtitle && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
