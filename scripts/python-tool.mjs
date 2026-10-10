/* eslint-disable @typescript-eslint/explicit-function-return-type */

import { existsSync, rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const virtualEnvironmentPython =
  process.platform === 'win32'
    ? join(root, '.venv', 'Scripts', 'python.exe')
    : join(root, '.venv', 'bin', 'python')
const systemPython = process.platform === 'win32' ? 'python' : 'python3'

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

function requireVirtualEnvironment() {
  if (!existsSync(virtualEnvironmentPython)) {
    throw new Error('Python virtual environment is missing. Run npm run python:setup first.')
  }
}

const action = process.argv[2]

if (action === 'setup') {
  if (!existsSync(virtualEnvironmentPython)) {
    run(systemPython, ['-m', 'venv', '.venv'])
  }
  run(virtualEnvironmentPython, [
    '-m',
    'pip',
    'install',
    '--disable-pip-version-check',
    '-r',
    'requirements-dev.txt'
  ])
} else if (action === 'test') {
  const python = existsSync(virtualEnvironmentPython) ? virtualEnvironmentPython : systemPython
  run(python, ['-m', 'unittest', 'discover', '-s', 'backend/tests', '-v'])
} else if (action === 'build') {
  requireVirtualEnvironment()
  const distribution = join(root, 'python-dist')
  const work = join(root, '.python-build')
  rmSync(distribution, { recursive: true, force: true })
  rmSync(work, { recursive: true, force: true })

  const args = [
    '-m',
    'PyInstaller',
    '--noconfirm',
    '--clean',
    '--onefile',
    '--name',
    'stubuddy-backend',
    '--distpath',
    distribution,
    '--workpath',
    work,
    '--specpath',
    work,
    '--paths',
    root,
    'scripts/stubuddy_backend.py'
  ]
  if (process.platform === 'win32') args.splice(4, 0, '--windowed')
  if (process.platform === 'win32') {
    args.splice(
      -1,
      0,
      '--hidden-import',
      'backend.capture_windows',
      '--exclude-module',
      'backend.capture_wayland'
    )
  } else if (process.platform === 'linux') {
    args.splice(
      -1,
      0,
      '--hidden-import',
      'backend.capture_wayland',
      '--exclude-module',
      'backend.capture_windows'
    )
  } else {
    args.splice(
      -1,
      0,
      '--exclude-module',
      'backend.capture_windows',
      '--exclude-module',
      'backend.capture_wayland'
    )
  }
  run(virtualEnvironmentPython, args)
} else {
  throw new Error(`Unknown Python tool action: ${action ?? '(missing)'}`)
}
