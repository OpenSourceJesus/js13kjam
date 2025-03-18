import os

if not os.path.isdir('blender-curve-to-svg'):
	os.system('git clone https://github.com/OpenSourceJesus/blender-curve-to-svg.git --depth=1')
if not os.path.isdir('tinifyjs'):
	os.system('git clone https://github.com/OpenSourceJesus/tinifyjs.git --depth=1')
import tinifyjs.Install