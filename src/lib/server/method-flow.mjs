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

function readPythonFlow(source, methodId) {
  const start = source.lines.indexOf('# @method-flow')
  if (start === -1) return null
  const end = source.lines.indexOf('# @end-method-flow', start + 1)
  const declaration = source.lines.slice(start + 1, end)
  if (end === -1 || source.lines.lastIndexOf('# @method-flow') !== start || declaration.some(line => !line.startsWith('# '))) {
    fail(methodId + '：Python 流程标注范围无效')
  }
  try {
    return JSON.parse(declaration.map(line => line.slice(2)).join('\n'))
  } catch {
    fail(methodId + '：Python 流程标注格式无效')
  }
}

function validateWorkflow(workflow, steps, methodId) {
  const invalid = reason => fail(`${methodId}：流程图${reason}`)
  const stepIds = new Set(steps.map(step => step.id))
  const anchors = new Set()
  const depictedSteps = new Set()
  if (!text(workflow.title) || !text(workflow.description) || !Array.isArray(workflow.items) || !workflow.targets) invalid('声明不完整')
  for (const id of Object.values(workflow.targets)) if (!stepIds.has(id)) invalid('目标步骤不存在')
  if (workflow.legacySourceSteps && (!Array.isArray(workflow.legacySourceSteps)
    || workflow.legacySourceSteps.some(id => !stepIds.has(id)))) invalid('旧步骤定位无效')
  function visit(items) {
    for (const item of items) {
      if (item.kind === 'group') {
        if (!text(item.layout) || !Array.isArray(item.children)) invalid('分组无效')
        visit(item.children)
        continue
      }
      if (!text(item.anchor) || anchors.has(item.anchor)) invalid('节点锚点缺失或重复')
      anchors.add(item.anchor)
      if (item.target && !Object.hasOwn(workflow.targets, item.target)) invalid('节点目标不存在')
      if (item.kind === 'step') {
        if (!stepIds.has(item.step) || depictedSteps.has(item.step)) invalid('节点步骤无效或重复')
        depictedSteps.add(item.step)
      } else if (item.kind !== 'port' || !item.target || !text(item.label) || !['input', 'output'].includes(item.direction)) {
        invalid('输入输出节点无效')
      }
    }
  }
  visit(workflow.items)
  if (depictedSteps.size !== stepIds.size) invalid('未覆盖全部程序步骤')
  if (!Array.isArray(workflow.connections) || workflow.connections.some(edge => !anchors.has(edge.from) || !anchors.has(edge.to))) invalid('连线端点不存在')
}

function normalizeFormula(formula, context) {
  if (!formula) return formula
  const validEquations = value => Array.isArray(value) && value.length > 0 && value.every(text)
  const combined = equations => String.raw`\begin{aligned}&${equations.join(String.raw`\\[12pt]&`)}\end{aligned}`
  if (formula.equations !== undefined && (!validEquations(formula.equations) || formula.expression !== undefined)) fail(context + '：逐条公式无效或重复声明')
  if (formula.variants && (typeof formula.variants !== 'object' || Array.isArray(formula.variants))) fail(context + '：分支公式无效')
  const variants = {}, variantEquations = {}
  for (const [key, value] of Object.entries(formula.variants ?? {})) {
    if (validEquations(value)) {
      if (formula.equations && value.length !== formula.equations.length) fail(context + '：分支公式数量不一致')
      variantEquations[key] = value
      variants[key] = combined(value)
    } else if (text(value)) variants[key] = value
    else fail(context + '：分支公式无效')
  }
  return { ...formula, expression: formula.equations ? combined(formula.equations) : formula.expression,
    ...(formula.variants && { variants, variantEquations }) }
}

/** Descriptions reference live Python; no copied code and no Python execution. */
export function loadMethodFlow(methodId, { root = process.cwd() } = {}) {
  if (!/^[a-z][a-z0-9_]*$/.test(methodId)) return null
  const configPath = path.join(root, 'src/data/method_flows', methodId + '.json')
  const sources = new Map()
  function readSource(relative) {
    if (!sources.has(relative)) {
      const bytes = fs.readFileSync(sourcePath(root, relative))
      sources.set(relative, { path: relative, sha256: hash(bytes), lines: bytes.toString('utf8').split(/\r?\n/) })
    }
    return sources.get(relative)
  }
  const pythonPath = `python/methods/${methodId}.py`
  const pythonSource = fs.existsSync(path.join(root, pythonPath)) ? readSource(pythonPath) : null
  const pythonFlow = pythonSource && readPythonFlow(pythonSource, methodId)
  const hasJson = fs.existsSync(configPath)
  if (pythonFlow && hasJson) fail(methodId + '：流程同时定义在 Python 和 JSON 中')
  if (!pythonFlow && !hasJson) return null
  const config = pythonFlow ?? JSON.parse(fs.readFileSync(configPath, 'utf8'))
  if (config.schemaVersion !== 2 || config.methodId !== methodId || !text(config.methodName) || !text(config.description) || !config.steps?.length) fail(methodId + '：流程说明版本、身份或步骤不完整')
  if ('code' in config) fail(methodId + '：流程说明不得保存代码副本')
  if (!pythonFlow) sources.clear()
  if (config.workflow) validateWorkflow(config.workflow, config.steps, methodId)
  const counters = []
  const steps = config.steps.map((step, index) => {
    const context = `${methodId} / ${step.name || index + 1}`
    step = { ...step, formula: normalizeFormula(step.formula, context) }
    for (const key of ['name', 'description', 'basis']) if (!text(step[key])) fail(context + '：缺少 ' + key)
    if ('code' in step || 'codeLines' in step) fail(context + '：步骤不得保存代码副本或固定行号')
    if (step.id !== index + 1 || !text(step.formula?.expression) || !text(step.formula?.explanation) || !step.formula.symbols?.length) fail(context + '：步骤序号或公式说明不完整')
    if (step.formula.variants && (typeof step.formula.variants !== 'object' || Array.isArray(step.formula.variants) || Object.values(step.formula.variants).some(value => !text(value)))) fail(context + '：分支公式无效')
    if (step.formula.symbols.some(v => !text(v.symbol) || !text(v.meaning))) fail(context + '：公式符号说明不完整')
    for (const key of ['inputs', 'outputs']) {
      if (!step[key]?.length || step[key].some(v => !text(v.code) || !text(v.symbol) || !text(v.meaning))) fail(context + '：缺少输入输出映射')
    }
    if (!step.sources?.length) fail(context + '：缺少真实源码引用')
    if (step.primarySource !== undefined && (!Number.isInteger(step.primarySource) || step.primarySource < 0 || step.primarySource >= step.sources.length)) fail(context + '：本步核心代码定位无效')
    const depth = step.depth ?? 0, kind = step.kind ?? 'step'
    if (!Number.isInteger(depth) || depth < 0 || depth > 3 || (index === 0 && depth !== 0) || depth > (config.steps[index - 1]?.depth ?? 0) + 1) fail(context + '：调用层级不连续')
    if (!['step', 'call', 'loop', 'condition', 'return'].includes(kind) || (depth > 0 && !text(step.context))) fail(context + '：缺少执行关系说明')
    counters.length = depth + 1
    counters[depth] = (counters[depth] || 0) + 1
    const references = step.sources.map(ref => {
      const source = readSource(ref.file), lines = source.lines
      let { start, end } = ref.symbol ? symbolRange(lines, ref.symbol, ref.file) : { start: 0, end: lines.length }
      if (!ref.symbol && !ref.from) fail(context + '：源码引用缺少符号或起始锚点')
      if (ref.after) start = anchor(lines, ref.after, start, end, context) + 1
      if (ref.from) start = anchor(lines, ref.from, start, end, context)
      if (ref.until && ref.through) fail(context + '：until 与 through 不可同时使用')
      if (ref.until) end = anchor(lines, ref.until, start + 1, end, context)
      if (ref.through) end = anchor(lines, ref.through, start, end, context) + 1
      if (!hasExecutable(lines.slice(start, end))) fail(context + '：源码范围只有说明而无可执行语句')
      return { file: ref.file, symbol: ref.symbol, label: ref.label || ref.symbol || path.basename(ref.file), start, end }
    })
    return { ...step, depth, kind, number: counters.join('.'), sources: references }
  })
  const algorithm = path.join(root, 'src/content/algorithms', methodId + '.md')
  const definition = fs.existsSync(algorithm) ? matter(fs.readFileSync(algorithm, 'utf8')).data.implementation : null
  const implementationSummary = config.implementation || definition?.summary || ''
  const artifacts = (config.artifacts || []).map(relative => {
    const bytes = fs.readFileSync(sourcePath(root, relative, true))
    return { path: relative, sha256: hash(bytes), bytes: bytes.length }
  })
  return { ...config, implementation: implementationSummary, steps, sources: [...sources.values()], artifacts }
}

export function validateCompletedMethodFlows(methods, root = process.cwd()) {
  for (const method of methods) if (method.layer1.process.status === 'done') {
    if (!loadMethodFlow(method.id, { root })) fail(method.id + '：已完成的程序流程缺少说明配置')
  }
}
