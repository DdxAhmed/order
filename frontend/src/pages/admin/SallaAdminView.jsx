import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import { Plus, ShieldCheck, AlertCircle, ExternalLink, RefreshCw } from 'lucide-react';
import Modal from '../../components/Modal';

export default function SallaAdminView() {
  const { t } = useLang();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAddMappingOpen, setIsAddMappingOpen] = useState(false);
  const [isPolicyOpen, setIsPolicyOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Mapping Form
  const [merchantId, setMerchantId] = useState('');
  const [productId, setProductId] = useState('');
  const [sku, setSku] = useState('');
  const [serviceKey, setServiceKey] = useState('');

  // Policy Form
  const [policyServiceKey, setPolicyServiceKey] = useState('');
  const [maxUses, setMaxUses] = useState(5);
  const [periodSeconds, setPeriodSeconds] = useState(86400);
  const [cooldownSeconds, setCooldownSeconds] = useState(30);

  const loadSallaData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/salla');
      setData(res);
      if (res.authorizations?.length && !merchantId) {
        setMerchantId(res.authorizations[0].merchant_id);
      }
      if (res.registered_services?.length) {
        setServiceKey(res.registered_services[0]);
        setPolicyServiceKey(res.registered_services[0]);
      }
    } catch (err) {
      console.error('Failed to load Salla settings', err);
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  useEffect(() => {
    loadSallaData();
  }, [loadSallaData]);

  const handleCreateMapping = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/salla/mappings', {
        merchant_id: parseInt(merchantId, 10),
        product_id: productId.trim() || null,
        sku: sku.trim() || null,
        service_key: serviceKey.trim(),
      });
      setIsAddMappingOpen(false);
      setProductId('');
      setSku('');
      setSuccessMsg('تم حفظ ربط المنتج بنجاح');
      await loadSallaData();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/salla/policies', {
        service_key: policyServiceKey.trim(),
        max_uses: parseInt(maxUses, 10),
        period_seconds: parseInt(periodSeconds, 10),
        cooldown_seconds: parseInt(cooldownSeconds, 10),
      });
      setIsPolicyOpen(false);
      setSuccessMsg('تم حفظ وتطبيق سياسة الاستخدام بنجاح');
      await loadSallaData();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('salla_settings')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            إدارة ربط منتجات متجر سلة مع الخدمات وسياسات معدل الاستخدام والتفويضات
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {data?.install_url && (
            <a
              href={data.install_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-alt"
              style={{ minHeight: 44, padding: '0 18px', gap: '0.45rem' }}
            >
              <ExternalLink size={15} />
              <span>تثبيت تطبيق سلة</span>
            </a>
          )}
          <button
            onClick={() => { setErrorMsg(null); setIsAddMappingOpen(true); }}
            className="btn-neon"
            style={{ width: 'auto', minHeight: 44, padding: '0 20px', fontSize: '0.95rem' }}
          >
            <Plus size={17} />
            <span>ربط منتج جديد</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="alert-neon" role="alert">
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert-neon alert-success" role="alert">
          <ShieldCheck size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Mappings Table */}
      <div className="card-neon" style={{ padding: '1.75rem' }}>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '1.25rem', color: '#fff' }}>
          ربط منتجات سلة (Product Mappings)
        </h3>

        <div className="table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>معرف التاجر (Merchant ID)</th>
                <th>معرف المنتج (Product ID)</th>
                <th>رمز التخزين (SKU)</th>
                <th>مفتاح الخدمة (Service Key)</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="4" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--m)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                      <RefreshCw size={18} className="animate-spin" color="var(--p)" />
                      <span>جاري تحميل بيانات سلة...</span>
                    </div>
                  </td>
                </tr>
              ) : !data?.mappings?.length ? (
                <tr>
                  <td colSpan="4" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--m)' }}>
                    لا توجد منتجات مربوطة حاليًا. اربط منتج سلة بخدمة Steam لبدء التسليم الآلي.
                  </td>
                </tr>
              ) : (
                data.mappings.map((m) => (
                  <tr key={m.id}>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{m.merchant_id}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{m.product_id || '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{m.sku || '—'}</td>
                    <td>
                      <span className="badge badge-success">{m.service_key}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Usage Policies Card */}
      <div className="card-neon" style={{ padding: '1.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff' }}>
              سياسات معدل الاستخدام (Usage Policies)
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--m)' }}>
              حماية الخدمات من الضغط وتحديد الحد الأقصى لطلبات الرموز خلال اليوم
            </p>
          </div>

          <button
            onClick={() => { setErrorMsg(null); setIsPolicyOpen(true); }}
            className="btn-alt"
            style={{ minHeight: 40, padding: '0 16px', fontSize: '0.85rem' }}
          >
            تعديل أو إضافة سياسة
          </button>
        </div>

        <div className="table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>مفتاح الخدمة</th>
                <th>أقصى استخدام (Max Uses)</th>
                <th>فترة الصلاحية (ثانية)</th>
                <th>فترة الانتظار (Cooldown)</th>
              </tr>
            </thead>
            <tbody>
              {!data?.policies?.length ? (
                <tr>
                  <td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: 'var(--m)' }}>
                    لا توجد سياسات مخصصة، يتم تطبيق الإعدادات الافتراضية
                  </td>
                </tr>
              ) : (
                data.policies.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 800, color: 'var(--p)' }}>{p.service_key}</td>
                    <td>{p.max_uses} مرات</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{p.period_seconds} ثانية (24 ساعة)</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{p.cooldown_seconds} ثانية</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Mapping Modal */}
      <Modal isOpen={isAddMappingOpen} onClose={() => setIsAddMappingOpen(false)} title="ربط منتج سلة بخدمة">
        <form onSubmit={handleCreateMapping}>
          <div className="field">
            <label className="lbl">متجر سلة (التاجر)</label>
            <select
              className="in"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              required
            >
              {data?.authorizations?.map((a) => (
                <option key={a.merchant_id} value={a.merchant_id}>
                  تاجر #{a.merchant_id} ({a.app_id || 'سلة'})
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl">معرف المنتج في سلة (Product ID)</label>
            <input
              type="text"
              className="in"
              placeholder="مثال: 12345678"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="lbl">رمز التخزين (SKU)</label>
            <input
              type="text"
              className="in"
              placeholder="مثال: STEAM-CODE-01"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="lbl">مفتاح الخدمة المسجلة (Service Key)</label>
            <select
              className="in"
              value={serviceKey}
              onChange={(e) => setServiceKey(e.target.value)}
              required
            >
              {data?.registered_services?.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsAddMappingOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              حفظ الربط
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Policy Modal */}
      <Modal isOpen={isPolicyOpen} onClose={() => setIsPolicyOpen(false)} title="تعديل سياسة الاستخدام">
        <form onSubmit={handleSavePolicy}>
          <div className="field">
            <label className="lbl">الخدمة</label>
            <select
              className="in"
              value={policyServiceKey}
              onChange={(e) => setPolicyServiceKey(e.target.value)}
              required
            >
              {data?.registered_services?.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl">الحد الأقصى لمرات الاستخدام (Max Uses)</label>
            <input
              type="number"
              className="in"
              min={1}
              max={100}
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl">فترة الصلاحية بالثواني (86400 = 24 ساعة)</label>
            <input
              type="number"
              className="in"
              value={periodSeconds}
              onChange={(e) => setPeriodSeconds(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl">فترة الانتظار بين الطلبات بالثواني (Cooldown)</label>
            <input
              type="number"
              className="in"
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsPolicyOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              حفظ السياسة
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
