import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import { History, Filter, ChevronDown, ChevronUp, Code } from 'lucide-react';

export default function AuditView() {
  const { t } = useLang();

  const [events, setEvents] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [platformFilter, setPlatformFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  const loadAuditEvents = async () => {
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
  };

  useEffect(() => {
    loadAuditEvents();
  }, [platformFilter]);

  const toggleExpand = (id) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('audit')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            سجلات التدقيق الأمني لجميع العمليات الحساسة في النظام
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <select
            className="form-select"
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            style={{ width: 'auto', minWidth: 170 }}
          >
            <option value="">جميع المنصات</option>
            {platforms.map((p) => (
              <option key={p.code} value={p.code}>
                {p.name}
              </option>
            ))}
          </select>
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
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>جاري تحميل السجلات...</td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  لا توجد سجلات تدقيق
                </td>
              </tr>
            ) : (
              events.map((ev) => {
                const isExpanded = expandedId === ev.id;
                return (
                  <React.Fragment key={ev.id}>
                    <tr>
                      <td style={{ fontWeight: 700, color: '#c7d2fe' }}>
                        {ev.action}
                      </td>
                      <td>
                        <span className="badge badge-neutral">{ev.target_type}</span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {ev.target_id || '—'}
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>
                        {ev.actor_admin_id ? (
                          <span style={{ color: 'var(--accent-secondary)' }}>مسؤول</span>
                        ) : ev.actor_telegram_id ? (
                          <span style={{ color: 'var(--accent-primary)' }}>Telegram</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>النظام</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.825rem' }}>
                        {ev.created_at ? new Date(ev.created_at).toLocaleString('ar-EG') : '—'}
                      </td>
                      <td>
                        {ev.metadata && Object.keys(ev.metadata).length > 0 ? (
                          <button
                            onClick={() => toggleExpand(ev.id)}
                            className="btn btn-ghost btn-sm"
                            style={{ gap: '0.25rem' }}
                          >
                            <Code size={13} />
                            <span>{isExpanded ? 'إخفاء' : 'تفاصيل'}</span>
                            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>—</span>
                        )}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan="6" style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem 1.5rem' }}>
                          <pre
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: '0.8rem',
                              color: '#38bdf8',
                              margin: 0,
                              direction: 'ltr',
                              whiteSpace: 'pre-wrap',
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
