import fs from 'node:fs'
import path from 'node:path'
import { createHash } from 'node:crypto'
import matter from 'gray-matter'

export class MethodFlowError extends Error {}
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const text = value => typeof value === 'string' && value.trim().length > 0
const fail = message => { throw new MethodFlowError(message) }

function sourcePath(root, relative, artifact = false) {
  const pattern = artifact ? /^python\/methods\/[a-zA-Z0-9_]+\.(py|tsv)$/ : /^python\/(methods\/[a-zA-Z0-9_]+|base)\.py$/
  if (!text(relative) || !pattern.test(relative)) fail('源码路径不在允许范围：' + relative)
  const file = path.join(root, relative)
  if (!fs.existsSync(file)) fail('源码文件不存在：' + relative)
  const pythonRoot = fs.realpathSync(path.join(root, 'python'))
  const actual = fs.realpathSync(file), within = path.relative(pythonRoot, actual)
  if (within.startsWith('..') || path.isAbsolute(within)) fail('源码路径超出Python目录：' + relative)
  return actual
}

function symbolRange(lines, symbol, file) {
  let start = 0, end = lines.length
  for (const name of symbol.split('.')) {
    if (!/^[a-zA-Z_]\w*$/.test(name)) fail('无效的源码符号：' + symbol)
    const found = []
    for (let i = start; i < end; i++) {
      if (new RegExp(`^\\s*(?:async\\s+)?(?:def|class)\\s+${name}(?:\\s*\\(|\\s*:)`).test(lines[i])) found.push(i)
    }
    if (found.length !== 1) fail(`${file}：符号 ${symbol} 未唯一定位`)
    start = found[0]
    const indent = lines[start].search(/\S/)
    let inDocstring = false
    for (let i = start + 1; i < end; i++) {
      const line = lines[i], trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const quoteCount = (line.match(/"""|'''/g) || []).length
      if (inDocstring) { if (quoteCount % 2) inDocstring = false; continue }
      if (line.search(/\S/) <= indent && !/^[)\]}]/.test(trimmed)) { end = i; break }
      if (quoteCount % 2) inDocstring = true
    }
  }
  const indent = lines[start].search(/\S/)
  while (end > start && (!lines[end - 1].trim() || (lines[end - 1].trim().startsWith('#') && lines[end - 1].search(/\S/) <= indent))) end--
  return { start, end }
}

function anchor(lines, value, start, end, context) {
  if (!text(value)) fail(context + '：定位锚点为空')
  const matches = []
  for (let i = start; i < end; i++) if (lines[i].includes(value)) matches.push(i)
  if (matches.length !== 1) fail(context + '：锚点未唯一匹配：' + value)
  return matches[0]
}

function hasExecutable(lines) {
  let inDocstring = false, inSignature = false
  return lines.some(line => {
    const trimmed = line.trim(), quotes = (line.match(/"""|'''/g) || []).length
    if (inDocstring) { if (quotes % 2) inDocstring = false; return false }
    if (quotes) { if (quotes % 2) inDocstring = true; return false }
    if (inSignature) { if (/:\s*(?:#.*)?$/.test(trimmed)) inSignature = false; return false }
    if (/^(?:(?:async )?def |class )/.test(trimmed)) {
      inSignature = !/:\s*(?:#.*)?$/.test(trimmed)
      return false
    }
    return trimmed && !trimmed.startsWith('#') && !/^pass\b/.test(trimmed)
  })
}

/** Descriptions reference live Python; no copied code and no Python execution. */
export function loadMethodFlow(methodId, { root = process.cwd() } = {}) {
  if (!/^[a-z][a-z0-9_]*$/.test(methodId)) return null
  const configPath = path.join(root, 'src/data/method_flows', methodId + '.json')
  if (!fs.existsSync(configPath)) return null
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  if (config.schemaVersion !== 2 || config.methodId !== methodId || !text(config.methodName) || !text(config.description) || !config.steps?.length) fail(methodId + '：流程说明版本、身份或步骤不完整')
  if ('code' in config) fail(methodId + '：流程说明不得保存代码副本')
  const sources = new Map()
  function readSource(relative) {
    if (!sources.has(relative)) {
      const bytes = fs.readFileSync(sourcePath(root, relative))
      sources.set(relative, { path: relative, sha256: hash(bytes), lines: bytes.toString('utf8').split(/\r?\n/) })
    }
    return sources.get(relative)
  }
  const steps = config.steps.map((step, index) => {
    const context = `${methodId} / ${step.name || index + 1}`
    for (const key of ['name', 'description', 'basis']) if (!text(step[key])) fail(context + '：缺少 ' + key)
    if ('code' in step || 'codeLines' in step) fail(context + '：步骤不得保存代码副本或固定行号')
    if (step.id !== index + 1 || !text(step.formula?.expression) || !text(step.formula?.explanation) || !step.formula.symbols?.length) fail(context + '：步骤序号或公式说明不完整')
    if (step.formula.symbols.some(v => !text(v.symbol) || !text(v.meaning))) fail(context + '：公式符号说明不完整')
    for (const key of ['inputs', 'outputs']) {
      if (!step[key]?.length || step[key].some(v => !text(v.code) || !text(v.symbol) || !text(v.meaning))) fail(context + '：缺少输入输出映射')
    }
    if (!step.sources?.length) fail(context + '：缺少真实源码引用')
    const references = step.sources.map(ref => {
      const source = readSource(ref.file), lines = source.lines
      let { start, end } = ref.symbol ? symbolRange(lines, ref.symbol, ref.file) : { start: 0, end: lines.length }
      if (!ref.symbol && !ref.from) fail(context + '：源码引用缺少符号或起始锚点')
      if (ref.from) start = anchor(lines, ref.from, start, end, context)
      if (ref.until && ref.through) fail(context + '：until 与 through 不可同时使用')
      if (ref.until) end = anchor(lines, ref.until, start + 1, end, context)
      if (ref.through) end = anchor(lines, ref.through, start, end, context) + 1
      if (!hasExecutable(lines.slice(start, end))) fail(context + '：源码范围只有说明而无可执行语句')
      return { file: ref.file, symbol: ref.symbol, label: ref.label || ref.symbol || path.basename(ref.file), start, end }
    })
    return { ...step, sources: references }
  })
  const algorithm = path.join(root, 'src/content/algorithms', methodId + '.md')
  const implementation = fs.existsSync(algorithm) ? matter(fs.readFileSync(algorithm, 'utf8')).data.implementation?.summary || '' : ''
  const artifacts = (config.artifacts || []).map(relative => {
    const bytes = fs.readFileSync(sourcePath(root, relative, true))
    return { path: relative, sha256: hash(bytes), bytes: bytes.length }
  })
  return { ...config, implementation, steps, sources: [...sources.values()], artifacts }
}

export function validateCompletedMethodFlows(methods, root = process.cwd()) {
  for (const method of methods) if (method.layer1.process.status === 'done') {
    if (!loadMethodFlow(method.id, { root })) fail(method.id + '：已完成的程序流程缺少说明配置')
  }
}
