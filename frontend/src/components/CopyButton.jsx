import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useLang } from '../context/LangContext';

export default function CopyButton({ text, className = 'btn btn-secondary btn-sm' }) {
  const [copied, setCopied] = useState(false);
  const { t } = useLang();

  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  return (
    <button onClick={handleCopy} className={className} title={copied ? t('copied') : t('copy')}>
      {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />}
      <span>{copied ? t('copied') : t('copy')}</span>
    </button>
  );
}
