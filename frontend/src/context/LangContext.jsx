import React, { createContext, useContext, useState, useEffect } from 'react';

const LangContext = createContext(null);

const translations = {
  ar: {
    app_title: 'OrderTrofy',
    portal_subtitle: 'نظام تسليم وتأكيد أكواد Steam الآمن',
    admin_portal: 'لوحة الإدارة',
    customer_portal: 'بوابة العميل',
    dashboard: 'لوحة التحكم',
    accounts: 'المخزون والحسابات',
    orders: 'الطلبات',
    customers: 'العملاء',
    mailboxes: 'صناديق البريد',
    platforms: 'المنصات',
    import: 'استيراد CSV',
    salla_settings: 'إعدادات سلة',
    audit: 'سجل التدقيق',
    logout: 'تسجيل الخروج',
    login: 'تسجيل الدخول',
    email: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    order_number: 'رقم الطلب',
    steam_user: 'اسم المستخدم في Steam',
    open_portal: 'فتح البوابة واستخراج الرمز',
    request_code: 'طلب الرمز',
    code_ready: 'تم استخراج الرمز بنجاح',
    waiting_mail: 'بانتظار وصول البريد...',
    processing: 'جاري استخراج الرمز...',
    status_available: 'متاح',
    status_assigned: 'مخصص',
    status_disabled: 'معطل',
    status_reserved: 'محجوز',
    status_archived: 'مؤرشف',
    save: 'حفظ',
    cancel: 'إلغاء',
    add_account: 'إضافة حساب جديد',
    add_order: 'إنشاء طلب جديد',
    add_customer: 'إضافة عميل',
    add_mailbox: 'إضافة صندوق بريد',
    identifier: 'المعرف / اسم المستخدم',
    platform: 'المنصة',
    notes: 'ملاحظات',
    actions: 'الإجراءات',
    search: 'بحث...',
    status: 'الحالة',
    copy: 'نسخ',
    copied: 'تم النسخ!',
  },
  en: {
    app_title: 'OrderTrofy',
    portal_subtitle: 'Secure Steam Code Delivery & Store Portal',
    admin_portal: 'Admin Portal',
    customer_portal: 'Customer Portal',
    dashboard: 'Dashboard',
    accounts: 'Inventory & Accounts',
    orders: 'Orders',
    customers: 'Customers',
    mailboxes: 'Mailboxes',
    platforms: 'Platforms',
    import: 'CSV Import',
    salla_settings: 'Salla Settings',
    audit: 'Audit Logs',
    logout: 'Logout',
    login: 'Login',
    email: 'Email',
    password: 'Password',
    order_number: 'Order Number',
    steam_user: 'Steam Username',
    open_portal: 'Open Portal & Get Code',
    request_code: 'Request Code',
    code_ready: 'Code Retrieved Successfully',
    waiting_mail: 'Waiting for email...',
    processing: 'Processing code...',
    status_available: 'Available',
    status_assigned: 'Assigned',
    status_disabled: 'Disabled',
    status_reserved: 'Reserved',
    status_archived: 'Archived',
    save: 'Save',
    cancel: 'Cancel',
    add_account: 'Add New Account',
    add_order: 'Create New Order',
    add_customer: 'Add Customer',
    add_mailbox: 'Add Mailbox',
    identifier: 'Identifier / Username',
    platform: 'Platform',
    notes: 'Notes',
    actions: 'Actions',
    search: 'Search...',
    status: 'Status',
    copy: 'Copy',
    copied: 'Copied!',
  },
};

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('ordertrofy_lang') || 'ar');

  useEffect(() => {
    localStorage.setItem('ordertrofy_lang', lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const toggleLang = () => {
    setLang((prev) => (prev === 'ar' ? 'en' : 'ar'));
  };

  const t = (key) => {
    return translations[lang]?.[key] || translations['ar']?.[key] || key;
  };

  return (
    <LangContext.Provider value={{ lang, setLang, toggleLang, t, isRtl: lang === 'ar' }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  const context = useContext(LangContext);
  if (!context) {
    throw new Error('useLang must be used within a LangProvider');
  }
  return context;
}
