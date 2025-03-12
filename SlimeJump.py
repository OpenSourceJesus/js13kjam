from Main import *

def Lerp (min, max, t):
	return min + t * (max - min)

def InvLerp (from_, to, n):
	return (n - from_) / (to - from_)

def Remap (inFrom, inTo, outFrom, outTo, n):
	t = InvLerp(inFrom, inTo, n)
	return Lerp(outFrom, outTo, t)

def GenLevel ():
	bytes = open('/tmp/js13kjam API.js', 'rb').read()
	obCount = 70
	wallPos = [999, 0]
	initOffY = 500
	lightPos = [-999, initOffY]
	for i in range(0, len(bytes), 9):
		wallX = bytes[i]
		wallY = bytes[i + 1]
		lightX = bytes[i + 2]
		lightY = bytes[i + 3]
		r = bytes[i + 4]
		g = bytes[i + 5]
		b = bytes[i + 6]
		mixMode = bytes[i + 7]
		byte = bytes[i + 8]
		wallOff = [180, 0]
		if wallPos[0] > 5678 and byte == 32:
			wallOff = [Remap(0, 255, 180, 900, wallX), Remap(255, 0, -500, 500, wallY)]
			if abs(wallOff[1]) < 20:
				wallOff[1] = 0
		wallPos[0] += wallOff[0]
		wallPos[1] += wallOff[1]
		lightOff = [Remap(0, 255, 300, 900, lightX), Remap(255, 0, -300, 300, lightY)]
		lightPos[0] += lightOff[0]
		lightPos[1] += lightOff[1]
		off_ = wallPos[1] + initOffY - lightPos[1]
		if abs(off_) > 400:
			lightPos[1] += off_
		if mixMode < 128:
			print(mixMode)
		light = Copy(bpy.data.objects['Light'])
		light.name += '_Clone'
		light.location.x = lightPos[0]
		light.location.y = lightPos[1]
		wall = Copy(bpy.data.objects['Wall'], False)
		wall.hide_set(False)
		for child in wall.children:
			child.hide_set(False)
		wall.name += '_Clone'
		wall.location.x = wallPos[0]
		wall.location.y = wallPos[1]
		obCount -= 1
		if obCount == 0:
			return