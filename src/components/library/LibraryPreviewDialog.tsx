'use client'

import type { ComponentPropsWithRef, ReactNode } from 'react'
import { ArrowLeft, X } from 'lucide-react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import './dialog.css'

export function LibraryPreviewDialog({ title, detail, backLabel, onClose, actions, padded, scroll, children }: {
  title: string; detail?: string; backLabel?: string; onClose: () => void; actions?: ReactNode
  padded?: boolean; scroll?: Pick<ComponentPropsWithRef<'div'>, 'ref' | 'onClick'>; children: ReactNode
}) {
  const { dialog, closeButton } = usePreviewDialog(onClose)

  return <dialog {...dialog} className="library-document-dialog"
    data-has-parent={Boolean(backLabel) || undefined} aria-label={title}>
    <div className="library-document-dialog-bar">
      <button type="button" className="library-document-dialog-back" aria-label={backLabel || '返回原窗口'} onClick={onClose}>
        <ArrowLeft size={20} aria-hidden="true" />
      </button>
      <span className="library-document-dialog-heading">{title}{detail && <span className="library-document-dialog-id">{detail}</span>}</span>
      <div className="flex items-center gap-2">
        {actions}
        <button type="button" ref={closeButton} className="library-document-dialog-close" aria-label={`关闭${title}`} title="关闭" onClick={onClose}>
          <X size={22} aria-hidden="true" />
        </button>
      </div>
    </div>
    <div {...scroll} className={padded ? 'library-document-dialog-scroll library-entity-content' : 'library-document-dialog-scroll'} data-library-dialog-scroll>
      {children}
    </div>
  </dialog>
}
