import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import CopyButton from '../../components/CopyButton';
import {
  ShoppingBag,
  Plus,
  Link,
  UserCheck,
  CheckCircle,
  AlertCircle,
  Gamepad2,
  ExternalLink,
} from 'lucide-react';

export default function OrdersView() {
  const { t } = useLang();

  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [assignableAccounts, setAssignableAccounts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [isAddOrderOpen, setIsAddOrderOpen] = useState(false);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [isLinkOpen, setIsLinkOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [generatedLink, setGeneratedLink] = useState('');
  const [errorMsg, setErrorMsg] = useState(null);

  // Forms
  const [orderRef, setOrderRef] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [accountId, setAccountId] = useState('');
  const [reassignReason, setReassignReason] = useState('');

  const loadOrders = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/orders');
      setOrders(res.orders || []);
      setCustomers(res.customers || []);
      setAssignableAccounts(res.assignable_accounts || []);

      if (res.customers?.length && !customerId) {
        setCustomerId(res.customers[0].id);
      }
      if (res.assignable_accounts?.length && !accountId) {
        setAccountId(res.assignable_accounts[0].id);
      }
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, []);

  const handleCreateOrder = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/orders', {
        external_reference: orderRef.trim(),
        customer_id: customerId,
      });
      setIsAddOrderOpen(false);
      setOrderRef('');
      await loadOrders();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  const openAssignModal = (order) => {
    setSelectedOrder(order);
    setErrorMsg(null);
    setIsAssignOpen(true);
  };

  const handleAssignSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/assignments', {
        account_id: accountId,
        order_id: selectedOrder.id,
        reassign_reason: reassignReason.trim() || null,
      });
      setIsAssignOpen(false);
      setReassignReason('');
      await loadOrders();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  const handleGenerateLink = async (order) => {
    setErrorMsg(null);
    try {
      const res = await api.post(`/admin/orders/${order.id}/activation`, {});
      setGeneratedLink(res.link);
      setSelectedOrder(order);
      setIsLinkOpen(true);
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('orders')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            إدارة الطلبات وربطها بالعملاء وحسابات Steam
          </p>
        </div>

        <button onClick={() => { setErrorMsg(null); setIsAddOrderOpen(true); }} className="btn btn-primary">
          <Plus size={18} />
          <span>{t('add_order')}</span>
        </button>
      </div>

      {/* Orders Table */}
      <div className="table-container">
        <table className="modern-table">
          <thead>
            <tr>
              <th>{t('order_number')}</th>
              <th>العميل</th>
              <th>الحساب المخصص</th>
              <th>{t('status')}</th>
              <th>تاريخ الإنشاء</th>
              <th>{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>
                  جاري تحميل الطلبات...
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  لا توجد طلبات مسجلة بعد
                </td>
              </tr>
            ) : (
              orders.map((ord) => (
                <tr key={ord.id}>
                  <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                    {ord.external_reference}
                  </td>
                  <td>{ord.customer_name}</td>
                  <td>
                    {ord.assignment ? (
                      <span className="badge badge-info" style={{ gap: '0.35rem', fontFamily: 'var(--font-mono)' }}>
                        <Gamepad2 size={13} />
                        <span>{ord.assignment.account_identifier}</span>
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>لم يخصص حساب</span>
                    )}
                  </td>
                  <td>
                    {ord.status === 'activated' ? (
                      <span className="badge badge-success">مفعّل</span>
                    ) : ord.status === 'pending' ? (
                      <span className="badge badge-warning">معلق</span>
                    ) : (
                      <span className="badge badge-neutral">{ord.status}</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {ord.created_at ? new Date(ord.created_at).toLocaleDateString('ar-EG') : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        onClick={() => openAssignModal(ord)}
                        className="btn btn-secondary btn-sm"
                        title={ord.assignment ? 'إعادة تخصيص حساب' : 'تخصيص حساب'}
                      >
                        <UserCheck size={14} />
                        <span>{ord.assignment ? 'تغيير' : 'تخصيص'}</span>
                      </button>

                      <button
                        onClick={() => handleGenerateLink(ord)}
                        className="btn btn-ghost btn-sm"
                        title="رابط التفعيل الموحد"
                      >
                        <Link size={14} color="var(--accent-secondary)" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Order Modal */}
      <Modal isOpen={isAddOrderOpen} onClose={() => setIsAddOrderOpen(false)} title="إنشاء طلب جديد">
        {errorMsg && (
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateOrder}>
          <div className="form-group">
            <label className="form-label">{t('order_number')}</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: ORD-10023 أو 85472"
              value={orderRef}
              onChange={(e) => setOrderRef(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">العميل</label>
            <select
              className="form-select"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              required
            >
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsAddOrderOpen(false)} className="btn btn-secondary">
              {t('cancel')}
            </button>
            <button type="submit" className="btn btn-primary">
              {t('save')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Assign Account Modal */}
      <Modal isOpen={isAssignOpen} onClose={() => setIsAssignOpen(false)} title={`تخصيص حساب للطلب [${selectedOrder?.external_reference}]`}>
        {errorMsg && (
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleAssignSubmit}>
          <div className="form-group">
            <label className="form-label">اختر حساب المخزون</label>
            <select
              className="form-select"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              required
            >
              {assignableAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.identifier} ({t(`status_${a.status}`)})
                </option>
              ))}
            </select>
          </div>

          {selectedOrder?.assignment && (
            <div className="form-group">
              <label className="form-label">سبب إعادة التخصيص</label>
              <input
                type="text"
                className="form-input"
                placeholder="مثال: مشكلة في الحساب السابق أو طلب العميل"
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
              />
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsAssignOpen(false)} className="btn btn-secondary">
              {t('cancel')}
            </button>
            <button type="submit" className="btn btn-primary">
              تأكيد التخصيص
            </button>
          </div>
        </form>
      </Modal>

      {/* Link Modal */}
      <Modal isOpen={isLinkOpen} onClose={() => setIsLinkOpen(false)} title="رابط العميل الموحد">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            يمكن للعميل فتح الرابط الموحد وإدخال رقم الطلب واسم المستخدم لاستلام الكود مباشرة
          </p>

          <div
            style={{
              padding: '1rem',
              background: 'rgba(0,0,0,0.4)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.95rem',
              wordBreak: 'break-all',
              color: '#38bdf8',
            }}
          >
            {generatedLink}
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem' }}>
            <CopyButton text={generatedLink} className="btn btn-primary" />
            <button type="button" onClick={() => setIsLinkOpen(false)} className="btn btn-secondary">
              إغلاق
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
