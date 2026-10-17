import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import { ChevronDown, ChevronUp, Code, RefreshCw } from 'lucide-react';

export default function AuditView() {
  const { t } = useLang();

  const [events, setEvents] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [platformFilter, setPlatformFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  const loadAuditEvents = useCallback(async () => {
    setLoading(true);
    try {
      const query = platformFilter ? `?platform=${encodeURIComponent(platformFilter)}` : '';
      const res = await api.get(`/admin/audit${query}`);
      setEvents(res.events || []);
      setPlatforms(res.platforms || []);
    } catch (err) {
      console.error('Failed to load audit events', err);
    } finally {
      setLoading(false);
    }
  }, [platformFilter]);

  useEffect(() => {
    loadAuditEvents();
  }, [loadAuditEvents]);

  const toggleExpand = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('audit')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            سجلات التدقيق الأمني لجميع العمليات الحساسة وتتبع محاولات استخراج الأكواد
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select
            className="in"
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            style={{ width: 'auto', minWidth: 170, minHeight: 44 }}
          >
            <option value="">جميع المنصات</option>
            {platforms.map((p) => (
              <option key={p.code} value={p.code}>{p.name}</option>
            ))}
          </select>

          <button
            onClick={loadAuditEvents}
            disabled={loading}
            className="btn-alt"
            style={{ minHeight: 44, padding: '0 16px' }}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>{t('refresh')}</span>
          </button>
        </div>
      </div>

      <div className="table-container">
        <table className="modern-table">
          <thead>
            <tr>
              <th>العملية (Action)</th>
              <th>الهدف (Target)</th>
              <th>المعرف</th>
              <th>المسؤول / الفاعل</th>
              <th>التاريخ والوقت</th>
              <th>البيانات</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                    <RefreshCw size={18} className="animate-spin" color="var(--p)" />
                    <span>جاري تحميل السجلات...</span>
                  </div>
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  لا توجد سجلات تدقيق مطابقة
                </td>
              </tr>
            ) : (
              events.map((ev) => {
                const isExpanded = expandedId === ev.id;
                return (
                  <React.Fragment key={ev.id}>
                    <tr>
                      <td style={{ fontWeight: 800, color: 'var(--p)' }}>
                        {ev.action}
                      </td>
                      <td>
                        <span className="badge badge-neutral">{ev.target_type}</span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--m)' }}>
                        {ev.target_id || '—'}
                      </td>
                      <td style={{ fontSize: '0.9rem' }}>
                        {ev.actor_admin_id ? (
                          <span style={{ color: 'var(--p)', fontWeight: 600 }}>مشرف</span>
                        ) : ev.actor_telegram_id ? (
                          <span style={{ color: '#38bdf8' }}>Telegram</span>
                        ) : (
                          <span style={{ color: 'var(--m)' }}>النظام</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--m)', fontSize: '0.85rem' }}>
                        {ev.created_at ? new Date(ev.created_at).toLocaleString('ar-EG') : '—'}
                      </td>
                      <td>
                        {ev.metadata && Object.keys(ev.metadata).length > 0 ? (
                          <button
                            type="button"
                            onClick={() => toggleExpand(ev.id)}
                            className="btn-alt"
                            style={{ minHeight: 32, padding: '0 10px', fontSize: '0.8rem', gap: '0.35rem' }}
                          >
                            <Code size={13} />
                            <span>{isExpanded ? 'إخفاء' : 'تفاصيل'}</span>
                            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                        ) : (
                          <span style={{ color: 'var(--m)', fontSize: '0.8rem' }}>—</span>
                        )}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan="6" style={{ background: 'rgba(10, 12, 50, 0.75)', padding: '1rem 1.5rem' }}>
                          <pre
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: '0.825rem',
                              color: 'var(--p)',
                              margin: 0,
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                              direction: 'ltr',
                              textAlign: 'left',
                              background: 'rgba(0, 0, 0, 0.3)',
                              padding: '1rem',
                              borderRadius: '8px',
                              border: '1px solid var(--line)',
                            }}
                          >
                            {JSON.stringify(ev.metadata, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
