import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useLang } from '../context/LangContext';
import { useRouter } from '../context/RouterContext';
import { ShieldCheck, LogOut, Globe, User, Menu, X, ArrowLeft } from 'lucide-react';

export default function AdminNavbar({ sidebarOpen, onToggleSidebar }) {
  const { adminUser, adminLogout } = useAuth();
  const { lang, toggleLang, t } = useLang();
  const { navigate } = useRouter();

  const handleLogout = async () => {
    await adminLogout();
    navigate('/admin/login');
  };

  return (
    <header className="top-navbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        {/* Mobile Sidebar Hamburger Toggle */}
        <button
          type="button"
          onClick={onToggleSidebar}
          className="btn btn-secondary btn-sm"
          style={{ display: 'inline-flex', padding: '0.45rem', border: '1px solid var(--border-subtle)' }}
          aria-label={sidebarOpen ? 'إغلاق القائمة' : 'فتح القائمة'}
        >
          {sidebarOpen ? <X size={19} /> : <Menu size={19} />}
        </button>

        {/* Brand / Logo */}
        <div
          onClick={() => navigate('/admin')}
          className="brand-badge"
          title="الرئيسية"
        >
          <div
            className="brand-icon"
            style={{
              background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
              boxShadow: '0 0 15px rgba(99, 102, 241, 0.4)',
            }}
          >
            <ShieldCheck size={22} color="#ffffff" />
          </div>
          <div>
            <h1 className="brand-title">
              OrderTrofy <span style={{ color: 'var(--accent-primary)', fontSize: '0.85rem', fontWeight: 700 }}>Admin</span>
            </h1>
            <span className="brand-subtitle hide-on-mobile">
              لوحة الإدارة المركزية لحسابات وصناديق Steam
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
        {/* Customer Portal Quick Link */}
        <button
          onClick={() => navigate('/')}
          className="btn btn-ghost btn-sm hide-on-mobile"
          title="عرض بوابة العميل"
          style={{ gap: '0.4rem', color: 'var(--text-secondary)' }}
        >
          <ArrowLeft size={15} />
          <span>بوابة العميل</span>
        </button>

        {/* Language switch */}
        <button
          onClick={toggleLang}
          className="btn btn-secondary btn-sm"
          title="تغيير اللغة"
          style={{ gap: '0.35rem' }}
        >
          <Globe size={15} />
          <span>{lang === 'ar' ? 'English' : 'عربي'}</span>
        </button>

        {/* Admin User Info & Logout */}
        {adminUser && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
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
              <span
                style={{
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  maxWidth: 130,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
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
              title={t('logout')}
              style={{ color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}
            >
              <LogOut size={15} />
              <span className="hide-on-mobile">{t('logout')}</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
