import os, base64

_thisDir = os.path.split(os.path.abspath(__file__))[0]

with open(os.path.join(_thisDir, 'Black Cat.blend'), 'rb') as blendFile:
	print(base64.b64encode(blendFile.read()).decode('utf-8'))