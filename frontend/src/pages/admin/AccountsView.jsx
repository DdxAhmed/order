import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import {
  KeyRound,
  Plus,
  Search,
  Filter,
  Edit2,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Gamepad2,
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

  const loadAccounts = async () => {
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
  };

  useEffect(() => {
    loadAccounts();
  }, [statusFilter, platformFilter]);

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('accounts')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            إدارة حسابات المخزون وصناديق البريد المرتبطة بها
          </p>
        </div>

        <button onClick={() => { setActionError(null); setIsAddOpen(true); }} className="btn btn-primary">
          <Plus size={18} />
          <span>{t('add_account')}</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="glass-panel" style={{ padding: '1rem 1.25rem' }}>
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.85rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: '1 1 240px', position: 'relative' }}>
            <input
              type="text"
              className="form-input"
              placeholder={t('search')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: '2.5rem' }}
            />
            <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} />
          </div>

          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: 'auto', minWidth: 150 }}
          >
            <option value="">جميع الحالات</option>
            {statuses.map((st) => (
              <option key={st} value={st}>
                {t(`status_${st}`)}
              </option>
            ))}
          </select>

          <select
            className="form-select"
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            style={{ width: 'auto', minWidth: 150 }}
          >
            <option value="">جميع المنصات</option>
            {platforms.map((p) => (
              <option key={p.code} value={p.code}>
                {p.name}
              </option>
            ))}
          </select>

          <button type="submit" className="btn btn-secondary">
            <span>تصفية</span>
          </button>
        </form>
      </div>

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
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>
                  جاري تحميل الحسابات...
                </td>
              </tr>
            ) : accounts.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  لا توجد حسابات مطابقة لمعايير البحث
                </td>
              </tr>
            ) : (
              accounts.map((acc) => (
                <tr key={acc.id}>
                  <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                    {acc.identifier}
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ gap: '0.35rem' }}>
                      <Gamepad2 size={13} />
                      <span>{acc.platform_name || acc.platform_code}</span>
                    </span>
                  </td>
                  <td>{acc.mailbox_label || '—'}</td>
                  <td>
                    {acc.status === 'available' ? (
                      <span className="badge badge-success">{t('status_available')}</span>
                    ) : acc.status === 'assigned' ? (
                      <span className="badge badge-info">{t('status_assigned')}</span>
                    ) : acc.status === 'disabled' ? (
                      <span className="badge badge-danger">{t('status_disabled')}</span>
                    ) : (
                      <span className="badge badge-warning">{acc.status}</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {acc.notes || '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        onClick={() => openEditModal(acc)}
                        className="btn btn-secondary btn-sm"
                        title="تعديل"
                      >
                        <Edit2 size={13} />
                      </button>
                      {acc.status === 'available' ? (
                        <button
                          onClick={() => handleQuickStatusChange(acc, 'disabled')}
                          className="btn btn-ghost btn-sm"
                          title="تعطيل"
                        >
                          <XCircle size={14} color="var(--danger)" />
                        </button>
                      ) : acc.status === 'disabled' ? (
                        <button
                          onClick={() => handleQuickStatusChange(acc, 'available')}
                          className="btn btn-ghost btn-sm"
                          title="تفعيل"
                        >
                          <CheckCircle size={14} color="var(--success)" />
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
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{actionError}</span>
          </div>
        )}
        <form onSubmit={handleCreateAccount}>
          <div className="form-group">
            <label className="form-label">{t('platform')}</label>
            <select
              className="form-select"
              value={addPlatformId}
              onChange={(e) => setAddPlatformId(e.target.value)}
              required
            >
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">صندوق البريد المربوط</label>
            <select
              className="form-select"
              value={addMailboxId}
              onChange={(e) => setAddMailboxId(e.target.value)}
              required
            >
              {mailboxes.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} ({m.auth_mode})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">{t('identifier')}</label>
            <input
              type="text"
              className="form-input"
              placeholder="اسم مستخدم الحساب في المنصة"
              value={addIdentifier}
              onChange={(e) => setAddIdentifier(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">كلمة مرور الحساب (اختياري - تُحفظ مشفرة)</label>
            <input
              type="password"
              className="form-input"
              placeholder="••••••••••••"
              value={addPassword}
              onChange={(e) => setAddPassword(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">{t('notes')}</label>
            <textarea
              className="form-textarea"
              rows="2"
              placeholder="أي ملاحظات داخلية عن الحساب..."
              value={addNotes}
              onChange={(e) => setAddNotes(e.target.value)}
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

      {/* Edit Account Modal */}
      <Modal isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} title="تعديل حساب المخزون">
        {actionError && (
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{actionError}</span>
          </div>
        )}
        <form onSubmit={handleEditSubmit}>
          <div className="form-group">
            <label className="form-label">{t('identifier')}</label>
            <input
              type="text"
              className="form-input"
              value={editIdentifier}
              onChange={(e) => setEditIdentifier(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">صندوق البريد</label>
            <select
              className="form-select"
              value={editMailboxId}
              onChange={(e) => setEditMailboxId(e.target.value)}
              required
            >
              {mailboxes.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">{t('status')}</label>
            <select
              className="form-select"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              disabled={selectedAccount?.status === 'assigned'}
            >
              <option value="available">{t('status_available')}</option>
              <option value="disabled">{t('status_disabled')}</option>
              <option value="reserved">{t('status_reserved')}</option>
              <option value="archived">{t('status_archived')}</option>
              {selectedAccount?.status === 'assigned' && (
                <option value="assigned">{t('status_assigned')}</option>
              )}
            </select>
            {selectedAccount?.status === 'assigned' && (
              <span style={{ fontSize: '0.75rem', color: 'var(--warning)', marginTop: '0.2rem' }}>
                لا يمكن تغيير حالة حساب مخصص مباشرة؛ استخدم إعادة التخصيص من صفحة الطلبات.
              </span>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">{t('notes')}</label>
            <textarea
              className="form-textarea"
              rows="2"
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setIsEditOpen(false)} className="btn btn-secondary">
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
