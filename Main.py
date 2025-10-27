import os, sys, json, string, atexit, webbrowser, subprocess, math
from zipfile import *
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
NO_PHYSICS_INDCTR = '-no_physics'
ON_START_INDCTR = '-on-start='
ON_PRE_BUILD_INDCTR = '-on-pre-build='
ON_POST_BUILD_INDCTR = '-on-post-build='
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
startScriptPath = ''
preBuildScriptPath = ''
postBuildScriptPath = ''
for arg in sys.argv:
	if 'blender' in arg:
		BLENDER = arg
	elif arg.startswith(DONT_MANGLE_INDCTR):
		dontMangleArg = arg
	elif arg == NO_PHYSICS_INDCTR:
		usePhysics = False
	elif arg.startswith(ON_START_INDCTR):
		startScriptPath = arg[len(ON_START_INDCTR) :]
	elif arg.startswith(ON_PRE_BUILD_INDCTR):
		preBuildScriptPath = arg[len(ON_PRE_BUILD_INDCTR) :]
	elif arg.startswith(ON_POST_BUILD_INDCTR):
		postBuildScriptPath = arg[len(ON_POST_BUILD_INDCTR) :]

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
	cmd.append('--')
	for arg in sys.argv:
		if arg.startswith('--') or arg.startswith(DONT_MANGLE_INDCTR) or arg == '-minify':
			cmd.append(arg)
	if startScriptPath != '':
		cmd += ['--python', startScriptPath]
	if preBuildScriptPath != '':
		cmd += [ON_PRE_BUILD_INDCTR + preBuildScriptPath]
	if postBuildScriptPath != '':
		cmd += [ON_POST_BUILD_INDCTR + postBuildScriptPath]
	print(' '.join(cmd))
	subprocess.check_call(cmd)
	sys.exit()

if not bpy:
	if isLinux:
		if not os.path.isfile('/usr/bin/blender'):
			print('Did you install blender 4.5?')
			print('snap install blender --classic')
	else:
		print('Download blender 4.5 from: https://blender.org')
	sys.exit()

MAX_SCRIPTS_PER_OBJECT = 16
MAX_SHAPE_PNTS = 32
MAX_ATTACH_COLLIDER_CNT = 64
MAX_POTRACE_PASSES_PER_OBJECT_MAT = 8
MAX_ATTRIBUTES_PER_OBJECT = 16
MAX_ELTS_IN_ATTRIBUTES_ARR = 16
MAX_RENDER_CAMS_PER_OBJECT = 64

def GetScripts (ob, isAPI : bool):
	scripts = []
	type = 'runtime'
	if isAPI:
		type = 'api'
	for i in range(MAX_SCRIPTS_PER_OBJECT):
		if not getattr(ob, type + 'ScriptDisable%i' %i):
			txt = getattr(ob, type + 'Script%i' %i)
			if txt:
				if isAPI:
					scripts.append((txt.as_string(), getattr(ob, 'apiScriptType%i' %i)))
				else:
					scripts.append((txt.as_string(), getattr(ob, 'initScript%i' %i), getattr(ob, 'runtimeScriptType%i' %i)))
	return scripts

def TryChangeToInt (f : float):
	if int(f) == f:
		return int(f)
	else:
		return f

def Multiply (v : list, multiply : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt * multiply[i])
	return output

def Divide (v : list, divide : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt / divide[i])
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

def Rotate90 (v : Vector, clockwise : bool = True):
	if clockwise:
		return Vector((v.y, -v.x))
	else:
		return Vector((-v.y, v.x))

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

def ToVector2String (prop : bpy.props.FloatVectorProperty):
	return '{x : ' + str(prop[0]) + ', y : ' + str(-prop[1]) + '}'

def GetFileName (filePath : str):
	filePath = filePath.replace('\\', '/')
	return filePath[filePath.rfind('/') + 1 :]

def GetVarNameForObject (ob):
	output = '_' + ob.name
	disallowedChars = ' /\\`~?|!@#$%^&*()[]{}<>=+-;:",.' + "'"
	for disallowedChar in disallowedChars:
		output = output.replace(disallowedChar, '')
	return output

def GetColor (clr : list):
	_clr = ClampComponents(Round(Multiply(clr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
	idxOfClr = IndexOfValue(_clr, clrs)
	keyOfClr = ''
	if idxOfClr == -1:
		keyOfClr = string.ascii_letters[len(clrs)]
		clrs[keyOfClr] = _clr
	else:
		keyOfClr = string.ascii_letters[idxOfClr]
	return keyOfClr

def GetObjectPosition (ob):
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	off = Vector(world.exportOff)
	x, y, z = ob.location * SCALE
	if ob.type == 'LIGHT':
		radius = ob.data.shadow_soft_size
		x -= radius
		y -= radius
	else:
		y = -y
	x += off.x
	y += off.y
	return Round(Vector((x, y)))

DEFAULT_CLR = [0, 0, 0, 0]
VISUALIZER_CLR = (0.2, 1.0, 0.2, 0.8)
exportedObs = []
datas = []
clrs = {}
rigidBodies = {}
colliders = {}
joints = {}
charControllers = {}
pathsDatas = []
imgs = {}
imgsPaths = []
particleSystems = []
initCode = []
updateCode = []
apiCode = ''
svgsDatas = {}
exportType = None
vars = []
attributes = {}
pivots = {}
globals = []
renderCode = []
zOrders = {}

def ExportObject (ob):
	global svgsDatas
	if not ob.export or ob in exportedObs:
		return
	obVarName = GetVarNameForObject(ob)
	_attributes = GetAttributes(ob)
	if _attributes != {}:
		for key, value in _attributes.items():
			_attributes[key] = str(value).replace("'", '"')
		attributes[obVarName] = _attributes
	RegisterPhysics (ob)
	RegisterParticleSystem (ob)
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	off = Vector(world.exportOff)
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
		alpha = round(ob.clr1Alpha * 255)
		clr = Round(Multiply(ob.data.color, [255, 255, 255]))
		data.append(GetColor([clr[0], clr[1], clr[2], alpha]))
		data.append(GetColor(ob.clr2))
		data.append(GetColor(ob.clr3))
		data.append(list(ob.clrPositions))
		data.append(ob.subtractive)
		datas.append(data)
	elif ob.type == 'CURVE':
		tempCollection = bpy.data.collections.new('Temp')
		bpy.context.scene.collection.children.link(tempCollection)
		newCurveData = bpy.data.curves.new(name = 'Temp', type = 'CURVE')
		newOb = bpy.data.objects.new(name = 'Temp', object_data = newCurveData)
		tempCollection.objects.link(newOb)
		prevObName = ob.name
		ob.name += '_'
		if exportType == 'html':
			geoDatas = []
			for frame in range(ob.minPathFrame, ob.maxPathFrame + 1):
				bpy.context.scene.frame_set(frame)
				depsgraph = bpy.context.evaluated_depsgraph_get()
				evaluatedOb = ob.evaluated_get(depsgraph)
				curveData = evaluatedOb.to_curve(depsgraph, apply_modifiers = True)
				spline = curveData.splines[0]
				pnts = spline.bezier_points
				controlPnts = [pnt.co.copy() for pnt in pnts]
				leftHandles = [pnt.handle_left.copy() for pnt in pnts]
				rightHandles = [pnt.handle_right.copy() for pnt in pnts]
				worldMatrix = evaluatedOb.matrix_world.copy()
				geoDatas.append({'controlPnts' : controlPnts, 'leftHandles' : leftHandles, 'rightHandles' : rightHandles, 'cyclic' : spline.use_cyclic_u, 'matrix' : worldMatrix})
			bpy.context.scene.frame_set(prevFrame)
			pathDataFrames = []
			prevPathData = ''
			posFrames = []
			data = []
			prevPos = None
			for frame, geoData in enumerate(geoDatas):
				if frame > 0:
					pos = geoData['matrix'].translation()
					posFrames.append([TryChangeToInt(pos.x - prevPos.x), TryChangeToInt(pos.y - prevPos.y)])
				prevPos = ob.location
			for frame, geoData in enumerate(geoDatas):
				newCurveData.splines.clear()
				newCurveData.splines.new('BEZIER')
				newCurveData.splines[0].bezier_points.add(len(geoData['controlPnts']) - 1)
				for i, pnt in enumerate(geoData['controlPnts']):
					spline = newCurveData.splines[0]
					spline.bezier_points[i].co = pnt
					spline.bezier_points[i].handle_left = geoData['leftHandles'][i]
					spline.bezier_points[i].handle_right = geoData['rightHandles'][i]
				spline.use_cyclic_u = geoData['cyclic']
				newOb.matrix_world = geoData['matrix']
				bpy.ops.object.select_all(action = 'DESELECT')
				newOb.select_set(True)
				bpy.ops.curve.export_svg()
				svgTxt = open(bpy.context.scene.export_svg_output, 'r').read()
				idxOfName = svgTxt.find('"' + newOb.name + '"') + 1
				idxOfGroupStart = svgTxt.rfind('\n', 0, idxOfName)
				groupEndIndctr = '</g>'
				idxOfGroupEnd = svgTxt.find(groupEndIndctr, idxOfGroupStart) + len(groupEndIndctr)
				group = svgTxt[idxOfGroupStart : idxOfGroupEnd]
				parentGroupIndctr = '\n  <g'
				idxOfParentGroupStart = svgTxt.find(parentGroupIndctr)
				idxOfParentGroupContents = svgTxt.find('\n', idxOfParentGroupStart + len(parentGroupIndctr))
				idxOfParentGroupEnd = svgTxt.rfind('</g')
				_min, _max = GetRectMinMax(newOb)
				scale = Vector((sx, sy))
				_min *= scale
				_min += off
				_max *= scale
				_max += off
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
					vector = newOb.matrix_world @ Vector((x, y, 0))
					x = vector.x
					y = vector.y
					minPathVector = GetMinComponents(minPathVector, vector, True)
					maxPathVector = GetMaxComponents(maxPathVector, vector, True)
					pathData.append(x)
					pathData.append(y)
				_off = -minPathVector + Vector((32, 32))
				for i, pathValue in enumerate(pathData):
					if i % 2 == 1:
						pathData[i] = ToByteString(maxPathVector[1] - pathValue + 32)
					else:
						pathData[i] = ToByteString(pathValue + _off[0])
				strokeWidth = 0
				if ob.useStroke:
					strokeWidth = ob.strokeWidth
				jiggleDist = ob.jiggleDist * int(ob.useJiggle)
				x = _min.x - strokeWidth / 2 - jiggleDist
				y = -_max.y + strokeWidth / 2 + jiggleDist
				size = _max - _min
				size += Vector((1, 1)) * (strokeWidth + jiggleDist * 2)
				if ob.roundPosAndSize:
					x = int(round(x))
					y = int(round(y))
					size = Vector(Round(size))
				pathDataStr = ''.join(pathData)
				if frame == 0:
					if HandleCopyObject(newOb, [x, y]):
						break
					posFrames.insert(0, [TryChangeToInt(x), TryChangeToInt(y)])
					data.append(posFrames)
					data.append(ob.posPingPong)
					data.append(TryChangeToInt(size.x))
					data.append(TryChangeToInt(size.y))
					materialClr = DEFAULT_CLR
					if ob.active_material:
						materialClr = ob.active_material.diffuse_color
					data.append(GetColor(materialClr))
					data.append(round(strokeWidth))
					data.append(GetColor(ob.strokeClr))
					data.append(prevObName)
					data.append(spline.use_cyclic_u)
					data.append(round(ob.location.z))
					data.append(GetAttributes(ob))
					data.append(TryChangeToInt(ob.jiggleDist * int(ob.useJiggle)))
					data.append(TryChangeToInt(ob.jiggleDur))
					data.append(ob.jiggleFrames * int(ob.useJiggle))
					data.append(TryChangeToInt(ob.rotAngRange[0]))
					data.append(TryChangeToInt(ob.rotAngRange[1]))
					data.append(TryChangeToInt(ob.rotDur * int(ob.useRot)))
					data.append(ob.rotPingPong)
					data.append(TryChangeToInt(ob.scaleXRange[0]))
					data.append(TryChangeToInt(ob.scaleXRange[1]))
					data.append(TryChangeToInt(ob.scaleYRange[0]))
					data.append(TryChangeToInt(ob.scaleYRange[1]))
					data.append(TryChangeToInt(ob.scaleDur * int(ob.useScale)))
					data.append(TryChangeToInt(ob.scaleHaltDurAtMin * int(ob.useScale)))
					data.append(TryChangeToInt(ob.scaleHaltDurAtMax * int(ob.useScale)))
					data.append(ob.scalePingPong)
					data.append(TryChangeToInt(ob.pivot[0]))
					data.append(TryChangeToInt(ob.pivot[1]))
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
			pathsDatas.append(chr(1).join(pathDataFrames))
		elif exportType == 'exe':
			RenderObject (ob, newOb, lambda : RenderCurve (ob, newOb, os.path.join(TMP_DIR, ob.name)))
		tempCollection.objects.unlink(newOb)
		bpy.data.objects.remove(newOb)
		bpy.data.curves.remove(newCurveData)
		bpy.context.scene.collection.children.unlink(tempCollection)
		bpy.data.collections.remove(tempCollection)
		bpy.data.objects[prevObName + '_'].name = prevObName
	elif ob.type == 'MESH':
		prevObName = ob.name
		ob.name += '_'
		geoDatas = []
		for frame in range(ob.minPathFrame, ob.maxPathFrame + 1):
			bpy.context.scene.frame_set(frame)
			depsgraph = bpy.context.evaluated_depsgraph_get()
			evaluatedOb = ob.evaluated_get(depsgraph)
			meshData = evaluatedOb.to_mesh(preserve_all_data_layers = False, depsgraph = depsgraph)
			verts = [v.co.copy() for v in meshData.vertices]
			faces = [p.vertices[:] for p in meshData.polygons]
			worldMatrix = evaluatedOb.matrix_world.copy()
			geoDatas.append({'verts' : verts, 'faces' : faces, 'matrix' : worldMatrix})
		bpy.context.scene.frame_set(prevFrame)
		tempCollection = bpy.data.collections.new('Temp')
		bpy.context.scene.collection.children.link(tempCollection)
		newMeshData = bpy.data.meshes.new(name = 'Temp')
		newOb = bpy.data.objects.new(name = 'Temp', object_data = newMeshData)
		tempCollection.objects.link(newOb)
		visibleClrValues = []
		tints = []
		minVisibleClrValue = 1
		minVisibleClrValueIdx = 0
		for i in range(MAX_POTRACE_PASSES_PER_OBJECT_MAT):
			if i == 0 or getattr(ob, 'useMinVisibleClrValue%i' %i):
				visibleClrValue = getattr(ob, 'minVisibleClrValue%i' %i)
				if visibleClrValue < minVisibleClrValue:
					visibleClrValues.insert(minVisibleClrValueIdx, visibleClrValue)
					tints.insert(minVisibleClrValueIdx, getattr(ob, 'tintOutput%i' %i))
					minVisibleClrValueIdx = i
					minVisibleClrValue = visibleClrValue
		renderCams = []
		for i in range(MAX_RENDER_CAMS_PER_OBJECT):
			renderCam = getattr(ob, 'renderCam%i' %i)
			if renderCam:
				renderCams.append(renderCam)
		scene = bpy.context.scene
		if renderCams == []:
			renderCams = [scene.camera]
		for matSlotIdx, matSlot in enumerate(ob.material_slots):
			mat = matSlot.material
			if mat:
				newName = prevObName
				if matSlotIdx > 0:
					newName += '_' + mat.name
				newOb.active_material = mat
				for frame, geoData in enumerate(geoDatas):
					newMeshData.clear_geometry()
					newMeshData.from_pydata(geoData['verts'], [], geoData['faces'])
					newMeshData.update()
					newOb.matrix_world = geoData['matrix']
					_min, _max = GetRectMinMax(ob)
					if frame > 0:
						newName = newName.replace('_' + str(frame - 1), '')
						newName += '_' + str(frame)
					elif frame == 0 and HandleCopyObject(newOb, list(_min)):
						break
					prevMatClrs = {}
					for matSlot in ob.material_slots:
						mat2 = matSlot.material
						if mat2 and mat != mat2:
							prevMatClrs[mat2] = mat2.diffuse_color
							mat2.diffuse_color = DEFAULT_CLR
					RenderObject (ob, newOb, lambda : RenderMesh (ob, newOb, renderCams, newName, tints, frame, visibleClrValues, mat, prevMatClrs))
		tempCollection.objects.unlink(newOb)
		bpy.data.objects.remove(newOb)
		bpy.data.meshes.remove(newMeshData)
		scene.collection.children.unlink(tempCollection)
		bpy.data.collections.remove(tempCollection)
		bpy.data.objects[prevObName + '_'].name = prevObName
	elif ob.type == 'GREASEPENCIL':
		_min, _max = GetRectMinMax(ob)
		if HandleCopyObject(ob, list(_min)):
			return
		scene = bpy.context.scene
		renderSettings = scene.render
		imageSettings = renderSettings.image_settings
		viewSettings = imageSettings.view_settings
		prevRenderPath = renderSettings.filepath
		prevResPercent = renderSettings.resolution_percentage
		prevTransparentFilm = renderSettings.film_transparent
		prevExposure = viewSettings.exposure
		prevGamma = viewSettings.gamma
		prevRenderFormat = imageSettings.file_format
		prevClrMode = imageSettings.color_mode
		renderSettings.film_transparent = True
		prevClrManagement = imageSettings.color_management
		prevExposure = viewSettings.exposure
		prevGamma = viewSettings.gamma
		if len(bpy.data.lights) == 0:
			imageSettings.color_management = 'OVERRIDE'
			viewSettings.exposure = 32
			viewSettings.gamma = 5
		imageSettings.file_format = 'BMP'
		imageSettings.color_mode = 'BW'
		world = bpy.data.worlds[0]
		worldClr = world.color
		prevWorldClr = list(worldClr)
		prevMatAlpha = ob.active_material.grease_pencil.color[3]
		ob.active_material.grease_pencil.color = Subtract([1, 1, 1, 1], ob.active_material.grease_pencil.color)
		ob.active_material.grease_pencil.color[3] = prevMatAlpha
		world.color = [0, 0, 0]
		prevObsClrs = {}
		for ob2 in bpy.data.objects:
			if ob2 != ob:
				mat = ob2.active_material
				if mat:
					matClr = mat.diffuse_color
					prevObsClrs[ob2] = list(matClr)
					mat.diffuse_color = DEFAULT_CLR
		cam = scene.camera
		renderSettings.filepath = os.path.join(TMP_DIR, 'Render.bmp')
		renderSettings.resolution_percentage *= ob.resPercent
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
		materialClr = DEFAULT_CLR
		if ob.active_material:
			materialClr = ob.active_material.diffuse_color
		prevMatAlpha = materialClr[3]
		fillClr = Subtract([1, 1, 1, 1], materialClr)
		fillClr[3] = prevMatAlpha
		fillClr = ClampComponents(Round(Multiply(fillClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
		svgTxt = svgTxt[: idxOfFillStart] + 'rgb(' + str(fillClr[0]) + ' ' + str(fillClr[1]) + ' ' + str(fillClr[2]) + ')' + svgTxt[idxOfFillEnd :]
		if ob.useStroke:
			strokeClr = ClampComponents(Round(Multiply(ob.strokeClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
			svgTxt = svgTxt.replace('stroke="none"', 'stroke="rgb(' + str(strokeClr[0]) + ' ' + str(strokeClr[1]) + ' ' + str(strokeClr[2]) + ')" stroke-width=' + str(ob.strokeWidth))
		ob.active_material.grease_pencil.color = Subtract([1, 1, 1, 1], ob.active_material.grease_pencil.color)
		ob.active_material.grease_pencil.color[3] = prevMatAlpha
		world.color = prevWorldClr
		for ob2 in bpy.data.objects:
			if ob2 in prevObsClrs:
				ob2.active_material.diffuse_color = prevObsClrs[ob2]
		renderSettings.filepath = prevRenderPath
		renderSettings.resolution_percentage = prevResPercent
		renderSettings.film_transparent = prevTransparentFilm
		viewSettings.exposure = prevExposure
		viewSettings.gamma = prevGamma
		imageSettings.file_format = prevRenderFormat
		imageSettings.color_mode = prevClrMode
		imageSettings.color_management = prevClrManagement
		svgsDatas[ob.name] = svgTxt
	elif ob.type == 'EMPTY':
		if ob.empty_display_type == 'IMAGE':
			size = ob.scale * ob.empty_display_size
			pos = GetImagePosition(ob)
			pivots[obVarName] = GetPivot(ob)
			if HandleCopyObject(ob, pos):
				return
			obData = ob.data
			imgName = GetFileName(obData.filepath)
			imgPath = TMP_DIR + '/' + imgName
			prevRotMode = ob.rotation_mode
			ob.rotation_mode = 'XYZ'
			img = ''
			if exportType == 'html':
				img = '<img id="' + ob.name + '" src="' + imgName + '" width=' + str(size[0]) + ' height=' + str(size[1]) + ' style="z-index:' + str(round(ob.location.z)) + ';position:absolute;transform:translate(' + str(TryChangeToInt(pos.x)) + 'px,' + str(TryChangeToInt(pos.y)) + 'px)'
				if ob.rotation_euler.z != 0:
					img += 'rotate(' + str(ob.rotation_euler.z) + 'rad)'
				img += ';user-drag:none;-webkit-user-drag:none;user-select:none;-moz-user-select:none;-webkit-user-select:none;-ms-user-select:none'
				if ob.use_empty_image_alpha and ob.color[3] != 1:
					img += ';opacity:' + str(ob.color[3])
				img += '">'
				imgs[ob.name] = img
			elif exportType == 'exe':
				imgSize = Vector(list(ob.data.size) + [0])
				if imgSize.x > imgSize.y:
					size.x *= imgSize.x / imgSize.y
				else:
					size.y *= imgSize.y / imgSize.x
				AddImageDataForExe (ob, imgPath.replace(TMP_DIR, '.'), pos, size, ob.color[3])
			ob.rotation_mode = prevRotMode
			ob.data.save(filepath = imgPath)
			if imgPath not in imgsPaths:
				imgsPaths.append(imgPath)
		else:
			childrenNames = []
			for child in ob.children:
				ExportObject (child)
				childrenNames.append(child.name)
			datas.append([ob.name, TryChangeToInt(ob.location.x), TryChangeToInt(-ob.location.y), childrenNames, GetAttributes(ob)])
	exportedObs.append(ob)

def RegisterPhysics (ob):
	obVarName = GetVarNameForObject(ob)
	rigidBodyName = obVarName + 'RigidBody'
	rigidBodyDescName = rigidBodyName + 'Desc'
	attachColliderTo = []
	for i in range(MAX_ATTACH_COLLIDER_CNT):
		if getattr(ob, 'attach%i' %i):
			attachColliderTo.append(getattr(ob, 'attachTo%i' %i))
	collisionGroupMembership = 0
	for i, enabled in enumerate(ob.collisionGroupMembership):
		if enabled:
			collisionGroupMembership |= (1 << i)
	collisionGroupFilter = 0
	for i, enabled in enumerate(ob.collisionGroupFilter):
		if enabled:
			collisionGroupFilter |= (1 << i)
	prevRotMode = ob.rotation_mode
	ob.rotation_mode = 'XYZ'
	if exportType == 'html':
		if ob.rigidBodyExists:
			rigidBody = 'var ' + rigidBodyDescName + ' = RAPIER.RigidBodyDesc.' + ob.rigidBodyType + '()'
			if ob.location.x != 0 or ob.location.y != 0:
				rigidBody += '.setTranslation(' + str(ob.location.x) + ', ' + str(-ob.location.y) + ')'
			if ob.rotation_euler.z != 0:
				rigidBody += '.setRotation(' + str(ob.rotation_euler.z) + ')'
			if not ob.canRot:
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
			rigidBody += 'rigidBodyDescsIds["' + ob.name + '"] = ' + rigidBodyDescName + ';'
			rigidBodies[ob] = rigidBody
		if ob.colliderExists:
			colliderName = obVarName + 'Collider'
			colliderDescName = colliderName + 'Desc'
			collider = 'var ' + colliderDescName + ' = RAPIER.ColliderDesc.' + ob.colliderShapeType + '('
			if ob.colliderShapeType == 'ball':
				collider += str(ob.colliderRadius)
			elif ob.colliderShapeType == 'halfspace':
				collider += ToVector2String(ob.colliderNormal)
			elif ob.colliderShapeType == 'cuboid':
				collider += str(ob.colliderSize[0] / 2) + ', ' + str(ob.colliderSize[1] / 2)
			elif ob.colliderShapeType == 'roundCuboid':
				collider += str(ob.colliderSize[0] / 2) + ', ' + str(ob.colliderSize[1] / 2) + ', ' + str(ob.colliderCuboidBorderRadius)
			elif ob.colliderShapeType == 'capsule':
				collider += str(ob.colliderCapsuleHeight / 2) + ', ' + str(ob.colliderCapsuleRadius)
			elif ob.colliderShapeType == 'segment':
				collider += ToVector2String(ob.colliderSegmentPnt0) + ', ' + ToVector2String(ob.colliderSegmentPnt1)
			elif ob.colliderShapeType == 'triangle':
				collider += ToVector2String(ob.colliderTrianglePnt0) + ', ' + ToVector2String(ob.colliderTrianglePnt1) + ', ' + ToVector2String(ob.colliderTrianglePnt2)
			elif ob.colliderShapeType == 'roundTriangle':
				collider += ToVector2String(ob.colliderTrianglePnt0) + ', ' + ToVector2String(ob.colliderTrianglePnt1) + ', ' + ToVector2String(ob.colliderTrianglePnt2) + ', ' + str(ob.colliderTriangleBorderRadius)
			elif ob.colliderShapeType == 'polyline':
				collider += '['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'usePolylinePnt%i' %i):
						point = getattr(ob, 'colliderPolylinePnt%i' %i)
						collider += str(point[0]) + ', ' + str(point[1]) + ', '
				collider += '], ['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'usePolylineIdx%i' %i):
						idx = getattr(ob, 'colliderPolylineIdx%i' %i)
						collider += str(idx[0]) + ', ' + str(idx[1]) + ', '
				collider += ']'
			elif ob.colliderShapeType == 'trimesh':
				collider += '['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'useColliderTrimeshPnt%i' %i):
						point = getattr(ob, 'colliderTrimeshPnt%i' %i)
						collider += str(point[0]) + ', ' + str(point[1]) + ', '
				collider += '], ['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'useColliderTrimeshIdx%i' %i):
						idx = getattr(ob, 'colliderTrimeshIdx%i' %i)
						collider += str(idx[0]) + ', ' + str(idx[1]) + ', '
				collider += ']'
			elif ob.colliderShapeType == 'convexHull':
				collider += '['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'useColliderConvexHullPnt%i' %i):
						point = getattr(ob, 'colliderConvexHullPnt%i' %i)
						collider += str(point[0]) + ', ' + str(point[1]) + ', '
				collider += ']'
			elif ob.colliderShapeType == 'roundConvexHull':
				collider += '['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'useColliderConvexHullPnt%i' %i):
						point = getattr(ob, 'colliderConvexHullPnt%i' %i)
						collider += str(point[0]) + ', ' + str(point[1]) + ', '
				collider += '], ' + str(ob.colliderConvexHullBorderRadius)
			elif ob.colliderShapeType == 'heightfield':
				collider += '['
				for i in range(MAX_SHAPE_PNTS):
					if getattr(ob, 'useColliderHeight%i' %i):
						collider += str(getattr(ob, 'colliderHeight%i' %i))
				collider += '], ' + ToVector2String(ob.colliderHeightfieldScale)
			collider += ')'
			if ob.location.x != 0 or ob.location.y != 0:
				collider += '.setTranslation(' + str(ob.location.x) + ', ' + str(-ob.location.y) + ')'
			if ob.rotation_euler.z != 0:
				collider += '.setRotation(' + str(ob.rotation_euler.z) + ')'
			collider += '.setActiveEvents(3);\n'
			if ob.density != 0:
				collider += colliderDescName + '.density = ' + str(ob.density) + ';\n'
			if collisionGroupMembership != 65535 or collisionGroupFilter != 65535:
				collider += colliderDescName + '.setCollisionGroups(0x{:04X}{:04X});\n'.format(collisionGroupFilter, collisionGroupMembership)
			if not ob.colliderEnable:
				collider += colliderDescName + '.enabled = false;\n'
			if attachColliderTo == []:
				collider += colliderName + ' = world.createCollider(' + colliderDescName +');'
				if ob.isSensor:
					collider += colliderName + '.setSensor(true);\n'
				collider += 'collidersIds["' + ob.name + '"] = ' + colliderName + ';'
			else:
				for attachTo in attachColliderTo:
					attachToVarName = GetVarNameForObject(attachTo)
					collider += colliderName + attachToVarName + ' = world.createCollider(' + colliderDescName + ', ' + attachToVarName + 'RigidBody);\n'
					if ob.isSensor:
						collider += colliderName + attachToVarName + '.setSensor(true);\n'
					collider += 'collidersIds["' + colliderName + attachToVarName + '"] = ' + colliderName + attachToVarName + ';\n'
			colliders[ob] = collider
		if ob.jointExists:
			jointName = obVarName + 'Joint'
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
			joint += ');\n' + jointName + ' = world.createImpulseJoint(' + jointDataName + ', ' + GetVarNameForObject(ob.anchorRigidBody1) + 'RigidBody, ' + GetVarNameForObject(ob.anchorRigidBody2) + 'RigidBody, true);'
			joints[ob] = joint
		if ob.charControllerExists:
			charControllerName = obVarName + 'CharController'
			charController = 'var ' + charControllerName + ' = new RAPIER.KinematicCharacterController(' + str(ob.contactOff) + ', new RAPIER.IntegrationParameters(), '
			charControllers[ob] = charController
	else:
		localCenter = sum((Vector(v) for v in ob.bound_box), Vector()) / 8
		xCoords = [v[0] for v in ob.bound_box]
		yCoords = [v[1] for v in ob.bound_box]
		size = Vector((max(xCoords) - min(xCoords), max(yCoords) - min(yCoords), 0))
		pivot = GetPivot(ob)
		pivotOffX = pivot[0] * size.x
		pivotOffY = pivot[1] * size.y
		localPivot = localCenter + Vector((pivotOffX, pivotOffY, 0))
		worldPivot = ob.matrix_world @ localPivot
		posStr = str([worldPivot.x, -worldPivot.y])
		if ob.rigidBodyExists:
			rigidBodyName = obVarName + 'RigidBody'
			rigidBody = rigidBodyName + ' = sim.add_rigid_body(' + str(ob.rigidBodyEnable) + ', ' + str(RIGID_BODY_TYPES.index(ob.rigidBodyType)) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(ob.gravityScale) + ', ' + str(ob.dominance) + ', ' + str(ob.canRot) + ', ' + str(ob.linearDrag) + ', ' + str(ob.angDrag) + ', ' + str(ob.canSleep) + ', ' + str(ob.continuousCollideDetect) + ')\nrigidBodiesIds["' + obVarName + '"] = ' + rigidBodyName
			rigidBodies[ob] = rigidBody
			vars.append(rigidBodyName + ' = (-1, -1)')
			globals.append(rigidBodyName)
		if ob.colliderExists:
			matrix = ob.matrix_world
			pos = matrix.to_translation()
			rot = matrix.to_euler()
			rot.x = 0
			rot.y = 0
			rotAndSizeMatrix = Matrix.LocRotScale(Vector((0, 0, 0)), rot, ob.scale)
			rotatedSize = rot.to_matrix() @ ob.scale
			maxRotatedSizeComponent = max(rotatedSize.x, rotatedSize.y)
			radius = ob.colliderRadius * maxRotatedSizeComponent
			normal = (rotAndSizeMatrix @ Vector(list(ob.colliderNormal) + [0])).to_2d()
			size = (rotAndSizeMatrix @ Vector(list(ob.colliderSize) + [0])).to_2d()
			cuboidBorderRadius = ob.colliderCuboidBorderRadius * maxRotatedSizeComponent
			triangleBorderRadius = ob.colliderTriangleBorderRadius * maxRotatedSizeComponent
			if ob.colliderIsVertical:
				capsuleHeight = (rotAndSizeMatrix @ Vector((0, ob.colliderCapsuleHeight, 0))).y
				capsuleRadius = (rotAndSizeMatrix @ Vector((ob.colliderCapsuleHeight, 0, 0))).x
			else:
				capsuleHeight = (rotAndSizeMatrix @ Vector((ob.colliderCapsuleHeight, 0, 0))).x
				capsuleRadius = (rotAndSizeMatrix @ Vector((0, ob.colliderCapsuleHeight, 0))).y
			polylinePnts = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderPolylinePnt%i' %i):
					pnt = getattr(ob, 'colliderPolylinePnt%i' %i)
					pnt = (rotAndSizeMatrix @ Vector(list(pnt) + [0])).to_2d()
					polylinePnts.append(list(pnt))
			polylineIdxs = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderPolylineIdx%i' %i):
					idx = getattr(ob, 'colliderPolylineIdx%i' %i)
					polylineIdxs.append(list(idx))
			polylineIdxsStr = ''
			if polylineIdxs != []:
				polylineIdxsStr = str(polylineIdxs)
				if len(polylineIdxs) == 1:
					polylineIdxsStr = '[' + polylineIdxsStr + ']'
				polylineIdxsStr =', ' + polylineIdxsStr
			trimeshPnts = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderTrimeshPnt%i' %i):
					pnt = getattr(ob, 'colliderTrimeshPnt%i' %i)
					pnt = (rotAndSizeMatrix @ Vector(list(pnt) + [0])).to_2d()
					trimeshPnts.append(list(pnt))
			trimeshIdxs = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderTrimeshIdx%i' %i):
					idx = getattr(ob, 'colliderTrimeshIdx%i' %i)
					trimeshIdxs.append(list(idx))
			convexHullPnts = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderConvexHullPnt%i' %i):
					pnt = getattr(ob, 'colliderConvexHullPnt%i' %i)
					pnt = (rotAndSizeMatrix @ Vector(list(pnt) + [0])).to_2d()
					convexHullPnts.append(list(pnt))
			heights = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderHeight%i' %i):
					height = getattr(ob, 'colliderHeight%i' %i)
					pnt = (rotAndSizeMatrix @ Vector(list(pnt) + [0])).to_2d()
					heights.append(height)
			convexHullBorderRadius = ob.colliderConvexHullBorderRadius * maxRotatedSizeComponent
			heightfieldScale = (rotAndSizeMatrix @ Vector(list(ob.colliderHeightfieldScale) + [0])).to_2d()
			colliderName = obVarName + 'Collider'
			if attachColliderTo == []:
				if ob.colliderShapeType == 'ball':
					collider = colliderName + ' = sim.add_ball_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'halfspace':
					collider = colliderName + ' = sim.add_halfspace_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'cuboid':
					collider = colliderName + ' = sim.add_cuboid_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundCuboid':
					collider = colliderName + ' = sim.add_round_cuboid_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSize)) + ', ' + str(cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'capsule':
					collider = colliderName + ' = sim.add_capsule_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(capsuleHeight) + ', ' + str(ob.colliderCapsuleRadius) + ', ' + str(ob.colliderIsVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'segment':
					collider = colliderName + ' = sim.add_segment_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSegmentPnt0)) + ', ' + str(list(ob.colliderSegmentPnt1)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'triangle':
					collider = colliderName + ' = sim.add_triangle_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundTriangle':
					collider = colliderName + ' = sim.add_round_triangle_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'polyline':
					collider = colliderName + ' = sim.add_polyline_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + polylineIdxsStr + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'trimesh':
					collider = colliderName + ' = sim.add_trimesh_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'convexHull':
					collider = colliderName + ' = sim.add_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundConvexHull':
					collider = colliderName + ' = sim.add_round_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(convexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'heightfield':
					collider = colliderName + ' = sim.add_heightfield_collider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ',' + str(list(heightfieldScale)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				collider += '\ncollidersIds["' + obVarName + '"] = ' + colliderName
				vars.append(colliderName + ' = (-1, -1)')
				globals.append(colliderName)
			else:
				for attachTo in attachColliderTo:
					attachToVarName = GetVarNameForObject(attachTo)
					if ob.colliderShapeType == 'ball':
						collider = colliderName + attachToVarName + ' = sim.add_ball_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'halfspace':
						collider = colliderName + attachToVarName + ' = sim.add_halfspace_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'cuboid':
						collider = colliderName + attachToVarName + ' = sim.add_cuboid_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundCuboid':
						collider = colliderName + attachToVarName + ' = sim.add_round_cuboid_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'capsule':
						collider = colliderName + attachToVarName + ' = sim.add_capsule_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(capsuleHeight) + ', ' + str(ob.colliderCapsuleRadius) + ', ' + str(ob.colliderIsVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'segment':
						collider = colliderName + attachToVarName + ' = sim.add_segment_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSegmentPnt0)) + ', ' + str(list(ob.colliderSegmentPnt1)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'triangle':
						collider = colliderName + attachToVarName + ' = sim.add_triangle_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundTriangle':
						collider = colliderName + attachToVarName + ' = sim.add_round_triangle_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'polyline':
						collider = colliderName + attachToVarName + ' = sim.add_polyline_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + polylineIdxsStr + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'trimesh':
						collider = colliderName + attachToVarName + ' = sim.add_trimesh_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'convexHull':
						collider = colliderName + attachToVarName + ' = sim.add_convex_hull_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundConvexHull':
						collider = colliderName + attachToVarName + ' = sim.add_round_convex_hull_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.colliderConvexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'heightfield':
						collider = colliderName + attachToVarName + ' = sim.add_heightfield_collider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ',' + str(list(heightfieldScale)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					collider += '\ncollidersIds["' + obVarName + attachToVarName + '"] = ' + colliderName + attachToVarName
					vars.append(colliderName + attachToVarName + ' = (-1, -1)')
					globals.append(colliderName + attachToVarName)
			colliders[ob] = collider
		if ob.jointExists:
			jointName = obVarName + 'Joint'
			if ob.jointType == 'fixed':
				joint = jointName + ' = sim.add_fixed_joint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(ob.anchorRot1) + ', ' + str(ob.anchorRot2) + ')'
			elif ob.jointType == 'spring':
				joint = jointName + ' = sim.add_spring_joint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(ob.restLen) + ', ' + str(ob.stiffness) + ', ' + str(ob.damping) + ')'
			elif ob.jointType == 'revolute':
				joint = jointName + ' = sim.add_revolute_joint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ')'
			elif ob.joinType == 'prismatic':
				joint = jointName + ' = sim.add_prismatic_joint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(list(ob.jointAxis)) + ')'
			elif ob.joinType == 'rope':
				joint = jointName + ' = sim.add_rope_joint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(list(ob.jointLen)) + ')'
			joint += '\njointsIds["' + obVarName + '"] = ' + jointName
			vars.append(jointName + ' = (-1, -1)')
			globals.append(jointName)
			joints[ob] = joint
	ob.rotation_mode = prevRotMode

def RegisterParticleSystem (ob):
	if not ob.particleSystemExists or not ob.particle:
		return
	obVarName = GetVarNameForObject(ob)
	particleSystemName = obVarName + 'ParticleSystem'
	particleName = GetVarNameForObject(ob.particle)
	pos = GetObjectPosition(ob)
	rateMin = ob.minEmitRate if ob.useMinMaxEmitSpeed else ob.emitRate
	rateMax = ob.maxEmitRate if ob.useMinMaxEmitSpeed else ob.emitRate
	lifeMin = ob.minLife if ob.useMinMaxLife else ob.life
	lifeMax = ob.maxLife if ob.useMinMaxEmitSpeed else ob.life
	speedMin = ob.minEmitSpeed if ob.useMinMaxEmitSpeed else ob.emitSpeed
	speedMax = ob.maxEmitSpeed if ob.useMinMaxEmitSpeed else ob.emitSpeed
	rotMin = ob.minEmitRot if ob.useMinMaxEmitRot else math.degrees(-ob.rotation_euler.z)
	rotMax = ob.maxEmitRot if ob.useMinMaxEmitRot else math.degrees(-ob.rotation_euler.z)
	sizeMin = ob.minEmitSize if ob.useMinMaxEmitSize else 1
	sizeMax = ob.minEmitSize if ob.useMinMaxEmitSize else 1
	gravityScaleMin = ob.minGravityScale if ob.useMinMaxGravityScale else ob.particle.gravityScale
	gravityScaleMax = ob.maxGravityScale if ob.useMinMaxGravityScale else ob.particle.gravityScale
	bouncinessMin = ob.minBounciness if ob.useMinMaxBounciness else ob.particle.bounciness
	bouncinessMax = ob.maxBounciness if ob.useMinMaxBounciness else ob.particle.bounciness
	emitRadiusNormalizedMin = ob.minEmitRadiusNormalized if ob.useMinMaxEmitRadiusNormalized else ob.emitRadiusNormalized
	emitRadiusNormalizedMax = ob.maxEmitRadiusNormalized if ob.useMinMaxEmitRadiusNormalized else ob.emitRadiusNormalized
	linearDragMin = ob.minLinearDrag if ob.useMinMaxLinearDrag else ob.particle.linearDrag
	linearDragMax = ob.maxLinearDrag if ob.useMinMaxLinearDrag else ob.particle.linearDrag
	angDragMin = ob.minAngDrag if ob.useMinMaxAngDrag else ob.particle.angDrag
	angDragMax = ob.maxAngDrag if ob.useMinMaxAngDrag else ob.particle.angDrag
	if exportType == 'html':
		initClause = f'''
var EM_{obVarName} = {{
  acc : 0,
  rate : [{rateMin}, {rateMax}],
  life : [{lifeMin}, {lifeMax}],
  speed : [{speedMin}, {speedMax}],
  rot : [{rotMin}, {rotMax}],
  size : [{sizeMin}, {sizeMax}],
  origin : {pos},
  id : '{particleName}',
  enable : {ob.particleSystemEnable}
}};
var PS_{obVarName} = [];
'''
		updateClause = f'''
(function() {{
	var e = EM_{obVarName};
	if (!e.enable) return;
	e.acc += $.dt * e.rate;
	while (e.acc >= 1)
	{{
		var ang = random(0, 2 * Math.PI);
		var sp = random(e.speed[0], e.speed[1]);
		var dir = ang_to_dir(ang);
		var id = e.id + '__' + Date.now() + '__' + Math.random().toString(36).slice(2);
		$.copy_node (e.id, id, [e.origin[0], e.origin[1]]);
		PS_{obVarName}.push({{
			id : id,
			pos : [e.origin[0], e.origin[1]],
			vel : [dir[0]*sp, dir[1]*sp],
			life : random(e.life[0], e.life[1])
		}});
		e.acc -= 1;
	}}
	for (var i = PS_{obVarName}.length - 1; i >= 0; --i)
	{{
		var p = PS_{obVarName}[i];
		p.life -= $.dt;
		if (p.life <= 0)
		{{
			var node = document.getElementById(p.id);
			if (node)
				$.remove (node);
			PS_{obVarName}.splice(i, 1);
			continue;
		}}
		p.pos[0] += p.vel[0] * $.dt;
		p.pos[1] += p.vel[1] * $.dt;
		var node = document.getElementById(p.id);
		if (node)
			node.style.transform = 'translate(' + p.pos[0] + 'px,' + p.pos[1] + 'px)';
	}}
}})();
'''
		initCode.append(initClause)
		updateCode.append(updateClause)
	elif exportType == 'exe':
		shapeData = []
		shapeIndices = []
		if ob.emitShapeType == 'ball':
			particleSystem = f'{particleSystemName} = ParticleSystem("{obVarName}", "{particleName}", {ob.particleSystemEnable}, {ob.prewarmDur}, {rateMin}, {rateMax}, {lifeMin}, {lifeMax}, {speedMin}, {speedMax}, {rotMin}, {rotMax}, {sizeMin}, {sizeMax}, {gravityScaleMin}, {gravityScaleMax}, {bouncinessMin}, {bouncinessMax}, {emitRadiusNormalizedMin}, {emitRadiusNormalizedMax}, {linearDragMin}, {linearDragMax}, {angDragMin}, {angDragMax}, {list(ob.emitTint)}, {SHAPE_TYPES.index(ob.emitShapeType)}, {-ob.rotation_euler.z}, {ob.emitRadius})'
		particleSystem += f'\nparticleSystems["{obVarName}"] = {particleSystemName}'
		vars.append(f'{particleSystemName} : Optional[ParticleSystem] = None')
		globals.append(particleSystemName)
		particleSystems.append(particleSystem)

def RenderObject (ob, newOb, renderFunc, *args):
	scene = bpy.context.scene
	prevCam = scene.camera
	renderSettings = scene.render
	imageSettings = renderSettings.image_settings
	viewSettings = imageSettings.view_settings
	prevRenderPath = renderSettings.filepath
	prevResPercent = renderSettings.resolution_percentage
	prevTransparentFilm = renderSettings.film_transparent
	prevExposure = viewSettings.exposure
	prevGamma = viewSettings.gamma
	prevRenderFormat = imageSettings.file_format
	prevClrMode = imageSettings.color_mode
	renderSettings.film_transparent = True
	prevClrManagement = imageSettings.color_management
	prevExposure = viewSettings.exposure
	prevGamma = viewSettings.gamma
	if len(bpy.data.lights) == 0:
		imageSettings.color_management = 'OVERRIDE'
		viewSettings.exposure = 32
		viewSettings.gamma = 5
	imageSettings.file_format = 'BMP'
	imageSettings.color_mode = 'BW'
	renderSettings.filepath = os.path.join(TMP_DIR, 'Render.bmp')
	renderSettings.resolution_percentage *= ob.resPercent
	prevHideObsInRender = {}
	for ob2 in bpy.data.objects:
		prevHideObsInRender[ob2] = ob2.hide_render
		ob2.hide_render = ob2 != newOb
	renderFunc (*args)
	scene.camera = prevCam
	for ob in bpy.data.objects:
		ob.hide_render = prevHideObsInRender[ob]
	renderSettings.filepath = prevRenderPath
	renderSettings.resolution_percentage = prevResPercent
	renderSettings.film_transparent = prevTransparentFilm
	viewSettings.exposure = prevExposure
	viewSettings.gamma = prevGamma
	imageSettings.file_format = prevRenderFormat
	imageSettings.color_mode = prevClrMode
	imageSettings.color_management = prevClrManagement

def RenderCurve (*args):
	ob = args[0]
	newOb = args[1]
	renderPath = args[2]
	scene = bpy.context.scene
	renderSettings = scene.render
	renderSettings.filepath = renderPath
	imageSettings = renderSettings.image_settings
	imageSettings.file_format = 'PNG'
	imageSettings.color_mode = 'RGBA'
	imgsPaths.append(renderPath)
	camData = bpy.data.cameras.new('Temp')
	cam = bpy.data.objects.new('Temp', object_data = camData)
	scene.collection.objects.link(cam)
	scene.camera = cam
	bpy.context.view_layer.objects.active = ob
	ob.select_set(True)
	bpy.ops.view3d.camera_to_view_selected()
	bpy.ops.render.render(write_still = True)
	pos = ob.location.copy()
	pos.y *= -1
	_min, _max = GetRectMinMax(ob)
	size = _max - _min
	AddImageDataForExe (ob, '.' + renderPath[renderPath.rfind('/') :], pos, size, 1)
	scene.collection.objects.unlink(cam)
	bpy.data.objects.remove(cam)

def RenderMesh (*args):
	ob = args[0]
	newOb = args[1]
	renderCams = args[2]
	newName = args[3]
	tints = args[4]
	frame = args[5]
	visibleClrValues = args[6]
	mat = args[7]
	prevMatClrs = args[8]
	scene = bpy.context.scene
	renderSettings = scene.render
	for cam in renderCams:
		prevName = newName
		if frame > 0:
			newName += '_' + str(frame)
		scene.camera = cam
		bpy.ops.render.render(write_still = True)
		for i, tint in enumerate(tints):
			prevName2 = newName
			if i > 0:
				newName += '_' + str(i)
			cmd = [POTRACE_PATH, '-s', renderSettings.filepath, '-k ' + str(visibleClrValues[i]), '-i']
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
			materialClr = mat.diffuse_color
			fillClr = ClampComponents(Round(Multiply(materialClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
			if ob.gradientFill:
				svgTxt = svgTxt[: idxOfFillStart] + 'url(#' + ob.gradientFill.name + ')' + svgTxt[idxOfFillEnd :]
			else:
				svgTxt = svgTxt[: idxOfFillStart] + 'rgb(' + str(fillClr[0] * tint[0]) + ' ' + str(fillClr[1] * tint[1]) + ' ' + str(fillClr[2] * tint[2]) + ')' + svgTxt[idxOfFillEnd :]
			if ob.useStroke:
				strokeClr = ClampComponents(Round(Multiply(ob.strokeClr, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
				svgTxt = svgTxt.replace('stroke="none"', 'stroke="rgb(' + str(strokeClr[0]) + ' ' + str(strokeClr[1]) + ' ' + str(strokeClr[2]) + ')" stroke-width=' + str(ob.strokeWidth))
			svgsDatas[newName] = svgTxt
			newName = prevName2
		newName = prevName
		for matSlot in ob.material_slots:
			mat2 = matSlot.material
			if mat2 in prevMatClrs:
				mat2.diffuse_color = prevMatClrs[mat2]

def AddImageDataForExe (ob, imgPath, pos, size, opacity):
	surface = GetVarNameForObject(ob)
	surfaceRect = surface + 'Rect'
	tint = [int(c * 255) for c in ob.tint]
	renderCodeClause = surface + ' = pygame.image.load("' + imgPath + '").convert_alpha()\n'
	if tint + [opacity] != [255, 255, 255, 1]:
		renderCodeClause += 'tintSurface = pygame.Surface(' + surface + '.get_size()).convert_alpha()\ntintSurface.fill((' + str(tint[0]) + ', ' + str(tint[1]) + ', ' + str(tint[2]) + ', ' + str(opacity * 255) + '))\n' + surface + '.blit(tintSurface, (0, 0), special_flags = pygame.BLEND_RGBA_MULT)\n'
	renderCodeClause += surface + ' = pygame.transform.scale(' + surface + ', (' + str(size[0]) + ',' + str(size[1]) + '))\n'
	if ob.rotation_euler.z != 0:
		renderCodeClause += surface + ' = pygame.transform.rotate(' + surface + ', ' + str(math.degrees(-ob.rotation_euler.z)) + ')\n'
	renderCodeClause += 'initRots["' + surface + '"] = ' + str(math.degrees(-ob.rotation_euler.z)) + '\nsurfaces["' + surface + '"] = ' + surface + '\n' + surfaceRect + ' = ' + surface + '.get_rect().move(' + str(TryChangeToInt(pos.x)) + ', ' + str(TryChangeToInt(pos.y)) + ')\nsurfacesRects["' + surface + '"] = ' + surfaceRect + '\nzOrders["' + surface + '"] = ' + str(ob.location.z)
	if ob.hide_get():
		renderCodeClause += '\nhide.append("' + surface + '")'
	renderCode.append(renderCodeClause)

def GetPivot (ob):
	if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE':
		pivot = list(ob.empty_image_offset)
		pivot[0] *= -1
		pivot[1] *= -1
		return pivot
	else:
		return list(ob.pivot)

def GetImagePosition (ob):
	size = ob.scale * ob.empty_display_size
	pos = ob.location.copy()
	pos += size * Vector((ob.empty_image_offset[0], ob.empty_image_offset[1] + 1, 0))
	pos.y *= -1
	return pos

def HandleCopyObject (ob, pos):
	if IsCopiedObject(ob):
		if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE':
			if exportType == 'exe':
				idxOfPeriod = ob.name.find('.')
				if idxOfPeriod == -1:
					obNameWithoutPeriod = ob.name
				else:
					obNameWithoutPeriod = ob.name[: idxOfPeriod]
				origOb = bpy.data.objects[obNameWithoutPeriod]
				imgName = GetFileName(origOb.data.filepath)
				imgPath = TMP_DIR + '/' + imgName
				if imgPath not in imgsPaths:
					imgsPaths.append(imgPath)
				AddImageDataForExe (ob, imgPath.replace(TMP_DIR, '.'), GetImagePosition(ob), ob.scale * ob.empty_display_size, ob.color[3])
		prevRotMode = ob.rotation_mode
		ob.rotation_mode = 'XYZ'
		datas.append([obNameWithoutPeriod, ob.name, TryChangeToInt(pos[0]), TryChangeToInt(pos[1]), TryChangeToInt(math.degrees(ob.rotation_euler.z)), GetAttributes(ob)])
		exportedObs.append(ob)
		ob.rotation_mode = prevRotMode
		return True
	else:
		return False

def IsCopiedObject (ob):
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
			return True
	return False

def GetAttributes (ob):
	output = {}
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useBool%i' %i):
			output[getattr(ob, 'boolName%i' %i)] = getattr(ob, 'boolVal%i' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useInt%i' %i):
			output[getattr(ob, 'intName%i' %i)] = getattr(ob, 'intVal%i' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useFloat%i' %i):
			output[getattr(ob, 'floatName%i' %i)] = getattr(ob, 'floatVal%i' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useString%i' %i):
			output[getattr(ob, 'stringName%i' %i)] = getattr(ob, 'stringVal%i' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useBoolArray%i' %i):
			arr = []
			for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
				if getattr(ob, 'useBoolArray%i,%i' %(i, i2)):
					arr.append(getattr(ob, 'boolArrayVal%i,%i' %(i, i2)))
			output[getattr(ob, 'boolArrayName%i' %i)] = arr
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useIntArray%i' %i):
			arr = []
			for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
				if getattr(ob, 'useIntArray%i,%i' %(i, i2)):
					arr.append(getattr(ob, 'intArrayVal%i,%i' %(i, i2)))
			output[getattr(ob, 'intArrayName%i' %i)] = arr
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useFloatArray%i' %i):
			arr = []
			for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
				if getattr(ob, 'useFloatArray%i,%i' %(i, i2)):
					arr.append(getattr(ob, 'floatArrayVal%i,%i' %(i, i2)))
			output[getattr(ob, 'floatArrayName%i' %i)] = arr
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useStringArray%i' %i):
			arr = []
			for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
				if getattr(ob, 'useStringArray%i,%i' %(i, i2)):
					arr.append(getattr(ob, 'stringArrayVal%i,%i' %(i, i2)))
			output[getattr(ob, 'stringArrayName%i' %i)] = arr
	return output

def GetPathDelta (fromPathData, toPathData):
	output = ''
	for i in range(len(fromPathData)):
		fromPathVal = ord(fromPathData[i])
		toPathVal = ord(toPathData[i])
		if fromPathVal != toPathVal:
			output += ToByteString(i + 32) + ToByteString(toPathVal - fromPathVal + 32 + 128)
	return output

def GetBlenderData ():
	global vars, clrs, datas, joints, pivots, globals, apiCode, initCode, pathsDatas, updateCode, exportedObs, svgsDatas, renderCode, rigidBodies, colliders, attributes, charControllers, particleSystems
	vars = []
	attributes = {}
	pivots = {}
	exportedObs = []
	apiCode = ''
	datas = []
	clrs = {}
	pathsDatas = []
	imgs = {}
	imgsPaths = []
	rigidBodies = {}
	colliders = {}
	joints = {}
	charControllers = {}
	particleSystems = []
	initCode = []
	updateCode = []
	svgsDatas = {}
	globals = []
	renderCode = []
	for ob in bpy.data.objects:
		ExportObject (ob)
	for ob in bpy.data.objects:
		for scriptInfo in GetScripts(ob, True):
			script = scriptInfo[0]
			_type = scriptInfo[1]
			if _type == exportType:
				apiCode += script + '\n'
		for scriptInfo in GetScripts(ob, False):
			script = scriptInfo[0]
			isInit = scriptInfo[1]
			_type = scriptInfo[2]
			if _type == exportType:
				if isInit:
					if script not in initCode:
						initCode.append(script)
				else:
					if script not in updateCode:
						updateCode.append(script)
	return (datas, initCode, updateCode, apiCode)

buildInfo = {
	'html' : None,
	'html-size': None,
	'zip' : None,
	'zip-size' : None,
	'js-size' : None,
	'js-gz-size' : None,
}

PYTHON = '''from python import os, sys, math, pygame, random, PyRapier2d
from random import uniform

os.environ['SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS'] = '1'


# Physics Section Start
sim = PyRapier2d.Simulation()
rigidBodiesIds = {}
collidersIds = {}
jointsIds = {}
# Physics Section End
surfaces = {}
hide = []
surfacesRects = {}
initRots = {}
zOrders = {}
if sys.platform == 'win32':
	TMP_DIR = os.path.expanduser('~\\AppData\\Local\\Temp')
else:
	TMP_DIR = '/tmp'
# Pivots
# Attributes
off = pygame.math.Vector2()

def add (v, v2):
	return pygame.math.Vector2(v[0] + v2[0], v[1] + v2[1])

def subtract (v, v2):
	return pygame.math.Vector2(v[0] - v2[0], v[1] - v2[1])

def multiply (v, f):
	return pygame.math.Vector2(v[0] * f, v[1] * f)

def divide (v, f):
	return pygame.math.Vector2(v[0] / f, v[1] / f)

def magnitude (v) -> float:
	return math.sqrt(sqr_magnitude(v))

def sqr_magnitude (v) -> float:
	return v[0] * v[0] + v[1] * v[1]

def normalize (v):
	return divide(v, magnitude(v))

def copy_object (name, newName, pos, rot = 0, wakeUp = True, attachTo : str = '', copyParticles = True):
	global pivots, initRots, surfaces, surfacesRects, collidersIds, rigidBodiesIds
	if name in pivots:
		surface = surfaces[name].copy()
		surfacesRects[newName] = surfacesRects[name].copy()
		surfaces[newName] = surface
		pivots[newName] = pivots[name].copy()
		initRots[newName] = rot
		game.sortedObNames.append(newName)
	if name in attributes:
		attributes[newName] = attributes[name].copy()
	if name in zOrders:
		zOrders[newName] = zOrders[name]
	if name in rigidBodiesIds:
		rigidBodiesIds[newName] = sim.copy_rigid_body(rigidBodiesIds[name], pos, 0, wakeUp)
		for i, collider in enumerate(sim.get_rigid_body_colliders(rigidBodiesIds[newName])):
			collidersIds[newName + ':' + str(i)] = collider
	else:
		if name in pivots:
			surfaces[newName] = pygame.transform.rotate(surface, rot)
			initRots[newName] = rot
		if name in collidersIds:
			if attachTo == '':
				collidersIds[newName] = sim.copy_collider(collidersIds[name], pos, rot)
			else:
				collidersIds[newName] = sim.copy_collider(collidersIds[name], pos, rot, rigidBodiesIds[attachTo])
	if name in particleSystems:
		particleSystems[newName] = particleSystems[name].copy(newName, pos, rot, copyParticles)

def remove_object (name, removeColliders = True, wakeUp = True, removeParticles = True):
	if name in pivots:
		del surfaces[name]
		del surfacesRects[name]
		del initRots[name]
		del pivots[name]
		game.sortedObNames.remove(name)
	if name in attributes:
		del attributes[name]
	if name in zOrders:
		del zOrders[name]
	if name in rigidBodiesIds:
		rigidBody = rigidBodiesIds[name]
		if removeColliders:
			for collider in sim.get_rigid_body_colliders(rigidBody):
				for colliderName in collidersIds:
					if collidersIds[colliderName] == collider:
						del collidersIds[colliderName]
						break
		sim.remove_rigid_body (rigidBody, removeColliders)
		del rigidBodiesIds[name]
	elif name in collidersIds:
		sim.remove_collider (collidersIds[name], wakeUp)
		del collidersIds[name]
	if name in particleSystems:
		particleSystem = particleSystems.pop(name)
		if removeParticles:
			for particle in particleSystem.particles:
				remove_object (particle.name)

def ang_to_dir (ang):
	ang = math.radians(ang)
	return pygame.math.Vector2(math.cos(ang), math.sin(ang))

def rotate_surface (surface, deg, pivot, offset):
	rotatedSurface = pygame.transform.rotate(surface, -deg)
	rotatedOff = offset.rotate(deg)
	rect = rotatedSurface.get_rect(center = pivot - rotatedOff)
	return rotatedSurface, rect

def rotate_vector (v, pivot, deg):
	deg = math.radians(deg)
	ang = math.atan2(v[1] - pivot[1], v[0] - pivot[0]) + deg
	return pivot + (pygame.math.Vector2(math.cos(ang), math.sin(ang)).normalize() * (pygame.math.Vector2(v) - pivot).length())

def degrees (ang):
	return float(math.degrees(ang))

def radians (ang):
	return float(math.radians(ang))

def get_object_position (name):
	if name in rigidBodiesIds:
		return sim.get_rigid_body_position(rigidBodiesIds[name])
	elif name in collidersIds:
		return sim.get_collider_position(collidersIds[name])
	else:
		return None

def get_object_rotation (name):
	if name in rigidBodiesIds:
		return sim.get_rigid_body_rotation(rigidBodiesIds[name])
	elif name in collidersIds:
		return sim.get_collider_rotation(collidersIds[name])
	else:
		return None

class Particle:
	name : str
	life : float

	def __init__ (self, name : str, life : float):
		self.name = name
		self.life = life

	def __eq__ (self, other : Particle) -> bool:
		if not isinstance(other, Particle):
			return False
		return self.name == other.name

class ParticleSystem:
	name : str
	particleName : str
	enable : bool
	prewarmDur : float
	minRate : float
	maxRate : float
	intvl : float
	minLife : float
	maxLife : float
	minSpeed : float
	maxSpeed : float
	minRot : float
	maxRot : float
	minSize : float
	maxSize : float
	minGravityScale : float
	maxGravityScale : float
	minBounciness : float
	maxBounciness : float
	maxEmitRadiusNormalized : float
	minEmitRadiusNormalized : float
	minLinearDrag : float
	maxLinearDrag : float
	minAngDrag : float
	maxAngDrag : float
	tint : list[float]
	shapeType : int
	shapeRot : float
	ballRadius : float
	timer : float
	lastId : int
	particles : list[Particle]

	def __init__ (self, name : str, particleName : str, enable : bool, prewarmDur : float, minRate : float, maxRate : float, minLife : float, maxLife : float, minSpeed : float, maxSpeed : float, minRot : float, maxRot : float, minSize : float, maxSize : float, minGravityScale : float, maxGravityScale : float, minBounciness : float, maxBounciness : float, maxEmitRadiusNormalized : float, minEmitRadiusNormalized : float, minLinearDrag : float, maxLinearDrag : float, minAngDrag : float, maxAngDrag : float, tint : list[float], shapeType : int, shapeRot : float, ballRadius : float = 0.0):
		self.name = name
		self.particleName = particleName
		self.enable = enable
		self.minRate = minRate
		self.maxRate = maxRate
		self.intvl = 1.0 / uniform(minRate, maxRate)
		self.minSize = minSize
		self.maxSize = maxSize
		self.minLife = minLife
		self.maxLife = maxLife
		self.minSpeed = minSpeed
		self.maxSpeed = maxSpeed
		self.minRot = math.radians(minRot)
		self.maxRot = math.radians(maxRot)
		self.minGravityScale = minGravityScale
		self.maxGravityScale = maxGravityScale
		self.minBounciness = minBounciness
		self.maxBounciness = maxBounciness
		self.maxEmitRadiusNormalized = maxEmitRadiusNormalized
		self.minEmitRadiusNormalized = minEmitRadiusNormalized
		self.minLinearDrag = minLinearDrag
		self.maxLinearDrag = maxLinearDrag
		self.minAngDrag = minAngDrag
		self.maxAngDrag = maxAngDrag
		self.tint = tint
		self.shapeType = shapeType
		self.shapeRot = math.radians(shapeRot)
		self.ballRadius = ballRadius
		self.timer = 0.0
		self.lastId = 0
		self.particles = []
		while self.timer < prewarmDur:
			self.timer += self.intvl
			self.update (self.intvl)
			self.intvl = 1.0 / uniform(self.minRate, self.maxRate)
		self.update (prewarmDur - self.timer)

	def update (self, dt : float):
		self.timer += dt
		if self.timer >= self.intvl:
			self.timer -= self.intvl
			self.emit ()
		for particle in list(self.particles):
			particle.life -= dt
			if particle.life <= 0:
				remove_object (particle.name)
				self.particles.remove(particle)

	def emit (self):
		self.intvl = 1.0 / uniform(self.minRate, self.maxRate)
		rot = uniform(self.minRot, self.maxRot)
		size = uniform(self.minSize, self.maxSize)
		newParticleName = self.name + ':' + str(self.lastId)
		self.lastId += 1
		obPos = get_object_position(self.name)
		if self.shapeType == 0: # ball
			pos = pygame.math.Vector2(obPos[0] + self.ballRadius * math.cos(rot), obPos[1] + self.ballRadius * math.sin(rot))
		else:
			pos = pygame.math.Vector2(0, 0)
		copy_object (self.particleName, newParticleName, pos, rot)
		rigidBody = rigidBodiesIds[newParticleName]
		sim.set_gravity_scale (rigidBody, uniform(self.minGravityScale, self.maxGravityScale), False)
		if newParticleName in collidersIds:
			sim.set_bounciness (collidersIds[newParticleName], uniform(self.minBounciness, self.maxBounciness))
		sim.set_rigid_body_enabled (rigidBody, True)
		sim.set_linear_velocity (rigidBody, ang_to_dir(rot) * uniform(self.minSpeed, self.maxSpeed))
		self.particles.append(Particle(newParticleName, uniform(self.minLife, self.maxLife)))

	def copy (self, newName : str, pos, rot : float = 0, copyParticles : bool = True):
		self = ParticleSystem(newName, self.particleName, self.enable, self.prewarmDur, self.minRate, self.maxRate, self.minLife, self.maxLife, self.minSpeed, self.maxSpeed, self.minRot, self.maxRot, self.minSize, self.maxSize, self.minGravityScale, self.maxGravityScale, self.minBounciness, self.maxBounciness, self.maxEmitRadiusNormalized, self.minEmitRadiusNormalized, self.minLinearDrag, self.maxLinearDrag, self.minAngDrag, self.maxAngDrag, self.tint, self.shapeType, self.shapeRot, self.ballRadius)
		particleSystem = self
		if copyParticles:
			for particle in self.particles:
				particlePos = get_object_position(particle.name)
				particleRot = get_object_rotation(particle.name)
				newParticleName = newName + ':' + str(self.lastId)
				copy_object (particle.name, newParticleName, rotate_vector(particlePos, pos, rot), particleRot + rot)
				particleSystem.particles.append(Particle(newParticleName, particle.life))
		particleSystems[newName] = particleSystem
		return particleSystem

particleSystems : dict[str, ParticleSystem] = {}

class Game:
	def __init__ (self, title : str = 'Game'):
		pygame.display.set_caption(title)
		self.clock = pygame.time.Clock()
		self.running = True
		self.dt = self.clock.tick(60) / 1000
		self.frame = 0
		self.sortedObNames : list[str] = []

	def run (self):
		while self.running:
			self.handle_events ()
			self.update ()
			self.render ()
			self.dt = self.clock.tick(60) / 1000
			self.frame += 1

	def handle_events (self):
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				self.running = False

	def init (self):
		global sim, off, hide, pivots, initRots, surfaces, jointsIds, attributes, collidersIds, surfacesRects, rigidBodiesIds, particleSystems
# Globals
		sim = PyRapier2d.Simulation()
		rigidBodiesIds = {}
		collidersIds = {}
		jointsIds = {}
		surfaces = {}
		hide = []
		surfacesRects = {}
		initRots = {}
		particleSystems = {}
		zOrders = {}
		off = pygame.math.Vector2()
# Init Pivots And Attributes
# Init Physics
# Init Rendering
# Init Particle Systems
		self.sortedObNames = [name for name, z in sorted(zOrders.items(), key = lambda item : item[1])]

	def update (self):
		global off
# Globals
# Physics Section Start
		sim.step ()
# Physics Section End
# Update
		for particleSystem in list(particleSystems.values()):
			if particleSystem.enable:
				particleSystem.update (self.dt)

	def render (self):
# Background
		for name in self.sortedObNames:
			if name not in hide:
				surface = surfaces[name]
				if name in rigidBodiesIds:
					rigidBody = rigidBodiesIds[name]
					pos = sim.get_rigid_body_position(rigidBody)
					rot = sim.get_rigid_body_rotation(rigidBody)
					width, height = surface.get_size()
					pivot = pivots[name]
					offset = pygame.math.Vector2(pivot[0] * width, pivot[1] * height) - pygame.math.Vector2(width, height) / 2
					rotatedSurface, rect = rotate_surface(surface, rot + initRots[name], pos, offset)
					screen.blit(rotatedSurface, (rect.left - off.x, rect.top - off.y))
				else:
					pos = surfacesRects[name].topleft
					screen.blit(surface, (pos[0] - off.x, pos[1] - off.y))
		pygame.display.flip()

# Vars

pygame.init()
screen = pygame.display.set_mode(flags = pygame.FULLSCREEN)
windowSize = pygame.display.get_window_size()
game = Game()
game.init ()
# API
# Init User Code
game.run ()'''
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
		$.draw_svg (e[0], e[1], [e[2], e[3]], c[e[4]], e[5], c[e[6]], e[7], p.split('\\n')[i].split(String.fromCharCode(1)), e[8], e[9], e[10], e[11], e[12], e[13], [e[14], e[15]], e[16], e[17], [e[18], e[19]], [e[20], e[21]], e[22], e[23], e[24], e[25], [e[26], e[27]], [e[28], e[29]], [e[30], e[31]], [e[32], e[33]], [e[34], e[35]], [e[36], e[37]], [e[38], e[39]], [e[40], e[41]], [e[42], e[43]], e[44], e[45], e[46], e[47], e[48], e[49], e[50]);
		i ++;
	}
	else if (l > 6)
		$.add_radial_gradient (e[0], [e[1], e[2]], e[3], e[4], c[e[5]], c[e[6]], c[e[7]], e[8], e[9]);
	else if (l > 5)
		$.copy_node (e[0], e[1], [e[2], e[3]], e[4], e[5]);
	else
		g.push(e);
}
for (var e of g)
	add_group (e[0], [e[1], e[2]], e[3], e[4]);
$.main ()
'''
JS = '''
var svgNS = 'http://www.w3.org/2000/svg';
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
	return Math.sqrt(v[0] * v[0] + v[1] * v[1]);
}
function magnitude_vec (v)
{
	return Math.sqrt(v.x * v.x + v.y * v.y);
}
function normalize (v)
{
	return divide(v, magnitude(v));
}
function normalize_vec (v)
{
	return divide_vec(v, magnitude_vec(v));
}
function multiply (v, f)
{
	return [v[0] * f, v[1] * f];
}
function multiply_vec (v, f)
{
	return {x : v.x * f, y : v.y * f};
}
function divide (v, f)
{
	return [v[0] / f, v[1] / f];
}
function divide_vec (v, f)
{
	return {x : v.x / f, y : v.y / f};
}
function add (v, v2)
{
	return [v[0] - v2[0], v[1] - v2[1]];
}
function add_vec (v, v2)
{
	return {x : v.x + v2.x, y : v.y + v2.y};
}
function subtract (v, v2)
{
	return [v[0] - v2[0], v[1] - v2[1]];
}
function subtract_vec (v, v2)
{
	return {x : v.x - v2.x, y : v.y - v2.y};
}
function random (min, max)
{
	return Math.random() * (max - min) + min;
}
function add_group (id, pos, childIds = [], attributes = {}, txt = '')
{
	var group = document.createElementNS(svgNS, 'g');
	group.id = id;
	group.setAttribute('x', pos[0]);
	group.setAttribute('y', pos[1]);
	group.innerHTML = txt;
	for (var [key, val] of Object.entries(attributes))
		group.setAttribute(key, val);
	for (var childId of childIds)
	{
		var node = document.getElementById(childId);
		node.style.position = 'fixed';
		group.appendChild(node);
	}
	document.body.appendChild(group);
	return group;
}
function shuffle (arr)
{
	var currIdx = arr.length;
	while (currIdx != 0)
	{
		var randIdx = Math.floor(Math.random() * currIdx);
		currIdx --;
		[arr[currIdx], arr[randIdx]] = [arr[randIdx], arr[currIdx]];
	}
}
'''
PHYSICS = '''
import RAPIER from 'https://cdn.skypack.dev/@dimforge/rapier2d-compat';

// Vars
var world;
var rigidBodiesIds = {};
var rigidBodyDescsIds = {};
var collidersIds = {};
RAPIER.init().then(() => {
	// Gravity
	world = new RAPIER.World(gravity);
	// Settings
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
		var output = 'M ' + pathStr.charCodeAt(0) + ', ' + pathStr.charCodeAt(1) + ' ';
		for (var i = 2; i < pathStr.length; i += 2)
		{
			if ((i - 2) % 6 == 0)
				output += 'C ';
			output += '' + pathStr.charCodeAt(i) + ', ' + pathStr.charCodeAt(i + 1) + ' '
		}
		if (cyclic)
			output += 'Z';
		return output;
	}
	copy_node (id, newId, pos, rot = 0, attributes = {})
	{
		var copy = document.getElementById(id).cloneNode(true);
		copy.id = newId;
		copy.setAttribute('x', pos[0]);
		copy.setAttribute('y', pos[1]);
		copy.style.transform = 'translate(' + pos[0] + ', ' + pos[1] + ')rotate(' + rot + 'deg)';
		for (var [key, val] of Object.entries(attributes))
			copy.setAttribute(key, val);
		document.body.appendChild(copy);
		var colliders = [];
		// Physics Section Start
		var rigidBody = rigidBodiesIds[id];
		if (rigidBody)
		{
			rigidBodiesIds[newId] = world.createRigidBody(new RAPIER.RigidBodyDesc(rigidBody.bodyType()).setAngularDamping(rigidBody.angularDamping()).setCanSleep(rigidBodyDescsIds[id].canSleep).setCcdEnabled(rigidBody.isCcdEnabled()).setDominanceGroup(rigidBody.dominanceGroup()).setEnabled(rigidBody.isEnabled()).setGravityScale(rigidBody.gravityScale()).setLinearDamping(rigidBody.linearDamping()).lockRotations(rigidBody.lockRotations()).setRotation(rot).setTranslation(pos[0], pos[1]));
			for (var i = 0; i < rigidBody.numColliders(); i ++)
				colliders.push(rigidBody.collider(i));
		}
		var collider = collidersIds[id];
		if (collider)
		{
			var newColliderDesc = new RAPIER.ColliderDesc(collider.shape).setActiveEvents(collider.activeEvents).setCollisionGroups(collider.collisionGroups).setDensity(collider.density).setEnabled(collider.enabled).setRotation(collider.rotation).setTranslation(pos[0], pos[1]);
			if (rigidBody)
				collider = world.createCollider(newColliderDesc, rigidBodiesIds[newId]);
			else
			{
				collider = world.createCollider(newColliderDesc);
				collidersIds[newId] = collider;
			}
			colliders.push(collider);
		}
		// Physics Section End
		return [copy, colliders];
	}
	add_radial_gradient (id, pos, zIdx, diameter, clr, clr2, clr3, clrPositions, subtractive)
	{
		var group = document.createElementNS(svgNS, 'g');
		group.id = id;
		group.setAttribute('x', pos[0]);
		group.setAttribute('y', pos[1]);
		var mixMode = 'lighter';
		if (subtractive)
			mixMode = 'darker';
		group.style = 'position:absolute;left:' + (pos[0] + diameter / 2) + 'px;top:' + (pos[1] + diameter / 2) + 'px;background-image:radial-gradient(rgba(' + clr[0] + ', ' + clr[1] + ', ' + clr[2] + ', ' + clr[3] + ') ' + clrPositions[0] + '%, rgba(' + clr2[0] + ', ' + clr2[1] + ', ' + clr2[2] + ', ' + clr2[3] + ') ' + clrPositions[1] + '%, rgba(' + clr3[0] + ', ' + clr3[1] + ', ' + clr3[2] + ', ' + clr3[3] + ') ' + clrPositions[2] + '%);width:' + diameter + 'px;height:' + diameter + 'px;z-index:' + zIdx + ';mix-blend-mode:plus-' + mixMode;
		document.body.appendChild(group);
	}
	draw_svg (positions, posPingPong, size, fillClr, lineWidth, lineClr, id, pathFramesStrings, cyclic, zIdx, attributes, jiggleDist, jiggleDur, jiggleFrames, rotAngRange, rotDur, rotPingPong, scaleXRange, scaleYRange, scaleDur, scaleHaltDurAtMin, scaleHaltDurAtMax, scalePingPong, pivot, fillHatchDensity, fillHatchRandDensity, fillHatchAng, fillHatchWidth, lineHatchDensity, lineHatchRandDensity, lineHatchAng, lineHatchWidth, mirrorX, mirrorY, capType, joinType, dashArr, cycleDur)
	{
		var fillClrTxt = 'rgb(' + fillClr[0] + ' ' + fillClr[1] + ' ' + fillClr[2] + ')';
		var lineClrTxt = 'rgb(' + lineClr[0] + ' ' + lineClr[1] + ' ' + lineClr[2] + ')';
		var pos = positions[0];
		var svg = document.createElementNS(svgNS, 'svg');
		svg.setAttribute('fill-opacity', fillClr[3] / 255);
		svg.id = id;
		svg.style = 'z-index:' + zIdx + ';position:absolute';
		svg.setAttribute('transform-pivot', pivot[0] + '% ' + pivot[1] + '%');
		svg.setAttribute('x', pos[0]);
		svg.setAttribute('y', pos[1]);
		svg.setAttribute('width', size[0]);
		svg.setAttribute('height', size[1]);
		var trs = 'translate(' + pos[0] + ', ' + pos[1] + ')';
		svg.setAttribute('transform', trs);
		var i = 0;
		var pathsValsAndStrings = $.get_svg_paths_and_strings(pathFramesStrings, cyclic);
		var anim;
		var frames;
		var firstFrame = '';
		for (var pathVals of pathsValsAndStrings[0])
		{
			var path = document.createElementNS(svgNS, 'path');
			path.id = id + ' ';
			if (i > 0)
				path.setAttribute('opacity', 0);
			path.style = 'fill:' + fillClrTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineClrTxt;
			path.setAttribute('d', pathVals);
			if (jiggleFrames > 0)
			{
				anim = document.createElementNS(svgNS, 'animate');
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
		for (var [key, val] of Object.entries(attributes))
			svg.setAttribute(key, val);
		document.body.appendChild(svg);
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
			anim = document.createElementNS(svgNS, 'animatetransform');
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
			anim = document.createElementNS(svgNS, 'animatetransform');
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
			anim = document.createElementNS(svgNS, 'animate');
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
			svg.setAttribute('transform-origin', 50 - (pivot[0] - 50) + '% ' + pivot[1] + '%');
		}
		if (mirrorY)
		{
			svg = $.copy_node(id, '`' + id, pos);
			svg.setAttribute('transform', trs + 'scale(1,-1)');
			svg.setAttribute('transform-origin', pivot[0] + '% ' + (50 - (pivot[1] - 50)) + '%');
		}
		var pathRect = svg.children[svg.children.length - 1].getBoundingClientRect();
		for (var i = svg.children.length - 2; i >= 0; i --)
		{
			var child = svg.children[i];
			var childRect = child.getBoundingClientRect();
			var pathAnchor = [lerp(pathRect.x, pathRect.right, pivot[0] / 100), lerp(pathRect.y, pathRect.bottom, pivot[1] / 100)];
			var childAnchor = [lerp(childRect.x, childRect.right, pivot[0] / 100), lerp(childRect.y, childRect.bottom, pivot[1] / 100)];
			child.setAttribute('transform', 'translate(' + (pathAnchor[0] - childAnchor[0]) + ', ' + (pathAnchor[1] - childAnchor[1]) + ')');
			pathRect = childRect;
		}
	}
	hatch (id, clr, useFIll, svg, path, density, randDensity, ang, width)
	{
		var luminance = (.2126 * clr[0] + .7152 * clr[1] + .0722 * clr[2]) / 255;
		var pattern = document.createElementNS(svgNS, 'pattern');
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
	// Physics Section Start
	set_transforms (dict)
	{
		for (var [key, val] of Object.entries(dict))
		{
			var node = document.getElementById(key);
			var trs = node.style.transform;
			var idxOfPosStart = trs.indexOf('translate(');
			var idxOfPosEnd = trs.indexOf(')', idxOfPosStart) + 1;
			var idxOfRotStart = trs.indexOf('rotate(');
			var idxOfRotEnd = trs.indexOf(')', idxOfRotStart) + 1;
			var pos = val.translation();
			var posStr = 'translate(' + (pos.x - node.getAttribute('width') / 2) + 'px,' + (pos.y - node.getAttribute('height') / 2) + 'px)';
			var rotStr = 'rotate(' + val.rotation() + 'rad)';
			if (idxOfRotStart > -1)
				trs = trs.slice(0, idxOfRotStart) + rotStr + trs.slice(idxOfRotEnd);
			else
				trs = rotStr + trs;
			if (idxOfPosStart > -1)
				trs = posStr + trs.slice(idxOfPosEnd);
			else
				trs = posStr + trs;
			node.style.transform = trs;
		}
	}
	remove (node)
	{
		if (rigidBodiesIds[node.id])
			delete rigidBodiesIds[node.id];
		else if (collidersIds[node.id])
			delete collidersIds[node.id];
		node.remove();
	}
	// Physics Section End
	main ()
	{
		// Init
		var f = t => {
			$.dt = (t - $.prevTicks) / 1000;
			$.prevTicks = t;
			window.requestAnimationFrame(f);
			// Update
		};
		window.requestAnimationFrame(t => {
			$.prevTicks = t;
			window.requestAnimationFrame(f);
		});
		// Physics Section Start
		setInterval(() => {
			world.step();
			$.set_transforms (rigidBodiesIds);
			$.set_transforms (collidersIds);
		}, 16);
		// Physics Section End
	}
}
var $ = new api;
'''

def GenJs (world):
	global datas, apiCode, clrs
	jsApi = JS_API
	if not usePhysics:
		while True:
			physicsSectionStartIndctr = '// Physics Section Start'
			idxOfPhysicsSectionStart = jsApi.find(physicsSectionStartIndctr) + len(physicsSectionStartIndctr)
			if idxOfPhysicsSectionStart == -1:
				break
			physicsSectionEndIndctr = '// Physics Section End'
			idxOfPhysicsSectionEnd = jsApi.find(physicsSectionEndIndctr) + len(physicsSectionEndIndctr)
			jsApi = jsApi[: idxOfPhysicsSectionStart] + jsApi[idxOfPhysicsSectionEnd :]
	js = [JS, jsApi, apiCode]
	if usePhysics:
		physics = PHYSICS
		vars = ''
		for key in rigidBodies.keys():
			rigidBodyName = GetVarNameForObject(key) + 'RigidBody'
			vars += 'var ' + rigidBodyName + ';\n'
		for key in colliders.keys():
			colliderName = GetVarNameForObject(key) + 'Collider'
			attachTo = []
			for i in range(MAX_ATTACH_COLLIDER_CNT):
				if getattr(key, 'attach%i' %i):
					attachTo.append(getattr(key, 'attachTo%i' %i))
			if attachTo == []:
				vars += 'var ' + colliderName + ';\n'
			else:
				for _attachTo in attachTo:
					vars += 'var ' + colliderName + GetVarNameForObject(_attachTo) + ';\n'
		for key in joints.keys():
			jointName = GetVarNameForObject(key) + 'Joint'
			vars += 'var ' + jointName + ';\n'
		for key in charControllers.keys():
			charControllerName = GetVarNameForObject(key) + 'CharController'
			vars += 'var ' + charControllerName + ';\n'
		physics = physics.replace('// Vars', vars)
		if bpy.context.scene.use_gravity:
			gravity = ToVector2String(bpy.context.scene.gravity)
		else:
			gravity = '{x : 0, y : 0}'
		physics = physics.replace('// Gravity', 'var gravity = ' + gravity + ';')
		settings = ''
		if world.unitLen != 1:
			settings = 'world.lengthUnit = ' + str(world.unitLen) + ';'
		physics = physics.replace('// Settings', settings)
		physics = physics.replace('// Colliders', '\n'.join(colliders.values()))
		physics = physics.replace('// Rigid Bodies', '\n'.join(rigidBodies.values()))
		physics = physics.replace('// Joints', '\n'.join(joints.values()))
		physics = physics.replace('// Char Controllers', '\n'.join(charControllers.values()))
		js += [physics]
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	datas = json.dumps(datas).replace(', ', ',').replace(': ', ':')
	clrs = json.dumps(clrs).replace(' ', '')
	if world.minifyMethod == 'terser':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += 'var D=`' + datas + '`\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + clrs + '`\n' + JS_SUFFIX
		open(jsTmp, 'w').write(js)
		cmd = ['python3', 'tinifyjs/Main.py', '-i=' + jsTmp, '-o=' + jsTmp, '-no_compress', dontMangleArg]
		print(' '.join(cmd))
		subprocess.run(cmd)
		js = open(jsTmp, 'r').read()
	elif world.minifyMethod == 'roadroller':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += 'var D=`' + datas + '`\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + clrs + '`\n' + JS_SUFFIX
		open(jsTmp, 'w').write(js)
		cmd = ['npx', 'roadroller', jsTmp, '-o', jsTmp]
		print(' '.join(cmd))
		subprocess.check_call(cmd)
		js = open(jsTmp, 'r').read()
	else:
		js += '\nvar D=`' + datas + '`;\nvar p=`' + '\n'.join(pathsDatas) + '`;\nvar C=`' + clrs + '`\n' + JS_SUFFIX.replace('\t', '')
	return js

def GenHtml (world, datas, background = ''):
	global apiCode, clrs, initCode, updateCode, pathsDatas
	js = GenJs(world)
	if background:
		background = 'background-color:%s;' %background
	o = [
		'<!DOCTYPE html>',
		'<html style="' + background + 'width:9999px;height:9999px;overflow:hidden">',
		'<body>',
		''.join(imgs.values()),
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

def GenPython (world, datas, background = ''):
	global vars, apiCode, clrs, initCode, updateCode, pathsDatas
	python = PYTHON
	if not usePhysics:
		while True:
			physicsSectionStartIndctr = '# Physics Section Start'
			idxOfPhysicsSectionStart = python.find(physicsSectionStartIndctr) + len(physicsSectionStartIndctr)
			if idxOfPhysicsSectionStart == -1:
				break
			physicsSectionEndIndctr = '# Physics Section End'
			idxOfPhysicsSectionEnd = python.find(physicsSectionEndIndctr) + len(physicsSectionEndIndctr)
			python = python[: idxOfPhysicsSectionStart] + python[idxOfPhysicsSectionEnd :]
	python = python.replace('# API', apiCode)
	python = python.replace('# Vars', '\n'.join(vars))
	python = python.replace('# Pivots', 'pivots = ' + str(pivots))
	python = python.replace('# Attributes', 'attributes = ' + str(attributes))
	gravity = [0, 0]
	if bpy.context.scene.use_gravity:
		gravity = list(bpy.context.scene.gravity)
	physicsInitClauses = ['sim.set_length_unit (' + str(world.unitLen) + ')\nsim.set_gravity (' + str(gravity[0]) + ', ' + str(gravity[1]) + ')']
	for rigidBody in rigidBodies.values():
		physicsInitClauses.append(rigidBody)
	for collider in colliders.values():
		physicsInitClauses.append(collider)
	for joint in joints.values():
		physicsInitClauses.append(joint)
	physicsInitCode = ''
	for clause in physicsInitClauses:
		for line in clause.split('\n'):
			physicsInitCode += '		' + line + '\n'
	for i, renderClause in enumerate(renderCode):
		_renderClause = ''
		for line in renderClause.split('\n'):
			_renderClause += '		' + line + '\n'
		renderCode[i] = _renderClause
	particleSystemsCode = ''
	for clause in particleSystems:
		for line in clause.split('\n'):
			particleSystemsCode += '		' + line + '\n'
	python = python.replace('# Init Pivots And Attributes', '		pivots = ' + str(pivots) + '\n		attributes = ' + str(attributes))
	python = python.replace('# Init Physics', physicsInitCode)
	python = python.replace('# Init Rendering', '\n'.join(renderCode))
	python = python.replace('# Init Particle Systems', particleSystemsCode)
	python = python.replace('# Init User Code', '\n'.join(initCode))
	for i, updateScript in enumerate(updateCode):
		_updateScript = ''
		for line in updateScript.split('\n'):
			_updateScript += '		' + line + '\n'
		updateCode[i] = _updateScript
	python = python.replace('# Globals', '		global ' + ', '.join(globals))
	python = python.replace('# Update', '\n'.join(updateCode))
	python = python.replace('# Background', '		screen.fill(' + str(Multiply(list(world.color), [255] * 3)) + ')')
	buildInfo['exe-size'] = len(python)
	return python

# SERVER_PROC = None
prevObMode = None
prevSvgExportPath = None

def PreBuild ():
	global prevObMode, prevSvgExportPath
	if preBuildScriptPath != '':
		exec(open(preBuildScriptPath, 'r').read())
	if bpy.context.active_object:
		prevObMode = bpy.context.active_object.mode
		bpy.ops.object.mode_set(mode = 'OBJECT')
	prevSvgExportPath = bpy.context.scene.export_svg_output
	bpy.context.scene.export_svg_output = TMP_DIR + '/Output.svg'

def PostBuild ():
	global prevObMode, prevSvgExportPath
	if postBuildScriptPath != '':
		exec(open(postBuildScriptPath, 'r').read())
	if bpy.context.active_object:
		bpy.ops.object.mode_set(mode = prevObMode)
	bpy.context.scene.export_svg_output = prevSvgExportPath

def BuildHtml (world):
	global exportType
	# global SERVER_PROC
	# if SERVER_PROC:
	# 	SERVER_PROC.kill()
	exportType = 'html'
	PreBuild ()
	blenderInfo = GetBlenderData()
	datas = blenderInfo[0]
	html = GenHtml(world, datas)
	htmlPath = os.path.expanduser(world.htmlPath)
	htmlPath = htmlPath.replace('\\', '/')
	if not htmlPath:
		htmlPath = TMP_DIR + '/index.html'
	if not htmlPath.endswith('.html'):
		htmlPath += '.html'
	print('Saving:', htmlPath)
	open(htmlPath, 'w').write(html)
	zipPath = os.path.expanduser(world.zipPath)
	zipPath = zipPath.replace('\\', '/')
	if not zipPath.endswith('.zip'):
		zipPath += '.zip'
	print('Saving:', zipPath)
	with ZipFile(zipPath, 'w') as zip:
		zip.write(htmlPath, GetFileName(htmlPath))
		for imgPath in imgsPaths:
			zip.write(imgPath, GetFileName(imgPath))
		zip.extractall(zipPath.replace('.zip', ''))
	zip = open(zipPath, 'rb').read()
	buildInfo['zip'] = zipPath
	buildInfo['zip-size'] = len(zip)
	if world.js13kbjam and len(html.encode('utf-8')) > 1024 * 13:
		raise SyntaxError('HTML is over 13kb')
	webbrowser.open(zipPath.replace('.zip', '/index.html'))

	# cmd = ['python', '-m', 'http.setAttributerver', '6969']
	# print(' '.join(cmd))
	# SERVER_PROC = subprocess.Popen(cmd, cwd = TMP_DIR)

	# atexit.register(lambda : SERVER_PROC.kill())
	# webbrowser.open('http://localhost:6969')
	PostBuild ()
	return html

def BuildExe (world):
	global exportType
	exportType = 'exe'
	PreBuild ()
	blenderInfo = GetBlenderData()
	datas = blenderInfo[0]
	python = GenPython(world, datas)
	pythonPath = TMP_DIR + '/Temp.py'
	open(pythonPath, 'w').write(python)
	exePath = os.path.expanduser(world.exePath)
	exePath = exePath.replace('\\', '/')
	if not exePath:
		exePath = TMP_DIR + '/' + bpy.path.basename(bpy.data.filepath).replace('.blend', '')
	if not exePath.endswith('.exe'):
		exePath += '.exe'
	cmd = 'python3 CodonBuild.py ' + pythonPath + ' ' + exePath + ' ' + str(world.debugMode)
	print(cmd)
	os.system(cmd)
	zipPath = os.path.expanduser(world.zipPath)
	zipPath = zipPath.replace('\\', '/')
	if not zipPath.endswith('.zip'):
		zipPath += '.zip'
	print('Saving:', zipPath)
	with ZipFile(zipPath, 'w') as zip:
		zip.write(exePath, GetFileName(exePath))
		for imgPath in imgsPaths:
			zip.write(imgPath, GetFileName(imgPath))
		zip.extractall(zipPath.replace('.zip', ''))
	zip = open(zipPath, 'rb').read()
	buildInfo['zip'] = zipPath
	buildInfo['zip-size'] = len(zip)
	os.remove(exePath)
	indexOfExeNameStart = exePath.rfind('/') + 1
	if indexOfExeNameStart == -1:
		indexOfExeNameStart = 0
	exePath = zipPath.replace('.zip', '') + '/' + exePath[indexOfExeNameStart :]
	cmd = 'chmod +x ' + exePath
	print(cmd)
	subprocess.check_call(cmd.split())
	cmd = exePath
	print(cmd)
	subprocess.check_call(cmd.split(), cwd = zipPath.replace('.zip', ''))
	PostBuild ()

def BuildUnity (world):
	global exportType
	exportType = 'unity'
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

def OnDrawColliders (self, ctx):
	gpu.state.blend_set('ALPHA')
	gpu.state.line_width_set(2)
	shader = gpu.shader.from_builtin('UNIFORM_COLOR')
	shader.bind()
	shader.uniform_float('color', VISUALIZER_CLR)
	for ob in self.obs:
		if not ob or not ob.colliderExists:
			continue
		matrix = ob.matrix_world
		pos = matrix.to_translation()
		rot = matrix.to_euler()
		rot.x = 0
		rot.y = 0
		matrix = Matrix.LocRotScale(pos, rot, ob.scale)
		if ob.colliderShapeType == 'ball':
			radius = ob.colliderRadius
			segments = 32
			verts = []
			for i in range(segments + 1):
				ang = (i / segments) * 2 * math.pi
				verts.append(matrix @ Vector((radius * math.cos(ang), radius * math.sin(ang), 0)))
			batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : verts})
			batch.draw(shader)
		elif ob.colliderShapeType == 'halfspace':
			normal = Vector(list(ob.colliderNormal) + [0]).normalized()
			dir = Vector(list(Rotate90(normal)) + [0])
			pnt = matrix @ (-dir * 99999)
			pnt2 = matrix @ (dir * 99999)
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
		elif ob.colliderShapeType == 'cuboid':
			_min, _max = -Vector((ob.colliderSize[0], ob.colliderSize[1], 0)) / 2, Vector((ob.colliderSize[0], ob.colliderSize[1], 0)) / 2
			verts = [matrix @ v for v in [_min, Vector((_min.x, _max.y, 0)), _max, Vector((_max.x, _min.y, 0))]]
			batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : verts})
			batch.draw(shader)
		elif ob.colliderShapeType == 'roundCuboid':
			halfWidth = ob.colliderSize[0] / 2
			halfHeight = ob.colliderSize[1] / 2
			radius = ob.colliderCuboidBorderRadius
			segments = 8
			verts = []
			center = (halfWidth, halfHeight, 0)
			for i in range(segments + 1):
				t = i / segments
				ang = (math.pi / 2) * (1 - t)
				x = center[0] + radius * math.cos(ang)
				y = center[1] + radius * math.sin(ang)
				verts.append(matrix @ Vector((x, y, 0)))
			center = (halfWidth, -halfHeight, 0)
			for i in range(segments + 1):
				t = i / segments
				ang = (2 * math.pi) - (math.pi / 2) * t
				x = center[0] + radius * math.cos(ang)
				y = center[1] + radius * math.sin(ang)
				verts.append(matrix @ Vector((x, y, 0)))
			center = (-halfWidth, -halfHeight, 0)
			for i in range(segments + 1):
				t = i / segments
				ang = (3 * math.pi / 2) - (math.pi / 2) * t
				x = center[0] + radius * math.cos(ang)
				y = center[1] + radius * math.sin(ang)
				verts.append(matrix @ Vector((x, y, 0)))
			center = (-halfWidth, halfHeight, 0)
			for i in range(segments + 1):
				t = i / segments
				ang = math.pi - (math.pi / 2) * t
				x = center[0] + radius * math.cos(ang)
				y = center[1] + radius * math.sin(ang)
				verts.append(matrix @ Vector((x, y, 0)))
			batch = batch_for_shader(shader, 'LINE_LOOP', {"pos" : verts})
			batch.draw(shader)
		elif ob.colliderShapeType == 'capsule':
			radius = ob.colliderCapsuleRadius
			height = ob.colliderCapsuleHeight / 2
			localPnt = Vector((-radius, -height / 2))
			if not ob.colliderIsVertical:
				localPnt = Rotate90(localPnt)
			localPnt = Vector(list(localPnt) + [0])
			pnt = matrix @ localPnt
			localPnt2 = Vector((-radius, height / 2))
			if not ob.colliderIsVertical:
				localPnt2 = Rotate90(localPnt2)
			localPnt2 = Vector(list(localPnt2) + [0])
			pnt2 = matrix @ localPnt2
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
			localPnt = Vector((radius, -height / 2))
			if not ob.colliderIsVertical:
				localPnt = Rotate90(localPnt)
			localPnt = Vector(list(localPnt) + [0])
			pnt = matrix @ localPnt
			localPnt2 = Vector((radius, height / 2))
			if not ob.colliderIsVertical:
				localPnt2 = Rotate90(localPnt2)
			localPnt2 = Vector(list(localPnt2) + [0])
			pnt2 = matrix @ localPnt2
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
			segments = 16
			for h in [height, -height]:
				verts = []
				for i in range(segments + 1):
					ang = i / segments * math.pi * 2
					x, y = radius * math.cos(ang), radius * math.sin(ang)
					if h < 0:
						y = -y
					localVert = Vector((x, y + h / 2))
					if not ob.colliderIsVertical:
						localVert = Rotate90(localVert)
					localVert = Vector((list(localVert) + [0]))
					verts.append(matrix @ localVert)
				batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : verts})
				batch.draw(shader)
		elif ob.colliderShapeType == 'segment':
			pnt = matrix @ Vector(list(ob.colliderSegmentPnt0))
			pnt2 = matrix @ Vector(list(ob.colliderSegmentPnt1))
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
		elif ob.colliderShapeType == 'triangle':
			pnt = matrix @ Vector(list(ob.colliderTrianglePnt0) + [0])
			pnt2 = matrix @ Vector(list(ob.colliderTrianglePnt1) + [0])
			pnt3 = matrix @ Vector(list(ob.colliderTrianglePnt2) + [0])
			batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : [pnt, pnt2, pnt3]})
			batch.draw(shader)
		# elif ob.colliderShapeType == 'roundTriangle':
		# 	try:
		# 		pnt = Vector(list(ob.colliderTrianglePnt0) + [0])
		# 		pnt2 = Vector(list(ob.colliderTrianglePnt1) + [0])
		# 		pnt3 = Vector(list(ob.colliderTrianglePnt2) + [0])
		# 		radius = ob.colliderTriangleBorderRadius
		# 		v12, v21 = (pnt2 - pnt).normalized(), (pnt - pnt2).normalized()
		# 		v23, v32 = (pnt3 - pnt2).normalized(), (pnt2 - pnt3).normalized()
		# 		v31, v13 = (pnt - pnt3).normalized(), (pnt3 - pnt).normalized()
		# 		halfAng = math.acos(max(-1, min(1, v12.dot(v13)))) / 2
		# 		halfAng2 = math.acos(max(-1, min(1, v21.dot(v23)))) / 2
		# 		halfAng3 = math.acos(max(-1, min(1, v31.dot(v32)))) / 2
		# 		bisector1 = (v12 + v13).normalized()
		# 		bisector2 = (v21 + v23).normalized()
		# 		bisector3 = (v31 + v32).normalized()
		# 		center = pnt + bisector1 * (radius / (math.sin(halfAng)))
		# 		center2 = pnt2 + bisector2 * (radius / (math.sin(halfAng2)))
		# 		center3 = pnt3 + bisector3 * (radius / (math.sin(halfAng3)))
		# 		perp12 = Vector((-v12.y, v12.x, 0))
		# 		perp13 = Vector((v13.y, -v13.x, 0))
		# 		perp21 = Vector((v21.y, -v21.x, 0))
		# 		perp23 = Vector((-v23.y, v23.x, 0))
		# 		perp31 = Vector((-v31.y, v31.x, 0))
		# 		perp32 = Vector((v32.y, -v32.x, 0))
		# 		t12, t13 = center + radius * perp12, center + radius * perp13
		# 		t21, t23 = center2 + radius * perp21, center2 + radius * perp23
		# 		t31, t32 = center3 + radius * perp31, center3 + radius * perp32
		# 		def GetArcPoints (center, startPnt, endPnt, segments = 12):
		# 			toStartPnt, toEndPnt = startPnt - center, endPnt - center
		# 			startAng = math.atan2(toStartPnt.y, toStartPnt.x)
		# 			endAng = math.atan2(toEndPnt.y, toEndPnt.x)
		# 			if endAng < startAng:
		# 				endAng += 2 * math.pi
		# 			if (endAng - startAng) > math.pi:
		# 				endAng -= 2 * math.pi
		# 			verts = []
		# 			for i in range(segments + 1):
		# 				ang = startAng + (endAng - startAng) * i / segments
		# 				verts.append(matrix @ (center + radius * Vector((math.cos(ang), math.sin(ang), 0))))
		# 			return verts
		# 		verts = GetArcPoints(center, t13, t12)
		# 		verts.extend(GetArcPoints(center2, t21, t23))
		# 		verts.extend(GetArcPoints(center3, t32, t31))
		# 	except (ValueError, ZeroDivisionError):
		# 		pnt = matrix @ pnt1
		# 		pnt2 = matrix @ pnt2
		# 		pnt3 = matrix @ pnt3
		# 		verts = [pnt, pnt2, pnt3]
		# 	batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : verts})
		# 	batch.draw(shader)
		elif ob.colliderShapeType == 'polyline':
			pnts = []
			idxs = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'usePolylinePnt%i' %i):
					pnts.append(matrix @ Vector(list(getattr(ob, 'colliderPolylinePnt%i' %i)) + [0]))
				if getattr(ob, 'usePolylineIdx%i' %i):
					idxs.append(list(getattr(ob, 'colliderPolylineIdx%i' %i)))
			if idxs == []:
				batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : pnts})
			else:
				batch = batch_for_shader(shader, 'LINES', {'pos' : pnts}, indices = idxs)
			batch.draw(shader)
		elif ob.colliderShapeType == 'trimesh':
			pnts = []
			idxs = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useTrimeshPnt%i' %i):
					pnts.append(matrix @ Vector(list(getattr(ob, 'colliderTrimeshPnt%i' %i)) + [0]))
				if getattr(ob, 'useTrimeshIdx%i' %i):
					idxs.append(list(getattr(ob, 'colliderTrimeshIdx%i' %i)))
			if idxs == []:
				batch = batch_for_shader(shader, 'TRI_STRIP', {'pos' : pnts})
			else:
				batch = batch_for_shader(shader, 'TRIS', {'pos' : pnts}, indices = idxs)
			batch.draw(shader)
		elif ob.colliderShapeType == 'convexHull':
			pnts = []
			for i in range(MAX_SHAPE_PNTS):
				if getattr(ob, 'useColliderConvexHullPnt%i' %i):
					pnts.append(matrix @ Vector(list(getattr(ob, 'colliderConvexHullPnt%i' %i)) + [0]))
			batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : pnts})
			batch.draw(shader)
	gpu.state.blend_set('NONE')

def OnDrawPivots (self, ctx):
	gpu.state.blend_set('ALPHA')
	gpu.state.line_width_set(2)
	shader = gpu.shader.from_builtin('UNIFORM_COLOR')
	shader.bind()
	shader.uniform_float('color', VISUALIZER_CLR)
	for ob in self.obs:
		prevRotMode = ob.rotation_mode
		ob.rotation_mode = 'XYZ'
		matrix = Matrix.LocRotScale(Vector((0, 0, 0)), ob.rotation_euler, Vector((1, 1, 1)))
		if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE':
			size = ob.scale * ob.empty_display_size
			imgSize = Vector(list(ob.data.size) + [0])
			if imgSize.x > imgSize.y:
				size.x *= imgSize.x / imgSize.y
			else:
				size.y *= imgSize.y / imgSize.x
			_min = ob.location - size / 2
			_max = ob.location + size / 2
		else:
			_min, _max = GetRectMinMax(ob)
			size = _max - _min
		pivot = Vector(list(ob.pivot) + [0]) / 100
		pivot = _min + size * pivot
		pnt = matrix @ (pivot + Vector((-1, 0, 0)))
		pnt2 = matrix @ (pivot + Vector((1, 0, 0)))
		batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
		batch.draw(shader)
		pnt = matrix @ (pivot + Vector((0, -1, 0)))
		pnt2 = matrix @ (pivot + Vector((0, 1, 0)))
		batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
		batch.draw(shader)
		ob.rotation_mode = prevRotMode
	gpu.state.blend_set('NONE')

def OnDrawColliderHandles (self, ctx):
	for ob in self.obs:
		for handle in [child for child in ob.children if child.name.startswith(ob.name + '_Handle')]:
			try:
				if ob.colliderShapeType == 'ball':
					pass
				elif ob.colliderShapeType == 'halfspace':
					pass
				elif ob.colliderShapeType == 'cuboid':
					pass
				elif ob.colliderShapeType == 'roundCuboid':
					pass
				elif ob.colliderShapeType == 'capsule':
					pass
				elif ob.colliderShapeType == 'segment' or ob.colliderShapeType == 'triangle' or ob.colliderShapeType == 'roundTriangle' or ob.colliderShapeType == 'polyline' or ob.colliderShapeType == 'trimesh' or ob.colliderShapeType == 'convexHull' or ob.colliderShapeType == 'roundConvexHull':
					handleIdxStr = handle.name.rsplit('_Handle', 1)[-1]
					handleIdx = int(handleIdxStr)
					newPos = handle.location
					propName = f'collider{ob.colliderShapeType[0].upper() + ob.colliderShapeType[1 :]}Pnt{handleIdx}'
					currVal = getattr(ob, propName)
					if (currVal[0] != newPos.x) or (currVal[1] != newPos.y):
						setattr(ob, propName, (newPos.x, newPos.y))
				elif ob.colliderShapeType == 'heightField':
					pass
			except (ValueError, IndexError, AttributeError):
				continue

def GetLastUsedPropertyIndex (ob, usePropName, propCnt, minIdx = 0) -> int:
	for i in range(propCnt - 1, minIdx - 1, -1):
		if getattr(ob, usePropName + str(i)):
			return i
	return -1

canUpdateProps = True
def OnUpdateProperty (self, ctx, propName):
	global canUpdateProps
	if not canUpdateProps:
		return
	canUpdateProps = False
	for ob in ctx.selected_objects:
		if ob != self:
			setattr(ob, propName, getattr(self, propName))

def OnUpdateTint (self, ctx):
	for ob in ctx.selected_objects:
		ob.color = list(ob.tint) + [ob.color[3]]
	OnUpdateProperty (ob, ctx, 'tint')

def Update ():
	canUpdateProps = True
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
					attachedTxt = getattr(ob, 'apiScript%i' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(ob, 'apiScript%i' %i, origTxt)
								break
					attachedTxt = getattr(ob, 'runtimeScript%i' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(ob, 'runtimeScript%i' %i, origTxt)
								break
			bpy.data.texts.remove(txt)
	return 0.1

CAP_TYPES = ['butt', 'round', 'square']
CAP_TYPE_ITEMS = [('butt', 'butt', ''), ('round', 'round', ''), ('square', 'square', '')]
JOIN_TYPES = ['arcs', 'bevl', 'miter', 'miter-clip', 'round']
JOIN_TYPE_ITEMS = [('arcs', 'arcs', ''), ('bevel', 'bevel', ''), ('miter', 'miter', ''), ('miter-clip', 'miter-clip', ''), ('round', 'round', '')]
MINIFY_METHOD_ITEMS = [('none', 'none', ''), ('terser', 'terser', ''), ('roadroller', 'roadroller', '')]
SHAPE_TYPE_ITEMS = [('ball', 'circle', ''), ('halfspace', 'half-space', ''), ('cuboid', 'rectangle', ''), ('roundCuboid', 'rounded-rectangle', ''), ('capsule', 'capsule', ''), ('segment', 'segment', ''), ('triangle', 'triangle', ''), ('roundTriangle', 'rounded-triangle', ''), ('polyline', 'segment-series', ''), ('trimesh', 'triangle-mesh', ''), ('convexHull', 'convex-polygon', ''), ('roundConvexHull', 'rounded-convex-polygon', ''), ('heightfield', 'heightfield', ''), ]
SHAPE_TYPES = ['ball', 'halfspace', 'cuboid', 'roundCuboid', 'capsule', 'segment', 'triangle', 'roundTriangle', 'polyline', 'trimesh', 'convexHull', 'roundConvexHull', 'heightfield']
RIGID_BODY_TYPE_ITEMS = [('dynamic', 'dynamic', ''), ('fixed', 'fixed', ''), ('kinematicPositionBased', 'kinematic-position-based', ''), ('kinematicVelocityBased', 'kinematic-velocity-based', '')]
RIGID_BODY_TYPES = ['dynamic', 'fixed', 'kinematicPositionBased', 'kinematicVelocityBased']
JOINT_TYPE_ITEMS = [('fixed', 'fixed', ''), ('spring', 'spring', ''), ('revolute', 'revolute', ''), ('prismatic', 'prismatic', ''), ('rope', 'rope', '')]
SCRIPT_TYPE_ITEMS = [('html', 'html', ''), ('exe', 'exe', ''), ('unity', 'unity', '')]
BOUNCINESS_COMBINE_RULE_ITEMS = [('average', 'average', ''), ('minimum', 'min', ''), ('multiply', 'multiply', ''), ('maximum', 'max', '')]
BOUNCINESS_COMBINE_RULES = ['average', 'minimum', 'multiply', 'maximum']

bpy.types.World.exportScale = bpy.props.FloatProperty(name = 'Scale', default = 1)
bpy.types.World.exportOff = bpy.props.IntVectorProperty(name = 'Offset', size = 2)
bpy.types.World.htmlPath = bpy.props.StringProperty(name = 'Export .html')
bpy.types.World.exePath = bpy.props.StringProperty(name = 'Export .exe')
bpy.types.World.zipPath = bpy.props.StringProperty(name = 'Export .zip')
bpy.types.World.unityProjPath = bpy.props.StringProperty(name = 'Unity project path', default = TMP_DIR + '/TestUnityProject')
bpy.types.World.minifyMethod = bpy.props.EnumProperty(name = 'Minify using library', items = MINIFY_METHOD_ITEMS)
bpy.types.World.js13kbjam = bpy.props.BoolProperty(name = 'Error on export if output is over 13kb')
bpy.types.World.invalidHtml = bpy.props.BoolProperty(name = 'Save space with invalid html wrapper')
bpy.types.World.unitLen = bpy.props.FloatProperty(name = 'Unit length', min = 0, default = 1)
bpy.types.World.debugMode = bpy.props.BoolProperty(name = 'Debug mode', default = True)
bpy.types.Object.export = bpy.props.BoolProperty(name = 'Export', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'export'))
bpy.types.Object.roundPosAndSize = bpy.props.BoolProperty(name = 'Round position and size', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'roundPosAndSize'))
bpy.types.Object.pivot = bpy.props.FloatVectorProperty(name = 'Pivot point', size = 2, default = [50, 50], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'pivot'))
bpy.types.Object.useStroke = bpy.props.BoolProperty(name = 'Use stroke', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useStroke'))
bpy.types.Object.strokeWidth = bpy.props.FloatProperty(name = 'Stroke width', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeWidth'))
bpy.types.Object.strokeClr = bpy.props.FloatVectorProperty(name = 'Stroke color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = [0, 0, 0, 1], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeClr'))
bpy.types.Object.gradientFill = bpy.props.PointerProperty(name = 'Fill with light', type = bpy.types.Light, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'gradientFill'))
bpy.types.Object.capType = bpy.props.EnumProperty(name = 'Stroke cap type', items = CAP_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'capType'))
bpy.types.Object.joinType = bpy.props.EnumProperty(name = 'Stroke corner type', items = JOIN_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'joinType'))
bpy.types.Object.dashLengthsAndSpaces = bpy.props.FloatVectorProperty(name = 'Stroke dash lengths and spaces', size = 5, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'dashLengthsAndSpaces'))
bpy.types.Object.mirrorX = bpy.props.BoolProperty(name = 'Mirror on x-axis', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'mirrorX'))
bpy.types.Object.mirrorY = bpy.props.BoolProperty(name = 'Mirror on y-axis', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'mirrorY'))
bpy.types.Object.useJiggle = bpy.props.BoolProperty(name = 'Use jiggle', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useJiggle'))
bpy.types.Object.jiggleDist = bpy.props.FloatProperty(name = 'Jiggle distance', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jiggleDist'))
bpy.types.Object.jiggleDur = bpy.props.FloatProperty(name = 'Jiggle duration', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jiggleDur'))
bpy.types.Object.jiggleFrames = bpy.props.IntProperty(name = 'Jiggle frames', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jiggleFrames'))
bpy.types.Object.useRot = bpy.props.BoolProperty(name = 'Use rotate', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useRot'))
bpy.types.Object.rotPingPong = bpy.props.BoolProperty(name = 'Ping pong rotate', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rotPingPong'))
bpy.types.Object.rotAngRange = bpy.props.FloatVectorProperty(name = 'Rotate ang range', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rotAngRange'))
bpy.types.Object.rotDur = bpy.props.FloatProperty(name = 'Rotate duration', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rotDur'))
bpy.types.Object.useScale = bpy.props.BoolProperty(name = 'Use scale', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useScale'))
bpy.types.Object.scalePingPong = bpy.props.BoolProperty(name = 'Ping pong scale', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scalePingPong'))
bpy.types.Object.scaleXRange = bpy.props.FloatVectorProperty(name = 'X scale range', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scaleXRange'))
bpy.types.Object.scaleYRange = bpy.props.FloatVectorProperty(name = 'Y scale range', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scaleYRange'))
bpy.types.Object.scaleDur = bpy.props.FloatProperty(name = 'Scale duration', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scaleDur'))
bpy.types.Object.scaleHaltDurAtMin = bpy.props.FloatProperty(name = 'Halt duration at min', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scaleHaltDurAtMin'))
bpy.types.Object.scaleHaltDurAtMax = bpy.props.FloatProperty(name = 'Halt duration at max', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scaleHaltDurAtMax'))
bpy.types.Object.cycleDur = bpy.props.FloatProperty(name = 'Cycle stroke duration', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'cycleDur'))
bpy.types.Object.clr2 = bpy.props.FloatVectorProperty(name = 'Color 2', subtype = 'COLOR', size = 4, min = 0, max = 1, default = [0, 0, 0, 0], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'clr2'))
bpy.types.Object.clr3 = bpy.props.FloatVectorProperty(name = 'Color 3', subtype = 'COLOR', size = 4, min = 0, max = 1, default = [0, 0, 0, 0], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'clr3'))
bpy.types.Object.clr1Alpha = bpy.props.FloatProperty(name = 'Color 1 alpha', min = 0, max = 1, default = 1, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'clr1Alpha'))
bpy.types.Object.clrPositions = bpy.props.IntVectorProperty(name = 'Color Positions', size = 3, min = 0, max = 100, default = [0, 50, 100], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'clrPositions'))
bpy.types.Object.subtractive = bpy.props.BoolProperty(name = 'Is subtractive', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'subtractive'))
bpy.types.Object.useFillHatch = bpy.props.BoolVectorProperty(name = 'Use fill hatch', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useFilLHatch'))
bpy.types.Object.fillHatchDensity = bpy.props.FloatVectorProperty(name = 'Fill hatch density', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'fillHatchDensity'))
bpy.types.Object.fillHatchRandDensity = bpy.props.FloatVectorProperty(name = 'Fill hatch randomize density percent', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'fillHatchRandDensity'))
bpy.types.Object.fillHatchAng = bpy.props.FloatVectorProperty(name = 'Fill hatch ang', size = 2, min = -360, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'fillHatchAng'))
bpy.types.Object.fillHatchWidth = bpy.props.FloatVectorProperty(name = 'Fill hatch width', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'fillHatchWidth'))
bpy.types.Object.useStrokeHatch = bpy.props.BoolVectorProperty(name = 'Use stroke hatch', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useStrokeHatch'))
bpy.types.Object.strokeHatchDensity = bpy.props.FloatVectorProperty(name = 'Stroke hatch density', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeHatchDensity'))
bpy.types.Object.strokeHatchRandDensity = bpy.props.FloatVectorProperty(name = 'Stroke hatch randomize density percent', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeHatchRandDenstiy'))
bpy.types.Object.strokeHatchAng = bpy.props.FloatVectorProperty(name = 'Stroke hatch ang', size = 2, min = -360, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeHatchAng'))
bpy.types.Object.strokeHatchWidth = bpy.props.FloatVectorProperty(name = 'Stroke hatch width', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeHatchWidth'))
bpy.types.Object.minPathFrame = bpy.props.IntProperty(name = 'Min frame for shape animation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minPathFrame'))
bpy.types.Object.maxPathFrame = bpy.props.IntProperty(name = 'Max frame for shape animation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxPathFrame'))
bpy.types.Object.minPosFrame = bpy.props.IntProperty(name = 'Min frame for position animation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minPosFrame'))
bpy.types.Object.maxPosFrame = bpy.props.IntProperty(name = 'Max frame for position animation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxPosFrame'))
bpy.types.Object.posPingPong = bpy.props.BoolProperty(name = 'Ping pong position animation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'posPingPong'))
bpy.types.Object.colliderExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderExists'))
bpy.types.Object.colliderEnable = bpy.props.BoolProperty(name = 'Enable', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderEnable'))
bpy.types.Object.colliderShapeType = bpy.props.EnumProperty(name = 'Shape type', items = SHAPE_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderShapeType'))
bpy.types.Object.colliderRadius = bpy.props.FloatProperty(name = 'Radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderRadius'))
bpy.types.Object.colliderNormal = bpy.props.FloatVectorProperty(name = 'Normal', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderNormal'))
bpy.types.Object.colliderSize = bpy.props.FloatVectorProperty(name = 'Size', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderSize'))
bpy.types.Object.colliderCuboidBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderCuboidBorderRadius'))
bpy.types.Object.colliderCapsuleHeight = bpy.props.FloatProperty(name = 'Height', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderCapsuleHeight'))
bpy.types.Object.colliderCapsuleRadius = bpy.props.FloatProperty(name = 'Radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderCapsuleRadius'))
bpy.types.Object.colliderIsVertical = bpy.props.BoolProperty(name = 'Is vertical', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderIsVertical'))
bpy.types.Object.colliderSegmentPnt0 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderSegmentPnt0'))
bpy.types.Object.colliderSegmentPnt1 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderSegmentPnt1'))
bpy.types.Object.colliderTrianglePnt0 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTrianglePnt0'))
bpy.types.Object.colliderTrianglePnt1 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTrianglePnt1'))
bpy.types.Object.colliderTrianglePnt2 = bpy.props.FloatVectorProperty(name = 'Position 3', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTrianglePnt2'))
bpy.types.Object.colliderTriangleBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTriangleBorderRadius'))
bpy.types.Object.colliderConvexHullBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderConvexHullBorderRadius'))
bpy.types.Object.colliderHeightfieldScale = bpy.props.FloatVectorProperty(name = 'Scale', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderHeightfieldScale'))
bpy.types.Object.isSensor = bpy.props.BoolProperty(name = 'Is sensor', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'isSensor'))
bpy.types.Object.density = bpy.props.FloatProperty(name = 'Density', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'density'))
bpy.types.Object.bounciness = bpy.props.FloatProperty(name = 'Bounciness', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'bounciness'))
bpy.types.Object.bouncinessCombineRule = bpy.props.EnumProperty(name = 'Bounciness combine rule', items = BOUNCINESS_COMBINE_RULE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'bouncinessCombineRule'))
bpy.types.Object.collisionGroupMembership = bpy.props.BoolVectorProperty(name = 'Collision group membership', size = 16, default = [True] * 16, description = 'Which collision groups this object belongs to', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'collisionGroupMembership'))
bpy.types.Object.collisionGroupFilter = bpy.props.BoolVectorProperty(name = 'Collision group filter', size = 16, default = [True] * 16, description = 'Which collision groups this object can collide with', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'collisionGroupFilter'))
bpy.types.Object.rigidBodyExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rigidBodyExists'))
bpy.types.Object.rigidBodyEnable = bpy.props.BoolProperty(name = 'Enable', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rigidBodyEnable'))
bpy.types.Object.rigidBodyType = bpy.props.EnumProperty(name = 'Type', items = RIGID_BODY_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'rigidBodyType'))
bpy.types.Object.linearDrag = bpy.props.FloatProperty(name = 'Linear drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'linearDrag'))
bpy.types.Object.angDrag = bpy.props.FloatProperty(name = 'Angular drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'angDrag'))
bpy.types.Object.dominance = bpy.props.IntProperty(name = 'Dominance', min = -127, max = 127, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'dominance'))
bpy.types.Object.continuousCollideDetect = bpy.props.BoolProperty(name = 'Continuous collision detection', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'continuousCollideDetect'))
bpy.types.Object.gravityScale = bpy.props.FloatProperty(name = 'Gravity scale', default = 1, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'gravityScale'))
bpy.types.Object.canSleep = bpy.props.BoolProperty(name = 'Can sleep', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'canSleep'))
bpy.types.Object.canRot = bpy.props.BoolProperty(name = 'Can rotate', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'canRot'))
bpy.types.Object.jointExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jointExists'))
bpy.types.Object.jointType = bpy.props.EnumProperty(name = 'Type', items = JOINT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jointType'))
bpy.types.Object.anchorPos1 = bpy.props.FloatVectorProperty(name = 'Anchor position 1', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorPos1'))
bpy.types.Object.anchorPos2 = bpy.props.FloatVectorProperty(name = 'Anchor position 2', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorPos2'))
bpy.types.Object.anchorRot1 = bpy.props.FloatProperty(name = 'Anchor rotation 1', min = 0, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorRot1'))
bpy.types.Object.anchorRot2 = bpy.props.FloatProperty(name = 'Anchor rotation 2', min = 0, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorRot2'))
bpy.types.Object.anchorRigidBody1 = bpy.props.PointerProperty(name = 'Anchor rigid body 1', type = bpy.types.Object, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorRigidBody1'))
bpy.types.Object.anchorRigidBody2 = bpy.props.PointerProperty(name = 'Anchor rigid body 2', type = bpy.types.Object, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'anchorRigidBody2'))
bpy.types.Object.restLen = bpy.props.FloatProperty(name = 'Rest length', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'restLen'))
bpy.types.Object.stiffness = bpy.props.FloatProperty(name = 'Stiffness', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stiffness'))
bpy.types.Object.damping = bpy.props.FloatProperty(name = 'Damping', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'damping'))
bpy.types.Object.jointAxis = bpy.props.FloatVectorProperty(name = 'Axis', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'jointAxis'))
bpy.types.Object.jointLen = bpy.props.FloatProperty(name = 'Length', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'joinLen'))
bpy.types.Object.charControllerExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'charControllerExists'))
bpy.types.Object.contactOff = bpy.props.FloatProperty(name = 'Contact offset', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'contactOff'))
bpy.types.Object.resPercent = bpy.props.IntProperty(name = 'Resolution percent', min = 0, max = 100, default = 100, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'resPercent'))
bpy.types.Object.tint = bpy.props.FloatVectorProperty(name = 'Tint', subtype = 'COLOR', size = 3, min = 0, max = 1, default = [1, 1, 1], update = lambda ob, ctx : OnUpdateTint (ob, ctx))
bpy.types.Object.particleSystemExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'particleSystemExists'))
bpy.types.Object.particleSystemEnable = bpy.props.BoolProperty(name = 'Enable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'particleSystemEnable'))
bpy.types.Object.particle = bpy.props.PointerProperty(name = 'Particle', type = bpy.types.Object, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'particle'))
bpy.types.Object.prewarmDur = bpy.props.FloatProperty(name = 'Prewarm duration', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'prewarmDur'))
bpy.types.Object.useMinMaxEmitRate = bpy.props.BoolProperty(name = 'Use min and max emit rate', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxEmitRate'))
bpy.types.Object.minEmitRate = bpy.props.FloatProperty(name = 'Min emit rate', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitRate'))
bpy.types.Object.maxEmitRate = bpy.props.FloatProperty(name = 'Max emit rate', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitRate'))
bpy.types.Object.emitRate = bpy.props.FloatProperty(name = 'Emit rate', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitRate'))
bpy.types.Object.useMinMaxEmitSpeed = bpy.props.BoolProperty(name = 'Use min and max initial particle speed', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxEmitSpeed'))
bpy.types.Object.emitSpeed = bpy.props.FloatProperty(name = 'Initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitSpeed'))
bpy.types.Object.minEmitSpeed = bpy.props.FloatProperty(name = 'Min initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitSpeed'))
bpy.types.Object.maxEmitSpeed = bpy.props.FloatProperty(name = 'Max initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitSpeed'))
bpy.types.Object.useMinMaxLife = bpy.props.BoolProperty(name = 'Use min and max initial particle lifetime', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxLife'))
bpy.types.Object.minLife = bpy.props.FloatProperty(name = 'Min initial particle lifetime', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minLife'))
bpy.types.Object.maxLife = bpy.props.FloatProperty(name = 'Max initial particle lifetime', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxLife'))
bpy.types.Object.life = bpy.props.FloatProperty(name = 'Initial particle lifetime', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'life'))
bpy.types.Object.emitSpeed = bpy.props.FloatProperty(name = 'Initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitSpeed'))
bpy.types.Object.minEmitSpeed = bpy.props.FloatProperty(name = 'Min initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitSpeed'))
bpy.types.Object.maxEmitSpeed = bpy.props.FloatProperty(name = 'Max initial particle speed', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitSpeed'))
bpy.types.Object.useMinMaxEmitRot = bpy.props.BoolProperty(name = 'Use min and max initial particle rotation', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxEmitRot'))
bpy.types.Object.minEmitRot = bpy.props.FloatProperty(name = 'Min initial particle rotation', min = 0, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitRot'))
bpy.types.Object.maxEmitRot = bpy.props.FloatProperty(name = 'Max initial particle rotation', min = 0, max = 360, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitRot'))
bpy.types.Object.useMinMaxEmitSize = bpy.props.BoolProperty(name = 'Use min and max initial particle size', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxEmitSize'))
bpy.types.Object.minEmitSize = bpy.props.FloatProperty(name = 'Min initial particle size', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitSize'))
bpy.types.Object.maxEmitSize = bpy.props.FloatProperty(name = 'Max initial particle size', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitSize'))
bpy.types.Object.emitTint = bpy.props.FloatVectorProperty(name = 'Initial particle tint', subtype = 'COLOR', size = 4, min = 0, max = 1, default = [1, 1, 1, 1], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitTint'))
bpy.types.Object.emitShapeType = bpy.props.EnumProperty(name = 'Shape type', items = SHAPE_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitShapeType'))
bpy.types.Object.emitRadius = bpy.props.FloatProperty(name = 'Shape type', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitRadius'))
bpy.types.Object.useMinMaxEmitRadiusNormalized = bpy.props.BoolProperty(name = 'Use min and max shape radius normalized', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxEmitRadiusNormalized'))
bpy.types.Object.minEmitRadiusNormalized = bpy.props.FloatProperty(name = 'Min shape radius normalized', min = 0, max = 1, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minEmitRadiusNormalized'))
bpy.types.Object.maxEmitRadiusNormalized = bpy.props.FloatProperty(name = 'Max shape radius normalized', min = 0, max = 1, default = 1, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxEmitRadiusNormalized'))
bpy.types.Object.emitRadiusNormalized = bpy.props.FloatProperty(name = 'Shape radius normalized', min = 0, max = 1, default = 1, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitRadiusNormalized'))
bpy.types.Object.useMinMaxLinearDrag = bpy.props.BoolProperty(name = 'Use min and max linear drag', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxLinearDrag'))
bpy.types.Object.minLinearDrag = bpy.props.FloatProperty(name = 'Min linear drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minLinearDrag'))
bpy.types.Object.maxLinearDrag = bpy.props.FloatProperty(name = 'Max linear drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxLinearDrag'))
bpy.types.Object.useMinMaxAngDrag = bpy.props.BoolProperty(name = 'Use min and max angular drag', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxAngDrag'))
bpy.types.Object.minAngDrag = bpy.props.FloatProperty(name = 'Min angular drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minAngDrag'))
bpy.types.Object.maxAngDrag = bpy.props.FloatProperty(name = 'Max angular drag', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxAngDrag'))
bpy.types.Object.useMinMaxGravityScale = bpy.props.BoolProperty(name = 'Use min and max gravity scale', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxGravityScale'))
bpy.types.Object.minGravityScale = bpy.props.FloatProperty(name = 'Min gravity scale', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minGravityScale'))
bpy.types.Object.maxGravityScale = bpy.props.FloatProperty(name = 'Max gravity scale', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxGravityScale'))
bpy.types.Object.useMinMaxBounciness = bpy.props.BoolProperty(name = 'Use min and max bounciness', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinMaxBounciness'))
bpy.types.Object.minBounciness = bpy.props.FloatProperty(name = 'Min bounciness', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minBounciness'))
bpy.types.Object.maxBounciness = bpy.props.FloatProperty(name = 'Max bounciness', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'maxBounciness'))

for i in range(MAX_SCRIPTS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'apiScript%i' %i,
		bpy.props.PointerProperty(name = 'API script%i' %i, type = bpy.types.Text, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'API script%i' %i))
	)
	setattr(
		bpy.types.Object,
		'apiScriptDisable%i' %i,
		bpy.props.BoolProperty(name = 'Disable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'apiScriptDisable%i' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%i' %i,
		bpy.props.PointerProperty(name = 'Runtime script%i' %i, type = bpy.types.Text, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScript%i' %i))
	)
	setattr(
		bpy.types.Object,
		'apiScriptType%i' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'apiScriptType%i' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScriptDisable%i' %i,
		bpy.props.BoolProperty(name = 'Disable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScriptDisable%i' %i))
	)
	setattr(
		bpy.types.Object,
		'initScript%i' %i,
		bpy.props.BoolProperty(name = 'Is init', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'initScript%i' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScriptType%i' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScriptType%i' %i))
	)
for i in range(MAX_SHAPE_PNTS):
	setattr(
		bpy.types.Object,
		'colliderPolylinePnt%i' %i,
		bpy.props.FloatVectorProperty(name = 'Point%i' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderPolylinePnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderPolylinePnt%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderPolylinePnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'colliderPolylineIdx%i' %i,
		bpy.props.IntVectorProperty(name = 'Index%i' %i, size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderPolylineIdx%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderPolylineIdx%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderPolylineIdx%i' %i))
	)
	setattr(
		bpy.types.Object,
		'colliderTrimeshPnt%i' %i,
		bpy.props.FloatVectorProperty(name = 'Point%i' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTrimeshPnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderTrimeshPnt%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderTrimeshPnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'colliderTrimeshIdx%i' %i,
		bpy.props.IntVectorProperty(name = 'Index%i' %i, size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderTrimeshIdx%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderTrimeshIdx%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderTrimeshIdx%i' %i))
	)
	setattr(
		bpy.types.Object,
		'colliderConvexHullPnt%i' %i,
		bpy.props.FloatVectorProperty(name = 'Point%i' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderConvexHullPnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderConvexHullPnt%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderConvexHullPnt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'colliderHeight%i' %i,
		bpy.props.FloatProperty(name = 'Point%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderHeight%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useColliderHeight%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useColliderHeight%i' %i))
	)
for i in range(MAX_ATTACH_COLLIDER_CNT):
	setattr(
		bpy.types.Object,
		'attachTo%i' %i,
		bpy.props.PointerProperty(name = 'Rigid body%i' %i, type = bpy.types.Object, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'attachTo%i' %i))
	)
	setattr(
		bpy.types.Object,
		'attach%i' %i,
		bpy.props.BoolProperty(name = 'Attach to rigid body%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'attach%i' %i))
	)
for i in range(MAX_POTRACE_PASSES_PER_OBJECT_MAT):
	setattr(
		bpy.types.Object,
		'minVisibleClrValue%i' %i,
		bpy.props.FloatProperty(name = 'Min visible color value', min = 0, max = 1, default = .01, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minVisibleClrValue%i' %i))
	)
	setattr(
		bpy.types.Object,
		'tintOutput%i' %i,
		bpy.props.FloatVectorProperty(name = 'Tint output', subtype = 'COLOR', size = 4, min = 0, default = [1, 1, 1, 1], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'tintOutput%i' %i))
	)
	if i > 0:
		setattr(
			bpy.types.Object,
			'useMinVisibleClrValue%i' %i,
			bpy.props.BoolProperty(name = 'Use', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinVisibleClrValue%i' %i))
		)
for i in range(MAX_ATTRIBUTES_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'boolName%i' %i,
		bpy.props.StringProperty(name = 'Bool name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'boolName%i' %i))
	)
	setattr(
		bpy.types.Object,
		'boolVal%i' %i,
		bpy.props.BoolProperty(name = 'Bool value%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'boolVal%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useBool%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useBool%i' %i))
	)
	setattr(
		bpy.types.Object,
		'intName%i' %i,
		bpy.props.StringProperty(name = 'Int name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intName%i' %i))
	)
	setattr(
		bpy.types.Object,
		'intVal%i' %i,
		bpy.props.IntProperty(name = 'Int value%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intVal%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useInt%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useInt%i' %i))
	)
	setattr(
		bpy.types.Object,
		'floatName%i' %i,
		bpy.props.StringProperty(name = 'Float name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatName%i' %i))
	)
	setattr(
		bpy.types.Object,
		'floatVal%i' %i,
		bpy.props.FloatProperty(name = 'Float value%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatVal%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useFloat%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useFloat%i' %i))
	)
	setattr(
		bpy.types.Object,
		'stringName%i' %i,
		bpy.props.StringProperty(name = 'String name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringName%i' %i))
	)
	setattr(
		bpy.types.Object,
		'stringVal%i' %i,
		bpy.props.StringProperty(name = 'String value%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringVal%i' %i))
	)
	setattr(
		bpy.types.Object,
		'useString%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useString%i' %i))
	)
	setattr(
		bpy.types.Object,
		'boolArrayName%i' %i,
		bpy.props.StringProperty(name = 'Bool array name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'boolArrayName%i' %i))
	)
	for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
		setattr(
			bpy.types.Object,
			'boolArrayVal%i,%i' %(i, i2),
			bpy.props.BoolProperty(name = 'Bool array value%i,%i' %(i, i2), update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'boolArrayVal%i,%i' %(i, i2)))
		)
		setattr(
			bpy.types.Object,
			'useBoolArray%i,%i' %(i, i2),
			bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useBoolArray%i,%i' %(i, i2)))
		)
	setattr(
		bpy.types.Object,
		'useBoolArray%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useBoolArray%i' %i))
	)
	setattr(
		bpy.types.Object,
		'intArrayName%i' %i,
		bpy.props.StringProperty(name = 'Int array name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intArrayName%i' %i))
	)
	for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
		setattr(
			bpy.types.Object,
			'intArrayVal%i,%i' %(i, i2),
			bpy.props.IntProperty(name = 'Int array value%i,%i' %(i, i2), update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intArrayVal%i,%i' %(i, i2)))
		)
		setattr(
			bpy.types.Object,
			'useIntArray%i,%i' %(i, i2),
			bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useIntArray%i,%i' %(i, i2)))
		)
	setattr(
		bpy.types.Object,
		'useIntArray%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useIntArray%i' %i))
	)
	setattr(
		bpy.types.Object,
		'floatArrayName%i' %i,
		bpy.props.StringProperty(name = 'Float array name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatArrayName%i' %i))
	)
	for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
		setattr(
			bpy.types.Object,
			'floatArrayVal%i,%i' %(i, i2),
			bpy.props.FloatProperty(name = 'Float array value%i,%i' %(i, i2), update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatArrayVal%i,%i' %(i, i2)))
		)
		setattr(
			bpy.types.Object,
			'useFloatArray%i,%i' %(i, i2),
			bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useFloatArray%i,%i' %(i, i2)))
		)
	setattr(
		bpy.types.Object,
		'useFloatArray%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useFloatArray%i' %i))
	)
	setattr(
		bpy.types.Object,
		'stringArrayName%i' %i,
		bpy.props.StringProperty(name = 'String array name%i' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringArrayName%i' %i))
	)
	for i2 in range(MAX_ELTS_IN_ATTRIBUTES_ARR):
		setattr(
			bpy.types.Object,
			'stringArrayVal%i,%i' %(i, i2),
			bpy.props.StringProperty(name = 'String array value%i,%i' %(i, i2), update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringArrayVal%i,%i' %(i, i2)))
		)
		setattr(
			bpy.types.Object,
			'useStringArray%i,%i' %(i, i2),
			bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useStringArray%i,%i' %(i, i2)))
		)
	setattr(
		bpy.types.Object,
		'useStringArray%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useStringArray%i' %i))
	)
for i in range(MAX_RENDER_CAMS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'renderCam%i' %i,
		bpy.props.PointerProperty(name = 'Render camera%i' %i, type = bpy.types.Camera, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'renderCam%i' %i))
	)

@bpy.utils.register_class
class HTMLExport (bpy.types.Operator):
	bl_idname = 'world.html_export'
	bl_label = 'Export to HTML'

	@classmethod
	def poll (cls, ctx):
		return True

	def execute (self, ctx):
		BuildHtml (ctx.world)
		return {'FINISHED'}

@bpy.utils.register_class
class ExeExport (bpy.types.Operator):
	bl_idname = 'world.exe_export'
	bl_label = 'Export to Exe'

	@classmethod
	def poll (cls, ctx):
		return True

	def execute (self, ctx):
		BuildExe (ctx.world)
		return {'FINISHED'}

@bpy.utils.register_class
class UnityExport (bpy.types.Operator):
	bl_idname = 'world.unity_export'
	bl_label = 'Export to Unity'

	@classmethod
	def poll (cls, ctx):
		return True

	def execute (self, ctx):
		BuildUnity (ctx.world)
		return {'FINISHED'}

@bpy.utils.register_class
class WorldPanel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_World_Panel'
	bl_label = 'Export'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, ctx):
		row = self.layout.row()
		row.prop(ctx.world, 'exportScale')
		self.layout.prop(ctx.world, 'exportOff')
		self.layout.prop(ctx.world, 'htmlPath')
		self.layout.prop(ctx.world, 'exePath')
		self.layout.prop(ctx.world, 'zipPath')
		self.layout.prop(ctx.world, 'unityProjPath')
		if usePhysics:
			self.layout.prop(ctx.world, 'unitLen')
		self.layout.prop(ctx.world, 'debugMode')
		self.layout.operator('world.html_export', icon = 'CONSOLE')
		self.layout.operator('world.exe_export', icon = 'CONSOLE')
		self.layout.operator('world.unity_export', icon = 'CONSOLE')

@bpy.utils.register_class
class JS13KBPanel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_JS13KB_Panel'
	bl_label = 'js13kgames.com'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, ctx):
		self.layout.prop(ctx.world, 'js13kbjam')
		row = self.layout.row()
		row.prop(ctx.world, 'minifyMethod')
		row.prop(ctx.world, 'invalidHtml')
		if buildInfo['zip-size']:
			self.layout.label(text = buildInfo['zip'])
			if buildInfo['zip-size'] <= 1024 * 13:
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

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		self.layout.prop(ob, 'export')
		if ob.type == 'CURVE' or ob.type == 'MESH' or ob.type == 'GREASEPENCIL':
			self.layout.prop(ob, 'roundPosAndSize')
			self.layout.prop(ob, 'pivot')
			self.layout.prop(ob, 'useStroke')
			if ob.useStroke:
				self.layout.prop(ob, 'strokeWidth')
				self.layout.prop(ob, 'strokeClr')
				self.layout.prop(ob, 'capType')
				self.layout.prop(ob, 'joinType')
				self.layout.prop(ob, 'dashLengthsAndSpaces')
			self.layout.prop(ob, 'gradientFill')
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
			self.layout.prop(ob, 'useRot')
			if ob.useRot:
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
			self.layout.prop(ob, 'resPercent')
		if ob.type == 'MESH' or ob.type == 'GREASEPENCIL':
			for i in range(GetLastUsedPropertyIndex(ob, 'useMinVisibleClrValue', MAX_POTRACE_PASSES_PER_OBJECT_MAT) + 2, 1):
				row = self.layout.row()
				row.prop(ob, 'minVisibleClrValue%i' %i)
				row.prop(ob, 'tintOutput%i' %i)
				if i > 0:
					row.prop(ob, 'useMinVisibleClrValue%i' %i)
			for i in range(GetLastUsedPropertyIndex(ob, 'renderCam', MAX_RENDER_CAMS_PER_OBJECT) + 2):
				self.layout.prop(ob, 'renderCam%i' %i)
		self.layout.label(text = 'Scripts')
		for i in range(GetLastUsedPropertyIndex(ob, 'apiScript', MAX_SCRIPTS_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'apiScript%i' %i)
			row.prop(ob, 'apiScriptType%i' %i)
			row.prop(ob, 'apiScriptDisable%i' %i)
		for i in range(GetLastUsedPropertyIndex(ob, 'runtimeScript', MAX_SCRIPTS_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'runtimeScript%i' %i)
			row.prop(ob, 'initScript%i' %i)
			row.prop(ob, 'runtimeScriptType%i' %i)
			row.prop(ob, 'runtimeScriptDisable%i' %i)

@bpy.utils.register_class
class AttributesPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Attributes_Panel'
	bl_label = 'Attributes'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		for i in range(GetLastUsedPropertyIndex(ob, 'useBool', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'boolName%i' %i)
			row.prop(ob, 'boolVal%i' %i)
			row.prop(ob, 'useBool%i' %i)
		for i in range(GetLastUsedPropertyIndex(ob, 'useInt', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'intName%i' %i)
			row.prop(ob, 'intVal%i' %i)
			row.prop(ob, 'useInt%i' %i)
		for i in range(GetLastUsedPropertyIndex(ob, 'useFloat', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'floatName%i' %i)
			row.prop(ob, 'floatVal%i' %i)
			row.prop(ob, 'useFloat%i' %i)
		for i in range(GetLastUsedPropertyIndex(ob, 'useString', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'stringName%i' %i)
			row.prop(ob, 'stringVal%i' %i)
			row.prop(ob, 'useString%i' %i)
		for i in range(GetLastUsedPropertyIndex(ob, 'useBoolArray', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'boolArrayName%i' %i)
			row.prop(ob, 'useBoolArray%i' %i)
			if getattr(ob, 'useBoolArray%i' %i):
				for i2 in range(GetLastUsedPropertyIndex(ob, 'useBoolArray%i,' %i, MAX_ELTS_IN_ATTRIBUTES_ARR) + 2):
					row = self.layout.row()
					row.prop(ob, 'boolArrayVal%i,%i' %(i, i2))
					row.prop(ob, 'useBoolArray%i,%i' %(i, i2))
		for i in range(GetLastUsedPropertyIndex(ob, 'useIntArray', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'intArrayName%i' %i)
			row.prop(ob, 'useIntArray%i' %i)
			if getattr(ob, 'useIntArray%i' %i):
				for i2 in range(GetLastUsedPropertyIndex(ob, 'useIntArray%i,' %i, MAX_ELTS_IN_ATTRIBUTES_ARR) + 2):
					row = self.layout.row()
					row.prop(ob, 'intArrayVal%i,%i' %(i, i2))
					row.prop(ob, 'useIntArray%i,%i' %(i, i2))
		for i in range(GetLastUsedPropertyIndex(ob, 'useFloatArray', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'floatArrayName%i' %i)
			row.prop(ob, 'useFloatArray%i' %i)
			if getattr(ob, 'useFloatArray%i' %i):
				for i2 in range(GetLastUsedPropertyIndex(ob, 'useFloatArray%i,' %i, MAX_ELTS_IN_ATTRIBUTES_ARR) + 2):
					row = self.layout.row()
					row.prop(ob, 'floatArrayVal%i,%i' %(i, i2))
					row.prop(ob, 'useFloatArray%i,%i' %(i, i2))
		for i in range(GetLastUsedPropertyIndex(ob, 'useStringArray', MAX_ATTRIBUTES_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'stringArrayName%i' %i)
			row.prop(ob, 'useStringArray%i' %i)
			if getattr(ob, 'useStringArray%i' %i):
				for i2 in range(GetLastUsedPropertyIndex(ob, 'useStringArray%i,' %i, MAX_ELTS_IN_ATTRIBUTES_ARR) + 2):
					row = self.layout.row()
					row.prop(ob, 'stringArrayVal%i,%i' %(i, i2))
					row.prop(ob, 'useStringArray%i,%i' %(i, i2))

@bpy.utils.register_class
class LightPanel (bpy.types.Panel):
	bl_idname = 'LIGHT_PT_Light_Panel'
	bl_label = 'Gradient'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'data'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob or ob.type != 'LIGHT':
			return
		self.layout.prop(ob, 'clr2')
		self.layout.prop(ob, 'clr3')
		self.layout.prop(ob, 'clr1Alpha')
		self.layout.prop(ob, 'clrPositions')
		self.layout.prop(ob, 'subtractive')

@bpy.utils.register_class
class ImagePanel (bpy.types.Panel):
	bl_idname = 'IMAGE_PT_Image_Panel'
	bl_label = 'Image'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'data'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob or ob.type != 'EMPTY' or ob.empty_display_type != 'IMAGE':
			return
		self.layout.prop(ob, 'tint')

@bpy.utils.register_class
class ParticleSystemPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Particle_System_Panel'
	bl_label = 'Particle System'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		self.layout.prop(ob, 'particleSystemExists')
		if not ob.particleSystemExists:
			return
		self.layout.prop(ob, 'particleSystemEnable')
		self.layout.prop(ob, 'particle')
		self.layout.prop(ob, 'prewarmDur')
		self.layout.label(text = 'Emission')
		self.layout.prop(ob, 'useMinMaxEmitRate')
		if ob.useMinMaxEmitRate:
			self.layout.prop(ob, 'minEmitRate')
			self.layout.prop(ob, 'maxEmitRate')
		else:
			self.layout.prop(ob, 'emitRate')
		self.layout.prop(ob, 'useMinMaxLife')
		if ob.useMinMaxLife:
			self.layout.prop(ob, 'minLife')
			self.layout.prop(ob, 'maxLife')
		else:
			self.layout.prop(ob, 'life')
		self.layout.prop(ob, 'useMinMaxEmitSpeed')
		if ob.useMinMaxEmitSpeed:
			self.layout.prop(ob, 'minEmitSpeed')
			self.layout.prop(ob, 'maxEmitSpeed')
		else:
			self.layout.prop(ob, 'emitSpeed')
		self.layout.prop(ob, 'useMinMaxEmitRot')
		if ob.useMinMaxEmitRot:
			self.layout.prop(ob, 'minEmitRot')
			self.layout.prop(ob, 'maxEmitRot')
		self.layout.prop(ob, 'useMinMaxEmitSize')
		if ob.useMinMaxEmitSize:
			self.layout.prop(ob, 'minEmitSize')
			self.layout.prop(ob, 'maxEmitSize')
		self.layout.prop(ob, 'emitTint')
		self.layout.label(text = 'Shape')
		self.layout.prop(ob, 'emitShapeType')
		self.layout.prop(ob, 'emitRadius')
		self.layout.prop(ob, 'useMinMaxEmitRadiusNormalized')
		if ob.useMinMaxEmitRadiusNormalized:
			self.layout.prop(ob, 'minEmitRadiusNormalized')
			self.layout.prop(ob, 'maxEmitRadiusNormalized')
		else:
			self.layout.prop(ob, 'emitRadiusNormalized')
		self.layout.label(text = 'Physics')
		self.layout.prop(ob, 'useMinMaxGravityScale')
		if ob.useMinMaxGravityScale:
			self.layout.prop(ob, 'minGravityScale')
			self.layout.prop(ob, 'maxGravityScale')
		self.layout.prop(ob, 'useMinMaxLinearDrag')
		if ob.useMinMaxLinearDrag:
			self.layout.prop(ob, 'minLinearDrag')
			self.layout.prop(ob, 'maxLinearDrag')
		self.layout.prop(ob, 'useMinMaxAngDrag')
		if ob.useMinMaxAngDrag:
			self.layout.prop(ob, 'minAngDrag')
			self.layout.prop(ob, 'maxAngDrag')
		self.layout.prop(ob, 'useMinMaxBounciness')
		if ob.useMinMaxBounciness:
			self.layout.prop(ob, 'minBounciness')
			self.layout.prop(ob, 'maxBounciness')

@bpy.utils.register_class
class RigidBodyPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Rigid_Body_Panel'
	bl_label = 'Rigid Body'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, ctx):
		ob = ctx.active_object
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
		self.layout.prop(ob, 'canRot')

@bpy.utils.register_class
class ColliderPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Collider_Panel'
	bl_label = 'Collider'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		self.layout.prop(ob, 'colliderExists')
		if not ob.colliderExists:
			return
		self.layout.prop(ob, 'colliderEnable')
		self.layout.prop(ob, 'colliderShapeType')
		if ob.colliderShapeType == 'ball':
			self.layout.prop(ob, 'colliderRadius')
		elif ob.colliderShapeType == 'halfspace':
			self.layout.prop(ob, 'colliderNormal')
		elif ob.colliderShapeType == 'cuboid':
			self.layout.prop(ob, 'colliderSize')
		elif ob.colliderShapeType == 'roundCuboid':
			self.layout.prop(ob, 'colliderSize')
			self.layout.prop(ob, 'colliderCuboidBorderRadius')
		elif ob.colliderShapeType == 'capsule':
			self.layout.prop(ob, 'colliderCapsuleHeight')
			self.layout.prop(ob, 'colliderCapsuleRadius')
			self.layout.prop(ob, 'colliderIsVertical')
		elif ob.colliderShapeType == 'segment':
			self.layout.prop(ob, 'colliderSegmentPnt0')
			self.layout.prop(ob, 'colliderSegmentPnt1')
		elif ob.colliderShapeType == 'triangle':
			self.layout.prop(ob, 'colliderTrianglePnt0')
			self.layout.prop(ob, 'colliderTrianglePnt1')
			self.layout.prop(ob, 'colliderTrianglePnt2')
		elif ob.colliderShapeType == 'roundTriangle':
			self.layout.prop(ob, 'colliderTrianglePnt0')
			self.layout.prop(ob, 'colliderTrianglePnt1')
			self.layout.prop(ob, 'colliderTrianglePnt2')
			self.layout.prop(ob, 'colliderTriangleBorderRadius')
		elif ob.colliderShapeType == 'polyline':
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderPolylinePnt%i' %i)
				row.prop(ob, 'useColliderPolylinePnt%i' %i)
				if not getattr(ob, 'useColliderPolylinePnt%i' %i):
					break
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderPolylineIdx%i' %i)
				row.prop(ob, 'useColliderPolylineIdx%i' %i)
				if not getattr(ob, 'useColliderPolylineIdx%i' %i):
					break
		elif ob.colliderShapeType == 'trimesh':
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderTrimeshPnt%i' %i)
				row.prop(ob, 'useColliderTrimeshPnt%i' %i)
				if not getattr(ob, 'useColliderTrimeshPnt%i' %i):
					break
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderTrimeshIdx%i' %i)
				row.prop(ob, 'useColliderTrimeshIdx%i' %i)
				if not getattr(ob, 'useColliderTrimeshIdx%i' %i):
					break
		elif ob.colliderShapeType == 'convexHull':
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderConvexHullPnt%i' %i)
				row.prop(ob, 'useColliderConvexHullPnt%i' %i)
				if not getattr(ob, 'useColliderConvexHullPnt%i' %i):
					break
		elif ob.colliderShapeType == 'roundConvexHull':
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderConvexHullPnt%i' %i)
				row.prop(ob, 'useColliderConvexHullPnt%i' %i)
				if not getattr(ob, 'useColliderConvexHullPnt%i' %i):
					break
			self.layout.prop(ob, 'colliderConvexHullBorderRadius')
		elif ob.colliderShapeType == 'heightfield':
			for i in range(MAX_SHAPE_PNTS):
				row = self.layout.row()
				row.prop(ob, 'colliderHeight%i' %i)
				row.prop(ob, 'useColliderHeight%i' %i)
				if not getattr(ob, 'useColliderHeight%i' %i):
					break
			self.layout.prop(ob, 'colliderHeightfieldScale')
		self.layout.prop(ob, 'isSensor')
		self.layout.prop(ob, 'density')
		self.layout.prop(ob, 'bounciness')
		self.layout.prop(ob, 'bouncinessCombineRule')
		self.layout.label(text = 'Collision Groups')
		box = self.layout.box()
		box.label(text = 'Membership (Object is in these groups)')
		col = box.column()
		for i in range(4):
			row = col.row()
			for j in range(4):
				idx = i * 4 + j
				row.prop(ob, 'collisionGroupMembership', index = idx, text = str(idx + 1))
		box.label(text = 'Filter (Object collides with these groups)')
		col = box.column()
		for i in range(4):
			row = col.row()
			for j in range(4):
				idx = i * 4 + j
				row.prop(ob, 'collisionGroupFilter', index = idx, text = str(idx + 1))
		for i in range(MAX_ATTACH_COLLIDER_CNT):
			row = self.layout.row()
			row.prop(ob, 'attachTo%i' %i)
			row.prop(ob, 'attach%i' %i)
			if not getattr(ob, 'attach%i' %i):
				return

@bpy.utils.register_class
class JointPanel (bpy.types.Panel):
	bl_idname = 'PHYSICS_PT_Joint_Panel'
	bl_label = 'Joint'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'physics'

	def draw (self, ctx):
		ob = ctx.active_object
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

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		self.layout.prop(ob, 'charControllerExists')
		if not ob.charControllerExists:
			return
		self.layout.prop(ob, 'contactOff')

class DrawColliders (bpy.types.Operator):
	bl_idname = 'view3d.draw_colliders'
	bl_label = 'Draw Colliders'
	handle = None
	isRunning = False

	def modal (self, ctx, event):
		if not DrawColliders.isRunning:
			bpy.types.SpaceView3D.draw_handler_remove(DrawColliders.handle, 'WINDOW')
			DrawColliders.handle = None
			ctx.area.tag_redraw()
			return {'CANCELLED'}
		ctx.area.tag_redraw()
		if event.type in {'RIGHTMOUSE', 'ESC'}:
			DrawColliders.isRunning = False
			return {'PASS_THROUGH'}
		return {'PASS_THROUGH'}

	def invoke (self, ctx, event):
		if ctx.area.type == 'VIEW_3D':
			if DrawColliders.handle:
				DrawColliders.isRunning = False
				return {'FINISHED'}
			self.obs = ctx.selected_objects
			if not self.obs:
				self.report({'INFO'}, 'No objects selected.')
				return {'CANCELLED'}
			args = (self, ctx)
			DrawColliders.handle = bpy.types.SpaceView3D.draw_handler_add(OnDrawColliders, args, 'WINDOW', 'POST_VIEW')
			DrawColliders.isRunning = True
			ctx.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, 'View3D not found, cannot run operator')
			return {'CANCELLED'}

class DrawPivots (bpy.types.Operator):
	bl_idname = 'view3d.draw_pivots'
	bl_label = 'Draw Pivots'
	handle = None
	isRunning = False

	def modal (self, ctx, event):
		if not DrawPivots.isRunning:
			bpy.types.SpaceView3D.draw_handler_remove(DrawPivots.handle, 'WINDOW')
			DrawPivots.handle = None
			ctx.area.tag_redraw()
			return {'CANCELLED'}
		ctx.area.tag_redraw()
		if event.type in {'RIGHTMOUSE', 'ESC'}:
			DrawPivots.isRunning = False
			return {'PASS_THROUGH'}
		return {'PASS_THROUGH'}

	def invoke (self, ctx, event):
		if ctx.area.type == 'VIEW_3D':
			if DrawPivots.handle:
				DrawPivots.isRunning = False
				return {'FINISHED'}
			self.obs = ctx.selected_objects
			if not self.obs:
				self.report({'INFO'}, 'No objects selected.')
				return {'CANCELLED'}
			args = (self, ctx)
			DrawPivots.handle = bpy.types.SpaceView3D.draw_handler_add(OnDrawPivots, args, 'WINDOW', 'POST_VIEW')
			DrawPivots.isRunning = True
			ctx.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, 'View3D not found, cannot run operator')
			return {'CANCELLED'}

class VisualizersPanel (bpy.types.Panel):
	bl_label = 'Visualizers'
	bl_idname = 'VIEW3D_PT_visualizers'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Tool'

	def draw (self, ctx):
		layout = self.layout
		if DrawColliders.isRunning:
			layout.operator('view3d.draw_colliders', text = 'Stop Visualizing Colliders', depress = True)
		else:
			layout.operator('view3d.draw_colliders', text = 'Visualize Colliders', depress = False)
		if ColliderHandles.isRunning:
			layout.operator('view3d.collider_handles', text = 'Stop Editing Collider', depress = True)
		else:
			layout.operator('view3d.collider_handles', text = 'Edit Collider', depress = False)
		if DrawPivots.isRunning:
			layout.operator('view3d.draw_pivots', text = 'Stop Visualizing Pivots', depress = True)
		else:
			layout.operator('view3d.draw_pivots', text = 'Visualize Pivots', depress = False)

class ColliderHandles (bpy.types.Operator):
	bl_idname = 'view3d.collider_handles'
	bl_label = 'Edit Colliders'
	handle = None
	isRunning = False

	@classmethod
	def poll (cls, ctx):
		ob = ctx.object
		return ob and ob.colliderExists

	def modal (self, ctx, event):
		if not ColliderHandles.isRunning:
			bpy.types.SpaceView3D.draw_handler_remove(ColliderHandles.handle, 'WINDOW')
			ColliderHandles.handle = None
			for ob in self.obs:
				removeHandles = [child for child in ob.children if child.name.startswith(ob.name + '_Handle')]
				for removeHandle in removeHandles:
					bpy.data.objects.remove(removeHandle, do_unlink = True)
			ctx.area.tag_redraw()
			return {'CANCELLED'}
		ctx.area.tag_redraw()
		if event.type in {'RIGHTMOUSE', 'ESC'}:
			ColliderHandles.isRunning = False
			return {'PASS_THROUGH'}
		return {'PASS_THROUGH'}

	def invoke (self, ctx, event):
		if ctx.area.type == 'VIEW_3D':
			if ColliderHandles.handle:
				ColliderHandles.isRunning = False
				return {'FINISHED'}
			self.obs = ctx.selected_objects
			if not self.obs:
				self.report({'INFO'}, "No objects selected; can't run operator")
				return {'CANCELLED'}
			for ob in self.obs:
				isTriangle = ob.colliderShapeType == 'triangle' or ob.colliderShapeType == 'roundTriangle'
				isSegmentOrTriangle = ob.colliderShapeType == 'segment' or isTriangle
				pntCnt = MAX_SHAPE_PNTS
				if ob.colliderShapeType == 'segment':
					pntCnt = 2
				elif isTriangle:
					pntCnt = 3
				if ob.colliderShapeType == 'ball':
					pass
				elif ob.colliderShapeType == 'halfspace':
					pass
				elif ob.colliderShapeType == 'cuboid':
					pass
				elif ob.colliderShapeType == 'roundCuboid':
					pass
				elif ob.colliderShapeType == 'capsule':
					pass
				elif isSegmentOrTriangle or ob.colliderShapeType == 'polyline' or ob.colliderShapeType == 'trimesh' or ob.colliderShapeType == 'convexHull' or ob.colliderShapeType == 'roundConvexHull':
					for i in range(pntCnt):
						if not isSegmentOrTriangle:
							usePnt = getattr(ob, f'useCollider{str(ob.colliderShapeType)[0].upper() + str(ob.colliderShapeType)[1 :]}Pnt{i}')
						if isSegmentOrTriangle or usePnt:
							localPnt = getattr(ob, f'collider{str(ob.colliderShapeType)[0].upper() + str(ob.colliderShapeType)[1 :]}Pnt{i}')
							handle = bpy.data.objects.new(ob.name + f'_Handle{i}', None)
							handle.empty_display_type = 'CUBE'
							handle.empty_display_size = 0.1
							handle.location = (localPnt[0], localPnt[1], 0)
							handle.parent = ob
							ctx.collection.objects.link(handle)
				elif ob.colliderShapeType == 'heightField':
					pass
			self.report({'INFO'}, 'Made handles for collider(s)')
			args = (self, ctx)
			ColliderHandles.handle = bpy.types.SpaceView3D.draw_handler_add(OnDrawColliderHandles, args, 'WINDOW', 'POST_VIEW')
			ColliderHandles.isRunning = True
			ctx.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "View3D not found; can't run operator")
			return {'CANCELLED'}
		return {'FINISHED'}

REGISTER_CLASSES = (
	DrawColliders,
	DrawPivots,
	VisualizersPanel,
	ColliderHandles,
)

VIEW_3D_OPERATORS = (
	DrawColliders,
	DrawPivots,
	ColliderHandles,
)

def register ():
	for cls in REGISTER_CLASSES:
		bpy.utils.register_class(cls)
	for cls in VIEW_3D_OPERATORS:
		cls.handle = None
		cls.isRunning = False

def unregister ():
	if DrawColliders.handle:
		bpy.types.SpaceView3D.draw_handler_remove(DrawColliders.handle, 'WINDOW')
		bpy.types.SpaceView3D.draw_handler_remove(DrawPivots.handle, 'WINDOW')
	for cls in VIEW_3D_OPERATORS:
		cls.handle = None
		cls.isRunning = False
	for cls in reversed(REGISTER_CLASSES):
		bpy.utils.unregister_class(cls)

if __name__ == '__main__':
	register ()

for arg in sys.argv:
	if arg.startswith('-o='):
		bpy.data.worlds[0].htmlPath = arg.split('=')[-1]
	elif arg == '-minify':
		bpy.data.worlds[0].minifyMethod = 'terser'
	elif arg == '-js13kjam':
		bpy.data.worlds[0].minifyMethod = 'terser'
		bpy.data.worlds[0].js13kbjam = True
		bpy.data.worlds[0].invalidHtml = True
bpy.app.timers.register(Update)