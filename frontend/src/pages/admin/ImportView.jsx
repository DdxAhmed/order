import React, { useState } from 'react';
import { api } from '../../api/client';
import { useLang } from '../../context/LangContext';
import {
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertCircle,
  FileText,
  ArrowRight,
} from 'lucide-react';

export default function ImportView({ setCurrentSection }) {
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
      setSuccessMsg(res.message || 'تم استيراد الحسابات بنجاح');
      setPreviewData(null);
      setFile(null);
    } catch (err) {
      setErrorMsg(err.message || 'تعذر استيراد الدفعة');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h2 style={{ fontSize: '1.65rem', fontWeight: 800, marginBottom: '0.35rem' }}>
          {t('import')}
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          استيراد حسابات المخزون دفعة واحدة من ملف CSV مع المعاينة والتحقق المسبق
        </p>
      </div>

      {errorMsg && (
        <div className="alert alert-danger">
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="alert alert-success">
          <CheckCircle2 size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Upload Zone */}
      <div className="glass-panel" style={{ padding: '2rem' }}>
        <form onSubmit={handleUploadPreview} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div
            style={{
              border: '2px dashed var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              padding: '2.5rem 1.5rem',
              textAlign: 'center',
              background: 'rgba(0, 0, 0, 0.2)',
              cursor: 'pointer',
              position: 'relative',
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
                width: 52,
                height: 52,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(99, 102, 241, 0.15)',
                color: 'var(--accent-primary)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '0.75rem',
              }}
            >
              <Upload size={26} />
            </div>

            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.25rem' }}>
              {file ? file.name : 'اختر ملف CSV أو اسحبه هنا'}
            </h4>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              يجب أن يحتوي الملف على الأعمدة: platform, account_identifier, mailbox_reference, status, notes
            </p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="submit"
              disabled={!file || uploading}
              className="btn btn-primary"
            >
              <FileSpreadsheet size={16} />
              <span>{uploading ? 'جاري قراءة ومعاينة الملف...' : 'معاينة وفحص الملف'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Preview Table & Commit Action */}
      {previewData && (
        <div className="glass-panel" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
                معاينة نتائج الملف ({previewData.total_rows} سطر)
              </h3>
              <span style={{ fontSize: '0.85rem', color: previewData.error_count > 0 ? 'var(--danger)' : 'var(--success)' }}>
                {previewData.error_count > 0
                  ? `يوجد ${previewData.error_count} خطأ يجب تصحيحه قبل الاعتماد`
                  : 'جميع الأسطر صحيحة وجاهزة للاستيراد'}
              </span>
            </div>

            <button
              onClick={handleCommit}
              disabled={committing || previewData.error_count > 0}
              className="btn btn-success"
            >
              <CheckCircle2 size={16} />
              <span>{committing ? 'جاري الاعتماد...' : 'تأكيد واستيراد الحسابات'}</span>
            </button>
          </div>

          <div className="table-container">
            <table className="modern-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('platform')}</th>
                  <th>{t('identifier')}</th>
                  <th>صندوق البريد</th>
                  <th>{t('status')}</th>
                  <th>الحالة والتحقق</th>
                </tr>
              </thead>
              <tbody>
                {previewData.rows?.map((row) => (
                  <tr key={row.row_number}>
                    <td style={{ color: 'var(--text-muted)' }}>{row.row_number}</td>
                    <td>{row.data?.platform}</td>
                    <td style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                      {row.data?.account_identifier}
                    </td>
                    <td>{row.data?.mailbox_reference}</td>
                    <td>{row.data?.status}</td>
                    <td>
                      {row.error ? (
                        <span className="badge badge-danger">{row.error}</span>
                      ) : (
                        <span className="badge badge-success">صالح</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
