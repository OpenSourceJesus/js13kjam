import os, re, io, ast, sys, json, math, time, string, atexit, struct, shutil, contextlib, threading, subprocess, webbrowser
import ctypes, ctypes.util
from zipfile import *
_thisDir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisDir)
Util_SCRIPTS_PATH = os.path.join(_thisDir, 'Util')
sys.path.append(Util_SCRIPTS_PATH)
PY2GB_PATH = os.path.join(_thisDir, 'Py2Gb')
if os.path.isdir(PY2GB_PATH) and PY2GB_PATH not in sys.path:
	sys.path.insert(0, PY2GB_PATH)
from MathUtil import *
from SystemUtil import *
try:
	from py2gba.blender_export import export_gba_py_assembly as _py2gb_export_gba_py_assembly
	from py2gba.blender_export import py2gba_asm as _py2gb_py2gb_asm
except Exception:
	_py2gb_export_gba_py_assembly = None
	_py2gb_py2gb_asm = None

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
MAX_RENDER_CAMS_PER_OBJECT = 128
MAX_PARTICLE_SYSTEM_BURSTS = 64

def GetScripts (ob):
	scripts = []
	for i in range(MAX_SCRIPTS_PER_OBJECT):
		if not getattr(ob, 'scriptDisable%i' %i):
			txt = getattr(ob, 'script%i' %i)
			if txt:
				scripts.append((txt.as_string(), getattr(ob, 'initScript%i' %i), getattr(ob, 'scriptType%i' %i), txt))
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

def ToByteString (n, delimeters = '\\`', escapeQuotes : bool = False):
	n = round(n)
	if n < 32:
		n = 32
	byteStr = chr(n)
	if byteStr in delimeters:
		byteStr = chr(n + 1)
	elif escapeQuotes and byteStr in '"' + "'":
		byteStr = '\\' + byteStr
	return byteStr

def ToSvgNumberString (n):
	return str(TryChangeToInt(n))

def GetSvgPathFromValues (pathVals, cyclic):
	if len(pathVals) < 2:
		return ''
	output = 'M ' + ToSvgNumberString(pathVals[0]) + ',' + ToSvgNumberString(pathVals[1]) + ' '
	i = 2
	while i < len(pathVals):
		if (i - 2) % 6 == 0 and i + 6 <= len(pathVals):
			output += 'C '
			output += ToSvgNumberString(pathVals[i]) + ',' + ToSvgNumberString(pathVals[i + 1]) + ' '
			output += ToSvgNumberString(pathVals[i + 2]) + ',' + ToSvgNumberString(pathVals[i + 3]) + ' '
			output += ToSvgNumberString(pathVals[i + 4]) + ',' + ToSvgNumberString(pathVals[i + 5]) + ' '
			i += 6
		elif i + 2 <= len(pathVals):
			output += 'L ' + ToSvgNumberString(pathVals[i]) + ',' + ToSvgNumberString(pathVals[i + 1]) + ' '
			i += 2
		else:
			break
	if cyclic:
		output += 'Z'
	return output

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
RAW_PATH_DATA_MODE_PREFIX = chr(2)
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
svgsDatas = {}
exportType = None
vars = []
attributes = {}
pivots = {}
ui = []
uiMethods = []
globals = []
renderCode = []
zOrders = {}
prefabs = {}
templateScripts = {}
prefabTemplateDatas = []
prefabPathsDatas = []
templateOnlyObs = set ()
instancedCollectionObs = set ()
collectionInstanceOffsetStack = []
collectionInstanceTransformStack = []
collectionInstanceCopyCounts = {}

def GetObjectsInCollectionRecursive (coll):
	obSet = set()
	for ob in coll.all_objects:
		obSet.add(ob)
	return obSet

def GetCollectionInstanceOffset ():
	instancePos, _ = GetCollectionInstanceTransform()
	return instancePos

def Rotate2DByAngle (v, angle):
	return Vector((
		v.x * math.cos(angle) - v.y * math.sin(angle),
		v.x * math.sin(angle) + v.y * math.cos(angle),
		0
	))

def GetCollectionInstanceTransform ():
	if collectionInstanceTransformStack == []:
		return (Vector((0, 0, 0)), 0)
	return collectionInstanceTransformStack[-1]

def GetCollectionInstanceCopyName (templateOb, instanceOb):
	global collectionInstanceCopyCounts
	key = instanceOb.name + '|' + templateOb.name
	count = collectionInstanceCopyCounts.get(key, 0)
	collectionInstanceCopyCounts[key] = count + 1
	copySuffix = '' if count == 0 else '_' + str(count)
	return templateOb.name + '@' + instanceOb.name + copySuffix

def AddCollectionInstanceCopy (templateOb, instanceOb):
	pos = GetObjectPosition(templateOb)
	instanceName = GetCollectionInstanceCopyName(templateOb, instanceOb)
	prevRotMode = templateOb.rotation_mode
	templateOb.rotation_mode = 'XYZ'
	rot = TryChangeToInt(math.degrees(templateOb.rotation_euler.z))
	templateOb.rotation_mode = prevRotMode
	(prefabTemplateDatas if templateOb in templateOnlyObs else datas).append([
		templateOb.name,
		instanceName,
		TryChangeToInt(pos[0]),
		TryChangeToInt(pos[1]),
		rot,
		GetAttributes(templateOb)
	])
	return instanceName

def GatherPrefabDefinition (coll):
	obSet = GetObjectsInCollectionRecursive(coll)
	obSet = { ob for ob in obSet if ob.exportOb and ob in exportedObs }
	if not obSet:
		return None
	exportedTransforms = {}
	def register_exported_transform (name, pos, rot = 0):
		if not isinstance(name, str):
			return
		if pos is None or len(pos) < 2:
			return
		exportedTransforms[name] = (
			TryChangeToInt(pos[0]),
			TryChangeToInt(pos[1]),
			TryChangeToInt(rot)
		)
	def parse_exported_entry (entry):
		if not isinstance(entry, list):
			return
		l = len(entry)
		if l > 10 and isinstance(entry[7], str):
			frames = entry[0]
			if isinstance(frames, list) and len(frames) > 0 and isinstance(frames[0], list) and len(frames[0]) >= 2:
				register_exported_transform(entry[7], frames[0], 0)
			return
		if l >= 4 and isinstance(entry[0], str) and isinstance(entry[3], list):
			register_exported_transform(entry[0], [entry[1], entry[2]], entry[5] if l > 5 else 0)
			return
		if l > 5 and isinstance(entry[1], str) and not isinstance(entry[3], list):
			register_exported_transform(entry[1], [entry[2], entry[3]], entry[4])
			return
		if l > 6 and isinstance(entry[0], str):
			register_exported_transform(entry[0], [entry[1], entry[2]], 0)
			return
		if l >= 4 and isinstance(entry[0], str) and isinstance(entry[1], (int, float)) and isinstance(entry[2], (int, float)):
			register_exported_transform(entry[0], [entry[1], entry[2]], entry[3] if isinstance(entry[3], (int, float)) else 0)
	for entry in prefabTemplateDatas:
		parse_exported_entry(entry)
	for entry in datas:
		parse_exported_entry(entry)
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	off = Vector(world.exportOff)
	def worldPos (ob):
		if ob.name in exportedTransforms:
			return exportedTransforms[ob.name][:2]
		wpos = ob.matrix_world.to_translation()
		x = wpos.x * SCALE + off.x
		y = -wpos.y * SCALE + off.y
		return (TryChangeToInt(x), TryChangeToInt(y))
	def worldRot (ob):
		if ob.name in exportedTransforms:
			return exportedTransforms[ob.name][2]
		r = TryChangeToInt(-math.degrees(ob.matrix_world.to_euler('XYZ').z))
		return r
	roots = [ ob for ob in obSet if ob.parent not in obSet or ob.parent is None ]
	nodes = {}
	for ob in obSet:
		children = [ c for c in ob.children if c in obSet ]
		if ob.parent in obSet and ob.parent is not None:
			parent = ob.parent
			px, py = worldPos(parent)
			ox, oy = worldPos(ob)
			prot = worldRot(parent)
			orot = worldRot(ob)
			rad = math.radians(-prot)
			dx, dy = ox - px, oy - py
			localX = TryChangeToInt(dx * math.cos(rad) - dy * math.sin(rad))
			localY = TryChangeToInt(dx * math.sin(rad) + dy * math.cos(rad))
			localPos = [ localX, localY ]
			localRot = TryChangeToInt(orot - prot)
		else:
			localPos = [ 0, 0 ]
			localRot = 0
		nodes[ob.name] = { 'children': [ c.name for c in children ], 'localPos': localPos, 'localRot': localRot }
	return { 'roots': [ ob.name for ob in roots ], 'nodes': nodes }

def GatherPrefabs ():
	global prefabs
	prefabs = {}
	for coll in bpy.data.collections:
		if coll.exportPrefab:
			defn = GatherPrefabDefinition(coll)
			if defn:
				prefabs[coll.name] = defn

def GetInstancedObjects (scene):
	sceneObs = set(scene.collection.all_objects)
	return sceneObs

def GetInstancedCollectionTemplateObjects (scene):
	sceneObs = set(scene.collection.all_objects)
	pendingCollections = []
	for ob in sceneObs:
		if ob.exportOb and getattr(ob, 'instance_type', None) == 'COLLECTION' and getattr(ob, 'instance_collection', None):
			pendingCollections.append(ob.instance_collection)
	visitedCollections = set()
	while pendingCollections:
		coll = pendingCollections.pop()
		if coll in visitedCollections:
			continue
		visitedCollections.add(coll)
		for ob in coll.all_objects:
			if ob not in sceneObs:
				sceneObs.add(ob)
			if ob.exportOb and getattr(ob, 'instance_type', None) == 'COLLECTION' and getattr(ob, 'instance_collection', None):
				pendingCollections.append(ob.instance_collection)
	templateObs = set()
	for coll in visitedCollections:
		for ob in coll.all_objects:
			templateObs.add(ob)
	return templateObs

def ExportObject (ob):
	global svgsDatas
	if not ob.exportOb or ob in exportedObs:
		return
	obVarName = GetVarNameForObject(ob)
	_attributes = GetAttributes(ob)
	if _attributes != {}:
		for key, value in _attributes.items():
			_attributes[key] = str(value).replace("'", '"')
		attributes[obVarName] = _attributes
	RegisterPhysics (ob)
	RegisterParticleSystem (ob)
	RegisterUI (ob)
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
		(prefabTemplateDatas if ob in templateOnlyObs else datas).append(data)
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
				pathDataVals = []
				minPathVector = Vector((float('inf'), float('inf')))
				maxPathVector = Vector((-float('inf'), -float('inf')))
				for vector in vectors:
					if len(vector) == 1:
						continue
					components = vector.split(',')
					x = float(components[0])
					y = float(components[1])
					vector = newOb.matrix_world @ Vector((x, y, 0))
					x = vector.x
					y = vector.y
					minPathVector = GetMinComponents(minPathVector, vector, True)
					maxPathVector = GetMaxComponents(maxPathVector, vector, True)
					pathDataVals.append(x)
					pathDataVals.append(y)
				_off = -minPathVector + Vector((32, 32))
				for i, pathValue in enumerate(pathDataVals):
					if i % 2 == 1:
						pathDataVals[i] = maxPathVector[1] - pathValue + 32
					else:
						pathDataVals[i] = pathValue + _off[0]
				strokeWidth = 0
				if ob.useStroke:
					strokeWidth = ob.strokeWidth
				jiggleDist = ob.jiggleDist * int(ob.useJiggle)
				x = _min.x - strokeWidth / 2 - jiggleDist
				y = -_max.y + strokeWidth / 2 + jiggleDist
				if ob.parent and ob.parent.type == 'EMPTY' and ob.parent.empty_display_type != 'IMAGE':
					parentPos = Vector(GetObjectPosition(ob.parent))
					x -= parentPos.x
					y -= parentPos.y
				size = _max - _min
				size += Vector((1, 1)) * (strokeWidth + jiggleDist * 2)
				if ob.roundPosAndSize:
					x = int(round(x))
					y = int(round(y))
					size = Vector(Round(size))
				if not ob.roundAndCompressPathData:
					pathDataStr = RAW_PATH_DATA_MODE_PREFIX + GetSvgPathFromValues(pathDataVals, spline.use_cyclic_u)
				else:
					for i, pathValue in enumerate(pathDataVals):
						pathDataVals[i] = ToByteString(pathValue)
					pathDataStr = ''.join(pathDataVals)
				if frame == 0:
					if HandleCopyObject(newOb, [x, y]):
						break
					posFrames.insert(0, [TryChangeToInt(x), TryChangeToInt(y)])
					data.append(posFrames)
					data.append(ob.posPingPong)
					data.append(TryChangeToInt(size.x))
					data.append(TryChangeToInt(size.y))
					data.append(GetColor(ob.color))
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
					if not ob.roundAndCompressPathData:
						pathDataFrames.append(pathDataStr)
					else:
						pathDataFrames.append(GetPathDelta(prevPathData, pathDataStr))
				prevPathData = pathDataStr
			(prefabTemplateDatas if ob in templateOnlyObs else datas).append(data)
			(prefabPathsDatas if ob in templateOnlyObs else pathsDatas).append(chr(1).join(pathDataFrames))
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
							prevMatClrs[mat2] = mat2.color
							mat2.color = DEFAULT_CLR
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
					matClr = mat.color
					prevObsClrs[ob2] = list(matClr)
					mat.color = DEFAULT_CLR
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
			materialClr = ob.active_material.color
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
				ob2.active_material.color = prevObsClrs[ob2]
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
			collectionInstanceRot = None
			if getattr(ob, 'instance_type', None) == 'COLLECTION' and getattr(ob, 'instance_collection', None):
				prevRotMode = ob.rotation_mode
				ob.rotation_mode = 'XYZ'
				collectionInstanceRot = TryChangeToInt(math.degrees(-ob.rotation_euler.z))
				collectionInstanceRotRad = ob.rotation_euler.z
				ob.rotation_mode = prevRotMode
				instancedSet = { c for c in GetObjectsInCollectionRecursive(ob.instance_collection) if c.exportOb }
				rootChildren = [ c for c in instancedSet if c.parent not in instancedSet or c.parent is None ]
				prevInstancePos, prevInstanceRot = GetCollectionInstanceTransform()
				localInstancePos = Vector((ob.location.x, ob.location.y, 0))
				instancePos = prevInstancePos + Rotate2DByAngle(localInstancePos, prevInstanceRot)
				collectionInstanceOffsetStack.append(instancePos)
				collectionInstanceTransformStack.append((instancePos, prevInstanceRot + collectionInstanceRotRad))
				for child in rootChildren:
					if child in exportedObs:
						childrenNames.append(AddCollectionInstanceCopy(child, ob))
					else:
						ExportObject (child)
						childrenNames.append(child.name)
				collectionInstanceOffsetStack.pop()
				collectionInstanceTransformStack.pop()
			else:
				for child in ob.children:
					ExportObject (child)
					childrenNames.append(child.name)
			if collectionInstanceRot is None:
				(prefabTemplateDatas if ob in templateOnlyObs else datas).append([ob.name, TryChangeToInt(ob.location.x), TryChangeToInt(-ob.location.y), childrenNames, GetAttributes(ob)])
			else:
				(prefabTemplateDatas if ob in templateOnlyObs else datas).append([ob.name, TryChangeToInt(ob.location.x), TryChangeToInt(-ob.location.y), childrenNames, GetAttributes(ob), collectionInstanceRot])
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
	instanceOffset, instanceRot = GetCollectionInstanceTransform()
	localPhysicsPos = Vector((ob.location.x, ob.location.y, 0))
	worldPhysicsPos = instanceOffset + Rotate2DByAngle(localPhysicsPos, instanceRot)
	physicsX = worldPhysicsPos.x
	physicsY = worldPhysicsPos.y
	objectRotZ = ob.rotation_euler.z - instanceRot
	if exportType == 'html':
		if ob.rigidBodyExists:
			rigidBody = 'var ' + rigidBodyDescName + ' = RAPIER.RigidBodyDesc.' + ob.rigidBodyType + '()'
			if physicsX != 0 or physicsY != 0:
				rigidBody += '.setTranslation(' + str(physicsX) + ', ' + str(-physicsY) + ')'
			if objectRotZ != 0:
				rigidBody += '.setRotation(' + str(objectRotZ) + ')'
			if not ob.canRot:
				rigidBody += '.lockRotations();\n'
			rigidBody += ';\n'
			if not ob.rigidBodyEnable:
				rigidBody += rigidBodyDescName + '.enabled = false;\n'
			if ob.dominance != 0:
				rigidBody += rigidBodyDescName + '.setDominanceGroup(' + str(ob.dominance) + ');\n'
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
			colliderPosX = physicsX + ob.colliderPosOff[0]
			colliderPosY = -physicsY - ob.colliderPosOff[1]
			colliderRot = objectRotZ + ob.colliderRotOff
			if attachColliderTo != []:
				colliderPosX = ob.colliderPosOff[0]
				colliderPosY = -ob.colliderPosOff[1]
				colliderRot = ob.colliderRotOff
			if colliderPosX != 0 or colliderPosY != 0:
				collider += '.setTranslation(' + str(colliderPosX) + ', ' + str(colliderPosY) + ')'
			if colliderRot != 0:
				collider += '.setRotation(' + str(colliderRot) + ')'
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
				collider += 'colliderOffsetsIds["' + ob.name + '"] = [' + str(ob.colliderPosOff[0]) + ', ' + str(-ob.colliderPosOff[1]) + '];'
			else:
				for attachTo in attachColliderTo:
					attachToVarName = GetVarNameForObject(attachTo)
					collider += colliderName + attachToVarName + ' = world.createCollider(' + colliderDescName + ', ' + attachToVarName + 'RigidBody);\n'
					if ob.isSensor:
						collider += colliderName + attachToVarName + '.setSensor(true);\n'
					collider += 'collidersIds["' + colliderName + attachToVarName + '"] = ' + colliderName + attachToVarName + ';\n'
					collider += 'colliderOffsetsIds["' + colliderName + attachToVarName + '"] = [' + str(ob.colliderPosOff[0]) + ', ' + str(-ob.colliderPosOff[1]) + '];\n'
					collider += 'if (!collidersIds["' + ob.name + '"]) collidersIds["' + ob.name + '"] = ' + colliderName + attachToVarName + ';\n'
					collider += 'if (!colliderOffsetsIds["' + ob.name + '"]) colliderOffsetsIds["' + ob.name + '"] = [' + str(ob.colliderPosOff[0]) + ', ' + str(-ob.colliderPosOff[1]) + '];\n'
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
		worldPivot += instanceOffset
		posStr = str([worldPivot.x, -worldPivot.y])
		if ob.rigidBodyExists:
			rigidBodyName = obVarName + 'RigidBody'
			rigidBody = rigidBodyName + ' = sim.add_rigid_body(' + str(ob.rigidBodyEnable) + ', ' + str(RIGID_BODY_TYPES.index(ob.rigidBodyType)) + ', ' + posStr + ', ' + str(math.degrees(objectRotZ)) + ', ' + str(ob.gravityScale) + ', ' + str(ob.dominance) + ', ' + str(ob.canRot) + ', ' + str(ob.linearDrag) + ', ' + str(ob.angDrag) + ', ' + str(ob.canSleep) + ', ' + str(ob.continuousCollideDetect) + ')\nrigidBodiesIds["' + obVarName + '"] = ' + rigidBodyName
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
			colliderPosStr = str([worldPivot.x + ob.colliderPosOff[0], -worldPivot.y - ob.colliderPosOff[1]])
			colliderAttachPosStr = str([ob.colliderPosOff[0], -ob.colliderPosOff[1]])
			colliderRotStr = str(math.degrees(objectRotZ + ob.colliderRotOff))
			colliderAttachRotStr = str(math.degrees(ob.colliderRotOff))
			colliderName = obVarName + 'Collider'
			if attachColliderTo == []:
				if ob.colliderShapeType == 'ball':
					collider = colliderName + ' = sim.add_ball_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'halfspace':
					collider = colliderName + ' = sim.add_halfspace_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'cuboid':
					collider = colliderName + ' = sim.add_cuboid_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundCuboid':
					collider = colliderName + ' = sim.add_round_cuboid_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSize)) + ', ' + str(cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'capsule':
					collider = colliderName + ' = sim.add_capsule_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(capsuleHeight) + ', ' + str(ob.colliderCapsuleRadius) + ', ' + str(ob.colliderIsVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'segment':
					collider = colliderName + ' = sim.add_segment_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSegmentPnt0)) + ', ' + str(list(ob.colliderSegmentPnt1)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'triangle':
					collider = colliderName + ' = sim.add_triangle_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundTriangle':
					collider = colliderName + ' = sim.add_round_triangle_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'polyline':
					collider = colliderName + ' = sim.add_polyline_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + polylineIdxsStr + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'trimesh':
					collider = colliderName + ' = sim.add_trimesh_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'convexHull':
					collider = colliderName + ' = sim.add_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'roundConvexHull':
					collider = colliderName + ' = sim.add_round_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(convexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				elif ob.colliderShapeType == 'heightfield':
					collider = colliderName + ' = sim.add_heightfield_collider(' + str(ob.colliderEnable) + ', ' + colliderPosStr + ', ' + colliderRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ',' + str(list(heightfieldScale)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ')'
				collider += '\ncollidersIds["' + obVarName + '"] = ' + colliderName
				vars.append(colliderName + ' = (-1, -1)')
				globals.append(colliderName)
			else:
				for attachTo in attachColliderTo:
					attachToVarName = GetVarNameForObject(attachTo)
					if ob.colliderShapeType == 'ball':
						collider = colliderName + attachToVarName + ' = sim.add_ball_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(radius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'halfspace':
						collider = colliderName + attachToVarName + ' = sim.add_halfspace_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(normal)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'cuboid':
						collider = colliderName + attachToVarName + ' = sim.add_cuboid_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundCuboid':
						collider = colliderName + attachToVarName + ' = sim.add_round_cuboid_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(size)) + ', ' + str(cuboidBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'capsule':
						collider = colliderName + attachToVarName + ' = sim.add_capsule_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(capsuleHeight) + ', ' + str(ob.colliderCapsuleRadius) + ', ' + str(ob.colliderIsVertical) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'segment':
						collider = colliderName + attachToVarName + ' = sim.add_segment_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderSegmentPnt0)) + ', ' + str(list(ob.colliderSegmentPnt1)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'triangle':
						collider = colliderName + attachToVarName + ' = sim.add_triangle_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundTriangle':
						collider = colliderName + attachToVarName + ' = sim.add_round_triangle_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(list(ob.colliderTrianglePnt0)) + ', ' + str(list(ob.colliderTrianglePnt1)) + ', ' + str(list(ob.colliderTrianglePnt2)) + ', ' + str(triangleBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'polyline':
						collider = colliderName + attachToVarName + ' = sim.add_polyline_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(polylinePnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + polylineIdxsStr + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'trimesh':
						collider = colliderName + attachToVarName + ' = sim.add_trimesh_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(trimeshPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(trimeshIdxs) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'convexHull':
						collider = colliderName + attachToVarName + ' = sim.add_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'roundConvexHull':
						collider = colliderName + attachToVarName + ' = sim.add_round_convex_hull_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(convexHullPnts) + ', ' + str(ob.colliderConvexHullBorderRadius) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
					elif ob.colliderShapeType == 'heightfield':
						collider = colliderName + attachToVarName + ' = sim.add_heightfield_collider(' + str(ob.colliderEnable) + ', ' + colliderAttachPosStr + ', ' + colliderAttachRotStr + ', ' + str(collisionGroupMembership) + ', ' + str(collisionGroupFilter) + ', ' + str(heights) + ',' + str(list(heightfieldScale)) + ', ' + str(ob.isSensor) + ', ' + str(ob.density) + ', ' + str(ob.bounciness) + ', ' + str(BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule)) + ', rigidBodiesIds["' + attachToVarName + '"])'
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
	sizeMax = ob.maxEmitSize if ob.useMinMaxEmitSize else 1
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
	e.acc += dt * e.rate;
	while (e.acc >= 1)
	{{
		var ang = random(0, 2 * Math.PI);
		var sp = random(e.speed[0], e.speed[1]);
		var dir = ang_to_dir(ang);
		var id = e.id + '__' + Date.now() + '__' + Math.random().toString(36).slice(2);
		copy_node (e.id, id, [e.origin[0], e.origin[1]]);
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
		p.life -= dt;
		if (p.life <= 0)
		{{
			var node = document.getElementById(p.id);
			if (node)
				remove (node);
			PS_{obVarName}.splice(i, 1);
			continue;
		}}
		p.pos[0] += p.vel[0] * dt;
		p.pos[1] += p.vel[1] * dt;
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
		bursts = []
		prevBurstTime = 0.0
		for i in range(MAX_PARTICLE_SYSTEM_BURSTS):
			if getattr(ob, f'useBurst{i}'):
				burstTime = getattr(ob, f'burstTime{i}')
				bursts.append((burstTime - prevBurstTime, getattr(ob, f'burstCnt{i}')))
				prevBurstTime = burstTime
		if ob.emitShapeType == 'ball':
			particleSystem = f'{particleSystemName} = ParticleSystem("{obVarName}", "{particleName}", {ob.particleSystemEnable}, {ob.prewarmDur}, {rateMin}, {rateMax}, {bursts}, {lifeMin}, {lifeMax}, {speedMin}, {speedMax}, {rotMin}, {rotMax}, {sizeMin}, {sizeMax}, {gravityScaleMin}, {gravityScaleMax}, {bouncinessMin}, {bouncinessMax}, {emitRadiusNormalizedMin}, {emitRadiusNormalizedMax}, {linearDragMin}, {linearDragMax}, {angDragMin}, {angDragMax}, {list(ob.emitTint)}, {SHAPE_TYPES.index(ob.emitShapeType)}, {-ob.rotation_euler.z}, {ob.emitRadius})'
		particleSystem += f'\nparticleSystems["{obVarName}"] = {particleSystemName}'
		vars.append(f'{particleSystemName} : Optional[ParticleSystem] = None')
		globals.append(particleSystemName)
		particleSystems.append(particleSystem)

def RegisterUI (ob):
	if not ob.uiExists:
		return
	obVarName = GetVarNameForObject(ob)
	uiClause = f'ui["{obVarName}"] = UIElement("{obVarName}", {ob.uiEnable})'
	if ob.useOnPointerEnter:
		uiClause += f'\nuiCallbacks["{obVarName}"] = {obVarName}OnPointerEnter'
		uiMethods.append( f'def {obVarName}OnPointerEnter () -> None:\n	{ob.onPointerEnter}')
	ui.append(uiClause)

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
			materialClr = mat.color
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
				mat2.color = prevMatClrs[mat2]

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
	localOffset = Vector((size.x * ob.empty_image_offset[0], size.y * (ob.empty_image_offset[1] + 1), 0))
	rotatedOffset = Rotate2DByAngle(localOffset, ob.rotation_euler.z)
	pos += rotatedOffset
	pos.y *= -1
	return pos

def HandleCopyObject (ob, pos):
	if IsCopiedObject(ob):
		idxOfPeriod = ob.name.find('.')
		if idxOfPeriod == -1:
			obNameWithoutPeriod = ob.name
		else:
			obNameWithoutPeriod = ob.name[: idxOfPeriod]
		if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE':
			if exportType == 'exe':
				origOb = bpy.data.objects[obNameWithoutPeriod]
				imgName = GetFileName(origOb.data.filepath)
				imgPath = TMP_DIR + '/' + imgName
				if imgPath not in imgsPaths:
					imgsPaths.append(imgPath)
				AddImageDataForExe (ob, imgPath.replace(TMP_DIR, '.'), GetImagePosition(ob), ob.scale * ob.empty_display_size, ob.color[3])
		prevRotMode = ob.rotation_mode
		ob.rotation_mode = 'XYZ'
		(prefabTemplateDatas if ob in templateOnlyObs else datas).append([obNameWithoutPeriod, ob.name, TryChangeToInt(pos[0]), TryChangeToInt(pos[1]), TryChangeToInt(math.degrees(ob.rotation_euler.z)), GetAttributes(ob)])
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
			if getattr(ob, 'boolVal%i' %i):
				output[getattr(ob, 'boolName%i' %i)] = 1
			else:
				output[getattr(ob, 'boolName%i' %i)] = 0
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

def Py2Js (pyCode, txtBlock = None):
	pyScriptPath = os.path.join(TMP_DIR, 'Temp.py')
	jsScriptPath = pyScriptPath.replace('.py', '.js')
	open(pyScriptPath, 'w').write(pyCode)
	cmd = ['py2js', pyScriptPath, '-o', jsScriptPath]
	print(' '.join(cmd))
	try:
		result = subprocess.run(cmd, check=True, capture_output=True, text=True)
	except subprocess.CalledProcessError as e:
		if txtBlock:
			source = str(txtBlock)
			if not isinstance(txtBlock, str):
				source = (
					getattr(txtBlock, 'filename', None)
					or getattr(txtBlock, 'filepath', None)
					or getattr(txtBlock, 'name', None)
					or source
				)
			print(source + f': Error: {e.stderr}')
		else:
			print(f"Error: {e.stderr}", pyCode)
		return ''
	jsCode = open(jsScriptPath, 'r').read()
	jsCode = re.sub(r'([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)\.items\s*\(\)', r'Object.entries(\1)', jsCode)
	return jsCode

def Py2GbAsm (pyCode, txtBlock = None, symbol_base : str = 'gba_export', kind : str = 'update'):
	'''Transpile Python to ARM Thumb assembly for GBA (via py2gba package). kind is "init" or "update".'''
	if _py2gb_py2gb_asm:
		return _py2gb_py2gb_asm(
			pyCode,
			tmp_dir = TMP_DIR,
			repo_root_dir = _thisDir,
			txt_block = txtBlock,
			symbol_base = symbol_base,
			kind = kind,
		)
	return ''

# Backward-compatible alias for older callers.
Py2GbaAsm = Py2GbAsm

def _gba_draw_circle_rgba (canvas, center_xy, radius, color_rgba, width = 0.0):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	h = int(canvas.shape[0])
	w = int(canvas.shape[1])
	if radius <= 0:
		return
	cx = float(center_xy[0])
	cy = float(center_xy[1])
	r = float(radius)
	x0 = max(0, int(math.floor(cx - r - 1)))
	y0 = max(0, int(math.floor(cy - r - 1)))
	x1 = min(w, int(math.ceil(cx + r + 1)))
	y1 = min(h, int(math.ceil(cy + r + 1)))
	if x0 >= x1 or y0 >= y1:
		return
	yy, xx = np.ogrid[y0 : y1, x0 : x1]
	dist2 = (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy)
	r2 = r * r
	if width <= 0:
		mask = dist2 <= r2
	else:
		inner = max(0.0, r - float(width))
		mask = (dist2 <= r2) & (dist2 >= inner * inner)
	if not np.any(mask):
		return
	src = np.zeros((y1 - y0, x1 - x0, 4), dtype = np.float32)
	src[:, :, 0] = max(0, min(255, int(color_rgba[0]))) / 255.0
	src[:, :, 1] = max(0, min(255, int(color_rgba[1]))) / 255.0
	src[:, :, 2] = max(0, min(255, int(color_rgba[2]))) / 255.0
	src[:, :, 3] = 1.0
	alpha = max(0.0, min(1.0, max(0, min(255, int(color_rgba[3]))) / 255.0))
	blend = mask.astype(np.float32)[..., None] * alpha
	dst = canvas[y0 : y1, x0 : x1]
	dst[:] = (1.0 - blend) * dst + blend * src

def _runtime_ticks_ms (frame : int = None, start_time : float = None):
	if frame is not None:
		return int(round((max(0, frame - 1) * 1000.0) / 60.0))
	if start_time is not None:
		return int(max(0.0, (time.time() - start_time) * 1000.0))
	return 0

def _replace_runtime_ticks_calls (expr : str, ticks : int):
	'''Replace supported tick function calls with a numeric value.'''
	if not isinstance(expr, str):
		return expr
	return re.sub(
		r'(?:pygame\s*\.\s*time\s*\.\s*get_ticks|js13k_get_ticks)\s*\(\s*\)',
		str(ticks),
		expr,
		flags = re.IGNORECASE,
	)

_RUNTIME_KEY_INDEX = {
	'LEFT' : 0,
	'RIGHT' : 1,
	'DOWN' : 2,
	'UP' : 3,
	'A' : 4,
	'B' : 5,
	'START' : 6,
	'SELECT' : 7,
}

_RUNTIME_GB_BUTTON_ORDER = ('LEFT', 'RIGHT', 'DOWN', 'UP', 'A', 'B', 'START', 'SELECT')
_RUNTIME_GB_BUTTON_KEYSYM_DEFAULTS = {
	'LEFT' : 'Left',
	'RIGHT' : 'Right',
	'DOWN' : 'Down',
	'UP' : 'Up',
	'A' : 'x',
	'B' : 'z',
	'START' : 'Return',
	'SELECT' : 'BackSpace',
}
_RUNTIME_X11 = {
	'tried' : False,
	'ok' : False,
	'lib' : None,
	'display' : None,
	'keycode_cache' : {},
}

def _runtime_button_keysym_map ():
	'''Return GB button -> X11 keysym mapping, with optional env overrides.

	Env format:
	JS13K_MGBA_KEYMAP="A=x,B=z,START=Return,SELECT=BackSpace,LEFT=Left,RIGHT=Right,DOWN=Down,UP=Up"
	'''
	mapping = dict(_RUNTIME_GB_BUTTON_KEYSYM_DEFAULTS)
	raw = os.environ.get('JS13K_MGBA_KEYMAP', '')
	if not raw:
		return mapping
	for part in str(raw).split(','):
		part = part.strip()
		if '=' not in part:
			continue
		name, keysym = part.split('=', 1)
		name = name.strip().upper()
		keysym = keysym.strip()
		if name in mapping and keysym != '':
			mapping[name] = keysym
	return mapping

def _runtime_try_init_x11 ():
	state = _RUNTIME_X11
	if state['tried']:
		return bool(state['ok'])
	state['tried'] = True
	if not isLinux:
		return False
	if not os.environ.get('DISPLAY'):
		return False
	try:
		lib_name = ctypes.util.find_library('X11') or 'libX11.so.6'
		lib = ctypes.CDLL(lib_name)
		lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
		lib.XOpenDisplay.restype = ctypes.c_void_p
		lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
		lib.XCloseDisplay.restype = ctypes.c_int
		lib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
		lib.XQueryKeymap.restype = ctypes.c_int
		lib.XStringToKeysym.argtypes = [ctypes.c_char_p]
		lib.XStringToKeysym.restype = ctypes.c_ulong
		lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
		lib.XKeysymToKeycode.restype = ctypes.c_uint
		display = lib.XOpenDisplay(None)
		if not display:
			return False
		state['lib'] = lib
		state['display'] = display
		state['ok'] = True
		return True
	except Exception:
		return False

def _runtime_x11_key_pressed (keysym_name : str):
	if not _runtime_try_init_x11():
		return False
	state = _RUNTIME_X11
	lib = state['lib']
	display = state['display']
	try:
		keymap = ctypes.create_string_buffer(32)
		lib.XQueryKeymap(display, keymap)
		cache = state['keycode_cache']
		keysym_name = str(keysym_name)
		keycode = cache.get(keysym_name)
		if keycode is None:
			keysym = lib.XStringToKeysym(keysym_name.encode('utf-8'))
			if keysym == 0:
				cache[keysym_name] = 0
				return False
			keycode = int(lib.XKeysymToKeycode(display, keysym))
			cache[keysym_name] = keycode
		if keycode <= 0:
			return False
		return bool(keymap.raw[keycode // 8] & (1 << (keycode % 8)))
	except Exception:
		return False

def _replace_runtime_key_calls (expr : str):
	'''Normalize supported pygame key API calls/constants to js13k runtime forms.'''
	if not isinstance(expr, str):
		return expr
	out = re.sub(
		r'pygame\s*\.\s*key\s*\.\s*get_pressed\s*\(\s*\)',
		'js13k_get_pressed()',
		expr,
		flags = re.IGNORECASE,
	)
	for name, idx in _RUNTIME_KEY_INDEX.items():
		out = re.sub(
			r'pygame\s*\.\s*K_' + name + r'\b',
			str(idx),
			out,
			flags = re.IGNORECASE,
		)
	return out

def _runtime_key_state_snapshot ():
	'''Return GB button state for expression evaluation/log mirroring.

	Order: LEFT, RIGHT, DOWN, UP, A, B, START, SELECT.
	Uses global X11 key state on Linux (works while mGBA has focus). Falls back
	to all-False when unavailable.
	'''
	btn_map = _runtime_button_keysym_map()
	out = []
	for btn in _RUNTIME_GB_BUTTON_ORDER:
		out.append(bool(_runtime_x11_key_pressed(btn_map.get(btn, ''))))
	return tuple(out)

def _eval_runtime_expr_value (value, frame : int = None, start_time : float = None):
	if isinstance(value, (int, float)):
		return float(value)
	if value is None:
		return None
	if not isinstance(value, str):
		try:
			return float(value)
		except Exception:
			return None
	ticks = _runtime_ticks_ms(frame = frame, start_time = start_time)
	expr = value.strip()
	match = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', expr)
	if match:
		expr = match.group(1).strip()
	expr = _replace_runtime_ticks_calls(expr, ticks)
	expr = _replace_runtime_key_calls(expr)
	try:
		return float(expr)
	except Exception:
		pass
	key_state = _runtime_key_state_snapshot()
	try:
		val = eval(
			expr,
			{'__builtins__' : {}},
			{
				'int' : int,
				'float' : float,
				'round' : round,
				'abs' : abs,
				'max' : max,
				'min' : min,
				'js13k_get_pressed' : (lambda : key_state),
			},
		)
		if isinstance(val, (int, float, bool)):
			return float(val)
	except Exception:
		return None
	return None

def _gba_draw_circle_from_script (canvas, circle : dict, frame : int = None, start_time : float = None):
	if not isinstance(circle, dict):
		return
	cond = circle.get('condition')
	if cond is not None and cond != '':
		cond_val = _eval_runtime_expr_value(cond, frame = frame, start_time = start_time)
		if cond_val is None or abs(float(cond_val)) <= 1e-9:
			return
	center = circle.get('center', [0, 0])
	if not isinstance(center, (list, tuple)) or len(center) < 2:
		return
	cx = _eval_runtime_expr_value(center[0], frame = frame, start_time = start_time)
	cy = _eval_runtime_expr_value(center[1], frame = frame, start_time = start_time)
	radius = _eval_runtime_expr_value(circle.get('radius', 0), frame = frame, start_time = start_time)
	width = _eval_runtime_expr_value(circle.get('width', 0), frame = frame, start_time = start_time)
	if cx is None or cy is None or radius is None:
		return
	if width is None:
		width = 0.0
	color_raw = circle.get('color', [255, 255, 255, 255])
	if isinstance(color_raw, (list, tuple)) and len(color_raw) == 3:
		color_raw = [color_raw[0], color_raw[1], color_raw[2], 255]
	elif not isinstance(color_raw, (list, tuple)) or len(color_raw) < 4:
		color_raw = [255, 255, 255, 255]
	color = []
	for i in range(4):
		c = _eval_runtime_expr_value(color_raw[i], frame = frame, start_time = start_time)
		if c is None:
			c = 255 if i < 3 else 255
		color.append(int(max(0, min(255, round(c)))))
	_gba_draw_circle_rgba(canvas, [cx, cy], float(radius), color, float(width))

def _is_pygame_draw_circle_call (call_node):
	if not isinstance(call_node, ast.Call):
		return False
	func = call_node.func
	return (
		isinstance(func, ast.Attribute)
		and func.attr == 'circle'
		and isinstance(func.value, ast.Attribute)
		and func.value.attr == 'draw'
		and isinstance(func.value.value, ast.Name)
		and func.value.value.id == 'pygame'
	)

def _is_display_get_surface_call (node):
	return (
		isinstance(node, ast.Call)
		and isinstance(node.func, ast.Attribute)
		and node.func.attr == 'get_surface'
		and isinstance(node.func.value, ast.Attribute)
		and node.func.value.attr == 'display'
		and isinstance(node.func.value.value, ast.Name)
		and node.func.value.value.id == 'pygame'
	)

def _is_this_surface_member (node):
	return (
		isinstance(node, ast.Attribute)
		and node.attr == 'surface'
		and isinstance(node.value, ast.Name)
		and node.value.id == 'this'
	)

def _is_get_ticks_call (node):
	if not isinstance(node, ast.Call):
		return False
	# Original pygame runtime API form.
	if (
		isinstance(node.func, ast.Attribute)
		and node.func.attr == 'get_ticks'
		and isinstance(node.func.value, ast.Attribute)
		and node.func.value.attr == 'time'
		and isinstance(node.func.value.value, ast.Name)
		and node.func.value.value.id == 'pygame'
	):
		return True
	# Normalized gba/gbc script form introduced by _normalize_gb_script_code.
	return isinstance(node.func, ast.Name) and node.func.id == 'js13k_get_ticks'

def _has_dynamic_runtime_expr (node):
	for n in ast.walk(node):
		if _is_get_ticks_call(n):
			return True
	return False

def _serialize_script_expr (node):
	if isinstance(node, ast.Constant):
		if isinstance(node.value, (int, float)):
			return node.value
	if isinstance(node, (ast.Tuple, ast.List)):
		return [_serialize_script_expr(e) for e in node.elts]
	try:
		return '<expr:' + ast.unparse(node) + '>'
	except Exception:
		return '<expr:0>'

def _literal_truthy_from_ast_node (node):
	'''Return True/False for literal truthy tests, or None when dynamic/unknown.'''
	try:
		val = ast.literal_eval(node)
	except Exception:
		return None
	if isinstance(val, bool):
		return val
	if isinstance(val, (int, float)):
		return bool(val)
	return None

def _is_in_statically_dead_if_branch (node, parent_map):
	'''Check whether node is in a compile-time dead branch of `if` statement.'''
	child = node
	parent = parent_map.get(child)
	while parent is not None:
		if isinstance(parent, ast.If):
			truth = _literal_truthy_from_ast_node(parent.test)
			if truth is False and child in parent.body:
				return True
			if truth is True and child in parent.orelse:
				return True
		child = parent
		parent = parent_map.get(child)
	return False

def _walk_statically_reachable_stmts (stmts):
	'''Yield statements on branches that are compile-time reachable.'''
	for stmt in list(stmts or []):
		yield stmt
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				for inner in _walk_statically_reachable_stmts(stmt.body):
					yield inner
			elif truth is False:
				for inner in _walk_statically_reachable_stmts(stmt.orelse):
					yield inner

def _extract_dynamic_draw_circles_from_script (code : str, is_init : bool):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return []
	return _extract_dynamic_draw_circles_from_stmts(getattr(tree, 'body', []), is_init, parent_condition = None)

def _extract_dynamic_draw_circles_from_stmts (stmts, is_init : bool, parent_condition = None):
	circles = []
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Expr):
			node = stmt.value
			if not isinstance(node, ast.Call) or not _is_pygame_draw_circle_call(node):
				pass
			elif len(node.args) < 4:
				pass
			else:
				target = node.args[0]
				target_type = None
				if _is_display_get_surface_call(target):
					target_type = 'display_surface'
				elif _is_this_surface_member(target):
					target_type = 'this_surface'
				if target_type:
					color_node = node.args[1]
					center_node = node.args[2]
					radius_node = node.args[3]
					width_node = node.args[4] if len(node.args) >= 5 else ast.Constant(value = 0)
					if (
						_has_dynamic_runtime_expr(color_node)
						or _has_dynamic_runtime_expr(center_node)
						or _has_dynamic_runtime_expr(radius_node)
						or _has_dynamic_runtime_expr(width_node)
					):
						circle = {
							'color' : _serialize_script_expr(color_node),
							'center' : _serialize_script_expr(center_node),
							'radius' : _serialize_script_expr(radius_node),
							'width' : _serialize_script_expr(width_node),
							'is_init' : bool(is_init),
							'target_type' : target_type,
						}
						if parent_condition is not None:
							circle['condition'] = parent_condition
						circles.append(circle)
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				circles.extend(_extract_dynamic_draw_circles_from_stmts(stmt.body, is_init, parent_condition))
				continue
			if truth is False:
				circles.extend(_extract_dynamic_draw_circles_from_stmts(stmt.orelse, is_init, parent_condition))
				continue
			test_expr = _serialize_script_expr(stmt.test)
			body_cond = _combine_expr_conditions(parent_condition, test_expr)
			else_cond = _combine_expr_conditions(parent_condition, _negate_expr_condition(test_expr))
			circles.extend(_extract_dynamic_draw_circles_from_stmts(stmt.body, is_init, body_cond))
			circles.extend(_extract_dynamic_draw_circles_from_stmts(stmt.orelse, is_init, else_cond))
	return circles

def _is_print_call (call_node):
	return isinstance(call_node, ast.Call) and isinstance(call_node.func, ast.Name) and call_node.func.id == 'print'

def _serialize_print_call_text (call_node):
	if not _is_print_call(call_node):
		return None
	sep = ' '
	end = '\n'
	for kw in list(call_node.keywords or []):
		if kw.arg == 'sep':
			val = _serialize_script_expr(kw.value)
			if isinstance(val, str):
				sep = val
			elif isinstance(val, (int, float, bool)):
				sep = str(val)
		elif kw.arg == 'end':
			val = _serialize_script_expr(kw.value)
			if isinstance(val, str):
				end = val
			elif isinstance(val, (int, float, bool)):
				end = str(val)
	parts = []
	for arg in list(call_node.args or []):
		val = _serialize_script_expr(arg)
		if isinstance(val, str):
			parts.append(val)
		elif isinstance(val, (int, float, bool)):
			parts.append(str(val))
		else:
			parts.append(str(val))
	return sep.join(parts) + end

def _unwrap_expr_placeholder (expr):
	if not isinstance(expr, str):
		return str(expr)
	m = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', expr.strip())
	return m.group(1).strip() if m else expr.strip()

def _combine_expr_conditions (lhs, rhs):
	if lhs is None:
		return rhs
	if rhs is None:
		return lhs
	lhs_s = _unwrap_expr_placeholder(lhs)
	rhs_s = _unwrap_expr_placeholder(rhs)
	return '<expr:(' + lhs_s + ') and (' + rhs_s + ')>'

def _negate_expr_condition (expr):
	if expr is None:
		return None
	expr_s = _unwrap_expr_placeholder(expr)
	return '<expr:not (' + expr_s + ')>'

def _extract_print_calls_from_stmts (stmts, is_init : bool, owner_name : str, parent_condition = None):
	prints = []
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Expr) and _is_print_call(stmt.value):
			text = _serialize_print_call_text(stmt.value)
			if text is None:
				continue
			info = {
				'owner_name' : owner_name or '__world__',
				'is_init' : bool(is_init),
				'text' : text,
			}
			if parent_condition is not None:
				info['condition'] = parent_condition
			prints.append(info)
			continue
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				prints.extend(_extract_print_calls_from_stmts(stmt.body, is_init, owner_name, parent_condition))
				continue
			if truth is False:
				prints.extend(_extract_print_calls_from_stmts(stmt.orelse, is_init, owner_name, parent_condition))
				continue
			test_expr = _serialize_script_expr(stmt.test)
			body_cond = _combine_expr_conditions(parent_condition, test_expr)
			else_cond = _combine_expr_conditions(parent_condition, _negate_expr_condition(test_expr))
			prints.extend(_extract_print_calls_from_stmts(stmt.body, is_init, owner_name, body_cond))
			prints.extend(_extract_print_calls_from_stmts(stmt.orelse, is_init, owner_name, else_cond))
	return prints

def _extract_print_calls_from_script (code : str, is_init : bool, owner_name : str):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return []
	return _extract_print_calls_from_stmts(getattr(tree, 'body', []), is_init, owner_name, parent_condition = None)

def _augment_runtime_with_dynamic_circles (script_runtime : dict, script_entries : list):
	if not isinstance(script_runtime, dict):
		script_runtime = {}
	# Rebuild dynamic circle overlays from source scripts so dead branches
	# (for example `if False:`) do not leak into baked fallback rendering.
	init_draw = []
	update_draw = []
	surface_ops = []
	for op in list(script_runtime.get('surface_ops') or []):
		if isinstance(op, dict) and op.get('op') == 'draw_circle_surface_member':
			continue
		surface_ops.append(op)
	print_calls = []
	existing_print_keys = set()
	for info in list(script_runtime.get('print_calls') or []):
		if not isinstance(info, dict):
			continue
		key = (
			bool(info.get('is_init')),
			str(info.get('owner_name') or '__world__'),
			str(info.get('text', '')),
			str(info.get('condition') or ''),
		)
		existing_print_keys.add(key)
		print_calls.append(info)
	for entry in script_entries or []:
		code = entry.get('code', '')
		is_init = bool(entry.get('is_init'))
		owner_name = entry.get('owner_name') or '__world__'
		extracted = _extract_dynamic_draw_circles_from_script(code, is_init)
		for circle in extracted:
			target_type = circle.get('target_type')
			if target_type == 'display_surface':
				if is_init:
					init_draw.append(circle)
				else:
					update_draw.append(circle)
			elif target_type == 'this_surface':
				# Fallback path: apply dynamic this.surface draw calls on image surfaces.
				surface_ops.append({
					'op' : 'draw_circle_surface_member',
					'owner_name' : owner_name,
					'member' : 'surface',
					'is_init' : bool(is_init),
					'center' : circle.get('center') or [0.0, 0.0],
					'radius' : circle.get('radius') or 0.0,
					'color' : circle.get('color') or [255, 255, 255, 255],
					'width' : circle.get('width') or 0.0,
					'condition' : circle.get('condition'),
				})
			else:
				continue
		for info in _extract_print_calls_from_script(code, is_init, owner_name):
			key = (
				bool(info.get('is_init')),
				str(info.get('owner_name') or '__world__'),
				str(info.get('text', '')),
				str(info.get('condition') or ''),
			)
			if key in existing_print_keys:
				continue
			existing_print_keys.add(key)
			print_calls.append(info)
	script_runtime['init_draw_circles'] = init_draw
	script_runtime['update_draw_circles'] = update_draw
	script_runtime['surface_ops'] = surface_ops
	script_runtime['print_calls'] = print_calls
	return script_runtime

def _normalize_gb_script_code (code : str, is_init : bool):
	if not code:
		return code
	code2 = code
	uses_ticks = bool(re.search(r'pygame\s*\.\s*time\s*\.\s*get_ticks\s*\(\s*\)', code2, flags = re.IGNORECASE))
	if uses_ticks:
		code2 = re.sub(
			r'pygame\s*\.\s*time\s*\.\s*get_ticks\s*\(\s*\)',
			'js13k_get_ticks()',
			code2,
			flags = re.IGNORECASE,
		)
		if is_init:
			prefix = (
				'global __js13k_ticks\n'
				'__js13k_ticks = 0\n'
				'def js13k_get_ticks():\n'
				'    return __js13k_ticks\n'
			)
		else:
			# Keep a monotonic millisecond-ish counter for update scripts.
			prefix = (
				'global __js13k_ticks\n'
				'try:\n'
				'    __js13k_ticks += 16\n'
				'except:\n'
				'    __js13k_ticks = 0\n'
				'def js13k_get_ticks():\n'
				'    return __js13k_ticks\n'
			)
		code2 = prefix + code2
	return code2

def ExportGbaPyAssembly (world, gba_out_path : str):
	'''Collect gba-py scripts from world and exported objects; write Thumb assembly next to the .gba.'''
	global exportType
	prev_export = exportType
	exportType = 'gba'
	script_entries = []
	if world:
		for scriptInfo in GetScripts(world):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type == 'gba-py':
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init))
				script_entries.append({
					'code' : scriptTxt,
					'is_init' : is_init,
					'script_obj' : script,
					'owner_name' : '__world__',
					'symbol_hint' : 'world_' + getattr(script, 'name', 'script'),
				})
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		for scriptInfo in GetScripts(ob):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type == 'gba-py':
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init))
				script_entries.append({
					'code' : scriptTxt,
					'is_init' : is_init,
					'script_obj' : script,
					'owner_name' : ob.name,
					'symbol_hint' : ob.name + '_' + getattr(script, 'name', 'script'),
				})
	exportType = prev_export
	if _py2gb_export_gba_py_assembly:
		runtime = _run_py2gba_export_with_resolved_logs(_py2gb_export_gba_py_assembly, script_entries, gba_out_path)
		return _augment_runtime_with_dynamic_circles(runtime, script_entries)
	return {'script_count' : 0, 'init_quit' : False, 'update_quit' : False, 'init_draw_circles' : [], 'update_draw_circles' : [], 'surface_ops' : [], 'builtin_only_quit' : True}

def ExportGbcPyAssembly (world, gbc_out_path : str):
	'''Collect gbc-py scripts from world and exported objects; write translated assembly next to the .gbc.'''
	global exportType
	prev_export = exportType
	exportType = 'gbc'
	script_entries = []
	if world:
		for scriptInfo in GetScripts(world):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type == 'gbc-py':
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init))
				script_entries.append({
					'code' : scriptTxt,
					'is_init' : is_init,
					'script_obj' : script,
					'owner_name' : '__world__',
					'symbol_hint' : 'world_' + getattr(script, 'name', 'script'),
				})
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		for scriptInfo in GetScripts(ob):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type == 'gbc-py':
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init))
				script_entries.append({
					'code' : scriptTxt,
					'is_init' : is_init,
					'script_obj' : script,
					'owner_name' : ob.name,
					'symbol_hint' : ob.name + '_' + getattr(script, 'name', 'script'),
				})
	exportType = prev_export
	if _py2gb_export_gba_py_assembly:
		runtime = _run_py2gba_export_with_resolved_logs(_py2gb_export_gba_py_assembly, script_entries, gbc_out_path)
		return _augment_runtime_with_dynamic_circles(runtime, script_entries)
	return {'script_count' : 0, 'init_quit' : False, 'update_quit' : False, 'init_draw_circles' : [], 'update_draw_circles' : [], 'surface_ops' : [], 'builtin_only_quit' : True}

def GetBlenderData ():
	global ui, vars, clrs, datas, joints, pivots, prefabs, globals, initCode, svgsDatas, colliders, renderCode, pathsDatas, updateCode, attributes, uiMethods, exportedObs, rigidBodies, charControllers, particleSystems, templateScripts, prefabTemplateDatas, prefabPathsDatas, templateOnlyObs, collectionInstanceCopyCounts
	vars = []
	attributes = {}
	pivots = {}
	exportedObs = []
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
	ui = []
	uiMethods = []
	initCode = []
	updateCode = []
	svgsDatas = {}
	globals = []
	renderCode = []
	prefabs = {}
	templateScripts = {}
	prefabTemplateDatas = []
	prefabPathsDatas = []
	collectionInstanceCopyCounts = {}
	instancedObjects = GetInstancedObjects(bpy.context.scene)
	instancedCollectionTemplateObjects = GetInstancedCollectionTemplateObjects(bpy.context.scene)
	inPrefabColl = set()
	inNonPrefabColl = set()
	for coll in bpy.data.collections:
		exportPrefab = getattr(coll, 'exportPrefab', False)
		for ob in coll.objects:
			if exportPrefab:
				inPrefabColl.add(ob)
			else:
				inNonPrefabColl.add(ob)
	templateOnlyObs = set(inPrefabColl)
	for ob in bpy.data.objects:
		if ob in instancedObjects and ob not in instancedCollectionTemplateObjects:
			ExportObject (ob)
	GatherPrefabs ()
	for ob in bpy.data.objects:
		if not ob.exportOb:
			continue
		if ob not in exportedObs and ob not in templateOnlyObs:
			continue
		for scriptInfo in GetScripts(ob):
			scriptTxt = scriptInfo[0]
			isInit = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type.startswith(exportType):
				if _type == 'html-py':
					scriptTxt = Py2Js(scriptTxt, script)
				elif _type == 'gba-py':
					continue
				obName = ob.name
				sceneId = obName[:-1] if obName.endswith('_') else obName
				if sceneId not in templateScripts:
					templateScripts[sceneId] = {'init': [], 'update': []}
				if isInit:
					if scriptTxt not in templateScripts[sceneId]['init']:
						templateScripts[sceneId]['init'].append(scriptTxt)
				else:
					if scriptTxt not in templateScripts[sceneId]['update']:
						templateScripts[sceneId]['update'].append(scriptTxt)
	world = bpy.context.world
	if world:
		for scriptInfo in GetScripts(world):
			scriptTxt = scriptInfo[0]
			isInit = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			if _type.startswith(exportType):
				if _type == 'html-py':
					scriptTxt = Py2Js(scriptTxt, script)
				elif _type == 'gba-py':
					continue
				if isInit:
					if script not in initCode:
						initCode.append(scriptTxt)
				else:
					if script not in updateCode:
						updateCode.append(scriptTxt)
	return (datas, initCode, updateCode)

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
pivots = {}
attributes = {}
liveObjectNames = set()
instanceToTemplate = {}
templateScripts = {}
scripts = {}
scriptLocals = {}
_currentInstanceName = None

class _ThisObject:
	def __init__ (self, name):
		self.name = name
	def get_position (self):
		return get_object_position(self.name)
	def get_rotation (self):
		return get_object_rotation(self.name)

mousePos = pygame.math.Vector2()
mousePosWorld = pygame.math.Vector2()
prevMousePos = pygame.math.Vector2()
prevMousePosWorld = pygame.math.Vector2()
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

def register_instance (templateName, instanceName):
	liveObjectNames.add(instanceName)
	instanceToTemplate[instanceName] = templateName

def unregister_instance (name):
	liveObjectNames.discard(name)
	instanceToTemplate.pop(name, None)
	scripts.pop(name, None)
	scriptLocals.pop(name, None)

def _get_script_locals (instanceName, this):
	if instanceName not in scriptLocals:
		scriptLocals[instanceName] = {}
	scriptLocals[instanceName]['this'] = this
	scriptLocals[instanceName]['_currentInstanceName'] = instanceName
	return scriptLocals[instanceName]

def _exec_script (code, instanceName, this, phase):
	try:
		exec(code, globals(), _get_script_locals(instanceName, this))
	except Exception as err:
		print(f"[script:{phase}] {instanceName}: {err}")

def run_init_scripts (name):
	global _currentInstanceName
	this = _ThisObject(name)
	tid = instanceToTemplate.get(name)
	if tid and tid in templateScripts and templateScripts[tid].get('init'):
		_currentInstanceName = name
		for code in templateScripts[tid]['init']:
			try: exec(code, { **globals(), 'this': this, '_currentInstanceName': name })
			except: pass
		_currentInstanceName = None
	if name in scripts and scripts[name].get('init'):
		_currentInstanceName = name
		for code in scripts[name]['init']:
			_exec_script(code, name, this, 'init')
		_currentInstanceName = None

def run_update_scripts ():
	global _currentInstanceName
	for name in list(liveObjectNames):
		this = _ThisObject(name)
		tid = instanceToTemplate.get(name)
		if tid and tid in templateScripts and templateScripts[tid].get('update'):
			_currentInstanceName = name
			for code in templateScripts[tid]['update']:
				_exec_script(code, name, this, 'update')
			_currentInstanceName = None
		if name in scripts and scripts[name].get('update'):
			_currentInstanceName = name
			for code in scripts[name]['update']:
				_exec_script(code, name, this, 'update')
			_currentInstanceName = None

def add_script (instanceName, code, type):
	if instanceName not in scripts:
		scripts[instanceName] = {'init': [], 'update': []}
	scripts[instanceName][type].append(code)
	if type == 'init':
		global _currentInstanceName
		_currentInstanceName = instanceName
		this = _ThisObject(instanceName)
		_exec_script(code, instanceName, this, 'init')
		_currentInstanceName = None

def remove_script (instanceName, type, index):
	if instanceName in scripts and type in scripts[instanceName] and 0 <= index < len(scripts[instanceName][type]):
		scripts[instanceName][type].pop(index)

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
		particleSystem = particleSystems[name]
		newParticleSystem = particleSystem.copy(newName)
		if copyParticles:
			for particle in particleSystem.particles:
				particlePos = get_object_position(particle.name)
				particleRot = get_object_rotation(particle.name)
				newParticleName = newName + ':' + str(particleSystem.lastId)
				copy_object (particle.name, newParticleName, rotate_vector(particlePos, pos, rot), particleRot + rot)
				newParticleSystem.particles.append(Particle(newParticleName, particle.life))
		particleSystems[newName] = newParticleSystem
	register_instance(name, newName)
	run_init_scripts(newName)

def remove_object (name, removeColliders = True, wakeUp = True, removeParticles = True):
	unregister_instance(name)
	if name in pivots:
		del surfaces[name]
		del surfacesRects[name]
		del initRots[name]
		del pivots[name]
		game.sortedObNames = [item for item in game.sortedObNames if item != name]
	if name in attributes:
		del attributes[name]
	if name in zOrders:
		del zOrders[name]
	if name in rigidBodiesIds:
		rigidBody = rigidBodiesIds[name]
		if removeColliders:
			for removeCollider in sim.get_rigid_body_colliders(rigidBody):
				for colliderName, collider in list(collidersIds.items()):
					if collider == removeCollider:
						del collidersIds[colliderName]
						break
		sim.remove_rigid_body (rigidBody, removeColliders)
		del rigidBodiesIds[name]
	elif name in collidersIds:
		sim.remove_collider (collidersIds[name], wakeUp)
		del collidersIds[name]
	if removeParticles and name in particleSystems:
		particleSystem = particleSystems.pop(name)
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
		raise ValueError('name needs to refer to a rigid body or a collider found in rigidBodiesIds or collidersIds')

def get_object_rotation (name):
	if name in rigidBodiesIds:
		return sim.get_rigid_body_rotation(rigidBodiesIds[name])
	elif name in collidersIds:
		return sim.get_collider_rotation(collidersIds[name])
	else:
		raise ValueError('name needs to refer to a rigid body or a collider found in rigidBodiesIds or collidersIds')

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
	bursts : list[tuple[float, int]]
	currBurstIdx : int
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

	def __init__ (self, name : str, particleName : str, enable : bool, prewarmDur : float, minRate : float, maxRate : float, bursts : list[tuple[float, int]], minLife : float, maxLife : float, minSpeed : float, maxSpeed : float, minRot : float, maxRot : float, minSize : float, maxSize : float, minGravityScale : float, maxGravityScale : float, minBounciness : float, maxBounciness : float, maxEmitRadiusNormalized : float, minEmitRadiusNormalized : float, minLinearDrag : float, maxLinearDrag : float, minAngDrag : float, maxAngDrag : float, tint : list[float], shapeType : int, shapeRot : float, ballRadius : float = 0.0):
		self.name = name
		self.particleName = particleName
		self.enable = enable
		self.minRate = minRate
		self.maxRate = maxRate
		self.intvl = 1.0 / uniform(minRate, maxRate)
		self.bursts = bursts
		self.currBurstIdx = 0
		self.minSize = minSize
		self.maxSize = maxSize
		self.minLife = minLife
		self.maxLife = maxLife
		self.minSpeed = minSpeed
		self.maxSpeed = maxSpeed
		self.minRot = minRot
		self.maxRot = maxRot
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
		if self.currBurstIdx < len(self.bursts):
			burst = self.bursts[self.currBurstIdx]
			if self.timer >= burst[0]:
				self.timer -= burst[0]
				for i in range(burst[1]):
					self.emit ()
				self.currBurstIdx += 1
		if self.timer >= self.intvl:
			self.timer -= self.intvl
			self.intvl = 1.0 / uniform(self.minRate, self.maxRate)
			self.emit ()
		for particle in list(self.particles):
			particle.life -= dt
			if particle.life <= 0:
				remove_object (particle.name)
				self.particles.remove(particle)

	def emit (self):
		size = uniform(self.minSize, self.maxSize)
		newParticleName = self.name + ':' + str(self.lastId)
		self.lastId += 1
		obPos = get_object_position(self.name)
		rot = uniform(self.minRot, self.maxRot)
		normalizedRadius = uniform(self.minEmitRadiusNormalized, self.maxEmitRadiusNormalized)
		randRad = uniform(0, 2 * math.pi)
		if self.shapeType == 0: # ball
			pos = pygame.math.Vector2(obPos[0] + self.ballRadius * normalizedRadius * math.cos(randRad), obPos[1] + self.ballRadius * normalizedRadius * math.sin(randRad))
		else:
			pos = pygame.math.Vector2(0, 0)
		copy_object (self.particleName, newParticleName, pos, rot)
		if newParticleName in surfaces:
			surfaces[newParticleName] = pygame.transform.scale_by(surfaces[newParticleName], size)
		rigidBody = rigidBodiesIds[newParticleName]
		for collider in sim.get_rigid_body_colliders(rigidBody):
			sim.set_bounciness (collider, uniform(self.minBounciness, self.maxBounciness))
			sim.set_collider_enabled (collider, True)
		sim.set_gravity_scale (rigidBody, uniform(self.minGravityScale, self.maxGravityScale), False)
		sim.set_linear_drag (rigidBody, uniform(self.minLinearDrag, self.maxLinearDrag))
		sim.set_angular_drag (rigidBody, uniform(self.minAngDrag, self.maxAngDrag))
		sim.set_rigid_body_enabled (rigidBody, True)
		sim.set_linear_velocity (rigidBody, ang_to_dir(math.degrees(randRad)) * uniform(self.minSpeed, self.maxSpeed))
		self.particles.append(Particle(newParticleName, uniform(self.minLife, self.maxLife)))

	def copy (self, newName : str):
		return ParticleSystem(newName, self.particleName, self.enable, self.prewarmDur, self.minRate, self.maxRate, self.bursts, self.minLife, self.maxLife, self.minSpeed, self.maxSpeed, self.minRot, self.maxRot, self.minSize, self.maxSize, self.minGravityScale, self.maxGravityScale, self.minBounciness, self.maxBounciness, self.maxEmitRadiusNormalized, self.minEmitRadiusNormalized, self.minLinearDrag, self.maxLinearDrag, self.minAngDrag, self.maxAngDrag, self.tint, self.shapeType, self.shapeRot, self.ballRadius)

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
		global ui, sim, off, hide, pivots, initRots, surfaces, jointsIds, attributes, uiCallbacks, collidersIds, surfacesRects, rigidBodiesIds, particleSystems
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
		ui = {}
		uiCallbacks = {}
# Init Pivots, Attributes, UI
# Init Physics
# Init Rendering
# Init Particle Systems
		self.sortedObNames = [name for name, z in sorted(zOrders.items(), key = lambda item : item[1])]
# Register Live Objects And Run Inits

	def update (self):
		global off, mousePos, uiCallbacks, mousePosWorld, prevMousePos, prevMousePosWorld
# Globals
		mousePos = pygame.mouse.get_pos()
		mousePosWorld = mousePos + off
# Physics Section Start
		sim.step ()
# Physics Section End
		run_update_scripts ()
		for particleSystem in list(particleSystems.values()):
			if particleSystem.enable:
				particleSystem.update (self.dt)
		for name, uiOb in list(ui.items()):
			if uiOb.enable:
				uiOb.update ()
		prevMousePos = mousePos
		prevMousePosWorld = mousePosWorld

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
class UIElement:
	name : str
	enable : bool

	def __init__ (self, name : str, enable : bool):
		self.name = name
		self.enable = enable

	def update (self):
		if self.name in uiCallbacks and surfacesRects[self.name].collidepoint(mousePosWorld) and not surfacesRects[self.name].collidepoint(prevMousePosWorld):
			uiCallbacks[self.name] ()

	def copy (self, newName : str, enable : bool):
		newUIElt = UIElement(newName, enable)
		uiCallbacks[newName] = uiCallbacks[self.name].copy()
		return newUIElt

ui : dict[str, UIElement] = {}
uiCallbacks : dict[str, Callable[[], None]] = {}
# UI Methods
game.init ()
# API
# Init User Code
game.run ()'''
JS_SUFFIX = '''
var d = JSON.parse(D);
var c = JSON.parse(C);
var prefabTemplatesData = typeof PT !== 'undefined' ? JSON.parse(PT) : [];
var prefabPathCount = typeof PPC !== 'undefined' ? PPC : 0;
var templateIdsToHide = [];
var templateG = [];
var templateCopies = [];
var ti = 0;
for (var e of prefabTemplatesData)
{
	var l = e.length;
	if (l > 10)
	{
		add_svg (e[0], e[1], [e[2], e[3]], c[e[4]], e[5], c[e[6]], e[7], p.split('\\n')[ti].split(String.fromCharCode(1)), e[8], e[9], e[10], e[11], e[12], e[13], [e[14], e[15]], e[16], e[17], [e[18], e[19]], [e[20], e[21]], e[22], e[23], e[24], e[25], [e[26], e[27]], [e[28], e[29]], [e[30], e[31]], [e[32], e[33]], [e[34], e[35]], [e[36], e[37]], [e[38], e[39]], [e[40], e[41]], [e[42], e[43]], e[44], e[45], e[46], e[47], e[48], e[49], e[50]);
		templateIdsToHide.push(e[7]);
		ti ++;
	}
	else if (l > 6)
	{
		add_radial_gradient (e[0], [e[1], e[2]], e[3], e[4], c[e[5]], c[e[6]], c[e[7]], e[8], e[9]);
		templateIdsToHide.push(e[0]);
	}
	else if (Array.isArray(e[3]))
		templateG.push(e);
	else if (l > 5)
		templateCopies.push(e);
	else
		templateG.push(e);
}
function children_ready (childIds)
{
	for (var childId of childIds)
		if (!document.getElementById(childId))
			return false;
	return true;
}
function build_child_parent_map (groups)
{
	var output = {};
	for (var g of groups)
	{
		var parentId = g[0];
		var childIds = g[3];
		for (var childId of childIds)
			output[childId] = parentId;
	}
	return output;
}
var templateChildParent = build_child_parent_map(templateG);
var pendingTemplateGroups = templateG.slice();
var pendingTemplateCopies = templateCopies.slice();
var templateSafety = pendingTemplateGroups.length + pendingTemplateCopies.length + 1;
while ((pendingTemplateGroups.length > 0 || pendingTemplateCopies.length > 0) && templateSafety > 0)
{
	templateSafety --;
	var progressed = false;
	for (var idx = pendingTemplateCopies.length - 1; idx >= 0; idx --)
	{
		var e = pendingTemplateCopies[idx];
		var parentId = templateChildParent[e[1]] || null;
		if (!document.getElementById(e[0]))
			continue;
		copy_node (e[0], e[1], [e[2], e[3]], e[4], e[5], parentId);
		templateIdsToHide.push(e[1]);
		pendingTemplateCopies.splice(idx, 1);
		progressed = true;
	}
	for (var idx = pendingTemplateGroups.length - 1; idx >= 0; idx --)
	{
		var e = pendingTemplateGroups[idx];
		if (!children_ready(e[3]))
			continue;
		add_div (e[0], [e[1], e[2]], e[3], e[4], '', e[5] || 0);
		templateIdsToHide.push(e[0]);
		pendingTemplateGroups.splice(idx, 1);
		progressed = true;
	}
	if (!progressed)
		break;
}
for (var e of pendingTemplateGroups)
{
	add_div (e[0], [e[1], e[2]], e[3], e[4], '', e[5] || 0);
	templateIdsToHide.push(e[0]);
}
for (var e of pendingTemplateCopies)
{
	var parentId = templateChildParent[e[1]] || null;
	copy_node (e[0], e[1], [e[2], e[3]], e[4], e[5], parentId);
	templateIdsToHide.push(e[1]);
}
for (var id of templateIdsToHide)
{
	var el = document.getElementById(id);
	if (el)
		el.style.visibility = 'hidden';
}
var templateIdSet = {};
for (var id of templateIdsToHide)
	templateIdSet[id] = 1;
var i = prefabPathCount;
var prefabs = typeof P !== 'undefined' ? JSON.parse(P) : {};
var templateScripts = __TEMPLATE_SCRIPTS_JSON__;
var g = [];
var copies = [];
for (var e of d)
{
	var l = e.length;
	if (l > 10)
	{
		if (templateIdSet[e[7]])
			continue;
		add_svg (e[0], e[1], [e[2], e[3]], c[e[4]], e[5], c[e[6]], e[7], p.split('\\n')[i].split(String.fromCharCode(1)), e[8], e[9], e[10], e[11], e[12], e[13], [e[14], e[15]], e[16], e[17], [e[18], e[19]], [e[20], e[21]], e[22], e[23], e[24], e[25], [e[26], e[27]], [e[28], e[29]], [e[30], e[31]], [e[32], e[33]], [e[34], e[35]], [e[36], e[37]], [e[38], e[39]], [e[40], e[41]], [e[42], e[43]], e[44], e[45], e[46], e[47], e[48], e[49], e[50]);
		register_instance (e[7], e[7]);
		run_init_scripts (e[7]);
		i ++;
	}
	else if (l > 6)
	{
		if (templateIdSet[e[0]])
			continue;
		add_radial_gradient (e[0], [e[1], e[2]], e[3], e[4], c[e[5]], c[e[6]], c[e[7]], e[8], e[9]);
		register_instance (e[0], e[0]);
		run_init_scripts (e[0]);
	}
	else if (Array.isArray(e[3]))
	{
		if (!templateIdSet[e[0]])
			g.push(e);
	}
	else if (l > 5)
	{
		if (!templateIdSet[e[1]] && !templateIdSet[e[0]])
			copies.push(e);
	}
	else if (!templateIdSet[e[0]])
		g.push(e);
}
var childParent = build_child_parent_map(g);
var pendingGroups = g.slice();
var pendingCopies = copies.slice();
var runtimeSafety = pendingGroups.length + pendingCopies.length + 1;
while ((pendingGroups.length > 0 || pendingCopies.length > 0) && runtimeSafety > 0)
{
	runtimeSafety --;
	var progressed = false;
	for (var idx = pendingCopies.length - 1; idx >= 0; idx --)
	{
		var e = pendingCopies[idx];
		var parentId = childParent[e[1]] || null;
		if (!document.getElementById(e[0]))
			continue;
		copy_node (e[0], e[1], [e[2], e[3]], e[4], e[5], parentId);
		register_instance (e[0], e[1]);
		run_init_scripts (e[1]);
		pendingCopies.splice(idx, 1);
		progressed = true;
	}
	for (var idx = pendingGroups.length - 1; idx >= 0; idx --)
	{
		var e = pendingGroups[idx];
		if (!children_ready(e[3]))
			continue;
		add_div (e[0], [e[1], e[2]], e[3], e[4], '', e[5] || 0);
		register_instance (e[0], e[0]);
		run_init_scripts (e[0]);
		pendingGroups.splice(idx, 1);
		progressed = true;
	}
	if (!progressed)
		break;
}
for (var e of pendingGroups)
{
	add_div (e[0], [e[1], e[2]], e[3], e[4], '', e[5] || 0);
	register_instance (e[0], e[0]);
	run_init_scripts (e[0]);
}
for (var e of pendingCopies)
{
	var parentId = childParent[e[1]] || null;
	copy_node (e[0], e[1], [e[2], e[3]], e[4], e[5], parentId);
	register_instance (e[0], e[1]);
	run_init_scripts (e[1]);
}
// Init
main ()
'''
JS = '''
var svgNS = 'http://www.w3.org/2000/svg';
var sceneNodeOrder = 0;
function to_z_index (zIdx)
{
	var z = Number(zIdx);
	if (!Number.isFinite(z))
		return 0;
	return Math.round(z);
}
globalThis.to_z_index = to_z_index;
function has_explicit_z_index (node)
{
	var z = (node.style && node.style.zIndex != null) ? String(node.style.zIndex).trim() : '';
	return z != '' && z.toLowerCase() != 'auto';
}
globalThis.has_explicit_z_index = has_explicit_z_index;
function get_effective_z_index (node)
{
	if (!node)
		return 0;
	if (has_explicit_z_index(node))
		return to_z_index(node.style.zIndex);
	var inferred = null;
	if (node.children)
	{
		for (var child of node.children)
		{
			var childZ = get_effective_z_index(child);
			if (inferred == null || childZ < inferred)
				inferred = childZ;
		}
	}
	if (inferred == null)
		inferred = 0;
	node.dataset.inferredZIndex = String(inferred);
	return inferred;
}
globalThis.get_effective_z_index = get_effective_z_index;
function apply_z_index (node, zIdx)
{
	var z = to_z_index(zIdx);
	node.style.zIndex = String(z);
	node.dataset.zIndex = String(z);
	if (!node.dataset.sceneNodeOrder)
	{
		node.dataset.sceneNodeOrder = String(sceneNodeOrder);
		sceneNodeOrder ++;
	}
}
globalThis.apply_z_index = apply_z_index;
function append_to_scene (node, parent = null, reorderAncestors = true)
{
	if (!node.dataset.sceneNodeOrder)
	{
		node.dataset.sceneNodeOrder = String(sceneNodeOrder);
		sceneNodeOrder ++;
	}
	var targetParent = parent || document.body;
	var nodeZ = get_effective_z_index(node);
	var nodeOrder = Number(node.dataset.sceneNodeOrder || 0);
	var insertBefore = null;
	for (var child of targetParent.children)
	{
		if (child == node)
			continue;
		if (!child.dataset.sceneNodeOrder)
		{
			child.dataset.sceneNodeOrder = String(sceneNodeOrder);
			sceneNodeOrder ++;
		}
		var childZ = get_effective_z_index(child);
		var childOrder = Number(child.dataset.sceneNodeOrder || 0);
		if (childZ > nodeZ || (childZ == nodeZ && childOrder > nodeOrder))
		{
			insertBefore = child;
			break;
		}
	}
	targetParent.insertBefore(node, insertBefore);
	if (reorderAncestors && targetParent !== document.body && targetParent.parentElement)
		append_to_scene (targetParent, targetParent.parentElement, true);
}
globalThis.append_to_scene = append_to_scene;
function ang (from, to)
{
	return Math.acos(dot(normalize(from), normalize(to))) * (180 / Math.PI);
}
globalThis.ang = ang;
function signed_ang (from, to)
{
	return ang(from, to) * Math.sign(from[0] * to[1] - from[1] * to[0]);
}
globalThis.signed_ang = signed_ang;
function rotate (v, ang)
{
	ang /= 180 / Math.PI;
	ang += Math.atan2(v[1], v[0]);
	var mag = magnitude(v);
	return [Math.cos(ang) * mag, Math.sin(ang) * mag];
}
globalThis.rotate = rotate;
function rotate_to (from, to, maxAng)
{
	return rotate(from, clamp(signed_ang(from, to), -maxAng, maxAng));
}
globalThis.rotate_to = rotate_to;
function lerp (min, max, t)
{
	return min + t * (max - min);
}
globalThis.lerp = lerp;
function clamp (n, min, max)
{
	return Math.min(Math.max(n, min), max);
}
globalThis.clamp = clamp;
function inv_lerp (from, to, n)
{
	return (n - from) / (to - from);
}
globalThis.inv_lerp = inv_lerp;
function remap (inFrom, inTo, outFrom, outTo, n)
{
	return lerp(outFrom, outTo, inv_lerp(inFrom, inTo, n));
}
globalThis.remap = remap;
function ang_to_dir (ang)
{
	ang *= Math.PI / 180;
	return new RAPIER.Vector2(Math.cos(ang), Math.sin(ang));
}
globalThis.ang_to_dir = ang_to_dir;
function random_vector (maxDist)
{
	var dist = random(0, maxDist);
	var ang = random(0, 2 * Math.PI);
	var dir = ang_to_dir(ang);
	return new RAPIER.Vector2(dir.x * dist, dir.y * dist);
}
globalThis.random_vector = random_vector;
function magnitude (v)
{
	return Math.sqrt(v.x * v.x + v.y * v.y);
}
globalThis.magnitude = magnitude;
function normalize (v)
{
	return divide_scaler(v, magnitude(v));
}
globalThis.normalize = normalize;
function multiply (v, v2)
{
	return new RAPIER.Vector2(v.x * v2.x, v.y * v2.y);
}
globalThis.multiply = multiply;
function multiply_scaler (v, f)
{
	return new RAPIER.Vector2(v.x * f, v.y * f);
}
globalThis.multiply_scaler = multiply_scaler;
function divide_scaler (v, f)
{
	return new RAPIER.Vector2(v.x / f, v.y / f);
}
globalThis.divide_scaler = divide_scaler;
function divide (v, v2)
{
	return new RAPIER.Vector2(v.x / v2.x, v.y / v2.y);
}
globalThis.divide = divide;
function add (v, v2)
{
	return new RAPIER.Vector2(v.x + v2.x, v.y + v2.y);
}
globalThis.add = add;
function subtract (v, v2)
{
	return new RAPIER.Vector2(v.x - v2.x, v.y - v2.y);
}
globalThis.subtract = subtract;
function distance (v, v2)
{
	return magnitude(subtract(v, v2));
}
globalThis.distance = distance;
function random (min, max)
{
	return Math.random() * (max - min) + min;
}
globalThis.random = random;
function add_div (id, pos, childIds = [], attributes = {}, txt = '', rot = 0)
{
	var group = document.createElement('div');
	group.id = id;
	group.style.position = 'absolute';
	group.style.transform = 'translate(' + pos[0] + 'px, ' + pos[1] + 'px)';
	if (rot != 0)
		group.style.transform += ' rotate(' + rot + 'deg)';
	group.innerHTML = txt;
	for (var [key, val] of Object.entries(attributes))
		group.setAttribute(key, val);
	append_to_scene (group);
	for (var childId of childIds)
	{
		var node = document.getElementById(childId);
		node.style.position = 'absolute';
		append_to_scene (node, group);
	}
	return group;
}
globalThis.add_div = add_div;
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
globalThis.shuffle = shuffle;
'''
PHYSICS = '''
import RAPIER from 'https://cdn.jsdelivr.net/npm/@dimforge/rapier2d-compat/+esm';

// Vars
var rigidBodiesIds = globalThis.rigidBodiesIds || {};
var rigidBodyDescsIds = globalThis.rigidBodyDescsIds || {};
var collidersIds = globalThis.collidersIds || {};
var colliderOffsetsIds = globalThis.colliderOffsetsIds || {};
globalThis.rigidBodiesIds = rigidBodiesIds;
globalThis.rigidBodyDescsIds = rigidBodyDescsIds;
globalThis.collidersIds = collidersIds;
globalThis.colliderOffsetsIds = colliderOffsetsIds;
globalThis.RAPIER = RAPIER;
await RAPIER.init().then(() => {
	// Gravity
	globalThis.world = new RAPIER.World(gravity);
	globalThis.eventQueue = new RAPIER.EventQueue(true);
	// Settings
	// Rigid Bodies
	// Colliders
	// Joints
	// Char Controllers
});
'''
JS_API = '''
var liveInstanceIds = new Set();
var instanceToTemplate = {};
var scripts = {};
var scriptScopes = {};
var _currentInstanceId = null;
var pendingPhysicsCopies = [];
var visualOffsetsIds = globalThis.visualOffsetsIds || {};
globalThis.visualOffsetsIds = visualOffsetsIds;
function register_instance (templateId, instanceId)
{
	liveInstanceIds.add(instanceId);
	instanceToTemplate[instanceId] = templateId;
}
globalThis.register_instance = register_instance;
function unregister_instance (instanceId)
{
	liveInstanceIds.delete(instanceId);
	delete instanceToTemplate[instanceId];
	delete scriptScopes[instanceId];
}
globalThis.unregister_instance = unregister_instance;
function _prepare_script (code)
{
	return code
		.replace(/(^|[^\\w])(new\\s+)?globalThis\\.RAPIER\\.Vector2\\s*\\(/g, function (_, prefix, hasNew)
		{
			return prefix + (hasNew ? '' : 'new ') + 'globalThis.RAPIER.Vector2(';
		})
		.replace(/(^|[^\\w])(new\\s+)?RAPIER\\.Vector2\\s*\\(/g, function (_, prefix, hasNew)
		{
			return prefix + (hasNew ? '' : 'new ') + 'RAPIER.Vector2(';
		})
		.replace(/([A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*|\\[[^\\]]+\\])*)\\.items\\s*\\(\\)/g, 'Object.entries($1)')
		.replace(/^async function\\s+([A-Za-z_$][\\w$]*)\\s*\\(([^)]*)\\)\\s*\\{/gm, '_scope.$1 = async ($2) => {')
		.replace(/^function\\s+([A-Za-z_$][\\w$]*)\\s*\\(([^)]*)\\)\\s*\\{/gm, '_scope.$1 = ($2) => {');
}
globalThis._prepare_script = _prepare_script;
function _exec_script (instanceId, code, phase)
{
	var el = document.getElementById(instanceId);
	if (!el)
		return;
	if (!scriptScopes[instanceId])
		scriptScopes[instanceId] = {};
	var scope = scriptScopes[instanceId];
	scope.this = el;
	scope._currentInstanceId = instanceId;
	var prepared = _prepare_script(code);
	try
	{
		(new Function('_scope', '_api', '_currentInstanceId', 'with (_api) {\\nwith (_scope) {\\n' + prepared + '\\n}\\n}')).call(el, scope, globalThis, instanceId);
	}
	catch (err)
	{
		console.error('[script:' + phase + '] ' + instanceId, err);
	}
}
globalThis._exec_script = _exec_script;
function run_init_scripts (instanceId)
{
	var tid = instanceToTemplate[instanceId];
	var templateScriptSet = typeof templateScripts !== 'undefined' && templateScripts && templateScripts[tid];
	if (templateScriptSet && templateScriptSet.init)
	{
		_currentInstanceId = instanceId;
		for (var i = 0; i < templateScriptSet.init.length; i ++)
			_exec_script(instanceId, templateScriptSet.init[i], 'init');
		_currentInstanceId = null;
	}
	var rt = (typeof scripts === 'object' && scripts) ? scripts[instanceId] : null;
	if (rt && rt.init)
		for (var i = 0; i < rt.init.length; i ++)
			_exec_script(instanceId, rt.init[i], 'init');
}
globalThis.run_init_scripts = run_init_scripts;
function run_update_scripts ()
{
	liveInstanceIds.forEach(function (id)
	{
		var tid = instanceToTemplate[id];
		var templateScriptSet = typeof templateScripts !== 'undefined' && templateScripts && templateScripts[tid];
		if (templateScriptSet && templateScriptSet.update)
		{
			_currentInstanceId = id;
			for (var i = 0; i < templateScriptSet.update.length; i ++)
				_exec_script(id, templateScriptSet.update[i], 'update');
			_currentInstanceId = null;
		}
		var rt = (typeof scripts === 'object' && scripts) ? scripts[id] : null;
		if (rt && rt.update)
			for (var i = 0; i < rt.update.length; i ++)
				_exec_script(id, rt.update[i], 'update');
	});
}
globalThis.run_update_scripts = run_update_scripts;
function add_script (instanceId, code, type)
{
	if (!scripts[instanceId])
		scripts[instanceId] = { init: [], update: [] };
	scripts[instanceId][type].push(code);
	if (type === 'init')
	{
		_currentInstanceId = instanceId;
		_exec_script(instanceId, code, 'init');
		_currentInstanceId = null;
	}
}
globalThis.add_script = add_script;
function remove_script (instanceId, type, index)
{
	if (scripts[instanceId] && scripts[instanceId][type])
		scripts[instanceId][type].splice(index, 1);
}
globalThis.remove_script = remove_script;
function get_svg_paths_and_strings (framesStrings, cyclic)
{
	var pathsVals = [];
	var pathsStrings = [];
	var i = 0;
	var pathMode = 'compressed';
	for (var frameStr of framesStrings)
	{
		if (frameStr.length > 0 && frameStr.charCodeAt(0) == 2)
		{
			pathMode = 'raw';
			frameStr = frameStr.slice(1);
		}
		if (i == 0)
			var prevPathStr = frameStr;
		else if (pathMode == 'compressed')
			for (var i2 = 0; i2 < frameStr.length; i2 += 2)
			{
				var idx = frameStr.charCodeAt(i2) - 32;
				prevPathStr = prevPathStr.slice(0, idx) + String.fromCharCode(prevPathStr.charCodeAt(idx) + frameStr.charCodeAt(i2 + 1) - 160) + prevPathStr.slice(idx + 1);
			}
		else
			prevPathStr = frameStr;
		if (pathMode == 'compressed')
			pathsVals.push(get_svg_path(prevPathStr, cyclic));
		else
			pathsVals.push(prevPathStr);
		pathsStrings.push(prevPathStr);
		i ++;
	}
	return [pathsVals, pathsStrings, pathMode];
}
globalThis.get_svg_paths_and_strings = get_svg_paths_and_strings;
function get_svg_path (pathStr, cyclic)
{
	var output = 'M ' + pathStr.charCodeAt(0) + ', ' + pathStr.charCodeAt(1) + ' ';
	var i = 2;
	while (i < pathStr.length)
	{
		if ((i - 2) % 6 == 0 && i + 6 <= pathStr.length)
		{
			output += 'C ';
			output += pathStr.charCodeAt(i) + ', ' + pathStr.charCodeAt(i + 1) + ' ' + pathStr.charCodeAt(i + 2) + ', ' + pathStr.charCodeAt(i + 3) + ' ' + pathStr.charCodeAt(i + 4) + ', ' + pathStr.charCodeAt(i + 5) + ' ';
			i += 6;
		}
		else if (i + 2 <= pathStr.length)
		{
			output += 'L ' + pathStr.charCodeAt(i) + ', ' + pathStr.charCodeAt(i + 1) + ' ';
			i += 2;
		}
		else
			break;
	}
	if (cyclic)
		output += 'Z';
	return output;
}
globalThis.get_svg_path = get_svg_path;
function get_local_transform (node)
{
	var trs = '';
	if (node && node.style && node.style.transform)
		trs = node.style.transform;
	else if (node && node.getAttribute)
		trs = node.getAttribute('transform') || '';
	var tx = 0;
	var ty = 0;
	var rz = 0;
	var tm = trs.match(/translate\\(\\s*([\\-\\d.]+(?:e[-+]?\\d+)?)(?:px)?\\s*,\\s*([\\-\\d.]+(?:e[-+]?\\d+)?)(?:px)?\\s*\\)/i);
	if (tm)
	{
		tx = parseFloat(tm[1]);
		ty = parseFloat(tm[2]);
	}
	var rm = trs.match(/rotate\\(\\s*([\\-\\d.]+(?:e[-+]?\\d+)?)\\s*(deg|rad)?\\s*\\)/i);
	if (rm)
	{
		rz = parseFloat(rm[1]);
		if (!rm[2] || rm[2] == 'deg')
			rz *= Math.PI / 180;
	}
	return {x : tx, y : ty, rot : rz};
}
globalThis.get_local_transform = get_local_transform;
function get_world_transform (node)
{
	var chain = [];
	var curr = node;
	while (curr && curr !== document.body)
	{
		chain.push(curr);
		curr = curr.parentElement;
	}
	chain.reverse();
	var world = {x : 0, y : 0, rot : 0};
	for (var n of chain)
	{
		var local = get_local_transform(n);
		var dx = local.x * Math.cos(world.rot) - local.y * Math.sin(world.rot);
		var dy = local.x * Math.sin(world.rot) + local.y * Math.cos(world.rot);
		world.x += dx;
		world.y += dy;
		world.rot += local.rot;
	}
	return world;
}
globalThis.get_world_transform = get_world_transform;
function clone_node_physics (id, newId, worldTrs)
{
	function get_rigidbody_ancestor (node)
	{
		var curr = node ? node.parentElement : null;
		while (curr && curr !== document.body)
		{
			if (rigidBodiesIds[curr.id])
				return rigidBodiesIds[curr.id];
			curr = curr.parentElement;
		}
		return null;
	}
	var world = globalThis.world;
	if (!world)
		return false;
	if (rigidBodiesIds[newId] || collidersIds[newId])
		return true;
	var rigidBody = rigidBodiesIds[id];
	var collider = collidersIds[id];
	if (!rigidBody && !collider)
		return false;
	var srcNode = document.getElementById(id);
	var srcWorld = srcNode ? get_world_transform(srcNode) : {x : 0, y : 0, rot : 0};
	var baseOff = colliderOffsetsIds[id] || [0, 0];
	var colliders = [];
	if (rigidBody)
	{
		rigidBodiesIds[newId] = world.createRigidBody(new RAPIER.RigidBodyDesc(rigidBody.bodyType()).setAngularDamping(rigidBody.angularDamping()).setCanSleep(rigidBodyDescsIds[id].canSleep).setCcdEnabled(rigidBody.isCcdEnabled()).setDominanceGroup(rigidBody.dominanceGroup()).setEnabled(rigidBody.isEnabled()).setGravityScale(rigidBody.gravityScale()).setLinearDamping(rigidBody.linearDamping()).lockRotations(rigidBody.lockRotations()).setRotation(worldTrs.rot).setTranslation(worldTrs.x, worldTrs.y));
		for (var i = 0; i < rigidBody.numColliders(); i ++)
			colliders.push(rigidBody.collider(i));
	}
	if (collider)
	{
		var activeEvents = typeof collider.activeEvents == 'function' ? collider.activeEvents() : collider.activeEvents;
		var collisionGroups = typeof collider.collisionGroups == 'function' ? collider.collisionGroups() : collider.collisionGroups;
		var density = typeof collider.density == 'function' ? collider.density() : collider.density;
		var enabled = typeof collider.isEnabled == 'function' ? collider.isEnabled() : collider.enabled;
		var sensor = typeof collider.isSensor == 'function' ? collider.isSensor() : false;
		var newColliderDesc;
		var newNode = document.getElementById(newId);
		var parentRigidBody = (!rigidBody && newNode) ? get_rigidbody_ancestor(newNode) : null;
		if (rigidBody)
		{
			// For attached colliders, translation/rotation are body-local.
			var localRot = collider.rotation();
			if (typeof rigidBody.rotation == 'function')
				localRot -= rigidBody.rotation();
			newColliderDesc = new RAPIER.ColliderDesc(collider.shape).setRotation(localRot).setTranslation(baseOff[0], baseOff[1]);
			collider = world.createCollider(newColliderDesc, rigidBodiesIds[newId]);
		}
		else if (parentRigidBody)
		{
			var worldRot = collider.rotation();
			var rotDelta = worldRot - srcWorld.rot;
			var targetWorldRot = worldTrs.rot + rotDelta;
			var targetWorldX = worldTrs.x + baseOff[0];
			var targetWorldY = worldTrs.y + baseOff[1];
			var bodyPos = parentRigidBody.translation();
			var bodyRot = typeof parentRigidBody.rotation == 'function' ? parentRigidBody.rotation() : 0;
			var dx = targetWorldX - bodyPos.x;
			var dy = targetWorldY - bodyPos.y;
			var cos = Math.cos(-bodyRot);
			var sin = Math.sin(-bodyRot);
			var localX = dx * cos - dy * sin;
			var localY = dx * sin + dy * cos;
			newColliderDesc = new RAPIER.ColliderDesc(collider.shape).setRotation(targetWorldRot - bodyRot).setTranslation(localX, localY);
			collider = world.createCollider(newColliderDesc, parentRigidBody);
		}
		else
		{
			var worldRot = collider.rotation();
			var rotDelta = worldRot - srcWorld.rot;
			var tx = worldTrs.x + baseOff[0];
			var ty = worldTrs.y + baseOff[1];
			newColliderDesc = new RAPIER.ColliderDesc(collider.shape).setRotation(worldTrs.rot + rotDelta).setTranslation(tx, ty);
			collider = world.createCollider(newColliderDesc);
		}
		if (activeEvents !== undefined && activeEvents !== null)
			collider.setActiveEvents(activeEvents);
		if (collisionGroups !== undefined && collisionGroups !== null && !Number.isNaN(Number(collisionGroups)))
			collider.setCollisionGroups(Number(collisionGroups));
		if (density !== undefined && density !== null && !Number.isNaN(Number(density)))
			collider.setDensity(Number(density));
		if (enabled !== undefined && enabled !== null)
			collider.setEnabled(!!enabled);
		if (sensor)
			collider.setSensor(true);
		collidersIds[newId] = collider;
		colliderOffsetsIds[newId] = colliderOffsetsIds[id] || [0, 0];
		colliders.push(collider);
	}
	return true;
}
globalThis.clone_node_physics = clone_node_physics;
function resolve_pending_physics_copies ()
{
	if (!globalThis.world || pendingPhysicsCopies.length == 0)
		return;
	for (var i = pendingPhysicsCopies.length - 1; i >= 0; i --)
	{
		var p = pendingPhysicsCopies[i];
		var node = document.getElementById(p.newId);
		if (!node)
		{
			pendingPhysicsCopies.splice(i, 1);
			continue;
		}
		var worldTrs = get_world_transform(node);
		if (clone_node_physics(p.id, p.newId, worldTrs))
			pendingPhysicsCopies.splice(i, 1);
	}
}
globalThis.resolve_pending_physics_copies = resolve_pending_physics_copies;
function copy_node (id, newId, pos, rot = 0, attributes = {}, parentId = null, useTemplateTransform = true)
{
	var copy = document.getElementById(id).cloneNode(true);
	copy.id = newId;
	copy.style.visibility = 'visible';
	copy.style.x = pos[0];
	copy.style.y = pos[1];
	var base = {x : 0, y : 0, rot : 0};
	if (useTemplateTransform)
		base = get_local_transform(copy);
	var existingTransform = copy.style.transform || '';
	var extraTransforms = existingTransform
		.replace(/translate\\(\\s*[\\-\\d.]+(?:e[-+]?\\d+)?(?:px)?\\s*,\\s*[\\-\\d.]+(?:e[-+]?\\d+)?(?:px)?\\s*\\)/gi, '')
		.replace(/rotate\\(\\s*[\\-\\d.]+(?:e[-+]?\\d+)?\\s*(?:deg|rad)?\\s*\\)/gi, '')
		.trim();
	var tx = base.x + pos[0];
	var ty = base.y + pos[1];
	var rz = base.rot + rot * (Math.PI / 180);
	var transformTxt = 'translate(' + tx + 'px, ' + ty + 'px) rotate(' + rz + 'rad)' + (extraTransforms ? ' ' + extraTransforms : '');
	copy.style.transform = transformTxt;
	if (copy.tagName && copy.tagName.toLowerCase() == 'svg')
		copy.setAttribute('transform', 'translate(' + tx + ', ' + ty + ') rotate(' + (rz * (180 / Math.PI)) + ')');
	for (var [key, val] of Object.entries(attributes))
		copy.setAttribute(key, val);
	var parent = null;
	if (parentId)
		parent = document.getElementById(parentId);
	var deferPhysics = parentId && !parent;
	if (parent)
		append_to_scene (copy, parent);
	else
		append_to_scene (copy);
	var worldTrs = get_world_transform(copy);
	var colliders = [];
	var hadPhysics = false;
	if (!deferPhysics)
		hadPhysics = clone_node_physics(id, newId, worldTrs);
	if (!hadPhysics)
		pendingPhysicsCopies.push({id : id, newId : newId});
	return [copy, colliders];
}
globalThis.copy_node = copy_node;
function add_radial_gradient (id, pos, zIdx, diameter, clr, clr2, clr3, clrPositions, subtractive)
{
	var group = document.createElementNS(svgNS, 'g');
	group.id = id;
	group.style.x = pos[0];
	group.style.y = pos[1];
	group.style.position = 'absolute';
	group.style.left = (pos[0] + diameter / 2) + 'px';
	group.style.top = (pos[1] + diameter / 2) + 'px';
	group.style.backgroundImage = 'radial-gradient(rgba(' + clr[0] + ', ' + clr[1] + ', ' + clr[2] + ', ' + clr[3] + ') ' + clrPositions[0] + '%, rgba(' + clr2[0] + ', ' + clr2[1] + ', ' + clr2[2] + ', ' + clr2[3] + ') ' + clrPositions[1] + '%, rgba(' + clr3[0] + ', ' + clr3[1] + ', ' + clr3[2] + ', ' + clr3[3] + ') ' + clrPositions[2] + '%)';
	group.style.width = diameter + 'px';
	group.style.height = diameter + 'px';
	apply_z_index (group, zIdx);
	var mixMode = 'lighter';
	if (subtractive)
		mixMode = 'darker';
	group.style.mixBlendMode = 'plus-' + mixMode;
	append_to_scene (group);
}
globalThis.add_radial_gradient = add_radial_gradient;
function add_svg (positions, posPingPong, size, fillClr, lineWidth, lineClr, id, pathFramesStrings, cyclic, zIdx, attributes, jiggleDist, jiggleDur, jiggleFrames, rotAngRange, rotDur, rotPingPong, scaleXRange, scaleYRange, scaleDur, scaleHaltDurAtMin, scaleHaltDurAtMax, scalePingPong, pivot, fillHatchDensity, fillHatchRandDensity, fillHatchAng, fillHatchWidth, lineHatchDensity, lineHatchRandDensity, lineHatchAng, lineHatchWidth, mirrorX, mirrorY, capType, joinType, dashArr, cycleDur)
{
	var fillClrTxt = 'rgb(' + fillClr[0] + ' ' + fillClr[1] + ' ' + fillClr[2] + ')';
	var lineClrTxt = 'rgb(' + lineClr[0] + ' ' + lineClr[1] + ' ' + lineClr[2] + ')';
	var pos = positions[0];
	var svg = document.createElementNS(svgNS, 'svg');
	svg.style.fillOpacity = fillClr[3] / 255;
	svg.id = id;
	apply_z_index (svg, zIdx);
	svg.style.position = 'absolute';
	svg.style.transformOrigin = pivot[0] + '% ' + pivot[1] + '%';
	svg.style.x = pos[0];
	svg.style.y = pos[1];
	svg.style.width = size[0];
	svg.style.height = size[1];
	var trs = 'translate(' + pos[0] + ', ' + pos[1] + ')';
	svg.setAttribute('transform', trs);
	var i = 0;
	var pathsValsAndStrings = get_svg_paths_and_strings(pathFramesStrings, cyclic);
	var pathMode = pathsValsAndStrings[2];
	var anim;
	var frames;
	var firstFrame = '';
	for (var pathVals of pathsValsAndStrings[0])
	{
		var path = document.createElementNS(svgNS, 'path');
		if (i > 0)
			path.style.opacity = 0;
		path.style.fill = fillClrTxt;
		path.style.strokeWidth = lineWidth;
		path.style.stroke = lineClrTxt;
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
				if (pathMode == 'compressed')
				{
					for (var i3 = 0; i3 < pathVals.length; i3 += 2)
					{
						off = normalize(random_vector(1));
						off = [off[0] * jiggleDist, off[1] * jiggleDist];
						pathVals = pathVals.slice(0, i3) + String.fromCharCode(pathVals.charCodeAt(i3) + off[0]) + String.fromCharCode(pathVals.charCodeAt(i3 + 1) + off[1]) + pathVals.slice(i3 + 2);
					}
					pathVals = get_svg_path(pathVals, cyclic);
				}
				else
				{
					var coordIdx = 0;
					var jiggleOff = [0, 0];
					var numPattern = /-?\\d*\\.?\\d+(?:e[-+]?\\d+)?/ig;
					pathVals = pathVals.replace(numPattern, function (match)
					{
						if (coordIdx % 2 == 0)
						{
							jiggleOff = normalize(random_vector(1));
							jiggleOff = [jiggleOff[0] * jiggleDist, jiggleOff[1] * jiggleDist];
						}
						var output = parseFloat(match) + jiggleOff[coordIdx % 2];
						coordIdx ++;
						return output;
					});
				}
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
	append_to_scene (svg);
	var off = lineWidth / 2 + jiggleDist;
	var min = 32 - off;
	svg.style.viewbox = min + ' ' + min + ' ' + (size[0] + off * 2) + ' ' + (size[1] + off * 2);
	path = svg.children[0];
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
		svg.appendChild(anim);
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
		svg.appendChild(anim);
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
	path.remove();
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
			hatch ('_' + id, ...args, fillHatchDensity[0], fillHatchRandDensity[0], fillHatchAng[0], fillHatchWidth[0]);
		if (fillHatchDensity[1] > 0)
			hatch ('|' + id, ...args, fillHatchDensity[1], fillHatchRandDensity[1], fillHatchAng[1], fillHatchWidth[1]);
		lineClr[3] = 255;
	}
	if (magnitude(lineHatchDensity) > 0)
	{
		var args = [lineClr, false, svg, path]; 
		if (lineHatchDensity[0] > 0)
			hatch ('@' + id, ...args, lineHatchDensity[0], lineHatchRandDensity[0], lineHatchAng[0], lineHatchWidth[0]);
		if (lineHatchDensity[1] > 0)
			hatch ('$' + id, ...args, lineHatchDensity[1], lineHatchRandDensity[1], lineHatchAng[1], lineHatchWidth[1]);
		lineClr[3] = 255;
	}
	svg.style.strokeOpacity = lineClr[3] / 255;
	if (mirrorX)
	{
		svg = copy_node(id, '~' + id, pos)[0];
		svg.style.transform = trs + 'scale(-1,1)';
		svg.style.transformOrigin = 50 - (pivot[0] - 50) + '% ' + pivot[1] + '%';
	}
	if (mirrorY)
	{
		svg = copy_node(id, '`' + id, pos)[0];
		svg.style.transform = trs + 'scale(1,-1)';
		svg.style.transformOrigin = pivot[0] + '% ' + (50 - (pivot[1] - 50)) + '%';
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
globalThis.add_svg = add_svg;
function hatch (id, clr, useFIll, svg, path, density, randDensity, ang, width)
{
	var luminance = (.2126 * clr[0] + .7152 * clr[1] + .0722 * clr[2]) / 255;
	var pattern = document.createElementNS(svgNS, 'pattern');
	pattern.id = id;
	pattern.style = 'transform:rotate(' + ang + 'deg)';
	pattern.style.width = '100%';
	pattern.style.height = '100%';
	pattern.style.patternUnits = 'userSpaceOnUse';
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
	path.style.strokeWidth = width * (1 - luminance);
	path.style.stroke = 'black';
	pattern.appendChild(path);
	svg.appendChild(pattern);
	path = path.cloneNode(true);
	if (useFIll)
		path.style.fill = 'url(#' + id + ')';
	else
		path.style.stroke = 'url(#' + id + ')';
	svg.appendChild(path);
}
globalThis.hatch = hatch;
// Physics Section Start
function set_transforms (dict)
{
	function has_rigidbody_ancestor (node)
	{
		var curr = node ? node.parentElement : null;
		while (curr && curr !== document.body)
		{
			if (rigidBodiesIds[curr.id])
				return true;
			curr = curr.parentElement;
		}
		return false;
	}
	for (var [key, val] of Object.entries(dict))
	{
		if (dict === collidersIds && rigidBodiesIds[key])
			continue;
		var node = document.getElementById(key);
		if (!node)
			continue;
		if (dict === collidersIds && has_rigidbody_ancestor(node))
			continue;
		var pos = val.translation();
		var localVisualOffset = null;
		if (dict === collidersIds)
		{
			var colliderOff = colliderOffsetsIds[key];
			if (colliderOff)
			{
				pos.x -= colliderOff[0];
				pos.y -= colliderOff[1];
			}
			if (!visualOffsetsIds[key])
			{
				var authoredWorld = get_world_transform(node);
				var dx = authoredWorld.x - pos.x;
				var dy = authoredWorld.y - pos.y;
				var initialRot = val.rotation();
				var c0 = Math.cos(initialRot);
				var s0 = Math.sin(initialRot);
				visualOffsetsIds[key] = [dx * c0 + dy * s0, -dx * s0 + dy * c0];
			}
			localVisualOffset = visualOffsetsIds[key];
		}
		var rect = node.getBoundingClientRect();
		var nodeWidth = 0;
		var nodeHeight = 0;
		if (node.tagName && node.tagName.toLowerCase() == 'svg')
		{
			nodeWidth = parseFloat(node.style.width) || 0;
			nodeHeight = parseFloat(node.style.height) || 0;
		}
		else if (node.tagName && node.tagName.toLowerCase() == 'img')
		{
			nodeWidth = node.width || node.naturalWidth || 0;
			nodeHeight = node.height || node.naturalHeight || 0;
		}
		if (!nodeWidth || !nodeHeight)
		{
			nodeWidth = node.offsetWidth || node.clientWidth || rect.width;
			nodeHeight = node.offsetHeight || node.clientHeight || rect.height;
		}
		var pivotX = 0.5;
		var pivotY = 0.5;
		if (nodeWidth > 0 && nodeHeight > 0)
		{
			var transformOrigin = (window.getComputedStyle(node).transformOrigin || '').trim();
			var o = transformOrigin.match(/^([\\-.\\d]+)px\\s+([\\-.\\d]+)px/);
			if (o)
			{
				pivotX = parseFloat(o[1]) / nodeWidth;
				pivotY = parseFloat(o[2]) / nodeHeight;
			}
		}
		var posX = pos.x - nodeWidth * pivotX;
		var posY = pos.y - nodeHeight * pivotY;
		if (dict === collidersIds && localVisualOffset)
		{
			var r = val.rotation();
			var cr = Math.cos(r);
			var sr = Math.sin(r);
			posX = pos.x + localVisualOffset[0] * cr - localVisualOffset[1] * sr;
			posY = pos.y + localVisualOffset[0] * sr + localVisualOffset[1] * cr;
		}
		var parent = node.parentElement;
		var parentWorld = {x : 0, y : 0, rot : 0};
		if (parent && parent !== document.body)
		{
			parentWorld = get_world_transform(parent);
			posX -= parentWorld.x;
			posY -= parentWorld.y;
			var cos = Math.cos(-parentWorld.rot);
			var sin = Math.sin(-parentWorld.rot);
			var lx = posX * cos - posY * sin;
			var ly = posX * sin + posY * cos;
			posX = lx;
			posY = ly;
		}
		var localRot = val.rotation();
		if (parent && parent !== document.body)
			localRot -= parentWorld.rot;
		var existingTransform = node.style.transform || '';
		var extraTransforms = existingTransform
			.replace(/translate\\(\\s*[\\-\\d.]+(?:e[-+]?\\d+)?(?:px)?\\s*,\\s*[\\-\\d.]+(?:e[-+]?\\d+)?(?:px)?\\s*\\)/gi, '')
			.replace(/rotate\\(\\s*[\\-\\d.]+(?:e[-+]?\\d+)?\\s*(?:deg|rad)?\\s*\\)/gi, '')
			.trim();
		node.style.transform = 'translate(' + posX + 'px,' + posY + 'px) rotate(' + localRot + 'rad)' + (extraTransforms ? ' ' + extraTransforms : '');
	}
}
globalThis.set_transforms = set_transforms;
function spawn_prefab (prefabName, instanceId, pos, rot = 0, attributeOverrides = {})
{
	var defn = prefabs[prefabName];
	if (!defn)
		return null;
	var roots = defn.roots;
	var nodes = defn.nodes;
	function spawnNode (templateId, newId, localPos, localRot, parentNode = null)
	{
		var atts = attributeOverrides[templateId] || {};
		var result = copy_node(templateId, newId, localPos, localRot, atts, parentNode ? parentNode.id : null, false);
		register_instance (templateId, newId);
		var spawnedNode = result && result[0] ? result[0] : null;
		var nodeDef = nodes[templateId];
		if (nodeDef && spawnedNode)
		{
			var childIds = nodeDef.children;
			if (childIds && childIds.length > 0)
			{
				var childTemplateIds = {};
				for (var c = 0; c < childIds.length; c ++)
					childTemplateIds[childIds[c]] = true;
				for (var c = spawnedNode.children.length - 1; c >= 0; c --)
				{
					var existingChild = spawnedNode.children[c];
					if (childTemplateIds[existingChild.id])
						existingChild.remove();
				}
			}
			for (var i = 0; i < childIds.length; i ++)
			{
				var childTemplateId = childIds[i];
				var childDef = nodes[childTemplateId];
				if (!childDef)
					continue;
				var childNewId = instanceId + '_' + childTemplateId;
				spawnNode (childTemplateId, childNewId, childDef.localPos, childDef.localRot, spawnedNode);
			}
		}
		run_init_scripts (newId);
		return result;
	}
	var rootWorld = [pos && pos.x != null ? pos.x : 0, pos && pos.y != null ? pos.y : 0];
	var rootRot = rot;
	if (roots.length == 0)
		return null;
	if (document.getElementById(instanceId))
	{
		var suffix = 1;
		var candidate = instanceId + '_inst';
		while (document.getElementById(candidate))
		{
			candidate = instanceId + '_inst' + suffix;
			suffix ++;
		}
		instanceId = candidate;
	}
	var container = add_div(instanceId, rootWorld, [], {}, '', rootRot);
	for (var r = 0; r < roots.length; r ++)
	{
		var rid = roots[r];
		var rdef = nodes[rid];
		if (!rdef)
			continue;
		var rpos = [rdef.localPos[0] || 0, rdef.localPos[1] || 0];
		var rrot = rdef.localRot || 0;
		spawnNode (rid, instanceId + '_' + rid, rpos, rrot, container);
	}
	return container;
}
globalThis.spawn_prefab = spawn_prefab;
function remove_node (node)
{
	if (!node)
		return;
	function removeRecursive (current)
	{
		unregister_instance (current.id);
		while (current.firstChild)
			removeRecursive (current.firstChild);
		if (rigidBodiesIds[current.id])
			delete rigidBodiesIds[current.id];
		if (collidersIds[current.id])
		{
			delete collidersIds[current.id];
			delete colliderOffsetsIds[current.id];
			delete visualOffsetsIds[current.id];
		}
		current.remove();
	}
	removeRecursive (node);
}
globalThis.remove_node = remove_node;
function remove_prefab (rootNodeOrId)
{
	var root = typeof rootNodeOrId === 'string' ? document.getElementById(rootNodeOrId) : rootNodeOrId;
	if (!root)
		return;
	function removeRecursive (node)
	{
		unregister_instance (node.id);
		while (node.firstChild)
			removeRecursive (node.firstChild);
		remove (node);
	}
	removeRecursive (root);
}
globalThis.remove_prefab = remove_prefab;
function get_prefab_node (instanceId, templateId)
{
	return document.getElementById(instanceId + '_' + templateId) || document.getElementById(instanceId);
}
globalThis.get_prefab_node = get_prefab_node;
// Physics Section End
globalThis.prevTicks = 0;
globalThis.dt = 0;
function main ()
{
	var f = t => {
		dt = (t - prevTicks) / 1000;
// Physics Section Start
		globalThis.world.timestep = dt;
		globalThis.world.step(globalThis.eventQueue);
		resolve_pending_physics_copies ();
		set_transforms (rigidBodiesIds);
		set_transforms (collidersIds);
// Physics Section End
		prevTicks = t;
		window.requestAnimationFrame(f);
		run_update_scripts ();
		// Update
	};
	window.requestAnimationFrame(t => {
		prevTicks = t;
		window.requestAnimationFrame(f);
	});
}
'''

def GenJs (world):
	global datas, clrs, prefabs, prefabTemplateDatas, prefabPathsDatas
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
	js = [JS, jsApi]
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
	datas = json.dumps(datas).replace(', ', ',').replace(': ', ':')
	clrs = json.dumps(clrs).replace(' ', '')
	prefabsJson = json.dumps(prefabs).replace(', ', ',').replace(': ', ':')
	prefabTemplateDatasJson = json.dumps(prefabTemplateDatas).replace(', ', ',').replace(': ', ':')
	prefabPathCount = len(prefabPathsDatas)
	pathsCombined = ('\n'.join(prefabPathsDatas) + '\n' + '\n'.join(pathsDatas)) if prefabPathsDatas else '\n'.join(pathsDatas)
	pathsCombinedEsc = pathsCombined.replace('\\', '\\\\').replace('`', '\\`')
	ptEsc = prefabTemplateDatasJson.replace('\\', '\\\\').replace('`', '\\`')
	jsDataVars = 'var D=`' + datas + '`\nvar p=`' + pathsCombinedEsc + '`;\nvar C=`' + clrs + '`\nvar P=`' + prefabsJson + '`\nvar PT=`' + ptEsc + '`\nvar PPC=' + str(prefabPathCount) + '\n'
	templateScriptsJson = json.dumps(templateScripts)
	templateScriptsInlined = 'JSON.parse("' + templateScriptsJson.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '")'
	def _prepare_injected_script (code):
		code = re.sub(r'(^|[^\w])(new\s+)?globalThis\.RAPIER\.Vector2\s*\(', lambda m: m.group(1) + ('' if m.group(2) else 'new ') + 'globalThis.RAPIER.Vector2(', code, flags = re.M)
		code = re.sub(r'(^|[^\w])(new\s+)?RAPIER\.Vector2\s*\(', lambda m: m.group(1) + ('' if m.group(2) else 'new ') + 'RAPIER.Vector2(', code, flags = re.M)
		code = re.sub(r'([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)\.items\s*\(\)', r'Object.entries(\1)', code)
		return code
	initInjected = '\n'.join('(function(){ ' + _prepare_injected_script(s) + ' })();' for s in initCode)
	updateInjected = '\n'.join('(function(){ ' + _prepare_injected_script(s) + ' })();' for s in updateCode)
	if world.minifyMethod == 'terser':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += jsDataVars + JS_SUFFIX
		js = js.replace('// Init', initInjected)
		js = js.replace('// Update', updateInjected)
		js = js.replace('__TEMPLATE_SCRIPTS_JSON__', templateScriptsInlined)
		open(jsTmp, 'w').write(js)
		cmd = ['python3', 'tinifyjs/Main.py', '-i=' + jsTmp, '-o=' + jsTmp, '-no_compress', dontMangleArg]
		print(' '.join(cmd))
		subprocess.run(cmd)
		js = open(jsTmp, 'r').read()
	elif world.minifyMethod == 'roadroller':
		jsTmp = os.path.join(TMP_DIR, 'js13kjam API.js')
		js += jsDataVars + JS_SUFFIX
		js = js.replace('// Init', initInjected)
		js = js.replace('// Update', updateInjected)
		js = js.replace('__TEMPLATE_SCRIPTS_JSON__', templateScriptsInlined)
		open(jsTmp, 'w').write(js)
		cmd = ['npx', 'roadroller', jsTmp, '-o', jsTmp]
		print(' '.join(cmd))
		subprocess.check_call(cmd)
		js = open(jsTmp, 'r').read()
	else:
		js += '\n' + jsDataVars + JS_SUFFIX.replace('\t', '')
		js = js.replace('// Init', initInjected)
		js = js.replace('// Update', updateInjected)
		js = js.replace('__TEMPLATE_SCRIPTS_JSON__', templateScriptsInlined)
	return js

def GenHtml (world, datas, background = ''):
	global clrs, initCode, updateCode, pathsDatas
	js = GenJs(world)
	if background:
		background = 'background-color:%s;' %background
	o = [
		'<!DOCTYPE html>',
		'<html style="' + background + 'width:9999px;height:9999px;overflow:hidden">',
		'<head>',
		'<meta charset="utf-8">',
		'</head>',
		'<body>',
		''.join(imgs.values()),
		''.join(svgsDatas.values()),
		'<script type="importmap">',
		world.importMap,
		'</script>',
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
	global ui, vars, clrs, initCode, updateCode, pathsDatas, uiMethods
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
	python = python.replace('# API', '')
	python = python.replace('# Vars', '\n'.join(vars))
	python = python.replace('# UI Methods', '\n'.join((uiMethods)))
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
	uiCode = ''
	for clause in ui:
		for line in clause.split('\n'):
			uiCode += '		' + line + '\n'
	python = python.replace('# Init Pivots, Attributes, UI', f'		pivots = {pivots}\n		attributes = {attributes}\n{uiCode}')
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

_GBA_EMU_PROCS = []
def _run_py2gba_export_with_resolved_logs (export_fn, script_entries, out_path):
	start_time = time.time()
	stdout_buf = io.StringIO()
	stderr_buf = io.StringIO()
	with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
		result = export_fn(
			script_entries,
			out_path,
			tmp_dir = TMP_DIR,
			repo_root_dir = _thisDir,
		)
	for raw in stdout_buf.getvalue().splitlines():
		line = raw.rstrip('\n')
		if line:
			print(_resolve_runtime_print_exprs(line, start_time = start_time))
	for raw in stderr_buf.getvalue().splitlines():
		line = raw.rstrip('\n')
		if line:
			print(_resolve_runtime_print_exprs(line, start_time = start_time))
	return result

def _resolve_runtime_print_exprs (text : str, frame : int = None, start_time : float = None):
	'''Resolve <expr:...> print placeholders to runtime values.'''
	if not isinstance(text, str):
		text = str(text)
	if frame is not None:
		# Match 60 Hz frame stepping used by fallback print mirroring.
		ticks = int(round((max(0, frame - 1) * 1000.0) / 60.0))
	elif start_time is not None:
		ticks = int(max(0.0, (time.time() - start_time) * 1000.0))
	else:
		ticks = 0
	# Fast path for the common placeholder.
	text = re.sub(
		r'<expr:\s*(?:pygame\s*\.\s*time\s*\.\s*get_ticks|js13k_get_ticks)\s*\(\s*\)\s*>',
		str(ticks),
		text,
		flags = re.IGNORECASE,
	)
	def _eval_expr (m):
		expr = m.group(1).strip()
		# Replace supported runtime function calls with numeric values first.
		expr_with_ticks = _replace_runtime_ticks_calls(expr, ticks)
		expr_eval = _replace_runtime_key_calls(expr_with_ticks)
		# Fast path: plain integer after replacement.
		if re.fullmatch(r'[+-]?\d+', expr_eval):
			return expr_eval
		key_state = _runtime_key_state_snapshot()
		try:
			val = eval(
				expr_eval,
				{'__builtins__' : {}},
				{
					'int' : int,
					'float' : float,
					'round' : round,
					'abs' : abs,
					'max' : max,
					'min' : min,
					'js13k_get_pressed' : (lambda : key_state),
				},
			)
			if isinstance(val, (int, float, bool, str)):
				return str(val)
			return str(val)
		except Exception:
			# Fallback: at least substitute ticks call in the placeholder.
			return expr_eval
	text = re.sub(r'<expr:\s*([^<>]*)\s*>', _eval_expr, text, flags = re.IGNORECASE)
	# Last-resort cleanup if any expression wrapper still leaks through.
	if '<expr:' in text.lower():
		text = re.sub(r'(?i)<expr:\s*', '', text)
		text = text.replace('>', '')
		text = _replace_runtime_ticks_calls(text, ticks)
		text = _replace_runtime_key_calls(text)
	else:
		text = _replace_runtime_ticks_calls(text, ticks)
		text = _replace_runtime_key_calls(text)
	return text

def _pipe_process_output_to_terminal (proc, prefix = 'mGBA'):
	start_time = time.time()
	def _reader():
		try:
			if not proc.stdout:
				return
			for line in proc.stdout:
				line = line.rstrip('\n')
				if line:
					line = _resolve_runtime_print_exprs(line, start_time = start_time)
					print('[' + prefix + ']', line)
		except Exception:
			pass
	thread = threading.Thread(target = _reader, daemon = True)
	thread.start()
	_GBA_EMU_PROCS.append((proc, thread))

def _start_gba_update_print_mirror (proc, script_runtime, script_label : str = 'gba-py'):
	print_calls = list((script_runtime or {}).get('print_calls') or [])
	init_calls = [p for p in print_calls if p.get('is_init')]
	update_calls = [p for p in print_calls if not p.get('is_init')]
	if not init_calls and not update_calls:
		return
	def _runner():
		frame = 0
		init_printed = False
		def _should_emit (info, frame):
			cond = info.get('condition')
			if cond is None or cond == '':
				return True
			val = _eval_runtime_expr_value(cond, frame = frame)
			if val is None:
				return False
			return abs(float(val)) > 1e-9
		while proc.poll() is None:
			frame += 1
			if not init_printed:
				for info in init_calls:
					if not _should_emit(info, frame):
						continue
					owner = info.get('owner_name') or '__world__'
					text = str(info.get('text', '')).rstrip('\n')
					text = _resolve_runtime_print_exprs(text, frame = frame)
					print(f"[{script_label}:init:runtime] {owner} {text}")
				init_printed = True
			for info in update_calls:
				if not _should_emit(info, frame):
					continue
				owner = info.get('owner_name') or '__world__'
				text = str(info.get('text', '')).rstrip('\n')
				text = _resolve_runtime_print_exprs(text, frame = frame)
				print(f"[{script_label}:update:runtime] {owner} [f={frame}] {text}")
			time.sleep(1.0 / 60.0)
	thread = threading.Thread(target = _runner, daemon = True)
	thread.start()
	_GBA_EMU_PROCS.append((proc, thread))

_GBA_NINTENDO_LOGO = bytes([
	0x24, 0xFF, 0xAE, 0x51, 0x69, 0x9A, 0xA2, 0x21, 0x3D, 0x84, 0x82, 0x0A, 0x84, 0xE4, 0x09, 0xAD, 0x11, 0x24,
	0x8B, 0x98, 0xC0, 0x81, 0x7F, 0x21, 0xA3, 0x52, 0xBE, 0x19, 0x93, 0x09, 0xCE, 0x20, 0x10, 0x46, 0x4A, 0x4A,
	0xF8, 0x27, 0x31, 0xEC, 0x58, 0xC7, 0xE8, 0x33, 0x82, 0xE3, 0xCE, 0xBF, 0x85, 0xF4, 0xDF, 0x94, 0xCE, 0x4B,
	0x09, 0xC1, 0x94, 0x56, 0x8A, 0xC0, 0x13, 0x72, 0xA7, 0xFC, 0x9F, 0x84, 0x4D, 0x73, 0xA3, 0xCA, 0x9A, 0x61,
	0x58, 0x97, 0xA3, 0x27, 0xFC, 0x03, 0x98, 0x76, 0x23, 0x1D, 0xC7, 0x61, 0x03, 0x04, 0xAE, 0x56, 0xBF, 0x38, 0x84,
	0x00, 0x40, 0xA7, 0x0E, 0xFD, 0xFF, 0x52, 0xFE, 0x03, 0x6F, 0x95, 0x30, 0xF1, 0x97, 0xFB, 0xC0, 0x85,
	0x60, 0xD6, 0x80, 0x25, 0xA9, 0x63, 0xBE, 0x03, 0x01, 0x4E, 0x38, 0xE2, 0xF9, 0xA2, 0x34, 0xFF, 0xBB, 0x3E,
	0x03, 0x44, 0x78, 0x00, 0x90, 0xCB, 0x88, 0x11, 0x3A, 0x94, 0x65, 0xC0, 0x7C, 0x63, 0x87, 0xF0, 0x3C, 0xAF,
	0xD6, 0x25, 0xE4, 0x8B, 0x38, 0x0A, 0xAC, 0x72, 0x21, 0xD4, 0xF8, 0x07,
])
_GBC_NINTENDO_LOGO = bytes([
	0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B, 0x03, 0x73, 0x00, 0x83,
	0x00, 0x0C, 0x00, 0x0D, 0x00, 0x08, 0x11, 0x1F, 0x88, 0x89, 0x00, 0x0E,
	0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9, 0x99, 0xBB, 0xBB, 0x67, 0x63,
	0x6E, 0x0E, 0xEC, 0xCC, 0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33, 0x3E,
])
_GBC_DEFAULT_BG_COLORS = [
	(224, 248, 208),
	(136, 192, 112),
	(52, 104, 86),
	(8, 24, 32),
]

def _gba_complement_check (rom : bytearray):
	chk = 0
	for b in rom[0xA0 : 0xBD]:
		chk = (chk - b) & 0xFF
	rom[0xBD] = (chk - 0x19) & 0xFF

def _gbc_compute_header_checksums (rom : bytearray):
	header_chk = 0
	for b in rom[0x134 : 0x14D]:
		header_chk = (header_chk - b - 1) & 0xFF
	rom[0x14D] = header_chk
	global_chk = 0
	for i, b in enumerate(rom):
		if i == 0x14E or i == 0x14F:
			continue
		global_chk = (global_chk + b) & 0xFFFF
	rom[0x14E] = (global_chk >> 8) & 0xFF
	rom[0x14F] = global_chk & 0xFF

def _gbc_tile_to_2bpp (tile_colors_8x8):
	out = bytearray(16)
	for y in range(8):
		lo = 0
		hi = 0
		for x in range(8):
			val = int(tile_colors_8x8[y, x]) & 0x3
			shift = 7 - x
			lo |= (val & 0x1) << shift
			hi |= ((val >> 1) & 0x1) << shift
		out[y * 2] = lo
		out[y * 2 + 1] = hi
	return bytes(out)

def _gbc_quantize_palette4 (pixels_rgb_u8, lock_extremes : bool = True):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBC requires NumPy (included with Blender).')
	flat = pixels_rgb_u8.astype(np.float32)
	if flat.shape[0] == 0:
		palette = np.array(_GBC_DEFAULT_BG_COLORS, dtype = np.uint8)
		return palette[: 4]
	unique, counts = np.unique(flat.astype(np.uint8), axis = 0, return_counts = True)
	weights = counts.astype(np.float32)
	if unique.shape[0] <= 4:
		palette = unique.astype(np.float32)
	else:
		luma = (unique[:, 0].astype(np.float32) * 0.299 + unique[:, 1].astype(np.float32) * 0.587 + unique[:, 2].astype(np.float32) * 0.114)
		if lock_extremes:
			dark_idx = int(np.argmin(luma))
			bright_idx = int(np.argmax(luma))
			chosen = [dark_idx]
			if bright_idx != dark_idx:
				chosen.append(bright_idx)
		else:
			chosen = [int(np.argmax(weights))]
		while len(chosen) < 4:
			chosen_arr = unique[np.array(chosen, dtype = np.int32)].astype(np.float32)
			diff = unique[:, None, :].astype(np.float32) - chosen_arr[None, :, :]
			min_d2 = (diff * diff).sum(axis = 2).min(axis = 1)
			score = min_d2 * np.sqrt(np.maximum(1.0, weights))
			score[np.array(chosen, dtype = np.int32)] = -1.0
			chosen.append(int(np.argmax(score)))
		palette = unique[np.array(chosen, dtype = np.int32)].astype(np.float32)
		u = unique.astype(np.float32)
		for _ in range(6):
			diff = u[:, None, :] - palette[None, :, :]
			assign = np.argmin((diff * diff).sum(axis = 2), axis = 1)
			for i in range(4):
				if lock_extremes and i < 2:
					continue
				mask = (assign == i)
				if not np.any(mask):
					continue
				w = weights[mask][:, None]
				palette[i] = (u[mask] * w).sum(axis = 0) / np.maximum(1.0, w.sum())
	if palette.shape[0] < 4:
		pad = np.repeat(palette[-1 :], 4 - palette.shape[0], axis = 0)
		palette = np.concatenate([palette, pad], axis = 0)
	return np.clip(palette, 0.0, 255.0).astype(np.uint8)

def _gbc_quantize_indices_for_palette (pixels_rgb_u8, palette_u8):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBC requires NumPy (included with Blender).')
	pix = pixels_rgb_u8.astype(np.float32)
	pal = palette_u8.astype(np.float32)
	diff = pix[:, None, :] - pal[None, :, :]
	d2 = (diff * diff).sum(axis = 2)
	indices = np.argmin(d2, axis = 1).astype(np.uint8)
	err = float(np.take_along_axis(d2, indices[:, None], axis = 1).sum())
	return indices, err

def _gbc_encode_tiles_and_map (rgba_canvas_160x144):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBC requires NumPy (included with Blender).')
	rgb_u8 = (np.clip(rgba_canvas_160x144[:, :, :3], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
	tile_pixels = []
	tile_local_palettes = []
	for ty in range(18):
		for tx in range(20):
			pix = rgb_u8[ty * 8 : ty * 8 + 8, tx * 8 : tx * 8 + 8, :].reshape((64, 3))
			tile_pixels.append(pix)
			tile_local_palettes.append(_gbc_quantize_palette4(pix, lock_extremes = True))
	if not tile_pixels:
		return b'', bytes(32 * 32), bytes(32 * 32), [np.array(_GBC_DEFAULT_BG_COLORS[: 4], dtype = np.uint8)]
	palette_bank = [tile_local_palettes[0]]
	while len(palette_bank) < 8:
		worst_i = -1
		worst_err = -1.0
		for i, pix in enumerate(tile_pixels):
			best_err = None
			for pal in palette_bank:
				_, err = _gbc_quantize_indices_for_palette(pix, pal)
				if best_err is None or err < best_err:
					best_err = err
			if best_err is not None and best_err > worst_err:
				worst_err = best_err
				worst_i = i
		if worst_i == -1 or worst_err <= 0.0:
			break
		candidate = tile_local_palettes[worst_i]
		if any(np.array_equal(candidate, p) for p in palette_bank):
			break
		palette_bank.append(candidate)
	for _ in range(2):
		assignments = []
		for pix in tile_pixels:
			best_idx = 0
			best_err = None
			for pi, pal in enumerate(palette_bank):
				_, err = _gbc_quantize_indices_for_palette(pix, pal)
				if best_err is None or err < best_err:
					best_err = err
					best_idx = pi
			assignments.append(best_idx)
		for pi in range(len(palette_bank)):
			group = [tile_pixels[i] for i, a in enumerate(assignments) if a == pi]
			if not group:
				continue
			joined = np.concatenate(group, axis = 0)
			palette_bank[pi] = _gbc_quantize_palette4(joined, lock_extremes = True)
	tile_indices = []
	tile_palette_idx = []
	for pix in tile_pixels:
		best_idx = 0
		best_err = None
		best_indices = None
		for pi, pal in enumerate(palette_bank):
			idxs, err = _gbc_quantize_indices_for_palette(pix, pal)
			if best_err is None or err < best_err:
				best_err = err
				best_idx = pi
				best_indices = idxs
		tile_palette_idx.append(best_idx)
		tile_indices.append(best_indices)
	tile_matrix = np.stack(tile_indices, axis = 0)
	unique_tiles, inverse, counts = np.unique(tile_matrix, axis = 0, return_inverse = True, return_counts = True)
	if unique_tiles.shape[0] <= 256:
		palette_tiles = unique_tiles
		unique_to_palette = np.arange(unique_tiles.shape[0], dtype = np.int32)
	else:
		top = np.argsort(-counts)[: 256]
		palette_tiles = unique_tiles[top]
		dist = np.abs(unique_tiles[:, None, :].astype(np.int16) - palette_tiles[None, :, :].astype(np.int16)).sum(axis = 2)
		unique_to_palette = np.argmin(dist, axis = 1).astype(np.int32)
		print('GBC export: reduced unique tiles from', unique_tiles.shape[0], 'to 256.')
	tilemap_linear = unique_to_palette[inverse].astype(np.uint8)
	attr_linear = np.array(tile_palette_idx, dtype = np.uint8)
	tilemap = np.zeros((32, 32), dtype = np.uint8)
	attrmap = np.zeros((32, 32), dtype = np.uint8)
	for ty in range(18):
		row_src_start = ty * 20
		row_src_end = row_src_start + 20
		tilemap[ty, :20] = tilemap_linear[row_src_start : row_src_end]
		attrmap[ty, :20] = attr_linear[row_src_start : row_src_end] & 0x07
	tile_bytes = bytearray()
	for tile_flat in palette_tiles:
		tile_8x8 = tile_flat.reshape((8, 8))
		tile_bytes.extend(_gbc_tile_to_2bpp(tile_8x8))
	return bytes(tile_bytes), tilemap.tobytes(), attrmap.tobytes(), palette_bank

def _gbc_build_program (frame_data_addr : int, frame_stride : int, frame_count : int, tile_data_len : int, tilemap_len : int, attrmap_len : int, bg_palette_bytes : bytes):
	code = bytearray()
	def emit(*vals):
		code.extend(vals)
	def jr(op):
		emit(op, 0x00)
		return len(code) - 1
	def patch_jr(pos, target):
		disp = int(target) - int(pos + 1)
		if disp < -128 or disp > 127:
			raise RuntimeError('GBC export: branch offset out of range.')
		code[pos] = disp & 0xFF
	def ld_a_imm(v):
		emit(0x3E, int(v) & 0xFF)
	def ldh_imm_a(reg):
		emit(0xE0, int(reg) & 0xFF)
	def ld_hl_imm(v):
		emit(0x21, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	def ld_de_imm(v):
		emit(0x11, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	def ld_bc_imm(v):
		emit(0x01, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	frame_count = max(1, int(frame_count))
	frame_data_addr = int(frame_data_addr) & 0xFFFF
	frame_stride = int(frame_stride) & 0xFFFF
	frame_end_addr = (frame_data_addr + frame_stride * frame_count) & 0xFFFF
	next_frame_addr = frame_data_addr if frame_count <= 1 else ((frame_data_addr + frame_stride) & 0xFFFF)
	wptr_lo_addr = 0xC100
	wptr_hi_addr = 0xC101
	emit(0xF3)  # di
	emit(0x31, 0xFE, 0xFF)  # ld sp, $FFFE
	emit(0xAF)  # xor a
	ldh_imm_a(0x40)  # LCDC off
	ld_a_imm(0x80)  # BG palette index 0, autoinc
	ldh_imm_a(0x68)
	for b in bg_palette_bytes:
		ld_a_imm(b)
		ldh_imm_a(0x69)
	ld_hl_imm(frame_data_addr)
	emit(0xCD, 0x00, 0x00)  # call copy_frame (patched)
	call_init_copy_patch = len(code) - 2
	ld_a_imm(next_frame_addr & 0xFF)
	emit(0xEA, wptr_lo_addr & 0xFF, (wptr_lo_addr >> 8) & 0xFF)
	ld_a_imm((next_frame_addr >> 8) & 0xFF)
	emit(0xEA, wptr_hi_addr & 0xFF, (wptr_hi_addr >> 8) & 0xFF)
	emit(0xAF)  # xor a
	ldh_imm_a(0x4F)  # VBK = 0
	emit(0xAF)  # xor a
	ldh_imm_a(0x42)  # SCY
	ldh_imm_a(0x43)  # SCX
	ld_a_imm(0x91)  # LCDC on, BG on
	ldh_imm_a(0x40)
	emit(0xFB)  # ei
	main_loop_addr = len(code)
	emit(0xCD, 0x00, 0x00)  # call wait_vblank (patched)
	call_wait_patch = len(code) - 2
	emit(0xFA, wptr_lo_addr & 0xFF, (wptr_lo_addr >> 8) & 0xFF)  # ld a, (wptr_lo)
	emit(0x6F)  # ld l, a
	emit(0xFA, wptr_hi_addr & 0xFF, (wptr_hi_addr >> 8) & 0xFF)  # ld a, (wptr_hi)
	emit(0x67)  # ld h, a
	emit(0xCD, 0x00, 0x00)  # call copy_frame (patched)
	call_loop_copy_patch = len(code) - 2
	emit(0x7C)  # ld a, h
	emit(0xFE, (frame_end_addr >> 8) & 0xFF)  # cp frame_end_hi
	jr_store_hi_less = jr(0x38)  # jr c, store_ptr
	jr_reset_hi_gt = jr(0x20)  # jr nz, reset_ptr
	emit(0x7D)  # ld a, l
	emit(0xFE, frame_end_addr & 0xFF)  # cp frame_end_lo
	jr_store_lo_less = jr(0x38)  # jr c, store_ptr
	reset_ptr_addr = len(code)
	ld_hl_imm(frame_data_addr)
	jr_after_reset = jr(0x18)  # jr after_reset
	store_ptr_addr = len(code)
	emit(0x7D)  # ld a, l
	emit(0xEA, wptr_lo_addr & 0xFF, (wptr_lo_addr >> 8) & 0xFF)
	emit(0x7C)  # ld a, h
	emit(0xEA, wptr_hi_addr & 0xFF, (wptr_hi_addr >> 8) & 0xFF)
	after_reset_addr = len(code)
	jr_loop = jr(0x18)  # jr main_loop
	wait_vblank_addr = len(code)
	wait_vblank_end_addr = len(code)
	emit(0xF0, 0x44)  # ld a, [LY]
	emit(0xFE, 0x90)  # cp 144
	emit(0x30, 0xFA)  # jr nc, wait_vblank_end_addr
	wait_vblank_start_addr = len(code)
	emit(0xF0, 0x44)  # ld a, [LY]
	emit(0xFE, 0x90)  # cp 144
	emit(0x38, 0xFA)  # jr c, wait_vblank_start_addr
	emit(0xC9)  # ret
	copy_frame_addr = len(code)
	emit(0xD5)  # push de
	emit(0xC5)  # push bc
	emit(0xAF)  # xor a
	ldh_imm_a(0x4F)  # VBK = 0
	ld_de_imm(0x8000)
	ld_bc_imm(tile_data_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc (patched)
	call_copy_tiles_patch = len(code) - 2
	ld_de_imm(0x9800)
	ld_bc_imm(tilemap_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc (patched)
	call_copy_map_patch = len(code) - 2
	ld_a_imm(0x01)
	ldh_imm_a(0x4F)  # VBK = 1 (attributes)
	ld_de_imm(0x9800)
	ld_bc_imm(attrmap_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc (patched)
	call_copy_attr_patch = len(code) - 2
	emit(0xAF)  # xor a
	ldh_imm_a(0x4F)  # VBK = 0
	emit(0xC1)  # pop bc
	emit(0xD1)  # pop de
	emit(0xC9)  # ret
	copy_addr = len(code)
	emit(0x78)  # ld a,b
	emit(0xB1)  # or c
	emit(0xC8)  # ret z
	emit(0x2A)  # ld a,[hl+]
	emit(0x12)  # ld [de],a
	emit(0x13)  # inc de
	emit(0x0B)  # dec bc
	emit(0x18, 0xF7)  # jr copy loop
	patch_jr(jr_store_hi_less, store_ptr_addr)
	patch_jr(jr_reset_hi_gt, reset_ptr_addr)
	patch_jr(jr_store_lo_less, store_ptr_addr)
	patch_jr(jr_after_reset, after_reset_addr)
	patch_jr(jr_loop, main_loop_addr)
	# Silence unused-local warning for explicit locations.
	_ = (wait_vblank_addr, wait_vblank_end_addr, wait_vblank_start_addr)
	copy_abs = 0x150 + copy_addr
	copy_frame_abs = 0x150 + copy_frame_addr
	wait_vblank_abs = 0x150 + wait_vblank_addr
	code[call_init_copy_patch] = copy_frame_abs & 0xFF
	code[call_init_copy_patch + 1] = (copy_frame_abs >> 8) & 0xFF
	code[call_wait_patch] = wait_vblank_abs & 0xFF
	code[call_wait_patch + 1] = (wait_vblank_abs >> 8) & 0xFF
	code[call_loop_copy_patch] = copy_frame_abs & 0xFF
	code[call_loop_copy_patch + 1] = (copy_frame_abs >> 8) & 0xFF
	code[call_copy_tiles_patch] = copy_abs & 0xFF
	code[call_copy_tiles_patch + 1] = (copy_abs >> 8) & 0xFF
	code[call_copy_map_patch] = copy_abs & 0xFF
	code[call_copy_map_patch + 1] = (copy_abs >> 8) & 0xFF
	code[call_copy_attr_patch] = copy_abs & 0xFF
	code[call_copy_attr_patch + 1] = (copy_abs >> 8) & 0xFF
	return bytes(code)

def _gbc_encode_metasprite_rgba (rgba, sprite_w_px : int, sprite_h_px : int, palette4 = None, max_tiles : int = 16):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('GBC export requires NumPy.')
	if rgba is None:
		return (bytes([0] * 16), 1, 1)
	sprite_w_px = max(8, min(32, int(sprite_w_px)))
	sprite_h_px = max(8, min(32, int(sprite_h_px)))
	tiles_w = max(1, min(4, int(math.ceil(sprite_w_px / 8.0))))
	tiles_h = max(1, min(4, int(math.ceil(sprite_h_px / 8.0))))
	while tiles_w * tiles_h > max_tiles:
		if tiles_w >= tiles_h and tiles_w > 1:
			tiles_w -= 1
		elif tiles_h > 1:
			tiles_h -= 1
		else:
			break
	resized = _gba_nn_resize_rgba(rgba, tiles_w * 8, tiles_h * 8).copy()
	if resized.shape[0] != tiles_h * 8 or resized.shape[1] != tiles_w * 8:
		return (bytes([0] * 16), 1, 1)
	pal = palette4
	if pal is None or len(pal) < 4:
		pal = _GBC_DEFAULT_BG_COLORS[: 4]
	pal_np = np.array([[int(c[0]), int(c[1]), int(c[2])] for c in pal[: 4]], dtype = np.float32)
	out = bytearray()
	for ty in range(tiles_h):
		for tx in range(tiles_w):
			tile = resized[ty * 8 : (ty + 1) * 8, tx * 8 : (tx + 1) * 8, :]
			alpha = np.clip(tile[:, :, 3], 0.0, 1.0)
			rgb255 = np.clip(tile[:, :, :3], 0.0, 1.0) * 255.0
			idx = np.zeros((8, 8), dtype = np.uint8)
			for y in range(8):
				for x in range(8):
					if alpha[y, x] <= 0.2:
						idx[y, x] = 0
						continue
					d = pal_np[1 : 4] - rgb255[y, x]
					err = np.sum(d * d, axis = 1)
					idx[y, x] = int(1 + int(np.argmin(err)))
			out.extend(_gbc_tile_to_2bpp(idx))
	return (bytes(out), tiles_w, tiles_h)

def _gbc_palette_bytes_from_palette_bank (palette_bank):
	palette_bytes = bytearray()
	default_pal = _GBC_DEFAULT_BG_COLORS[: 4]
	for p_idx in range(8):
		pal = palette_bank[p_idx] if palette_bank is not None and p_idx < len(palette_bank) else default_pal
		for r, g, b in pal:
			c = _gba_pack_rgb555_le(r, g, b)
			palette_bytes.append(c & 0xFF)
			palette_bytes.append((c >> 8) & 0xFF)
	return bytes(palette_bytes)

def _gbc_palette4_from_rgba (rgba):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBC requires NumPy (included with Blender).')
	if rgba is None:
		return _GBC_DEFAULT_BG_COLORS[: 4]
	alpha = np.clip(rgba[:, :, 3], 0.0, 1.0)
	opaque = alpha > 0.2
	if not np.any(opaque):
		return _GBC_DEFAULT_BG_COLORS[: 4]
	rgb = (np.clip(rgba[:, :, :3], 0.0, 1.0) * 255.0).astype(np.uint8)
	pix = rgb[opaque]
	if pix.shape[0] == 0:
		return _GBC_DEFAULT_BG_COLORS[: 4]
	return _gbc_quantize_palette4(pix, lock_extremes = True)

def _gbc_build_dynamic_physics_program (bg_data_addr : int, bg_tile_data_len : int, bg_tilemap_len : int, bg_attrmap_len : int, sprite_data_addr : int, sprite_tile_count : int, sprite_tiles_w : int, sprite_tiles_h : int, init_x : int, init_y : int, bg_palette_bytes : bytes, obj_palette_bytes : bytes, collider_data_addr : int = 0, collider_count : int = 0, grav_step_x : int = 0, grav_step_y : int = 1):
	code = bytearray()
	def emit(*vals):
		code.extend(vals)
	def jr(op):
		emit(op, 0x00)
		return len(code) - 1
	def patch_jr(pos, target):
		disp = int(target) - int(pos + 1)
		if disp < -128 or disp > 127:
			raise RuntimeError('GBC export: dynamic physics branch offset out of range.')
		code[pos] = disp & 0xFF
	def ld_a_imm(v):
		emit(0x3E, int(v) & 0xFF)
	def ldh_imm_a(reg):
		emit(0xE0, int(reg) & 0xFF)
	def ld_hl_imm(v):
		emit(0x21, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	def ld_de_imm(v):
		emit(0x11, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	def ld_bc_imm(v):
		emit(0x01, int(v) & 0xFF, (int(v) >> 8) & 0xFF)
	init_x = max(0, min(159, int(init_x)))
	init_y = max(0, min(143, int(init_y)))
	grav_step_x = max(-32, min(32, int(grav_step_x)))
	grav_step_y = max(-32, min(32, int(grav_step_y)))
	collider_count = max(0, min(31, int(collider_count)))
	sprite_tile_count = max(1, min(16, int(sprite_tile_count)))
	sprite_tiles_w = max(1, min(4, int(sprite_tiles_w)))
	sprite_tiles_h = max(1, min(4, int(sprite_tiles_h)))
	if sprite_tiles_w * sprite_tiles_h > sprite_tile_count:
		sprite_tiles_h = max(1, sprite_tile_count // sprite_tiles_w)
	sprite_w_px = max(8, min(32, sprite_tiles_w * 8))
	sprite_h_px = max(8, min(32, sprite_tiles_h * 8))
	max_x = max(0, min(159, 160 - sprite_tiles_w * 8))
	offscreen_bottom_y = max(145, min(252, 144 + sprite_tiles_h * 8))
	y_addr = 0xC110
	vy_addr = 0xC111
	x_addr = 0xC112
	vx_addr = 0xC113
	gacc_y_addr = 0xC114
	gacc_x_addr = 0xC115
	dead_addr = 0xC116
	emit(0xF3)  # di
	emit(0x31, 0xFE, 0xFF)  # ld sp, $FFFE
	emit(0xAF)  # xor a
	ldh_imm_a(0x40)  # LCDC off
	# CGB BG palette 0.
	ld_a_imm(0x80)
	ldh_imm_a(0x68)
	for b in (bg_palette_bytes or bytes()):
		ld_a_imm(b); ldh_imm_a(0x69)
	# CGB OBJ palette 0.
	ld_a_imm(0x80)
	ldh_imm_a(0x6A)
	for b in (obj_palette_bytes or bytes()):
		ld_a_imm(b); ldh_imm_a(0x6B)
	# Copy static BG once.
	ld_hl_imm(bg_data_addr)
	emit(0xCD, 0x00, 0x00)  # call copy_bg
	call_copy_bg_patch = len(code) - 2
	# Copy sprite tile into VRAM bank 1 tile 0.
	ld_a_imm(0x01)
	ldh_imm_a(0x4F)  # VBK = 1
	ld_hl_imm(sprite_data_addr)
	ld_de_imm(0x8000)
	ld_bc_imm(sprite_tile_count * 16)
	emit(0xCD, 0x00, 0x00)  # call copy_bc
	call_copy_sprite_patch = len(code) - 2
	emit(0xAF)
	ldh_imm_a(0x4F)  # VBK = 0
	# Seed y/vy state and OAM metasprite entries.
	ld_a_imm(init_y)
	emit(0xEA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
	ld_a_imm(init_x)
	emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, dead_addr & 0xFF, (dead_addr >> 8) & 0xFF)
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			ld_a_imm(init_y + row * 8 + 16)
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)  # OAM y
			ld_a_imm(init_x + col * 8 + 8)
			emit(0xEA, (base + 1) & 0xFF, ((base + 1) >> 8) & 0xFF)  # OAM x
			ld_a_imm(idx)
			emit(0xEA, (base + 2) & 0xFF, ((base + 2) >> 8) & 0xFF)  # tile idx
			ld_a_imm(0x08)  # OBJ tile bank 1
			emit(0xEA, (base + 3) & 0xFF, ((base + 3) >> 8) & 0xFF)
	emit(0xAF); ldh_imm_a(0x42); ldh_imm_a(0x43)  # SCY/SCX
	ld_a_imm(0x93)  # LCDC on with OBJ
	ldh_imm_a(0x40)
	emit(0xFB)  # ei
	main_loop_addr = len(code)
	emit(0xCD, 0x00, 0x00)  # call wait_vblank
	call_wait_patch = len(code) - 2
	emit(0xCD, 0x00, 0x00)  # call update_body
	call_update_patch = len(code) - 2
	jr_loop = jr(0x18)
	update_addr = len(code)
	# If already despawned, keep sprite hidden and skip physics update.
	emit(0xFA, dead_addr & 0xFF, (dead_addr >> 8) & 0xFF)
	emit(0xB7)  # or a
	jr_not_dead = jr(0x28)  # jr z, update_live
	emit(0xAF)  # a = 0 (hidden y)
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)
	emit(0xC9)
	update_live_addr = len(code)
	patch_jr(jr_not_dead, update_live_addr)
	# Integrate gravity to velocity with a 1/16 accumulator.
	if grav_step_x != 0:
		grav_mag_x = max(1, min(32, abs(int(grav_step_x))))
		emit(0xFA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # ld a,(gacc_x)
		emit(0xC6, grav_mag_x & 0xFF)  # add a, grav_mag_x
		emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # store acc
		emit(0xFE, 16)  # cp 16
		jr_x_no_v = jr(0x38)  # jr c, no_vx_step
		emit(0xD6, 16)  # sub 16
		emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
		emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(vx)
		emit(0x3C if grav_step_x > 0 else 0x3D)  # inc/dec a
		emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # (vx)=a
		x_no_v_addr = len(code)
		patch_jr(jr_x_no_v, x_no_v_addr)
	emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
	emit(0x47)  # ld b,a (vx)
	# x += vx
	emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	emit(0x80)  # add a,b
	emit(0xFE, max_x & 0xFF)
	jr_store_x = jr(0x38)  # jr c, store_x
	ld_a_imm(max_x)
	store_x_addr = len(code)
	emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	if grav_step_y != 0:
		grav_mag_y = max(1, min(32, abs(int(grav_step_y))))
		emit(0xFA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # ld a,(gacc_y)
		emit(0xC6, grav_mag_y & 0xFF)  # add a, grav_mag_y
		emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # store acc
		emit(0xFE, 16)  # cp 16
		jr_y_no_v = jr(0x38)  # jr c, no_vy_step
		emit(0xD6, 16)  # sub 16
		emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
		emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
		emit(0x3C if grav_step_y > 0 else 0x3D)  # inc/dec a
		emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # (vy)=a
		y_no_v_addr = len(code)
		patch_jr(jr_y_no_v, y_no_v_addr)
	emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
	emit(0x47)  # ld b,a (vy)
	# y += vy
	emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	emit(0x80)  # add a,b
	emit(0xEA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	# Runtime collider pass: resolve downward contacts against authored collider AABBs.
	if collider_count > 0:
		emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
		emit(0xB7)  # or a
		jr_skip_collider_pass = jr(0x28)  # jr z, no collider step
		emit(0xCB, 0x7F)  # bit 7,a
		jr_skip_collider_neg = jr(0x20)  # jr nz, no collider step
		ld_hl_imm(collider_data_addr)
		emit(0x0E, collider_count & 0xFF)  # ld c, collider_count
		collider_loop_addr = len(code)
		emit(0x79)  # ld a,c
		emit(0xB7)  # or a
		jr_collider_done_zero = jr(0x28)  # jr z, done
		emit(0x2A)  # ld a,(hl+) ; collider x
		emit(0x57)  # ld d,a
		emit(0x2A)  # ld a,(hl+) ; collider y
		emit(0x5F)  # ld e,a
		emit(0x2A)  # ld a,(hl+) ; collider w
		emit(0x47)  # ld b,a
		emit(0x23)  # inc hl ; skip collider h (reserved for phase-2)
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)  # ld a,(x)
		emit(0xC6, sprite_w_px & 0xFF)  # add a, sprite_w
		emit(0xBA)  # cp d
		jr_collider_next_x_before = jr(0x38)  # jr c, next
		jr_collider_next_x_touch = jr(0x28)  # jr z, next
		emit(0x7A)  # ld a,d
		emit(0x80)  # add a,b ; a = collider_right
		emit(0x47)  # ld b,a
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)  # ld a,(x)
		emit(0xB8)  # cp b
		jr_collider_next_x_after = jr(0x30)  # jr nc, next
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
		emit(0xBB)  # cp e
		jr_collider_next_y_below_top = jr(0x30)  # jr nc, next
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
		emit(0xC6, sprite_h_px & 0xFF)  # add a, sprite_h
		emit(0xBB)  # cp e
		jr_collider_next_y_above_top = jr(0x38)  # jr c, next
		# Hit: snap sprite on top of collider and clear fall velocity.
		emit(0x7B)  # ld a,e
		emit(0xD6, sprite_h_px & 0xFF)  # sub sprite_h
		jr_store_hit_y = jr(0x30)  # jr nc, store_y
		emit(0xAF)  # xor a
		store_hit_y_addr = len(code)
		emit(0xEA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
		emit(0xAF)  # xor a
		emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
		emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
		jr_collider_done_hit = jr(0x18)  # jr done
		collider_next_addr = len(code)
		patch_jr(jr_collider_next_x_before, collider_next_addr)
		patch_jr(jr_collider_next_x_touch, collider_next_addr)
		patch_jr(jr_collider_next_x_after, collider_next_addr)
		patch_jr(jr_collider_next_y_below_top, collider_next_addr)
		patch_jr(jr_collider_next_y_above_top, collider_next_addr)
		emit(0x0D)  # dec c
		jr_collider_loop = jr(0x18)  # jr collider_loop
		collider_done_addr = len(code)
		patch_jr(jr_collider_done_zero, collider_done_addr)
		patch_jr(jr_collider_done_hit, collider_done_addr)
		patch_jr(jr_collider_loop, collider_loop_addr)
		patch_jr(jr_store_hit_y, store_hit_y_addr)
		collider_skip_addr = len(code)
		patch_jr(jr_skip_collider_pass, collider_skip_addr)
		patch_jr(jr_skip_collider_neg, collider_skip_addr)
	# Despawn once below visible screen range to prevent wrap-around reappearance.
	emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	emit(0xFE, offscreen_bottom_y & 0xFF)
	jr_not_despawn = jr(0x38)  # jr c, keep_visible
	ld_a_imm(1)
	emit(0xEA, dead_addr & 0xFF, (dead_addr >> 8) & 0xFF)
	emit(0xAF)  # hide all metasprite tiles
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)
	emit(0xC9)
	keep_visible_addr = len(code)
	patch_jr(jr_not_despawn, keep_visible_addr)
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
			emit(0xC6, (16 + row * 8) & 0xFF)
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)
			emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
			emit(0xC6, (8 + col * 8) & 0xFF)
			emit(0xEA, (base + 1) & 0xFF, ((base + 1) >> 8) & 0xFF)
	emit(0xC9)
	wait_vblank_addr = len(code)
	emit(0xF0, 0x44)  # ld a,[LY]
	emit(0xFE, 0x90)
	emit(0x30, 0xFA)  # jr nc, wait_end
	emit(0xF0, 0x44)
	emit(0xFE, 0x90)
	emit(0x38, 0xFA)  # jr c, wait_start
	emit(0xC9)
	copy_bg_addr = len(code)
	emit(0xD5); emit(0xC5)
	emit(0xAF); ldh_imm_a(0x4F)  # bank 0
	ld_de_imm(0x8000); ld_bc_imm(bg_tile_data_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc
	call_copy_bg_tiles_patch = len(code) - 2
	ld_de_imm(0x9800); ld_bc_imm(bg_tilemap_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc
	call_copy_bg_map_patch = len(code) - 2
	ld_a_imm(0x01); ldh_imm_a(0x4F)  # bank 1 attrs
	ld_de_imm(0x9800); ld_bc_imm(bg_attrmap_len)
	emit(0xCD, 0x00, 0x00)  # call copy_bc
	call_copy_bg_attr_patch = len(code) - 2
	emit(0xAF); ldh_imm_a(0x4F)
	emit(0xC1); emit(0xD1); emit(0xC9)
	copy_addr = len(code)
	emit(0x78); emit(0xB1); emit(0xC8)
	emit(0x2A); emit(0x12); emit(0x13); emit(0x0B)
	emit(0x18, 0xF7)
	def patch_call(pos, target):
		abs_addr = 0x150 + target
		code[pos] = abs_addr & 0xFF
		code[pos + 1] = (abs_addr >> 8) & 0xFF
	patch_jr(jr_loop, main_loop_addr)
	patch_jr(jr_store_x, store_x_addr)
	patch_call(call_copy_bg_patch, copy_bg_addr)
	patch_call(call_copy_sprite_patch, copy_addr)
	patch_call(call_wait_patch, wait_vblank_addr)
	patch_call(call_update_patch, update_addr)
	patch_call(call_copy_bg_tiles_patch, copy_addr)
	patch_call(call_copy_bg_map_patch, copy_addr)
	patch_call(call_copy_bg_attr_patch, copy_addr)
	return bytes(code)

def _gbc_build_dynamic_physics_rom (canvas_160x144, sprite_tile_bytes : bytes, sprite_tiles_w : int, sprite_tiles_h : int, init_x : int, init_y : int, bg_palette_bank, obj_palette4, collider_rects = None, grav_step_x : int = 0, grav_step_y : int = 1):
	tile_data_len = 384 * 16
	tilemap_len = 32 * 32
	attrmap_len = 32 * 32
	tile_data, tilemap, attrmap, palette_bank = _gbc_encode_tiles_and_map(canvas_160x144)
	if len(tile_data) > tile_data_len:
		raise RuntimeError('GBC dynamic physics export frame requires too many tiles.')
	tile_data = tile_data + b'\x00' * (tile_data_len - len(tile_data))
	if len(tilemap) != tilemap_len or len(attrmap) != attrmap_len:
		raise RuntimeError('GBC dynamic physics export map layout mismatch.')
	bg_palette_bytes = _gbc_palette_bytes_from_palette_bank(bg_palette_bank if bg_palette_bank is not None else palette_bank)
	obj_bank = [obj_palette4] + [_GBC_DEFAULT_BG_COLORS[: 4] for _ in range(7)]
	obj_palette_bytes = _gbc_palette_bytes_from_palette_bank(obj_bank)
	bg_payload = tile_data + tilemap + attrmap
	collider_rects = list(collider_rects or [])
	if len(collider_rects) > 31:
		print('GBC export: clamping runtime colliders to 31 entries (from', len(collider_rects), ').')
		collider_rects = collider_rects[: 31]
	collider_payload = bytearray()
	for x, y, w, h in collider_rects:
		collider_payload.extend([
			max(0, min(255, int(x))),
			max(0, min(255, int(y))),
			max(1, min(255, int(w))),
			max(1, min(255, int(h))),
		])
	code_start = 0x150
	rom_size = 0x8000
	sprite_tile_count = max(1, min(16, int((len(sprite_tile_bytes) if sprite_tile_bytes else 0) // 16)))
	collider_count = len(collider_payload) // 4
	probe = _gbc_build_dynamic_physics_program(0, tile_data_len, tilemap_len, attrmap_len, 0, sprite_tile_count, sprite_tiles_w, sprite_tiles_h, init_x, init_y, bg_palette_bytes, obj_palette_bytes, collider_data_addr = 0, collider_count = collider_count, grav_step_x = grav_step_x, grav_step_y = grav_step_y)
	bg_data_addr = code_start + len(probe)
	if bg_data_addr & 0xF:
		bg_data_addr += 0x10 - (bg_data_addr & 0xF)
	sprite_data_addr = bg_data_addr + len(bg_payload)
	collider_data_addr = sprite_data_addr + sprite_tile_count * 16
	code = _gbc_build_dynamic_physics_program(bg_data_addr, tile_data_len, tilemap_len, attrmap_len, sprite_data_addr, sprite_tile_count, sprite_tiles_w, sprite_tiles_h, init_x, init_y, bg_palette_bytes, obj_palette_bytes, collider_data_addr = collider_data_addr, collider_count = collider_count, grav_step_x = grav_step_x, grav_step_y = grav_step_y)
	total_need = collider_data_addr + len(collider_payload)
	if total_need > rom_size:
		raise RuntimeError('GBC dynamic physics export exceeds 32KB ROM size.')
	rom = bytearray(rom_size)
	rom[0x100 : 0x104] = bytes([0x00, 0xC3, 0x50, 0x01])
	rom[0x104 : 0x134] = _GBC_NINTENDO_LOGO
	title = b'JS13KGBCDYNPHY'
	rom[0x134 : 0x143] = title[: 15].ljust(15, b'\x00')
	rom[0x143] = 0xC0
	rom[0x144 : 0x146] = b'00'
	rom[0x146] = 0x00
	rom[0x147] = 0x00
	rom[0x148] = 0x00
	rom[0x149] = 0x00
	rom[0x14A] = 0x01
	rom[0x14B] = 0x33
	rom[0x14C] = 0x00
	rom[code_start : code_start + len(code)] = code
	rom[bg_data_addr : bg_data_addr + len(bg_payload)] = bg_payload
	sprite_payload = (sprite_tile_bytes or b'')
	if len(sprite_payload) < sprite_tile_count * 16:
		sprite_payload = sprite_payload + b'\x00' * (sprite_tile_count * 16 - len(sprite_payload))
	rom[sprite_data_addr : sprite_data_addr + sprite_tile_count * 16] = sprite_payload[: sprite_tile_count * 16]
	if collider_payload:
		rom[collider_data_addr : collider_data_addr + len(collider_payload)] = bytes(collider_payload)
	_gbc_compute_header_checksums(rom)
	print('GBC export: runtime mode = dynamic physics phase1 (single sprite), runtime colliders =', collider_count)
	return bytes(rom)

def _gbc_build_rom (canvas_160x144):
	canvases = canvas_160x144 if isinstance(canvas_160x144, list) else [canvas_160x144]
	canvases = [c for c in canvases if c is not None]
	if not canvases:
		raise RuntimeError('GBC export: no canvas frames to encode.')
	tile_data_len = 384 * 16
	tilemap_len = 32 * 32
	attrmap_len = 32 * 32
	encoded_frames = []
	palette_bank = None
	for i, frame_canvas in enumerate(canvases):
		tile_data, tilemap, attrmap, frame_palette = _gbc_encode_tiles_and_map(frame_canvas)
		if len(tile_data) > tile_data_len:
			raise RuntimeError('GBC export frame requires too many tiles.')
		tile_data = tile_data + b'\x00' * (tile_data_len - len(tile_data))
		if len(tilemap) != tilemap_len or len(attrmap) != attrmap_len:
			raise RuntimeError('GBC export map layout mismatch.')
		if i == 0:
			palette_bank = frame_palette
		encoded_frames.append((tile_data, tilemap, attrmap))
	palette_bytes = bytearray()
	default_pal = _GBC_DEFAULT_BG_COLORS[: 4]
	for p_idx in range(8):
		pal = palette_bank[p_idx] if p_idx < len(palette_bank) else default_pal
		for r, g, b in pal:
			c = _gba_pack_rgb555_le(r, g, b)
			palette_bytes.append(c & 0xFF)
			palette_bytes.append((c >> 8) & 0xFF)
	frame_stride = tile_data_len + tilemap_len + attrmap_len
	frame_count = len(encoded_frames)
	code_start = 0x150
	rom_size = 0x8000
	while True:
		code_template = _gbc_build_program(0, frame_stride, frame_count, tile_data_len, tilemap_len, attrmap_len, palette_bytes)
		frame_data_addr = code_start + len(code_template)
		if frame_data_addr & 0xF:
			frame_data_addr += 0x10 - (frame_data_addr & 0xF)
		need = frame_stride * frame_count
		if frame_data_addr + need <= rom_size:
			break
		if frame_count <= 1:
			raise RuntimeError('GBC export exceeds 32KB ROM size.')
		frame_count -= 1
		print('GBC export: limiting animated frames to', frame_count, 'to fit 32KB ROM.')
	code = _gbc_build_program(frame_data_addr, frame_stride, frame_count, tile_data_len, tilemap_len, attrmap_len, palette_bytes)
	frame_payload = bytearray()
	for tile_data, tilemap, attrmap in encoded_frames[: frame_count]:
		frame_payload.extend(tile_data)
		frame_payload.extend(tilemap)
		frame_payload.extend(attrmap)
	rom = bytearray(rom_size)
	rom[0x100 : 0x104] = bytes([0x00, 0xC3, 0x50, 0x01])
	rom[0x104 : 0x134] = _GBC_NINTENDO_LOGO
	title = b'JS13KGBCEXPORT'
	rom[0x134 : 0x143] = title[: 15].ljust(15, b'\x00')
	rom[0x143] = 0xC0  # CGB only
	rom[0x144 : 0x146] = b'00'
	rom[0x146] = 0x00
	rom[0x147] = 0x00
	rom[0x148] = 0x00
	rom[0x149] = 0x00
	rom[0x14A] = 0x01
	rom[0x14B] = 0x33
	rom[0x14C] = 0x00
	rom[code_start : code_start + len(code)] = code
	rom[frame_data_addr : frame_data_addr + len(frame_payload)] = frame_payload
	_gbc_compute_header_checksums(rom)
	print('GBC export: runtime mode = animated, frames =', frame_count)
	return bytes(rom)

def _gba_pack_rgb555_le (r : int, g : int, b : int):
	r = int(r)
	g = int(g)
	b = int(b)
	return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

def _gba_rgba_to_mode3 (rgba):
	out = bytearray(240 * 160 * 2)
	i = 0
	for y in range(160):
		for x in range(240):
			r, g, b, a = rgba[y, x]
			r = int(max(0, min(1, r)) * 255)
			g = int(max(0, min(1, g)) * 255)
			b = int(max(0, min(1, b)) * 255)
			al = max(0.0, min(1.0, a))
			if al < 1.0:
				r = int(r * al)
				g = int(g * al)
				b = int(b * al)
			h = _gba_pack_rgb555_le(r, g, b)
			out[i] = h & 0xFF
			out[i + 1] = (h >> 8) & 0xFF
			i += 2
	return out

def _gba_nn_resize_rgba (src, tw : int, th : int):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	sh, sw = src.shape[0], src.shape[1]
	if sw == 0 or sh == 0:
		return np.zeros((th, tw, 4), dtype = np.float32)
	ys = (np.arange(th, dtype = np.float32) * sh / th).astype(np.int32)
	xs = (np.arange(tw, dtype = np.float32) * sw / tw).astype(np.int32)
	ys = np.clip(ys, 0, sh - 1)
	xs = np.clip(xs, 0, sw - 1)
	return src[np.ix_(ys, xs)]

def _gba_resize_cover_rgba (src, tw : int, th : int):
	sw = int(src.shape[1])
	sh = int(src.shape[0])
	if sw <= 0 or sh <= 0:
		return _gba_nn_resize_rgba(src, tw, th)
	scale = max(float(tw) / float(sw), float(th) / float(sh))
	rw = max(1, int(round(sw * scale)))
	rh = max(1, int(round(sh * scale)))
	resized = _gba_nn_resize_rgba(src, rw, rh)
	x0 = max(0, (rw - tw) // 2)
	y0 = max(0, (rh - th) // 2)
	return resized[y0 : y0 + th, x0 : x0 + tw]

def _gba_cover_transform (sw : int, sh : int, tw : int, th : int):
	scale = max(float(tw) / float(sw), float(th) / float(sh))
	rw = max(1, int(round(sw * scale)))
	rh = max(1, int(round(sh * scale)))
	x0 = max(0, (rw - tw) // 2)
	y0 = max(0, (rh - th) // 2)
	return scale, x0, y0

def _gba_to_gbc_cover_point (x : float, y : float):
	scale, x0, y0 = _gba_cover_transform(240, 160, 160, 144)
	return int(round(float(x) * scale)) - x0, int(round(float(y) * scale)) - y0

def _gba_to_gbc_cover_len (v : float):
	scale, _, _ = _gba_cover_transform(240, 160, 160, 144)
	return max(1, int(round(float(v) * scale)))

def _gbc_collect_runtime_colliders (scene_obs, ignored_name : str = None):
	rects = []
	for ob in scene_obs or []:
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		if ignored_name and ob.name == ignored_name:
			continue
		if not getattr(ob, 'colliderExists', False):
			continue
		if not getattr(ob, 'colliderEnable', True):
			continue
		if getattr(ob, 'isSensor', False):
			continue
		shape = str(getattr(ob, 'colliderShapeType', ''))
		cx = float(ob.location.x) + float(getattr(ob, 'colliderPosOff', (0.0, 0.0))[0])
		cy = -float(ob.location.y) - float(getattr(ob, 'colliderPosOff', (0.0, 0.0))[1])
		w = 0.0
		h = 0.0
		if shape in ('cuboid', 'roundCuboid'):
			size = getattr(ob, 'colliderSize', (0.0, 0.0))
			w = float(size[0])
			h = float(size[1])
		elif shape == 'ball':
			r = float(getattr(ob, 'colliderRadius', 0.0))
			w = r * 2.0
			h = r * 2.0
		elif shape == 'capsule':
			r = float(getattr(ob, 'colliderCapsuleRadius', 0.0))
			ch = float(getattr(ob, 'colliderCapsuleHeight', 0.0))
			if bool(getattr(ob, 'colliderIsVertical', True)):
				w = r * 2.0
				h = ch + r * 2.0
			else:
				w = ch + r * 2.0
				h = r * 2.0
		else:
			continue
		if w <= 0.0 or h <= 0.0:
			continue
		cx_gbc, cy_gbc = _gba_to_gbc_cover_point(cx, cy)
		w_gbc = _gba_to_gbc_cover_len(w)
		h_gbc = _gba_to_gbc_cover_len(h)
		left = int(round(cx_gbc - w_gbc * 0.5))
		top = int(round(cy_gbc - h_gbc * 0.5))
		left = max(0, min(255, left))
		top = max(0, min(255, top))
		w_gbc = max(1, min(255 - left, int(w_gbc)))
		h_gbc = max(1, min(255 - top, int(h_gbc)))
		rects.append((left, top, w_gbc, h_gbc))
	return rects

def _gba_apply_tint_opacity_to_rgba (rgba, tint_rgb, opacity : float):
	if rgba is None:
		return None
	out = rgba.copy()
	out[:, :, 0] *= float(tint_rgb[0])
	out[:, :, 1] *= float(tint_rgb[1])
	out[:, :, 2] *= float(tint_rgb[2])
	out[:, :, 3] *= float(opacity)
	return out

def _gba_rotate_rgba_degrees (src, angle_deg):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	if abs(angle_deg) < 1e-7:
		return src
	h, w = int(src.shape[0]), int(src.shape[1])
	if h < 1 or w < 1:
		return src
	rad = math.radians(angle_deg)
	cos_a = math.cos(rad)
	sin_a = math.sin(rad)
	cx = (w - 1) * 0.5
	cy = (h - 1) * 0.5

	def rot_fwd(px, py):
		dx = px - cx
		dy = py - cy
		return (dx * cos_a + dy * sin_a + cx, -dx * sin_a + dy * cos_a + cy)

	minx = miny = float('inf')
	maxx = maxy = float('-inf')
	for px, py in ((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)):
		qx, qy = rot_fwd(px, py)
		minx = min(minx, qx)
		maxx = max(maxx, qx)
		miny = min(miny, qy)
		maxy = max(maxy, qy)

	ox0 = int(math.floor(minx + 1e-9))
	oy0 = int(math.floor(miny + 1e-9))
	out_w = max(1, int(math.ceil(maxx - 1e-9)) - ox0 + 1)
	out_h = max(1, int(math.ceil(maxy - 1e-9)) - oy0 + 1)

	yy, xx = np.mgrid[0 : out_h, 0 : out_w].astype(np.float32)
	qx = xx + float(ox0)
	qy = yy + float(oy0)
	dqx = qx - cx
	dqy = qy - cy
	sx = cos_a * dqx - sin_a * dqy + cx
	sy = sin_a * dqx + cos_a * dqy + cy

	x0 = np.floor(sx).astype(np.int32)
	y0 = np.floor(sy).astype(np.int32)
	x1 = x0 + 1
	y1 = y0 + 1
	wx = (sx - x0).astype(np.float32)
	wy = (sy - y0).astype(np.float32)
	wx = np.clip(wx, 0.0, 1.0)
	wy = np.clip(wy, 0.0, 1.0)

	valid = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
	x0c = np.clip(x0, 0, w - 1)
	x1c = np.clip(x1, 0, w - 1)
	y0c = np.clip(y0, 0, h - 1)
	y1c = np.clip(y1, 0, h - 1)

	c00 = src[y0c, x0c]
	c10 = src[y0c, x1c]
	c01 = src[y1c, x0c]
	c11 = src[y1c, x1c]
	one_wx = (1.0 - wx)[..., None]
	wx_ = wx[..., None]
	one_wy = (1.0 - wy)[..., None]
	wy_ = wy[..., None]
	out = one_wx * one_wy * c00 + wx_ * one_wy * c10 + one_wx * wy_ * c01 + wx_ * wy_ * c11
	out = out * valid[..., None].astype(np.float32)
	return out

def _gba_blit_rgba (canvas, src, x : int, y : int, tint_rgb, opacity : float):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	ch, cw = canvas.shape[0], canvas.shape[1]
	sh, sw = src.shape[0], src.shape[1]
	x0 = max(0, x)
	y0 = max(0, y)
	x1 = min(cw, x + sw)
	y1 = min(ch, y + sh)
	if x0 >= x1 or y0 >= y1:
		return
	sx0 = x0 - x
	sy0 = y0 - y
	dst = canvas[y0 : y1, x0 : x1]
	patch = src[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)].copy()
	patch[:, :, 0] *= tint_rgb[0]
	patch[:, :, 1] *= tint_rgb[1]
	patch[:, :, 2] *= tint_rgb[2]
	patch[:, :, 3] *= opacity
	alpha = patch[:, :, 3 : 4]
	dst[:] = (1.0 - alpha) * dst + alpha * patch

def _gba_load_saved_image_rgba (ob):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	img_path = os.path.join(TMP_DIR, GetFileName(ob.data.filepath))
	if not os.path.isfile(img_path):
		return None
	img_name = '__gba_' + GetFileName(img_path).replace('.', '_')
	prev = bpy.data.images.get(img_name)
	if prev:
		bpy.data.images.remove(prev)
	img = bpy.data.images.load(img_path)
	img.name = img_name
	w, h = img.size
	if w < 1 or h < 1:
		bpy.data.images.remove(img)
		return None
	pix = np.array(img.pixels[:], dtype = np.float32).reshape(h, w, 4)
	pix = pix[::-1, :, :]
	bpy.data.images.remove(img)
	return pix

def _gba_apply_script_surface_ops (image_surfaces : dict, surface_ops : list, frame : int = None, start_time : float = None, include_init : bool = True, include_update : bool = True):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	if not surface_ops:
		return image_surfaces
	owner_members = {}
	for owner_name, surf in image_surfaces.items():
		owner_members[owner_name] = {'surface' : surf}
	for op in surface_ops:
		is_init = bool(op.get('is_init', True))
		if is_init and not include_init:
			continue
		if (not is_init) and not include_update:
			continue
		owner_name = op.get('owner_name')
		if not owner_name:
			continue
		members = owner_members.setdefault(owner_name, {})
		member = op.get('member')
		_type = op.get('op')
		if _type == 'create_surface_member' and member:
			size = op.get('size') or [1, 1]
			w = max(1, int(size[0]))
			h = max(1, int(size[1]))
			members[member] = np.zeros((h, w, 4), dtype = np.float32)
		elif _type == 'assign_surface_member' and member:
			src_owner = op.get('src_owner_name') or owner_name
			src_member = op.get('src_member')
			src = owner_members.get(src_owner, {}).get(src_member) if src_member else None
			if src is not None:
				members[member] = src
		elif _type == 'fill_surface_member' and member:
			surf = members.get(member)
			if surf is None:
				continue
			clr = op.get('color') or [255, 255, 255, 255]
			rgba = []
			for i in range(4):
				v = _eval_runtime_expr_value(clr[i], frame = frame, start_time = start_time) if i < len(clr) else (255 if i < 3 else 255)
				if v is None:
					v = 255
				rgba.append(max(0, min(255, int(round(v)))))
			surf[:, :, 0] = rgba[0] / 255.0
			surf[:, :, 1] = rgba[1] / 255.0
			surf[:, :, 2] = rgba[2] / 255.0
			surf[:, :, 3] = rgba[3] / 255.0
		elif _type == 'draw_circle_surface_member' and member:
			surf = members.get(member)
			if surf is None:
				continue
			_gba_draw_circle_from_script(
				surf,
				{
					'center' : op.get('center') or [0.0, 0.0],
					'radius' : op.get('radius') or 0.0,
					'color' : op.get('color') or [255, 255, 255, 255],
					'width' : op.get('width') or 0.0,
					'condition' : op.get('condition'),
				},
				frame = frame,
				start_time = start_time,
			)
	for owner_name in list(image_surfaces.keys()):
		override = owner_members.get(owner_name, {}).get('surface')
		if override is not None:
			image_surfaces[owner_name] = override
	return image_surfaces

def _gba_apply_display_draw_circles (canvas, script_runtime, frame : int = None, start_time : float = None):
	if canvas is None:
		return canvas
	runtime = script_runtime or {}
	for circle in list(runtime.get('init_draw_circles') or []):
		_gba_draw_circle_from_script(canvas, circle, frame = frame, start_time = start_time)
	for circle in list(runtime.get('update_draw_circles') or []):
		_gba_draw_circle_from_script(canvas, circle, frame = frame, start_time = start_time)
	return canvas

def _gba_composite_scene (world, image_empties, image_surfaces = None, transform_overrides = None, script_runtime = None, frame : int = None):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('Export GBA requires NumPy (included with Blender).')
	bg = list(world.color)
	canvas = np.zeros((160, 240, 4), dtype = np.float32)
	canvas[:, :, 0] = bg[0]
	canvas[:, :, 1] = bg[1]
	canvas[:, :, 2] = bg[2]
	canvas[:, :, 3] = 1.0
	for ob in image_empties:
		pix = None
		if image_surfaces:
			pix = image_surfaces.get(ob.name)
		if pix is None:
			pix = _gba_load_saved_image_rgba(ob)
		if pix is None:
			continue
		size = ob.scale * ob.empty_display_size
		img_size = Vector(list(ob.data.size) + [0])
		if img_size.x > img_size.y:
			size.x *= img_size.x / img_size.y
		else:
			size.y *= img_size.y / img_size.x
		tw = max(1, int(round(abs(size.x))))
		th = max(1, int(round(abs(size.y))))
		scaled = _gba_nn_resize_rgba(pix, tw, th)
		override = None if not transform_overrides else transform_overrides.get(ob.name)
		if override:
			rot_deg = float(override.get('rot_deg', 0.0))
		else:
			rot_deg = math.degrees(ob.rotation_euler.z)
		if abs(rot_deg) > 1e-10:
			scaled = _gba_rotate_rgba_degrees(scaled, rot_deg)
		if override:
			pos = Vector((float(override.get('x', 0.0)), float(override.get('y', 0.0)), 0.0))
		else:
			pos = GetImagePosition(ob)
		tint = list(ob.tint)
		_gba_blit_rgba(canvas, scaled, int(pos.x), int(pos.y), tint, ob.color[3])
	_gba_apply_display_draw_circles(canvas, script_runtime, frame = frame)
	return canvas

def _gba_try_build_and_install_pyrapier2d ():
	pyrapier_repo = os.path.join(_thisDir, 'PyRapier2d')
	local_target = os.path.join(pyrapier_repo, '.pyrapier_site')
	if not os.path.isfile(os.path.join(pyrapier_repo, 'Cargo.toml')):
		print('GBA export: PyRapier2d repo missing Cargo.toml at', pyrapier_repo)
		return False
	env = os.environ.copy()
	env['PYO3_USE_ABI3_FORWARD_COMPATIBILITY'] = '1'
	if sys.platform.startswith('linux'):
		env['PIP_BREAK_SYSTEM_PACKAGES'] = '1'
	for cargo_path in [os.path.expanduser('~/.cargo/bin'), '/usr/bin', '/usr/local/bin']:
		if os.path.isdir(cargo_path) and cargo_path not in env.get('PATH', ''):
			env['PATH'] = cargo_path + os.pathsep + env.get('PATH', '')
	python_execs = []
	for exe in [
		getattr(sys, 'executable', None),
		getattr(sys, '_base_executable', None),
		getattr(getattr(bpy, 'app', None), 'binary_path_python', None) if bpy else None,
		shutil.which('python3'),
		shutil.which('python'),
	]:
		if exe and exe not in python_execs:
			python_execs.append(exe)
	if python_execs == []:
		print('GBA export: no Python executable found for building PyRapier2d.')
		return False
	def _run(exe, args):
		cmd = [exe] + args
		try:
			return subprocess.run(cmd, cwd = pyrapier_repo, env = env, capture_output = True, text = True, check = False), None
		except Exception as e:
			return None, e
	last_err = ''
	for exe in python_execs:
		proc, exc = _run(exe, ['-m', 'maturin', 'develop', '--release'])
		if proc and proc.returncode == 0:
			print('GBA export: installed PyRapier2d via maturin develop using', exe)
			return True
		if exc:
			last_err = str(exc)
		elif proc:
			last_err = (proc.stderr or proc.stdout or '').strip()
	for exe in python_execs:
		pip_install_maturin = ['-m', 'pip', 'install', '--user', 'maturin']
		pip_install_wheel = ['-m', 'pip', 'install', '--user', '--force-reinstall']
		pip_install_wheel_target = ['-m', 'pip', 'install', '--upgrade', '--force-reinstall', '--target', local_target]
		if sys.platform.startswith('linux'):
			pip_install_maturin.append('--break-system-packages')
			pip_install_wheel.append('--break-system-packages')
			pip_install_wheel_target.append('--break-system-packages')
		_run(exe, pip_install_maturin)
		proc, exc = _run(exe, ['-m', 'maturin', 'build', '--release'])
		if not proc or proc.returncode != 0:
			if exc:
				last_err = str(exc)
			elif proc:
				last_err = (proc.stderr or proc.stdout or '').strip()
			continue
		wheels_dir = os.path.join(pyrapier_repo, 'target', 'wheels')
		if not os.path.isdir(wheels_dir):
			last_err = 'maturin build succeeded but wheels directory was not created'
			continue
		wheels = sorted([f for f in os.listdir(wheels_dir) if f.endswith('.whl')], reverse = True)
		if not wheels:
			last_err = 'maturin build succeeded but no wheel was produced'
			continue
		wheel_path = os.path.join(wheels_dir, wheels[0])
		proc, exc = _run(exe, pip_install_wheel + [wheel_path])
		if proc and proc.returncode == 0:
			print('GBA export: installed PyRapier2d wheel for current Python using', exe)
			return True
		proc_target, exc_target = _run(exe, pip_install_wheel_target + [wheel_path])
		if proc_target and proc_target.returncode == 0:
			print('GBA export: installed PyRapier2d wheel into local target', local_target, 'using', exe)
			return True
		if exc:
			last_err = str(exc)
		elif proc:
			last_err = (proc.stderr or proc.stdout or '').strip()
		if exc_target:
			last_err = str(exc_target)
		elif proc_target:
			last_err = (proc_target.stderr or proc_target.stdout or '').strip()
	if last_err:
		last_err = last_err[: 500]
		print('GBA export: failed to build/install PyRapier2d:', last_err)
	else:
		print('GBA export: failed to build/install PyRapier2d (no error text available).')
	return False

def _gba_try_import_pyrapier2d ():
	import importlib
	import os
	import site
	import sys
	def _import_pyrapier(remove_shadow_paths = False):
		original = None
		removed = []
		local_target = os.path.join(_thisDir, 'PyRapier2d', '.pyrapier_site')
		added_paths = []
		if remove_shadow_paths:
			cwd = os.path.abspath(os.getcwd())
			for p in list(sys.path):
				path = p or cwd
				candidate = os.path.join(path, 'PyRapier2d')
				if os.path.isdir(candidate) and not os.path.isfile(os.path.join(candidate, '__init__.py')):
					removed.append(p)
			if removed:
				print('GBA export: removing namespace-shadow paths for PyRapier2d import:', removed)
				original = list(sys.path)
				sys.path = [p for p in sys.path if p not in removed]
		for extra in [local_target, site.getusersitepackages()]:
			if extra and os.path.isdir(extra) and extra not in sys.path:
				sys.path.insert(0, extra)
				added_paths.append(extra)
		try:
			if 'PyRapier2d' in sys.modules:
				del sys.modules['PyRapier2d']
			mod_local = importlib.import_module('PyRapier2d')
			return mod_local
		except Exception:
			return None
		finally:
			for p in added_paths:
				if p in sys.path:
					sys.path.remove(p)
			if original is not None:
				sys.path = original
	try:
		mod = importlib.import_module('PyRapier2d')
		if hasattr(mod, 'Simulation'):
			return mod
	except Exception:
		mod = None
	mod2 = _import_pyrapier(remove_shadow_paths = True)
	if mod2 is not None:
		mod = mod2
		if hasattr(mod2, 'Simulation'):
			return mod2
	if _gba_try_build_and_install_pyrapier2d():
		mod3 = _import_pyrapier(remove_shadow_paths = True)
		if mod3 is not None:
			mod = mod3
			if hasattr(mod3, 'Simulation'):
				print('GBA export: PyRapier2d recovered after local build/install.')
				return mod3
	mod_file = getattr(mod, '__file__', None) if mod else None
	mod_path = getattr(mod, '__path__', None) if mod else None
	if mod_path:
		print('GBA export: PyRapier2d namespace paths:', list(mod_path))
	print('GBA export: PyRapier2d import resolved to', mod_file or '<namespace package>', 'without Simulation; skipping Rapier bake.')
	return None

def _gba_get_collision_groups (ob):
	membership = 0
	for i, enabled in enumerate(ob.collisionGroupMembership):
		if enabled:
			membership |= (1 << i)
	filter_mask = 0
	for i, enabled in enumerate(ob.collisionGroupFilter):
		if enabled:
			filter_mask |= (1 << i)
	return membership, filter_mask

def _gba_get_image_size (ob):
	size = ob.scale * ob.empty_display_size
	img_size = Vector(list(ob.data.size) + [0])
	if img_size.x > img_size.y:
		size.x *= img_size.x / img_size.y
	else:
		size.y *= img_size.y / img_size.x
	return max(1.0, abs(size.x)), max(1.0, abs(size.y))

def _gba_get_object_size (ob):
	if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE' and ob.data:
		return _gba_get_image_size(ob)
	x_coords = [v[0] for v in ob.bound_box]
	y_coords = [v[1] for v in ob.bound_box]
	w = max(1.0, abs(max(x_coords) - min(x_coords)) * abs(ob.scale.x))
	h = max(1.0, abs(max(y_coords) - min(y_coords)) * abs(ob.scale.y))
	return w, h

def _gba_get_object_pose (ob):
	prev_rot_mode = ob.rotation_mode
	ob.rotation_mode = 'XYZ'
	rot_deg = math.degrees(ob.rotation_euler.z)
	if ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE':
		pos = GetImagePosition(ob)
	else:
		pos = GetObjectPosition(ob)
	ob.rotation_mode = prev_rot_mode
	return [float(pos.x), float(pos.y)], float(rot_deg)

def _gba_add_cuboid_collider_for_object (sim, ob, membership, filter_mask, attach_to = None):
	pos, rot_deg = _gba_get_object_pose(ob)
	w, h = _gba_get_object_size(ob)
	return sim.add_cuboid_collider(
		ob.colliderEnable,
		pos,
		rot_deg + ob.colliderRotOff,
		membership,
		filter_mask,
		[w, h],
		ob.isSensor,
		ob.density,
		ob.bounciness,
		BOUNCINESS_COMBINE_RULES.index(ob.bouncinessCombineRule),
		attach_to,
	)

def _gba_generate_rapier_frames (world, scene_obs, image_empties, image_surfaces, script_runtime):
	if not getattr(world, 'usePhysics', True):
		return None
	py_rapier = _gba_try_import_pyrapier2d()
	if not py_rapier:
		print('GBA export: PyRapier2d not available; exporting a single static frame.')
		return None
	physics_obs = [ob for ob in scene_obs if ob.exportOb and not ob.hide_get() and (getattr(ob, 'rigidBodyExists', False) or getattr(ob, 'colliderExists', False))]
	if not physics_obs:
		return None
	sim = py_rapier.Simulation()
	sim.set_length_unit (float(world.unitLen))
	gravity = [0, 0]
	if bpy.context.scene.use_gravity:
		g = list(bpy.context.scene.gravity)
		gravity = [g[0], g[1]]
	sim.set_gravity (gravity[0], gravity[1])
	rigid_bodies = {}
	for ob in physics_obs:
		if not getattr(ob, 'rigidBodyExists', False):
			continue
		pos, rot_deg = _gba_get_object_pose(ob)
		_type = RIGID_BODY_TYPES.index(ob.rigidBodyType) if ob.rigidBodyType in RIGID_BODY_TYPES else 0
		rigid_bodies[ob.name] = sim.add_rigid_body(
			ob.rigidBodyEnable,
			_type,
			pos,
			rot_deg,
			ob.gravityScale,
			ob.dominance,
			ob.canRot,
			ob.linearDrag,
			ob.angDrag,
			ob.canSleep,
			ob.continuousCollideDetect,
		)
	for ob in physics_obs:
		membership, filter_mask = _gba_get_collision_groups(ob)
		attach_targets = []
		for i in range(MAX_ATTACH_COLLIDER_CNT):
			if getattr(ob, 'attach%i' %i):
				attach_ob = getattr(ob, 'attachTo%i' %i)
				if attach_ob and attach_ob.name in rigid_bodies:
					attach_targets.append(rigid_bodies[attach_ob.name])
		if ob.name in rigid_bodies and not attach_targets:
			attach_targets = [rigid_bodies[ob.name]]
		if getattr(ob, 'colliderExists', False):
			for attach_to in (attach_targets or [None]):
				_gba_add_cuboid_collider_for_object(sim, ob, membership, filter_mask, attach_to = attach_to)
		elif ob.name in rigid_bodies:
			for attach_to in attach_targets:
				_gba_add_cuboid_collider_for_object(sim, ob, membership, filter_mask, attach_to = attach_to)
	def _rotate2d (x, y, deg):
		r = math.radians(deg)
		c = math.cos(r)
		s = math.sin(r)
		return (x * c - y * s, x * s + y * c)
	image_bindings = {}
	for image_ob in image_empties:
		controller = image_ob if image_ob.name in rigid_bodies else None
		if controller is None:
			parent = image_ob.parent
			while parent:
				if parent.name in rigid_bodies:
					controller = parent
					break
				parent = parent.parent
		if controller is None:
			continue
		img_pos0, img_rot0 = _gba_get_object_pose(image_ob)
		body_pos0, body_rot0 = _gba_get_object_pose(controller)
		dx = img_pos0[0] - body_pos0[0]
		dy = img_pos0[1] - body_pos0[1]
		local_x, local_y = _rotate2d(dx, dy, -body_rot0)
		image_bindings[image_ob.name] = {
			'handle' : rigid_bodies[controller.name],
			'local_x' : local_x,
			'local_y' : local_y,
			'rot_off' : img_rot0 - body_rot0,
		}
	frame_count = int(max(1, min(360, getattr(world, 'bakedPhysicsFrames', 120))))
	any_dynamic = any(getattr(ob, 'rigidBodyExists', False) and getattr(ob, 'rigidBodyType', '') == 'dynamic' and getattr(ob, 'rigidBodyEnable', True) for ob in physics_obs)
	if not any_dynamic:
		frame_count = 1
	frames = []
	debug_first = None
	debug_last = None
	_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = 1, include_init = True, include_update = False)
	for frame in range(frame_count):
		_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = frame + 1, include_init = False, include_update = True)
		transform_overrides = {}
		for ob in image_empties:
			binding = image_bindings.get(ob.name)
			if binding:
				pos = sim.get_rigid_body_position(binding['handle'])
				rot = sim.get_rigid_body_rotation(binding['handle'])
				if pos is not None and rot is not None:
					off_x, off_y = _rotate2d(binding['local_x'], binding['local_y'], rot)
					transform_overrides[ob.name] = {
						'x' : pos[0] + off_x,
						'y' : pos[1] + off_y,
						'rot_deg' : rot + binding['rot_off'],
					}
		canvas = _gba_composite_scene(world, image_empties, image_surfaces = image_surfaces, transform_overrides = transform_overrides, script_runtime = script_runtime, frame = frame + 1)
		frames.append(_gba_rgba_to_mode3(canvas))
		if frame + 1 < frame_count:
			sim.step ()
	print('GBA export: baked', len(frames), 'Rapier frame(s) for runtime playback.')
	return frames

def _gba_has_update_visuals (script_runtime):
	runtime = script_runtime or {}
	if list(runtime.get('update_draw_circles') or []):
		return True
	for op in list(runtime.get('surface_ops') or []):
		if not bool(op.get('is_init', True)):
			return True
	return False

def _gba_generate_script_only_frames (world, image_empties, image_surfaces, script_runtime):
	if not _gba_has_update_visuals(script_runtime):
		return None
	frame_count = int(max(1, min(360, getattr(world, 'bakedPhysicsFrames', 120))))
	if frame_count <= 1:
		return None
	frames = []
	_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = 1, include_init = True, include_update = False)
	for frame in range(frame_count):
		_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = frame + 1, include_init = False, include_update = True)
		canvas = _gba_composite_scene(world, image_empties, image_surfaces = image_surfaces, script_runtime = script_runtime, frame = frame + 1)
		frames.append(_gba_rgba_to_mode3(canvas))
	print('GBA export: baked', len(frames), 'script-driven frame(s) for runtime playback.')
	return frames

def _gbc_generate_script_canvases (world, image_empties, image_surfaces, script_runtime):
	if not _gba_has_update_visuals(script_runtime):
		return None
	frame_count = int(max(1, min(360, getattr(world, 'bakedPhysicsFrames', 120))))
	if frame_count <= 1:
		return None
	# GBC ROM is 32KB; frame payloads are large, so cap bake upfront.
	frame_count = min(frame_count, 8)
	canvases = []
	_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = 1, include_init = True, include_update = False)
	for frame in range(frame_count):
		_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = frame + 1, include_init = False, include_update = True)
		canvas_gba_space = _gba_composite_scene(world, image_empties, image_surfaces = image_surfaces, script_runtime = script_runtime, frame = frame + 1)
		canvases.append(_gba_resize_cover_rgba(canvas_gba_space, 160, 144))
	print('GBC export: baked', len(canvases), 'script-driven frame(s) for runtime playback.')
	return canvases

def _gba_build_runtime_code_linked (script_runtime : dict, bitmap_rom_offset : int, frame_count : int = 1):
	asm_path = script_runtime.get('assembly_path') if script_runtime else None
	init_symbols = list(script_runtime.get('init_symbols') or []) if script_runtime else []
	update_symbols = list(script_runtime.get('update_symbols') or []) if script_runtime else []
	frame_count = max(1, int(frame_count))
	clang = shutil.which('clang')
	ld_lld = shutil.which('ld.lld')
	objcopy = shutil.which('llvm-objcopy') or shutil.which('objcopy')
	if not clang or not ld_lld or not objcopy:
		print('GBA export: missing clang/ld.lld/objcopy; using fallback runtime (no per-frame gba-py execution).')
		return None
	script_asm = ''
	if asm_path and os.path.isfile(asm_path):
		try:
			script_asm = open(asm_path, 'r', encoding = 'utf-8').read()
		except Exception as e:
			print('GBA export: failed to read gba-py assembly for linking:', e)
			return None
	script_asm = re.sub(
		r'\n\t\.weak py2gba_builtin_print\n\t\.thumb_func\npy2gba_builtin_print:\n\tbx\tlr\n',
		'\n',
		script_asm,
		flags = re.MULTILINE,
	)
	init_calls = '\n'.join('\tbl\t' + sym for sym in init_symbols) if init_symbols else '\t@ no init script calls'
	update_calls = '\n'.join('\tbl\t' + sym for sym in update_symbols) if update_symbols else '\t@ no update script calls'
	main_loop_body = '\n'.join([
		'\tbl\tpy2gba_wait_vblank',
		'\t@ no baked frame playback; keep VRAM live between updates',
		'\tbl\tpy2gba_call_update',
	])
	frame_base_rom = 0x08000000 + bitmap_rom_offset
	frame_stride = 240 * 160 * 2
	frame_end_rom = frame_base_rom + frame_stride * frame_count
	runtime_asm = f'''.syntax unified
.cpu arm7tdmi
.fpu softvfp

.section .text
.arm
.global gba_entry
gba_entry:
\tadr\tr0, gba_thumb_entry + 1
\tbx\tr0

.thumb
.thumb_func
gba_thumb_entry:
\tldr\tr0, =0x04000000
\tmovs\tr1, #3
\tstrb\tr1, [r0]
\tmovs\tr1, #4
\tstrb\tr1, [r0, #1]
\tldr\tr6, =0x0203FFFC
\tldr\tr7, =0x{frame_base_rom:08X}
\tstr\tr7, [r6]
\tbl\tpy2gba_blit_frame
\tbl\tpy2gba_call_init
gba_main_loop:
{main_loop_body}
\tb\tgba_main_loop

.thumb_func
py2gba_wait_vblank:
\tldr\tr1, =0x04000006
py2gba_wait_vblank_end:
\tldrh\tr0, [r1]
\tcmp\tr0, #160
\tbhs\tpy2gba_wait_vblank_end
py2gba_wait_vblank_start:
\tldrh\tr0, [r1]
\tcmp\tr0, #160
\tblo\tpy2gba_wait_vblank_start
\tbx\tlr

.thumb_func
py2gba_blit_frame:
\tpush\t{{r4-r7, lr}}
\tldr\tr6, =0x0203FFFC
\tldr\tr1, [r6]
\tldr\tr2, =0x06000000
\tldr\tr3, =240 * 160 * 2
py2gba_blit_copy_loop:
\tldr\tr4, [r1]
\tstr\tr4, [r2]
\tadds\tr1, #4
\tadds\tr2, #4
\tsubs\tr3, #4
\tbne\tpy2gba_blit_copy_loop
\tldr\tr0, =0x{frame_stride:08X}
\tadds\tr1, r0
\tldr\tr0, =0x{frame_end_rom:08X}
\tcmp\tr1, r0
\tblo\tpy2gba_blit_store
\tldr\tr1, =0x{frame_base_rom:08X}
py2gba_blit_store:
\tstr\tr1, [r6]
\tpop\t{{r4-r7, pc}}

.thumb_func
py2gba_call_init:
\tpush\t{{lr}}
{init_calls}
\tpop\t{{pc}}

.thumb_func
py2gba_call_update:
\tpush\t{{lr}}
{update_calls}
\tpop\t{{pc}}

.global py2gba_builtin_print
.thumb_func
py2gba_builtin_print:
\tpush\t{{r1-r7, lr}}
\tldr\tr1, =0x04FFF780
\tldr\tr2, =0x0000C0DE
\tstrh\tr2, [r1]
\tldrh\tr2, [r1]
\tldr\tr3, =0x00001DEA
\tcmp\tr2, r3
\tbne\tpy2gba_print_done
\tldr\tr1, =0x04FFF600
\tadds\tr2, r0, #0
\tmovs\tr6, #0
py2gba_print_copy:
\tcmp\tr6, #255
\tbhs\tpy2gba_print_copy_end
\tldrb\tr3, [r2]
\tstrb\tr3, [r1]
\tadds\tr2, #1
\tadds\tr1, #1
\tadds\tr6, #1
\tcmp\tr3, #0
\tbne\tpy2gba_print_copy
\tb\tpy2gba_print_after_copy
py2gba_print_copy_end:
\tmovs\tr3, #0
\tstrb\tr3, [r1]
py2gba_print_after_copy:
\tsubs\tr1, #1
\tldr\tr4, =py2gba_print_counter
\tldrb\tr5, [r4]
\tadds\tr5, #1
\tstrb\tr5, [r4]
\tmovs\tr3, #32
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tmovs\tr3, #91
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tldr\tr6, =py2gba_hex_chars
\tlsrs\tr7, r5, #4
\tldrb\tr7, [r6, r7]
\tstrb\tr7, [r1]
\tadds\tr1, #1
\tmovs\tr7, #15
\tands\tr7, r5
\tldrb\tr7, [r6, r7]
\tstrb\tr7, [r1]
\tadds\tr1, #1
\tmovs\tr3, #93
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tmovs\tr3, #10
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tmovs\tr3, #0
\tstrb\tr3, [r1]
\tldr\tr1, =0x04FFF700
\tldr\tr2, =0x00000103
\tstrh\tr2, [r1]
\t
py2gba_print_done:
\tpop\t{{r1-r7, pc}}

\t.align 2
py2gba_print_counter:
\t.word 0
py2gba_hex_chars:
\t.ascii "0123456789ABCDEF"
'''
	full_asm = runtime_asm + '\n\n' + script_asm
	base = os.path.join(TMP_DIR, 'gba_link_runtime')
	asm_file = base + '.s'
	obj_file = base + '.o'
	elf_file = base + '.elf'
	bin_file = base + '.bin'
	ld_file = base + '.ld'
	ld_script = '''SECTIONS
{
	. = 0x08000200;
	.text : { *(.text*) *(.rodata*) }
}
'''
	open(asm_file, 'w', encoding = 'utf-8').write(full_asm)
	open(ld_file, 'w', encoding = 'utf-8').write(ld_script)
	cmd_asm = [clang, '--target=armv4t-none-eabi', '-c', asm_file, '-o', obj_file]
	cmd_ld = [ld_lld, '-flavor', 'gnu', '-m', 'armelf', '-T', ld_file, '--entry=gba_entry', '-nostdlib', '-o', elf_file, obj_file]
	cmd_objcopy = [objcopy, '-O', 'binary', elf_file, bin_file]
	try:
		print(' '.join(cmd_asm))
		subprocess.run(cmd_asm, check = True, capture_output = True, text = True)
		print(' '.join(cmd_ld))
		subprocess.run(cmd_ld, check = True, capture_output = True, text = True)
		print(' '.join(cmd_objcopy))
		subprocess.run(cmd_objcopy, check = True, capture_output = True, text = True)
	except subprocess.CalledProcessError as e:
		print('GBA export: linked runtime build failed:', e.stderr or e.stdout or str(e))
		return None
	return open(bin_file, 'rb').read()

def _gba_build_rom_mode3 (pixel_bytes : bytes, bitmap_rom_offset : int, script_runtime = None, frame_count : int = 1):
	CODE_START = 0x200
	frame_count = max(1, int(frame_count))
	code_bytes = _gba_build_runtime_code_linked(script_runtime or {}, bitmap_rom_offset, frame_count = frame_count)
	if code_bytes:
		target_bitmap_offset = max(bitmap_rom_offset, CODE_START + len(code_bytes))
		target_bitmap_offset = (target_bitmap_offset + 3) & ~3
		if target_bitmap_offset != bitmap_rom_offset:
			bitmap_rom_offset = target_bitmap_offset
			code_bytes = _gba_build_runtime_code_linked(script_runtime or {}, bitmap_rom_offset, frame_count = frame_count) or code_bytes
			bitmap_rom_offset = max(bitmap_rom_offset, CODE_START + len(code_bytes))
			bitmap_rom_offset = (bitmap_rom_offset + 3) & ~3
	else:
		raise RuntimeError('GBA export requires linked runtime (clang + ld.lld + llvm-objcopy/objcopy). Static fallback rendering is disabled.')
	print('GBA export: runtime mode = linked, frames =', frame_count, ', pixel_bytes =', len(pixel_bytes))
	rom_len = bitmap_rom_offset + len(pixel_bytes)
	rom = bytearray(rom_len)
	struct.pack_into('<I', rom, 0, 0xEA000000 | (((CODE_START - 8) // 4) & 0xFFFFFF))
	rom[0x04 : 0x04 + len(_GBA_NINTENDO_LOGO)] = _GBA_NINTENDO_LOGO
	title = b'JS13KGBAEXP'
	rom[0xA0 : 0xAC] = title[: 12].ljust(12, b'\x00')
	rom[0xAC : 0xB0] = b'JS13'
	rom[0xB0] = 0x30
	rom[0xB2] = 0x96
	rom[0xB3] = 0x00
	rom[0xB4] = 0x00
	rom[0xBC] = 0x00
	rom[CODE_START : CODE_START + len(code_bytes)] = code_bytes
	rom[bitmap_rom_offset : bitmap_rom_offset + len(pixel_bytes)] = pixel_bytes
	_gba_complement_check(rom)
	return bytes(rom)

def _gb_scene_has_physics (scene_obs):
	for ob in scene_obs or []:
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		if getattr(ob, 'rigidBodyExists', False) or getattr(ob, 'colliderExists', False):
			return True
	return False

def _gb_runtime_is_stubbed (script_runtime):
	asm_path = (script_runtime or {}).get('assembly_path')
	if not asm_path or not os.path.isfile(asm_path):
		return False
	try:
		asm_txt = open(asm_path, 'r', encoding = 'utf-8').read(512)
	except Exception:
		return False
	return 'py2gba pygame-aware stub backend' in asm_txt

def BuildGba (world):
	PreBuild ()
	try:
		try:
			import numpy
		except ImportError:
			raise RuntimeError('GBA export needs NumPy.')
		scene_obs = list(bpy.context.scene.collection.all_objects)
		gba_imgs = []
		for ob in scene_obs:
			if not ob.exportOb or ob.hide_get():
				continue
			if ob.type != 'EMPTY' or ob.empty_display_type != 'IMAGE' or not ob.data or not ob.data.filepath:
				continue
			gba_imgs.append(ob)
		if not gba_imgs:
			print('GBA export: no image empties with Export object enabled; wrote blank screen.')
		gba_imgs.sort(key = lambda o: o.location.z)
		for ob in gba_imgs:
			img_path = os.path.join(TMP_DIR, GetFileName(ob.data.filepath))
			prev_rot = ob.rotation_mode
			ob.rotation_mode = 'XYZ'
			ob.data.save(filepath = img_path)
			ob.rotation_mode = prev_rot
		bitmap_off = 0x300
		out = os.path.expanduser(world.gbaPath).replace('\\', '/')
		if not out:
			out = TMP_DIR + '/' + bpy.path.basename(bpy.data.filepath).replace('.blend', '') + '.gba'
		elif not out.lower().endswith('.gba'):
			out += '.gba'
		script_runtime = ExportGbaPyAssembly(world, out)
		image_surfaces = {}
		for ob in gba_imgs:
			pix = _gba_load_saved_image_rgba(ob)
			if pix is not None:
				image_surfaces[ob.name] = pix
		has_physics = bool(getattr(world, 'usePhysics', True)) and _gb_scene_has_physics(scene_obs)
		if has_physics:
			update_symbols = list((script_runtime or {}).get('update_symbols') or [])
			if not update_symbols:
				raise RuntimeError(
					'GBA dynamic physics requires runtime update code, but no update symbols were generated. '
					'Blender rigid-body playback bake is disabled, so add gba-py update scripts or disable physics for GBA export.'
				)
			if _gb_runtime_is_stubbed(script_runtime):
				raise RuntimeError(
					'GBA dynamic physics requires a full py2gba compiler/runtime; the current py2gba backend is a pygame stub. '
					'Install/use full Py2Gb toolchain to execute real update logic on-device.'
				)
		frame_count = 1
		_gba_apply_script_surface_ops(image_surfaces, script_runtime.get('surface_ops', []), frame = 1, include_init = True, include_update = False)
		canvas = _gba_composite_scene(world, gba_imgs, image_surfaces = image_surfaces, script_runtime = script_runtime, frame = 1)
		pixel_bytes = _gba_rgba_to_mode3(canvas)
		print('GBA export: baked playback disabled; runtime is dynamic-only.')
		rom = _gba_build_rom_mode3(pixel_bytes, bitmap_off, script_runtime, frame_count = frame_count)
		MakeFolderForFile(out)
		open(out, 'wb').write(rom)
		print('Saved GBA ROM:', out, '(%i bytes)' %len(rom))
		rom_path = os.path.abspath(out)
		try:
			proc = subprocess.Popen(
				['mgba-qt', '-d', '--log-level', '255', '-C', 'logToStdout=true', rom_path],
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				text = True,
				bufsize = 1,
			)
			_pipe_process_output_to_terminal(proc, prefix = 'mGBA')
			_start_gba_update_print_mirror(proc, script_runtime)
		except FileNotFoundError:
			print('mgba-qt not found in PATH; open the ROM manually:', rom_path)
	finally:
		PostBuild ()

def BuildGbc (world):
	PreBuild ()
	try:
		try:
			import numpy
		except ImportError:
			raise RuntimeError('GBC export needs NumPy.')
		scene_obs = list(bpy.context.scene.collection.all_objects)
		gbc_imgs = []
		for ob in scene_obs:
			if not ob.exportOb or ob.hide_get():
				continue
			if ob.type != 'EMPTY' or ob.empty_display_type != 'IMAGE' or not ob.data or not ob.data.filepath:
				continue
			gbc_imgs.append(ob)
		if not gbc_imgs:
			print('GBC export: no image empties with Export object enabled; wrote blank screen.')
		gbc_imgs.sort(key = lambda o: o.location.z)
		for ob in gbc_imgs:
			img_path = os.path.join(TMP_DIR, GetFileName(ob.data.filepath))
			prev_rot = ob.rotation_mode
			ob.rotation_mode = 'XYZ'
			ob.data.save(filepath = img_path)
			ob.rotation_mode = prev_rot
		out = os.path.expanduser(world.gbcPath).replace('\\', '/')
		if not out:
			out = TMP_DIR + '/' + bpy.path.basename(bpy.data.filepath).replace('.blend', '') + '.gbc'
		elif not out.lower().endswith('.gbc'):
			out += '.gbc'
		script_runtime = ExportGbcPyAssembly(world, out)
		image_surfaces = {}
		for ob in gbc_imgs:
			pix = _gba_load_saved_image_rgba(ob)
			if pix is not None:
				image_surfaces[ob.name] = pix
		has_physics = bool(getattr(world, 'usePhysics', True)) and _gb_scene_has_physics(scene_obs)
		if has_physics:
			sprite_ob = None
			for ob in gbc_imgs:
				if getattr(ob, 'rigidBodyExists', False) and getattr(ob, 'rigidBodyEnable', True) and getattr(ob, 'rigidBodyType', '') == 'dynamic':
					sprite_ob = ob
					break
			if sprite_ob is None:
				for ob in gbc_imgs:
					if getattr(ob, 'rigidBodyExists', False) and getattr(ob, 'rigidBodyEnable', True):
						sprite_ob = ob
						break
			if sprite_ob is None:
				raise RuntimeError('GBC dynamic physics phase1 requires at least one exported image empty with an enabled rigid body.')
			bg_imgs = [ob for ob in gbc_imgs if ob.name != sprite_ob.name]
			_gba_apply_script_surface_ops(
				image_surfaces,
				script_runtime.get('surface_ops', []),
				frame = 1,
				include_init = True,
				include_update = False,
			)
			canvas_gba_space = _gba_composite_scene(
				world,
				bg_imgs,
				image_surfaces = image_surfaces,
				script_runtime = script_runtime,
				frame = 1,
			)
			canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
			_, _, _, bg_palette_bank = _gbc_encode_tiles_and_map(canvas_gbc)
			sprite_rgba = _gba_apply_tint_opacity_to_rgba(image_surfaces.get(sprite_ob.name), list(sprite_ob.tint), sprite_ob.color[3])
			sprite_pal = _gbc_palette4_from_rgba(sprite_rgba)
			sprite_w, sprite_h = _gba_get_image_size(sprite_ob)
			sprite_w = _gba_to_gbc_cover_len(sprite_w)
			sprite_h = _gba_to_gbc_cover_len(sprite_h)
			sprite_tile, sprite_tiles_w, sprite_tiles_h = _gbc_encode_metasprite_rgba(
				sprite_rgba,
				int(round(sprite_w)),
				int(round(sprite_h)),
				palette4 = sprite_pal,
			)
			init_pos = GetImagePosition(sprite_ob)
			init_x, init_y = _gba_to_gbc_cover_point(float(init_pos.x), float(init_pos.y))
			gravity_x = 0.0
			gravity_y = 0.0
			if bpy.context.scene.use_gravity:
				g = list(bpy.context.scene.gravity)
				gravity_x = float(g[0])
				gravity_y = float(g[1])
			gravity_scale = float(getattr(sprite_ob, 'gravityScale', 1.0))
			effective_x = gravity_x * gravity_scale
			effective_down = -gravity_y * gravity_scale
			# Preserve magnitude differences directly in phase-1 runtime.
			grav_step_x = int(round(effective_x))
			grav_step_y = int(round(effective_down))
			if abs(effective_x) > 1e-6 and grav_step_x == 0:
				grav_step_x = 1 if effective_x > 0 else -1
			if abs(effective_down) > 1e-6 and grav_step_y == 0:
				grav_step_y = 1 if effective_down > 0 else -1
			grav_step_x = max(-32, min(32, grav_step_x))
			grav_step_y = max(-32, min(32, grav_step_y))
			collider_rects = _gbc_collect_runtime_colliders(scene_obs, ignored_name = sprite_ob.name)
			rom = _gbc_build_dynamic_physics_rom(canvas_gbc, sprite_tile, sprite_tiles_w, sprite_tiles_h, init_x, init_y, bg_palette_bank, sprite_pal, collider_rects = collider_rects, grav_step_x = grav_step_x, grav_step_y = grav_step_y)
		else:
			_gba_apply_script_surface_ops(
				image_surfaces,
				script_runtime.get('surface_ops', []),
				frame = 1,
				include_init = True,
				include_update = False,
			)
			canvas_gba_space = _gba_composite_scene(
				world,
				gbc_imgs,
				image_surfaces = image_surfaces,
				script_runtime = script_runtime,
				frame = 1,
			)
			canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
			rom = _gbc_build_rom(canvas_gbc)
			print('GBC export: baked playback disabled; runtime is dynamic-only.')
		MakeFolderForFile(out)
		open(out, 'wb').write(rom)
		print('Saved GBC ROM:', out, '(%i bytes)' %len(rom))
		rom_path = os.path.abspath(out)
		try:
			proc = subprocess.Popen(
				['mgba-qt', '-d', '--log-level', '255', '-C', 'logToStdout=true', rom_path],
				stdout = subprocess.PIPE,
				stderr = subprocess.STDOUT,
				text = True,
				bufsize = 1,
			)
			_pipe_process_output_to_terminal(proc, prefix = 'mGBA')
			_start_gba_update_print_mirror(proc, script_runtime, script_label = 'gbc-py')
		except FileNotFoundError:
			print('mgba-qt not found in PATH; open the ROM manually:', rom_path)
	finally:
		PostBuild ()

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
	if not world.zipPath:
		zipPath = TMP_DIR + '/index.zip'
	else:
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
	cmd = 'python3 CodonBuild.py ' + pythonPath + ' "' + exePath + '" ' + str(world.debugMode)
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
	cmd = 'chmod +x '
	print(cmd)
	subprocess.check_call(cmd.split() + ['"' + exePath + '"'])
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
	for UtilScript in GetAllFilePathsOfType(Util_SCRIPTS_PATH, '.cs'):
		CopyFile (UtilScript, os.path.join(scriptsPath, UtilScript[UtilScript.rfind('/') + 1:]))
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
		pos += Vector((ob.colliderPosOff[0], ob.colliderPosOff[1], 0))
		rot = matrix.to_euler()
		rot.x = 0
		rot.y = 0
		rot.z += ob.colliderRotOff
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
		if getattr(ob, usePropName + str(i), False):
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
	world = bpy.context.world
	for txt in bpy.data.texts:
		idxOfPeriod = txt.name.find('.')
		if idxOfPeriod != -1:
			for ob in bpy.data.objects:
				for i in range(MAX_SCRIPTS_PER_OBJECT):
					attachedTxt = getattr(ob, 'script%i' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(ob, 'script%i' %i, origTxt)
								break
			if world:
				for i in range(MAX_SCRIPTS_PER_OBJECT):
					attachedTxt = getattr(world, 'script%i' %i)
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: idxOfPeriod]:
								setattr(world, 'script%i' %i, origTxt)
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
SCRIPT_TYPE_ITEMS = [('html-py', 'html-py', ''), ('html-js', 'html-js', ''), ('exe', 'exe', ''), ('unity', 'unity', ''), ('gba-py', 'gba-py', 'Python → Thumb asm for GBA (see Export to GBA)'), ('gbc-py', 'gbc-py', 'Python → assembly for GBC (see Export to GBC)')]
BOUNCINESS_COMBINE_RULE_ITEMS = [('average', 'average', ''), ('minimum', 'min', ''), ('multiply', 'multiply', ''), ('maximum', 'max', '')]
BOUNCINESS_COMBINE_RULES = ['average', 'minimum', 'multiply', 'maximum']

bpy.types.World.exportScale = bpy.props.FloatProperty(name = 'Scale', default = 1)
bpy.types.World.exportOff = bpy.props.IntVectorProperty(name = 'Offset', size = 2)
bpy.types.World.importMap = bpy.props.StringProperty(name = 'Import map')
bpy.types.World.htmlPath = bpy.props.StringProperty(name = 'Export .html')
bpy.types.World.exePath = bpy.props.StringProperty(name = 'Export .exe')
bpy.types.World.gbaPath = bpy.props.StringProperty(name = 'Export .gba', default = TMP_DIR + '/export.gba')
bpy.types.World.gbcPath = bpy.props.StringProperty(name = 'Export .gbc', default = TMP_DIR + '/export.gbc')
bpy.types.World.usePhysics = bpy.props.BoolProperty(name = 'Use physics', default = True)
bpy.types.World.zipPath = bpy.props.StringProperty(name = 'Export .zip')
bpy.types.World.unityProjPath = bpy.props.StringProperty(name = 'Unity project path', default = TMP_DIR + '/TestUnityProject')
bpy.types.World.minifyMethod = bpy.props.EnumProperty(name = 'Minify using library', items = MINIFY_METHOD_ITEMS)
bpy.types.World.js13kbjam = bpy.props.BoolProperty(name = 'Error on export if output is over 13kb')
bpy.types.World.invalidHtml = bpy.props.BoolProperty(name = 'Save space with invalid html wrapper')
bpy.types.World.unitLen = bpy.props.FloatProperty(name = 'Unit length', min = 0, default = 1)
bpy.types.World.debugMode = bpy.props.BoolProperty(name = 'Debug mode', default = True)
bpy.types.Object.exportOb = bpy.props.BoolProperty(name = 'Export object', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'export'))
bpy.types.Object.roundPosAndSize = bpy.props.BoolProperty(name = 'Round position and size', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'roundPosAndSize'))
bpy.types.Object.roundAndCompressPathData = bpy.props.BoolProperty(name = 'Round and compress path data', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'roundAndCompressPathData'))
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
bpy.types.Object.colliderPosOff = bpy.props.FloatVectorProperty(name = 'Position offset', size = 2, default = [0, 0], update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderPosOff'))
bpy.types.Object.colliderRotOff = bpy.props.FloatProperty(name = 'Rotation offset', subtype = 'ANGLE', default = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'colliderRotOff'))
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
bpy.types.Object.uiExists = bpy.props.BoolProperty(name = 'Exists', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'uiExists'))
bpy.types.Object.uiEnable = bpy.props.BoolProperty(name = 'Enable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'uiEnable'))
bpy.types.Object.useOnPointerEnter = bpy.props.BoolProperty(name = 'Use on pointer enter', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useOnPointerEnter'))
bpy.types.Object.onPointerEnter = bpy.props.StringProperty(name = 'On pointer enter', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'onPointerEnter'))
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
bpy.types.Object.emitRadius = bpy.props.FloatProperty(name = 'Shape radius', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'emitRadius'))
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
bpy.types.Collection.exportPrefab = bpy.props.BoolProperty(name = 'Export prefab', default = False, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'exportPrefab'))

for i in range(MAX_SCRIPTS_PER_OBJECT):
	setattr(
		bpy.types.World,
		'script%i' %i,
		bpy.props.PointerProperty(name = 'Script%i' %i, type = bpy.types.Text)
	)
	setattr(
		bpy.types.World,
		'scriptDisable%i' %i,
		bpy.props.BoolProperty(name = 'Disable')
	)
	setattr(
		bpy.types.World,
		'initScript%i' %i,
		bpy.props.BoolProperty(name = 'Is init')
	)
	setattr(
		bpy.types.World,
		'scriptType%i' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS)
	)
	setattr(
		bpy.types.Object,
		'script%i' %i,
		bpy.props.PointerProperty(name = 'Script%i' %i, type = bpy.types.Text, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'script%i' %i))
	)
	setattr(
		bpy.types.Object,
		'scriptDisable%i' %i,
		bpy.props.BoolProperty(name = 'Disable', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scriptDisable%i' %i))
	)
	setattr(
		bpy.types.Object,
		'initScript%i' %i,
		bpy.props.BoolProperty(name = 'Is init', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'initScript%i' %i))
	)
	setattr(
		bpy.types.Object,
		'scriptType%i' %i,
		bpy.props.EnumProperty(name = 'Type', items = SCRIPT_TYPE_ITEMS, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'scriptType%i' %i))
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
for i in range(MAX_PARTICLE_SYSTEM_BURSTS):
	setattr(
		bpy.types.Object,
		'useBurst%i' %i,
		bpy.props.BoolProperty(name = 'Include', update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'useBurst%i' %i))
	)
	setattr(
		bpy.types.Object,
		'burstTime%i' %i,
		bpy.props.FloatProperty(name = 'Time since last burst', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'burstTime%i' %i))
	)
	setattr(
		bpy.types.Object,
		'burstCnt%i' %i,
		bpy.props.IntProperty(name = 'Particle count', min = 0, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'burstCnt%i' %i))
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
class GbaExport (bpy.types.Operator):
	bl_idname = 'world.gba_export'
	bl_label = 'Export to GBA (.gba)'
	bl_description = 'Build a Game Boy Advance ROM (Mode 3 bitmap) from image empties; open the .gba in Dolphin (GBA), mGBA, or VisualBoyAdvance'

	@classmethod
	def poll (cls, ctx):
		return True

	def execute (self, ctx):
		try:
			BuildGba (ctx.world)
		except Exception as e:
			self.report({'ERROR'}, str(e))
			return {'CANCELLED'}
		return {'FINISHED'}

@bpy.utils.register_class
class GbcExport (bpy.types.Operator):
	bl_idname = 'world.gbc_export'
	bl_label = 'Export to GBC (.gbc)'
	bl_description = 'Build a Game Boy Color ROM from image empties; open the .gbc in mGBA'

	@classmethod
	def poll (cls, ctx):
		return True

	def execute (self, ctx):
		try:
			BuildGbc (ctx.world)
		except Exception as e:
			self.report({'ERROR'}, str(e))
			return {'CANCELLED'}
		return {'FINISHED'}

@bpy.utils.register_class
class WorldPanel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_World_Panel'
	bl_label = 'Export'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, ctx):
		self.layout.prop(ctx.world, 'exportScale')
		self.layout.prop(ctx.world, 'exportOff')
		self.layout.prop(ctx.world, 'importMap')
		self.layout.prop(ctx.world, 'htmlPath')
		self.layout.prop(ctx.world, 'exePath')
		self.layout.prop(ctx.world, 'gbaPath')
		self.layout.prop(ctx.world, 'gbcPath')
		self.layout.prop(ctx.world, 'usePhysics')
		self.layout.prop(ctx.world, 'zipPath')
		self.layout.prop(ctx.world, 'unityProjPath')
		if usePhysics:
			self.layout.prop(ctx.world, 'unitLen')
		self.layout.prop(ctx.world, 'debugMode')
		self.layout.label(text = 'Global scripts')
		for i in range(GetLastUsedPropertyIndex(ctx.world, 'script', MAX_SCRIPTS_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ctx.world, 'script%i' %i)
			row.prop(ctx.world, 'initScript%i' %i)
			row.prop(ctx.world, 'scriptType%i' %i)
			row.prop(ctx.world, 'scriptDisable%i' %i)
		self.layout.operator('world.html_export', icon = 'CONSOLE')
		self.layout.operator('world.exe_export', icon = 'CONSOLE')
		self.layout.operator('world.unity_export', icon = 'CONSOLE')
		self.layout.operator('world.gba_export', icon = 'CONSOLE')
		self.layout.operator('world.gbc_export', icon = 'CONSOLE')

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
		self.layout.prop(ob, 'exportOb')
		if ob.type == 'CURVE' or ob.type == 'MESH' or ob.type == 'GREASEPENCIL':
			self.layout.label(text = 'Graphics')
			self.layout.prop(ob, 'roundPosAndSize')
			if ob.type == 'CURVE':
				self.layout.prop(ob, 'roundAndCompressPathData')
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
			if ob.type != 'CURVE':
				for i in range(GetLastUsedPropertyIndex(ob, 'useMinVisibleClrValue', MAX_POTRACE_PASSES_PER_OBJECT_MAT) + 2, 1):
					row = self.layout.row()
					row.prop(ob, 'minVisibleClrValue%i' %i)
					row.prop(ob, 'tintOutput%i' %i)
					if i > 0:
						row.prop(ob, 'useMinVisibleClrValue%i' %i)
				for i in range(GetLastUsedPropertyIndex(ob, 'renderCam', MAX_RENDER_CAMS_PER_OBJECT) + 2):
					self.layout.prop(ob, 'renderCam%i' %i)

@bpy.utils.register_class
class LocalScriptsPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Local_Scripts_Panel'
	bl_label = 'Local Scripts'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		for i in range(GetLastUsedPropertyIndex(ob, 'script', MAX_SCRIPTS_PER_OBJECT) + 2):
			row = self.layout.row()
			row.prop(ob, 'script%i' %i)
			row.prop(ob, 'initScript%i' %i)
			row.prop(ob, 'scriptType%i' %i)
			row.prop(ob, 'scriptDisable%i' %i)

@bpy.utils.register_class
class UIPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_UI_Panel'
	bl_label = 'UI'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, ctx):
		ob = ctx.active_object
		if not ob:
			return
		self.layout.prop(ob, 'uiExists')
		if not ob.uiExists:
			return
		self.layout.prop(ob, 'uiEnable')
		if not ob.uiEnable:
			return
		row = self.layout.row()
		row.prop(ob, 'useOnPointerEnter')
		row.prop(ob, 'onPointerEnter')

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
class PrefabPanel (bpy.types.Panel):
	bl_idname = 'COLLECTION_PT_Prefab_Panel'
	bl_label = 'Prefab'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'collection'

	@classmethod
	def poll (cls, ctx):
		collection = ctx.collection
		if not collection:
			return False
		ob = ctx.active_object
		if ob and getattr(ob, 'instance_type', None) == 'COLLECTION' and getattr(ob, 'instance_collection', None) == collection:
			return False
		return True

	def draw (self, ctx):
		collection = ctx.collection
		if not collection:
			return
		self.layout.prop(collection, 'exportPrefab')

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
		self.layout.label(text = 'Bursts')
		for i in range(GetLastUsedPropertyIndex(ob, 'useBurst', MAX_PARTICLE_SYSTEM_BURSTS) + 2):
			row = self.layout.row()
			row.prop(ob, 'burstTime%i' %i)
			row.prop(ob, 'burstCnt%i' %i)
			row.prop(ob, 'useBurst%i' %i)
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
		self.layout.prop(ob, 'colliderPosOff')
		self.layout.prop(ob, 'colliderRotOff')
		self.layout.prop(ob, 'isSensor')
		self.layout.prop(ob, 'density')
		self.layout.prop(ob, 'bounciness')
		self.layout.prop(ob, 'bouncinessCombineRule')
		self.layout.label(text = 'Collision Groups')
		box = self.layout.box()
		box.label(text = 'Membership (object is in these groups)')
		col = box.column()
		for i in range(4):
			row = col.row()
			for j in range(4):
				idx = i * 4 + j
				row.prop(ob, 'collisionGroupMembership', index = idx, text = str(idx + 1))
		box.label(text = 'Filter (object collides with these groups)')
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