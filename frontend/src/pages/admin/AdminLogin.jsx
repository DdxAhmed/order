import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useLang } from '../../context/LangContext';
import { useRouter } from '../../context/RouterContext';
import { ShieldCheck, AlertCircle, ArrowLeft, Globe, Eye, EyeOff } from 'lucide-react';

export default function AdminLogin() {
  const { adminUser, adminLogin } = useAuth();
  const { lang, toggleLang, t } = useLang();
  const { navigate } = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (adminUser) {
      navigate('/admin');
    }
  }, [adminUser, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setErrorMsg('الرجاء إدخال البريد الإلكتروني وكلمة المرور');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      await adminLogin(email.trim(), password);
      navigate('/admin');
    } catch (err) {
      setErrorMsg(err.message || 'البريد الإلكتروني أو كلمة المرور غير صحيحة');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ position: 'relative', minHeight: '100vh', background: 'var(--bg)' }}>
      {/* 3D Scene Background */}
      <div className="bg-scene" aria-hidden="true">
        <div className="floor"></div>
        <i className="spark" style={{ '--x': '15%', '--s': '4px', '--d': '12s', '--l': '1s' }}></i>
        <i className="spark" style={{ '--x': '35%', '--s': '3px', '--d': '15s', '--l': '4s' }}></i>
        <i className="spark" style={{ '--x': '65%', '--s': '5px', '--d': '11s', '--l': '2s' }}></i>
        <i className="spark" style={{ '--x': '85%', '--s': '4px', '--d': '14s', '--l': '5s' }}></i>
      </div>

      {/* Top minimal header */}
      <header className="nav-neon" style={{ position: 'relative', zIndex: 10 }}>
        <button
          onClick={() => navigate('/')}
          className="btn-alt"
          style={{ gap: '0.4rem', minHeight: 40, padding: '0 16px', fontSize: '0.85rem' }}
        >
          <ArrowLeft size={16} />
          <span>{t('back_to_store')}</span>
        </button>

        <button
          onClick={toggleLang}
          className="btn-alt"
          style={{ gap: '0.35rem', minHeight: 40, padding: '0 16px', fontSize: '0.85rem' }}
        >
          <Globe size={15} />
          <span>{lang === 'ar' ? 'English' : 'عربي'}</span>
        </button>
      </header>

      {/* Center Login Card with Neon Glowing Border */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem 1rem',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div className="card-neon" style={{ width: '100%', maxWidth: 460 }}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div
              className="logo-badge"
              style={{
                width: 72,
                height: 72,
                borderRadius: '22px',
                marginBottom: '1rem',
                border: '1.5px solid var(--p)',
                boxShadow: '0 0 40px rgba(200, 249, 32, 0.4)',
              }}
            >
              <ShieldCheck size={36} color="var(--p)" />
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 900, marginBottom: '0.35rem' }}>
              لوحة تحكم المسؤول
            </h2>
            <p style={{ color: 'var(--m)', fontSize: '0.9rem' }}>
              تسجيل دخول المشرف لإدارة المخزون وصناديق البريد والطلبات
            </p>
          </div>

          {errorMsg && (
            <div className="alert-neon" role="alert">
              <AlertCircle size={18} />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label className="lbl" htmlFor="admin_email">
                {t('email')}
              </label>
              <input
                id="admin_email"
                type="email"
                className="in"
                placeholder="admin@ordertrofy.store"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="field">
              <label className="lbl" htmlFor="admin_password">
                {t('password')}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="admin_password"
                  type={showPassword ? 'text' : 'password'}
                  className="in"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  style={{ paddingInlineEnd: 48 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  style={{
                    position: 'absolute',
                    insetInlineEnd: 14,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--m)',
                    padding: 4,
                  }}
                  aria-label={showPassword ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-neon" style={{ marginTop: '1.25rem' }}>
              <span>{loading ? 'جاري التحقق...' : t('login')}</span>
              <ShieldCheck size={20} />
            </button>
          </form>

          <div className="sep"></div>

          <p className="note">
            🔒 جلسة مشفرة ومؤمنة بأحدث خوارزميات التشفير ومحددات محاولات الدخول.
          </p>
        </div>
      </div>
    </div>
  );
}
