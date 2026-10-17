import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import {
  Plus,
  Search,
  Edit2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Gamepad2,
  RefreshCw,
} from 'lucide-react';

export default function AccountsView() {
  const { t } = useLang();

  const [accounts, setAccounts] = useState([]);
  const [platforms, setPlatforms] = useState([]);
  const [mailboxes, setMailboxes] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');

  // Modals
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Add Form state
  const [addPlatformId, setAddPlatformId] = useState('');
  const [addMailboxId, setAddMailboxId] = useState('');
  const [addIdentifier, setAddIdentifier] = useState('');
  const [addPassword, setAddPassword] = useState('');
  const [addNotes, setAddNotes] = useState('');

  // Edit Form state
  const [editStatus, setEditStatus] = useState('');
  const [editMailboxId, setEditMailboxId] = useState('');
  const [editPlatformId, setEditPlatformId] = useState('');
  const [editIdentifier, setEditIdentifier] = useState('');
  const [editNotes, setEditNotes] = useState('');

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (search.trim()) query.append('q', search.trim());
      if (statusFilter) query.append('status', statusFilter);
      if (platformFilter) query.append('platform', platformFilter);

      const res = await api.get(`/admin/accounts?${query.toString()}`);
      setAccounts(res.accounts || []);
      setPlatforms(res.platforms || []);
      setMailboxes(res.mailboxes || []);
      setStatuses(res.statuses || []);

      if (res.platforms?.length && !addPlatformId) {
        setAddPlatformId(res.platforms[0].id);
      }
      if (res.mailboxes?.length && !addMailboxId) {
        setAddMailboxId(res.mailboxes[0].id);
      }
    } catch (err) {
      console.error('Failed to load accounts', err);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, platformFilter, addPlatformId, addMailboxId]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadAccounts();
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setActionError(null);
    try {
      await api.post('/admin/accounts', {
        platform_id: addPlatformId,
        mailbox_id: addMailboxId,
        identifier: addIdentifier.trim(),
        password: addPassword || null,
        notes: addNotes.trim() || null,
      });
      setIsAddOpen(false);
      setAddIdentifier('');
      setAddPassword('');
      setAddNotes('');
      await loadAccounts();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const openEditModal = (account) => {
    setSelectedAccount(account);
    setEditIdentifier(account.identifier);
    setEditStatus(account.status);
    setEditPlatformId(account.platform_id);
    setEditMailboxId(account.mailbox_id);
    setEditNotes(account.notes || '');
    setActionError(null);
    setIsEditOpen(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setActionError(null);
    try {
      await api.put(`/admin/accounts/${selectedAccount.id}`, {
        platform_id: editPlatformId,
        mailbox_id: editMailboxId,
        identifier: editIdentifier.trim(),
        status: editStatus,
        notes: editNotes.trim() || null,
      });
      setIsEditOpen(false);
      await loadAccounts();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleQuickStatusChange = async (account, newStatus) => {
    try {
      await api.post(`/admin/accounts/${account.id}/status`, { status: newStatus });
      await loadAccounts();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('accounts')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            مخزون الحسابات الجاهزة وتوزيعها على المنصات وصناديق البريد
          </p>
        </div>

        <button
          onClick={() => { setActionError(null); setIsAddOpen(true); }}
          className="btn-neon"
          style={{ width: 'auto', minHeight: 48, padding: '0 24px', fontSize: '1rem' }}
        >
          <Plus size={18} />
          <span>{t('add_account')}</span>
        </button>
      </div>

      {/* Filters Bar */}
      <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.85rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: '1 1 240px' }}>
          <Search size={18} style={{ position: 'absolute', insetInlineStart: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--m)' }} />
          <input
            type="text"
            className="in"
            style={{ paddingInlineStart: 42, minHeight: 48 }}
            placeholder="بحث بمعرف الحساب أو اسم المستخدم..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="in"
          style={{ width: 'auto', minWidth: 150, minHeight: 48 }}
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">جميع المنصات</option>
          {platforms.map((p) => (
            <option key={p.code} value={p.code}>{p.name}</option>
          ))}
        </select>

        <select
          className="in"
          style={{ width: 'auto', minWidth: 150, minHeight: 48 }}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">جميع الحالات</option>
          {statuses.map((st) => (
            <option key={st} value={st}>{t(`status_${st}`)}</option>
          ))}
        </select>

        <button type="submit" className="btn-alt" style={{ minHeight: 48, padding: '0 18px' }}>
          <span>{t('search')}</span>
        </button>
      </form>

      {/* Accounts Table */}
      <div className="table-container">
        <table className="modern-table">
          <thead>
            <tr>
              <th>{t('identifier')}</th>
              <th>{t('platform')}</th>
              <th>صندوق البريد</th>
              <th>{t('status')}</th>
              <th>{t('notes')}</th>
              <th>{t('actions')}</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                    <RefreshCw size={18} className="animate-spin" color="var(--p)" />
                    <span>جاري تحميل الحسابات...</span>
                  </div>
                </td>
              </tr>
            ) : accounts.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: 'var(--m)' }}>
                  لا توجد حسابات مسجلة مطابقة للبحث
                </td>
              </tr>
            ) : (
              accounts.map((acc) => (
                <tr key={acc.id}>
                  <td style={{ fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--p)' }}>
                    {acc.identifier}
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ gap: '0.35rem' }}>
                      <Gamepad2 size={13} />
                      <span>{acc.platform_name}</span>
                    </span>
                  </td>
                  <td style={{ color: 'var(--m)', fontSize: '0.875rem' }}>{acc.mailbox_label}</td>
                  <td>
                    {acc.status === 'available' ? (
                      <span className="badge badge-success">متاح</span>
                    ) : acc.status === 'assigned' ? (
                      <span className="badge badge-info">مخصص</span>
                    ) : acc.status === 'disabled' ? (
                      <span className="badge badge-danger">معطل</span>
                    ) : (
                      <span className="badge badge-neutral">{acc.status}</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--m)', fontSize: '0.85rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {acc.notes || '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.45rem' }}>
                      <button
                        onClick={() => openEditModal(acc)}
                        className="btn-alt"
                        style={{ minHeight: 34, padding: '0 10px', fontSize: '0.8rem', gap: '0.35rem' }}
                        title="تعديل الحساب"
                      >
                        <Edit2 size={13} />
                        <span>تعديل</span>
                      </button>

                      {acc.status === 'available' ? (
                        <button
                          onClick={() => handleQuickStatusChange(acc, 'disabled')}
                          className="btn-alt"
                          style={{ minHeight: 34, padding: '0 10px', fontSize: '0.8rem', color: '#ff8787', borderColor: 'rgba(255,107,107,0.4)' }}
                          title="تعطيل الحساب"
                        >
                          <XCircle size={13} />
                          <span>تعطيل</span>
                        </button>
                      ) : acc.status === 'disabled' ? (
                        <button
                          onClick={() => handleQuickStatusChange(acc, 'available')}
                          className="btn-alt"
                          style={{ minHeight: 34, padding: '0 10px', fontSize: '0.8rem', color: 'var(--p)' }}
                          title="إعادة تفعيل الحساب"
                        >
                          <CheckCircle size={13} />
                          <span>تفعيل</span>
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Account Modal */}
      <Modal isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} title="إضافة حساب مخزون جديد">
        {actionError && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{actionError}</span>
          </div>
        )}
        <form onSubmit={handleCreateAccount}>
          <div className="field">
            <label className="lbl" htmlFor="add_account_platform">{t('platform')}</label>
            <select
              id="add_account_platform"
              className="in"
              value={addPlatformId}
              onChange={(e) => setAddPlatformId(e.target.value)}
              required
            >
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="add_account_mailbox">صندوق البريد المرتبط</label>
            <select
              id="add_account_mailbox"
              className="in"
              value={addMailboxId}
              onChange={(e) => setAddMailboxId(e.target.value)}
              required
            >
              {mailboxes.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="add_account_id">{t('identifier')}</label>
            <input
              id="add_account_id"
              type="text"
              className="in"
              placeholder="اسم مستخدم الحساب في Steam"
              value={addIdentifier}
              onChange={(e) => setAddIdentifier(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="add_account_password">كلمة المرور (مشفرة بـ AES-128-CBC)</label>
            <input
              id="add_account_password"
              type="password"
              className="in"
              placeholder="اختياري - تُشفر تلقائيًا بمفتاح متناظر"
              value={addPassword}
              onChange={(e) => setAddPassword(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="add_account_notes">{t('notes')}</label>
            <textarea
              id="add_account_notes"
              className="in"
              rows={2}
              placeholder="ملاحظات داخلية للمشرفين (اختياري)"
              value={addNotes}
              onChange={(e) => setAddNotes(e.target.value)}
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

      {/* Edit Account Modal */}
      <Modal isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} title={`تعديل الحساب [${selectedAccount?.identifier}]`}>
        {actionError && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{actionError}</span>
          </div>
        )}
        <form onSubmit={handleEditSubmit}>
          <div className="field">
            <label className="lbl" htmlFor="edit_account_id">{t('identifier')}</label>
            <input
              id="edit_account_id"
              type="text"
              className="in"
              value={editIdentifier}
              onChange={(e) => setEditIdentifier(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="edit_account_status">{t('status')}</label>
            <select
              id="edit_account_status"
              className="in"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              required
            >
              {statuses.map((st) => (
                <option key={st} value={st}>{t(`status_${st}`)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="edit_account_platform">{t('platform')}</label>
            <select
              id="edit_account_platform"
              className="in"
              value={editPlatformId}
              onChange={(e) => setEditPlatformId(e.target.value)}
              required
            >
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="edit_account_mailbox">صندوق البريد</label>
            <select
              id="edit_account_mailbox"
              className="in"
              value={editMailboxId}
              onChange={(e) => setEditMailboxId(e.target.value)}
              required
            >
              {mailboxes.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="edit_account_notes">{t('notes')}</label>
            <textarea
              id="edit_account_notes"
              className="in"
              rows={2}
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
            <button type="button" onClick={() => setIsEditOpen(false)} className="btn-alt">
              {t('cancel')}
            </button>
            <button type="submit" className="btn-neon" style={{ width: 'auto', minHeight: 48, padding: '0 24px' }}>
              حفظ التعديلات
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
