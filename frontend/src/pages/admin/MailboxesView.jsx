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
  RefreshCw,
  Power,
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
            {t('mailboxes')}
          </h2>
          <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
            إدارة صناديق IMAP وتفويضات Microsoft Graph المخصصة لاستقبال أكواد Steam
          </p>
        </div>

        <button
          onClick={() => { setErrorMsg(null); setIsAddOpen(true); }}
          className="btn-neon"
          style={{ width: 'auto', minHeight: 48, padding: '0 24px', fontSize: '1rem' }}
        >
          <Plus size={18} />
          <span>{t('add_mailbox')}</span>
        </button>
      </div>

      {/* Mailbox Cards Grid */}
      <div className="responsive-split-grid">
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--m)', gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
              <RefreshCw size={18} className="animate-spin" color="var(--p)" />
              <span>جاري تحميل صناديق البريد...</span>
            </div>
          </div>
        ) : mailboxes.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--m)', gridColumn: '1 / -1' }}>
            لا توجد صناديق بريد مضافة بعد. أضف صندوق IMAP للبدء في استلام أكواد Steam تلقائيًا.
          </div>
        ) : (
          mailboxes.map((m) => {
            const isTesting = testingId === m.id;
            const currentTest = testResult?.id === m.id ? testResult : null;

            return (
              <div
                key={m.id}
                className="card-neon"
                style={{
                  padding: '1.75rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: '16px',
                        background: 'rgba(200, 249, 32, 0.12)',
                        border: '1px solid rgba(200, 249, 32, 0.4)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--p)',
                        boxShadow: '0 0 20px rgba(200, 249, 32, 0.2)',
                      }}
                    >
                      <Mail size={24} />
                    </div>
                    <div>
                      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>{m.label}</h3>
                      <span style={{ fontSize: '0.825rem', color: 'var(--m)' }}>
                        {m.auth_mode === 'oauth_microsoft' ? 'Microsoft OAuth2 (Graph)' : 'Standard IMAP / SSL'}
                      </span>
                    </div>
                  </div>

                  <div>
                    {m.is_active ? (
                      <span className="badge badge-success">
                        <Radio size={12} className="animate-spin" />
                        <span>نشط ومفعّل</span>
                      </span>
                    ) : (
                      <span className="badge badge-danger">معطل</span>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    padding: '1rem',
                    borderRadius: '12px',
                    background: 'rgba(10, 12, 50, 0.5)',
                    border: '1px solid var(--line)',
                    display: 'grid',
                    gap: '0.5rem',
                    fontSize: '0.875rem',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--m)' }}>الخادم:</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{m.host}:{m.port}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--m)' }}>اسم المستخدم:</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{m.username}</span>
                  </div>
                </div>

                {/* Connection Test Result Feedback */}
                {currentTest && (
                  <div
                    className={`alert-neon ${currentTest.success ? 'alert-success' : ''}`}
                    style={{ margin: 0, padding: '10px 14px', fontSize: '0.85rem' }}
                  >
                    {currentTest.success ? <CheckCircle size={15} /> : <XCircle size={15} />}
                    <span>{currentTest.message}</span>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.65rem', marginTop: 'auto' }}>
                  <button
                    type="button"
                    onClick={() => handleTestConnection(m)}
                    disabled={isTesting}
                    className="btn-alt"
                    style={{ flex: 1, minHeight: 42, fontSize: '0.85rem', gap: '0.45rem' }}
                  >
                    <RefreshCw size={14} className={isTesting ? 'animate-spin' : ''} />
                    <span>{isTesting ? t('testing') : t('test_connection')}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleToggleDisable(m)}
                    className="btn-alt"
                    style={{
                      minHeight: 42,
                      padding: '0 14px',
                      color: m.is_active ? '#ff8787' : 'var(--p)',
                      borderColor: m.is_active ? 'rgba(255,107,107,0.4)' : 'var(--p)',
                    }}
                    title={m.is_active ? 'تعطيل هذا الصندوق' : 'تفعيل الصندوق'}
                  >
                    <Power size={15} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add Mailbox Modal */}
      <Modal isOpen={isAddOpen} onClose={() => setIsAddOpen(false)} title="إضافة صندوق بريد IMAP جديد">
        {errorMsg && (
          <div className="alert-neon" role="alert">
            <AlertCircle size={16} />
            <span>{errorMsg}</span>
          </div>
        )}
        <form onSubmit={handleCreateMailbox}>
          <div className="field">
            <label className="lbl" htmlFor="mb_label">اسم أو تسمية الصندوق (Label)</label>
            <input
              id="mb_label"
              type="text"
              className="in"
              placeholder="مثال: primary-imap أو steam-mailbox"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
            <div className="field">
              <label className="lbl" htmlFor="mb_host">خادم IMAP (Host)</label>
              <input
                id="mb_host"
                type="text"
                className="in"
                placeholder="imap.example.com"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label className="lbl" htmlFor="mb_port">المنفذ (Port)</label>
              <input
                id="mb_port"
                type="number"
                className="in"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="field">
            <label className="lbl" htmlFor="mb_username">عنوان البريد / المستخدم</label>
            <input
              id="mb_username"
              type="email"
              className="in"
              placeholder="mailbox@ordertrofy.store"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="mb_pass">كلمة مرور التطبيق (App Password)</label>
            <input
              id="mb_pass"
              type="password"
              className="in"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label className="lbl" htmlFor="mb_folder">مجلد البريد (Folder)</label>
            <input
              id="mb_folder"
              type="text"
              className="in"
              value={mailFolder}
              onChange={(e) => setMailFolder(e.target.value)}
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
