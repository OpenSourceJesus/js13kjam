import os, sys, shutil, sysconfig, argparse, subprocess
from pathlib import Path

def StringToBool (v):
	if isinstance(v, bool):
		return v
	if v.lower() in ('yes', 'true', 't', 'y', '1'):
		return True
	elif v.lower() in ('no', 'false', 'f', 'n', '0'):
		return False
	else:
		raise argparse.ArgumentTypeError('Boolean value expected.')

parser = argparse.ArgumentParser(
	description = "A robust compiler for Codon projects.",
	formatter_class = argparse.RawTextHelpFormatter
)
parser.add_argument(
	"scriptPath",
	type = Path,
	help = "Path to the Python script to compile."
)
parser.add_argument(
	"exePath",
	type = Path,
	help = "Path to the output executable."
)
parser.add_argument(
	"debug",
	type = StringToBool,
	help = "Use debug mode."
)
args = parser.parse_args()
scriptPath : Path = args.scriptPath
exePath : Path = args.exePath
debug : bool = args.debug
if not scriptPath.is_file():
	print(f"❌ Error: File not found at '{scriptPath}'")
	sys.exit(1)
if not all(shutil.which(cmd) for cmd in ["codon", "patchelf"]):
	print("❌ Error: Missing dependencies.")
	if not shutil.which("codon"):
		print("  - 'codon' command not found. Please ensure Codon is installed and in your PATH.")
	if not shutil.which("patchelf"):
		print("  - 'patchelf' command not found. Please install it.")
		print("    (e.g., 'sudo apt install patchelf' on Debian/Ubuntu)")
	sys.exit(1)
print(f"🚀 Starting Codon compilation for '{scriptPath}'")
print(f"   Output executable will be named '{exePath}'")
print("\n[1/4] Finding required library paths...")
try:
	python_lib_dir = Path(sysconfig.get_config_var('LIBDIR'))
	python_lib_soname = sysconfig.get_config_var('LDLIBRARY')
	codon_lib_dir = Path.home() / ".codon" / "lib" / "codon"
	if not all([python_lib_dir.is_dir(), codon_lib_dir.is_dir(), python_lib_soname]):
		raise ValueError("One or more library paths could not be determined.")
	print(f"  ✅ Python library directory: {python_lib_dir}")
	print(f"  ✅ Codon runtime directory: {codon_lib_dir}")
except (TypeError, ValueError) as e:
	print(f"❌ Error: Could not determine required library paths. {e}")
	sys.exit(1)
print("\n[2/4] Checking for 'libpython.so' symbolic link...")
genericSymlink = python_lib_dir / "libpython.so"
if not genericSymlink.exists():
	print("  ⚠️ WARNING: Generic 'libpython.so' symlink not found.")
	print("     Codon requires this to dynamically load the Python runtime.")
	print("\n     This script needs to create it by running the following command:")
	print(f"     > sudo ln -s {python_lib_soname} {genericSymlink}")
	try:
		response = input("\n     Do you want to authorize this command? (y/N) ")
		if response.lower() not in ['y', 'yes']:
			print("🚫 Aborting compilation due to missing link.")
			sys.exit(1)
		cmd = ["sudo", "ln", "-s", python_lib_soname, "libpython.so"]
		subprocess.run(cmd, cwd = python_lib_dir, check = True)
		print("  ✅ Symbolic link created successfully.")
	except (subprocess.CalledProcessError, FileNotFoundError) as e:
		print(f"\n❌ Error creating symbolic link: {e}")
		print("   Please try running the command manually.")
		sys.exit(1)
	except KeyboardInterrupt:
		print("\n🚫 Operation cancelled by user.")
		sys.exit(1)
else:
	print("  ✅ 'libpython.so' already exists. No action needed.")
print(f"\n[3/4] Compiling '{scriptPath}' with Codon...")
try:
	cmd = [
		"codon", "build", "-exe",
		"-o", exePath, str(scriptPath)
	]
	if debug:
		cmd += ['-debug']
	else:
		cmd += ['-release']
	subprocess.run(cmd, check = True, capture_output = True)
	print("  ✅ Compilation finished successfully.")
except subprocess.CalledProcessError as e:
	print(f"❌ Error during Codon compilation:")
	print(e.stderr.decode())
	sys.exit(1)
print(f"\n[4/4] Patching '{exePath}' to find libraries at runtime...")
try:
	rPath = f"{codon_lib_dir}:{python_lib_dir}"
	cmd = ["patchelf", "--set-rpath", rPath, exePath]
	subprocess.run(cmd, check = True)
	print("  ✅ Executable patched successfully.")
except (subprocess.CalledProcessError, FileNotFoundError) as e:
	print(f"❌ Error patching executable: {e}")
	sys.exit(1)
print("\n✨ Process Complete! ✨")
print("\nYour self-contained executable is ready.")
print("You can now run your application with the command:")
print(f"  .{exePath}")