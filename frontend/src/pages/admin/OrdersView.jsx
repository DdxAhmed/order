import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import CopyButton from '../../components/CopyButton';
import {
  Plus,
  Link,
  UserCheck,
  AlertCircle,
  Gamepad2,
  RefreshCw,
  Search,
} from 'lucide-react';

export default function OrdersView() {
  const { t } = useLang();

  const [orders, setOrders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [assignableAccounts, setAssignableAccounts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

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

  const loadOrders = useCallback(async () => {
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
  }, [customerId, accountId]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

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

  // Filtered orders
  const filteredOrders = orders.filter((ord) => {
    const matchesSearch =
      ord.external_reference?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ord.customer_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || ord.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('orders')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            إدارة طلبات العملاء وتخصيص حسابات Steam واستخراج روابط التفعيل
          </p>
        </div>

        <button
          onClick={() => { setErrorMsg(null); setIsAddOrderOpen(true); }}
          className="btn-neon"
          style={{ width: 'auto', minHeight: 48, padding: '0 24px', fontSize: '1rem' }}
        >
          <Plus size={18} />
          <span>{t('add_order')}</span>
        </button>
      </div>

      {/* Search & Filter Bar */}
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 260px' }}>
          <Search size={18} style={{ position: 'absolute', insetInlineStart: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--m)' }} />
          <input
            type="text"
            className="in"
            style={{ paddingInlineStart: 42, minHeight: 48 }}
            placeholder="بحث برقم الطلب أو اسم العميل..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {['all', 'activated', 'pending', 'revoked'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`btn-alt ${statusFilter === st ? 'active' : ''}`}
              style={{
                minHeight: 44,
                padding: '0 16px',
                fontSize: '0.85rem',
                background: statusFilter === st ? 'rgba(200, 249, 32, 0.2)' : 'rgba(30, 27, 67, 0.5)',
                borderColor: statusFilter === st ? 'var(--p)' : 'var(--line)',
                color: statusFilter === st ? 'var(--p)' : 'var(--m)',
              }}
            >
              {st === 'all' ? t('all') : st === 'activated' ? 'مفعّل' : st === 'pending' ? 'معلق' : 'ملغي'}
            </button>
          ))}
        </div>
      </div>

      {/* Orders Table Container */}
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
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                    <RefreshCw size={18} className="animate-spin" color="var(--p)" />
                    <span>جاري تحميل الطلبات...</span>
                  </div>
                </td>
              </tr>
            ) : filteredOrders.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  لا توجد طلبات مطابقة للمعايير المحددة
                </td>
              </tr>
            ) : (
              filteredOrders.map((ord) => (
                <tr key={ord.id}>
                  <td style={{ fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--p)' }}>
                    {ord.external_reference}
                  </td>
                  <td style={{ fontWeight: 600 }}>{ord.customer_name}</td>
                  <td>
                    {ord.assignment ? (
                      <span className="badge badge-info" style={{ gap: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                        <Gamepad2 size={13} />
                        <span>{ord.assignment.account_identifier}</span>
                      </span>
                    ) : (
                      <span style={{ color: 'var(--m)', fontSize: '0.85rem' }}>لم يُخصص حساب</span>
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
                  <td style={{ color: 'var(--m)', fontSize: '0.85rem' }}>
                    {ord.created_at ? new Date(ord.created_at).toLocaleDateString('ar-EG') : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => openAssignModal(ord)}
                        className="btn-alt"
                        style={{ minHeight: 36, padding: '0 12px', fontSize: '0.8rem', gap: '0.35rem' }}
                        title={ord.assignment ? 'تغيير الحساب المخصص' : 'تخصيص حساب'}
                      >
                        <UserCheck size={14} />
                        <span>{ord.assignment ? 'تغيير' : 'تخصيص'}</span>
                      </button>

                      <button
                        onClick={() => handleGenerateLink(ord)}
                        className="btn-alt"
                        style={{ minHeight: 36, padding: '0 12px', fontSize: '0.8rem', gap: '0.35rem' }}
                        title="رابط العميل الموحد"
                      >
                        <Link size={14} />
                        <span>الرابط</span>
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
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateOrder}>
          <div className="field">
            <label className="lbl" htmlFor="new_order_ref">{t('order_number')}</label>
            <input
              id="new_order_ref"
              type="text"
              className="in"
              placeholder="مثال: ORD-10023 أو 85472"
              value={orderRef}
              onChange={(e) => setOrderRef(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="new_order_customer">العميل</label>
            <select
              id="new_order_customer"
              className="in"
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

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsAddOrderOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              {t('save')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Assign Account Modal */}
      <Modal isOpen={isAssignOpen} onClose={() => setIsAssignOpen(false)} title={`تخصيص حساب للطلب [${selectedOrder?.external_reference}]`}>
        {errorMsg && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleAssignSubmit}>
          <div className="field">
            <label className="lbl" htmlFor="assign_account_select">اختر حساب المخزون</label>
            <select
              id="assign_account_select"
              className="in"
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
            <div className="field">
              <label className="lbl" htmlFor="reassign_reason">سبب إعادة التخصيص</label>
              <input
                id="reassign_reason"
                type="text"
                className="in"
                placeholder="مثال: مشكلة في الحساب السابق أو استبدال بطلب العميل"
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
              />
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsAssignOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              تأكيد التخصيص
            </button>
          </div>
        </form>
      </Modal>

      {/* Link Modal */}
      <Modal isOpen={isLinkOpen} onClose={() => setIsLinkOpen(false)} title="رابط العميل الموحد">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', textAlign: 'center' }}>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            يمكن للعميل فتح هذا الرابط وإدخال رقم الطلب واسم المستخدم لاستخراج رمز التحقق فوراً
          </p>

          <div
            style={{
              padding: '1.25rem',
              background: 'rgba(10, 12, 50, 0.7)',
              border: '1.5px solid var(--p)',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-mono)',
              fontSize: '1rem',
              wordBreak: 'break-all',
              color: 'var(--p)',
              boxShadow: '0 0 25px rgba(200, 249, 32, 0.15)',
            }}
          >
            {generatedLink}
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem' }}>
            <CopyButton text={generatedLink} className="btn-neon" label="نسخ الرابط" />
            <button type="button" onClick={() => setIsLinkOpen(false)} className="btn-alt">
              {t('close')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
