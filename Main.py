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
MAX_SHAPE_POINTS = 32
MAX_ATTACH_COLLIDER_CNT = 64
MAX_POTRACE_PASSES_PER_OBJECT_MAT = 8
MAX_ATTRIBUTES_PER_OBJECT = 16
MAX_RENDER_CAMS_PER_OBJECT = 64

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
				scripts.append((txt.as_string(), getattr(ob, 'apiScriptType%s' %i)))
			else:
				scripts.append((txt.as_string(), getattr(ob, 'initScript%s' %i), getattr(ob, 'runtimeScriptType%s' %i)))
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
initCode = []
updateCode = []
apiCode = ''
svgsDatas = {}
exportType = None
vars = []
attributes = {}
pivots = {}

def ExportObject (ob):
	global svgsDatas
	if ob.hide_get() or ob in exportedObs:
		return
	obVarName = GetVarNameForObject(ob)
	_attributes = GetAttributes(ob)
	if _attributes != {}:
		for key, value in _attributes.items():
			_attributes[key] = str(value)
		attributes[obVarName] = _attributes
	RegisterPhysics (ob)
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
			renderCam = getattr(ob, 'renderCam%s' %i)
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
				AddImageDataForExe (ob, imgPath, pos, size)
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
		_attachColliderTo = getattr(ob, 'attachTo%s' %i)
		if not getattr(ob, 'attach%s' %i):
			break
		attachColliderTo.append(_attachColliderTo)
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
				collider += '], ['
				for i in range(MAX_SHAPE_POINTS):
					if not getattr(ob, 'usePolylineIdx%s' %i):
						break
					idx = getattr(ob, 'polylineIdx%s' %i)
					collider += str(idx[0]) + ', ' + str(idx[1]) + ', '
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
					if not getattr(ob, 'useTrimeshIdx%s' %i):
						break
					idx = getattr(ob, 'trimeshIdx%s' %i)
					collider += str(idx[0]) + ', ' + str(idx[1]) + ', '
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
				collider += '], ' + str(ob.convexHullBorderRadius)
			elif ob.shapeType == 'heightfield':
				collider += '['
				for i in range(MAX_SHAPE_POINTS):
					if not getattr(ob, 'useHeight%s' %i):
						break
					collider += str(getattr(ob, 'height%s' %i))
				collider += '], ' + ToVector2String(ob.heightfieldScale)
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
			else:
				for attachTo in attachColliderTo:
					collider += colliderName + GetVarNameForObject(attachTo) + ' = world.createCollider(' + colliderDescName + ', ' + GetVarNameForObject(attachTo) + 'RigidBody);\n'
					if ob.isSensor:
						collider += colliderName + GetVarNameForObject(attachTo) + '.setSensor(true);\n'
			if not ob.rigidBodyExists and ob not in attachColliderTo:
				collider += 'collidersIds["' + ob.name + '"] = ' + colliderName + ';'
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
			vars.append(rigidBodyName + ' = None')
			rigidBody = rigidBodyName + ' = sim.AddRigidBody(' + str(ob.rigidBodyEnable) + ', ' + str(RIGID_BODY_TYPES.index(ob.rigidBodyType)) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(ob.gravityScale) + ', ' + str(ob.dominance) + ', ' + str(ob.canRot) + ', ' + str(ob.linearDrag) + ', ' + str(ob.angDrag) + ', ' + str(ob.canSleep) + ', ' + str(ob.continuousCollideDetect) + ')\nrigidBodiesIds["' + obVarName + '"] = ' + rigidBodyName
			rigidBodies[ob] = rigidBody
		if ob.colliderExists:
			polylinePnts = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'usePolylinePoint%s' %i):
					break
				pnt = getattr(ob, 'polylinePoint%s' %i)
				polylinePnts.append(list(pnt))
			polylineIdxs = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'usePolylineIdx%s' %i):
					break
				idx = getattr(ob, 'polylineIdx%s' %i)
				polylineIdxs.append(list(idx))
			polylineIdxsStr = ''
			if polylineIdxs != []:
				polylineIdxsStr = str(polylineIdxs)
			trimeshPnts = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useTrimeshPoint%s' %i):
					break
				pnt = getattr(ob, 'trimeshPoint%s' %i)
				trimeshPnts.append(list(pnt))
			trimeshIdxs = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useTrimeshIdx%s' %i):
					break
				idx = getattr(ob, 'trimeshIdx%s' %i)
				trimeshIdxs.append(list(idx))
			convexHullPnts = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useConvexHullPoint%s' %i):
					break
				pnt = getattr(ob, 'convexHullPoint%s' %i)
				convexHullPnts.append(list(pnt))
			heights = []
			for i in range(MAX_SHAPE_POINTS):
				if not getattr(ob, 'useHeight%s' %i):
					break
				heights.append(getattr(ob, 'height%s' %i))
			colliderName = obVarName + 'Collider'
			if attachColliderTo == []:
				vars.append(colliderName + ' = None')
				if ob.shapeType == 'ball':
					collider = colliderName + ' = sim.AddBallCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(ob.radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'halfspace':
					collider = colliderName + ' = sim.AddHalfspaceCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'cuboid':
					collider = colliderName + ' = sim.AddCuboidCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'roundCuboid':
					collider = colliderName + ' = sim.AddRoundCuboidCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.size)) + ', ' + str(ob.cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'capsule':
					collider = colliderName + ' = sim.AddCapsuleCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(ob.capsuleHeight) + ', ' + str(ob.capsuleRadius) + ', ' + str(ob.isVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'segment':
					collider = colliderName + ' = sim.AddSegmentCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.segmentPos1)) + ', ' + str(list(ob.segmentPos2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'triangle':
					collider = colliderName + ' = sim.AddTriangleCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.trianglePos1)) + ', ' + str(list(ob.trianglePos2)) + ', ' + str(list(ob.trianglePos3)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'roundTriangle':
					collider = colliderName + ' = sim.AddRoundTriangleCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.trianglePos1)) + ', ' + str(list(ob.trianglePos2)) + ', ' + str(list(ob.trianglePos3)) + ', ' + str(ob.triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'polyline':
					collider = colliderName + ' = sim.AddPolylineCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + polylineIdxsStr
				elif ob.shapeType == 'trimesh':
					collider = colliderName + ' = sim.AddTrimeshCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs)
				elif ob.shapeType == 'convexHull':
					collider = colliderName + ' = sim.AddConvexHullCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'roundConvexHull':
					collider = colliderName + ' = sim.AddRoundConvexHullCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.convexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
				elif ob.shapeType == 'heightfield':
					collider = colliderName + ' = sim.AddRoundConvexHullCollider(' + str(ob.colliderEnable) + ', ' + posStr + ', ' + str(math.degrees(ob.rotation_euler.z)) + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ', ' + str(ob.isSensor) + ', ' + str(ob.density)
			else:
				for attachTo in attachColliderTo:
					attachToVarName = GetVarNameForObject(attachTo)
					vars.append(colliderName + attachToVarName + ' = None')
					if ob.shapeType == 'ball':
						collider = colliderName + attachToVarName + ' = sim.AddBallCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(ob.radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'halfspace':
						collider = colliderName + attachToVarName + ' = sim.AddHalfspaceCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'cuboid':
						collider = colliderName + attachToVarName + ' = sim.AddCuboidCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'roundCuboid':
						collider = colliderName + attachToVarName + ' = sim.AddRoundCuboidCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.size)) + ', ' + str(ob.cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'capsule':
						collider = colliderName + attachToVarName + ' = sim.AddCapsuleCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(ob.capsuleHeight) + ', ' + str(ob.capsuleRadius) + ', ' + str(ob.isVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'segment':
						collider = colliderName + attachToVarName + ' = sim.AddSegmentCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.segmentPos1)) + ', ' + str(list(ob.segmentPos2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'triangle':
						collider = colliderName + attachToVarName + ' = sim.AddTriangleCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.trianglePos1)) + ', ' + str(list(ob.trianglePos2)) + ', ' + str(list(ob.trianglePos3)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'roundTriangle':
						collider = colliderName + attachToVarName + ' = sim.AddRoundTriangleCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.trianglePos1)) + ', ' + str(list(ob.trianglePos2)) + ', ' + str(list(ob.trianglePos3)) + ', ' + str(ob.triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'polyline':
						collider = colliderName + attachToVarName + ' = sim.AddPolylineCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + polylineIdxsStr + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'trimesh':
						collider = colliderName + attachToVarName + ' = sim.AddTrimeshCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'convexHull':
						collider = colliderName + attachToVarName + ' = sim.AddConvexHullCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'roundConvexHull':
						collider = colliderName + attachToVarName + ' = sim.AddRoundConvexHullCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.convexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
					elif ob.shapeType == 'heightfield':
						collider = colliderName + attachToVarName + ' = sim.AddRoundConvexHullCollider(' + str(ob.colliderEnable) + ', [0, 0], 0, ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', rigidBodiesIds["' + attachToVarName + '"]'
			collider += ')'
			if not ob.rigidBodyExists and ob not in attachColliderTo:
				collider += '\ncollidersIds["' + obVarName + '"] = ' + colliderName
			colliders[ob] = collider
		if ob.jointExists:
			jointName = obVarName + 'Joint'
			vars.append(jointName + ' = None')
			if ob.jointType == 'fixed':
				joint = jointName + ' = sim.AddFixedJoint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(ob.anchorRot1) + ', ' + str(ob.anchorRot2) + ')'
			elif ob.jointType == 'spring':
				joint = jointName + ' = sim.AddSpringJoint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(ob.restLen) + ', ' + str(ob.stiffness) + ', ' + str(ob.damping) + ')'
			elif ob.jointType == 'revolute':
				joint = jointName + ' = sim.AddRevoluteJoint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ')'
			elif ob.joinType == 'prismatic':
				joint = jointName + ' = sim.AddRevoluteJoint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(list(ob.jointAxis)) + ')'
			elif ob.joinType == 'rope':
				joint = jointName + ' = sim.AddRopeJoint(rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody1) + '"], rigidBodiesIds["' + GetVarNameForObject(ob.anchorRigidBody2) + '"], ' + str(list(ob.anchorPos1)) + ', ' + str(list(ob.anchorPos2)) + ', ' + str(list(ob.jointLen)) + ')'
			joint += '\njointsIds["' + obVarName + '"] = ' + jointName
			joints[ob] = joint
	ob.rotation_mode = prevRotMode

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
	AddImageDataForExe (ob, renderPath, pos, size)
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

def AddImageDataForExe (ob, imgPath, pos, size):
	surface = GetVarNameForObject(ob)
	surfaceRect = surface + 'Rect'
	initCodeLine = surface + ' = pygame.image.load("' + imgPath + '").convert_alpha()\n' + surface + ' = pygame.transform.scale(' + surface + ', (' + str(size[0]) + ',' + str(size[1]) + '))\n'
	if ob.rotation_euler.z != 0:
		initCodeLine += surface + ' = pygame.transform.rotate(' + surface + ', ' + str(math.degrees(-ob.rotation_euler.z)) + ')\n'
	initCodeLine += 'initRots["' + surface + '"] = ' + str(math.degrees(-ob.rotation_euler.z)) + '\nsurfaces["' + surface + '"] = ' + surface + '\n' + surfaceRect + ' = ' + surface + '.get_rect().move(' + str(TryChangeToInt(pos.x)) + ', ' + str(TryChangeToInt(pos.y)) + ')\nsurfacesRects["' + surface + '"] = ' + surfaceRect
	initCode.insert(0, initCodeLine)
	vars.append(surface + ' = None')
	vars.append(surfaceRect + ' = None')

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
				AddImageDataForExe (ob, imgPath, GetImagePosition(ob), ob.scale * ob.empty_display_size)
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
		if getattr(ob, 'useInt%i' %i):
			output[getattr(ob, 'intName%s' %i)] = getattr(ob, 'intVal%s' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useFloat%i' %i):
			output[getattr(ob, 'floatName%s' %i)] = getattr(ob, 'floatVal%s' %i)
	for i in range(MAX_ATTRIBUTES_PER_OBJECT):
		if getattr(ob, 'useString%i' %i):
			output[getattr(ob, 'stringName%s' %i)] = getattr(ob, 'stringVal%s' %i)
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
	global vars, clrs, datas, joints, pivots, apiCode, initCode, pathsDatas, updateCode, exportedObs, svgsDatas, rigidBodies, colliders, attributes, charControllers
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
	initCode = []
	updateCode = []
	svgsDatas = {}
	sortedObs = sorted(bpy.data.objects, key = lambda ob : ob.location.z)
	for ob in sortedObs:
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
				script = script.replace('$name', '"' + GetVarNameForObject(ob) + '"')
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

PYTHON = '''from python import os, math, pygame, typing, PyRapier2d
from typing import List

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

# Physics Section Start
sim = PyRapier2d.Simulation()
rigidBodiesIds = {}
collidersIds = {}
jointsIds = {}
# Physics Section End
surfaces = {}
surfacesRects = {}
initRots = {}
screen = None
windowSize = None
# Pivots
# Attributes
off = pygame.math.Vector2()

def add (v, v2) -> List[float]:
	_v = [float(v[0]), float(v[1])]
	_v2 = [float(v2[0]), float(v2[1])]
	return [_v[0] + _v2[0], _v[1] + _v2[1]]

def subtract (v, v2) -> List[float]:
	_v = [float(v[0]), float(v[1])]
	_v2 = [float(v2[0]), float(v2[1])]
	return [_v[0] - _v2[0], _v[1] - _v2[1]]

def multiply (v, f) -> List[float]:
	_v = [float(v[0]), float(v[1])]
	return [_v[0] * f, _v[1] * f]

def divide (v, f) -> List[float]:
	_v = [float(v[0]), float(v[1])]
	return [_v[0] / f, _v[1] / f]

def magnitude (v) -> float:
	return math.sqrt(sqr_magnitude(v))

def sqr_magnitude (v) -> float:
	return v[0] * v[0] + v[1] * v[1]

def normalize (v) -> List[float]:
	return divide(v, magnitude(v))

def copy_surface (name, newName, pos, rot, wakeUp = True):
	surface = surfaces[name].copy()
	surfacesRects[newName] = surfacesRects[name].copy()
	surfaces[newName] = surface
	initRots[newName] = initRots[name]
	pivots[newName] = pivots[name]
	if name in rigidBodiesIds:
		rigidBodiesIds[newName] = sim.CopyRigidBody(rigidBodiesIds[name], pos, rot, wakeUp)
	else:
		surface = pygame.transform.rotate(surface, rot)
		initRots[newName] = rot
		if name in collidersIds:
			collidersIds[newName] = sim.CopyCollider(collidersIds[name], pos, rot, wakeUp)

def remove_surface (name):
	del surfaces[name]
	del surfacesRects[name]
	del initRots[name]
	del pivots[name]
	if name in rigidBodiesIds:
		del rigidBodiesIds[name]
	elif name in collidersIds:
		del collidersIds[name]

def ang_to_dir (ang) -> List[float]:
	ang = math.radians(ang)
	return [float(math.cos(ang)), float(math.sin(ang))]

def rotate (surface, rot, pivot, offset):
	rotatedSurface = pygame.transform.rotate(surface, -rot)
	rotatedOff = offset.rotate(rot)
	rect = rotatedSurface.get_rect(center = pivot - rotatedOff)
	return rotatedSurface, rect

# Vars

class Game:
	def __init__ (self, title : str = 'Game'):
		pygame.display.set_caption(title)
		self.clock = pygame.time.Clock()
		self.running = True
		self.dt = 0.0

	def run (self):
		while self.running:
			self.handle_events ()
			self.update ()
			self.render ()
			self.dt = self.clock.tick(60) / 1000

	def handle_events (self):
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				self.running = False

	def update (self):
		global off
# Physics Section Start
		sim.step ()
		for name, rigidBodyId in rigidBodiesIds.items():
			if name in surfacesRects:
				pos = sim.GetRigidBodyPosition(rigidBodyId)
				size = surfacesRects[name].size
				surfacesRects[name].update(pos[0] - size[0] / 2, pos[1] - size[1] / 2, size[0], size[1])
# Physics Section End
# Update

	def render (self):
# Background
		for name, surface in surfaces.items():
			if name in rigidBodiesIds:
				rigidBody = rigidBodiesIds[name]
				pos = sim.GetRigidBodyPosition(rigidBody)
				rot = sim.GetRigidBodyRotation(rigidBody)
				width, height = surface.get_size()
				pivot = pivots[name]
				offset = pygame.math.Vector2(pivot[0] * width, pivot[1] * height) - pygame.math.Vector2(width, height) / 2
				rotatedSurface, rect = rotate(surface, rot + initRots[name], pos, offset)
				screen.blit(rotatedSurface, (rect.left - off.x, rect.top - off.y))
			else:
				pos = surfacesRects[name].topleft
				screen.blit(surface.copy(), (pos[0] - off.x, pos[1] - off.y))
		pygame.display.flip()

pygame.init()
screen = pygame.display.set_mode(flags = pygame.FULLSCREEN)
windowSize = pygame.display.get_window_size()
# API
# Init
game = Game()
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
				_attachTo = getattr(key, 'attachTo%s' %i)
				if not getattr(key, 'attach%s' %i):
					break
				attachTo.append(_attachTo)
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
	physicsInitCode = ['sim.SetLengthUnit (' + str(world.unitLen) + ')\nsim.SetGravity (' + str(gravity[0]) + ', ' + str(gravity[1]) + ')']
	for rigidBody in rigidBodies.values():
		physicsInitCode.append(rigidBody)
	for collider in colliders.values():
		physicsInitCode.append(collider)
	for joint in joints.values():
		physicsInitCode.append(joint)
	initCode = physicsInitCode + initCode
	python = python.replace('# Init', '\n'.join(initCode))
	for i, updateScript in enumerate(updateCode):
		_updateScript = ''
		for line in updateScript.split('\n'):
			_updateScript += '		' + line + '\n'
		updateCode[i] = _updateScript
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
	# if not exePath.endswith('.exe'):
	# 	exePath += '.exe'
	cmd = 'python3 CodonBuild.py ' + pythonPath + ' ' + exePath
	print(cmd)
	os.system(cmd)
	# subprocess.check_call(cmd.split())
	zipPath = os.path.expanduser(world.zipPath)
	zipPath = zipPath.replace('\\', '/')
	if not zipPath.endswith('.zip'):
		zipPath += '.zip'
	print('Saving:', zipPath)
	with ZipFile(zipPath, 'w') as zip:
		zip.write(exePath, GetFileName(exePath))
		for imgPath in imgsPaths:
			zip.write(imgPath, GetFileName(imgPath))
		# zip.extractall(zipPath.replace('.zip', ''))
	zip = open(zipPath, 'rb').read()
	buildInfo['zip'] = zipPath
	buildInfo['zip-size'] = len(zip)
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
	for ob in self.objects:
		if not ob or not ob.colliderExists:
			continue
		matrix = ob.matrix_world
		pos = matrix.to_translation()
		rot = matrix.to_euler()
		rot.x = 0
		rot.y = 0
		matrix = Matrix.LocRotScale(pos, rot, Vector((1, 1, 1)))
		if ob.shapeType == 'ball':
			radius = ob.radius
			segments = 32
			verts = []
			for i in range(segments + 1):
				ang = (i / segments) * 2 * math.pi
				verts.append(matrix @ Vector((radius * math.cos(ang), radius * math.sin(ang), 0)))
			batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : verts})
			batch.draw(shader)
		elif ob.shapeType == 'halfspace':
			normal = Vector(list(ob.normal) + [0]).normalized()
			dir = Vector(list(Rotate90(normal)) + [0])
			pnt = matrix @ (-dir * 99999)
			pnt2 = matrix @ (dir * 99999)
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
		elif ob.shapeType == 'cuboid':
			_min, _max = -Vector((ob.size[0], ob.size[1], 0)) / 2, Vector((ob.size[0], ob.size[1], 0)) / 2
			verts = [matrix @ v for v in [_min, Vector((_min.x, _max.y, 0)), _max, Vector((_max.x, _min.y, 0))]]
			batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : verts})
			batch.draw(shader)
		elif ob.shapeType == 'roundCuboid':
			halfWidth = ob.size[0] / 2
			halfHeight = ob.size[1] / 2
			radius = ob.cuboidBorderRadius
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
		elif ob.shapeType == 'capsule':
			radius = ob.capsuleRadius
			height = ob.capsuleHeight / 2
			localPnt = Vector((-radius, -height / 2))
			if not ob.isVertical:
				localPnt = Rotate90(localPnt)
			localPnt = Vector(list(localPnt) + [0])
			pnt = matrix @ localPnt
			localPnt2 = Vector((-radius, height / 2))
			if not ob.isVertical:
				localPnt2 = Rotate90(localPnt2)
			localPnt2 = Vector(list(localPnt2) + [0])
			pnt2 = matrix @ localPnt2
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
			localPnt = Vector((radius, -height / 2))
			if not ob.isVertical:
				localPnt = Rotate90(localPnt)
			localPnt = Vector(list(localPnt) + [0])
			pnt = matrix @ localPnt
			localPnt2 = Vector((radius, height / 2))
			if not ob.isVertical:
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
					if not ob.isVertical:
						localVert = Rotate90(localVert)
					localVert = Vector((list(localVert) + [0]))
					verts.append(matrix @ localVert)
				batch = batch_for_shader(shader, 'LINE_STRIP', {'pos' : verts})
				batch.draw(shader)
		elif ob.shapeType == 'segment':
			pnt = matrix @ Vector(list(ob.segmentPos1))
			pnt2 = matrix @ Vector(list(ob.segmentPos2))
			batch = batch_for_shader(shader, 'LINES', {'pos' : [pnt, pnt2]})
			batch.draw(shader)
		elif ob.shapeType == 'triangle':
			pnt = matrix @ Vector(list(ob.trianglePos1) + [0])
			pnt2 = matrix @ Vector(list(ob.trianglePos2) + [0])
			pnt3 = matrix @ Vector(list(ob.trianglePos3) + [0])
			batch = batch_for_shader(shader, 'LINE_LOOP', {'pos' : [pnt, pnt2, pnt3]})
			batch.draw(shader)
		# elif ob.shapeType == 'roundTriangle':
		# 	try:
		# 		pnt = Vector(list(ob.trianglePos1) + [0])
		# 		pnt2 = Vector(list(ob.trianglePos2) + [0])
		# 		pnt3 = Vector(list(ob.trianglePos3) + [0])
		# 		radius = ob.triangleBorderRadius
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
		# 	batch = batch_for_shader(shader, 'LINE_LOOP', {"pos" : verts})
		# 	batch.draw(shader)
	gpu.state.blend_set('NONE')

def OnDrawPivots (self, ctx):
	gpu.state.blend_set('ALPHA')
	gpu.state.line_width_set(2)
	shader = gpu.shader.from_builtin('UNIFORM_COLOR')
	shader.bind()
	shader.uniform_float('color', VISUALIZER_CLR)
	for ob in self.objects:
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

canUpdateProps = True
def OnUpdateProperty (self, ctx, propName):
	global canUpdateProps
	if not canUpdateProps:
		return
	canUpdateProps = False
	for ob in ctx.selected_objects:
		if ob != self:
			setattr(ob, propName, getattr(self, propName))

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
RIGID_BODY_TYPE_ITEMS = [('dynamic', 'dynamic', ''), ('fixed', 'fixed', ''), ('kinematicPositionBased', 'kinematic-position-based', ''), ('kinematicVelocityBased', 'kinematic-velocity-based', '')]
RIGID_BODY_TYPES = ['dynamic', 'fixed', 'kinematicVelocityBased', 'kinematic-velocity-based']
JOINT_TYPE_ITEMS = [('fixed', 'fixed', ''), ('spring', 'spring', ''), ('revolute', 'revolute', ''), ('prismatic', 'prismatic', ''), ('rope', 'rope', '')]
SCRIPT_TYPE_ITEMS = [('html', 'html', ''), ('exe', 'exe', ''), ('unity', 'unity', '')]

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
bpy.types.Object.roundPosAndSize = bpy.props.BoolProperty(name = 'Round position and size', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'roundPosAndSize'))
bpy.types.Object.pivot = bpy.props.FloatVectorProperty(name = 'Pivot point', size = 2, default = [50, 50], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'pivot'))
bpy.types.Object.useStroke = bpy.props.BoolProperty(name = 'Use stroke', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useStroke'))
bpy.types.Object.strokeWidth = bpy.props.FloatProperty(name = 'Stroke width', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'strokeWidth'))
bpy.types.Object.strokeClr = bpy.props.FloatVectorProperty(name = 'Stroke color', subtype = 'COLOR', size = 4, min = 0, max = 1, default = [0, 0, 0, 1])
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
bpy.types.Object.shapeType = bpy.props.EnumProperty(name = 'Shape type', items = SHAPE_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'shapeType'))
bpy.types.Object.radius = bpy.props.FloatProperty(name = 'Radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'radius'))
bpy.types.Object.normal = bpy.props.FloatVectorProperty(name = 'Normal', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'normal'))
bpy.types.Object.size = bpy.props.FloatVectorProperty(name = 'Size', size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'size'))
bpy.types.Object.cuboidBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'cuboidBorderRadius'))
bpy.types.Object.capsuleHeight = bpy.props.FloatProperty(name = 'Height', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'capsuleHeight'))
bpy.types.Object.capsuleRadius = bpy.props.FloatProperty(name = 'Radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'capsuleRadius'))
bpy.types.Object.isVertical = bpy.props.BoolProperty(name = 'Is vertical', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'isVertical'))
bpy.types.Object.segmentPos1 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'segmentPos1'))
bpy.types.Object.segmentPos2 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'segmentPos2'))
bpy.types.Object.trianglePos1 = bpy.props.FloatVectorProperty(name = 'Position 1', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'trianglePos1'))
bpy.types.Object.trianglePos2 = bpy.props.FloatVectorProperty(name = 'Position 2', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'trianglePos2'))
bpy.types.Object.trianglePos3 = bpy.props.FloatVectorProperty(name = 'Position 3', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'trianglePos3'))
bpy.types.Object.triangleBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'triangleBorderRadius'))
bpy.types.Object.convexHullBorderRadius = bpy.props.FloatProperty(name = 'Border radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'convexHullBorderRadius'))
bpy.types.Object.heightfieldScale = bpy.props.FloatVectorProperty(name = 'Scale', size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'heightfieldScale'))
bpy.types.Object.isSensor = bpy.props.BoolProperty(name = 'Is sensor', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'isSensor'))
bpy.types.Object.density = bpy.props.FloatProperty(name = 'Density', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'density'))
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

for i in range(MAX_SCRIPTS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'apiScript%s' %i,
		bpy.props.PointerProperty(name = 'API script%s' %i, type = bpy.types.Text, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'API script%s' %i))
	)
	setattr(
		bpy.types.Object,
		'apiScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'apiScript%sDisable' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%s' %i,
		bpy.props.PointerProperty(name = 'Runtime script%s' %i, type = bpy.types.Text, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScript%s' %i))
	)
	setattr(
		bpy.types.Object,
		'apiScriptType%s' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'apiScriptType%s' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScript%sDisable' %i))
	)
	setattr(
		bpy.types.Object,
		'initScript%s' %i,
		bpy.props.BoolProperty(name = 'Is init', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'initScript%s' %i))
	)
	setattr(
		bpy.types.Object,
		'runtimeScriptType%s' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'runtimeScriptType%s' %i))
	)
for i in range(MAX_SHAPE_POINTS):
	setattr(
		bpy.types.Object,
		'polylinePoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'polylinePoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'usePolylinePoint%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'usePolylinePoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'polylineIdx%s' %i,
		bpy.props.IntVectorProperty(name = 'Index%s' %i, size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'polylineIdx%s' %i))
	)
	setattr(
		bpy.types.Object,
		'usePolylineIdx%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'usePolylineIdx%s' %i))
	)
	setattr(
		bpy.types.Object,
		'trimeshPoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'trimeshPoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useTrimeshPoint%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useTrimeshPoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'trimeshIdx%s' %i,
		bpy.props.IntVectorProperty(name = 'Index%s' %i, size = 2, min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'trimeshIdx%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useTrimeshIdx%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useTrimeshIdx%s' %i))
	)
	setattr(
		bpy.types.Object,
		'convexHullPoint%s' %i,
		bpy.props.FloatVectorProperty(name = 'Point%s' %i, size = 2, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'convexHullPoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useConvexHullPoint%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useConvexHullPoint%s' %i))
	)
	setattr(
		bpy.types.Object,
		'height%s' %i,
		bpy.props.FloatProperty(name = 'Point%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'height%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useHeight%s' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useHeight%s' %i))
	)
for i in range(MAX_ATTACH_COLLIDER_CNT):
	setattr(
		bpy.types.Object,
		'attachTo%s' %i,
		bpy.props.PointerProperty(name = 'Rigid body%s' %i, type = bpy.types.Object, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'attachTo%s' %i))
	)
	setattr(
		bpy.types.Object,
		'attach%s' %i,
		bpy.props.BoolProperty(name = 'Attach to rigid body%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'attach%s' %i))
	)
for i in range(MAX_POTRACE_PASSES_PER_OBJECT_MAT):
	setattr(
		bpy.types.Object,
		'minVisibleClrValue%i' %i,
		bpy.props.FloatProperty(name = 'Min visible color value', min = 0, max = 1, default = .01, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'minVisibleClrValue%s' %i))
	)
	setattr(
		bpy.types.Object,
		'tintOutput%i' %i,
		bpy.props.FloatVectorProperty(name = 'Tint output', subtype = 'COLOR', size = 4, min = 0, default = [1, 1, 1, 1], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'tintOutput%s' %i))
	)
	if i > 0:
		setattr(
			bpy.types.Object,
			'useMinVisibleClrValue%i' %i,
			bpy.props.BoolProperty(name = 'Use', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useMinVisibleClrValue%s' %i))
		)
for i in range(MAX_ATTRIBUTES_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'intName%i' %i,
		bpy.props.StringProperty(name = 'Int name%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intName%s' %i))
	)
	setattr(
		bpy.types.Object,
		'intVal%i' %i,
		bpy.props.IntProperty(name = 'Int value%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'intVal%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useInt%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useInt%s' %i))
	)
	setattr(
		bpy.types.Object,
		'floatName%i' %i,
		bpy.props.StringProperty(name = 'Float name%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatName%s' %i))
	)
	setattr(
		bpy.types.Object,
		'floatVal%i' %i,
		bpy.props.FloatProperty(name = 'Float value%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'floatVal%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useFloat%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useFloat%s' %i))
	)
	setattr(
		bpy.types.Object,
		'stringName%i' %i,
		bpy.props.StringProperty(name = 'String name%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringName%s' %i))
	)
	setattr(
		bpy.types.Object,
		'stringVal%i' %i,
		bpy.props.StringProperty(name = 'String value%s' %i, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'stringVal%s' %i))
	)
	setattr(
		bpy.types.Object,
		'useString%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useString%s' %i))
	)
for i in range(MAX_RENDER_CAMS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'renderCam%s' %i,
		bpy.props.PointerProperty(name = 'Render camera%s' %i, type = bpy.types.Camera, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'renderCam%s' %i))
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

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
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
			for i in range(MAX_POTRACE_PASSES_PER_OBJECT_MAT):
				row = self.layout.row()
				row.prop(ob, 'minVisibleClrValue%s' %i)
				row.prop(ob, 'tintOutput%s' %i)
				if i > 0:
					row.prop(ob, 'useMinVisibleClrValue%s' %i)
					if not getattr(ob, 'useMinVisibleClrValue%s' %i):
						break
			foundUnassignedCam = False
			for i in range(MAX_RENDER_CAMS_PER_OBJECT):
				hasProp = getattr(ob, 'renderCam%s' %i)
				if hasProp or not foundUnassignedCam:
					self.layout.prop(ob, 'renderCam%s' %i)
				if not foundUnassignedCam:
					foundUnassignedCam = not hasProp
		self.layout.label(text = 'Scripts')
		foundUnassignedScript = False
		for i in range(MAX_SCRIPTS_PER_OBJECT):
			hasProp = getattr(ob, 'apiScript%s' %i)
			if hasProp or not foundUnassignedScript:
				row = self.layout.row()
				row.prop(ob, 'apiScript%s' %i)
				row.prop(ob, 'apiScriptType%s' %i)
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
				row.prop(ob, 'runtimeScriptType%s' %i)
				row.prop(ob, 'runtimeScript%sDisable' %i)
			if not foundUnassignedScript:
				foundUnassignedScript = not hasProp

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
		for i in range(MAX_ATTRIBUTES_PER_OBJECT):
			row = self.layout.row()
			row.prop(ob, 'intName%s' %i)
			row.prop(ob, 'intVal%s' %i)
			row.prop(ob, 'useInt%s' %i)
			if not getattr(ob, 'useInt%s' %i):
				break
		for i in range(MAX_ATTRIBUTES_PER_OBJECT):
			row = self.layout.row()
			row.prop(ob, 'floatName%s' %i)
			row.prop(ob, 'floatVal%s' %i)
			row.prop(ob, 'useFloat%s' %i)
			if not getattr(ob, 'useFloat%s' %i):
				break
		for i in range(MAX_ATTRIBUTES_PER_OBJECT):
			row = self.layout.row()
			row.prop(ob, 'stringName%s' %i)
			row.prop(ob, 'stringVal%s' %i)
			row.prop(ob, 'useString%s' %i)
			if not getattr(ob, 'useString%s' %i):
				break

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
			self.layout.prop(ob, 'isVertical')
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
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'polylineIdx%s' %i)
				row.prop(ob, 'usePolylineIdx%s' %i)
				if not getattr(ob, 'usePolylineIdx%s' %i):
					break
		elif ob.shapeType == 'trimesh':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'trimeshPoint%s' %i)
				row.prop(ob, 'useTrimeshPoint%s' %i)
				if not getattr(ob, 'useTrimeshPoint%s' %i):
					break
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'trimeshIdx%s' %i)
				row.prop(ob, 'useTrimeshIdx%s' %i)
				if not getattr(ob, 'useTrimeshIdx%s' %i):
					break
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
				row.prop(ob, 'convexHullPoint%s' %i)
				row.prop(ob, 'useConvexHullPoint%s' %i)
				if not getattr(ob, 'useConvexHullPoint%s' %i):
					break
			self.layout.prop(ob, 'convexHullBorderRadius')
		elif ob.shapeType == 'heightfield':
			for i in range(MAX_SHAPE_POINTS):
				row = self.layout.row()
				row.prop(ob, 'height%s' %i)
				row.prop(ob, 'useHeight%s' %i)
				if not getattr(ob, 'useHeight%s' %i):
					break
			self.layout.prop(ob, 'heightfieldScale')
		self.layout.prop(ob, 'isSensor')
		self.layout.prop(ob, 'density')
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
		if not ob.rigidBodyExists:
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
			self.objects = ctx.selected_objects
			if not self.objects:
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
			self.objects = ctx.selected_objects
			if not self.objects:
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
		if DrawPivots.isRunning:
			layout.operator('view3d.draw_pivots', text = 'Stop Visualizing Pivots', depress = True)
		else:
			layout.operator('view3d.draw_pivots', text = 'Visualize Pivots', depress = False)

classes = (
	DrawColliders,
	DrawPivots,
	VisualizersPanel
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
		bpy.data.worlds[0].htmlPath = arg.split('=')[-1]
	elif arg == '-minify':
		bpy.data.worlds[0].minifyMethod = 'terser'
	elif arg == '-js13kjam':
		bpy.data.worlds[0].minifyMethod = 'terser'
		bpy.data.worlds[0].js13kbjam = True
		bpy.data.worlds[0].invalidHtml = True
bpy.app.timers.register(Update)