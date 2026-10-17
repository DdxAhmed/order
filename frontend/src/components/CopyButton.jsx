import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useLang } from '../context/LangContext';

export default function CopyButton({ text, className = 'btn btn-secondary btn-sm', label }) {
  const [copied, setCopied] = useState(false);
  const { t } = useLang();

  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  const displayText = copied ? t('copied') : (label || t('copy'));

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={className}
      title={copied ? t('copied') : t('copy')}
      aria-label={copied ? t('copied') : t('copy')}
    >
      {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />}
      <span>{displayText}</span>
    </button>
  );
}
