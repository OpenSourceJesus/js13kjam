import os

if not os.path.isdir('blender-curve-to-svg'):
	os.system('git clone https://github.com/OpenSourceJesus/blender-curve-to-svg --depth=1')
if not os.path.isdir('tinifyjs'):
	os.system('git clone https://github.com/OpenSourceJesus/tinifyjs --depth=1')
os.system('''/bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"
pip install pygame
pip install pygame --break-system-packages
sudo apt update
sudo apt install patchelf
sudo dnf install patchelf''')
import tinifyjs.Install