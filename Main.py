import os, sys, json, string, atexit, webbrowser, subprocess, math
_thisDir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisDir)
EXTENSIONS_SCRIPTS_PATH = os.path.join(_thisDir, 'Extensions')
sys.path.append(EXTENSIONS_SCRIPTS_PATH)
from MathExtensions import *
from SystemExtensions import *

isLinux = False
POTRACE_PATH = 'potrace-1.16.'
UNITY_SCRIPTS_PATH = os.path.join(_thisDir, 'Unity Scripts')
DONT_MANGLE_INDCTR = '-no_mangle=['
NO_PHYSICS_IDCTR = '-no_physics'
if sys.platform == 'win32':
	TMP_DIR = os.path.expanduser('~\\AppData\\Local\\Temp')
	BLENDER = 'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe'
	POTRACE_PATH += 'win64\\potrace.exe'
else:
	TMP_DIR = '/tmp'
	if sys.platform == 'darwin':
		BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
		POTRACE_PATH += 'mac-x86_64/potrace'
	else:
		BLENDER = 'blender'
		POTRACE_PATH += 'linux-x86_64/potrace'
		isLinux = True
usePhysics = True
dontMangleArg = ''
for arg in sys.argv:
	if 'blender' in arg:
		BLENDER = arg
	elif arg.startswith(DONT_MANGLE_INDCTR):
		dontMangleArg = arg
	elif arg == NO_PHYSICS_IDCTR:
		usePhysics = False

try:
	import bpy, gpu
	from mathutils import *
	from gpu_extras.batch import batch_for_shader
except:
	bpy = None

if not bpy:
	cmd = [BLENDER]
	for arg in sys.argv:
		if arg.endswith('.blend'):
			cmd.append(arg)
	cmd += ['--python-exit-code', '1', '--python', __file__, '--python', os.path.join(_thisDir, 'blender-curve-to-svg', 'curve_to_svg.py')]
	exArgs = []
	for arg in sys.argv:
		if arg.startswith('--') or arg.startswith(DONT_MANGLE_INDCTR) or arg == '-minify':
			exArgs.append(arg)
	if exArgs:
		cmd.append('--')
		cmd += exArgs
	print(' '.join(cmd))
	subprocess.check_call(cmd)
	sys.exit()

if not bpy:
	if isLinux:
		if not os.path.isfile('/usr/bin/blender'):
			print('Did you install blender 4.5?')
			print('snap install blender')
	else:
		print('Download blender 4.5 from: https://blender.org')
	sys.exit()

MAX_SCRIPTS_PER_OBJECT = 16

def GetScripts (ob, isAPI : bool):
	scripts = []
	type = 'runtime'
	if isAPI:
		type = 'api'
	for i in range(MAX_SCRIPTS_PER_OBJECT):
		if getattr(ob, type + 'Script%sDisable' %i):
			continue
		txt = getattr(ob, type + 'Script%s' %i)
		if txt:
			if isAPI:
				scripts.append(txt.as_string())
			else:
				scripts.append((txt.as_string(), getattr(ob, 'initScript%s' %i)))
	return scripts

def TryChangeToInt (f : float):
	if int(f) == f:
		return int(f)
	else:
		return f

def To2D (v : Vector):
	return Vector((v.x, v.y))

def Multiply (v : list, multiply : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt * multiply[i])
	return output

def Subtract (v : list, subtract : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt - subtract[i])
	return output

def Round (v : list):
	output = []
	for elmt in v:
		output.append(int(round(elmt)))
	return output

def ClampComponents (v : list, min : list, max : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(Clamp(elmt, min[i], max[i]))
	return output

def GetMinComponents (v : Vector, v2 : Vector, use2D : bool = False):
	if use2D:
		return Vector((min(v.x, v2.x), min(v.y, v2.y)))
	else:
		return Vector((min(v.x, v2.x), min(v.y, v2.y), min(v.z, v2.z)))

def GetMaxComponents (v : Vector, v2 : Vector, use2D : bool = False):
	if use2D:
		return Vector((max(v.x, v2.x), max(v.y, v2.y)))
	else:
		return Vector((max(v.x, v2.x), max(v.y, v2.y), max(v.z, v2.z)))

def GetRectMinMax (ob):
	bounds = [(ob.matrix_world @ Vector(corner)) for corner in ob.bound_box]
	minX = min(v.x for v in bounds)
	minY = min(v.y for v in bounds)
	maxX = max(v.x for v in bounds)
	maxY = max(v.y for v in bounds)
	_min = Vector((minX, minY))
	_max = Vector((maxX, maxY))
	return _min, _max

def IndexOfValue (o, d : dict):
	for i, value in enumerate(d.values()):
		if o == value:
			return i
	return -1

def Copy (ob, copyData = True, copyActions = True, collection = None):
	copy = ob.copy()
	if copyData:
		copy.data = copy.data.copy()
	if copyActions and copy.animation_data:
		copy.animation_data.action = copy.animation_data.action.copy()
	if not collection:
		collection = bpy.context.collection
	collection.objects.link(copy)
	for child in ob.children:
		childCopy = Copy(child, copyData, copyActions, collection)
		childCopy.parent = copy
	return copy

def ToByteString (n, delimeters = '\\`', escapeQuotes : bool = True):
	n = round(n)
	if n < 32:
		n = 32
	byteStr = chr(n)
	if byteStr in delimeters:
		byteStr = chr(n + 1)
	elif escapeQuotes and byteStr in '"' + "'":
		byteStr = '\\' + byteStr
	return byteStr

def GetColor (color : list):
	_color = ClampComponents(Round(Multiply(color, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
	idxOfColor = IndexOfValue(_color, colors)
	keyOfColor = ''
	if idxOfColor == -1:
		keyOfColor = string.ascii_letters[len(colors)]
		colors[keyOfColor] = _color
	else:
		keyOfColor = string.ascii_letters[idxOfColor]
	return keyOfColor

def GetObjectPosition (ob):
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	offX = world.exportOffsetX
	offY = world.exportOffsetY
	off = Vector((offX, offY))
	x, y, z = ob.location * SCALE
	if ob.type == 'LIGHT':
		radius = ob.data.shadow_soft_size
		x -= radius
		y -= radius
	else:
		y = -y
	x += offX
	y += offY
	return Round(Vector((x, y)))

def GetVarNameFromObject (ob):
	output = '_' + ob.name
	disallowedChars = '/\\`~?|!@#$%^&*()[]{}<>=+-;:",.' + "'"
	for disallowedChar in disallowedChars:
		output = output.replace(disallowedChar, '')
	return output

def ToVector2String (prop : bpy.props.FloatVectorProperty):
	return '{x : ' + str(prop[0]) + ', y : ' + str(-prop[1]) + '}'

DEFAULT_COLOR = [0, 0, 0, 0]
exportedObs = []
datas = []
colors = {}
rigidBodies = {}
colliders = {}
joints = {}
charControllers = {}
pathsDatas = []
initCode = []
updateCode = []
userJS = ''
svgsDatas = {}

def ExportObject (ob):
	global svgsDatas
	if ob.hide_get() or ob in exportedObs:
		return
	RegisterPhysics (ob)
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	offX = world.exportOffsetX
	offY = world.exportOffsetY
	off = Vector((offX, offY))
	sx, sy, sz = ob.scale * SCALE
	prevFrame = bpy.context.scene.frame_current
	if ob.type == 'LIGHT':
		radius = ob.data.shadow_soft_size
		pos = GetObjectPosition(ob)
		if HandleCopyObject(ob, pos):
			return
		data = []
		data.append(ob.name)
		data.append(int(pos[0]))
		data.append(int(pos[1]))
		data.append(int(round(ob.location.z)))
		data.append(int(round(radius * 2)))
		alpha = round(ob.color1Alpha * 255)
		color = Round(Multiply(ob.data.color, [255, 255, 255]))
		data.append(GetColor([color[0], color[1], color[2], alpha]))
		data.append(GetColor(ob.color2))
		data.append(GetColor(ob.color3))
		data.append(list(ob.colorPositions))
		data.append(ob.subtractive)
		datas.append(data)
	elif ob.type == 'CURVE':
		prevData = ob.data
		pathDataFrames = []
		prevPathData = ''
		posFrames = []
		data = []
		prevPos = None
		for frame in range(ob.minPosFrame, ob.maxPosFrame + 1):
			bpy.context.scene.frame_set(frame)
			depsgraph = bpy.context.evaluated_depsgraph_get()
			evaluatedOb = ob.evaluated_get(depsgraph)
			curveData = evaluatedOb.to_curve(depsgraph, apply_modifiers = True).copy()
			ob.data = curveData.copy()
			if frame > ob.minPosFrame:
				posFrames.append([TryChangeToInt(ob.location.x - prevPos.x), TryChangeToInt(ob.location.y - prevPos.y)])
			prevPos = ob.location
		for frame in range(ob.minPathFrame, ob.maxPathFrame + 1):
			bpy.context.scene.frame_set(frame)
			depsgraph = bpy.context.evaluated_depsgraph_get()
			evaluatedOb = ob.evaluated_get(depsgraph)
			curveData = evaluatedOb.to_curve(depsgraph, apply_modifiers = True).copy()
			ob.data = curveData.copy()
			bpy.ops.object.select_all(action = 'DESELECT')
			ob.select_set(True)
			bpy.ops.curve.export_svg()
			svgTxt = open(bpy.context.scene.export_svg_output, 'r').read()
			idxOfName = svgTxt.find('"' + ob.name + '"') + 1
			idxOfGroupStart = svgTxt.rfind('\n', 0, idxOfName)
			groupEndIndctr = '</g>'
			idxOfGroupEnd = svgTxt.find(groupEndIndctr, idxOfGroupStart) + len(groupEndIndctr)
			group = svgTxt[idxOfGroupStart : idxOfGroupEnd]
			parentGroupIndctr = '\n  <g'
			idxOfParentGroupStart = svgTxt.find(parentGroupIndctr)
			idxOfParentGroupContents = svgTxt.find('\n', idxOfParentGroupStart + len(parentGroupIndctr))
			idxOfParentGroupEnd = svgTxt.rfind('</g')
			min, max = GetRectMinMax(ob)
			scale = Vector((sx, sy))
			min *= scale
			min += off
			max *= scale
			max += off
			svgTxt = svgTxt[: idxOfParentGroupContents] + group + svgTxt[idxOfParentGroupEnd :]
			pathDataIndctr = ' d="'
			idxOfPathDataStart = svgTxt.find(pathDataIndctr) + len(pathDataIndctr)
			idxOfPathDataEnd = svgTxt.find('"', idxOfPathDataStart)
			pathData = svgTxt[idxOfPathDataStart : idxOfPathDataEnd]
			pathData = pathData.replace('.0', '')
			vectors = pathData.split(' ')
			pathData = []
			minPathVector = Vector((float('inf'), float('inf')))
			maxPathVector = Vector((-float('inf'), -float('inf')))
			for vector in vectors:
				if len(vector) == 1:
					continue
				components = vector.split(',')
				x = int(round(float(components[0])))
				y = int(round(float(components[1])))
				vector = ob.matrix_world @ Vector((x, y, 0))
				x = vector.x
				y = vector.y
				minPathVector = GetMinComponents(minPathVector, vector, True)
				maxPathVector = GetMaxComponents(maxPathVector, vector, True)
				pathData.append(x)
				pathData.append(y)
			offset = -minPathVector + Vector((32, 32))
			for i, pathValue in enumerate(pathData):
				if i % 2 == 1:
					pathData[i] = ToByteString((maxPathVector[1] - pathValue + minPathVector[1]) + offset[1])
				else:
					pathData[i] = ToByteString(pathValue + offset[0])
			strokeWidth = 0
			if ob.useStroke:
				strokeWidth = ob.strokeWidth
			jiggleDist = ob.jiggleDist * int(ob.useJiggle)
			x = min.x - strokeWidth / 2 - jiggleDist
			y = -max.y + strokeWidth / 2 + jiggleDist
			size = max - min
			size += Vector((1, 1)) * (strokeWidth + jiggleDist * 2)
			if ob.roundPosAndSize:
				x = int(round(x))
				y = int(round(y))
				size = Vector(Round(size))
			pathDataStr = ''.join(pathData)
			if frame == ob.minPathFrame:
				if HandleCopyObject(ob, [x, y]):
					return
				posFrames.insert(0, [TryChangeToInt(x), TryChangeToInt(y)])
				data.append(posFrames)
				data.append(ob.posPingPong)
				data.append(TryChangeToInt(size.x))
				data.append(TryChangeToInt(size.y))
				materialColor = DEFAULT_COLOR
				if len(ob.material_slots) > 0:
					materialColor = ob.material_slots[0].material.diffuse_color
				data.append(GetColor(materialColor))
				data.append(round(strokeWidth))
				data.append(GetColor(ob.strokeClr))
				data.append(ob.name)
				data.append(ob.data.splines[0].use_cyclic_u)
				data.append(round(ob.location.z))
				data.append(False)
				data.append(TryChangeToInt(ob.jiggleDist * int(ob.useJiggle)))
				data.append(TryChangeToInt(ob.jiggleDur))
				data.append(ob.jiggleFrames * int(ob.useJiggle))
				data.append(TryChangeToInt(ob.rotAngRange[0]))
				data.append(TryChangeToInt(ob.rotAngRange[1]))
				data.append(TryChangeToInt(ob.rotDur * int(ob.useRotate)))
				data.append(ob.rotPingPong)
				data.append(TryChangeToInt(ob.scaleXRange[0]))
				data.append(TryChangeToInt(ob.scaleXRange[1]))
				data.append(TryChangeToInt(ob.scaleYRange[0]))
				data.append(TryChangeToInt(ob.scaleYRange[1]))
				data.append(TryChangeToInt(ob.scaleDur * int(ob.useScale)))
				data.append(TryChangeToInt(ob.scaleHaltDurAtMin * int(ob.useScale)))
				data.append(TryChangeToInt(ob.scaleHaltDurAtMax * int(ob.useScale)))
				data.append(ob.scalePingPong)
				data.append(TryChangeToInt(ob.origin[0]))
				data.append(TryChangeToInt(ob.origin[1]))
				data.append(TryChangeToInt(ob.fillHatchDensity[0] * int(ob.useFillHatch[0])))
				data.append(TryChangeToInt(ob.fillHatchDensity[1] * int(ob.useFillHatch[1])))
				data.append(TryChangeToInt(ob.fillHatchRandDensity[0] / 100 * int(ob.useFillHatch[0])))
				data.append(TryChangeToInt(ob.fillHatchRandDensity[1] / 100 * int(ob.useFillHatch[1])))
				data.append(TryChangeToInt(ob.fillHatchAng[0] * int(ob.useFillHatch[0])))
				data.append(TryChangeToInt(ob.fillHatchAng[1] * int(ob.useFillHatch[1])))
				data.append(TryChangeToInt(ob.fillHatchWidth[0] * int(ob.useFillHatch[0])))
				data.append(TryChangeToInt(ob.fillHatchWidth[1] * int(ob.useFillHatch[1])))
				data.append(TryChangeToInt(ob.strokeHatchDensity[0] * int(ob.useStrokeHatch[0])))
				data.append(TryChangeToInt(ob.strokeHatchDensity[1] * int(ob.useStrokeHatch[1])))
				data.append(TryChangeToInt(ob.strokeHatchRandDensity[0] / 100 * int(ob.useStrokeHatch[0])))
				data.append(TryChangeToInt(ob.strokeHatchRandDensity[1] / 100 * int(ob.useStrokeHatch[1])))
				data.append(TryChangeToInt(ob.strokeHatchAng[0] * int(ob.useStrokeHatch[0])))
				data.append(TryChangeToInt(ob.strokeHatchAng[1] * int(ob.useStrokeHatch[1])))
				data.append(TryChangeToInt(ob.strokeHatchWidth[0] * int(ob.useStrokeHatch[0])))
				data.append(TryChangeToInt(ob.strokeHatchWidth[1] * int(ob.useStrokeHatch[1])))
				data.append(ob.mirrorX)
				data.append(ob.mirrorY)
				data.append(CAP_TYPES.index(ob.capType))
				data.append(JOIN_TYPES.index(ob.joinType))
				dashArr = []
				for value in ob.dashLengthsAndSpaces:
					if value == 0:
						break
					dashArr.append(value)
				data.append(dashArr)
				data.append(TryChangeToInt(ob.cycleDur))
				pathDataFrames.append(pathDataStr)
			else:
				pathDataFrames.append(GetPathDelta(prevPathData, pathDataStr))
			prevPathData = pathDataStr
		datas.append(data)
		bpy.context.scene.frame_set(prevFrame)
		ob.data = prevData
		for curve in bpy.data.curves:
			if curve.users == 0:
				bpy.data.curves.remove(curve)
		pathsDatas.append(chr(1).join(pathDataFrames))
	elif ob.type == 'MESH':
		prevObName = ob.name
		ob.name += '_'
		geosDatas = []
		for frame in range(ob.minPathFrame, ob.maxPathFrame + 1):
			bpy.context.scene.frame_set(frame)
			depsgraph = bpy.context.evaluated_depsgraph_get()
			evaluatedOb = ob.evaluated_get(depsgraph)
			meshData = evaluatedOb.to_mesh(preserve_all_data_layers = False, depsgraph = depsgraph)
			verts = [v.co.copy() for v in meshData.vertices]
			faces = [p.vertices[:] for p in meshData.polygons]
			worldMatrix = evaluatedOb.matrix_world.copy()
			geosDatas.append({'verts' : verts, 'faces' : faces, 'matrix' : worldMatrix})
		bpy.context.scene.frame_set(prevFrame)
		tempCollection = bpy.data.collections.new('TempExportCollection')
		bpy.context.scene.collection.children.link(tempCollection)
		newMeshData = bpy.data.meshes.new(name='TempExportMesh')
		newOb = bpy.data.objects.new(name = 'TempExportObject', object_data = newMeshData)
		tempCollection.objects.link(newOb)
		for matSlotIdx, matSlot in enumerate(ob.material_slots):
			mat = matSlot.material
			if mat:
				newName = prevObName
				if matSlotIdx > 0:
					newName += '_' + mat.name
				newOb.active_material = mat
				for frame, geoData in enumerate(geosDatas):
					if frame > ob.minPathFrame:
						newName = newName.replace('_' + str(frame - 1), '')
						newName += '_' + str(frame)
					newMeshData.clear_geometry()
					newMeshData.from_pydata(geoData['verts'], [], geoData['faces'])
					newMeshData.update()
					newOb.matrix_world = geoData['matrix']
					min, max = GetRectMinMax(ob)
					if frame == ob.minPathFrame and HandleCopyObject(newOb, [min.x, min.y]):
						break
					scene = bpy.context.scene
					renderSettings = scene.render
					imageSettings = renderSettings.image_settings
					viewSettings = imageSettings.view_settings
					prevRenderPath = renderSettings.filepath
					prevTransparentFilm = renderSettings.film_transparent
					prevExposure = viewSettings.exposure
					prevGamma = viewSettings.gamma
					prevRenderFormat = imageSettings.file_format
					prevColorMode = imageSettings.color_mode
					renderSettings.film_transparent = True
					prevColorManagement = imageSettings.color_management
					prevExposure = viewSettings.exposure
					prevGamma = viewSettings.gamma
					if len(bpy.data.lights) == 0:
						imageSettings.color_management = 'OVERRIDE'
						viewSettings.exposure = 32
						viewSettings.gamma = 5
					imageSettings.file_format = 'BMP'
					imageSettings.color_mode = 'BW'
					renderPaths = []
					prevHideObsInRender = {}
					for ob2 in bpy.data.objects:
						prevHideObsInRender[ob2] = ob2.hide_render
						ob2.hide_render = ob2 != newOb
					prevMatColors = {}
					for matSlot in ob.material_slots:
						mat2 = matSlot.material
						if mat2 and mat != mat2:
							prevMatColors[mat2] = mat2.diffuse_color
							mat2.diffuse_color = DEFAULT_COLOR
					# renderResScale = renderSettings.resolution_percentage / 100
					# minHitDists = {}
					cam = scene.camera
					# camData = cam.data
					# viewFrame = camData.view_frame(scene = scene)
					# viewFrameTopLeft = viewFrame[0]
					# viewFrameTopRight = viewFrame[1]
					# viewFrameBottLeft = viewFrame[2]
					# viewFrameXRange = viewFrameTopRight - viewFrameTopLeft
					# viewFrameYRange = viewFrameBottLeft - viewFrameTopLeft
					# camWorldMatrix = cam.matrix_world
					# camPos = camWorldMatrix.translation
					# renderResolutionX = int(renderSettings.resolution_x * renderResScale)
					# renderResolutionY = int(renderSettings.resolution_y * renderResScale)
					# for ob in bpy.context.selected_objects:
					# 	bvhTree = bvhtree.BVHTree(ob, depsgraph, render = True)
					# 	for x in range(renderResolutionX):
					# 		for y in range(renderResolutionY):
					# 			xNormalized = x / (renderResolutionX - 1)
					# 			yNormalized = y / (renderResolutionY - 1)
					# 			pointOnNearClipPlane = viewFrameTopLeft + viewFrameXRange * xNormalized + viewFrameYRange * yNormalized
					# 			worldPointOnNearClipPlane = camWorldMatrix @ pointOnNearClipPlane
					# 			rayDir = (worldPointOnNearClipPlane - camPos).normalized()
					# 			hitDist = bvhTree.ray_cast(worldPointOnNearClipPlane, rayDir)[3]
					# 			if hitDist:
					# 				pass
					renderSettings.filepath = os.path.join(TMP_DIR, 'Render.bmp')
					bpy.ops.render.render(write_still = True)
					cmd = [POTRACE_PATH, '-s', renderSettings.filepath, '-k ' + str(.01), '-i']
					print(' '.join(cmd))
					subprocess.check_call(cmd)
					svgTxt = open(renderSettings.filepath.replace('.bmp', '.svg'), 'r').read()
					svgTxt = svgTxt.replace('\n', ' ')
					svgIndctr = '<svg '
					svgTxt = svgTxt[svgTxt.find(svgIndctr) :]
					svgTxt = svgTxt.replace(' version="1.0" xmlns="http://www.w3.org/2000/svg"', '')
					metadataEndIndctr = '/metadata>'
					svgTxt = svgTxt[: svgTxt.find('<metadata')] + svgTxt[svgTxt.find('/metadata>') + len(metadataEndIndctr) :]
					svgTxt = svgTxt.replace('00000', '')
					svgTxt = svgTxt.replace('.000000', '')
					camForward = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
					camToOb = newOb.location - cam.location
					projectedVec = camToOb.project(camForward)
					addToSvgTxt = 'id="' + newName + '" style="position:absolute;z-index:' + str(round(-projectedVec.length * 99999)) + '"'
					if frame > 0:
						addToSvgTxt += ' opacity=0'
					svgTxt = svgTxt[: len(svgIndctr)] + addToSvgTxt + svgTxt[len(svgIndctr) :]
					fillIndctr = 'fill="'
					idxOfFillStart = svgTxt.find(fillIndctr) + len(fillIndctr)
					idxOfFillEnd = svgTxt.find('"', idxOfFillStart)
					materialColor = DEFAULT_COLOR
					if len(ob.material_slots) > 0:
						materialColor = ob.material_slots[0].material.diffuse_color
					fillClr = ClampComponents(Round(Multiply(materialColor, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
					if ob.lightFill:
						svgTxt = svgTxt[: idxOfFillStart] + 'url(#' + ob.lightFill.name + ')' + svgTxt[idxOfFillEnd :]
					else:
						svgTxt = svgTxt[: idxOfFillStart] + 'rgb(' + str(fillClr[0]) + ' ' + str(fillClr[1]) + ' ' + str(fillClr[2]) + ')' + svgTxt[idxOfFillEnd :]
					if ob.useStroke:
						strokeClr = ClampComponents(Round(Multiply(ob.strokeClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
						svgTxt = svgTxt.replace('stroke="none"', 'stroke="rgb(' + str(strokeClr[0]) + ' ' + str(strokeClr[1]) + ' ' + str(strokeClr[2]) + ')" stroke-width=' + str(ob.strokeWidth))
					for ob in bpy.data.objects:
						ob.hide_render = prevHideObsInRender[ob]
					for matSlot in ob.material_slots:
						mat2 = matSlot.material
						if mat2 in prevMatColors:
							mat2.diffuse_color = prevMatColors[mat2]
					renderSettings.filepath = prevRenderPath
					renderSettings.film_transparent = prevTransparentFilm
					viewSettings.exposure = prevExposure
					viewSettings.gamma = prevGamma
					imageSettings.file_format = prevRenderFormat
					imageSettings.color_mode = prevColorMode
					imageSettings.color_management = prevColorManagement
					viewSettings.exposure = prevExposure
					viewSettings.gamma = prevGamma
					svgsDatas[newName] = svgTxt
		tempCollection.objects.unlink(newOb)
		bpy.data.objects.remove(newOb)
		bpy.data.meshes.remove(newMeshData)
		bpy.context.scene.collection.children.unlink(tempCollection)
		bpy.data.collections.remove(tempCollection)
		bpy.data.objects[prevObName + '_'].name = prevObName
		for mesh in bpy.data.meshes:
			if mesh.users == 0:
				bpy.data.meshes.remove(mesh)
	elif ob.type == 'GREASEPENCIL':
		min, max = GetRectMinMax(ob)
		if HandleCopyObject(ob, [min.x, min.y]):
			return
		scene = bpy.context.scene
		renderSettings = scene.render
		imageSettings = renderSettings.image_settings
		viewSettings = imageSettings.view_settings
		prevRenderPath = renderSettings.filepath
		prevTransparentFilm = renderSettings.film_transparent
		prevExposure = viewSettings.exposure
		prevGamma = viewSettings.gamma
		prevRenderFormat = imageSettings.file_format
		prevColorMode = imageSettings.color_mode
		renderSettings.film_transparent = True
		prevColorManagement = imageSettings.color_management
		prevExposure = viewSettings.exposure
		prevGamma = viewSettings.gamma
		if len(bpy.data.lights) == 0:
			imageSettings.color_management = 'OVERRIDE'
			viewSettings.exposure = 32
			viewSettings.gamma = 5
		imageSettings.file_format = 'BMP'
		imageSettings.color_mode = 'BW'
		renderPaths = []
		world = bpy.data.worlds[0]
		worldColor = world.color
		prevWorldColor = list(worldColor)
		prevMatAlpha = ob.active_material.grease_pencil.color[3]
		ob.active_material.grease_pencil.color = Subtract([1, 1, 1, 1], ob.active_material.grease_pencil.color)
		ob.active_material.grease_pencil.color[3] = prevMatAlpha
		world.color = [0, 0, 0]
		prevObsColors = {}
		for ob2 in bpy.data.objects:
			if ob2 != ob:
				mat = ob2.active_material
				if mat:
					matClr = mat.diffuse_color
					prevObsColors[ob2] = list(matClr)
					mat.diffuse_color = DEFAULT_COLOR
		cam = scene.camera
		renderSettings.filepath = os.path.join(TMP_DIR, 'Render.bmp')
		bpy.ops.render.render(write_still = True)
		cmd = [POTRACE_PATH, '-s', renderSettings.filepath, '-k ' + str(.01), '-i']
		print(' '.join(cmd))
		subprocess.check_call(cmd)
		svgTxt = open(renderSettings.filepath.replace('.bmp', '.svg'), 'r').read()
		svgTxt = svgTxt.replace('\n', ' ')
		svgIndctr = '<svg '
		svgTxt = svgTxt[svgTxt.find(svgIndctr) :]
		svgTxt = svgTxt.replace(' version="1.0" xmlns="http://www.w3.org/2000/svg"', '')
		metadataEndIndctr = '/metadata>'
		svgTxt = svgTxt[: svgTxt.find('<metadata')] + svgTxt[svgTxt.find('/metadata>') + len(metadataEndIndctr) :]
		camForward = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
		camToOb = ob.location - cam.location
		projectedVec = camToOb.project(camForward)
		svgTxt = svgTxt[: len(svgIndctr)] + 'id="' + ob.name + '" style="position:absolute;z-index:' + str(round(-projectedVec.length * 99999)) + '"' + svgTxt[len(svgIndctr) :]
		fillIndctr = 'fill="'
		idxOfFillStart = svgTxt.find(fillIndctr) + len(fillIndctr)
		idxOfFillEnd = svgTxt.find('"', idxOfFillStart)
		materialColor = DEFAULT_COLOR
		if len(ob.material_slots) > 0:
			materialColor = ob.material_slots[0].material.diffuse_color
		prevMatAlpha = materialColor[3]
		fillClr = Subtract([1, 1, 1, 1], materialColor)
		fillClr[3] = prevMatAlpha
		fillClr = ClampComponents(Round(Multiply(fillClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
		svgTxt = svgTxt[: idxOfFillStart] + 'rgb(' + str(fillClr[0]) + ' ' + str(fillClr[1]) + ' ' + str(fillClr[2]) + ')' + svgTxt[idxOfFillEnd :]
		if ob.useStroke:
			strokeClr = ClampComponents(Round(Multiply(ob.strokeClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
			svgTxt = svgTxt.replace('stroke="none"', 'stroke="rgb(' + str(strokeClr[0]) + ' ' + str(strokeClr[1]) + ' ' + str(strokeClr[2]) + ')" stroke-width=' + str(ob.strokeWidth))
		ob.active_material.grease_pencil.color = Subtract([1, 1, 1, 1], ob.active_material.grease_pencil.color)
		ob.active_material.grease_pencil.color[3] = prevMatAlpha
		world.color = prevWorldColor
		for ob2 in bpy.data.objects:
			if ob2 in prevObsColors:
				ob2.active_material.diffuse_color = prevObsColors[ob2]
		renderSettings.filepath = prevRenderPath
		renderSettings.film_transparent = prevTransparentFilm
		viewSettings.exposure = prevExposure
		viewSettings.gamma = prevGamma
		imageSettings.file_format = prevRenderFormat
		imageSettings.color_mode = prevColorMode
		imageSettings.color_management = prevColorManagement
		viewSettings.exposure = prevExposure
		viewSettings.gamma = prevGamma
		svgsDatas[ob.name] = svgTxt
	elif ob.type == 'EMPTY':
		if len(ob.children) > 0:
			childrenNames = []
			for child in ob.children:
				ExportObject (child)
				childrenNames.append(child.name)
			datas.append([ob.name, childrenNames])
	exportedObs.append(ob)

def RegisterPhysics (ob):
	rigidBodyName = GetVarNameFromObject(ob) + 'RigidBody'
	rigidBodyDescName = rigidBodyName + 'Desc'
	if ob.rigidBodyExists:
		rigidBody = 'var ' + rigidBodyDescName + ' = RAPIER.RigidBodyDesc.' + ob.rigidBodyType + '()'
		if ob.location[0] != 0 or ob.location[1] != 0:
			rigidBody += '.setTranslation(' + str(ob.location.x) + ', ' + str(-ob.location.y) + ')'
		if not ob.canRotate:
			rigidBody += '.lockRotations();\n'
		rigidBody += ';\n'
		if not ob.rigidBodyEnable:
			rigidBodyDescName + '.enabled = false;\n'
		if ob.dominance != 0:
			rigidBodyDescName + '.setDominanceGroup(' + str(ob.dominance) + ');\n'
		if ob.gravityScale != 1:
			rigidBody += rigidBodyDescName + '.setGravityScale(' + str(ob.gravityScale) + ');\n'
		if not ob.canSleep:
			rigidBody += rigidBodyDescName + '.setCanSleep(false);\n'
		if ob.linearDrag != 0:
			rigidBody += rigidBodyDescName + '.setLinearDamping(' + str(ob.linearDrag) + ');\n'
		if ob.angDrag != 0:
			rigidBody += rigidBodyDescName + '.setAngularDamping(' + str(ob.angDrag) + ');\n'
		rigidBody += rigidBodyName + ' = world.createRigidBody(' + rigidBodyDescName + ');\n'
		if ob.continuousCollideDetect:
			rigidBody += rigidBodyName + '.enableCcd(true);\n'
		rigidBody += 'rigidBodiesIds["' + ob.name + '"] = ' + rigidBodyName + ';'
		rigidBodies[ob] = rigidBody
	if ob.colliderExists:
		colliderName = GetVarNameFromObject(ob) + 'Collider'
		colliderDescName = colliderName + 'Desc'
		collider = 'var ' + colliderDescName + ' = RAPIER.ColliderDesc.' + ob.shapeType + '('
		if ob.shapeType == 'ball':
			collider += str(ob.radius)
		elif ob.shapeType == 'halfspace':
			collider += ToVector2String(ob.normal)
		elif ob.shapeType == 'cuboid':
			collider += str(ob.size[0] / 2) + ', ' + str(ob.size[1] / 2)
		elif ob.shapeType == 'roundCuboid':
			collider += str(ob.size[0] / 2) + ', ' + str(ob.size[1] / 2) + ', ' + str(ob.cuboidBorderRadius)
		elif ob.shapeType == 'capsule':
			collider += str(ob.capsuleHeight / 2) + ', ' + str(ob.capsuleRadius)
		elif ob.shapeType == 'segment':
			collider += ToVector2String(ob.segmentPos1) + ', ' + ToVector2String(ob.segmentPos2)
		elif ob.shapeType == 'triangle':
			collider += ToVector2String(ob.trianglePos1) + ', ' + ToVector2String(ob.trianglePos2) + ', ' + ToVector2String(ob.trianglePos3)
		elif ob.shapeType == 'roundTriangle':
			collider += ToVector2String(ob.trianglePos1) + ', ' + ToVector2String(ob.trianglePos2) + ', ' + ToVector2String(ob.trianglePos3) + ', ' + str(ob.triangleBorderRadius)
		elif ob.shapeType == 'polyline':
			collider += '['
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'usePolylinePoint%s' %i):
					break
				point = getattr(ob, 'polylinePoint%s' %i)
				collider += str(point[0]) + ', ' + str(point[1]) + ', '
			if ob.polylineIdx0 != -1:
				collider += '], ['
				for i in range(MAX_SHAPE_POINTS):
					idx = getattr(ob, 'polylineIdx%s' %i)
					if idx != -1:
						collider += str(idx) + ', '
			collider += ']'
		elif ob.shapeType == 'trimesh':
			collider += '['
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useTrimeshPoint%s' %i):
					break
				point = getattr(ob, 'trimeshPoint%s' %i)
				collider += str(point[0]) + ', ' + str(point[1]) + ', '
			collider += '], ['
			for i in range(MAX_SHAPE_POINTS):
				idx = getattr(ob, 'trimeshIdx%s' %i)
				if idx != -1:
					collider += str(idx) + ', '
			collider += ']'
		elif ob.shapeType == 'convexHull':
			collider += '['
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useConvexHullPoint%s' %i):
					break
				point = getattr(ob, 'convexHullPoint%s' %i)
				collider += str(point[0]) + ', ' + str(point[1]) + ', '
			collider += ']'
		elif ob.shapeType == 'roundConvexHull':
			collider += '['
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useRoundConvexHullPoint%s' %i):
					break
				point = getattr(ob, 'roundConvexHullPoint%s' %i)
				collider += str(point[0]) + ', ' + str(point[1]) + ', '
			collider += '], ' + str(ob.roundConvexHullBorderRadius)
		elif ob.shapeType == 'heightfield':
			collider += '['
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useHeight%s' %i):
					break
				collider += str(getattr(ob, 'height%s' %i))
			collider += '], ' + ToVector2String(ob.heightfieldScale)
		collider += ');\n'
		if ob.density != 0:
			collider += colliderDescName + '.density = ' + str(ob.density) + ';\n'
		if not ob.colliderEnable:
			collider += colliderDescName + '.enabled = false;\n'
		attachTo = []
		for i in range(MAX_ATTACH_COLLIDER_CNT):
			_attachTo = getattr(ob, 'attachTo%s' %i)
			if not getattr(ob, 'attach%s' %i):
				break
			attachTo.append(_attachTo)
		if attachTo == []:
			collider += colliderName + ' = world.createCollider(' + colliderDescName +');'
		else:
			for _attachTo in attachTo:
				collider += colliderName + GetVarNameFromObject(_attachTo) + ' = world.createCollider(' + colliderDescName + ', ' + GetVarNameFromObject(_attachTo) + 'RigidBody);\n'
		colliders[ob] = collider
	if ob.jointExists:
		jointName = GetVarNameFromObject(ob) + 'Joint'
		jointDataName = jointName + 'Data'
		joint = 'var ' + jointDataName + ' = RAPIER.JointData.' + ob.jointType + '('
		if ob.jointType == 'fixed':
			joint += ToVector2String(ob.anchorPos1)
			joint += str(ob.anchorRot1) + ', '
			joint += ToVector2String(ob.anchorPos2) + ', '
			joint += str(ob.anchorRot2)
		elif ob.jointType == 'spring':
			joint += str(ob.restLen) + ', '
			joint += str(ob.stiffness) + ', '
			joint += str(ob.damping) + ', '
			joint += ToVector2String(ob.anchorPos1) + ', '
			joint += ToVector2String(ob.anchorPos2)
		elif ob.jointType == 'revolute':
			joint += ToVector2String(ob.anchorPos1) + ', '
			joint += ToVector2String(ob.anchorPos2)
		elif ob.jointType == 'prismatic':
			joint += ToVector2String(ob.anchorPos1) + ', '
			joint += ToVector2String(ob.anchorPos2) + ', '
			joint += ToVector2String(ob.jointAxis)
		elif ob.jointType == 'rope':
			joint += str(ob.jointLen) + ', '
			joint += ToVector2String(ob.anchorPos1) + ', '
			joint += ToVector2String(ob.anchorPos2)
		joint += ');\n' + jointName + ' = world.createImpulseJoint(' + jointDataName + ', ' + GetVarNameFromObject(ob.anchorRigidBody1) + 'RigidBody, ' + GetVarNameFromObject(ob.anchorRigidBody2) + 'RigidBody, true);'
		joints[ob] = joint
	if ob.charControllerExists:
		charControllerName = GetVarNameFromObject(ob) + 'CharController'
		charController = 'var ' + charControllerName + ' = new RAPIER.KinematicCharacterController(' + str(ob.contactOff) + ', new RAPIER.IntegrationParameters(), '
		charControllers[ob] = charController

def HandleCopyObject (ob, pos):
	try:
		for exportedOb in exportedObs:
			idxOfPeriod = ob.name.find('.')
			if idxOfPeriod == -1:
				obNameWithoutPeriod = ob.name
			else:
				obNameWithoutPeriod = ob.name[: idxOfPeriod]
			idxOfPeriod = exportedOb.name.find('.')
			if idxOfPeriod == -1:
				exportedObNameWithoutPeriod = exportedOb.name
			else:
				exportedObNameWithoutPeriod = exportedOb.name[: idxOfPeriod]
			if obNameWithoutPeriod == exportedObNameWithoutPeriod:
				datas.append([obNameWithoutPeriod, ob.name, TryChangeToInt(pos[0]), TryChangeToInt(pos[1])])
				exportedObs.append(ob)
				return True
	except:
		return False
	return False

def GetPathDelta (fromPathData, toPathData):
	output = ''
	for i in range(len(fromPathData)):
		fromPathVal = ord(fromPathData[i])
		toPathVal = ord(toPathData[i])
		if fromPathVal != toPathVal:
			output += ToByteString(i + 32) + ToByteString(toPathVal - fromPathVal + 32 + 128)
	return output

def GetBlenderData ():
	global datas, colors, userJS, initCode, pathsDatas, updateCode, exportedObs, svgsDatas
	exportedObs = []
	userJS = ''
	datas = []
	colors = {}
	pathsDatas = []
	rigidBodies = {}
	colliders = {}
	joints = {}
	charControllers = {}
	initCode = []
	updateCode = []
	svgsDatas = {}
	for ob in bpy.data.objects:
		ExportObject (ob)
	for ob in bpy.data.objects:
		for script in GetScripts(ob, True):
			userJS += script
		for scriptInfo in GetScripts(ob, False):
			script = scriptInfo[0]
			isInit = scriptInfo[1]
			if isInit:
				initCode.append(script)
			else:
				updateCode.append(script)
	return (datas, initCode, updateCode, userJS)

buildInfo = {
	'html'  : None,
	'html-size':None,
	'zip'     : None,
	'zip-size': None,
	'js-size' : None,
	'js-gz-size' : None,
}

JS_SUFFIX = '''
var i = 0;
var d = JSON.parse(D);
var c = JSON.parse(C);
var g = [];
for (var e of d)
{
	var l = e.length;
	if (l > 10)
	{
		var pathFramesStrings = p.split('\\n')[i];
		if (e[51])
			pathFramesStrings = pathFramesStrings.split(String.fromCharCode(1));
		$.draw_svg (e[0], e[1], [e[2], e[3]], c[e[4]], e[5], c[e[6]], e[7], pathFramesStrings, e[8], e[9], e[10], e[11], e[12], e[13], [e[14], e[15]], e[16], e[17], [e[18], e[19]], [e[20], e[21]], e[22], e[23], e[24], e[25], [e[26], e[27]], [e[28], e[29]], [e[30], e[31]], [e[32], e[33]], [e[34], e[35]], [e[36], e[37]], [e[38], e[39]], [e[40], e[41]], [e[42], e[43]], e[44], e[45], e[46], e[47], e[48], e[49], e[50]);
		i ++;
	}
	else if (l > 4)
		$.add_radial_gradient (e[0], [e[1], e[2]], e[3], e[4], c[e[5]], c[e[6]], c[e[7]], e[8], e[9]);
	else if (l > 3)
		$.copy_node (e[0], e[1], [e[2], e[3]]);
	else
		g.push(e);
}
for (var e of g)
{
	var newGroup = document.createElement('g');
	newGroup.id = e[0];
	document.body.appendChild(newGroup);
	$.add_children (e[0], e[1]);
}
$.main ()
'''
JS = '''
function dot (from, to)
{
	return from[0] * to[0] + from[1] * to[1];
}
function ang (from, to)
{
	return Math.acos(dot(normalize(from), normalize(to))) * (180 / Math.PI);
}
function signed_ang (from, to)
{
	return ang(from, to) * Math.sign(from[0] * to[1] - from[1] * to[0]);
}
function rotate (v, ang)
{
	ang /= 180 / Math.PI;
	ang += Math.atan2(v[1], v[0]);
	var mag = magnitude(v);
	return [Math.cos(ang) * mag, Math.sin(ang) * mag];
}
function rotate_to (from, to, maxAng)
{
	return rotate(from, clamp(signed_ang(from, to), -maxAng, maxAng));
}
function get_pos_and_size (elmt)
{
	return [[parseInt(elmt.getAttribute('x')), parseInt(elmt.getAttribute('y'))], [parseInt(elmt.getAttribute('width')), parseInt(elmt.getAttribute('height'))]];
}
function lerp (min, max, t)
{
	return min + t * (max - min);
}
function clamp (n, min, max)
{
	return Math.min(Math.max(n, min), max);
}
function inv_lerp (from, to, n)
{
	return (n - from) / (to - from);
}
function remap (inFrom, inTo, outFrom, outTo, n)
{
	return lerp(outFrom, outTo, inv_lerp(inFrom, inTo, n));
}
function overlaps (min, max, min2, max2)
{
	return !(max[0] < min2[0]
		|| min[0] > max2[0]
		|| max[1] < min2[1]
		|| min[1] > max2[1]);
}
function ang_to_dir (ang)
{
	return [Math.cos(ang), Math.sin(ang)];
}
function random_vector (maxDist)
{
	var dist = random(0, maxDist);
	var ang = random(0, 2 * Math.PI);
	var dir = ang_to_dir(ang);
	return [dir[0] * dist, dir[1] * dist];
}
function magnitude (v)
{
	var output = 0;
	for (var elt of v)
		output += elt * elt;
	return Math.sqrt(output);
}
function normalize (v)
{
	var mag = magnitude(v);
	return [v[0] / mag, v[1] / mag];
}
function random (min, max)
{
	return Math.random() * (max - min) + min;
}
function add_group (id, pos, txt)
{
	var group = document.createElement('g');
	group.id = id;
	group.setAttribute('x', pos[0]);
	group.setAttribute('y', pos[1]);
	group.innerHTML = txt;
	document.body.appendChild(group);
	return group;
}
function shuffle (list)
{
	var currentIdx = list.length;
	while (currentIdx != 0)
	{
		var randIdx = Math.floor(Math.random() * currentIdx);
		currentIdx --;
		[list[currentIdx], list[randIdx]] = [list[randIdx], list[currentIdx]];
	}
}
'''
PHYSICS = '''
import RAPIER from 'https://cdn.skypack.dev/@dimforge/rapier2d-compat';

// Vars
var world;
var rigidBodiesIds = {};
RAPIER.init().then(() => {
	// Gravity
	world = new RAPIER.World(gravity);
	// Rigid Bodies
	// Colliders
	// Joints
	// Char Controllers
});
'''
JS_API = '''
class api
{
	get_svg_paths_and_strings (framesStrings, cyclic)
	{
		var pathsVals = [];
		var pathsStrings = [];
		var i = 0;
		for (var frameStr of framesStrings)
		{
			if (i == 0)
				var prevPathStr = frameStr;
			else
				for (var i2 = 0; i2 < frameStr.length; i2 += 2)
				{
					var idx = frameStr.charCodeAt(i2) - 32;
					prevPathStr = prevPathStr.slice(0, idx) + String.fromCharCode(prevPathStr.charCodeAt(idx) + frameStr.charCodeAt(i2 + 1) - 160) + prevPathStr.slice(idx + 1);
				}
			pathsVals.push($.get_svg_path(prevPathStr, cyclic));
			pathsStrings.push(prevPathStr);
			i ++;
		}
		return [pathsVals, pathsStrings];
	}
	get_svg_path (pathStr, cyclic)
	{
		var output = 'M ' + pathStr.charCodeAt(0) + ',' + pathStr.charCodeAt(1) + ' ';
		for (var i = 2; i < pathStr.length; i += 2)
		{
			if ((i - 2) % 6 == 0)
				output += 'C ';
			output += '' + pathStr.charCodeAt(i) + ',' + pathStr.charCodeAt(i + 1) + ' '
		}
		if (cyclic)
			output += 'Z';
		return output;
	}
	copy_node (id, newId, pos)
	{
		var copy = document.getElementById(id).cloneNode(true);
		copy.id = newId;
		copy.setAttribute('x', pos[0]);
		copy.setAttribute('y', pos[1]);
		copy.setAttribute('transform', 'translate(' + pos[0] + ',' + pos[1] + ')');
		document.body.appendChild(copy);
		return copy;
	}
	add_children (id, childIds)
	{
		var foundFirstChild = false;
		for (var childId of childIds)
		{
			var elt = document.getElementById(childId);
			elt.style.position = 'fixed';
			document.getElementById(id).appendChild(elt);
		}
	}
	add_radial_gradient (id, pos, zIdx, diameter, color, color2, color3, colorPositions, subtractive)
	{
		var group = document.createElement('g');
		group.id = id;
		group.setAttribute('x', pos[0]);
		group.setAttribute('y', pos[1]);
		var mixMode = 'lighter';
		if (subtractive)
			mixMode = 'darker';
		group.style = 'position:absolute;left:' + (pos[0] + diameter / 2) + 'px;top:' + (pos[1] + diameter / 2) + 'px;background-image:radial-gradient(rgba(' + color[0] + ',' + color[1] + ',' + color[2] + ',' + color[3] + ') ' + colorPositions[0] + '%, rgba(' + color2[0] + ',' + color2[1] + ',' + color2[2] + ',' + color2[3] + ') ' + colorPositions[1] + '%, rgba(' + color3[0] + ',' + color3[1] + ',' + color3[2] + ',' + color3[3] + ') ' + colorPositions[2] + '%);width:' + diameter + 'px;height:' + diameter + 'px;z-index:' + zIdx + ';mix-blend-mode:plus-' + mixMode;
		document.body.appendChild(group);
	}
	draw_svg (positions, posPingPong, size, fillClr, lineWidth, lineClr, id, pathFramesStrings, cyclic, zIdx, unused, jiggleDist, jiggleDur, jiggleFrames, rotAngRange, rotDur, rotPingPong, scaleXRange, scaleYRange, scaleDur, scaleHaltDurAtMin, scaleHaltDurAtMax, scalePingPong, origin, fillHatchDensity, fillHatchRandDensity, fillHatchAng, fillHatchWidth, lineHatchDensity, lineHatchRandDensity, lineHatchAng, lineHatchWidth, mirrorX, mirrorY, capType, joinType, dashArr, cycleDur)
	{
		var fillClrTxt = 'rgb(' + fillClr[0] + ' ' + fillClr[1] + ' ' + fillClr[2] + ')';
		var lineClrTxt = 'rgb(' + lineClr[0] + ' ' + lineClr[1] + ' ' + lineClr[2] + ')';
		var pos = positions[0];
		var svg = document.createElement('svg');
		svg.setAttribute('fill-opacity', fillClr[3] / 255);
		svg.id = id;
		svg.style = 'z-index:' + zIdx + ';position:absolute';
		svg.setAttribute('transform-origin', origin[0] + '% ' + origin[1] + '%');
		svg.setAttribute('x', pos[0]);
		svg.setAttribute('y', pos[1]);
		svg.setAttribute('width', size[0]);
		svg.setAttribute('height', size[1]);
		var trs = 'translate(' + pos[0] + ',' + pos[1] + ')';
		svg.setAttribute('transform', trs);
		var i = 0;
		var pathsValsAndStrings = $.get_svg_paths_and_strings(pathFramesStrings, cyclic);
		var anim;
		var frames;
		var firstFrame = '';
		for (var pathVals of pathsValsAndStrings[0])
		{
			var path = document.createElement('path');
			path.id = id + ' ';
			if (i > 0)
				path.setAttribute('opacity', 0);
			path.style = 'fill:' + fillClrTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineClrTxt;
			path.setAttribute('d', pathVals);
			if (jiggleFrames > 0)
			{
				anim = document.createElement('animate');
				anim.setAttribute('attributename', 'd');
				anim.setAttribute('repeatcount', 'indefinite');
				anim.setAttribute('dur', jiggleDur + 's');
				frames = '';
				for (var i2 = 0; i2 < jiggleFrames; i2 ++)
				{
					pathVals = pathsValsAndStrings[1][i];
					for (var i3 = 0; i3 < pathVals.length; i3 += 2)
					{
						off = normalize(random_vector(1));
						off = [off[0] * jiggleDist, off[1] * jiggleDist];
						pathVals = pathVals.slice(0, i3) + String.fromCharCode(pathVals.charCodeAt(i3) + off[0]) + String.fromCharCode(pathVals.charCodeAt(i3 + 1) + off[1]) + pathVals.slice(i3 + 2);
					}
					pathVals = $.get_svg_path(pathVals, cyclic);
					if (i2 == 0)
					{
						firstFrame = pathVals;
						anim.setAttribute('from', pathVals);
						anim.setAttribute('to', pathVals);
					}
					frames += pathVals + ';';
				}
				anim.setAttribute('values', frames + firstFrame);
				path.appendChild(anim);
			}
			svg.appendChild(path);
			i ++;
		}
		document.body.innerHTML += svg.outerHTML;
		var off = lineWidth / 2 + jiggleDist;
		var min = 32 - off;
		svg.setAttribute('viewbox', min + ' ' + min + ' ' + (size[0] + off * 2) + ' ' + (size[1] + off * 2));
		svg = document.getElementById(id);
		path = document.getElementById(id + ' ');
		var svgRect = svg.getBoundingClientRect();
		var pathRect = path.getBoundingClientRect();
		path.style.transform = 'translate(' + (svgRect.x - pathRect.x + off) + 'px,' + (svgRect.y - pathRect.y + off) + 'px)';
		if (rotDur > 0)
		{
			anim = document.createElement('animatetransform');
			anim.setAttribute('attributename', 'transform');
			anim.setAttribute('type', 'rotate');
			anim.setAttribute('repeatcount', 'indefinite');
			anim.setAttribute('dur', rotDur + 's');
			firstFrame = rotAngRange[0];
			anim.setAttribute('from', firstFrame);
			frames = firstFrame + ';' + rotAngRange[1];
			if (rotPingPong)
			{
				anim.setAttribute('to', firstFrame);
				frames += ';' + firstFrame;
			}
			else
				anim.setAttribute('to', rotAngRange[1]);
			anim.setAttribute('values', frames);
			anim.setAttribute('additive', 'sum');
			svg.innerHTML += anim.outerHTML;
		}
		var totalScaleDur = scaleDur + scaleHaltDurAtMin + scaleHaltDurAtMax;
		if (totalScaleDur > 0)
		{
			anim = document.createElement('animatetransform');
			anim.setAttribute('attributename', 'transform');
			anim.setAttribute('type', 'scale');
			anim.setAttribute('repeatcount', 'indefinite');
			if (scalePingPong)
				totalScaleDur += scaleDur;
			anim.setAttribute('dur', totalScaleDur + 's');
			firstFrame = scaleXRange[0] + ' ' + scaleYRange[0];
			anim.setAttribute('from', firstFrame);
			var thirdFrame = scaleXRange[1] + ' ' + scaleYRange[1];
			frames = firstFrame + ';' + firstFrame + ';' + thirdFrame + ';' + thirdFrame;
			var time = scaleHaltDurAtMin / totalScaleDur;
			var times = '0;' + time + ';';
			time += scaleDur / totalScaleDur;
			times += time + ';';
			time += scaleHaltDurAtMax / totalScaleDur;
			times += time;
			if (scalePingPong)
			{
				anim.setAttribute('to', firstFrame);
				frames += ';' + firstFrame;
				times += ';' + 1;
			}
			else
				anim.setAttribute('to', thirdFrame);
			anim.setAttribute('values', frames);
			anim.setAttribute('keytimes', times);
			anim.setAttribute('additive', 'sum');
			svg.innerHTML += anim.outerHTML;
		}
		if (cycleDur != 0)
		{
			anim = document.createElement('animate');
			anim.setAttribute('attributename', 'stroke-dashoffset');
			anim.setAttribute('repeatcount', 'indefinite');
			var pathLen = path.getTotalLength();
			anim.setAttribute('dur', cycleDur + 's');
			anim.setAttribute('from', 0);
			anim.setAttribute('to', pathLen);
			anim.setAttribute('values', '0;' + pathLen);
			path.appendChild(anim);
		}
		document.getElementById(id + ' ').remove();
		svg.appendChild(path);
		var capTypes = ['butt', 'round', 'square'];
		svg.style.strokeLinecap = capTypes[capType];
		var joinTypes = ['arcs', 'bevel', 'miter', 'miter-clip', 'round'];
		svg.style.strokeLinejoin = joinTypes[joinType];
		svg.style.strokeDasharray = dashArr;
		if (magnitude(fillHatchDensity) > 0)
		{
			var args = [fillClr, true, svg, path]; 
			if (fillHatchDensity[0] > 0)
				$.hatch ('_' + id, ...args, fillHatchDensity[0], fillHatchRandDensity[0], fillHatchAng[0], fillHatchWidth[0]);
			if (fillHatchDensity[1] > 0)
				$.hatch ('|' + id, ...args, fillHatchDensity[1], fillHatchRandDensity[1], fillHatchAng[1], fillHatchWidth[1]);
			lineClr[3] = 255;
		}
		if (magnitude(lineHatchDensity) > 0)
		{
			var args = [lineClr, false, svg, path]; 
			if (lineHatchDensity[0] > 0)
				$.hatch ('@' + id, ...args, lineHatchDensity[0], lineHatchRandDensity[0], lineHatchAng[0], lineHatchWidth[0]);
			if (lineHatchDensity[1] > 0)
				$.hatch ('$' + id, ...args, lineHatchDensity[1], lineHatchRandDensity[1], lineHatchAng[1], lineHatchWidth[1]);
			lineClr[3] = 255;
		}
		svg.setAttribute('stroke-opacity', lineClr[3] / 255);
		if (mirrorX)
		{
			svg = $.copy_node(id, '~' + id, pos);
			svg.setAttribute('transform', trs + 'scale(-1,1)');
			svg.setAttribute('transform-origin', 50 - (origin[0] - 50) + '% ' + origin[1] + '%');
		}
		if (mirrorY)
		{
			svg = $.copy_node(id, '`' + id, pos);
			svg.setAttribute('transform', trs + 'scale(1,-1)');
			svg.setAttribute('transform-origin', origin[0] + '% ' + (50 - (origin[1] - 50)) + '%');
		}
		var pathRect = svg.children[svg.children.length - 1].getBoundingClientRect();
		for (var i = svg.children.length - 2; i >= 0; i --)
		{
			var child = svg.children[i];
			var childRect = child.getBoundingClientRect();
			var pathAnchor = [lerp(pathRect.x, pathRect.right, origin[0] / 100), lerp(pathRect.y, pathRect.bottom, origin[1] / 100)];
			var childAnchor = [lerp(childRect.x, childRect.right, origin[0] / 100), lerp(childRect.y, childRect.bottom, origin[1] / 100)];
			child.setAttribute('transform', 'translate(' + (pathAnchor[0] - childAnchor[0]) + ',' + (pathAnchor[1] - childAnchor[1]) + ')');
			pathRect = childRect;
		}
	}
	hatch (id, color, useFIll, svg, path, density, randDensity, ang, width)
	{
		var luminance = (.2126 * color[0] + .7152 * color[1] + .0722 * color[2]) / 255;
		var pattern = document.createElement('pattern');
		pattern.id = id;
		pattern.style = 'transform:rotate(' + ang + 'deg)';
		pattern.setAttribute('width', '100%');
		pattern.setAttribute('height', '100%');
		pattern.setAttribute('patternunits', 'userSpaceOnUse');
		var path = path.cloneNode();
		var pathTxt = '';
		var x = 0;
		var interval = 15 / density * luminance;
		for (var i = 0; i < 99; i ++)
		{
			var off = random(-interval * randDensity, interval * randDensity);
			pathTxt += 'M ' + (x + off) + ' 0 L ' + (x + off) + ' ' + 999 + ' ';
			x += interval;
		}
		path.setAttribute('d', pathTxt);
		path.style = 'stroke-width:' + (width * (1 - luminance)) + ';stroke:black';
		pattern.appendChild(path);
		svg.appendChild(pattern);
		path = path.cloneNode(true);
		if (useFIll)
			path.style.fill = 'url(#' + id + ')';
		else
			path.style.stroke = 'url(#' + id + ')';
		svg.innerHTML += path.outerHTML;
	}
	main ()
	{
		// Init
		var f = ts => {
			$.dt = (ts - $.prev) / 1000;
			$.prev = ts;
			window.requestAnimationFrame(f);
			world.step();
			for (var [key, value] of Object.entries(rigidBodiesIds))
			{
				var node = document.getElementById(key);
				var trs = node.style.transform;
				var idxOfPosStart = trs.indexOf('translate(');
				var idxOfPosEnd = trs.indexOf(')', idxOfPosStart);
				var pos = value.translation();
				var posStr = 'translate(' + pos.x + 'px,' + pos.y + 'px)';
				if (idxOfPosStart == -1)
					node.style.transform = posStr + trs;
				else
					node.style.transform = trs.slice(0, idxOfPosStart) + posStr + trs.slice(idxOfPosEnd + 1);
			}
			// Update
		};
		window.requestAnimationFrame(ts => {
			$.prev = ts;
			window.requestAnimationFrame(f);
		});
	}
}
var $ = new api;
'''

def GenJsAPI (world):
	global datas, userJS, colors
	js = [JS, JS_API, userJS]
	if usePhysics:
		physics = PHYSICS
		vars = ''
		for key in rigidBodies.keys():
			rigidBodyName = GetVarNameFromObject(key) + 'RigidBody'
			vars += 'var ' + rigidBodyName + ';\n'
		for key in colliders.keys():
			colliderName = GetVarNameFromObject(key) + 'Collider'
			attachTo = []
			for i in range(MAX_ATTACH_COLLIDER_CNT):
				_attachTo = getattr(key, 'attachTo%s' %i)
				if not getattr(key, 'attach%s' %i):
					break
				attachTo.append(_attachTo)
			if attachTo == []:
				vars += 'var ' + colliderName + ';\n'
			else:
				for _attachTo in attachTo:
					vars += 'var ' + colliderName + GetVarNameFromObject(_attachTo) + ';\n'
		for key in joints.keys():
			jointName = GetVarNameFromObject(key) + 'Joint'
			vars += 'var ' + jointName + ';\n'
		for key in charControllers.keys():
			charControllerName = GetVarNameFromObject(key) + 'CharController'
			vars += 'var ' + charControllerName + ';\n'
		physics = physics.replace('// Vars', vars)
		physics = physics.replace('// Gravity', 'var gravity = ' + ToVector2String(bpy.context.scene.gravity) + ';')
		physics = physics.replace('// Colliders', '\n'.join(colliders.values()))
		physics = physics.replace('// Rigid Bodies', '\n'.join(rigidBodies.values()))
		physics = physics.replace('// Joints', '\n'.join(joints.values()))
		physics = physics.replace('// Char Controllers', '\n'.join(charControllers.values()))
		js += [physics]
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	datas = json.dumps(datas).replace(', ', ',')
	colors = json.dumps(colors).replace(' ', '')
	if world.minifyMethod == 'terser':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += 'var D=`' + datas + '`\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + colors + '`\n' + JS_SUFFIX
		open(jsTmp, 'w').write(js)
		cmd = ['python', 'tinifyjs/Main.py', '-i=' + jsTmp, '-o=' + jsTmp, '-no_compress', dontMangleArg]
		print(' '.join(cmd))
		subprocess.run(cmd)
		js = open(jsTmp, 'r').read()
	elif world.minifyMethod == 'roadroller':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += 'var D=`' + datas + '`\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + colors + '`\n' + JS_SUFFIX
		open(jsTmp, 'w').write(js)
		cmd = ['npx', 'roadroller', jsTmp, '-o', jsTmp]
		print(' '.join(cmd))
		subprocess.check_call(cmd)
		js = open(jsTmp, 'r').read()
	else:
		js += '\nvar D=`' + datas + '`;\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + colors + '`\n' + JS_SUFFIX.replace('\t', '')
	return js

def GenHtml (world, datas, background = ''):
	global userJS, colors, initCode, updateCode, pathsDatas
	js = GenJsAPI(world)
	if background:
		background = 'background-color:%s;' %background
	o = [
		'<!DOCTYPE html>',
		'<html>',
		'<body style="%swidth:600px;height:300px;overflow:hidden">' %background,
		''.join(svgsDatas.values()),
		'<script type="module">',
		js,
		'</script>'
	]
	htmlSize = len('\n'.join(o))
	buildInfo['js-size'] = len(js)
	if not world.invalidHtml:
		o += [
			'</body>',
			'</html>',
		]
		htmlSize += len('</body></html>')
	buildInfo['html-size'] = htmlSize
	return '\n'.join(o)

SERVER_PROC = None

def PreBuild ():
	for ob in bpy.data.objects:
		if '_Clone' in ob.name:
			for child in ob.children:
				bpy.data.objects.remove(child, do_unlink = True)
			bpy.data.objects.remove(ob, do_unlink = True)

def PostBuild ():
	if os.path.isfile('SlimeJump.py') and bpy.data.filepath.endswith('Slime Jump.blend'):
		import SlimeJump as slimeJump
		slimeJump.GenLevel ()

def BuildHtml (world):
	global SERVER_PROC
	if SERVER_PROC:
		SERVER_PROC.kill()
	PreBuild ()
	bpy.context.scene.export_svg_output = TMP_DIR + '/Output.svg'
	blenderInfo = GetBlenderData()
	datas = blenderInfo[0]
	html = GenHtml(world, datas)
	open(TMP_DIR + '/index.html', 'w').write(html)
	if world.js13kbjam:
		if os.path.isfile('/usr/bin/zip'):
			cmd = ['zip', '-9', 'index.html.zip', 'index.html']
			print(' '.join(cmd))
			subprocess.check_call(cmd, cwd = TMP_DIR)

			zip = open(TMP_DIR + '/index.html.zip','rb').read()
			buildInfo['zip-size'] = len(zip)
			if world.exportZip:
				out = os.path.expanduser(world.exportZip)
				if not out.endswith('.zip'):
					out += '.zip'
				buildInfo['zip'] = out
				print('Saving:', out)
				open(out, 'wb').write(zip)
			else:
				buildInfo['zip'] = TMP_DIR + '/index.html.zip'
		else:
			if len(html.encode('utf-8')) > 1024 * 13:
				raise SyntaxError('HTML is over 13kb')
	if world.exportHtml:
		out = os.path.expanduser(world.exportHtml)
		print('Saving:', out)
		open(out,'w').write(html)
		webbrowser.open(out)

	else:
		cmd = ['python', '-m', 'http.setAttributerver', '6969']
		SERVER_PROC = subprocess.Popen(cmd, cwd = TMP_DIR)

		atexit.register(lambda: SERVER_PROC.kill())
		webbrowser.open('http://localhost:6969')
	PostBuild ()
	return html

def BuildUnity (world):
	PreBuild ()
	assetsPath = os.path.join(world.unityProjPath, 'Assets')
	svgsExportPath = os.path.join(assetsPath, 'Art', 'Svgs')
	MakeFolderForFile (os.path.join(svgsExportPath, ''))
	for ob in bpy.data.objects:
		if ob.type == 'CURVE':
			bpy.ops.object.select_all(action = 'DESELECT')
			ob.select_set(True)
			bpy.context.scene.export_svg_output = os.path.join(svgsExportPath, ob.name + '.svg')
			bpy.ops.curve.export_svg()
	scenesPath = os.path.join(assetsPath, 'Scenes')
	scenePath = os.path.join(scenesPath, 'Test.unity')
	MakeFolderForFile (scenePath)
	scriptsPath = os.path.join(assetsPath, 'Scripts', 'Editor')
	makeSceneScriptPath = os.path.join(scriptsPath, 'MakeScene.cs')
	MakeFolderForFile (makeSceneScriptPath)
	MakeFolderForFile (os.path.join(scriptsPath, ''))
	CopyFile (os.path.join(UNITY_SCRIPTS_PATH, 'MakeScene.cs'), makeSceneScriptPath)
	for extensionsScript in GetAllFilePathsOfType(EXTENSIONS_SCRIPTS_PATH, '.cs'):
		CopyFile (extensionsScript, os.path.join(scriptsPath, extensionsScript[extensionsScript.rfind('/') + 1:]))
	if sys.platform == 'win32':
		unityVersionsPath = os.path.join('/', 'Program Files', 'Unity', 'Hub', 'Editor')
	else:
		unityVersionsPath = os.path.expanduser(os.path.join('~', 'Unity', 'Hub', 'Editor'))
	unityVersionPath = ''
	if os.path.isdir(unityVersionsPath):
		unityVersions = os.listdir(unityVersionsPath)
		for unityVersion in unityVersions:
			unityVersionPath = unityVersionsPath + '/' + unityVersion + '/Editor/Unity'
			if os.path.isfile(unityVersionPath):
				break
	if unityVersionPath == '':
		print('No Unity version installed')
		return
	cmd = unityVersionPath + ' -quit -createProject ' + world.unityProjPath + ' -executeMethod MakeScene.Do'
	subprocess.check_call(cmd.split())
	cmd = unityVersionPath + ' -createProject ' + world.unityProjPath
	subprocess.check_call(cmd.split())
	# scene = UnityDocument.load_yaml(scenePath)
	# print(scene.entries)
	# print(scene.entry)
	# entries = scene.filter(class_names = ('MonoBehaviour'), attributes = ('m_Enabled'))
	# for entry in entries:
	# 	entry.m_Enabled = 1
	# scene.dump_yaml()
	# print(scene.entry.__class__.__name__)
	# print(scene.entry.anchor)
	PostBuild ()

def DrawCollidersCallback (self, context):
	gpu.state.blend_set('ALPHA')
	gpu.state.line_width_set(2)
	shader = gpu.shader.from_builtin('UNIFORM_COLOR')
	shader.bind()
	for ob in self.objects:
		if not ob.colliderExists:
			continue
		matrix = ob.matrix_world
		color = (0.2, 1.0, 0.2, 0.8)
		shader.uniform_float('color', color)
		if ob.shapeType == 'ball':
			radius = ob.radius
			segments = 32
			localVerts = []
			for i in range(segments + 1):
				ang = (i / segments) * 2 * math.pi
				localVerts.append(Vector((radius * math.cos(ang), radius * math.sin(ang), 0)))
			worldVerts = [matrix @ v for v in localVerts]
			batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : worldVerts})
			batch.draw(shader)
		elif ob.shapeType == 'cuboid':
			min, max = -Vector((ob.size[0], ob.size[1], 0)) / 2, Vector((ob.size[0], ob.size[1], 0)) / 2
			verts = [matrix @ v for v in [min, Vector((min.x, max.y, 0)), max, Vector((max.x, min.y, 0))]]
			idxs = (
				(0, 1), (1, 2), (2, 3), (3, 0),
				(4, 5), (5, 6), (6, 7), (7, 4)
			)
			batch = batch_for_shader(shader, 'LINES', {'pos' : verts}, indices = idxs)
			batch.draw(shader)
		elif ob.shapeType == 'capsule':
			radius = ob.capsuleRadius
			height = ob.capsuleHeight / 2
			segments = 32
			top = Vector((0, 0, height))
			bottom = Vector((0, 0, -height))
			for i in range(4):
				ang = (i / 4) * 2 * math.pi
				x, y = radius * math.cos(ang), radius * math.sin(ang)
				p1 = matrix @ (top + Vector((x, y, 0)))
				p2 = matrix @ (bottom + Vector((x, y, 0)))
				batch = batch_for_shader(shader, 'LINES', {'pos': [p1, p2]})
				batch.draw(shader)
			for h in [height, -height]:
				localVerts = []
				for i in range(segments + 1):
					ang = (i / segments) * 2 * math.pi
					x, y = radius * math.cos(ang), radius * math.sin(ang)
					localVerts.append(matrix @ (Vector((x, y, h))))
				batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : localVerts})
				batch.draw(shader)
				for axis in ['x', 'y']:
					localVerts = []
					for i in range(int(segments / 2) + 1):
						ang = (i / segments) * math.pi
						if axis == 'x':
							x_, y_, z_ = 0, radius * math.cos(ang), radius * math.sin(ang)
						else:
							x_, y_, z_ = radius * math.cos(ang), 0, radius * math.sin(ang)
						if h > 0:
							localVerts.append(matrix @ (Vector((x_, y_, z_)) + top))
						else:
							localVerts.append(matrix @ (Vector((x_, y_, -z_)) + bottom))
					batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : localVerts})
					batch.draw(shader)
	gpu.state.blend_set('NONE')

def Update ():
	for ob in bpy.data.objects:
		for matSlot in ob.material_slots:
			mat = matSlot.material
			if mat:
				mat.use_nodes = False
	for txt in bpy.data.texts:
		idxOfPeriod = txt.name.find('.')
		if idxOfPeriod != -1:
			for ob in bpy.data.objects:
				for i in range(MAX_SCRIPTS_PER_OBJECT):
					attachedTxt = getattr(ob, 'apiScript%s' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(ob, 'apiScript%s' %i, origTxt)
								break
					attachedTxt = getattr(ob, 'runtimeScript%s' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(ob, 'runtimeScript%s' %i, origTxt)
								break
			bpy.data.texts.remove(txt)
	return 0.1

CAP_TYPES = ['butt', 'round', 'square']
CAP_TYPE_ITEMS = [('butt', 'butt', ''), ('round', 'round', ''), ('square', 'square', '')]
JOIN_TYPES = ['arcs', 'bevl', 'miter', 'miter-clip', 'round']
JOIN_TYPE_ITEMS = [('arcs', 'arcs', ''), ('bevel', 'bevel', ''), ('miter', 'miter', ''), ('miter-clip', 'miter-clip', ''), ('round', 'round', '')]
MINIFY_METHOD_ITEMS = [('none', 'none', ''), ('terser', 'terser', ''), ('roadroller', 'roadroller', '')]
SHAPE_TYPE_ITEMS = [('ball', 'circle', ''), ('halfspace', 'half-space', ''), ('cuboid', 'rectangle', ''), ('roundCuboid', 'rounded-rectangle', ''), ('capsule', 'capsule', ''), ('segment', 'segment', ''), ('triangle', 'triangle', ''), ('roundTriangle', 'rounded-triangle', ''), ('polyline', 'segment-series', ''), ('trimesh', 'triangle-mesh', ''), ('convexHull', 'convex-polygon', ''), ('roundConvexHull', 'rounded-convex-polygon', ''), ('heightfield', 'heightfield', ''), ]
RIGID_BODY_TYPE_ITEMS = [('dynamic', 'dynamic', ''), ('fixed', 'fixed', ''), ('kinemaitcPositionBased', 'kinemaitc-position-based', ''), ('kinemaitcVelocityBased', 'kinemaitc-velocity-based', '')]
JOINT_TYPE_ITEMS = [('fixed', 'fixed', ''), ('', '', ''), ('spring', 'spring', ''), ('revolute', 'revolute', ''), ('prismatic', 'prismatic', ''), ('rope', 'rope', '')]

bpy.types.World.exportScale = bpy.props.FloatProperty(name = 'Scale', default = 1)
bpy.types.World.exportOffsetX = bpy.props.IntProperty(name = 'Offset X')
bpy.types.World.exportOffsetY = bpy.props.IntProperty(name = 'Offset Y')
bpy.types.World.exportHtml = bpy.props.StringProperty(name = 'Export .html')
bpy.types.World.exportZip = bpy.props.StringProperty(name = 'Export .zip')
bpy.types.World.unityProjPath = bpy.props.StringProperty(name = 'Unity project path', default = TMP_DIR + '/TestUnityProject')
bpy.types.World.minifyMethod = bpy.props.EnumProperty(name = 'Minify using library', items = MINIFY_METHOD_ITEMS)
bpy.types.World.js13kbjam = bpy.props.BoolProperty(name = 'Error on export if output is over 13kb')
bpy.types.World.invalidHtml = bpy.props.BoolProperty(name = 'Save space with invalid html wrapper')
bpy.types.Object.roundPosAndSize = bpy.props.BoolProperty(name = 'Round position and size', default = True)
bpy.types.Object.origin = bpy.props.FloatVectorProperty(name = 'Origin', size = 2, default = [50, 50])
bpy.types.Object.collide = bpy.props.BoolProperty(name = 'Collide')
bpy.types.Object.useStroke = bpy.props.BoolProperty(name = 'Use stroke')
bpy.types.Object.strokeWidth = bpy.props.FloatProperty(name = 'Stroke width')
bpy.types.Object.strokeClr = bpy.props.FloatVectorProperty(name = 'Stroke color', subtype = 'COLOR', size = 4, default = [0, 0, 0, 0])
bpy.types.Object.capType = bpy.props.EnumProperty(name = 'Stroke cap type', items = CAP_TYPE_ITEMS)
bpy.types.Object.joinType = bpy.props.EnumProperty(name = 'Stroke corner type', items = JOIN_TYPE_ITEMS)
bpy.types.Object.dashLengthsAndSpaces = bpy.props.FloatVectorProperty(name = 'Stroke dash lengths and spaces', size = 5, min = 0)
bpy.types.Object.mirrorX = bpy.props.BoolProperty(name = 'Mirror on x-axis')
bpy.types.Object.mirrorY = bpy.props.BoolProperty(name = 'Mirror on y-axis')
bpy.types.Object.useJiggle = bpy.props.BoolProperty(name = 'Use jiggle')
bpy.types.Object.jiggleDist = bpy.props.FloatProperty(name = 'Jiggle distance', min = 0)
bpy.types.Object.jiggleDur = bpy.props.FloatProperty(name = 'Jiggle duration', min = 0)
bpy.types.Object.jiggleFrames = bpy.props.IntProperty(name = 'Jiggle frames', min = 0)
bpy.types.Object.useRotate = bpy.props.BoolProperty(name = 'Use rotate')
bpy.types.Object.rotPingPong = bpy.props.BoolProperty(name = 'Ping pong rotate')
bpy.types.Object.rotAngRange = bpy.props.FloatVectorProperty(name = 'Rotate angle range', size = 2)
bpy.types.Object.rotDur = bpy.props.FloatProperty(name = 'Rotate duration', min = 0)
bpy.types.Object.useScale = bpy.props.BoolProperty(name = 'Use scale')
bpy.types.Object.scalePingPong = bpy.props.BoolProperty(name = 'Ping pong scale')
bpy.types.Object.scaleXRange = bpy.props.FloatVectorProperty(name = 'X scale range', size = 2)
bpy.types.Object.scaleYRange = bpy.props.FloatVectorProperty(name = 'Y scale range', size = 2)
bpy.types.Object.scaleDur = bpy.props.FloatProperty(name = 'Scale duration', min = 0)
bpy.types.Object.scaleHaltDurAtMin = bpy.props.FloatProperty(name = 'Halt duration at min', min = 0)
bpy.types.Object.scaleHaltDurAtMax = bpy.props.FloatProperty(name = 'Halt duration at max', min = 0)
bpy.types.Object.cycleDur = bpy.props.FloatProperty(name = 'Cycle stroke duration')
bpy.types.Object.color2 = bpy.props.FloatVectorProperty(name = 'Color 2', subtype = 'COLOR', size = 4, default = [0, 0, 0, 0])
bpy.types.Object.color3 = bpy.props.FloatVectorProperty(name = 'Color 3', subtype = 'COLOR', size = 4, default = [0, 0, 0, 0])
bpy.types.Object.color1Alpha = bpy.props.FloatProperty(name = 'Color 1 alpha', min = 0, max = 1, default = 1)
bpy.types.Object.colorPositions = bpy.props.IntVectorProperty(name = 'Color Positions', size = 3, min = 0, max = 100, default = [0, 50, 100])
bpy.types.Object.subtractive = bpy.props.BoolProperty(name = 'Is subtractive')
bpy.types.Object.useFillHatch = bpy.props.BoolVectorProperty(name = 'Use fill hatch', size = 2)
bpy.types.Object.fillHatchDensity = bpy.props.FloatVectorProperty(name = 'Fill hatch density', size = 2, min = 0)
bpy.types.Object.fillHatchRandDensity = bpy.props.FloatVectorProperty(name = 'Fill hatch randomize density percent', size = 2, min = 0)
bpy.types.Object.fillHatchAng = bpy.props.FloatVectorProperty(name = 'Fill hatch angle', size = 2, min = -360, max = 360)
bpy.types.Object.fillHatchWidth = bpy.props.FloatVectorProperty(name = 'Fill hatch width', size = 2, min = 0)
bpy.types.Object.useStrokeHatch = bpy.props.BoolVectorProperty(name = 'Use stroke hatch', size = 2)
bpy.types.Object.strokeHatchDensity = bpy.props.FloatVectorProperty(name = 'Stroke hatch density', size = 2, min = 0)
bpy.types.Object.strokeHatchRandDensity = bpy.props.FloatVectorProperty(name = 'Stroke hatch randomize density percent', size = 2, min = 0)
bpy.types.Object.strokeHatchAng = bpy.props.FloatVectorProperty(name = 'Stroke hatch angle', size = 2, min = -360, max = 360)
bpy.types.Object.strokeHatchWidth = bpy.props.FloatVectorProperty(name = 'Stroke hatch width', size = 2, min = 0)
bpy.types.Object.minPathFrame = bpy.props.IntProperty(name = 'Min frame for shape animation')
bpy.types.Object.maxPathFrame = bpy.props.IntProperty(name = 'Max frame for shape animation')
bpy.types.Object.minPosFrame = bpy.props.IntProperty(name = 'Min frame for position animation')
bpy.types.Object.maxPosFrame = bpy.props.IntProperty(name = 'Max frame for position animation')
bpy.types.Object.posPingPong = bpy.props.BoolProperty(name = 'Ping pong position animation')
bpy.types.Object.colliderExists = bpy.props.BoolProperty(name = 'Exists')
bpy.types.Object.colliderEnable = bpy.props.BoolProperty(name = 'Enable', default = True)
bpy.types.Object.shapeType = bpy.props.EnumProperty(name = 'Shape type', items = SHAPE_TYPE_ITEMS)
bpy.types.Object.radius = bpy.props.FloatProperty(name = 'Radius', min = 0)
bpy.types.Object.normal = bpy.props.FloatVectorProperty(name = 'Normal', size = 2)
bpy.types.Object.size = bpy.props.FloatVectorProperty(name = 'Size', size = 2, min = 0)
bpy.types.Object.cuboidBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0)
bpy.types.Object.capsuleHeight = bpy.props.FloatProperty(name = 'Height', min = 0)
bpy.types.Object.capsuleRadius = bpy.props.FloatProperty(name = 'Radius', min = 0)
bpy.types.Object.segmentPos1 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2)
bpy.types.Object.segmentPos2 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2)
bpy.types.Object.segmentPos1 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2)
bpy.types.Object.trianglePos1 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2)
bpy.types.Object.trianglePos2 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2)
bpy.types.Object.trianglePos3 = bpy.props.FloatVectorProperty(name = 'Position 3', size = 2)
bpy.types.Object.triangleBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0)
bpy.types.Object.roundConvexHullBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0)
bpy.types.Object.heightfieldScale = bpy.props.FloatVectorProperty(name = 'Scale', size = 2)
bpy.types.Object.density = bpy.props.FloatProperty(name = 'Density', min = 0)
bpy.types.Object.rigidBodyExists = bpy.props.BoolProperty(name = 'Exists')
bpy.types.Object.rigidBodyEnable = bpy.props.BoolProperty(name = 'Enable', default = True)
bpy.types.Object.rigidBodyType = bpy.props.EnumProperty(name = 'Type', items = RIGID_BODY_TYPE_ITEMS)
bpy.types.Object.linearDrag = bpy.props.FloatProperty(name = 'Linear drag', min = 0)
bpy.types.Object.angDrag = bpy.props.FloatProperty(name = 'Angular drag', min = 0)
bpy.types.Object.dominance = bpy.props.IntProperty(name = 'Dominance', min = -127, max = 127)
bpy.types.Object.continuousCollideDetect = bpy.props.BoolProperty(name = 'Continuous collision detection')
bpy.types.Object.gravityScale = bpy.props.FloatProperty(name = 'Gravity scale', default = 1)
bpy.types.Object.canSleep = bpy.props.BoolProperty(name = 'Can sleep', default = True)
bpy.types.Object.canRotate = bpy.props.BoolProperty(name = 'Can rotate', default = True)
bpy.types.Object.jointExists = bpy.props.BoolProperty(name = 'Exists')
bpy.types.Object.jointType = bpy.props.EnumProperty(name = 'Type', items = JOINT_TYPE_ITEMS)
bpy.types.Object.anchorPos1 = bpy.props.FloatVectorProperty(name = 'Anchor position 1', size = 2)
bpy.types.Object.anchorPos2 = bpy.props.FloatVectorProperty(name = 'Anchor position 2', size = 2)
bpy.types.Object.anchorRot1 = bpy.props.FloatProperty(name = 'Anchor rotation 1', min = 0, max = 360)
bpy.types.Object.anchorRot2 = bpy.props.FloatProperty(name = 'Anchor rotation 2', min = 0, max = 360)
bpy.types.Object.anchorRigidBody1 = bpy.props.PointerProperty(name = 'Anchor rigid body 1', type = bpy.types.Object)
bpy.types.Object.anchorRigidBody2 = bpy.props.PointerProperty(name = 'Anchor rigid body 2', type = bpy.types.Object)
bpy.types.Object.restLen = bpy.props.FloatProperty(name = 'Rest length', min = 0)
bpy.types.Object.stiffness = bpy.props.FloatProperty(name = 'Stiffness', min = 0)
bpy.types.Object.damping = bpy.props.FloatProperty(name = 'Damping', min = 0)
bpy.types.Object.jointAxis = bpy.props.FloatVectorProperty(name = 'Axis', size = 2)
bpy.types.Object.jointLen = bpy.props.FloatProperty(name = 'Length', min = 0)
bpy.types.Object.charControllerExists = bpy.props.BoolProperty(name = 'Exists')
bpy.types.Object.contactOff = bpy.props.FloatProperty(name = 'Contact offset', min = 0)
bpy.types.Object.lightFill = bpy.props.PointerProperty(name = 'Fill with light', type = bpy.types.Light)

for i in range(MAX_SCRIPTS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'apiScript%s' %i,
		bpy.props.PointerProperty(name = 'API script%s' %i, type = bpy.types.Text)
	)
	setattr(
		bpy.types.Object,
		'apiScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable')
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%s' %i,
		bpy.props.PointerProperty(name = 'Runtime script%s' %i, type = bpy.types.Text)
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable')
	)
	setattr(
		bpy.types.Object,
		'initScript%s' %i,
		bpy.props.BoolProperty(name = 'Is init')
	)
MAX_SHAPE_POINTS = 32
for i in range(MAX_SHAPE_POINTS):
	setattr(
		bpy.types.Object,
		'polylinePoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2)
	)
	setattr(
		bpy.types.Object,
		'usePolylinePoint%s' %i,
		bpy.props.BoolProperty(name = 'Include%s' %i)
	)
	setattr(
		bpy.types.Object,
		'polylineIdx%s' %i,
		bpy.props.IntProperty(name = 'Index%s' %i, min = -1, default = -1)
	)
	setattr(
		bpy.types.Object,
		'trimeshPoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2)
	)
	setattr(
		bpy.types.Object,
		'useTrimeshPoint%s' %i,
		bpy.props.BoolProperty(name = 'Include%s' %i)
	)
	setattr(
		bpy.types.Object,
		'trimeshIdx%s' %i,
		bpy.props.IntProperty(name = 'Index%s' %i, min = -1, default = -1)
	)
	setattr(
		bpy.types.Object,
		'convexHullPoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2)
	)
	setattr(
		bpy.types.Object,
		'useConvexHullPoint%s' %i,
		bpy.props.BoolProperty(name = 'Include%s' %i)
	)
	setattr(
		bpy.types.Object,
		'roundConvexHullPoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2)
	)
	setattr(
		bpy.types.Object,
		'useRoundConvexHullPoint%s' %i,
		bpy.props.BoolProperty(name = 'Include%s' %i)
	)
	setattr(
		bpy.types.Object,
		'height%s' %i,
		bpy.props.FloatProperty(name = 'Point%s' %i)
	)
	setattr(
		bpy.types.Object,
		'useHeight%s' %i,
		bpy.props.BoolProperty(name = 'Include%s' %i)
	)
MAX_ATTACH_COLLIDER_CNT = 64
for i in range(MAX_ATTACH_COLLIDER_CNT):
	setattr(
		bpy.types.Object,
		'attachTo%s' %i,
		bpy.props.PointerProperty(name = 'Rigid body%s' %i, type = bpy.types.Object)
	)
	setattr(
		bpy.types.Object,
		'attach%s' %i,
		bpy.props.BoolProperty(name = 'Attach to rigid body%s' %i)
	)

@bpy.utils.register_class
class HTMLExport (bpy.types.Operator):
	bl_idname = 'world.html_export'
	bl_label = 'Export to HTML'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		BuildHtml (context.world)
		return { 'FINISHED' }

@bpy.utils.register_class
class UnityExport (bpy.types.Operator):
	bl_idname = 'world.unity_export'
	bl_label = 'Export to Unity'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		BuildUnity (context.world)
		return { 'FINISHED' }

@bpy.utils.register_class
class WorldPanel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_World_Panel'
	bl_label = 'Export'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, context):
		row = self.layout.row()
		row.prop(context.world, 'exportScale')
		row = self.layout.row()
		row.prop(context.world, 'exportOffsetX')
		row.prop(context.world, 'exportOffsetY')
		self.layout.prop(context.world, 'exportHtml')
		self.layout.prop(context.world, 'unityProjPath')
		self.layout.operator('world.html_export', icon = 'CONSOLE')
		self.layout.operator('world.unity_export', icon = 'CONSOLE')

@bpy.utils.register_class
class JS13KB_Panel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_JS13KB_Panel'
	bl_label = 'js13kgames.com'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, context):
		self.layout.prop(context.world, 'js13kbjam')
		row = self.layout.row()
		row.prop(context.world, 'minifyMethod')
		row.prop(context.world, 'invalidHtml')
		if context.world.js13kbjam:
			self.layout.prop(context.world, 'exportZip')
			if buildInfo['zip-size']:
				self.layout.label(text = buildInfo['zip'])
				if buildInfo['zip-size'] <= 1024*13:
					self.layout.label(text = 'zip bytes=%s' %( buildInfo['zip-size'] ))
				else:
					self.layout.label(text = 'zip KB=%s' %( buildInfo['zip-size'] / 1024 ))
				self.layout.label(text = 'html-size=%s' %buildInfo['html-size'])
				self.layout.label(text = 'js-size=%s' %buildInfo['js-size'])
				self.layout.label(text = 'js-gz-size=%s' %buildInfo['js-gz-size'])
		if buildInfo['html-size']:
			self.layout.label(text = buildInfo['html'])
			if buildInfo['html-size'] < 1024*16:
				self.layout.label(text = 'html bytes=%s' %( buildInfo['html-size'] ))
			else:
				self.layout.label(text = 'html KB=%s' %( buildInfo['html-size'] / 1024 ))

@bpy.utils.register_class
class ObjectPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Object_Panel'
	bl_label = 'Object'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, context):
		ob = context.active_object
		if not ob:
			return
		if ob.type == 'CURVE' or ob.type == 'MESH' or ob.type == 'GREASEPENCIL':
			self.layout.prop(ob, 'roundPosAndSize')
			self.layout.prop(ob, 'origin')
			self.layout.prop(ob, 'useStroke')
			if ob.useStroke:
				self.layout.prop(ob, 'strokeWidth')
				self.layout.prop(ob, 'strokeClr')
				self.layout.prop(ob, 'capType')
				self.layout.prop(ob, 'joinType')
				self.layout.prop(ob, 'dashLengthsAndSpaces')
			self.layout.prop(ob, 'lightFill')
			self.layout.prop(ob, 'useFillHatch')
			if ob.useFillHatch:
				self.layout.prop(ob, 'fillHatchDensity')
				self.layout.prop(ob, 'fillHatchRandDensity')
				self.layout.prop(ob, 'fillHatchAng')
				self.layout.prop(ob, 'fillHatchWidth')
			self.layout.prop(ob, 'useStrokeHatch')
			if ob.useStrokeHatch:
				self.layout.prop(ob, 'strokeHatchDensity')
				self.layout.prop(ob, 'strokeHatchRandDensity')
				self.layout.prop(ob, 'strokeHatchAng')
				self.layout.prop(ob, 'strokeHatchWidth')
			self.layout.prop(ob, 'mirrorX')
			self.layout.prop(ob, 'mirrorY')
			self.layout.label(text = 'Animation')
			self.layout.label(text = 'Jiggle')
			self.layout.prop(ob, 'useJiggle')
			if ob.useJiggle:
				self.layout.prop(ob, 'jiggleDist')
				self.layout.prop(ob, 'jiggleDur')
				self.layout.prop(ob, 'jiggleFrames')
			self.layout.label(text = 'Rotate')
			self.layout.prop(ob, 'useRotate')
			if ob.useRotate:
				self.layout.prop(ob, 'rotPingPong')
				self.layout.prop(ob, 'rotAngRange')
				self.layout.prop(ob, 'rotDur')
			self.layout.label(text = 'Scale')
			self.layout.prop(ob, 'useScale')
			if ob.useScale:
				self.layout.prop(ob, 'scalePingPong')
				self.layout.prop(ob, 'scaleXRange')
				self.layout.prop(ob, 'scaleYRange')
				self.layout.prop(ob, 'scaleDur')
				self.layout.prop(ob, 'scaleHaltDurAtMin')
				self.layout.prop(ob, 'scaleHaltDurAtMax')
			if ob.useStroke:
				self.layout.label(text = 'Cycle')
				self.layout.prop(ob, 'cycleDur')
			self.layout.label(text = 'Custom')
			self.layout.prop(ob, 'minPathFrame')
			self.layout.prop(ob, 'maxPathFrame')
			self.layout.prop(ob, 'minPosFrame')
			self.layout.prop(ob, 'maxPosFrame')
			self.layout.prop(ob, 'posPingPong')
		self.layout.label(text = 'Scripts')
		foundUnassignedScript = False
		for i in range(MAX_SCRIPTS_PER_OBJECT):
			hasProp = getattr(ob, 'apiScript%s' %i)
			if hasProp or not foundUnassignedScript:
				row = self.layout.row()
				row.prop(ob, 'apiScript%s' %i)
				row.prop(ob, 'apiScript%sDisable' %i)
			if not foundUnassignedScript:
				foundUnassignedScript = not hasProp
		foundUnassignedScript = False
		for i in range(MAX_SCRIPTS_PER_OBJECT):
			hasProp = getattr(ob, 'runtimeScript%s' %i)
			if hasProp or not foundUnassignedScript:
				row = self.layout.row()
				row.prop(ob, 'runtimeScript%s' %i)
				row.prop(ob, 'initScript%s' %i)
				row.prop(ob, 'runtimeScript%sDisable' %i)
			if not foundUnassignedScript:
				foundUnassignedScript = not hasProp

@bpy.utils.register_class
class LightPanel (bpy.types.Panel):
	bl_idname = 'LIGHT_PT_Light_Panel'
	bl_label = 'Gradient'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'data'

	def draw (self, context):
		ob = context.active_object
		if not ob or ob.type != 'LIGHT':
			return
		self.layout.prop(ob, 'color2')
		self.layout.prop(ob, 'color3')
		self.layout.prop(ob, 'color1Alpha')
		self.layout.prop(ob, 'colorPositions')
		self.layout.prop(ob, 'subtractive')

@bpy.utils.register_class
class RigidBodyPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Rigid_Body_Panel'
	bl_label = 'Rigid Body'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, context):
		ob = context.active_object
		if not ob:
			return
		self.layout.prop(ob, 'rigidBodyExists')
		if not ob.rigidBodyExists:
			return
		self.layout.prop(ob, 'rigidBodyEnable')
		self.layout.prop(ob, 'rigidBodyType')
		self.layout.prop(ob, 'linearDrag')
		self.layout.prop(ob, 'angDrag')
		self.layout.prop(ob, 'dominance')
		self.layout.prop(ob, 'continuousCollideDetect')
		self.layout.prop(ob, 'gravityScale')
		self.layout.prop(ob, 'canSleep')
		self.layout.prop(ob, 'canRotate')

@bpy.utils.register_class
class ColliderPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Collider_Panel'
	bl_label = 'Collider'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, context):
		ob = context.active_object
		if not ob:
			return
		self.layout.prop(ob, 'colliderExists')
		if not ob.colliderExists:
			return
		self.layout.prop(ob, 'colliderEnable')
		self.layout.prop(ob, 'shapeType')
		if ob.shapeType == 'ball':
			self.layout.prop(ob, 'radius')
		elif ob.shapeType == 'halfspace':
			self.layout.prop(ob, 'normal')
		elif ob.shapeType == 'cuboid':
			self.layout.prop(ob, 'size')
		elif ob.shapeType == 'roundCuboid':
			self.layout.prop(ob, 'size')
			self.layout.prop(ob, 'cuboidBorderRadius')
		elif ob.shapeType == 'capsule':
			self.layout.prop(ob, 'capsuleHeight')
			self.layout.prop(ob, 'capsuleRadius')
		elif ob.shapeType == 'segment':
			self.layout.prop(ob, 'segmentPos1')
			self.layout.prop(ob, 'segmentPos2')
		elif ob.shapeType == 'triangle':
			self.layout.prop(ob, 'trianglePos1')
			self.layout.prop(ob, 'trianglePos2')
			self.layout.prop(ob, 'trianglePos3')
		elif ob.shapeType == 'roundTriangle':
			self.layout.prop(ob, 'trianglePos1')
			self.layout.prop(ob, 'trianglePos2')
			self.layout.prop(ob, 'trianglePos3')
			self.layout.prop(ob, 'triangleBorderRadius')
		elif ob.shapeType == 'polyline':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'polylinePoint%s' %i)
				row.prop(ob, 'usePolylinePoint%s' %i)
				if not getattr(ob, 'usePolylinePoint%s' %i):
					break
			foundInvalidIdx = False
			for i in range(MAX_SHAPE_POINTS):
				idx = getattr(ob, 'polylineIdx%s' %i)
				validIdx = idx != -1
				if validIdx or not foundInvalidIdx:
					self.layout.prop(ob, 'polylineIdx%s' %i)
				if not foundInvalidIdx:
					foundInvalidIdx = not validIdx
		elif ob.shapeType == 'trimesh':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'trimeshPoint%s' %i)
				row.prop(ob, 'useTrimeshPoint%s' %i)
				if not getattr(ob, 'useTrimeshPoint%s' %i):
					break
			foundInvalidIdx = False
			for i in range(MAX_SHAPE_POINTS):
				idx = getattr(ob, 'trimeshIdx%s' %i)
				validIdx = idx != -1
				if validIdx or not foundInvalidIdx:
					self.layout.prop(ob, 'trimeshIdx%s' %i)
				if not foundInvalidIdx:
					foundInvalidIdx = not validIdx
		elif ob.shapeType == 'convexHull':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'convexHullPoint%s' %i)
				row.prop(ob, 'useConvexHullPoint%s' %i)
				if not getattr(ob, 'useConvexHullPoint%s' %i):
					break
		elif ob.shapeType == 'roundConvexHull':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'roundConvexHullPoint%s' %i)
				row.prop(ob, 'useRoundConvexHullPoint%s' %i)
				if not getattr(ob, 'useRoundConvexHullPoint%s' %i):
					break
			self.layout.prop(ob, 'roundConvexHullBorderRadius')
		elif ob.shapeType == 'heightfield':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'height%s' %i)
				row.prop(ob, 'useHeight%s' %i)
				if not getattr(ob, 'useHeight%s' %i):
					break
			self.layout.prop(ob, 'heightfieldScale')
		self.layout.prop(ob, 'density')
		for i in range(MAX_ATTACH_COLLIDER_CNT):
			row = self.layout.row()
			row.prop(ob, 'attachTo%s' %i)
			row.prop(ob, 'attach%s' %i)
			if not getattr(ob, 'attach%s' %i):
				return

@bpy.utils.register_class
class JointPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Joint_Panel'
	bl_label = 'Joint'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, context):
		ob = context.active_object
		if not ob:
			return
		self.layout.prop(ob, 'jointExists')
		if not ob.jointExists:
			return
		self.layout.prop(ob, 'jointType')
		self.layout.prop(ob, 'anchorRigidBody1')
		self.layout.prop(ob, 'anchorPos1')
		self.layout.prop(ob, 'anchorRigidBody2')
		self.layout.prop(ob, 'anchorPos2')
		if ob.jointType == 'fixed':
			self.layout.prop(ob, 'anchorRot1')
			self.layout.prop(ob, 'anchorRot2')
		elif ob.jointType == 'spring':
			self.layout.prop(ob, 'restLen')
			self.layout.prop(ob, 'stiffness')
			self.layout.prop(ob, 'damping')
		elif ob.jointType == 'prismatic':
			self.layout.prop(ob, 'jointAxis')
		elif ob.jointType == 'rope':
			self.layout.prop(ob, 'jointLen')
			
# @bpy.utils.register_class
class CharacterControllerPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Character_Controller_Panel'
	bl_label = 'Character Controller'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, context):
		ob = context.active_object
		if not ob:
			return
		self.layout.prop(ob, 'charControllerExists')
		if not ob.rigidBodyExists:
			return
		self.layout.prop(ob, 'contactOff')

class DrawColliders (bpy.types.Operator):
	bl_idname = 'view3d.draw_colliders'
	bl_label = 'Draw Colliders'
	handle = None
	isRunning = False

	def modal (self, context, event):
		if not self.isRunning:
			bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
			self.handle = None
			context.area.tag_redraw()
			return {'CANCELLED'}
		context.area.tag_redraw()
		if event.type in {'RIGHTMOUSE', 'ESC'}:
			self.isRunning = False
			return {'PASS_THROUGH'}
		return {'PASS_THROUGH'}

	def invoke (self, context, event):
		if context.area.type == 'VIEW_3D':
			if DrawColliders.handle:
				DrawColliders.isRunning = False
				return {'FINISHED'}
			self.objects = context.selected_objects
			if not self.objects:
				self.report({'INFO'}, 'No objects selected.')
				return {'CANCELLED'}
			args = (self, context)
			DrawColliders.handle = bpy.types.SpaceView3D.draw_handler_add(DrawCollidersCallback, args, 'WINDOW', 'POST_VIEW')
			DrawColliders.isRunning = True
			self.isRunning = True
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, 'View3D not found, cannot run operator')
			return {'CANCELLED'}

class DrawCollidersPanel (bpy.types.Panel):
	bl_label = 'Collider Visualizer'
	bl_idname = 'VIEW3D_PT_collider_visualizer'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tool'

	def draw (self, context):
		layout = self.layout
		if DrawColliders.isRunning:
			layout.operator('view3d.draw_colliders', text = 'Stop Visualizing', depress = True)
		else:
			layout.operator('view3d.draw_colliders', text = 'Visualize Colliders', depress = False)

@bpy.utils.register_class
class ConvertSelectedObjectsToCurves (bpy.types.Operator):
	bl_idname = 'render.convert_to_curves'
	bl_label = 'Convert Selected Objects To Curves'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		scene = bpy.context.scene
		world = bpy.data.worlds[0]
		SCALE = world.exportScale
		offX = world.exportOffsetX
		offY = world.exportOffsetY
		off = Vector((offX, offY))
		renderSettings = scene.render
		imageSettings = renderSettings.image_settings
		viewSettings = imageSettings.view_settings
		prevRenderPath = renderSettings.filepath
		prevTransparentFilm = renderSettings.film_transparent
		prevExposure = viewSettings.exposure
		prevGamma = viewSettings.gamma
		prevRenderFormat = imageSettings.file_format
		prevColorMode = imageSettings.color_mode
		renderSettings.film_transparent = True
		if len(bpy.data.lights) == 0:
			imageSettings.color_management = 'OVERRIDE'
			viewSettings.exposure = 32
			viewSettings.gamma = 5
		imageSettings.file_format = 'BMP'
		imageSettings.color_mode = 'BW'
		depsgraph = bpy.context.evaluated_depsgraph_get()
		prevHideObsInRender = {}
		for ob2 in bpy.data.objects:
			prevHideObsInRender[ob2] = ob.hide_render
			ob2.hide_render = ob != ob2
		# renderResScale = renderSettings.resolution_percentage / 100
		# minHitDists = {}
		# cam = scene.camera
		# camData = cam.data
		# viewFrame = camData.view_frame(scene = scene)
		# viewFrameTopLeft = viewFrame[0]
		# viewFrameTopRight = viewFrame[1]
		# viewFrameBottLeft = viewFrame[2]
		# viewFrameXRange = viewFrameTopRight - viewFrameTopLeft
		# viewFrameYRange = viewFrameBottLeft - viewFrameTopLeft
		# camWorldMatrix = cam.matrix_world
		# camPos = camWorldMatrix.translation
		# renderResolutionX = int(renderSettings.resolution_x * renderResScale)
		# renderResolutionY = int(renderSettings.resolution_y * renderResScale)
		# for ob in bpy.context.selected_objects:
		# 	bvhTree = bvhtree.BVHTree(ob, depsgraph, render = True)
		# 	for x in range(renderResolutionX):
		# 		for y in range(renderResolutionY):
		# 			xNormalized = x / (renderResolutionX - 1)
		# 			yNormalized = y / (renderResolutionY - 1)
		# 			pointOnNearClipPlane = viewFrameTopLeft + viewFrameXRange * xNormalized + viewFrameYRange * yNormalized
		# 			worldPointOnNearClipPlane = camWorldMatrix @ pointOnNearClipPlane
		# 			rayDir = (worldPointOnNearClipPlane - camPos).normalized()
		# 			hitDist = bvhTree.ray_cast(worldPointOnNearClipPlane, rayDir)[3]
		# 			if hitDist:
		# 				pass
		for i, ob in enumerate(bpy.context.selected_objects):
			renderSettings.filepath = os.path.join(TMP_DIR, 'Render' + str(i) + '.bmp')
			renderPaths.append(renderSettings.filepath)
			bpy.ops.render.render(write_still = True)
		for ob in bpy.context.selected_objects:
			ob.hide_render = prevHideObsInRender[ob]
		renderSettings.filepath = prevRenderPath
		renderSettings.film_transparent = prevTransparentFilm
		viewSettings.exposure = prevExposure
		viewSettings.gamma = prevGamma
		imageSettings.file_format = prevRenderFormat
		imageSettings.color_mode = prevColorMode
		cmd = [POTRACE_PATH, '-o ' + os.path.join(TMP_DIR, 'Render.svg'), '-s']
		cmd += renderPaths
		print(' '.join(cmd))
		subprocess.check_call(cmd)
		for i, ob in enumerate(bpy.context.selected_objects):
			svgTxt = open(renderPaths[i].replace('.bmp', '.svg'), 'r').read()
			# print('YAY' + str(i) + svgTxt)
			# idxOfTrsStart = svgTxt.rfind('transform="')
			# trsEndIndctr = '"'
			# idxOfTrsEnd = svgTxt.find(trsEndIndctr, idxOfTrsStart) + len(trsEndIndctr)
			# trs = svgTxt[idxOfTrsStart + len(idxOfTrsStart) : idxOfTrsEnd]
			# min, max = GetRectMinMax(ob)
			# pathDataIndctr = ' d="'
			# idxOfPathDataStart = svgTxt.find(pathDataIndctr) + len(pathDataIndctr)
			# idxOfPathDataEnd = svgTxt.find('"', idxOfPathDataStart)
			# pathData = svgTxt[idxOfPathDataStart : idxOfPathDataEnd]
			# pathData = pathData[: 1] + ' ' + pathData[1 :]
			# pathData = pathData[: -1]
			# pathData = pathData.replace('.0', '')
			# vectors = pathData.split(' ')
			# pathData = []
			# for vector in vectors:
			# 	if len(vector) == 1:
			# 		continue
			# 	components = vector.split(' ')
			# 	x = float(components[0])
			# 	y = float(components[1])
			# 	vector = ob.matrix_world @ Vector((x, y, 0))
			# 	pathData.append(x)
			# 	pathData.append(y)
		return { 'FINISHED' }

@bpy.utils.register_class
class ConvertToCurvesPanel (bpy.types.Panel):
	bl_idname = 'RENDER_PT_Convert_To_Curves_Panel'
	bl_label = 'Convert To Curves'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'render'

	def draw (self, context):
		self.layout.operator('render.convert_to_curves', icon = 'CONSOLE')

classes = (
	DrawColliders,
	DrawCollidersPanel
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	DrawColliders.handle = None
	DrawColliders.is_running = False

def unregister():
	if DrawColliders.handle:
		bpy.types.SpaceView3D.draw_handler_remove(DrawColliders.handle, 'WINDOW')
	DrawColliders.isRunning = False
	DrawColliders.handle = None
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

if __name__ == '__main__':
	register()

for arg in sys.argv:
	if arg.startswith('-o='):
		bpy.data.worlds[0].exportHtml = arg.split('=')[-1]
	elif arg == '-minify':
		bpy.data.worlds[0].minifyMethod = 'terser'
	elif arg == '-js13kjam':
		bpy.data.worlds[0].minifyMethod = 'terser'
		bpy.data.worlds[0].js13kbjam = True
		bpy.data.worlds[0].invalidHtml = True
bpy.app.timers.register(Update)