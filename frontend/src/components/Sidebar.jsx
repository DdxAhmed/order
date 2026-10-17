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
  ShieldCheck,
} from 'lucide-react';

export default function Sidebar({ isOpen, onClose }) {
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

  const handleItemClick = (path) => {
    navigate(path);
    if (onClose) onClose();
  };

  return (
    <aside className={`admin-sidebar ${isOpen ? 'open' : ''}`}>
      <div className="admin-sidebar-drawer">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPath === item.path || (item.path === '/admin' && currentPath === '/admin/');

          return (
            <button
              key={item.path}
              type="button"
              onClick={() => handleItemClick(item.path)}
              className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon
                size={18}
                className="nav-icon"
                color={isActive ? 'var(--accent-primary)' : 'var(--text-muted)'}
              />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div
        style={{
          marginTop: 'auto',
          paddingTop: '1.25rem',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          fontSize: '0.775rem',
          color: 'var(--text-muted)',
        }}
      >
        <ShieldCheck size={14} color="var(--success)" />
        <span>OrderTrofy v1.2 • نظام آمن</span>
      </div>
    </aside>
  );
}
