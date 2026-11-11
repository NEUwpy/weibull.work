"use client"

import katex from 'katex'
import styles from './ProcessEquation.module.css'

export function ProcessEquation({ expression, number }: { expression: string; number?: number }) {
  const html = katex.renderToString(expression, { displayMode: true, throwOnError: false, trust: false, strict: false })
  return <div className={styles.equation} data-equation-number={number}>
    <div className={styles.math} dangerouslySetInnerHTML={{ __html: html }} />
    {number !== undefined && <span className={styles.number} aria-label={`公式 ${number}`}>({number})</span>}
  </div>
}
