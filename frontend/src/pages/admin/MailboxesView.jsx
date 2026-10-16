import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import Modal from '../../components/Modal';
import {
  Mail,
  Plus,
  Radio,
  CheckCircle,
  XCircle,
  AlertCircle,
  Key,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';

export default function MailboxesView() {
  const { t } = useLang();

  const [mailboxes, setMailboxes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Add Form
  const [label, setLabel] = useState('');
  const [host, setHost] = useState('');
  const [port, setPort] = useState(993);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mailFolder, setMailFolder] = useState('INBOX');

  const loadMailboxes = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/mailboxes');
      setMailboxes(res.mailboxes || []);
    } catch (err) {
      console.error('Failed to load mailboxes', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMailboxes();
  }, []);

  const handleTestConnection = async (mailbox) => {
    setTestingId(mailbox.id);
    setTestResult(null);
    try {
      const res = await api.post(`/admin/mailboxes/${mailbox.id}/test`, {});
      setTestResult({ id: mailbox.id, success: res.connected, message: res.message });
      await loadMailboxes();
    } catch (err) {
      setTestResult({ id: mailbox.id, success: false, message: err.message });
    } finally {
      setTestingId(null);
    }
  };

  const handleToggleDisable = async (mailbox) => {
    try {
      await api.post(`/admin/mailboxes/${mailbox.id}/disable`, {});
      await loadMailboxes();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleCreateMailbox = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      await api.post('/admin/mailboxes', {
        label: label.trim(),
        host: host.trim(),
        port: parseInt(port, 10),
        username: username.trim(),
        password,
        mail_folder: mailFolder.trim() || 'INBOX',
      });
      setIsAddOpen(false);
      setLabel('');
      setHost('');
      setUsername('');
      setPassword('');
      await loadMailboxes();
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
            {t('mailboxes')}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            إدارة صناديق IMAP وتفويض Microsoft Graph لاستخراج أكواد Steam
          </p>
        </div>

        <button onClick={() => { setErrorMsg(null); setIsAddOpen(true); }} className="btn btn-primary">
          <Plus size={18} />
          <span>{t('add_mailbox')}</span>
        </button>
      </div>

      {/* Mailbox Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.25rem',
        }}
      >
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', gridColumn: '1 / -1' }}>
            جاري تحميل صناديق البريد...
          </div>
        ) : mailboxes.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', gridColumn: '1 / -1' }}>
            لا يوجد صناديق بريد مضافة بعد
          </div>
        ) : (
          mailboxes.map((m) => {
            const isTesting = testingId === m.id;
            const currentTest = testResult?.id === m.id ? testResult : null;

            return (
              <div key={m.id} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 'var(--radius-md)',
                        background: m.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: m.is_active ? 'var(--success)' : 'var(--danger)',
                      }}
                    >
                      <Mail size={22} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: '1.05rem', fontWeight: 700 }}>{m.label}</h4>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{m.username}</span>
                    </div>
                  </div>

                  <div>
                    {m.is_active ? (
                      <span className="badge badge-success">نشط</span>
                    ) : (
                      <span className="badge badge-danger">معطل</span>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    padding: '0.75rem',
                    background: 'rgba(0,0,0,0.25)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.35rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>البروتوكول:</span>
                    <span style={{ fontWeight: 600 }}>{m.auth_mode === 'microsoft_graph' ? 'Microsoft Graph (OAuth2)' : 'IMAP over TLS'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>المستضيف:</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{m.host}:{m.port}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>الحسابات المربوطة:</span>
                    <span className="badge badge-info" style={{ padding: '0.1rem 0.5rem' }}>{m.accounts_count} حساب</span>
                  </div>
                </div>

                {currentTest && (
                  <div
                    className={`alert ${currentTest.success ? 'alert-success' : 'alert-danger'}`}
                    style={{ padding: '0.65rem 0.85rem', fontSize: '0.825rem', marginBottom: 0 }}
                  >
                    {currentTest.success ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
                    <span>{currentTest.message}</span>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: 'auto', paddingTop: '0.5rem' }}>
                  <button
                    onClick={() => handleTestConnection(m)}
                    disabled={isTesting}
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                  >
                    <RefreshCw size={14} className={isTesting ? 'animate-spin' : ''} />
                    <span>{isTesting ? 'جاري الفحص...' : 'فحص الاتصال'}</span>
                  </button>

                  <button
                    onClick={() => handleToggleDisable(m)}
                    className={`btn btn-sm ${m.is_active ? 'btn-ghost' : 'btn-success'}`}
                  >
                    <span>{m.is_active ? 'تعطيل' : 'تفعيل'}</span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add Mailbox Modal */}
      <Modal isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} title="إضافة صندوق بريد IMAP">
        {errorMsg && (
          <div className="alert alert-danger">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateMailbox}>
          <div className="form-group">
            <label className="form-label">اسم تمييزي للصندوق</label>
            <input
              type="text"
              className="form-input"
              placeholder="مثال: Steam-Mailbox-01"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label">مستضيف IMAP</label>
              <input
                type="text"
                className="form-input"
                placeholder="imap.mail.me.com أو imap.gmail.com"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">المنفذ</label>
              <input
                type="number"
                className="form-input"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">عنوان البريد الإلكتروني</label>
            <input
              type="email"
              className="form-input"
              placeholder="steam-box@example.com"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">كلمة المرور أو App Password (تُحفظ مشفرة)</label>
            <input
              type="password"
              className="form-input"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">مجلد البريد</label>
            <input
              type="text"
              className="form-input"
              value={mailFolder}
              onChange={(e) => setMailFolder(e.target.value)}
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
