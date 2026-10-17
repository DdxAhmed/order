import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LangContext';
import { Award, Globe, LogOut } from 'lucide-react';

export default function CustomerNavbar() {
  const { customerSession, customerLogout } = useAuth();
  const { lang, toggleLang, t } = useLang();

  return (
    <header className="top-navbar">
      <div className="brand-badge">
        <div
          className="brand-icon"
          style={{
            background: 'linear-gradient(135deg, var(--accent-primary) 0%, #06b6d4 100%)',
            boxShadow: '0 0 15px var(--accent-glow)',
          }}
        >
          <Award size={22} color="#ffffff" />
        </div>
        <div>
          <h1 className="brand-title">
            OrderTrofy
          </h1>
          <span className="brand-subtitle hide-on-mobile">
            {t('portal_subtitle')}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {/* Language switch */}
        <button
          onClick={toggleLang}
          className="btn btn-secondary btn-sm"
          title="Switch Language / تغيير اللغة"
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
            title={t('logout')}
            style={{ gap: '0.35rem' }}
          >
            <LogOut size={15} />
            <span>{t('logout')}</span>
          </button>
        )}
      </div>
    </header>
  );
}
