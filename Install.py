import os

if not os.path.isdir('blender-curve-to-svg'):
	os.system('git clone https://github.com/OpenSourceJesus/blender-curve-to-svg.git --depth=1')