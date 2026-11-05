'use client'

import React, { useId } from 'react'
import { usePreviewDialog } from '@/components/shared/usePreviewDialog'
import type { CalculationNotice } from '@/lib/calculation-feedback'
import './calculation-notice.css'

export function CalculationNoticeDialog({ notice, onClose }: { notice: CalculationNotice; onClose: () => void }) {
  const { dialog, closeButton } = usePreviewDialog(onClose)
  const id = useId()

  return <dialog {...dialog} className="calculation-notice" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}>
    <h2 id={`${id}-title`}>{notice.title}</h2>
    {notice.sourceName && <p className="calculation-notice-source">{notice.sourceName}</p>}
    <p id={`${id}-description`} className="calculation-notice-description">{notice.description}</p>
    <button ref={closeButton} type="button" className="calculation-notice-confirm" onClick={onClose}>知道了</button>
  </dialog>
}
