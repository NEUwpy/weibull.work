import fs from 'node:fs'
import path from 'node:path'
import matter from 'gray-matter'

export const STATUS_VALUES = ['todo', 'in_progress', 'done', 'blocked', 'not_applicable']
export const LAYER1_KEYS = ['backend', 'tests', 'calculator', 'theory', 'process']
export const LAYER2_KEYS = ['calculation', 'analysis']
export const LAYER3_KEYS = ['applicability', 'verification']

export const METHOD_LEVELS = [
  'not_started',
  'layer1_in_progress',
  'layer1_complete',
  'layer2_complete',
  'closed_loop',
]

const METHOD_KEYS = [
  'id',
  'name',
  'family',
  'shared_core',
  'classification_source',
  'paper',
  'layer1',
  'layer2',
  'layer3',
]

const ITEM_KEYS = ['status', 'evidence', 'reason', 'note', 'exception_approved']
const PAPER_KEYS = [
  'status',
  'title',
  'publication',
  'year',
  'stable_id',
  'evidence',
  'reason',
  'note',
]

function fail(message) {
  throw new Error(`method-status: ${message}`)
}

function isPlainObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function assertOnlyKeys(context, value, allowedKeys) {
  for (const key of Object.keys(value)) {
    if (!allowedKeys.includes(key)) {
      fail(`${context}: unknown field "${key}"`)
    }
  }
}

function assertEvidenceList(context, evidence) {
  if (!Array.isArray(evidence)) {
    fail(`${context}: evidence must be an array of paths`)
  }
  for (const entry of evidence) {
    if (!isNonEmptyString(entry)) {
      fail(`${context}: evidence entries must be non-empty strings`)
    }
  }
}

function validateStatusItem(context, item) {
  if (!isPlainObject(item)) {
    fail(`${context}: must be an object with status and evidence`)
  }
  assertOnlyKeys(context, item, ITEM_KEYS)
  if (!STATUS_VALUES.includes(item.status)) {
    fail(`${context}: unknown status "${item.status}"`)
  }
  assertEvidenceList(context, item.evidence)
  if (item.status === 'done' && item.evidence.length === 0) {
    fail(`${context}: status "done" requires non-empty evidence`)
  }
  if (item.status === 'blocked' && !isNonEmptyString(item.reason)) {
    fail(`${context}: status "blocked" requires a reason`)
  }
  if (item.status === 'not_applicable') {
    if (item.exception_approved !== true || !isNonEmptyString(item.reason)) {
      fail(
        `${context}: status "not_applicable" on a mandatory item requires exception_approved: true and a reason`,
      )
    }
  }
}

function validatePaper(context, paper) {
  if (!isPlainObject(paper)) {
    fail(`${context}: paper must be an object with status and evidence`)
  }
  assertOnlyKeys(`${context}: paper`, paper, PAPER_KEYS)
  if (!STATUS_VALUES.includes(paper.status)) {
    fail(`${context}: paper has unknown status "${paper.status}"`)
  }
  assertEvidenceList(`${context}: paper`, paper.evidence)
  if (paper.status === 'done') {
    if (paper.evidence.length === 0) {
      fail(`${context}: paper status "done" requires non-empty evidence`)
    }
    const missingMeta = ['title', 'publication', 'stable_id'].filter(
      (key) => !isNonEmptyString(paper[key]),
    )
    if (!Number.isInteger(paper.year)) {
      missingMeta.push('year')
    }
    if (missingMeta.length > 0) {
      fail(
        `${context}: completed paper requires citation metadata, missing: ${missingMeta.join(', ')}`,
      )
    }
  }
  if (paper.status === 'blocked' && !isNonEmptyString(paper.reason)) {
    fail(`${context}: paper status "blocked" requires a reason`)
  }
  if (paper.status === 'not_applicable') {
    fail(`${context}: paper status "not_applicable" is not allowed`)
  }
}

function validateLayer(context, layer, expectedKeys) {
  if (!isPlainObject(layer)) {
    fail(`${context}: must be an object with keys ${expectedKeys.join(', ')}`)
  }
  assertOnlyKeys(context, layer, expectedKeys)
  for (const key of expectedKeys) {
    if (!(key in layer)) {
      fail(`${context}: missing item "${key}"`)
    }
    validateStatusItem(`${context}.${key}`, layer[key])
  }
}

function validateMethod(method) {
  if (!isPlainObject(method)) {
    fail('every methods entry must be an object')
  }
  if (!isNonEmptyString(method.id)) {
    fail('every methods entry requires a non-empty method id')
  }
  const context = method.id
  assertOnlyKeys(context, method, METHOD_KEYS)
  for (const key of ['name', 'family', 'classification_source']) {
    if (!isNonEmptyString(method[key])) {
      fail(`${context}: "${key}" must be a non-empty string`)
    }
  }
  if (method.shared_core !== null && method.shared_core !== undefined && !isNonEmptyString(method.shared_core)) {
    fail(`${context}: "shared_core" must be null or a non-empty string`)
  }
  validatePaper(context, method.paper)
  validateLayer(`${context} layer1`, method.layer1, LAYER1_KEYS)
  validateLayer(`${context} layer2`, method.layer2, LAYER2_KEYS)
  validateLayer(`${context} layer3`, method.layer3, LAYER3_KEYS)
}

function collectEvidencePaths(method) {
  const paths = [...method.paper.evidence]
  for (const [layerKey, keys] of [
    ['layer1', LAYER1_KEYS],
    ['layer2', LAYER2_KEYS],
    ['layer3', LAYER3_KEYS],
  ]) {
    for (const key of keys) {
      paths.push(...method[layerKey][key].evidence)
    }
  }
  return paths
}

function assertRepositoryPath(context, rootDir, candidatePath) {
  if (path.isAbsolute(candidatePath)) {
    fail(`${context}: path must be repository-relative: "${candidatePath}"`)
  }
  const resolved = path.resolve(rootDir, candidatePath)
  const relative = path.relative(rootDir, resolved)
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    fail(`${context}: path escapes the repository root: "${candidatePath}"`)
  }
  if (!fs.existsSync(resolved)) {
    fail(`${context}: path does not exist: "${candidatePath}"`)
  }
}

export function validateStatusDocument(document, expectedLeafIds, options = {}) {
  if (!isPlainObject(document)) {
    fail('status document must be an object')
  }
  if (document.schema_version !== 1) {
    fail(`unsupported schema_version "${document.schema_version}", expected 1`)
  }
  assertOnlyKeys('status document', document, ['schema_version', 'methods'])
  if (!Array.isArray(document.methods)) {
    fail('status document requires a methods array')
  }
  if (!Array.isArray(expectedLeafIds) || expectedLeafIds.length === 0) {
    fail('expectedLeafIds must be a non-empty array')
  }

  const seen = new Set()
  for (const method of document.methods) {
    validateMethod(method)
    if (seen.has(method.id)) {
      fail(`duplicate method id "${method.id}"`)
    }
    seen.add(method.id)
  }

  const missing = expectedLeafIds.filter((id) => !seen.has(id))
  const extra = [...seen].filter((id) => !expectedLeafIds.includes(id))
  if (missing.length > 0 || extra.length > 0) {
    fail(
      `method id coverage mismatch: missing [${missing.join(', ')}], extra [${extra.join(', ')}]`,
    )
  }

  if (options.checkEvidencePaths) {
    const rootDir = options.rootDir ?? process.cwd()
    for (const method of document.methods) {
      assertRepositoryPath(method.id, rootDir, method.classification_source)
      for (const evidencePath of collectEvidencePaths(method)) {
        assertRepositoryPath(method.id, rootDir, evidencePath)
      }
    }
  }

  if (options.catalogLeaves) {
    const catalogByLeafId = new Map()
    for (const leaf of options.catalogLeaves) {
      if (!isPlainObject(leaf) || !isNonEmptyString(leaf.id)) {
        fail('every catalog leaves entry requires a non-empty id')
      }
      catalogByLeafId.set(leaf.id, leaf)
    }
    for (const method of document.methods) {
      const catalogLeaf = catalogByLeafId.get(method.id)
      if (!catalogLeaf) continue
      if (catalogLeaf.name !== undefined && method.name !== catalogLeaf.name) {
        fail(
          `${method.id}: name in status document ("${method.name}") does not match methods.json ("${catalogLeaf.name}")`,
        )
      }
      if (catalogLeaf.family !== undefined && method.family !== catalogLeaf.family) {
        fail(
          `${method.id}: family in status document ("${method.family}") does not match methods.json ("${catalogLeaf.family}")`,
        )
      }
    }
  }

  return document
}

function isItemComplete(item) {
  if (item.status === 'done') return true
  return item.status === 'not_applicable' && item.exception_approved === true
}

function isItemUntouched(item) {
  return item.status === 'todo'
}

export function deriveMethodCapability(method) {
  const layer1Missing = []
  if (!isItemComplete(method.paper)) {
    layer1Missing.push('paper')
  }
  for (const key of LAYER1_KEYS) {
    if (!isItemComplete(method.layer1[key])) {
      layer1Missing.push(key)
    }
  }
  const layer1Complete = layer1Missing.length === 0
  const layer2Complete =
    layer1Complete && LAYER2_KEYS.every((key) => isItemComplete(method.layer2[key]))
  const layer3Complete =
    layer2Complete && LAYER3_KEYS.every((key) => isItemComplete(method.layer3[key]))

  const untouched =
    isItemUntouched(method.paper) &&
    LAYER1_KEYS.every((key) => isItemUntouched(method.layer1[key])) &&
    LAYER2_KEYS.every((key) => isItemUntouched(method.layer2[key])) &&
    LAYER3_KEYS.every((key) => isItemUntouched(method.layer3[key]))

  let level = 'layer1_in_progress'
  if (layer3Complete) {
    level = 'closed_loop'
  } else if (layer2Complete) {
    level = 'layer2_complete'
  } else if (layer1Complete) {
    level = 'layer1_complete'
  } else if (untouched) {
    level = 'not_started'
  }

  return {
    id: method.id,
    level,
    calculatorEnabled: layer1Complete,
    missingLayer1: layer1Missing,
    paper: method.paper,
    items: {
      theory: method.layer1.theory,
      process: method.layer1.process,
      calculation: method.layer2.calculation,
      analysis: method.layer2.analysis,
      applicability: method.layer3.applicability,
      verification: method.layer3.verification,
    },
  }
}

function normalizeItem(item) {
  const normalized = {
    status: item.status,
    evidence: [...item.evidence],
  }
  if (isNonEmptyString(item.reason)) normalized.reason = item.reason
  if (isNonEmptyString(item.note)) normalized.note = item.note
  if (item.exception_approved === true) normalized.exception_approved = true
  return normalized
}

function normalizePaper(paper) {
  const normalized = { status: paper.status }
  if (isNonEmptyString(paper.title)) normalized.title = paper.title
  if (isNonEmptyString(paper.publication)) normalized.publication = paper.publication
  if (Number.isInteger(paper.year)) normalized.year = paper.year
  if (isNonEmptyString(paper.stable_id)) normalized.stable_id = paper.stable_id
  normalized.evidence = [...paper.evidence]
  if (isNonEmptyString(paper.reason)) normalized.reason = paper.reason
  if (isNonEmptyString(paper.note)) normalized.note = paper.note
  return normalized
}

function normalizeLayer(layer, keys) {
  const normalized = {}
  for (const key of keys) {
    normalized[key] = normalizeItem(layer[key])
  }
  return normalized
}

export function buildGeneratedStatus(document, expectedLeafIds) {
  validateStatusDocument(document, expectedLeafIds)
  const byId = new Map(document.methods.map((method) => [method.id, method]))
  const methods = expectedLeafIds.map((id) => {
    const method = byId.get(id)
    const capability = deriveMethodCapability(method)
    return {
      id: method.id,
      name: method.name,
      family: method.family,
      shared_core: method.shared_core ?? null,
      classification_source: method.classification_source,
      level: capability.level,
      calculatorEnabled: capability.calculatorEnabled,
      missingLayer1: capability.missingLayer1,
      paper: normalizePaper(method.paper),
      layer1: normalizeLayer(method.layer1, LAYER1_KEYS),
      layer2: normalizeLayer(method.layer2, LAYER2_KEYS),
      layer3: normalizeLayer(method.layer3, LAYER3_KEYS),
    }
  })
  return {
    schemaVersion: 1,
    source: '05-状态.md',
    methods,
  }
}

export function parseStatusMarkdown(markdown, expectedLeafIds, options = {}) {
  if (typeof markdown !== 'string' || markdown.trim().length === 0) {
    fail('status markdown must be a non-empty string')
  }
  const parsed = matter(markdown)
  if (!isPlainObject(parsed.data) || Object.keys(parsed.data).length === 0) {
    fail('status markdown must start with YAML front matter')
  }
  return validateStatusDocument(parsed.data, expectedLeafIds, options)
}

export function flattenCatalogLeaves(methodsCatalog) {
  if (!Array.isArray(methodsCatalog)) {
    fail('methods catalog must be an array of categories')
  }
  const seenCategoryIds = new Set()
  const seenLeafIds = new Set()
  const leaves = []
  for (const category of methodsCatalog) {
    if (!isPlainObject(category) || !Array.isArray(category.children)) {
      fail('every methods catalog category requires a children array')
    }
    if (!isNonEmptyString(category.id)) {
      fail('every methods catalog category requires a non-empty id')
    }
    if (seenCategoryIds.has(category.id)) {
      fail(`duplicate category id in methods catalog: "${category.id}"`)
    }
    seenCategoryIds.add(category.id)
    for (const child of category.children) {
      if (!isPlainObject(child) || !isNonEmptyString(child.id)) {
        fail('every methods catalog leaf requires a non-empty id')
      }
      if (seenLeafIds.has(child.id)) {
        fail(`duplicate leaf id in methods catalog: "${child.id}"`)
      }
      seenLeafIds.add(child.id)
      leaves.push({ id: child.id, name: child.name, family: category.id })
    }
  }
  return leaves
}

export function flattenLeafIds(methodsCatalog) {
  return flattenCatalogLeaves(methodsCatalog).map((leaf) => leaf.id)
}
