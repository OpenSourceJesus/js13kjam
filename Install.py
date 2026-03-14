import os, sys, platform, subprocess

_thisDir = os.path.split(os.path.abspath(__file__))[0]
IS_LINUX = platform.system() == 'Linux'
IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'

# Pip flag for systems that use externally-managed Python (e.g. many Linux distros)
PIP_EXTRA_ARGS = ['--break-system-packages'] if IS_LINUX else []

def Run (cmd, **kwargs):
	shell = isinstance(cmd, str)
	cwd = kwargs.pop('cwd', _thisDir)
	return subprocess.run(cmd, shell=shell, cwd=cwd, **kwargs)

def PipInstall (*packages):
	for pkg in packages:
		Run ([sys.executable, '-m', 'pip', 'install', pkg] + PIP_EXTRA_ARGS)

# Clone repos
for repo in ('tinifyjs', 'PyRapier2d', 'blender-curve-to-svg'):
	if not os.path.isdir(os.path.join(_thisDir, repo)):
		Run (f'git clone https://github.com/OpenSourceJesus/{repo} --depth=1')

# Exaloop/codon (bash installer)
if IS_WINDOWS:
	# Try Git Bash or WSL bash
	for bash in ('bash', r'C:\Program Files\Git\bin\bash.exe'):
		proc = Run(f'"{bash}" -c "curl -fsSL https://exaloop.io/install.sh | bash"')
		if proc.returncode == 0:
			break
else:
	Run ('/bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"')

PipInstall ('pygame', 'maturin', 'codon-jit')

# Build tools: patchelf (Linux only), Rust (all platforms)
if IS_LINUX:
	# Suppress "command not found" only for package managers we don't use
	Run ('(sudo apt update && sudo apt install -y patchelf) 2>/dev/null || true')
	Run ('(sudo dnf install -y patchelf) 2>/dev/null || true')
	Run ('(sudo pacman -Syu --noconfirm patchelf) 2>/dev/null || true')
	# Install Rust without hiding stderr: sudo often needs a password (script has no TTY)
	Run ('(sudo apt install -y rustc) 2>/dev/null || true')
	Run ('(sudo dnf install -y rustc) 2>/dev/null || true')
	Run ('(sudo pacman -Syu --noconfirm rust) || true')  # show errors so user sees "password required" etc.
elif IS_MACOS:
	Run ('brew install rust 2>/dev/null || true')
# Windows: Rust typically via rustup (user install) or winget; skip if not present

# Build PyRapier2d (ensure cargo is on PATH: rustup ~/.cargo/bin, or system /usr/bin)
buildEnv = os.environ.copy()
cargoPaths = [os.path.expanduser('~/.cargo/bin'), '/usr/bin', '/usr/local/bin'] if not IS_WINDOWS else [os.path.expandvars(r'%USERPROFILE%\.cargo\bin')]
prepend = os.pathsep.join(p for p in cargoPaths if p and os.path.isdir(p))
if prepend:
	buildEnv['PATH'] = prepend + os.pathsep + buildEnv.get('PATH', '')
# Allow building on Python newer than PyO3's declared max (e.g. 3.14) via stable ABI
buildEnv['PYO3_USE_ABI3_FORWARD_COMPATIBILITY'] = '1'

def CargoInPath (env):
	for d in env.get('PATH', '').split(os.pathsep):
		if d and os.path.isfile(os.path.join(d, 'cargo')):
			return True
	return False
if not CargoInPath(buildEnv):
	print('Cargo not found. Install Rust, then re-run this script.')
	if IS_LINUX:
		print('  Garuda/Arch: sudo pacman -Syu rust')
		print('  Debian/Ubuntu: sudo apt install rustc')
		print('  Fedora: sudo dnf install rustc')
		print('  Or: https://rustup.rs')
	elif IS_MACOS:
		print('  brew install rust')
		print('  Or: https://rustup.rs')
	elif IS_WINDOWS:
		print('  Run the rustup installer: https://rustup.rs')
		print('  Or: winget install Rustlang.Rustup')
	else:
		print('  https://rustup.rs')
	sys.exit(1)

wheelsPath = os.path.join(_thisDir, 'PyRapier2d', 'target', 'wheels')
Run ([sys.executable, '-m', 'maturin', 'build', '--release'], cwd=os.path.join(_thisDir, 'PyRapier2d'), env=buildEnv)

if os.path.isdir(wheelsPath):
	files = os.listdir(wheelsPath)
	if files:
		wheel = os.path.join('PyRapier2d', 'target', 'wheels', files[0])
		Run ([sys.executable, '-m', 'pip', 'install', wheel] + PIP_EXTRA_ARGS)

# npm and rapydscript-ng (npm comes with Node.js)
if IS_LINUX:
	Run ('(sudo apt update && sudo apt install -y nodejs npm) 2>/dev/null || true')
	Run ('(sudo dnf install -y nodejs npm) 2>/dev/null || true')
	Run ('(sudo pacman -Syu --noconfirm nodejs npm) 2>/dev/null || true')
elif IS_MACOS:
	Run ('brew install node 2>/dev/null || true')
elif IS_WINDOWS:
	Run ('winget install OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements 2>nul || true')
npmEnv = os.environ.copy()
nodePaths = [os.path.expanduser('~/.local/bin'), '/usr/bin', '/usr/local/bin'] if not IS_WINDOWS else [os.path.expandvars(r'%APPDATA%\npm'), os.path.expandvars(r'%ProgramFiles%\nodejs')]
prependNpm = os.pathsep.join(p for p in nodePaths if p and os.path.isdir(p))
if prependNpm:
	npmEnv['PATH'] = prependNpm + os.pathsep + npmEnv.get('PATH', '')
def NpmInPath (env):
	for d in env.get('PATH', '').split(os.pathsep):
		if d and (os.path.isfile(os.path.join(d, 'npm')) or os.path.isfile(os.path.join(d, 'npm.cmd'))):
			return True
	return False
if NpmInPath(npmEnv):
	Run ('npm install -g rapydscript-ng', env=npmEnv)
else:
	print('npm not found. Install Node.js (includes npm), then re-run this script.')
	if IS_LINUX:
		print('  Garuda/Arch: sudo pacman -S nodejs npm')
		print('  Debian/Ubuntu: sudo apt install nodejs npm')
		print('  Fedora: sudo dnf install nodejs npm')
	elif IS_MACOS:
		print('  brew install node')
	elif IS_WINDOWS:
		print('  winget install OpenJS.NodeJS.LTS')
		print('  Or: https://nodejs.org')
	else:
		print('  https://nodejs.org')
	sys.exit(1)

import tinifyjs.Install