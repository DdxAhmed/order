import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import StatCard from '../../components/StatCard';
import {
  KeyRound,
  CheckCircle,
  ShoppingBag,
  Mail,
  Gamepad2,
  Activity,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';

export default function DashboardView({ setCurrentSection }) {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadStats = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/dashboard');
      setData(res);
    } catch (err) {
      console.error('Failed to load dashboard stats', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const counts = data?.counts || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('dashboard')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            نظرة عامة على حالة المخزون، الطلبات النشطة، وصناديق البريد المتزامنة
          </p>
        </div>

        <button
          onClick={loadStats}
          disabled={loading}
          className="btn-alt"
          style={{ gap: '0.5rem', minHeight: 44 }}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>{t('refresh')}</span>
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="stats-grid">
        <StatCard
          title="حسابات متاحة"
          value={counts.available_accounts || 0}
          subtitle="جاهزة للتخصيص الفوري للعملاء"
          icon={KeyRound}
          color="var(--p)"
          glow="rgba(200, 249, 32, 0.4)"
          badge="متوفر"
        />
        <StatCard
          title="حسابات مخصصة"
          value={counts.assigned_accounts || 0}
          subtitle="مرتبطة بطلبات نشطة"
          icon={CheckCircle}
          color="#38bdf8"
          glow="rgba(56, 189, 248, 0.4)"
          badge="نشط"
        />
        <StatCard
          title="إجمالي الطلبات"
          value={counts.orders || 0}
          subtitle="طلبات المتجر المسجلة"
          icon={ShoppingBag}
          color="#a78bfa"
          glow="rgba(167, 139, 250, 0.4)"
        />
        <StatCard
          title="صناديق البريد"
          value={counts.mailboxes || 0}
          subtitle="IMAP & Microsoft Graph"
          icon={Mail}
          color="#fbbf24"
          glow="rgba(251, 191, 36, 0.4)"
        />
      </div>

      {/* Steam Integration Status Banner */}
      <div
        className="card-neon"
        style={{
          padding: '1.5rem 1.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'linear-gradient(135deg, rgba(37, 43, 121, 0.7) 0%, rgba(30, 27, 67, 0.9) 100%)',
          border: '1.5px solid var(--line)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: '16px',
              background: 'rgba(200, 249, 32, 0.12)',
              border: '1px solid rgba(200, 249, 32, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--p)',
              boxShadow: '0 0 20px rgba(200, 249, 32, 0.25)',
            }}
          >
            <Gamepad2 size={28} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.15rem', color: '#fff' }}>
              محلل رسائل Steam Guard Mail Profile
            </div>
            <div style={{ fontSize: '0.875rem', color: 'var(--m)' }}>
              الحالة التشغيلية: <span style={{ color: 'var(--p)', fontWeight: 700 }}>{data?.steam_status || 'نشط ومفعّل'}</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => setCurrentSection('platforms')}
          className="btn-alt"
          style={{ minHeight: 42, padding: '0 20px' }}
        >
          <span>إعدادات Steam</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Split Grid: Recent Activity & Quick Actions */}
      <div className="responsive-split-grid">
        {/* Recent Audit Activity */}
        <div className="card-neon" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={20} color="var(--p)" />
              <span>آخر النشاطات وسجلات التدقيق</span>
            </h3>
            <button
              onClick={() => setCurrentSection('audit')}
              className="btn-alt"
              style={{ minHeight: 34, padding: '0 14px', fontSize: '0.8rem' }}
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
                    padding: '0.85rem 1.1rem',
                    borderRadius: '12px',
                    background: 'rgba(10, 12, 50, 0.45)',
                    border: '1px solid var(--line)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.9rem',
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 700, color: 'var(--p)' }}>{ev.action}</span>
                    <span style={{ margin: '0 0.5rem', color: 'var(--line)' }}>•</span>
                    <span style={{ color: 'var(--m)' }}>{ev.target_type}</span>
                  </div>
                  <span style={{ fontSize: '0.775rem', color: 'var(--m)' }}>
                    {ev.created_at ? new Date(ev.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--m)', fontSize: '0.9rem', textAlign: 'center', padding: '1.5rem' }}>
                لا توجد سجلات تدقيق حديثة
              </div>
            )}
          </div>
        </div>

        {/* Quick Operations */}
        <div className="card-neon" style={{ padding: '1.75rem' }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '1.25rem' }}>
            {t('quick_actions')}
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <button
              onClick={() => setCurrentSection('accounts')}
              className="btn-alt"
              style={{ justifyContent: 'space-between', minHeight: 52, padding: '0 1.25rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <KeyRound size={18} color="var(--p)" />
                <span>إضافة وتعديل حسابات المخزون</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('import')}
              className="btn-alt"
              style={{ justifyContent: 'space-between', minHeight: 52, padding: '0 1.25rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <CheckCircle size={18} color="var(--p)" />
                <span>استيراد جماعي لحسابات عبر CSV</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('orders')}
              className="btn-alt"
              style={{ justifyContent: 'space-between', minHeight: 52, padding: '0 1.25rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <ShoppingBag size={18} color="#38bdf8" />
                <span>إنشاء وتخصيص طلب لعميل</span>
              </span>
              <ArrowRight size={16} />
            </button>

            <button
              onClick={() => setCurrentSection('mailboxes')}
              className="btn-alt"
              style={{ justifyContent: 'space-between', minHeight: 52, padding: '0 1.25rem' }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Mail size={18} color="#fbbf24" />
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
