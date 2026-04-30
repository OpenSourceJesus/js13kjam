"""Shared neo-geo path repair: symlink without spaces + rewrite embedded bootstrap paths."""

import os
import sys


def posix_path(path):
	try:
		return os.path.normpath(str(path)).replace('\\', '/')
	except Exception:
		return str(path).replace('\\', '/')


def ensure_no_space_prefix_link(repo_root, real_local_abs, is_windows = None):
	is_windows_env = sys.platform == 'win32' if is_windows is None else bool(is_windows)
	if is_windows_env:
		return os.path.abspath(real_local_abs)
	real_abs = os.path.abspath(real_local_abs)
	link_abs = os.path.abspath(os.path.join(repo_root, '.js13k_ngdevkit_local'))
	try:
		if os.path.lexists(link_abs):
			try:
				if os.path.isdir(link_abs) and (not os.path.islink(link_abs)):
					print('WARN: cannot create neo-geo prefix symlink', link_abs + ': exists and is not a symlink')
					return real_abs
				os.unlink(link_abs)
			except OSError as err:
				print('WARN: could not refresh neo-geo prefix symlink:', err)
				return real_abs
		os.symlink(real_abs, link_abs, target_is_directory=True)
	except OSError as err:
		print('WARN: could not create neo-geo prefix symlink:', err)
		return real_abs
	return link_abs


def rewrite_installed_prefix_texts(installed_root_abs, needles, new_prefix_posix):
	installed_root_abs = os.path.abspath(str(installed_root_abs or '').strip())
	new_prefix_posix = str(new_prefix_posix or '').strip().rstrip('/')
	if installed_root_abs == '' or new_prefix_posix == '':
		return False
	uniq_needles = []
	seen_needle = set()
	for n in needles:
		px = posix_path(n).strip().rstrip('/')
		if px == '' or px in seen_needle:
			continue
		if px != new_prefix_posix.rstrip('/'):
			uniq_needles.append(px)
			seen_needle.add(px)
	uniq_needles.sort(key=lambda s: (-len(str(s)), str(s)))
	changed_any = False
	for root_dir, _, files in os.walk(installed_root_abs):
		for name in files:
			path_abs = os.path.join(root_dir, name)
			try:
				bsz = os.path.getsize(path_abs)
			except OSError:
				continue
			if bsz <= 0 or bsz > 12 * 1024 * 1024:
				continue
			try:
				with open(path_abs, 'rb') as bf:
					chunk = bf.read(8192)
			except Exception:
				continue
			if b'\0' in chunk:
				continue
			try:
				with open(path_abs, 'r', encoding='utf-8') as mf:
					txt = mf.read()
			except UnicodeDecodeError:
				continue
			prev = txt
			for needle in uniq_needles:
				if needle == '':
					continue
				txt = txt.replace('file:///' + needle, 'file:///' + new_prefix_posix)
				txt = txt.replace('file:/' + needle, 'file:/' + new_prefix_posix)
				txt = txt.replace(needle.replace('/', '\\'), new_prefix_posix.replace('/', '\\'))
				txt = txt.replace(needle, new_prefix_posix)
			if txt != prev:
				try:
					with open(path_abs, 'w', encoding='utf-8') as mf:
						mf.write(txt)
					changed_any = True
				except Exception:
					pass
	return changed_any


def finalize_installed_toolchain_roots(repo_root, ngdevkit_dir, bootstrap_local_dir=None, is_windows=None):
	is_windows_env = sys.platform == 'win32' if is_windows is None else bool(is_windows)
	local_prefix = os.path.join(ngdevkit_dir, 'local')
	real_local_abs = os.path.abspath(local_prefix)
	if not os.path.isdir(real_local_abs):
		print('WARN: neo-geo local prefix missing:', real_local_abs)
		return real_local_abs
	safe_abs = ensure_no_space_prefix_link(repo_root, real_local_abs, is_windows=is_windows_env)
	safe_px = posix_path(safe_abs)
	needle_list = [
		posix_path('/tmp/js13k_ngdevkit_bootstrap/ngdevkit/local'),
	]
	if bootstrap_local_dir:
		bl = os.path.abspath(bootstrap_local_dir)
		bp = posix_path(bl).rstrip('/')
		if bp != '' and bp not in needle_list:
			needle_list.append(bp)
	rl_px = posix_path(real_local_abs).rstrip('/')
	if rl_px != '' and rl_px != safe_px.rstrip('/') and rl_px not in needle_list:
		needle_list.append(rl_px)
	pc_root_src = os.path.join(ngdevkit_dir, 'ngdevkit.pc')
	if rewrite_installed_prefix_texts(real_local_abs, needle_list, safe_px):
		print('Neo Geo: rewrote toolchain path references under:', real_local_abs)
	if os.path.isfile(pc_root_src):
		try:
			with open(pc_root_src, 'r', encoding='utf-8') as f:
				pr = f.read()
			prev_pc = pr
			for needle in needle_list:
				nx = str(needle or '').strip().rstrip('/')
				if nx == '':
					continue
				pr = pr.replace(nx, safe_px.rstrip('/'))
				pr = pr.replace(nx.replace('/', '\\'), safe_px.replace('/', '\\'))
			if pr != prev_pc:
				with open(pc_root_src, 'w', encoding='utf-8') as f:
					f.write(pr)
				print('Neo Geo: rewrote:', pc_root_src)
		except Exception as err:
			print('WARN: failed to rewrite', pc_root_src + ':', err)
	return safe_abs
