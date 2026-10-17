import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useLang } from '../../context/LangContext';
import CopyButton from '../../components/CopyButton';
import {
  Gamepad2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Lock,
  ArrowRight,
  ShieldCheck,
  Key,
  Clock,
  Sparkles,
} from 'lucide-react';

export default function CustomerPortal() {
  const { customerSession, customerLogin, customerLogout } = useAuth();
  const { t, lang } = useLang();

  // Mode: 'credentials' (Order Ref + Account) vs 'token' (Activation Token)
  const [accessMode, setAccessMode] = useState('credentials');

  // Credentials Form state
  const [platform, setPlatform] = useState('steam');
  const [orderRef, setOrderRef] = useState('');
  const [username, setUsername] = useState('');

  // Activation Token Form state
  const [activationToken, setActivationToken] = useState('');

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Portal Data state
  const [portalData, setPortalData] = useState(null);
  const [verifyingId, setVerifyingId] = useState(null);
  const [pollInterval, setPollInterval] = useState(null);

  // Check URL parameters and pathname on mount (e.g., ?activate=TOKEN or /activate/TOKEN or ?order=REF&user=USER)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('activate') || params.get('token');
    const orderParam = params.get('order');
    const userParam = params.get('user');

    const path = window.location.pathname || '';
    const pathTokenMatch = path.match(/^\/activate\/([^\s/?#]+)/i);
    const finalToken = tokenParam || (pathTokenMatch ? pathTokenMatch[1] : null);

    if (finalToken) {
      setAccessMode('token');
      setActivationToken(finalToken);
    } else if (orderParam) {
      setOrderRef(orderParam);
      if (userParam) setUsername(userParam);
    }
  }, []);

  // Fetch portal details if session exists
  const fetchPortalData = useCallback(async () => {
    try {
      const data = await api.get('/customer/portal');
      setPortalData(data);
      return data;
    } catch (err) {
      console.warn('Portal session expired or invalid:', err.message);
      customerLogout();
    }
  }, [customerLogout]);

  useEffect(() => {
    if (customerSession) {
      fetchPortalData();
    }
  }, [customerSession, fetchPortalData]);

  // Clean up polling interval
  useEffect(() => {
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [pollInterval]);

  // Handle Credentials Access
  const handleAccessSubmit = async (e) => {
    e.preventDefault();
    if (!orderRef.trim() || !username.trim()) {
      setErrorMsg('الرجاء إدخال رقم الطلب واسم المستخدم');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.post('/customer/access', {
        order_reference: orderRef.trim(),
        steam_username: username.trim(),
        platform_code: platform,
      });
      customerLogin(res.session_token, res);
      await fetchPortalData();
    } catch (err) {
      setErrorMsg(err.message || 'بيانات الدخول غير صحيحة أو الطلب غير موجود');
    } finally {
      setLoading(false);
    }
  };

  // Handle Token Activation
  const handleActivationSubmit = async (e) => {
    e.preventDefault();
    if (!activationToken.trim()) {
      setErrorMsg('الرجاء إدخال رمز أو رابط التفعيل');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.post('/customer/activate', {
        activation_token: activationToken.trim(),
      });
      customerLogin(res.session_token, res);
      await fetchPortalData();
    } catch (err) {
      setErrorMsg(err.message || 'رمز التفعيل غير صالح أو منتهي الصلاحية');
    } finally {
      setLoading(false);
    }
  };

  // Trigger Code Verification for an Assignment
  const handleRequestCode = async (assignmentId) => {
    setVerifyingId(assignmentId);
    setErrorMsg(null);
    try {
      await api.post(`/customer/assignments/${assignmentId}/verify`, {});
      await fetchPortalData();

      // Poll every 3.5 seconds up to 30 times (approx 105 seconds)
      if (pollInterval) clearInterval(pollInterval);
      let count = 0;
      const interval = setInterval(async () => {
        count += 1;
        const fresh = await fetchPortalData();
        const asgn = fresh?.assignments?.find((a) => a.assignment_id === assignmentId);
        if (asgn?.verification_code || asgn?.current_status === 'failed' || count > 30) {
          clearInterval(interval);
          setVerifyingId(null);
        }
      }, 3500);
      setPollInterval(interval);
    } catch (err) {
      setErrorMsg(err.message || 'تعذر طلب الرمز حاليًا');
      setVerifyingId(null);
    }
  };

  // 1. Logged-in View: Customer Portal & OTP Retrieval
  if (customerSession && portalData) {
    return (
      <div className="wrap" style={{ gridTemplateColumns: '1fr', maxWidth: 860 }}>
        <section className="card-neon">
          <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
            <div
              style={{
                display: 'inline-flex',
                padding: '0.45rem 1.1rem',
                borderRadius: 'var(--radius-full)',
                background: 'rgba(200, 249, 32, 0.14)',
                border: '1.5px solid rgba(200, 249, 32, 0.5)',
                color: 'var(--p)',
                fontSize: '0.9rem',
                fontWeight: 700,
                marginBottom: '1rem',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: '0 0 20px rgba(200, 249, 32, 0.25)',
              }}
            >
              <CheckCircle2 size={18} />
              <span>طلب نشط وموثق بنجاح</span>
            </div>

            <h2 style={{ fontSize: 'clamp(1.5rem, 4vw, 2.2rem)', fontWeight: 900, marginBottom: '0.4rem' }}>
              مرحباً {portalData.customer?.display_name || 'بعميلنا العزيز'}
            </h2>
            <p style={{ color: 'var(--m)', fontSize: '1rem' }}>
              يمكنك استخراج رمز التحقق (Steam Guard) لحسابك مباشرة بنقرة واحدة
            </p>
          </div>

          {errorMsg && (
            <div className="alert-neon" role="alert">
              <AlertCircle size={18} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Assignments List */}
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            {portalData.assignments && portalData.assignments.length > 0 ? (
              portalData.assignments.map((item) => {
                const isVerifying = verifyingId === item.assignment_id;
                const hasCode = !!item.verification_code;

                return (
                  <div
                    key={item.assignment_id}
                    style={{
                      background: 'rgba(10, 12, 50, 0.65)',
                      border: '1.5px solid var(--line)',
                      borderRadius: 'var(--radius-lg)',
                      padding: '1.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '1.25rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                        <div
                          style={{
                            width: 46,
                            height: 46,
                            borderRadius: '14px',
                            background: 'rgba(200, 249, 32, 0.12)',
                            border: '1px solid rgba(200, 249, 32, 0.4)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'var(--p)',
                            boxShadow: '0 0 15px rgba(200, 249, 32, 0.2)',
                          }}
                        >
                          <Gamepad2 size={24} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '1.1rem' }}>
                            حساب Steam المخصص
                          </div>
                          <div style={{ fontSize: '0.9rem', color: 'var(--m)', fontFamily: 'var(--font-mono)' }}>
                            {item.account_identifier_masked}
                          </div>
                        </div>
                      </div>

                      <div>
                        {hasCode ? (
                          <span className="badge badge-success">
                            <Sparkles size={13} />
                            <span>الكود جاهز</span>
                          </span>
                        ) : isVerifying || item.current_status === 'processing' ? (
                          <span className="badge badge-warning">
                            <Clock size={13} className="animate-spin" />
                            <span>جاري الفحص...</span>
                          </span>
                        ) : item.current_status === 'waiting_mail' ? (
                          <span className="badge badge-info">
                            <Clock size={13} />
                            <span>بانتظار البريد</span>
                          </span>
                        ) : (
                          <span className="badge badge-neutral">متاح للطلب</span>
                        )}
                      </div>
                    </div>

                    {/* Verification Code Box Display */}
                    {hasCode ? (
                      <div
                        style={{
                          background: 'rgba(200, 249, 32, 0.08)',
                          border: '1.5px solid rgba(200, 249, 32, 0.4)',
                          borderRadius: 'var(--radius-lg)',
                          padding: '1.75rem 1.25rem',
                          textAlign: 'center',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          gap: '1rem',
                        }}
                      >
                        <span style={{ fontSize: '0.95rem', color: 'var(--m)', fontWeight: 700 }}>
                          رمز الدخول السريع (Steam Guard OTP)
                        </span>

                        <div className="steam-otp-box">
                          {item.verification_code}
                        </div>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center' }}>
                          <CopyButton
                            text={item.verification_code}
                            className="btn-alt"
                            label="نسخ الكود"
                          />
                          <button
                            type="button"
                            onClick={() => handleRequestCode(item.assignment_id)}
                            disabled={isVerifying}
                            className="btn-alt"
                          >
                            <RefreshCw size={15} className={isVerifying ? 'animate-spin' : ''} />
                            <span>طلب كود جديد</span>
                          </button>
                        </div>

                        <p style={{ fontSize: '0.825rem', color: 'var(--m)', marginTop: '0.25rem' }}>
                          ⚡ أدخل هذا الرمز في نافذة Steam لتسجيل الدخول فوراً
                        </p>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleRequestCode(item.assignment_id)}
                        disabled={isVerifying}
                        className="btn-neon"
                      >
                        <RefreshCw size={20} className={isVerifying ? 'animate-spin' : ''} />
                        <span>
                          {isVerifying ? 'جاري فحص صندوق البريد واستخراج الرمز...' : 'استخراج كود التحقق الآن'}
                        </span>
                      </button>
                    )}
                  </div>
                );
              })
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--m)' }}>
                لم يتم ربط حساب Steam بهذا الطلب بعد. يرجى التواصل مع الدعم.
              </div>
            )}
          </div>

          <div className="sep"></div>

          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={customerLogout}
              className="btn-alt"
              style={{ fontSize: '0.9rem', minHeight: 42 }}
            >
              تسجيل الخروج والعودة
            </button>
          </div>
        </section>
      </div>
    );
  }

  // 2. Public Landing View: Exact User-Provided Design
  return (
    <div className="wrap">
      {/* القسم الرئيسي (Hero Section) */}
      <section className="hero">
        <div className="logo-badge" aria-hidden="true">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>

        <h1 className="hero-title">
          خدمتك جاهزة<br />وتصلك في ثواني
        </h1>

        <p className="lead">
          اختر منصتك، أدخل رقم طلبك وحسابك، وافتح الخدمة بأمان وسهولة واستلم كود الدخول فوراً.
        </p>

        <div className="chips">
          <span className="chip">⚡ توصيل فوري</span>
          <span className="chip">🔒 آمن ومحمي</span>
          <span className="chip">🎮 جميع المنصات</span>
        </div>

        <ol className="steps">
          <li>
            <b>1</b>
            <span>اختر المنصة التي تلعب عليها</span>
          </li>
          <li>
            <b>2</b>
            <span>أدخل رقم الطلب وحسابك أو رمز التفعيل</span>
          </li>
          <li>
            <b>3</b>
            <span>افتح الخدمة واستلم كود التحقق مباشرة</span>
          </li>
        </ol>
      </section>

      {/* بطاقة النموذج (Card with Spinning Border) */}
      <section className="card-neon">
        <h2>افتح خدمتك الآن</h2>

        {errorMsg && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Mode Switch Pills */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '22px' }}>
          <button
            type="button"
            onClick={() => { setAccessMode('credentials'); setErrorMsg(null); }}
            className={`btn-alt ${accessMode === 'credentials' ? 'active' : ''}`}
            style={{
              flex: 1,
              minHeight: 44,
              fontSize: '0.88rem',
              background: accessMode === 'credentials' ? 'rgba(200, 249, 32, 0.18)' : 'rgba(10, 12, 50, 0.45)',
              borderColor: accessMode === 'credentials' ? 'var(--p)' : 'var(--line)',
              color: accessMode === 'credentials' ? 'var(--p)' : 'var(--m)',
            }}
          >
            <span>{t('direct_access')}</span>
          </button>

          <button
            type="button"
            onClick={() => { setAccessMode('token'); setErrorMsg(null); }}
            className={`btn-alt ${accessMode === 'token' ? 'active' : ''}`}
            style={{
              flex: 1,
              minHeight: 44,
              fontSize: '0.88rem',
              background: accessMode === 'token' ? 'rgba(200, 249, 32, 0.18)' : 'rgba(10, 12, 50, 0.45)',
              borderColor: accessMode === 'token' ? 'var(--p)' : 'var(--line)',
              color: accessMode === 'token' ? 'var(--p)' : 'var(--m)',
            }}
          >
            <span>{t('token_access')}</span>
          </button>
        </div>

        {accessMode === 'credentials' ? (
          /* Form 1: Order Reference & Steam Account */
          <form onSubmit={handleAccessSubmit} id="accessForm">
            {/* اختيار المنصة */}
            <div className="field">
              <span className="lbl" id="platLbl">اختر منصتك</span>
              <div className="plats" role="radiogroup" aria-labelledby="platLbl">
                <label className="plat">
                  <input
                    type="radio"
                    name="platform_code"
                    value="steam"
                    checked={platform === 'steam'}
                    onChange={(e) => setPlatform(e.target.value)}
                    required
                  />
                  <span>Steam PC</span>
                </label>

                <label className="plat">
                  <input
                    type="radio"
                    name="platform_code"
                    value="ubisoft"
                    checked={platform === 'ubisoft'}
                    onChange={(e) => setPlatform(e.target.value)}
                  />
                  <span>Ubisoft</span>
                </label>

                <label className="plat">
                  <input
                    type="radio"
                    name="platform_code"
                    value="rockstar"
                    checked={platform === 'rockstar'}
                    onChange={(e) => setPlatform(e.target.value)}
                  />
                  <span>Rockstar Games</span>
                </label>
              </div>
            </div>

            {/* رقم الطلب */}
            <div className="field">
              <label className="lbl" htmlFor="order_reference">
                رقم الطلب الخاص بك
              </label>
              <input
                className="in"
                id="order_reference"
                name="order_reference"
                autoComplete="off"
                required
                maxLength={120}
                placeholder="أدخل رقم طلبك (مثال: ORD-10023 أو 1234)"
                value={orderRef}
                onChange={(e) => setOrderRef(e.target.value)}
              />
            </div>

            {/* الحساب على المنصة */}
            <div className="field">
              <label className="lbl" htmlFor="account_alias">
                حسابك على المنصة
              </label>
              <input
                className="in"
                id="account_alias"
                name="account_alias"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck="false"
                required
                maxLength={255}
                placeholder="اسم الحساب أو المعرّف في Steam"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>

            {/* زر فتح الخدمة النيون */}
            <button type="submit" className="btn-neon" id="submitBtn" disabled={loading}>
              <span>{loading ? 'جاري فتح الخدمة...' : 'فتح الخدمة'}</span>
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.2" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d={lang === 'ar' ? 'M11 17l-5-5m0 0l5-5m-5 5h12' : 'M13 7l5 5m0 0l-5 5m5-5H6'} />
              </svg>
            </button>
          </form>
        ) : (
          /* Form 2: Activation Token */
          <form onSubmit={handleActivationSubmit} id="tokenForm">
            <div className="field">
              <label className="lbl" htmlFor="activation_token">
                {t('activation_token')}
              </label>
              <input
                className="in"
                id="activation_token"
                name="activation_token"
                autoComplete="off"
                required
                maxLength={255}
                placeholder="أدخل رمز أو رابط التفعيل الموحد"
                value={activationToken}
                onChange={(e) => setActivationToken(e.target.value)}
              />
            </div>

            <button type="submit" className="btn-neon" disabled={loading}>
              <span>{loading ? 'جاري تفعيل الطلب...' : t('activate_order')}</span>
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.2" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d={lang === 'ar' ? 'M11 17l-5-5m0 0l5-5m-5 5h12' : 'M13 7l5 5m0 0l-5 5m5-5H6'} />
              </svg>
            </button>
          </form>
        )}

        <div className="sep"></div>

        <p className="note">
          🔒 رقم الطلب مرجع محلي للاستخدام ولا نطلب كلمة مرور أو رمز دخول شخصي.
        </p>
      </section>
    </div>
  );
}
