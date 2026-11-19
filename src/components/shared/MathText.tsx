"use client"

import katex from 'katex'
import 'katex/dist/katex.min.css'

export function MathText({ math, className = '' }: { math: string; className?: string }) {
  const html = katex.renderToString(math, { throwOnError: false, trust: false, strict: false })
  return <span className={'inline-block align-middle ' + className} dangerouslySetInnerHTML={{ __html: html }} />
}
