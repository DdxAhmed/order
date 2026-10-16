import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import { Users, Plus, AlertCircle, ShoppingBag } from 'lucide-react';

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('customers')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            دليل العملاء المسجلين والطلبات المرتبطة بهم
          </p>
        </div>

        <button onClick={() => { setErrorMsg(null); setIsAddOpen(true); }} className="btn btn-primary">
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
                <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                  جاري تحميل العملاء...
                </td>
              </tr>
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  لا يوجد عملاء مسجلين حاليًا
                </td>
              </tr>
            ) : (
              customers.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 700 }}>{c.display_name}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                    {c.telegram_user_id || '—'}
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ gap: '0.35rem' }}>
                      <ShoppingBag size={13} />
                      <span>{c.orders_count} طلب</span>
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>{c.notes || '—'}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
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
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateCustomer}>
          <div className="form-group">
            <label className="form-label">اسم العميل أو الكنية</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: أحمد محمد أو متجر فلان"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">معرف Telegram الرقمي (اختياري)</label>
            <input
              type="number"
              className="form-input"
              placeholder="مثال: 987654321"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{t('notes')}</label>
            <textarea
              className="form-textarea"
              rows="2"
              placeholder="أي تفاصيل أو معلومات تواصل..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsAddOpen(false)} className="btn btn-secondary">
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
