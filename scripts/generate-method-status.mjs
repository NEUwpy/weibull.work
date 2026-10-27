import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  buildGeneratedStatus,
  flattenCatalogLeaves,
  flattenLeafIds,
  parseStatusMarkdown,
} from './lib/method-status.mjs'

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const STATUS_SOURCE = path.join(ROOT_DIR, '05-状态.md')
const METHODS_CATALOG = path.join(ROOT_DIR, 'src', 'data', 'methods.json')
const OUTPUT_FILE = path.join(ROOT_DIR, 'src', 'data', 'method-status.generated.json')

function main() {
  const checkMode = process.argv.includes('--check')

  const markdown = fs.readFileSync(STATUS_SOURCE, 'utf-8')
  const catalog = JSON.parse(fs.readFileSync(METHODS_CATALOG, 'utf-8'))
  const catalogLeaves = flattenCatalogLeaves(catalog)
  const expectedLeafIds = catalogLeaves.map((leaf) => leaf.id)

  const document = parseStatusMarkdown(markdown, expectedLeafIds, {
    checkEvidencePaths: true,
    rootDir: ROOT_DIR,
    catalogLeaves,
  })
  const generated = buildGeneratedStatus(document, expectedLeafIds)
  const serialized = `${JSON.stringify(generated, null, 2)}\n`

  if (checkMode) {
    if (!fs.existsSync(OUTPUT_FILE)) {
      console.error(
        'method-status: src/data/method-status.generated.json is missing. Run "npm run generate:method-status" and commit the result.',
      )
      process.exit(1)
    }
    const committed = fs.readFileSync(OUTPUT_FILE, 'utf-8')
    if (committed !== serialized) {
      console.error(
        'method-status: src/data/method-status.generated.json is stale relative to 05-状态.md. Run "npm run generate:method-status" and commit the result.',
      )
      process.exit(1)
    }
    console.log(
      `method-status: cache is up to date (${generated.methods.length} methods).`,
    )
    return
  }

  fs.writeFileSync(OUTPUT_FILE, serialized, 'utf-8')
  console.log(
    `method-status: wrote src/data/method-status.generated.json (${generated.methods.length} methods).`,
  )
}

try {
  main()
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
}
