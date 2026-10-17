import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import { Plus, AlertCircle, ShoppingBag, RefreshCw, User } from 'lucide-react';

export default function CustomersView() {
  const { t } = useLang();

  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const [displayName, setDisplayName] = useState('');
  const [telegramId, setTelegramId] = useState('');
  const [notes, setNotes] = useState('');

  const loadCustomers = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/customers');
      setCustomers(res.customers || []);
    } catch (err) {
      console.error('Failed to load customers', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, []);

  const handleCreateCustomer = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/customers', {
        display_name: displayName.trim(),
        telegram_user_id: telegramId ? parseInt(telegramId, 10) : null,
        notes: notes.trim() || null,
      });
      setIsAddOpen(false);
      setDisplayName('');
      setTelegramId('');
      setNotes('');
      await loadCustomers();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('customers')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            دليل العملاء المسجلين، معرفات Telegram، وإجمالي الطلبات المرتبطة
          </p>
        </div>

        <button
          onClick={() => { setErrorMsg(null); setIsAddOpen(true); }}
          className="btn-neon"
          style={{ width: 'auto', minHeight: 48, padding: '0 24px', fontSize: '1rem' }}
        >
          <Plus size={18} />
          <span>{t('add_customer')}</span>
        </button>
      </div>

      <div className="table-container">
        <table className="modern-table">
          <thead>
            <tr>
              <th>اسم العميل</th>
              <th>معرف Telegram</th>
              <th>عدد الطلبات</th>
              <th>{t('notes')}</th>
              <th>تاريخ الإضافة</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                    <RefreshCw size={18} className="animate-spin" color="var(--p)" />
                    <span>جاري تحميل العملاء...</span>
                  </div>
                </td>
              </tr>
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  لا يوجد عملاء مسجلين حاليًا
                </td>
              </tr>
            ) : (
              customers.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 800, color: 'var(--p)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <User size={15} color="var(--m)" />
                      <span>{c.display_name}</span>
                    </div>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--m)' }}>
                    {c.telegram_user_id || '—'}
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ gap: '0.4rem' }}>
                      <ShoppingBag size={13} />
                      <span>{c.orders_count} طلب</span>
                    </span>
                  </td>
                  <td style={{ color: 'var(--m)' }}>{c.notes || '—'}</td>
                  <td style={{ color: 'var(--m)', fontSize: '0.85rem' }}>
                    {c.created_at ? new Date(c.created_at).toLocaleDateString('ar-EG') : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Customer Modal */}
      <Modal isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} title="إضافة عميل جديد">
        {errorMsg && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateCustomer}>
          <div className="field">
            <label className="lbl" htmlFor="cust_name">اسم العميل</label>
            <input
              id="cust_name"
              type="text"
              className="in"
              placeholder="الاسم الكامل أو المعرّف"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="cust_telegram">معرف Telegram الرقمي (اختياري)</label>
            <input
              id="cust_telegram"
              type="number"
              className="in"
              placeholder="مثال: 987654321"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="cust_notes">{t('notes')}</label>
            <textarea
              id="cust_notes"
              className="in"
              rows={2}
              placeholder="ملاحظات حول العميل (اختياري)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsAddOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              {t('save')}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
