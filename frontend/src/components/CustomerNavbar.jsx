import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LangContext';
import { Award, Globe, LogOut } from 'lucide-react';

export default function CustomerNavbar() {
  const { customerSession, customerLogout } = useAuth();
  const { lang, toggleLang, t } = useLang();

  return (
    <nav
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.85rem 1.75rem',
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--accent-primary) 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px var(--accent-glow)',
          }}
        >
          <Award size={22} color="#ffffff" />
        </div>
        <div>
          <h1
            style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              margin: 0,
            }}
          >
            OrderTrofy
          </h1>
          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
            Steam Verification & Delivery
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        {/* Language switch */}
        <button
          onClick={toggleLang}
          className="btn btn-secondary btn-sm"
          title="Switch Language"
          style={{ gap: '0.35rem' }}
        >
          <Globe size={15} />
          <span>{lang === 'ar' ? 'English' : 'عربي'}</span>
        </button>

        {/* Customer Logout if active session exists */}
        {customerSession && (
          <button
            onClick={customerLogout}
            className="btn btn-danger btn-sm"
            title="تسجيل الخروج من الطلب"
            style={{ gap: '0.35rem' }}
          >
            <LogOut size={15} />
            <span>خروج</span>
          </button>
        )}
      </div>
    </nav>
  );
}
