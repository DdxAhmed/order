import React from 'react';
import { useLang } from '../context/LangContext';
import { useRouter } from '../context/RouterContext';
import {
  LayoutDashboard,
  KeyRound,
  ShoppingBag,
  Users,
  Mail,
  Gamepad2,
  FileSpreadsheet,
  Store,
  History,
} from 'lucide-react';

export default function Sidebar() {
  const { t } = useLang();
  const { currentPath, navigate } = useRouter();

  const menuItems = [
    { path: '/admin', label: t('dashboard'), icon: LayoutDashboard },
    { path: '/admin/orders', label: t('orders'), icon: ShoppingBag },
    { path: '/admin/accounts', label: t('accounts'), icon: KeyRound },
    { path: '/admin/customers', label: t('customers'), icon: Users },
    { path: '/admin/mailboxes', label: t('mailboxes'), icon: Mail },
    { path: '/admin/platforms', label: t('platforms'), icon: Gamepad2 },
    { path: '/admin/import', label: t('import'), icon: FileSpreadsheet },
    { path: '/admin/salla', label: t('salla_settings'), icon: Store },
    { path: '/admin/audit', label: t('audit'), icon: History },
  ];

  return (
    <aside
      style={{
        width: 250,
        flexShrink: 0,
        background: 'rgba(15, 23, 42, 0.7)',
        backdropFilter: 'blur(16px)',
        borderLeft: '1px solid var(--border-subtle)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.85rem',
        minHeight: 'calc(100vh - 65px)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPath === item.path || (item.path === '/admin' && currentPath === '/admin/');
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.7rem 0.95rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: isActive ? 700 : 500,
                color: isActive ? '#ffffff' : 'var(--text-secondary)',
                background: isActive
                  ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(99, 102, 241, 0.08) 100%)'
                  : 'transparent',
                border: isActive
                  ? '1px solid rgba(99, 102, 241, 0.35)'
                  : '1px solid transparent',
                textAlign: 'inherit',
                transition: 'all 0.2s ease',
                width: '100%',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.04)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }
              }}
            >
              <Icon
                size={18}
                color={isActive ? 'var(--accent-primary)' : 'var(--text-muted)'}
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
