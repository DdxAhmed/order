import React, { useEffect } from 'react';
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

export default function AdminLayout() {
  const { adminUser, loading } = useAuth();
  const { currentPath, navigate } = useRouter();

  // Route Guard: enforce authentication for all admin routes
  useEffect(() => {
    if (!loading && !adminUser) {
      navigate('/admin/login');
    }
  }, [adminUser, loading, navigate]);

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.1rem',
          color: 'var(--text-secondary)',
          background: 'var(--bg-primary)',
        }}
      >
        جاري التحقق من صلاحيات المسؤول...
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
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AdminNavbar />
      <div style={{ display: 'flex', flex: 1, width: '100%' }}>
        <Sidebar />
        <main style={{ flex: 1, padding: '2rem', overflowX: 'hidden' }}>
          {renderActiveView()}
        </main>
      </div>
    </div>
  );
}
