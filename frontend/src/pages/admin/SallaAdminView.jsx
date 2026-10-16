import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import { Store, Plus, ShieldCheck, AlertCircle, Save, ExternalLink } from 'lucide-react';

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

  const loadSallaData = async () => {
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
  };

  useEffect(() => {
    loadSallaData();
  }, []);

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
      setSuccessMsg('تم حفظ سياسة الاستخدام بنجاح');
      await loadSallaData();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('salla_settings')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            إدارة ربط منتجات متجر سلة مع الخدمات وسياسات معدل الاستخدام
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {data?.install_url && (
            <a
              href={data.install_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary"
            >
              <ExternalLink size={16} />
              <span>تثبيت تطبيق سلة</span>
            </a>
          )}
          <button onClick={() => { setErrorMsg(null); setIsAddMappingOpen(true); }} className="btn btn-primary">
            <Plus size={18} />
            <span>ربط منتج جديد</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="alert alert-danger">
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success">
          <ShieldCheck size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Mappings Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: '1rem' }}>
          ربط المنتجات (Product Mappings)
        </h3>

        <div className="table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>معرف التاجر</th>
                <th>معرف المنتج الرقمي</th>
                <th>رمز SKU</th>
                <th>مفتاح الخدمة المرتبطة</th>
                <th>تاريخ الإنشاء</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem' }}>جاري التحميل...</td>
                </tr>
              ) : data?.mappings?.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                    لم يتم تسجيل أي ربط لمنتجات سلة بعد
                  </td>
                </tr>
              ) : (
                data?.mappings?.map((m) => (
                  <tr key={m.id}>
                    <td>{m.merchant_id}</td>
                    <td>{m.product_id || '—'}</td>
                    <td>{m.sku || '—'}</td>
                    <td>
                      <span className="badge badge-info">{m.service_key}</span>
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      {m.created_at ? new Date(m.created_at).toLocaleDateString('ar-EG') : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Usage Policies Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
            سياسات الاستخدام ومعدل الطلبات (Usage Policies)
          </h3>
          <button onClick={() => { setErrorMsg(null); setIsPolicyOpen(true); }} className="btn btn-secondary btn-sm">
            <Plus size={15} />
            <span>ضبط سياسة</span>
          </button>
        </div>

        <div className="table-container">
          <table className="modern-table">
            <thead>
              <tr>
                <th>مفتاح الخدمة</th>
                <th>الحد الأقصى للاستخدامات</th>
                <th>المدة (بالثواني)</th>
                <th>فترة الانتظار (Cooldown)</th>
                <th>الحالة</th>
              </tr>
            </thead>
            <tbody>
              {data?.policies?.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600 }}>{p.service_key}</td>
                  <td>{p.max_uses} مرات</td>
                  <td>{p.period_seconds} ثانية ({(p.period_seconds / 3600).toFixed(0)} ساعة)</td>
                  <td>{p.cooldown_seconds} ثانية</td>
                  <td>
                    {p.is_active ? (
                      <span className="badge badge-success">مفعلة</span>
                    ) : (
                      <span className="badge badge-neutral">معطلة</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Mapping Modal */}
      <Modal isOpen={isAddMappingOpen} onClose={() => setIsAddMappingOpen(false)} title="ربط منتج سلة بخدمة">
        <form onSubmit={handleCreateMapping}>
          <div className="form-group">
            <label className="form-label">معرف التاجر في سلة (Merchant ID)</label>
            <input
              type="number"
              className="form-input"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">معرف المنتج الرقمي (اختياري إذا تم ملء SKU)</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: 12345678"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">رمز SKU (اختياري إذا تم ملء المعرف)</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: STEAM-CODE-01"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">مفتاح الخدمة المسموحة (Service Key)</label>
            <input
              type="text"
              className="form-input"
              value={serviceKey}
              onChange={(e) => setServiceKey(e.target.value)}
              placeholder="مثال: steam_code_delivery"
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsAddMappingOpen(false)} className="btn btn-secondary">
              {t('cancel')}
            </button>
            <button type="submit" className="btn btn-primary">
              {t('save')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Set Policy Modal */}
      <Modal isOpen={isPolicyOpen} onClose={() => setIsPolicyOpen(false)} title="ضبط سياسة الاستخدام">
        <form onSubmit={handleSavePolicy}>
          <div className="form-group">
            <label className="form-label">مفتاح الخدمة (Service Key)</label>
            <input
              type="text"
              className="form-input"
              value={policyServiceKey}
              onChange={(e) => setPolicyServiceKey(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">الحد الأقصى لعدد الاستخدامات</label>
            <input
              type="number"
              className="form-input"
              min="1"
              max="100"
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">مدة النافذة الزمنية (بالثواني)</label>
            <input
              type="number"
              className="form-input"
              value={periodSeconds}
              onChange={(e) => setPeriodSeconds(e.target.value)}
              required
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>86400 ثانية = 24 ساعة</span>
          </div>

          <div className="form-group">
            <label className="form-label">مهلة الانتظار بين كل استخدام (Cooldown بالثواني)</label>
            <input
              type="number"
              className="form-input"
              value={cooldownSeconds}
              onChange={(e) => setCooldownSeconds(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsPolicyOpen(false)} className="btn btn-secondary">
              {t('cancel')}
            </button>
            <button type="submit" className="btn btn-primary">
              {t('save')}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
