import React from 'react';
import { AuthProvider } from './context/AuthContext';
import { LangProvider } from './context/LangContext';
import { RouterProvider, useRouter } from './context/RouterContext';

// Layouts
import CustomerLayout from './layouts/CustomerLayout';
import AdminLayout from './layouts/AdminLayout';

// Pages
import CustomerPortal from './pages/customer/CustomerPortal';
import AdminLogin from './pages/admin/AdminLogin';

function MainRouter() {
  const { currentPath } = useRouter();

  // 1. Dedicated Admin Login Route
  if (currentPath === '/admin/login') {
    return <AdminLogin />;
  }

  // 2. Dedicated Protected Admin Routes
  if (currentPath.startsWith('/admin')) {
    return <AdminLayout />;
  }

  // 3. Customer Portal (Default / Public Root)
  return (
    <CustomerLayout>
      <CustomerPortal />
    </CustomerLayout>
  );
}

export default function App() {
  return (
    <LangProvider>
      <AuthProvider>
        <RouterProvider>
          <MainRouter />
        </RouterProvider>
      </AuthProvider>
    </LangProvider>
  );
}
