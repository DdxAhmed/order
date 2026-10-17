import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import { Gamepad2, CheckCircle2, AlertCircle, Save } from 'lucide-react';

export default function PlatformsView() {
  const { t } = useLang();

  const [platforms, setPlatforms] = useState([]);
  const [steamProfileJson, setSteamProfileJson] = useState('');
  const [steamEnabled, setSteamEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const loadPlatforms = useCallback(async () => {
    try {
      const res = await api.get('/admin/platforms');
      setPlatforms(res.platforms || []);
      if (res.steam) {
        setSteamProfileJson(JSON.stringify(res.steam.mail_profile || {}, null, 2));
        setSteamEnabled(res.steam.is_enabled);
      }
    } catch (err) {
      console.error('Failed to load platforms', err);
    }
  }, []);

  useEffect(() => {
    loadPlatforms();
  }, [loadPlatforms]);

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
      setMsg({ type: 'success', text: 'تم حفظ وتفعيل إعدادات Steam بنجاح' });
      await loadPlatforms();
    } catch (err) {
      setMsg({ type: 'danger', text: err.message || 'صيغة JSON غير صحيحة' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
          {t('platforms')}
        </h2>
        <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
          إدارة منصات الألعاب، إعدادات التعرف على رسائل Steam Guard وقواعد الاستخراج الآلي
        </p>
      </div>

      {msg && (
        <div className={`alert-neon ${msg.type === 'success' ? 'alert-success' : ''}`}>
          {msg.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
          <span>{msg.text}</span>
        </div>
      )}

      <div className="responsive-split-grid">
        {/* Steam Configuration Editor */}
        <div className="card-neon" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '16px',
                  background: 'rgba(200, 249, 32, 0.12)',
                  border: '1px solid rgba(200, 249, 32, 0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--p)',
                  boxShadow: '0 0 20px rgba(200, 249, 32, 0.2)',
                }}
              >
                <Gamepad2 size={26} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>Steam Mail Profile</h3>
                <span style={{ fontSize: '0.825rem', color: 'var(--m)' }}>
                  قواعد Regex وعناوين مرسل رسائل Steam
                </span>
              </div>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 700 }}>
              <input
                type="checkbox"
                checked={steamEnabled}
                onChange={(e) => setSteamEnabled(e.target.checked)}
                style={{ width: 18, height: 18, accentColor: 'var(--p)' }}
              />
              <span style={{ color: steamEnabled ? 'var(--p)' : 'var(--m)' }}>تفعيل المنصة</span>
            </label>
          </div>

          <form onSubmit={handleSaveSteam}>
            <div className="field">
              <label className="lbl">إعدادات JSON لمحلل رسائل Steam</label>
              <textarea
                className="in"
                rows={13}
                style={{ fontFamily: 'var(--font-mono)', fontSize: '0.875rem', direction: 'ltr', lineHeight: 1.5 }}
                value={steamProfileJson}
                onChange={(e) => setSteamProfileJson(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="btn-neon"
              style={{ marginTop: '0.5rem' }}
            >
              <Save size={18} />
              <span>{saving ? 'جاري الحفظ...' : 'حفظ إعدادات Steam'}</span>
            </button>
          </form>
        </div>

        {/* Platforms Catalog */}
        <div className="card-neon" style={{ padding: '1.75rem' }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '1.25rem' }}>
            المنصات المسجلة في النظام
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {platforms.map((p) => (
              <div
                key={p.code}
                style={{
                  padding: '1rem 1.25rem',
                  borderRadius: '14px',
                  background: 'rgba(10, 12, 50, 0.5)',
                  border: '1px solid var(--line)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <Gamepad2 size={20} color="var(--p)" />
                  <div>
                    <div style={{ fontWeight: 800, color: '#fff' }}>{p.name}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--m)', fontFamily: 'var(--font-mono)' }}>{p.code}</div>
                  </div>
                </div>

                <div>
                  {p.is_enabled ? (
                    <span className="badge badge-success">مفعلة</span>
                  ) : (
                    <span className="badge badge-neutral">غير مفعلة</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="sep"></div>

          <div style={{ padding: '1rem', borderRadius: '12px', background: 'rgba(200, 249, 32, 0.06)', border: '1px solid rgba(200, 249, 32, 0.2)', fontSize: '0.85rem', color: 'var(--m)' }}>
            💡 منصة Steam هي المنصة المعتمدة لتسليم الأكواد الآلية للعملاء مع دعم التشفير والتحقق من مرسل البريد الإلكتروني.
          </div>
        </div>
      </div>
    </div>
  );
}
