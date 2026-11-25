import { createHash } from 'node:crypto'

export class WorkbookIntegrityError extends Error {}

export function workbookSha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex')
}

export function readWorkbookManifest(entry, readBatchFile) {
  const raw = readBatchFile('manifest.json')
  if (workbookSha256(raw) !== entry.manifestSha256) throw new WorkbookIntegrityError('计算来源记录的哈希已变化')
  const manifest = JSON.parse(raw.toString('utf8'))
  if (manifest?.schemaVersion !== 1 || manifest.id !== entry.id) throw new WorkbookIntegrityError('计算来源与数据卡不匹配')
  return manifest
}

export function readWorkbookArtifact(manifest, relative, readBatchFile) {
  const record = manifest.files?.[relative]
  if (!record) throw new WorkbookIntegrityError('文件未在计算来源中登记')
  const raw = readBatchFile(relative)
  if (raw.length !== record.bytes || workbookSha256(raw) !== record.sha256) throw new WorkbookIntegrityError('文件身份已变化：' + relative)
  return raw
}
