import React, { useState } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Check,
} from 'lucide-react';

export default function ImportView() {
  const { t } = useLang();

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setPreviewData(null);
      setErrorMsg(null);
      setSuccessMsg(null);
    }
  };

  const handleUploadPreview = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('csv_file', file);

    try {
      const res = await api.post('/admin/import/preview', formData);
      setPreviewData(res);
    } catch (err) {
      setErrorMsg(err.message || 'فشل فحص ملف CSV');
    } finally {
      setUploading(false);
    }
  };

  const handleCommit = async () => {
    if (!previewData?.batch_id) return;

    setCommitting(true);
    setErrorMsg(null);
    try {
      const res = await api.post(`/admin/import/${previewData.batch_id}/commit`, {});
      setSuccessMsg(res.message || 'تم استيراد الحسابات بنجاح وإضافتها للمخزون');
      setPreviewData(null);
      setFile(null);
    } catch (err) {
      setErrorMsg(err.message || 'تعذر استيراد الدفعة');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.85rem', fontWeight: 900, marginBottom: '0.35rem', color: '#fff' }}>
          {t('import')}
        </h2>
        <p style={{ color: 'var(--m)', fontSize: '0.95rem' }}>
          استيراد حسابات المخزون دفعة واحدة من ملف CSV مع التحقق المسبق والمعاينة
        </p>
      </div>

      {errorMsg && (
        <div className="alert-neon" role="alert">
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert-neon alert-success" role="alert">
          <CheckCircle2 size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Upload Zone */}
      <div className="card-neon" style={{ padding: '2rem' }}>
        <form onSubmit={handleUploadPreview} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div
            style={{
              border: '2px dashed var(--line)',
              borderRadius: 'var(--radius-lg)',
              padding: '2.5rem 1.5rem',
              textAlign: 'center',
              background: 'rgba(10, 12, 50, 0.4)',
              cursor: 'pointer',
              position: 'relative',
              transition: 'border-color 0.2s',
            }}
          >
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={handleFileChange}
              style={{
                position: 'absolute',
                inset: 0,
                opacity: 0,
                cursor: 'pointer',
                width: '100%',
                height: '100%',
              }}
            />
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: '18px',
                background: 'rgba(200, 249, 32, 0.12)',
                border: '1px solid rgba(200, 249, 32, 0.4)',
                color: 'var(--p)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1rem',
                boxShadow: '0 0 25px rgba(200, 249, 32, 0.25)',
              }}
            >
              <Upload size={30} />
            </div>

            <h4 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '0.35rem', color: '#fff' }}>
              {file ? file.name : 'اختر ملف CSV أو اسحبه هنا'}
            </h4>
            <p style={{ fontSize: '0.85rem', color: 'var(--m)' }}>
              يجب أن يحتوي الملف على الأعمدة: <code style={{ color: 'var(--p)', fontFamily: 'var(--font-mono)' }}>identifier, platform, mailbox_label, password</code>
            </p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="submit"
              disabled={!file || uploading}
              className="btn-neon"
              style={{ width: 'auto', minHeight: 48, padding: '0 28px' }}
            >
              <FileSpreadsheet size={18} />
              <span>{uploading ? 'جاري فحص الملف...' : 'معاينة الملف والتحقق'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Preview Section */}
      {previewData && (
        <div className="card-neon" style={{ padding: '1.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff' }}>
                نتائج معاينة الدفعة (Batch #{previewData.batch_id})
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--m)' }}>
                إجمالي السجلات: {previewData.total_rows} • السجلات الصالحة: <span style={{ color: 'var(--p)', fontWeight: 700 }}>{previewData.valid_rows}</span> • السجلات غير الصالحة: <span style={{ color: '#ff8787', fontWeight: 700 }}>{previewData.invalid_rows}</span>
              </p>
            </div>

            <button
              type="button"
              onClick={handleCommit}
              disabled={committing || previewData.valid_rows === 0}
              className="btn-neon"
              style={{ width: 'auto', minHeight: 48, padding: '0 28px' }}
            >
              <Check size={18} />
              <span>{committing ? 'جاري الاستيراد...' : `تأكيد استيراد (${previewData.valid_rows}) حساب`}</span>
            </button>
          </div>

          {/* Sample Valid Rows */}
          {previewData.sample_valid && previewData.sample_valid.length > 0 && (
            <div className="table-container" style={{ marginBottom: '1.5rem' }}>
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>المعرف (Identifier)</th>
                    <th>المنصة (Platform)</th>
                    <th>صندوق البريد (Mailbox)</th>
                    <th>كلمة المرور</th>
                  </tr>
                </thead>
                <tbody>
                  {previewData.sample_valid.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--p)' }}>{r.identifier}</td>
                      <td>{r.platform}</td>
                      <td>{r.mailbox_label}</td>
                      <td style={{ color: 'var(--m)', fontFamily: 'var(--font-mono)' }}>{r.has_password ? '••••••••' : 'بدون'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Invalid Rows if any */}
          {previewData.sample_invalid && previewData.sample_invalid.length > 0 && (
            <div style={{ padding: '1rem', borderRadius: '12px', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)' }}>
              <h4 style={{ color: '#ff8787', fontWeight: 700, marginBottom: '0.5rem', fontSize: '0.95rem' }}>
                أخطاء في بعض السجلات:
              </h4>
              <ul style={{ paddingInlineStart: '1.25rem', fontSize: '0.875rem', color: '#ffd0d0' }}>
                {previewData.sample_invalid.map((inv, idx) => (
                  <li key={idx}>السطر {inv.row_number}: {inv.reason}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
