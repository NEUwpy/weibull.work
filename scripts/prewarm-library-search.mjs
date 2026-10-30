import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import nextEnv from '@next/env'

// --import awaits this module before Next's CLI starts in the same Node process.
// Leave missing-build diagnostics and command-line handling to Next itself.
const root = process.cwd()
const informational = process.argv.some(argument => ['--help', '-h', '--version', '-v'].includes(argument))
if (!informational && fs.existsSync(path.join(root, '.next', 'BUILD_ID'))) {
  nextEnv.loadEnvConfig(root, false)
  const require = createRequire(import.meta.url)
  const { register } = require(path.join(root, '.next', 'server', 'instrumentation.js'))
  await register()
}
