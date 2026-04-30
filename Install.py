import os, re, sys, shutil, tempfile, platform, subprocess
from ngdevkit_prefix_fixup import finalize_installed_toolchain_roots as _NeoGeoFinalizeInstallPrefix

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

def IsLikelyPlaceholderPy2GbBackend (repo_dir):
	"""Detect known placeholder py2gb/py2gba CLI backends."""
	main_candidates = (
		os.path.join(repo_dir, 'py2gb', '__main__.py'),
		os.path.join(repo_dir, 'py2gba', '__main__.py'),
	)
	for p in main_candidates:
		if not os.path.isfile(p):
			continue
		try:
			src = open(p, 'r', encoding = 'utf-8').read()
		except Exception:
			continue
		txt = str(src)
		if (
			('lightweight backend' in txt)
			or ('placeholder assembly' in txt)
			or ('does not emit pygame ABI bridge stubs' in txt)
		):
			return True
	return False

def RewriteToolchainDownloadUrls (toolchain_dir):
	if not os.path.isdir(toolchain_dir):
		return
	replacements = [
		('ftp://ftp.gnu.org/', 'https://ftpmirror.gnu.org/'),
		('http://ftp.gnu.org/', 'https://ftpmirror.gnu.org/'),
		('ftp://ftp.gnu.org', 'https://ftpmirror.gnu.org'),
		('http://ftp.gnu.org', 'https://ftpmirror.gnu.org'),
		('ftp://sourceware.org/', 'https://sourceware.org/'),
		('http://sourceware.org/', 'https://sourceware.org/'),
		('ftp://sourceware.org', 'https://sourceware.org'),
		('http://sourceware.org', 'https://sourceware.org'),
	]
	for root, _dirs, files in os.walk(toolchain_dir):
		for name in files:
			path = os.path.join(root, name)
			try:
				txt = open(path, 'r', encoding = 'utf-8').read()
			except Exception:
				continue
			prev = txt
			for a, b in replacements:
				txt = txt.replace(a, b)
			txt = re.sub(r'ftp://([A-Za-z0-9._:-]+)', r'https://\1', txt)
			if txt != prev:
				try:
					open(path, 'w', encoding = 'utf-8').write(txt)
				except Exception:
					pass

def EnsureNgdevkitLocalToolchain (ngdevkit_dir):
	local_prefix = os.path.join(ngdevkit_dir, 'local')
	pc_candidates = (
		os.path.join(local_prefix, 'share', 'pkgconfig', 'ngdevkit.pc'),
		os.path.join(local_prefix, 'lib', 'pkgconfig', 'ngdevkit.pc'),
	)
	if any(os.path.isfile(p) for p in pc_candidates):
		print('Neo Geo local toolchain already bootstrapped at:', local_prefix)
		_NeoGeoFinalizeInstallPrefix(_thisDir, ngdevkit_dir, None, IS_WINDOWS)
		return True
	if not os.path.isdir(ngdevkit_dir):
		print('ERROR: ngdevkit source tree missing:', ngdevkit_dir)
		return False
	# Build in a temp directory without spaces; ngdevkit makefiles are fragile with spaced paths.
	bootstrap_root = os.path.join(tempfile.gettempdir(), 'js13k_ngdevkit_bootstrap')
	bootstrap_src = os.path.join(bootstrap_root, 'ngdevkit')
	try:
		os.makedirs(bootstrap_root, exist_ok = True)
		if os.path.isdir(bootstrap_src):
			shutil.rmtree(bootstrap_src)
		shutil.copytree(ngdevkit_dir, bootstrap_src)
	except Exception as err:
		print('ERROR: failed to stage ngdevkit bootstrap source:', err)
		return False
	RewriteToolchainDownloadUrls(os.path.join(bootstrap_src, 'toolchain'))
	configure_cmd = 'autoreconf -iv && ./configure --prefix="$PWD/local" --enable-external-emudbg --enable-external-gngeo --disable-examples'
	if Run(configure_cmd, cwd = bootstrap_src).returncode != 0:
		print('ERROR: ngdevkit configure failed.')
		return False
	if Run('make download-toolchain', cwd = bootstrap_src).returncode != 0:
		print('ERROR: ngdevkit toolchain download failed.')
		return False
	if Run('make build-tools install-tools install-pkgconfig', cwd = bootstrap_src).returncode != 0:
		print('ERROR: ngdevkit local bootstrap failed.')
		return False
	try:
		built_local = os.path.join(bootstrap_src, 'local')
		if not os.path.isdir(built_local):
			print('ERROR: ngdevkit bootstrap did not produce local prefix:', built_local)
			return False
		if os.path.isdir(local_prefix):
			shutil.rmtree(local_prefix)
		shutil.copytree(built_local, local_prefix)
	except Exception as err:
		print('ERROR: failed to copy local ngdevkit prefix into project:', err)
		return False
	print('Neo Geo local toolchain bootstrapped at:', local_prefix)
	_NeoGeoFinalizeInstallPrefix(_thisDir, ngdevkit_dir, os.path.join(bootstrap_src, 'local'), IS_WINDOWS)
	return True

def RefreshNgdevkitExamplesConfigMk (examples_dir, make_prefix_abs):
	"""Write ngdevkit-examples/config.mk pointing at repo ngdevkit (avoids stale /tmp bootstrap paths)."""
	if not os.path.isdir(examples_dir):
		print('ERROR: ngdevkit-examples directory missing:', examples_dir)
		return False
	make_prefix_abs = os.path.abspath(str(make_prefix_abs or '').strip())
	if make_prefix_abs == '' or (not os.path.isdir(make_prefix_abs)):
		print('ERROR: invalid neo-geo toolchain prefix:', make_prefix_abs)
		return False
	local_prefix = make_prefix_abs
	pc_lib = os.path.join(local_prefix, 'lib', 'pkgconfig')
	pc_share = os.path.join(local_prefix, 'share', 'pkgconfig')
	env = os.environ.copy()
	pc_parts = [p for p in (pc_lib, pc_share) if os.path.isdir(p)]
	old_pc = str(env.get('PKG_CONFIG_PATH', '') or '').strip()
	if old_pc != '':
		pc_parts.append(old_pc)
	env['PKG_CONFIG_PATH'] = os.pathsep.join(pc_parts)
	path_parts = []
	local_bin = os.path.join(local_prefix, 'bin')
	if os.path.isdir(local_bin):
		path_parts.append(local_bin)
	for bindir in ('/usr/local/bin', '/usr/bin', '/bin'):
		if os.path.isdir(bindir):
			path_parts.append(bindir)
			break
	old_path = str(env.get('PATH', '') or '').strip()
	if old_path != '':
		path_parts.append(old_path)
	env['PATH'] = os.pathsep.join(path_parts)
	proc = Run('autoreconf -iv && ./configure', cwd = examples_dir, env = env)
	if proc.returncode != 0:
		print('ERROR: ngdevkit-examples autoreconf/configure failed.')
		return False
	cfg_mk = os.path.join(examples_dir, 'config.mk')
	if not os.path.isfile(cfg_mk):
		print('ERROR: ngdevkit-examples did not produce config.mk')
		return False
	print('Neo Geo ngdevkit-examples config.mk regenerated for toolchain prefix:', make_prefix_abs)
	return True

# Clone repos
for repo in ('Py2Js', 'tinifyjs', 'PyRapier2d', 'blender-curve-to-svg'):
	if not os.path.isdir(os.path.join(_thisDir, repo)):
		Run (f'git clone https://github.com/OpenSourceJesus/{repo} --depth=1')

# Py2Gb source can be overridden when you have a real transpiler backend.
py2gbRepoUrl = str(os.environ.get('JS13K_PY2GB_REPO', 'https://github.com/OpenSourceJesus/Py2Gb') or 'https://github.com/OpenSourceJesus/Py2Gb').strip()
py2gbRef = str(os.environ.get('JS13K_PY2GB_REF', '') or '').strip()
py2gbDir = os.path.join(_thisDir, 'Py2Gb')
if not os.path.isdir(py2gbDir):
	Run (f'git clone "{py2gbRepoUrl}" "{py2gbDir}" --depth=1')
if py2gbRef != '':
	Run (f'git -C "{py2gbDir}" fetch --depth=1 origin "{py2gbRef}" && git -C "{py2gbDir}" checkout FETCH_HEAD')

# Vendor ZGB locally for GBC C export integration.
thirdPartyDir = os.path.join(_thisDir, 'Third Party')
zgbDir = os.path.join(thirdPartyDir, 'ZGB')
if not os.path.isdir(thirdPartyDir):
	os.makedirs(thirdPartyDir, exist_ok = True)
if not os.path.isdir(zgbDir):
	Run (f'git clone https://github.com/Zal0/ZGB.git "{zgbDir}" --depth=1')

# Vendor a pre-existing Neo Geo C toolchain source tree.
ngdevkitRepoUrl = str(os.environ.get('JS13K_NEOGEO_TOOLCHAIN_REPO', 'https://github.com/dciabrin/ngdevkit') or 'https://github.com/dciabrin/ngdevkit').strip()
ngdevkitRef = str(os.environ.get('JS13K_NEOGEO_TOOLCHAIN_REF', '') or '').strip()
ngdevkitDir = os.path.join(thirdPartyDir, 'ngdevkit')
if not os.path.isdir(ngdevkitDir):
	Run (f'git clone "{ngdevkitRepoUrl}" "{ngdevkitDir}" --depth=1')
if ngdevkitRef != '':
	Run (f'git -C "{ngdevkitDir}" fetch --depth=1 origin "{ngdevkitRef}" && git -C "{ngdevkitDir}" checkout FETCH_HEAD')
if not EnsureNgdevkitLocalToolchain(ngdevkitDir):
	sys.exit(1)

# Optional ngdevkit examples (reference projects/build scripts).
ngdevkitExamplesRepoUrl = str(os.environ.get('JS13K_NEOGEO_EXAMPLES_REPO', 'https://github.com/dciabrin/ngdevkit-examples') or 'https://github.com/dciabrin/ngdevkit-examples').strip()
ngdevkitExamplesRef = str(os.environ.get('JS13K_NEOGEO_EXAMPLES_REF', '') or '').strip()
ngdevkitExamplesDir = os.path.join(thirdPartyDir, 'ngdevkit-examples')
if not os.path.isdir(ngdevkitExamplesDir):
	Run (f'git clone "{ngdevkitExamplesRepoUrl}" "{ngdevkitExamplesDir}" --depth=1')
if ngdevkitExamplesRef != '':
	Run (f'git -C "{ngdevkitExamplesDir}" fetch --depth=1 origin "{ngdevkitExamplesRef}" && git -C "{ngdevkitExamplesDir}" checkout FETCH_HEAD')
_examples_make_prefix = _NeoGeoFinalizeInstallPrefix(_thisDir, ngdevkitDir, None, IS_WINDOWS)
if not RefreshNgdevkitExamplesConfigMk(ngdevkitExamplesDir, _examples_make_prefix):
	sys.exit(1)

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

# Build tools: patchelf (Linux only), Rust (all platforms); emulators used by Main.py previews
if IS_LINUX:
	# Suppress "command not found" only for package managers we don't use
	Run ('(sudo apt update && sudo apt install -y patchelf) 2>/dev/null || true')
	Run ('(sudo dnf install -y patchelf) 2>/dev/null || true')
	Run ('(sudo pacman -S --noconfirm patchelf) 2>/dev/null || true')
	Run ('(sudo apt install -y mgba-qt) 2>/dev/null || true')
	Run ('(sudo dnf install -y mgba-qt) 2>/dev/null || true')
	Run ('(sudo pacman -S --noconfirm mgba-qt) 2>/dev/null || true')
	# Neo Geo export launcher tries FinalBurn Neo first, then MAME.
	Run ('(sudo apt install -y fbneo mame) 2>/dev/null || true')
	Run ('(sudo apt install -y finalburnneo) 2>/dev/null || true')
	Run ('(sudo dnf install -y fbneo mame) 2>/dev/null || true')
	Run ('(sudo dnf install -y finalburnneo) 2>/dev/null || true')
	Run ('(sudo pacman -S --noconfirm fbneo mame) 2>/dev/null || true')
	Run ('(sudo pacman -S --noconfirm finalburn-neo) 2>/dev/null || true')
	Run ('(yay -S --noconfirm ngdevkit ngdevkit-gngeo) 2>/dev/null || true')
	Run ('(paru -S --noconfirm ngdevkit ngdevkit-gngeo) 2>/dev/null || true')
	# Neo Geo SDK/toolchain packages (where available).
	Run ('(sudo add-apt-repository -y ppa:dciabrin/ngdevkit && sudo apt update && sudo apt install -y ngdevkit ngdevkit-gngeo) 2>/dev/null || true')
	Run ('(sudo dnf copr enable -y dciabrin/ngdevkit && sudo dnf install -y ngdevkit ngdevkit-gngeo) 2>/dev/null || true')
	# Install Rust without hiding stderr: sudo often needs a password (script has no TTY)
	Run ('(sudo apt install -y rustc) 2>/dev/null || true')
	Run ('(sudo dnf install -y rustc) 2>/dev/null || true')
	Run ('(sudo pacman -S --noconfirm rust) || true')  # show errors so user sees "password required" etc.
elif IS_MACOS:
	Run ('brew install rust mgba mame 2>/dev/null || true')
	Run ('brew install --cask finalburn-neo 2>/dev/null || true')
	Run ('brew tap dciabrin/ngdevkit 2>/dev/null || true')
	Run ('brew install ngdevkit ngdevkit-gngeo 2>/dev/null || true')
elif IS_WINDOWS:
	# mGBA installer; Rust is usually from rustup — see CargoInPath message below
	Run ('winget install -e --id mGBA.mGBA --accept-package-agreements --accept-source-agreements 2>nul || ver>nul')
	# Neo Geo emulator fallbacks used by Main.py launch path.
	Run ('winget install -e --id MAME.MAME --accept-package-agreements --accept-source-agreements 2>nul || ver>nul')
	Run ('winget install -e --id FinalBurnNeo.FinalBurnNeo --accept-package-agreements --accept-source-agreements 2>nul || ver>nul')

print('Neo Geo toolchain sources vendored at:', ngdevkitDir)
print('Neo Geo examples vendored at:', ngdevkitExamplesDir)
print('Use JS13K_NEOGEO_C_TOOLCHAIN_CMD to point Main.py at your build command.')

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
		print('  Garuda/Arch: sudo pacman -S rust')
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

# Py2Js (Python to JavaScript translator)
py2jsDir = os.path.join(_thisDir, 'Py2Js')
if os.path.isdir(py2jsDir):
	Run ([sys.executable, '-m', 'pip', 'install', '-e', py2jsDir] + PIP_EXTRA_ARGS)
else:
	print('Py2Js repo not found. Run: git clone https://github.com/OpenSourceJesus/Py2Js --depth=1')
	sys.exit(1)

# Py2Gb (Python to GBA/GB-family transpiler backend)
if os.path.isdir(py2gbDir):
	Run ([sys.executable, '-m', 'pip', 'install', '-e', py2gbDir] + PIP_EXTRA_ARGS)
	if IsLikelyPlaceholderPy2GbBackend(py2gbDir):
		print('ERROR: Installed Py2Gb backend appears to be placeholder/no-op.')
		print('Provide a real backend repository and re-run Install.py:')
		print('  JS13K_PY2GB_REPO=<git-url> JS13K_PY2GB_REF=<branch-or-tag> python Install.py')
		print('Current backend source:', py2gbRepoUrl)
		sys.exit(2)
else:
	print('Py2Gb repo not found. Set JS13K_PY2GB_REPO or clone into ./Py2Gb.')
	sys.exit(1)

import tinifyjs.Install