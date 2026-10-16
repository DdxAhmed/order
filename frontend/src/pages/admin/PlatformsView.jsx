import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import { Gamepad2, CheckCircle2, AlertCircle, Save } from 'lucide-react';

export default function PlatformsView() {
  const { t } = useLang();

  const [platforms, setPlatforms] = useState([]);
  const [steamConfig, setSteamConfig] = useState(null);
  const [steamProfileJson, setSteamProfileJson] = useState('');
  const [steamEnabled, setSteamEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const loadPlatforms = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/platforms');
      setPlatforms(res.platforms || []);
      if (res.steam) {
        setSteamConfig(res.steam);
        setSteamProfileJson(JSON.stringify(res.steam.mail_profile || {}, null, 2));
        setSteamEnabled(res.steam.is_enabled);
      }
    } catch (err) {
      console.error('Failed to load platforms', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlatforms();
  }, []);

  const handleSaveSteam = async (e) => {
    e.preventDefault();
    setMsg(null);
    setSaving(true);
    try {
      const parsed = JSON.parse(steamProfileJson);
      await api.post('/admin/platforms/steam', {
        profile: parsed,
        enable: steamEnabled,
      });
      setMsg({ type: 'success', text: 'تم حفظ إعدادات Steam بنجاح' });
      await loadPlatforms();
    } catch (err) {
      setMsg({ type: 'danger', text: err.message || 'صيغة JSON غير صحيحة' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
          {t('platforms')}
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          إدارة منصات الألعاب وقواعد التعرف على رسائل Steam Guard
        </p>
      </div>

      {msg && (
        <div className={`alert alert-${msg.type}`}>
          {msg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{msg.text}</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {/* Steam Configuration Editor */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div
                style={{
                  width: 42,
                  height: 42,
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
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Steam Mail Profile</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  قواعد regex والتحقق من مرسل الرسائل
                </span>
              </div>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={steamEnabled}
                onChange={(e) => setSteamEnabled(e.target.checked)}
                style={{ width: 18, height: 18, accentColor: 'var(--accent-primary)' }}
              />
              <span>تفعيل المنصة</span>
            </label>
          </div>

          <form onSubmit={handleSaveSteam}>
            <div className="form-group">
              <label className="form-label">إعدادات JSON لمحلل رسائل Steam</label>
              <textarea
                className="form-textarea"
                rows="14"
                style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', direction: 'ltr' }}
                value={steamProfileJson}
                onChange={(e) => setSteamProfileJson(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '0.5rem' }}
            >
              <Save size={16} />
              <span>{saving ? 'جاري الحفظ...' : 'حفظ إعدادات Steam'}</span>
            </button>
          </form>
        </div>

        {/* Platforms Catalog */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1.25rem' }}>
            كتالوج المنصات المسجلة
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {platforms.map((p) => (
              <div
                key={p.id}
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>{p.name}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Code: {p.code}
                  </div>
                </div>

                <div>
                  {p.is_enabled ? (
                    <span className="badge badge-success">مفعلة</span>
                  ) : (
                    <span className="badge badge-neutral">معطلة</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
