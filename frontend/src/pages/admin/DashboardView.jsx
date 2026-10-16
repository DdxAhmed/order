import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import StatCard from '../../components/StatCard';
import {
  KeyRound,
  CheckCircle,
  ShoppingBag,
  Users,
  Mail,
  AlertTriangle,
  Gamepad2,
  Activity,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';

export default function DashboardView({ setCurrentSection }) {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const res = await api.get('/admin/dashboard');
        setData(res);
      } catch (err) {
        console.error('Failed to load dashboard stats', err);
      } finally {
        setLoading(false);
      }
    }
    loadStats();
  }, []);

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>جاري تحميل الإحصائيات...</div>;
  }

  const counts = data?.counts || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div>
        <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
          {t('dashboard')}
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          نظرة عامة على حالة المخزون، الطلبات، وصناديق البريد النشطة
        </p>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
        }}
      >
        <StatCard
          title="حسابات متاحة"
          value={counts.available_accounts || 0}
          subtitle="جاهزة للتخصيص الفوري"
          icon={KeyRound}
          color="#10b981"
          glow="rgba(16, 185, 129, 0.3)"
        />
        <StatCard
          title="حسابات مخصصة"
          value={counts.assigned_accounts || 0}
          subtitle="مرتبطة بطلبات نشطة"
          icon={CheckCircle}
          color="#6366f1"
          glow="rgba(99, 102, 241, 0.3)"
        />
        <StatCard
          title="إجمالي الطلبات"
          value={counts.orders || 0}
          subtitle="طلبات المتجر المسجلة"
          icon={ShoppingBag}
          color="#06b6d4"
          glow="rgba(6, 182, 212, 0.3)"
        />
        <StatCard
          title="صناديق البريد النشطة"
          value={counts.mailboxes || 0}
          subtitle="IMAP & Microsoft Graph"
          icon={Mail}
          color="#f59e0b"
          glow="rgba(245, 158, 11, 0.3)"
        />
      </div>

      {/* Steam Integration Status Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'linear-gradient(135deg, rgba(22, 32, 54, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)',
          border: '1px solid rgba(6, 182, 212, 0.25)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(6, 182, 212, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8',
            }}
          >
            <Gamepad2 size={24} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#f8fafc' }}>
              حالة محلل رسائل Steam Mail Profile
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              الحالة الحالية: <span style={{ color: '#38bdf8', fontWeight: 600 }}>{data?.steam_status}</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => setCurrentSection('platforms')}
          className="btn btn-secondary btn-sm"
        >
          <span>إعدادات Steam</span>
        </button>
      </div>

      {/* Recent Events & Quick Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {/* Recent Audit Activity */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={18} color="var(--accent-primary)" />
              <span>آخر النشاطات وسجلات التدقيق</span>
            </h3>
            <button
              onClick={() => setCurrentSection('audit')}
              className="btn btn-ghost btn-sm"
            >
              عرض الكل
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {data?.recent_events?.length ? (
              data.recent_events.map((ev) => (
                <div
                  key={ev.id}
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.875rem',
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ev.action}</span>
                    <span style={{ margin: '0 0.5rem', color: 'var(--text-muted)' }}>•</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{ev.target_type}</span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {ev.created_at ? new Date(ev.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', textAlign: 'center', padding: '1rem' }}>
                لا توجد سجلات تدقيق حديثة
              </div>
            )}
          </div>
        </div>

        {/* Quick Operations */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1.25rem' }}>
            إجراءات سريعة
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <button
              onClick={() => setCurrentSection('accounts')}
              className="btn btn-secondary"
              style={{ justifyContent: 'space-between', padding: '0.9rem 1.1rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <KeyRound size={18} color="var(--accent-primary)" />
                <span>إضافة وتعديل حسابات المخزون</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('import')}
              className="btn btn-secondary"
              style={{ justifyContent: 'space-between', padding: '0.9rem 1.1rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle size={18} color="var(--success)" />
                <span>استيراد جماعي لحسابات عبر CSV</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('orders')}
              className="btn btn-secondary"
              style={{ justifyContent: 'space-between', padding: '0.9rem 1.1rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShoppingBag size={18} color="var(--accent-secondary)" />
                <span>إنشاء وتخصيص طلب لعميل</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('mailboxes')}
              className="btn btn-secondary"
              style={{ justifyContent: 'space-between', padding: '0.9rem 1.1rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Mail size={18} color="var(--warning)" />
                <span>فحص واختبار صناديق البريد</span>
              </span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
