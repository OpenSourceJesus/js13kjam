import os

_thisDir = os.path.split(os.path.abspath(__file__))[0]
if not os.path.isdir('blender-curve-to-svg'):
	os.system('git clone https://github.com/OpenSourceJesus/blender-curve-to-svg --depth=1')
if not os.path.isdir('tinifyjs'):
	os.system('git clone https://github.com/OpenSourceJesus/tinifyjs --depth=1')
if not os.path.isdir('PyRapier2d'):
	os.system('git clone https://github.com/OpenSourceJesus/PyRapier2d --depth=1')
os.system('''/bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"
pip install codon-jit
pip install codon-jit --break-system-packages
pip install maturin
pip install maturin --break-system-packages
pip install pygame
pip install pygame --break-system-packages
sudo apt update
sudo apt install patchelf
sudo dnf install patchelf
sudo apt install rustc
sudo apt install cargo
cd PyRapier2d
maturin build --release''')
filesAndDirs = os.listdir(_thisDir + '/PyRapier2d/target/wheels')
os.system('pip install PyRapier2d/target/wheels/' + filesAndDirs[0] + '\npip install PyRapier2d/target/wheels/' + filesAndDirs[0] + ' --break-system-packages')
import tinifyjs.Install