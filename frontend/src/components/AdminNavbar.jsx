import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LangContext';
import { useRouter } from '../context/RouterContext';
import { ShieldCheck, LogOut, Globe, User } from 'lucide-react';

export default function AdminNavbar() {
  const { adminUser, adminLogout } = useAuth();
  const { lang, toggleLang, t } = useLang();
  const { navigate } = useRouter();

  const handleLogout = async () => {
    await adminLogout();
    navigate('/admin/login');
  };

  return (
    <nav
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.85rem 1.75rem',
        background: 'rgba(15, 23, 42, 0.95)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(99, 102, 241, 0.25)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div
        onClick={() => navigate('/admin')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)',
          }}
        >
          <ShieldCheck size={22} color="#ffffff" />
        </div>
        <div>
          <h1
            style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              background: 'linear-gradient(135deg, #ffffff 0%, #e0e7ff 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              margin: 0,
            }}
          >
            OrderTrofy <span style={{ color: 'var(--accent-primary)', fontSize: '0.85rem', fontWeight: 600 }}>Admin</span>
          </h1>
          <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
            لوحة الإدارة المركزية لحسابات وصناديق Steam
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

        {/* Admin User Info & Logout */}
        {adminUser && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.35rem 0.75rem',
                background: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.8rem',
              }}
            >
              <User size={14} color="var(--accent-primary)" />
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {adminUser.display_name || adminUser.email}
              </span>
              <span
                style={{
                  fontSize: '0.65rem',
                  textTransform: 'uppercase',
                  padding: '0.1rem 0.4rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--accent-primary)',
                  color: '#ffffff',
                  fontWeight: 700,
                }}
              >
                {adminUser.role}
              </span>
            </div>

            <button
              onClick={handleLogout}
              className="btn btn-secondary btn-sm"
              title="تسجيل الخروج"
              style={{ color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}
            >
              <LogOut size={16} />
              <span>خروج</span>
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
