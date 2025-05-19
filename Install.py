import os

if not os.path.isdir('blender-curve-to-svg'):
	os.system('git clone https://github.com/OpenSourceJesus/blender-curve-to-svg --depth=1')
if not os.path.isdir('tinifyjs'):
	os.system('git clone https://github.com/OpenSourceJesus/tinifyjs --depth=1')
if not os.path.isdir('unity-yaml-parser'):
	os.system('git clone https://github.com/OpenSourceJesus/unity-yaml-parser --depth=1')
import tinifyjs.Install