/** The note's named summary is public; the rest of the note stays local. */
export function extractLibraryNoteSummary(markdown: string): string {
  const lines = markdown.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').split('\n')
  let start = 0
  if (lines[0]?.trim() === '---') {
    const end = lines.findIndex((line, index) => index > 0 && line.trim() === '---')
    if (end < 0) return ''
    start = end + 1
  }
  let collecting = false
  let fence = ''
  const summary: string[] = []
  for (const line of lines.slice(start)) {
    const marker = /^ {0,3}(`{3,}|~{3,})/.exec(line)?.[1]
    if (marker) {
      if (!fence) fence = marker
      else if (marker[0] === fence[0] && marker.length >= fence.length) fence = ''
      if (collecting) summary.push(line)
      continue
    }
    const heading = !fence && /^ {0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/.exec(line)
    if (heading) {
      if (collecting) break
      const title = heading[1].replace(/\*\*/g, '').replace(/^(?:\d+|[一二三四五六七八九十]+)[.．、)）][ \t]*/, '').trim()
      collecting = title === '一句话总结'
    } else if (collecting) summary.push(line)
  }
  while (summary.length && (!summary[summary.length - 1].trim() || /^(?:-{3,}|\*{3,}|_{3,})$/.test(summary[summary.length - 1].trim()))) summary.pop()
  return summary.join('\n').trim()
}
