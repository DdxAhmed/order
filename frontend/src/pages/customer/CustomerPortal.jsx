import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useLang } from '../../context/LangContext';
import CopyButton from '../../components/CopyButton';
import {
  Gamepad2,
  Key,
  ShieldCheck,
  RefreshCw,
  Clock,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Lock,
} from 'lucide-react';

export default function CustomerPortal() {
  const { customerSession, customerLogin, customerLogout } = useAuth();
  const { t } = useLang();

  // Access Form state
  const [orderRef, setOrderRef] = useState('');
  const [username, setUsername] = useState('');
  const [platform, setPlatform] = useState('steam');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Portal Data state
  const [portalData, setPortalData] = useState(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [verifyingId, setVerifyingId] = useState(null);
  const [pollInterval, setPollInterval] = useState(null);

  // Fetch portal details if session exists
  const fetchPortalData = async () => {
    try {
      const data = await api.get('/customer/portal');
      setPortalData(data);
      return data;
    } catch (err) {
      console.warn('Portal session expired:', err.message);
      customerLogout();
    }
  };

  useEffect(() => {
    if (customerSession) {
      fetchPortalData();
    }
  }, [customerSession]);

  // Handle Login
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
      setErrorMsg(err.message || 'بيانات الدخول غير صحيحة');
    } finally {
      setLoading(false);
    }
  };

  // Trigger Code Verification
  const handleRequestCode = async (assignmentId) => {
    setVerifyingId(assignmentId);
    setErrorMsg(null);
    try {
      await api.post(`/customer/assignments/${assignmentId}/verify`, {});
      await fetchPortalData();

      // Start automatic polling every 4 seconds for 2 minutes
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
      }, 4000);
      setPollInterval(interval);
    } catch (err) {
      setErrorMsg(err.message || 'تعذر طلب الرمز حاليًا');
      setVerifyingId(null);
    }
  };

  // If customer is authenticated and portal data is available
  if (customerSession && portalData) {
    return (
      <div style={{ maxWidth: 760, margin: '2.5rem auto', padding: '0 1rem' }}>
        <div
          className="glass-panel"
          style={{
            padding: '2.25rem',
            textAlign: 'center',
            position: 'relative',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              padding: '0.45rem 1rem',
              borderRadius: 'var(--radius-full)',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: 'var(--success)',
              fontSize: '0.85rem',
              fontWeight: 600,
              marginBottom: '1rem',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <CheckCircle2 size={16} />
            <span>طلب نشط وموثق</span>
          </div>

          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, marginBottom: '0.4rem' }}>
            مرحباً {portalData.customer?.display_name || 'بعميلنا العزيز'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '2rem' }}>
            يمكنك استخراج رمز التحقق لحساب Steam الخاص بك مباشرة من هذه البوابة
          </p>

          {errorMsg && (
            <div className="alert alert-danger" style={{ textAlign: 'right' }}>
              <AlertCircle size={18} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Assignments list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {portalData.assignments?.map((item) => {
              const isVerifying = verifyingId === item.assignment_id;
              const hasCode = !!item.verification_code;

              return (
                <div
                  key={item.assignment_id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '1.5rem',
                    textAlign: 'right',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
                        <Gamepad2 size={22} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                          حساب Steam المخصص
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {item.account_identifier_masked}
                        </div>
                      </div>
                    </div>

                    <div>
                      {item.current_status === 'succeeded' ? (
                        <span className="badge badge-success">جاهز</span>
                      ) : item.current_status === 'processing' || isVerifying ? (
                        <span className="badge badge-warning">جاري الفحص</span>
                      ) : item.current_status === 'waiting_mail' ? (
                        <span className="badge badge-info">بانتظار البريد</span>
                      ) : (
                        <span className="badge badge-neutral">متاح للطلب</span>
                      )}
                    </div>
                  </div>

                  {/* Verification Code Display */}
                  {hasCode ? (
                    <div
                      style={{
                        background: 'rgba(6, 182, 212, 0.08)',
                        border: '1px solid rgba(6, 182, 212, 0.3)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1.25rem',
                        textAlign: 'center',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.75rem',
                      }}
                    >
                      <div style={{ fontSize: '0.875rem', color: '#7dd3fc', fontWeight: 600 }}>
                        رمز التحقق (Steam Guard Code)
                      </div>
                      <div className="steam-code-box">
                        {item.verification_code}
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                        <CopyButton text={item.verification_code} className="btn btn-primary btn-sm" />
                        <button
                          onClick={() => handleRequestCode(item.assignment_id)}
                          className="btn btn-secondary btn-sm"
                          disabled={isVerifying}
                        >
                          <RefreshCw size={14} className={isVerifying ? 'animate-spin' : ''} />
                          <span>طلب رمز جديد</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                      <button
                        onClick={() => handleRequestCode(item.assignment_id)}
                        disabled={isVerifying}
                        className="btn btn-primary"
                        style={{ width: '100%', padding: '0.85rem' }}
                      >
                        <RefreshCw size={16} className={isVerifying ? 'animate-spin' : ''} />
                        <span>
                          {isVerifying ? 'جاري فحص صندوق البريد واستخراج الرمز...' : 'استخراج رمز التحقق الآن'}
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center' }}>
            <button onClick={customerLogout} className="btn btn-ghost btn-sm">
              إغلاق الجلسة والعودة
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Public Entrance Login Form
  return (
    <div style={{ maxWidth: 520, margin: '3.5rem auto', padding: '0 1rem' }}>
      <div className="glass-panel" style={{ padding: '2.5rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            style={{
              width: 58,
              height: 58,
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, var(--accent-primary) 0%, #06b6d4 100%)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 25px var(--accent-glow)',
              marginBottom: '1rem',
            }}
          >
            <Key size={30} color="#ffffff" />
          </div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.4rem' }}>
            بوابة استلام أكواد Steam
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            أدخل رقم طلبك واسم مستخدم الحساب للحصول على كود التحقق فوراً
          </p>
        </div>

        {errorMsg && (
          <div className="alert alert-danger">
            <AlertCircle size={18} />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleAccessSubmit}>
          <div className="form-group">
            <label className="form-label">{t('order_number')}</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: 12345 أو ORD-987"
              value={orderRef}
              onChange={(e) => setOrderRef(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">{t('steam_user')}</label>
            <input
              type="text"
              className="form-input"
              placeholder="اسم مستخدم Steam المسجل"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">{t('platform')}</label>
            <select
              className="form-select"
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              <option value="steam">Steam PC (ستيم)</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '0.9rem', marginTop: '1rem', fontSize: '1rem' }}
          >
            <ShieldCheck size={20} />
            <span>{loading ? 'جاري التحقق...' : t('open_portal')}</span>
          </button>
        </form>

        <div
          style={{
            marginTop: '1.75rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border-subtle)',
            textAlign: 'center',
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.4rem',
          }}
        >
          <Lock size={13} />
          <span>جلسة آمنة مشفرة بدون مشاركة أي بيانات حساسة</span>
        </div>
      </div>
    </div>
  );
}
