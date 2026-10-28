import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import ts from 'typescript'

// Load actual server TS and its local dependencies while allowing API clients to be stubbed.
export function loadServerModule(relative, overrides = {}, globals = {}) {
  const cache = new Map()
  function load(file) {
    file = path.resolve(file)
    if (cache.has(file)) return cache.get(file).exports
    const module = { exports: {} }
    cache.set(file, module)
    const require = createRequire(file)
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    }).outputText
    vm.runInNewContext(source, {
      module, exports: module.exports, process, console, URL, TextDecoder, TextEncoder,
      ReadableStream, Uint8Array, Buffer,
      setTimeout: (...args) => { const timer = setTimeout(...args); timer.unref(); return timer },
      require: name => {
        if (Object.hasOwn(overrides, name)) return overrides[name]
        const target = name.startsWith('./') || name.startsWith('../') ? path.resolve(path.dirname(file), name)
          : name.startsWith('@/') ? path.resolve('src', name.slice(2)) : null
        return target && fs.existsSync(target + '.ts') ? load(target + '.ts') : require(name)
      },
      ...globals,
    }, { filename: file })
    return module.exports
  }
  return load(relative)
}
