#!/usr/bin/env node
const fs = require('node:fs')
const path = require('node:path')

const repoRoot = path.resolve(__dirname, '..', '..')
const extensionRoot = path.resolve(__dirname, '..')
const bundledRoot = path.join(extensionRoot, 'bundled', 'backend')

function copyRecursive(source, target) {
  if (!fs.existsSync(source)) return
  const stat = fs.statSync(source)
  if (stat.isDirectory()) {
    fs.mkdirSync(target, { recursive: true })
    for (const entry of fs.readdirSync(source)) {
      copyRecursive(path.join(source, entry), path.join(target, entry))
    }
    return
  }
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.copyFileSync(source, target)
}

fs.rmSync(bundledRoot, { recursive: true, force: true })
copyRecursive(path.join(repoRoot, 'app'), path.join(bundledRoot, 'app'))
copyRecursive(path.join(repoRoot, 'pyproject.toml'), path.join(bundledRoot, 'pyproject.toml'))
copyRecursive(path.join(repoRoot, '.env.example'), path.join(bundledRoot, '.env.example'))
console.log(`Bundled backend into ${bundledRoot}`)
