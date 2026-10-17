import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useRouter } from '../context/RouterContext';
import AdminNavbar from '../components/AdminNavbar';
import Sidebar from '../components/Sidebar';

// Admin View Components
import DashboardView from '../pages/admin/DashboardView';
import AccountsView from '../pages/admin/AccountsView';
import OrdersView from '../pages/admin/OrdersView';
import CustomersView from '../pages/admin/CustomersView';
import MailboxesView from '../pages/admin/MailboxesView';
import PlatformsView from '../pages/admin/PlatformsView';
import ImportView from '../pages/admin/ImportView';
import SallaAdminView from '../pages/admin/SallaAdminView';
import AuditView from '../pages/admin/AuditView';
import { ShieldCheck, Loader2 } from 'lucide-react';

export default function AdminLayout() {
  const { adminUser, loading } = useAuth();
  const { currentPath, navigate } = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Route Guard: enforce authentication for all admin routes
  useEffect(() => {
    if (!loading && !adminUser) {
      navigate('/admin/login');
    }
  }, [adminUser, loading, navigate]);

  // Close mobile sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [currentPath]);

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          color: 'var(--text-secondary)',
          background: 'var(--bg-base)',
        }}
      >
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 20px var(--accent-glow)',
          }}
        >
          <ShieldCheck size={26} color="#ffffff" />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '1rem' }}>
          <Loader2 size={18} className="animate-spin" color="var(--accent-primary)" />
          <span>جاري التحقق من صلاحيات المسؤول...</span>
        </div>
      </div>
    );
  }

  if (!adminUser) {
    return null; // Will redirect via useEffect
  }

  const navigateToSection = (section) => {
    const target = section === 'dashboard' ? '/admin' : `/admin/${section}`;
    navigate(target);
  };

  // Determine current active component based on pathname
  const renderActiveView = () => {
    const cleanPath = currentPath.replace(/\/$/, '') || '/admin';

    switch (cleanPath) {
      case '/admin':
        return <DashboardView setCurrentSection={navigateToSection} />;
      case '/admin/orders':
        return <OrdersView />;
      case '/admin/accounts':
        return <AccountsView />;
      case '/admin/customers':
        return <CustomersView />;
      case '/admin/mailboxes':
        return <MailboxesView />;
      case '/admin/platforms':
        return <PlatformsView />;
      case '/admin/import':
        return <ImportView setCurrentSection={navigateToSection} />;
      case '/admin/salla':
        return <SallaAdminView />;
      case '/admin/audit':
        return <AuditView />;
      default:
        return <DashboardView setCurrentSection={navigateToSection} />;
    }
  };

  return (
    <div className="admin-shell">
      <AdminNavbar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
      />
      <div className="admin-body">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div
          className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
        <main className="admin-main">
          {renderActiveView()}
        </main>
      </div>
    </div>
  );
}
