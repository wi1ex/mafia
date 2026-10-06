import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import ts from 'typescript'

const root = resolve(import.meta.dirname, '..')

async function loadTypescript(relativePath, prepare = (source) => source) {
  const source = prepare(readFileSync(resolve(root, relativePath), 'utf8'))
  const compiled = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

export async function loadPublicContent() {
  const seo = JSON.parse(readFileSync(resolve(root, 'src/content/seo.json'), 'utf8'))
  const { PUBLIC_SCHEMAS } = await loadTypescript('src/content/structuredData.ts', (source) =>
    source.replace("import seo from './seo.json'", `const seo = ${JSON.stringify(seo)}`),
  )
  return { seo, PUBLIC_SCHEMAS }
}
