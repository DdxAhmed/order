import React from 'react';

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'var(--accent-primary)',
  glow = 'var(--accent-glow)',
  badge,
}) {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '1.4rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
            {title}
          </span>
          {badge && (
            <span
              style={{
                fontSize: '0.7rem',
                padding: '0.1rem 0.45rem',
                borderRadius: 'var(--radius-full)',
                background: `${color}18`,
                color: color,
                border: `1px solid ${color}33`,
                fontWeight: 700,
              }}
            >
              {badge}
            </span>
          )}
        </div>
        <div
          style={{
            fontSize: '1.9rem',
            fontWeight: 800,
            color: 'var(--text-primary)',
            lineHeight: 1.2,
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </div>
        {subtitle && (
          <span style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
            {subtitle}
          </span>
        )}
      </div>

      <div
        style={{
          width: 54,
          height: 54,
          borderRadius: 'var(--radius-lg)',
          background: `radial-gradient(circle at top left, ${color}33, ${color}10)`,
          border: `1px solid ${color}40`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          boxShadow: `0 0 18px ${glow}`,
          transition: 'transform 0.2s ease',
        }}
      >
        <Icon size={26} color={color} />
      </div>
    </div>
  );
}
