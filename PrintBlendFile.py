import sys, base64

for arg in sys.argv:
	if arg.endswith('.blend'):
		with open(arg, 'rb') as blendFile:
			print(arg, 'contents:\n' + base64.b64encode(blendFile.read()).decode('utf-8'))