import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildCase} from './建表母体.mjs';
await buildCase(path.dirname(fileURLToPath(import.meta.url)));
