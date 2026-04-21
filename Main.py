import os, re, io, ast, sys, json, math, time, string, atexit, struct, shutil, inspect, keyword, contextlib, threading, subprocess, webbrowser
import ctypes, ctypes.util
from zipfile import *
_thisDir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisDir)
Util_SCRIPTS_PATH = os.path.join(_thisDir, 'Util')
sys.path.append(Util_SCRIPTS_PATH)
PY2GB_PATH = os.path.join(_thisDir, 'Py2Gb')
PY2GB_BUILD_LIB_PATH = os.path.join(PY2GB_PATH, 'build', 'lib')
# Prefer bundled build/lib modules first so py2gb/py2gba imports resolve
# consistently even when a partial site-packages install is present.
if os.path.isdir(PY2GB_BUILD_LIB_PATH) and PY2GB_BUILD_LIB_PATH not in sys.path:
	sys.path.insert(0, PY2GB_BUILD_LIB_PATH)
if os.path.isdir(PY2GB_PATH) and PY2GB_PATH not in sys.path:
	sys.path.insert(0, PY2GB_PATH)
from MathUtil import *
from SystemUtil import *
try:
	from py2gb.blender_export import export_gba_py_assembly as _py2gb_export_gba_py_assembly
	from py2gb.blender_export import normalize_gb_script_code as _py2gb_normalize_gb_script_code
	from py2gb.blender_export import py2gb_asm as _py2gb_py2gb_asm
	from py2gb.blender_export import is_runtime_script_binding_name as _py2gb_is_runtime_script_binding_name
	from py2gb.blender_export import augment_runtime_physics_maps as _py2gb_augment_runtime_physics_maps
except Exception:
	try:
		from py2gba.blender_export import export_gba_py_assembly as _py2gb_export_gba_py_assembly
		from py2gba.blender_export import normalize_gb_script_code as _py2gb_normalize_gb_script_code
		try:
			from py2gba.blender_export import py2gb_asm as _py2gb_py2gb_asm
		except Exception:
			from py2gba.blender_export import py2gba_asm as _py2gb_py2gb_asm
		from py2gba.blender_export import is_runtime_script_binding_name as _py2gb_is_runtime_script_binding_name
		from py2gba.blender_export import augment_runtime_physics_maps as _py2gb_augment_runtime_physics_maps
	except Exception:
		_py2gb_export_gba_py_assembly = None
		_py2gb_normalize_gb_script_code = None
		_py2gb_py2gb_asm = None
		_py2gb_is_runtime_script_binding_name = None
		_py2gb_augment_runtime_physics_maps = None

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

def _write_startup_probe ():
	try:
		paths = (
			'/tmp/js13k_main_startup_probe.log',
			os.path.join(TMP_DIR, 'js13k_main_startup_probe.log'),
			os.path.join(_thisDir, 'js13k_main_startup_probe.log'),
		)
		msg = '[startup-probe] file=' + str(__file__) + ' cwd=' + str(os.getcwd()) + ' pid=' + str(os.getpid())
		for p in paths:
			try:
				with open(p, 'a') as f:
					f.write(msg + '\n')
			except Exception:
				pass
	except Exception:
		pass

_write_startup_probe()

def _get_gbc_trace_paths ():
	paths = []
	for p in (
		'/tmp/js13k_gbc_trace.log',
		os.path.join(TMP_DIR, 'js13k_gbc_trace.log'),
		os.path.join(_thisDir, 'js13k_gbc_trace.log'),
	):
		if p not in paths:
			paths.append(p)
	return paths

def _append_gbc_trace_lines (lines):
	try:
		rows = [str(x) for x in list(lines or [])]
	except Exception:
		rows = [str(lines)]
	if rows == []:
		return
	for p in _get_gbc_trace_paths():
		try:
			with open(p, 'a') as f:
				for row in rows:
					f.write(row + '\n')
		except Exception:
			pass

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
				scripts.append((txt.as_string(), getattr(ob, 'initScript%i' %i), getattr(ob, 'scriptType%i' %i), txt, getattr(ob, 'scriptIsGlobal%i' %i, False)))
	return scripts

_GB_GLOBAL_MEMBER_NODE_TYPES = (
	ast.Import,
	ast.ImportFrom,
	ast.Assign,
	ast.AnnAssign,
	ast.FunctionDef,
	ast.AsyncFunctionDef,
	ast.ClassDef,
)

def _get_ast_node_source_segment (code : str, lines : list, node):
	segment = ast.get_source_segment(code, node)
	if segment is None:
		start = getattr(node, 'lineno', None)
		end = getattr(node, 'end_lineno', None)
		if isinstance(start, int) and isinstance(end, int) and start >= 1 and end >= start:
			segment = '\n'.join(lines[start - 1 : end])
	return segment

def _build_gbc_global_assign_prefix (code : str, lines : list, node):
	'''Build one-time initializer source for simple top-level gbc globals.'''
	target_name = None
	value_node = None
	if isinstance(node, ast.Assign):
		if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
			target_name = node.targets[0].id
			value_node = node.value
	elif isinstance(node, ast.AnnAssign):
		if isinstance(node.target, ast.Name):
			target_name = node.target.id
			value_node = node.value
	if not isinstance(target_name, str) or target_name == '':
		return None
	if not isinstance(value_node, ast.AST):
		return 'global ' + target_name
	value_segment = _get_ast_node_source_segment(code, lines, value_node)
	if not isinstance(value_segment, str) or value_segment.strip() == '':
		return None
	return (
		'global ' + target_name + '\n'
		+ 'try:\n'
		+ '\t' + target_name + '\n'
		+ 'except:\n'
		+ '\t' + target_name + ' = ' + value_segment.strip()
	)

def _extract_top_level_member_defs (code : str):
	'''Return source text for top-level member definitions in a script.'''
	try:
		tree = ast.parse(code)
	except Exception:
		return ''
	lines = code.splitlines()
	chunks = []
	for node in list(getattr(tree, 'body', []) or []):
		if not isinstance(node, _GB_GLOBAL_MEMBER_NODE_TYPES):
			continue
		segment = None
		if isinstance(node, (ast.Assign, ast.AnnAssign)):
			segment = _build_gbc_global_assign_prefix(code, lines, node)
		if segment is None:
			segment = _get_ast_node_source_segment(code, lines, node)
		if isinstance(segment, str) and segment.strip() != '':
			chunks.append(segment.strip('\n'))
	return '\n\n'.join(chunks)

def _build_gbc_global_members_prefix (script_entries : list):
	'''Build a reusable gbc-py source prefix from scripts marked as global.'''
	parts = []
	for entry in list(script_entries or []):
		if not bool(entry.get('is_global')):
			continue
		raw_code = str(entry.get('raw_code', entry.get('code', '')) or '')
		members = _extract_top_level_member_defs(raw_code)
		if members.strip() != '':
			parts.append(members.strip())
	if not parts:
		return ''
	return '\n\n'.join(parts).strip() + '\n'

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
TRACE_EXPORT_EMITS = os.environ.get('JS13K_TRACE_EXPORT_EMITS', '1') != '0'
exportTraceEvents = []

def _get_export_trace_paths ():
	paths = []
	for p in (
		os.path.join('/tmp', 'js13k_export_trace.log'),
		os.path.join(TMP_DIR, 'js13k_export_trace.log'),
		os.path.join(_thisDir, 'js13k_export_trace.log'),
	):
		if p not in paths:
			paths.append(p)
	return paths

def _guess_export_entry_name (entry):
	if isinstance(entry, list):
		if len(entry) > 1 and isinstance(entry[1], str):
			return entry[1]
		if len(entry) > 0 and isinstance(entry[0], str):
			return entry[0]
		if len(entry) > 7 and isinstance(entry[7], str):
			return entry[7]
	return '<unknown>'

def _trace_export_emit (bucket, entry, source):
	if not TRACE_EXPORT_EMITS:
		return
	exportTraceEvents.append({
		'bucket' : str(bucket),
		'name' : _guess_export_entry_name(entry),
		'source' : str(source),
	})

def _write_export_trace_log ():
	if not TRACE_EXPORT_EMITS:
		return
	lines = []
	if exportTraceEvents == []:
		lines.append('[export-trace] no emitted entries for datas/prefabTemplateDatas')
	else:
		grouped = {}
		for info in exportTraceEvents:
			key = (info.get('bucket', ''), info.get('name', ''))
			if key not in grouped:
				grouped[key] = set()
			grouped[key].add(info.get('source', ''))
		lines.append('[export-trace] datas/prefabTemplateDatas emits:')
		for bucket, name in sorted(grouped.keys()):
			sources = ', '.join(sorted(grouped[(bucket, name)]))
			lines.append('[export-trace] ' + str(bucket) + ' ' + str(name) + ' <- ' + str(sources))
	for p in _get_export_trace_paths():
		try:
			open(p, 'w').write('\n'.join(lines) + '\n')
			print('[export-trace] wrote ' + p)
		except Exception as err:
			print('[export-trace] failed to write ' + p + ': ' + str(err))

def _write_export_trace_probe (stage):
	msg = '[export-trace-probe] stage=' + str(stage) + ' file=' + str(__file__) + ' cwd=' + str(os.getcwd()) + ' pid=' + str(os.getpid())
	for p in _get_export_trace_paths():
		try:
			probePath = p + '.probe'
			with open(probePath, 'a') as f:
				f.write(msg + '\n')
		except Exception:
			pass

class _TrackedExportList(list):
	def __init__ (self, bucket):
		super().__init__()
		self.bucket = str(bucket)
	def append (self, entry):
		caller = inspect.currentframe().f_back
		source = caller.f_code.co_name + ':' + str(caller.f_lineno) if caller else '<unknown>'
		_trace_export_emit(self.bucket, entry, source)
		return super().append(entry)
	def extend (self, values):
		for entry in list(values):
			self.append(entry)

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

def _collect_gbc_spawn_prefab_requests ():
	'''Best-effort static scan for spawn_prefab(...) calls in gbc-py scripts.
	Returns a list of dicts: {'prefab_name': str, 'pos': [x, y] or None, 'rot': float}.
	'''
	requests = []
	def _ast_number (node):
		if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
			return float(node.value)
		if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
			inner = _ast_number(node.operand)
			if inner is None:
				return None
			return inner if isinstance(node.op, ast.UAdd) else -inner
		return None
	def _ast_string (node):
		if isinstance(node, ast.Constant) and isinstance(node.value, str):
			return str(node.value)
		return None
	def _ast_pos2 (node):
		if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 2:
			x = _ast_number(node.elts[0])
			y = _ast_number(node.elts[1])
			if x is not None and y is not None:
				return [float(x), float(y)]
		if isinstance(node, ast.Dict):
			x = None
			y = None
			for key, val in zip(node.keys, node.values):
				k = _ast_string(key)
				if k is None:
					continue
				kl = k.lower()
				if kl == 'x':
					x = _ast_number(val)
				elif kl == 'y':
					y = _ast_number(val)
			if x is not None and y is not None:
				return [float(x), float(y)]
		if isinstance(node, ast.Call) and len(node.args) >= 2:
			x = _ast_number(node.args[0])
			y = _ast_number(node.args[1])
			if x is not None and y is not None:
				return [float(x), float(y)]
		return None
	def _find_kw (node, kw_name):
		for kw in list(getattr(node, 'keywords', []) or []):
			if str(getattr(kw, 'arg', '') or '') == kw_name:
				return kw.value
		return None
	def _scan_code (code_txt):
		raw = str(code_txt or '')
		if raw.strip() == '':
			return
		try:
			tree = ast.parse(raw)
		except Exception:
			return
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call):
				continue
			if not (isinstance(node.func, ast.Name) and node.func.id == 'spawn_prefab'):
				continue
			first = node.args[0] if len(node.args) > 0 else _find_kw(node, 'prefab_name')
			name = _ast_string(first)
			if name is None:
				continue
			name = str(name).strip()
			if name == '':
				continue
			pos_node = _find_kw(node, 'pos')
			rot_node = _find_kw(node, 'rot')
			# Support both signatures:
			# - spawn_prefab(name, instance_id, pos, rot, ...)
			# - spawn_prefab(name, pos, rot, ...)
			if len(node.args) > 2:
				pos_node = node.args[2] if pos_node is None else pos_node
				if len(node.args) > 3:
					rot_node = node.args[3] if rot_node is None else rot_node
			elif len(node.args) > 1:
				second_pos = _ast_pos2(node.args[1])
				if second_pos is not None:
					pos_node = node.args[1] if pos_node is None else pos_node
					if len(node.args) > 2:
						rot_node = node.args[2] if rot_node is None else rot_node
			pos = _ast_pos2(pos_node) if pos_node is not None else None
			rot = _ast_number(rot_node)
			if rot is None:
				rot = 0.0
			requests.append({
				'prefab_name' : name,
				'pos' : pos,
				'rot' : float(rot),
			})
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		for scriptInfo in GetScripts(ob):
			scriptTxt = scriptInfo[0]
			_type = scriptInfo[2]
			if _type == 'gbc-py':
				_scan_code(scriptTxt)
	world = bpy.context.world
	if world:
		for scriptInfo in GetScripts(world):
			scriptTxt = scriptInfo[0]
			_type = scriptInfo[2]
			if _type == 'gbc-py':
				_scan_code(scriptTxt)
	return requests

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
			rigidBody = rigidBodyName + ' = sim.add_rigid_body(' + str(ob.rigidBodyEnable) + ', ' + str(RIGID_BODY_TYPES.index(ob.rigidBodyType)) + ', ' + posStr + ', ' + str(math.degrees(objectRotZ)) + ', ' + str(ob.gravityScale) + ', ' + str(ob.dominance) + ', ' + str(ob.canRot) + ', ' + str(ob.linearDrag) + ', ' + str(ob.angDrag) + ', ' + str(ob.canSleep) + ', ' + str(ob.continuousCollideDetect) + ')\nrigidBodiesIds["' + obVarName + '"] = ' + rigidBodyName + '\nrigidBodiesIds["' + ob.name + '"] = ' + rigidBodyName
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
				collider += '\ncollidersIds["' + obVarName + '"] = ' + colliderName + '\ncollidersIds["' + ob.name + '"] = ' + colliderName
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
					collider += '\ncollidersIds["' + obVarName + attachToVarName + '"] = ' + colliderName + attachToVarName + '\nif "' + obVarName + '" not in collidersIds: collidersIds["' + obVarName + '"] = ' + colliderName + attachToVarName + '\nif "' + ob.name + '" not in collidersIds: collidersIds["' + ob.name + '"] = ' + colliderName + attachToVarName
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
	try:
		img_data = getattr(ob, 'data', None)
		img_size = Vector(list(img_data.size) + [0]) if img_data else None
	except Exception:
		img_size = None
	if img_size is not None and img_size.x != 0 and img_size.y != 0:
		if img_size.x > img_size.y:
			size.x *= img_size.x / img_size.y
		else:
			size.y *= img_size.y / img_size.x
	pos = ob.location.copy()
	localOffset = Vector((size.x * ob.empty_image_offset[0], size.y * (ob.empty_image_offset[1] + 1), 0))
	rotatedOffset = Rotate2DByAngle(localOffset, ob.rotation_euler.z)
	pos += rotatedOffset
	pos.y *= -1
	return pos

def GetImageCenterPosition (ob):
	size = ob.scale * ob.empty_display_size
	try:
		img_data = getattr(ob, 'data', None)
		img_size = Vector(list(img_data.size) + [0]) if img_data else None
	except Exception:
		img_size = None
	if img_size is not None and img_size.x != 0 and img_size.y != 0:
		if img_size.x > img_size.y:
			size.x *= img_size.x / img_size.y
		else:
			size.y *= img_size.y / img_size.x
	pos = GetImagePosition(ob).copy()
	centerOffset = Rotate2DByAngle(Vector((size.x * 0.5, size.y * 0.5, 0.0)), ob.rotation_euler.z)
	pos += centerOffset
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
	'''Transpile Python to ARM Thumb assembly for GBA (via py2gb package). kind is "init" or "update".'''
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
	# Support common emulator bindings by default.
	'A' : 'x|a',
	'B' : 'z|s',
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
	if isinstance(keysym_name, str) and ('|' in keysym_name):
		for part in keysym_name.split('|'):
			if _runtime_x11_key_pressed(part.strip()):
				return True
		return False
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
			if keysym == 0 and isinstance(keysym_name, str):
				alt = keysym_name.lower()
				if alt != keysym_name:
					keysym = lib.XStringToKeysym(alt.encode('utf-8'))
			if keysym == 0 and isinstance(keysym_name, str):
				alt = keysym_name.upper()
				if alt != keysym_name:
					keysym = lib.XStringToKeysym(alt.encode('utf-8'))
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

def _eval_runtime_expr_value (value, frame : int = None, start_time : float = None, extra_env : dict = None, const_env : dict = None):
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
	extra_env = extra_env if isinstance(extra_env, dict) else {}
	const_env = const_env if isinstance(const_env, dict) else {}
	protected_names = set((
		'int', 'float', 'round', 'abs', 'max', 'min', 'len', 'bool',
		'hasattr', 'getattr', 'keys', 'js13k_get_pressed',
	))
	class _RuntimeExprLocals(dict):
		def __missing__ (self, _key):
			return None
	eval_locals = _RuntimeExprLocals({
		'int' : int,
		'float' : float,
		'round' : round,
		'abs' : abs,
		'max' : max,
		'min' : min,
		'len' : len,
		'bool' : bool,
		'hasattr' : hasattr,
		'getattr' : getattr,
		'keys' : key_state,
		'js13k_get_pressed' : (lambda : key_state),
	})
	try:
		runtime_globals = __import__('builtins').globals()
	except Exception:
		runtime_globals = {}
	sim_runtime = runtime_globals.get('sim', runtime_globals.get('physics', None))
	rigid_bodies_runtime = runtime_globals.get('rigidBodiesIds', runtime_globals.get('rigidbodies', {}))
	rigid_bodies_named = runtime_globals.get('rigidBodies', runtime_globals.get('rbs', {}))
	colliders_runtime = runtime_globals.get('collidersIds', runtime_globals.get('colliders', {}))
	colliders_named = runtime_globals.get('cols', colliders_runtime)
	def _get_rigidbody_for_eval (_name):
		try:
			return _resolve_script_lookup_from_sources(_name, rigid_bodies_runtime, rigid_bodies_named)
		except Exception:
			return None
	def _get_collider_for_eval (_name):
		try:
			return _resolve_script_lookup_from_sources(_name, colliders_runtime, colliders_named)
		except Exception:
			return None
	eval_locals['sim'] = sim_runtime
	eval_locals['physics'] = sim_runtime
	eval_locals['get_rigidbody'] = _get_rigidbody_for_eval
	eval_locals['get_collider'] = _get_collider_for_eval
	for k, v in const_env.items():
		name = str(k)
		if re.fullmatch(r'[A-Za-z_]\w*', name) and not name.startswith('__'):
			if name in protected_names:
				continue
			if _is_simple_const_value(v):
				eval_locals[name] = v
	for k, v in extra_env.items():
		name = str(k)
		if re.fullmatch(r'[A-Za-z_]\w*', name) and not name.startswith('__'):
			if name in protected_names:
				continue
			eval_locals[name] = v
	try:
		val = eval(
			expr,
			{'__builtins__' : {}},
			eval_locals,
		)
		if isinstance(val, (int, float, bool)):
			return float(val)
	except Exception:
		return None
	return None

def _gba_draw_circle_from_script (canvas, circle : dict, frame : int = None, start_time : float = None, camera_offset = None):
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
	cam_x = 0.0
	cam_y = 0.0
	if isinstance(camera_offset, (list, tuple)) and len(camera_offset) >= 2:
		try:
			cam_x = float(camera_offset[0])
		except Exception:
			cam_x = 0.0
		try:
			cam_y = float(camera_offset[1])
		except Exception:
			cam_y = 0.0
	cx = float(cx) - cam_x
	cy = float(cy) - cam_y
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
		if isinstance(node.value, (int, float, bool, str)) or node.value is None:
			return node.value
	if isinstance(node, (ast.Tuple, ast.List)):
		return [_serialize_script_expr(e) for e in node.elts]
	try:
		return '<expr:' + ast.unparse(node) + '>'
	except Exception:
		return '<expr:0>'

def _inline_runtime_expr_with_env (value, const_env = None, expr_env = None, rb_alias = None, owner_name : str = None):
	'''Inline known symbolic names in <expr:...> placeholders using script env.'''
	const_env = const_env if isinstance(const_env, dict) else {}
	expr_env = expr_env if isinstance(expr_env, dict) else {}
	rb_alias = rb_alias if isinstance(rb_alias, dict) else {}
	if not isinstance(value, str):
		return value
	match = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', str(value).strip())
	if not match:
		return value
	expr = str(match.group(1) or '').strip()
	if expr == '':
		return value
	def _expr_env_value_to_ast (_value):
		if isinstance(_value, (int, float, bool)) or _value is None:
			return ast.Constant(value = _value)
		if isinstance(_value, str):
			m = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', _value.strip())
			src = m.group(1).strip() if m else _value
			try:
				return ast.parse(src, mode = 'eval').body
			except Exception:
				return None
		return None
	def _owner_rb_lookup_expr ():
		try:
			owner_candidates = _script_lookup_candidate_names(str(owner_name or ''))
		except Exception:
			owner_candidates = [str(owner_name or '')]
		owner_candidates = [c for c in list(owner_candidates or []) if isinstance(c, str) and c != '']
		if owner_candidates == []:
			return None
		expr_text = 'None'
		for key in reversed(owner_candidates):
			call_expr = 'get_rigidbody(' + repr(key) + ')'
			expr_text = '(' + call_expr + ' if (' + call_expr + ') is not None else ' + expr_text + ')'
		try:
			return ast.parse(expr_text, mode = 'eval').body
		except Exception:
			return None
	def _owner_col_lookup_expr ():
		try:
			owner_candidates = _script_lookup_candidate_names(str(owner_name or ''))
		except Exception:
			owner_candidates = [str(owner_name or '')]
		owner_candidates = [c for c in list(owner_candidates or []) if isinstance(c, str) and c != '']
		if owner_candidates == []:
			return None
		expr_text = 'None'
		for key in reversed(owner_candidates):
			call_expr = 'get_collider(' + repr(key) + ')'
			expr_text = '(' + call_expr + ' if (' + call_expr + ') is not None else ' + expr_text + ')'
		try:
			return ast.parse(expr_text, mode = 'eval').body
		except Exception:
			return None
	class _InlineRuntimeExprNames(ast.NodeTransformer):
		def visit_Attribute (self, node):
			node = self.generic_visit(node)
			if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'this':
				if node.attr == 'rb':
					repl = _owner_rb_lookup_expr()
					if repl is not None:
						return ast.copy_location(repl, node)
				if node.attr == 'col':
					repl = _owner_col_lookup_expr()
					if repl is not None:
						return ast.copy_location(repl, node)
			return node
		def visit_Name (self, node):
			if _is_runtime_script_binding_name(node.id):
				return node
			if node.id in const_env:
				try:
					repl = ast.parse(repr(const_env[node.id]), mode = 'eval').body
					return ast.copy_location(repl, node)
				except Exception:
					return node
			if node.id in expr_env:
				repl = _expr_env_value_to_ast(expr_env[node.id])
				if repl is not None:
					return ast.copy_location(repl, node)
			if node.id in rb_alias and isinstance(rb_alias.get(node.id), str):
				try:
					repl = ast.parse('get_rigidbody(' + repr(rb_alias.get(node.id)) + ')', mode = 'eval').body
					return ast.copy_location(repl, node)
				except Exception:
					return node
			return node
	try:
		root = ast.parse(expr, mode = 'eval').body
		root = _InlineRuntimeExprNames().visit(copy.deepcopy(root))
		root = ast.fix_missing_locations(root)
		return _serialize_script_expr(root)
	except Exception:
		return value

def _is_simple_const_value (value):
	if isinstance(value, (int, float, bool, str)) or value is None:
		return True
	if isinstance(value, (list, tuple)):
		return all(_is_simple_const_value(v) for v in value)
	if isinstance(value, dict):
		return all(_is_simple_const_value(k) and _is_simple_const_value(v) for k, v in value.items())
	return False

def _extract_simple_const_value (node):
	'''Return a simple compile-time constant, or None when unknown/unsupported.'''
	try:
		val = ast.literal_eval(node)
	except Exception:
		return None
	if _is_simple_const_value(val):
		return val
	return None

def _collect_simple_const_env_from_script (code : str):
	'''Collect simple top-level constant assignments for runtime print eval.'''
	env = {}
	try:
		tree = ast.parse(code or '')
	except Exception:
		return env
	def _walk (stmts):
		for stmt in list(stmts or []):
			if isinstance(stmt, ast.Assign):
				val = _extract_simple_const_value(stmt.value)
				for target in list(stmt.targets or []):
					if isinstance(target, ast.Name):
						if val is None:
							env.pop(target.id, None)
						else:
							env[target.id] = val
				continue
			if isinstance(stmt, ast.AnnAssign):
				if isinstance(stmt.target, ast.Name):
					val = _extract_simple_const_value(stmt.value) if stmt.value is not None else None
					if val is None:
						env.pop(stmt.target.id, None)
					else:
						env[stmt.target.id] = val
				continue
			if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
				env.pop(stmt.target.id, None)
				continue
			if isinstance(stmt, ast.If):
				truth = _literal_truthy_from_ast_node(stmt.test)
				if truth is True:
					_walk(stmt.body)
					continue
				if truth is False:
					_walk(stmt.orelse)
					continue
				# Dynamic branch flow makes post-if values uncertain.
				env.clear()
	_walk(getattr(tree, 'body', []))
	return env

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

def _extract_surface_scroll_dxdy_nodes (call_node):
	if not isinstance(call_node, ast.Call):
		return None, None
	args = list(call_node.args or [])
	dx_node = None
	dy_node = None
	if len(args) >= 2:
		dx_node = args[0]
		dy_node = args[1]
	elif len(args) == 1:
		first = args[0]
		if isinstance(first, (ast.Tuple, ast.List)) and len(list(first.elts or [])) >= 2:
			dx_node = first.elts[0]
			dy_node = first.elts[1]
		else:
			dx_node = first
			dy_node = ast.Constant(value = 0)
	for kw in list(call_node.keywords or []):
		if kw.arg == 'dx':
			dx_node = kw.value
		elif kw.arg == 'dy':
			dy_node = kw.value
	return dx_node, dy_node

def _extract_dynamic_surface_scroll_ops_from_script (code : str, is_init : bool):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return []
	return _extract_dynamic_surface_scroll_ops_from_stmts(getattr(tree, 'body', []), is_init, parent_condition = None)

def _extract_dynamic_surface_scroll_ops_from_stmts (stmts, is_init : bool, parent_condition = None):
	scroll_ops = []
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Expr):
			node = stmt.value
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Attribute)
				and node.func.attr == 'scroll'
			):
				target = node.func.value
				target_type = None
				if _is_display_get_surface_call(target):
					target_type = 'display_surface'
				elif _is_this_surface_member(target):
					target_type = 'this_surface'
				if target_type:
					dx_node, dy_node = _extract_surface_scroll_dxdy_nodes(node)
					if (
						dx_node is not None
						and dy_node is not None
						and (_has_dynamic_runtime_expr(dx_node) or _has_dynamic_runtime_expr(dy_node))
					):
						scroll = {
							'dx' : _serialize_script_expr(dx_node),
							'dy' : _serialize_script_expr(dy_node),
							'is_init' : bool(is_init),
							'target_type' : target_type,
						}
						if parent_condition is not None:
							scroll['condition'] = parent_condition
						scroll_ops.append(scroll)
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				scroll_ops.extend(_extract_dynamic_surface_scroll_ops_from_stmts(stmt.body, is_init, parent_condition))
				continue
			if truth is False:
				scroll_ops.extend(_extract_dynamic_surface_scroll_ops_from_stmts(stmt.orelse, is_init, parent_condition))
				continue
			test_expr = _serialize_script_expr(stmt.test)
			body_cond = _combine_expr_conditions(parent_condition, test_expr)
			else_cond = _combine_expr_conditions(parent_condition, _negate_expr_condition(test_expr))
			scroll_ops.extend(_extract_dynamic_surface_scroll_ops_from_stmts(stmt.body, is_init, body_cond))
			scroll_ops.extend(_extract_dynamic_surface_scroll_ops_from_stmts(stmt.orelse, is_init, else_cond))
	return scroll_ops

def _extract_set_camera_position_xy_nodes (call_node):
	if not isinstance(call_node, ast.Call):
		return None, None
	args = list(call_node.args or [])
	x_node = None
	y_node = None
	if len(args) >= 2:
		x_node = args[0]
		y_node = args[1]
	for kw in list(call_node.keywords or []):
		if kw.arg == 'x':
			x_node = kw.value
		elif kw.arg == 'y':
			y_node = kw.value
	return x_node, y_node

def _extract_dynamic_set_camera_ops_from_script (code : str, is_init : bool):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return []
	return _extract_dynamic_set_camera_ops_from_stmts(getattr(tree, 'body', []), is_init, parent_condition = None)

def _extract_dynamic_set_camera_ops_from_stmts (stmts, is_init : bool, parent_condition = None):
	camera_ops = []
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Expr):
			node = stmt.value
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Name)
				and str(node.func.id) == 'set_camera_position'
			):
				x_node, y_node = _extract_set_camera_position_xy_nodes(node)
				if x_node is not None and y_node is not None:
					op = {
						'op' : 'set_display_camera_pos',
						'x' : _serialize_script_expr(x_node),
						'y' : _serialize_script_expr(y_node),
						'is_init' : bool(is_init),
					}
					if parent_condition is not None:
						op['condition'] = parent_condition
					camera_ops.append(op)
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(stmt.body, is_init, parent_condition))
				continue
			if truth is False:
				camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(stmt.orelse, is_init, parent_condition))
				continue
			test_expr = _serialize_script_expr(stmt.test)
			body_cond = _combine_expr_conditions(parent_condition, test_expr)
			else_cond = _combine_expr_conditions(parent_condition, _negate_expr_condition(test_expr))
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(stmt.body, is_init, body_cond))
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(stmt.orelse, is_init, else_cond))
			continue
		if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'body', []), is_init, parent_condition))
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'orelse', []), is_init, parent_condition))
			continue
		if isinstance(stmt, (ast.With, ast.AsyncWith)):
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'body', []), is_init, parent_condition))
			continue
		if isinstance(stmt, ast.Try):
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'body', []), is_init, parent_condition))
			for _handler in list(getattr(stmt, 'handlers', []) or []):
				camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(_handler, 'body', []), is_init, parent_condition))
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'orelse', []), is_init, parent_condition))
			camera_ops.extend(_extract_dynamic_set_camera_ops_from_stmts(getattr(stmt, 'finalbody', []), is_init, parent_condition))
	return camera_ops

def _is_print_call (call_node):
	return isinstance(call_node, ast.Call) and isinstance(call_node.func, ast.Name) and call_node.func.id == 'print'

def _is_runtime_script_binding_name (name):
	if callable(_py2gb_is_runtime_script_binding_name):
		try:
			return bool(_py2gb_is_runtime_script_binding_name(name))
		except Exception:
			pass
	return isinstance(name, str) and name in set((
		'obs', 'objects',
		'colliders', 'collidersIds', 'get_collider',
		'cols',
		'rigidBodies', 'rigidBodiesIds', 'get_rigidbody',
		'rbs',
		'sim', 'physics',
	))

def _serialize_print_call_text (call_node, const_env = None, expr_env = None, rb_alias = None, vel_env = None, owner_name : str = None):
	if not _is_print_call(call_node):
		return None
	const_env = const_env if isinstance(const_env, dict) else {}
	expr_env = expr_env if isinstance(expr_env, dict) else {}
	rb_alias = rb_alias if isinstance(rb_alias, dict) else {}
	vel_env = vel_env if isinstance(vel_env, dict) else {}
	def _expr_env_value_to_ast (value):
		if isinstance(value, (int, float, bool)) or value is None:
			return ast.Constant(value = value)
		if isinstance(value, str):
			m = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', value.strip())
			if m:
				try:
					return ast.parse(m.group(1).strip(), mode = 'eval').body
				except Exception:
					return None
			return ast.Constant(value = value)
		return None
	def _inline_name_refs (node):
		class _InlineNameTransformer(ast.NodeTransformer):
			def visit_Name (self, n):
				if _is_runtime_script_binding_name(n.id):
					return n
				if n.id in const_env:
					try:
						repl = ast.parse(repr(const_env[n.id]), mode = 'eval').body
						return ast.copy_location(repl, n)
					except Exception:
						return n
				if n.id in expr_env:
					repl = _expr_env_value_to_ast(expr_env[n.id])
					if repl is not None:
						return ast.copy_location(repl, n)
				if n.id in rb_alias and isinstance(rb_alias.get(n.id), str):
					try:
						repl = ast.parse('get_rigidbody(' + repr(rb_alias.get(n.id)) + ')', mode = 'eval').body
						return ast.copy_location(repl, n)
					except Exception:
						pass
				return n
		try:
			new_node = _InlineNameTransformer().visit(copy.deepcopy(node))
			return ast.fix_missing_locations(new_node)
		except Exception:
			return node
	def _serialize_print_arg (node):
		def _serialize_owner_lookup_expr (_fn_name):
			try:
				owner_candidates = _script_lookup_candidate_names(str(owner_name or ''))
			except Exception:
				owner_candidates = [str(owner_name or '')]
			owner_candidates = [c for c in owner_candidates if isinstance(c, str) and c != '']
			if owner_candidates == []:
				return 'None'
			expr = 'None'
			for key in reversed(owner_candidates):
				call_expr = _fn_name + '(' + repr(key) + ')'
				expr = '(' + call_expr + ' if (' + call_expr + ') is not None else ' + expr + ')'
			return expr
		if (
			isinstance(node, ast.Attribute)
			and isinstance(node.value, ast.Name)
			and node.value.id == 'this'
			and node.attr == 'col'
		):
			return '<expr:' + _serialize_owner_lookup_expr('get_collider') + '>'
		if (
			isinstance(node, ast.Attribute)
			and isinstance(node.value, ast.Name)
			and node.value.id == 'this'
			and node.attr == 'rb'
		):
			return '<expr:' + _serialize_owner_lookup_expr('get_rigidbody') + '>'
		if isinstance(node, ast.Name) and node.id in rb_alias and isinstance(rb_alias.get(node.id), str):
			return '<expr:get_rigidbody(' + repr(rb_alias.get(node.id)) + ')>'
		if isinstance(node, ast.Call):
			func = node.func
			if (
				isinstance(func, ast.Attribute)
				and isinstance(func.value, ast.Name)
				and func.value.id in ('sim', 'physics')
				and len(node.args or []) >= 1
			):
				rb_kind, rb_value = _extract_rigidbody_name_expr(node.args[0])
				if rb_kind == 'name_ref' and rb_value in rb_alias:
					rb_kind = 'key'
					rb_value = rb_alias.get(rb_value)
				if rb_kind == 'key' and isinstance(rb_value, str):
					call_name = str(func.attr)
					# Emit a runtime handle lookup so alias vars (e.g. body) don't need
					# to be present in mirror-eval locals for velocity/position reads.
					if call_name in (
						'get_linear_velocity',
						'get_rigid_body_position',
						'get_rigid_body_rotation',
						'get_angular_velocity',
						'get_rigid_body_enabled',
						'get_gravity_scale',
					):
						arg_exprs = ['get_rigidbody(' + repr(rb_value) + ')']
						for extra_arg in list(node.args[1:] or []):
							extra_ser = _serialize_script_expr(_inline_name_refs(extra_arg))
							if isinstance(extra_ser, str) and extra_ser.startswith('<expr:') and extra_ser.endswith('>'):
								arg_exprs.append(extra_ser[6:-1])
							else:
								arg_exprs.append(repr(extra_ser))
						return '<expr:' + func.value.id + '.' + call_name + '(' + ', '.join(arg_exprs) + ')>'
		inlined = _inline_name_refs(node)
		return _serialize_script_expr(inlined)
	sep = ' '
	end = '\n'
	for kw in list(call_node.keywords or []):
		if kw.arg == 'sep':
			val = _serialize_print_arg(kw.value)
			if isinstance(val, str):
				sep = val
			elif isinstance(val, (int, float, bool)):
				sep = str(val)
		elif kw.arg == 'end':
			val = _serialize_print_arg(kw.value)
			if isinstance(val, str):
				end = val
			elif isinstance(val, (int, float, bool)):
				end = str(val)
	parts = []
	for arg in list(call_node.args or []):
		val = _serialize_print_arg(arg)
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

def _collect_assigned_names_from_stmts (stmts):
	assigned = set()
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Assign):
			for target in list(stmt.targets or []):
				if isinstance(target, ast.Name):
					assigned.add(target.id)
				else:
					mutated_name = _mutated_container_name_from_target(target)
					if mutated_name:
						assigned.add(mutated_name)
		elif isinstance(stmt, ast.AnnAssign):
			if isinstance(stmt.target, ast.Name):
				assigned.add(stmt.target.id)
			else:
				mutated_name = _mutated_container_name_from_target(stmt.target)
				if mutated_name:
					assigned.add(mutated_name)
		elif isinstance(stmt, ast.AugAssign):
			if isinstance(stmt.target, ast.Name):
				assigned.add(stmt.target.id)
			else:
				mutated_name = _mutated_container_name_from_target(stmt.target)
				if mutated_name:
					assigned.add(mutated_name)
		elif isinstance(stmt, ast.If):
			assigned.update(_collect_assigned_names_from_stmts(stmt.body))
			assigned.update(_collect_assigned_names_from_stmts(stmt.orelse))
	return assigned

def _mutated_container_name_from_target (target):
	'''Return base name for in-place container updates like `x[i] = ...`.'''
	node = target
	while isinstance(node, ast.Subscript):
		node = node.value
	if isinstance(node, ast.Name):
		return node.id
	return None

def _apply_simple_container_mutation (target, value_node, const_env, expr_env, rb_alias):
	'''Apply simple subscript writes to known literal containers in-place env.'''
	if not isinstance(target, ast.Subscript):
		return False
	base_name = _mutated_container_name_from_target(target)
	if not base_name or base_name not in const_env:
		return False
	base_val = const_env.get(base_name)
	if not isinstance(base_val, (list, tuple, dict)):
		return False
	try:
		index_val = ast.literal_eval(target.slice)
	except Exception:
		return False
	assign_val = _extract_simple_const_value(value_node)
	if assign_val is None:
		return False
	if isinstance(base_val, list):
		if not isinstance(index_val, int):
			return False
		idx = int(index_val)
		if idx < 0:
			idx += len(base_val)
		if idx < 0 or idx >= len(base_val):
			return False
		new_val = list(base_val)
		new_val[idx] = assign_val
		const_env[base_name] = new_val
	elif isinstance(base_val, tuple):
		if not isinstance(index_val, int):
			return False
		idx = int(index_val)
		tmp = list(base_val)
		if idx < 0:
			idx += len(tmp)
		if idx < 0 or idx >= len(tmp):
			return False
		tmp[idx] = assign_val
		const_env[base_name] = tuple(tmp)
	elif isinstance(base_val, dict):
		new_val = dict(base_val)
		new_val[index_val] = assign_val
		const_env[base_name] = new_val
	else:
		return False
	expr_env.pop(base_name, None)
	rb_alias.pop(base_name, None)
	return True

def _apply_simple_container_aug_mutation (target, op, value_node, const_env, expr_env, rb_alias):
	'''Apply simple subscript aug-assign writes like `x[i] += v` for literals.'''
	if not isinstance(target, ast.Subscript):
		return False
	base_name = _mutated_container_name_from_target(target)
	if not base_name or base_name not in const_env:
		return False
	base_val = const_env.get(base_name)
	if not isinstance(base_val, (list, tuple, dict)):
		return False
	try:
		index_val = ast.literal_eval(target.slice)
	except Exception:
		return False
	assign_val = _extract_simple_const_value(value_node)
	if assign_val is None:
		return False
	def _apply_aug (_old, _op, _rhs):
		if isinstance(_op, ast.Add):
			return _old + _rhs
		if isinstance(_op, ast.Sub):
			return _old - _rhs
		if isinstance(_op, ast.Mult):
			return _old * _rhs
		if isinstance(_op, ast.Div):
			return _old / _rhs
		if isinstance(_op, ast.FloorDiv):
			return _old // _rhs
		if isinstance(_op, ast.Mod):
			return _old % _rhs
		if isinstance(_op, ast.Pow):
			return _old ** _rhs
		if isinstance(_op, ast.LShift):
			return _old << _rhs
		if isinstance(_op, ast.RShift):
			return _old >> _rhs
		if isinstance(_op, ast.BitAnd):
			return _old & _rhs
		if isinstance(_op, ast.BitOr):
			return _old | _rhs
		if isinstance(_op, ast.BitXor):
			return _old ^ _rhs
		raise ValueError('unsupported augassign operator')
	try:
		if isinstance(base_val, list):
			if not isinstance(index_val, int):
				return False
			idx = int(index_val)
			if idx < 0:
				idx += len(base_val)
			if idx < 0 or idx >= len(base_val):
				return False
			old_item = base_val[idx]
			new_item = _apply_aug(old_item, op, assign_val)
			new_val = list(base_val)
			new_val[idx] = new_item
			const_env[base_name] = new_val
		elif isinstance(base_val, tuple):
			if not isinstance(index_val, int):
				return False
			tmp = list(base_val)
			idx = int(index_val)
			if idx < 0:
				idx += len(tmp)
			if idx < 0 or idx >= len(tmp):
				return False
			old_item = tmp[idx]
			tmp[idx] = _apply_aug(old_item, op, assign_val)
			const_env[base_name] = tuple(tmp)
		elif isinstance(base_val, dict):
			old_item = base_val.get(index_val)
			new_item = _apply_aug(old_item, op, assign_val)
			new_val = dict(base_val)
			new_val[index_val] = new_item
			const_env[base_name] = new_val
		else:
			return False
	except Exception:
		return False
	expr_env.pop(base_name, None)
	rb_alias.pop(base_name, None)
	return True

def _compose_expr_text_for_name (_name, const_env, expr_env):
	if _name in const_env and _is_simple_const_value(const_env.get(_name)):
		return repr(const_env.get(_name))
	if _name in expr_env:
		v = expr_env.get(_name)
		if isinstance(v, str):
			return _unwrap_expr_placeholder(v)
		if _is_simple_const_value(v):
			return repr(v)
	return None

def _apply_symbolic_container_mutation (target, value_node, const_env, expr_env, rb_alias, aug_op = None):
	'''Fallback: represent subscript mutation as runtime expression transform.'''
	if not isinstance(target, ast.Subscript):
		return False
	base_name = _mutated_container_name_from_target(target)
	if not base_name:
		return False
	base_expr = _compose_expr_text_for_name(base_name, const_env, expr_env)
	if base_expr is None:
		return False
	try:
		index_val = ast.literal_eval(target.slice)
	except Exception:
		return False
	if not isinstance(index_val, int):
		return False
	rhs_ser = _serialize_script_expr(value_node)
	if isinstance(rhs_ser, str):
		rhs_expr = _unwrap_expr_placeholder(rhs_ser)
	else:
		rhs_expr = repr(rhs_ser)
	op_name = 'set'
	if aug_op is not None:
		if isinstance(aug_op, ast.Add):
			op_name = 'add'
		elif isinstance(aug_op, ast.Sub):
			op_name = 'sub'
		elif isinstance(aug_op, ast.Mult):
			op_name = 'mul'
		elif isinstance(aug_op, ast.Div):
			op_name = 'div'
		elif isinstance(aug_op, ast.FloorDiv):
			op_name = 'floordiv'
		elif isinstance(aug_op, ast.Mod):
			op_name = 'mod'
		elif isinstance(aug_op, ast.Pow):
			op_name = 'pow'
		elif isinstance(aug_op, ast.LShift):
			op_name = 'lshift'
		elif isinstance(aug_op, ast.RShift):
			op_name = 'rshift'
		elif isinstance(aug_op, ast.BitAnd):
			op_name = 'and'
		elif isinstance(aug_op, ast.BitOr):
			op_name = 'or'
		elif isinstance(aug_op, ast.BitXor):
			op_name = 'xor'
		else:
			return False
	expr_env[base_name] = '<expr:js13k_vec_update((' + base_expr + '), ' + str(index_val) + ', (' + rhs_expr + '), ' + repr(op_name) + ')>'
	const_env.pop(base_name, None)
	rb_alias.pop(base_name, None)
	return True

def _extract_print_calls_from_stmts (stmts, is_init : bool, owner_name : str, parent_condition = None, const_env = None, expr_env = None, rb_alias = None, vel_env = None):
	prints = []
	const_env = const_env if isinstance(const_env, dict) else {}
	expr_env = expr_env if isinstance(expr_env, dict) else {}
	rb_alias = rb_alias if isinstance(rb_alias, dict) else {}
	vel_env = vel_env if isinstance(vel_env, dict) else {}
	for stmt in list(stmts or []):
		if isinstance(stmt, ast.Expr) and _is_print_call(stmt.value):
			text = _serialize_print_call_text(stmt.value, const_env = const_env, expr_env = expr_env, rb_alias = rb_alias, vel_env = vel_env, owner_name = owner_name)
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
		if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
			call = stmt.value
			func = call.func
			if (
				isinstance(func, ast.Attribute)
				and func.attr == 'set_linear_velocity'
				and isinstance(func.value, ast.Name)
				and func.value.id in ('sim', 'physics')
				and len(call.args or []) >= 2
			):
				rb_kind, rb_value = _extract_rigidbody_name_expr(call.args[0])
				if rb_kind == 'name_ref' and rb_value in rb_alias:
					rb_kind = 'key'
					rb_value = rb_alias.get(rb_value)
				vel = call.args[1]
				if isinstance(vel, (ast.List, ast.Tuple)) and len(vel.elts) >= 2:
					vx = _ast_numeric_literal(vel.elts[0])
					vy = _ast_numeric_literal(vel.elts[1])
					if rb_kind == 'key' and isinstance(rb_value, str) and vx is not None and vy is not None:
						vel_env[rb_value] = [float(vx), float(vy)]
			continue
		if isinstance(stmt, ast.Assign):
			val = _extract_simple_const_value(stmt.value)
			expr_val = _serialize_script_expr(stmt.value)
			rb_kind, rb_value = _extract_rigidbody_name_expr(stmt.value)
			if rb_kind == 'name_ref' and rb_value in rb_alias:
				rb_kind = 'key'
				rb_value = rb_alias.get(rb_value)
			for target in list(stmt.targets or []):
				if isinstance(target, ast.Name):
					if _is_runtime_script_binding_name(target.id):
						const_env.pop(target.id, None)
						expr_env.pop(target.id, None)
						rb_alias.pop(target.id, None)
						continue
					if val is None:
						const_env.pop(target.id, None)
					else:
						const_env[target.id] = val
					expr_env[target.id] = expr_val
					if rb_kind == 'key' and isinstance(rb_value, str):
						rb_alias[target.id] = rb_value
					else:
						rb_alias.pop(target.id, None)
				else:
					mutated_name = _mutated_container_name_from_target(target)
					if mutated_name:
						if not _apply_simple_container_mutation(target, stmt.value, const_env, expr_env, rb_alias):
							if _apply_symbolic_container_mutation(target, stmt.value, const_env, expr_env, rb_alias, aug_op = None):
								continue
							const_env.pop(mutated_name, None)
							expr_env.pop(mutated_name, None)
							rb_alias.pop(mutated_name, None)
			continue
		if isinstance(stmt, ast.AnnAssign):
			if isinstance(stmt.target, ast.Name):
				if _is_runtime_script_binding_name(stmt.target.id):
					const_env.pop(stmt.target.id, None)
					expr_env.pop(stmt.target.id, None)
					rb_alias.pop(stmt.target.id, None)
					continue
				val = _extract_simple_const_value(stmt.value) if stmt.value is not None else None
				expr_val = _serialize_script_expr(stmt.value) if stmt.value is not None else None
				if val is None:
					const_env.pop(stmt.target.id, None)
				else:
					const_env[stmt.target.id] = val
				if expr_val is None:
					expr_env.pop(stmt.target.id, None)
				else:
					expr_env[stmt.target.id] = expr_val
				rb_kind, rb_value = _extract_rigidbody_name_expr(stmt.value) if stmt.value is not None else (None, None)
				if rb_kind == 'name_ref' and rb_value in rb_alias:
					rb_kind = 'key'
					rb_value = rb_alias.get(rb_value)
				if rb_kind == 'key' and isinstance(rb_value, str):
					rb_alias[stmt.target.id] = rb_value
				else:
					rb_alias.pop(stmt.target.id, None)
			else:
				mutated_name = _mutated_container_name_from_target(stmt.target)
				if mutated_name:
					const_env.pop(mutated_name, None)
					expr_env.pop(mutated_name, None)
					rb_alias.pop(mutated_name, None)
			continue
		if isinstance(stmt, ast.AugAssign):
			mutated_name = stmt.target.id if isinstance(stmt.target, ast.Name) else _mutated_container_name_from_target(stmt.target)
			if mutated_name:
				if not _apply_simple_container_aug_mutation(stmt.target, stmt.op, stmt.value, const_env, expr_env, rb_alias):
					if _apply_symbolic_container_mutation(stmt.target, stmt.value, const_env, expr_env, rb_alias, aug_op = stmt.op):
						continue
					const_env.pop(mutated_name, None)
					expr_env.pop(mutated_name, None)
					rb_alias.pop(mutated_name, None)
			continue
		if isinstance(stmt, ast.If):
			truth = _literal_truthy_from_ast_node(stmt.test)
			if truth is True:
				prints.extend(_extract_print_calls_from_stmts(stmt.body, is_init, owner_name, parent_condition, const_env, expr_env, rb_alias, vel_env))
				continue
			if truth is False:
				prints.extend(_extract_print_calls_from_stmts(stmt.orelse, is_init, owner_name, parent_condition, const_env, expr_env, rb_alias, vel_env))
				continue
			test_expr = _serialize_script_expr(stmt.test)
			body_cond = _combine_expr_conditions(parent_condition, test_expr)
			else_cond = _combine_expr_conditions(parent_condition, _negate_expr_condition(test_expr))
			body_const_env = dict(const_env)
			body_expr_env = dict(expr_env)
			body_rb_alias = dict(rb_alias)
			body_vel_env = dict(vel_env)
			else_const_env = dict(const_env)
			else_expr_env = dict(expr_env)
			else_rb_alias = dict(rb_alias)
			else_vel_env = dict(vel_env)
			prints.extend(_extract_print_calls_from_stmts(stmt.body, is_init, owner_name, body_cond, body_const_env, body_expr_env, body_rb_alias, body_vel_env))
			prints.extend(_extract_print_calls_from_stmts(stmt.orelse, is_init, owner_name, else_cond, else_const_env, else_expr_env, else_rb_alias, else_vel_env))
			# Dynamic branch flow only invalidates names assigned in either branch.
			assigned_names = _collect_assigned_names_from_stmts(stmt.body)
			assigned_names.update(_collect_assigned_names_from_stmts(stmt.orelse))
			test_expr_src = _unwrap_expr_placeholder(test_expr)
			def _env_name_to_expr_text (_name, _const_env, _expr_env):
				if _name in _const_env and _is_simple_const_value(_const_env.get(_name)):
					return repr(_const_env.get(_name))
				if _name in _expr_env:
					v = _expr_env.get(_name)
					if isinstance(v, str):
						return _unwrap_expr_placeholder(v)
					if _is_simple_const_value(v):
						return repr(v)
				return None
			for assigned_name in assigned_names:
				body_expr_text = _env_name_to_expr_text(assigned_name, body_const_env, body_expr_env)
				else_expr_text = _env_name_to_expr_text(assigned_name, else_const_env, else_expr_env)
				if body_expr_text is not None and else_expr_text is not None:
					const_env.pop(assigned_name, None)
					expr_env[assigned_name] = '<expr:(' + body_expr_text + ') if (' + test_expr_src + ') else (' + else_expr_text + ')>'
				else:
					const_env.pop(assigned_name, None)
					expr_env.pop(assigned_name, None)
				rb_alias.pop(assigned_name, None)
	return prints

def _extract_print_calls_from_script (code : str, is_init : bool, owner_name : str, const_env = None, expr_env = None, rb_alias = None, vel_env = None):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return []
	const_env = const_env if isinstance(const_env, dict) else {}
	expr_env = expr_env if isinstance(expr_env, dict) else {}
	rb_alias = rb_alias if isinstance(rb_alias, dict) else {}
	vel_env = vel_env if isinstance(vel_env, dict) else {}
	return _extract_print_calls_from_stmts(
		getattr(tree, 'body', []),
		is_init,
		owner_name,
		parent_condition = None,
		const_env = const_env,
		expr_env = expr_env,
		rb_alias = rb_alias,
		vel_env = vel_env,
	)

def _strip_print_calls_from_python (code : str):
	'''Return Python code with top-level `print(...)` expression statements removed.'''
	try:
		tree = ast.parse(code or '')
	except Exception:
		return str(code or '')
	class _StripPrintExprs(ast.NodeTransformer):
		def visit_Expr (self, node):
			if (
				isinstance(node.value, ast.Call)
				and isinstance(node.value.func, ast.Name)
				and node.value.func.id == 'print'
			):
				return None
			return self.generic_visit(node)
	class _EnsureNonEmptyBlocks(ast.NodeTransformer):
		@staticmethod
		def _ensure_body(_stmts):
			if isinstance(_stmts, list) and len(_stmts) == 0:
				return [ast.Pass()]
			return _stmts
		def visit_If (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_For (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_AsyncFor (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_While (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_With (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_AsyncWith (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_Try (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			for handler in list(getattr(node, 'handlers', []) or []):
				handler.body = self._ensure_body(getattr(handler, 'body', []))
			return node
		def visit_FunctionDef (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_AsyncFunctionDef (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
		def visit_ClassDef (self, node):
			node = self.generic_visit(node)
			node.body = self._ensure_body(getattr(node, 'body', []))
			return node
	tree = _StripPrintExprs().visit(tree)
	tree = _EnsureNonEmptyBlocks().visit(tree)
	try:
		tree = ast.fix_missing_locations(tree)
	except Exception:
		pass
	try:
		return ast.unparse(tree)
	except Exception:
		return str(code or '')

def _augment_runtime_with_dynamic_circles (script_runtime : dict, script_entries : list):
	if not isinstance(script_runtime, dict):
		script_runtime = {}
	# Rebuild dynamic circle overlays from source scripts so dead branches
	# (for example `if False:`) do not leak into baked fallback rendering.
	init_draw = []
	update_draw = []
	init_display_ops = []
	for op in list(script_runtime.get('init_display_ops') or []):
		if not isinstance(op, dict):
			continue
		# Rebuild display scrolling from source scripts to keep dead branches
		# deterministic. Keep pre-parsed camera ops as a fallback path.
		if str(op.get('op') or '') in ('scroll_display_surface',):
			continue
		init_display_ops.append(op)
	update_display_ops = []
	for op in list(script_runtime.get('update_display_ops') or []):
		if not isinstance(op, dict):
			continue
		if str(op.get('op') or '') in ('scroll_display_surface',):
			continue
		update_display_ops.append(op)
	surface_ops = []
	for op in list(script_runtime.get('surface_ops') or []):
		if isinstance(op, dict) and op.get('op') == 'draw_circle_surface_member':
			continue
		surface_ops.append(op)
	existing_print_calls = [info for info in list(script_runtime.get('print_calls') or []) if isinstance(info, dict)]
	print_calls = []
	extracted_print_pairs = set()
	extracted_print_keys = set()
	entries = list(script_entries or [])
	# Match runtime semantics: init scripts run before update scripts.
	entries.sort(key = lambda e: (0 if bool((e or {}).get('is_init')) else 1))
	print_const_env_by_scope = {}
	print_expr_env_by_scope = {}
	print_const_env_by_owner = {}
	print_expr_env_by_owner = {}
	mirror_scripts = []
	for entry_idx, entry in enumerate(entries):
		code = entry.get('code', '')
		raw_code = entry.get('raw_code', code)
		analysis_code = str(raw_code if str(raw_code).strip() != '' else code)
		exec_code = str(code if str(code).strip() != '' else analysis_code)
		is_init = bool(entry.get('is_init'))
		owner_name = entry.get('owner_name') or '__world__'
		scope_key = str((owner_name, bool(is_init), entry.get('symbol_hint') or '', int(entry_idx)))
		env = {
			'const_env' : {},
			'expr_env' : {},
			'rb_alias' : {},
			'vel_env' : {},
		}
		extracted = _extract_dynamic_draw_circles_from_script(analysis_code, is_init)
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
		extracted_scrolls = _extract_dynamic_surface_scroll_ops_from_script(analysis_code, is_init)
		for scroll in extracted_scrolls:
			target_type = scroll.get('target_type')
			if target_type == 'display_surface':
				op = {
					'op' : 'scroll_display_surface',
					'dx' : scroll.get('dx') if scroll.get('dx') is not None else 0.0,
					'dy' : scroll.get('dy') if scroll.get('dy') is not None else 0.0,
				}
				if scroll.get('condition') is not None:
					op['condition'] = scroll.get('condition')
				if is_init:
					init_display_ops.append(op)
				else:
					update_display_ops.append(op)
			elif target_type == 'this_surface':
				op = {
					'op' : 'scroll_surface_member',
					'owner_name' : owner_name,
					'member' : 'surface',
					'is_init' : bool(is_init),
					'dx' : scroll.get('dx') if scroll.get('dx') is not None else 0.0,
					'dy' : scroll.get('dy') if scroll.get('dy') is not None else 0.0,
				}
				if scroll.get('condition') is not None:
					op['condition'] = scroll.get('condition')
				surface_ops.append(op)
			else:
				continue
		for info in _extract_print_calls_from_script(
			analysis_code,
			is_init,
			owner_name,
			const_env = env['const_env'],
			expr_env = env['expr_env'],
			rb_alias = env['rb_alias'],
			vel_env = env['vel_env'],
		):
			pair = (
				bool(info.get('is_init')),
				str(info.get('owner_name') or '__world__'),
			)
			extracted_print_pairs.add(pair)
			key = (
				bool(info.get('is_init')),
				str(info.get('owner_name') or '__world__'),
				str(info.get('text', '')),
				str(info.get('condition') or ''),
			)
			if key in extracted_print_keys:
				continue
			extracted_print_keys.add(key)
			info['scope_key'] = scope_key
			print_calls.append(info)
		# Persist compile-time constants for runtime print evaluation.
		print_const_env_by_scope[scope_key] = dict(env.get('const_env', {}))
		print_expr_env_by_scope[scope_key] = dict(env.get('expr_env', {}))
		# Backward-compat fallback map (owner scoped) for pre-existing entries.
		print_const_env_by_owner[owner_name] = dict(env.get('const_env', {}))
		print_expr_env_by_owner[owner_name] = dict(env.get('expr_env', {}))
		extracted_camera_ops = _extract_dynamic_set_camera_ops_from_script(analysis_code, is_init)
		# Safety net: if parser extraction missed set_camera_position calls
		# (for example due transformed wrappers), still emit a deterministic
		# owner camera op so GBC fallback does not drop camera control entirely.
		if not extracted_camera_ops and re.search(r'\bset_camera_position\s*\(', str(analysis_code or '')):
			owner_pos = _resolve_static_owner_camera_position(owner_name)
			if isinstance(owner_pos, (list, tuple)) and len(owner_pos) >= 2:
				extracted_camera_ops = [{
					'op' : 'set_display_camera_pos',
					'x' : float(owner_pos[0]),
					'y' : float(owner_pos[1]),
					'is_init' : bool(is_init),
				}]
		for camera_op in extracted_camera_ops:
			camera_op = dict(camera_op or {})
			camera_op['owner_name'] = owner_name
			camera_op['scope_key'] = scope_key
			camera_op['x'] = _inline_runtime_expr_with_env(
				camera_op.get('x', 0.0),
				const_env = env.get('const_env', {}),
				expr_env = env.get('expr_env', {}),
				rb_alias = env.get('rb_alias', {}),
				owner_name = owner_name,
			)
			camera_op['y'] = _inline_runtime_expr_with_env(
				camera_op.get('y', 0.0),
				const_env = env.get('const_env', {}),
				expr_env = env.get('expr_env', {}),
				rb_alias = env.get('rb_alias', {}),
				owner_name = owner_name,
			)
			if camera_op.get('condition') is not None:
				camera_op['condition'] = _inline_runtime_expr_with_env(
					camera_op.get('condition'),
					const_env = env.get('const_env', {}),
					expr_env = env.get('expr_env', {}),
					rb_alias = env.get('rb_alias', {}),
					owner_name = owner_name,
				)
			# Deterministic export fallback: if camera expression still references
			# transient local `pos`, rewrite to static owner coordinates so camera
			# bake never collapses to (0,0) when locals are unavailable.
			try:
				x_expr_txt = str(camera_op.get('x', ''))
			except Exception:
				x_expr_txt = ''
			try:
				y_expr_txt = str(camera_op.get('y', ''))
			except Exception:
				y_expr_txt = ''
			if ('pos[' in x_expr_txt) or ('pos[' in y_expr_txt):
				camera_op['camera_follow_owner'] = owner_name
				owner_pos = _resolve_static_owner_camera_position(owner_name)
				if isinstance(owner_pos, (list, tuple)) and len(owner_pos) >= 2:
					camera_op['x'] = float(owner_pos[0])
					camera_op['y'] = float(owner_pos[1])
					camera_op['resolved_from_owner_pos'] = True
			if is_init:
				init_display_ops.append(camera_op)
			else:
				update_display_ops.append(camera_op)
		mirror_scripts.append({
			'scope_key' : scope_key,
			'owner_name' : owner_name,
			'owner_attributes' : dict(entry.get('owner_attributes', {})) if isinstance(entry.get('owner_attributes', {}), dict) else {},
			'is_init' : bool(is_init),
			'is_global' : bool(entry.get('is_global')),
			'source_code' : str(entry.get('source_code', analysis_code) or ''),
			'source_line_offset' : int(entry.get('source_line_offset', 0) or 0),
			# Execute normalized/prefixed code so runtime compatibility shims
			# (for example cast_collider adapters) are active during mirror eval.
			# Keep print() calls in mirror code so they emit at exact execution time.
			'code' : exec_code,
		})
	# Prefer parser-rebuilt print metadata for script owner/phase pairs we handled,
	# while preserving backend-provided print calls for any untouched pairs.
	for info in existing_print_calls:
		pair = (
			bool(info.get('is_init')),
			str(info.get('owner_name') or '__world__'),
		)
		if pair in extracted_print_pairs:
			continue
		key = (
			bool(info.get('is_init')),
			str(info.get('owner_name') or '__world__'),
			str(info.get('text', '')),
			str(info.get('condition') or ''),
		)
		if key in extracted_print_keys:
			continue
		extracted_print_keys.add(key)
		print_calls.append(info)
	has_set_camera_op = False
	for _op in list(init_display_ops or []):
		if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
			has_set_camera_op = True
			break
	if not has_set_camera_op:
		for _op in list(update_display_ops or []):
			if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
				has_set_camera_op = True
				break
	if has_set_camera_op:
		init_display_ops = [
			_op for _op in list(init_display_ops or [])
			if not (isinstance(_op, dict) and str(_op.get('op') or '') == 'scroll_display_surface')
		]
		update_display_ops = [
			_op for _op in list(update_display_ops or [])
			if not (isinstance(_op, dict) and str(_op.get('op') or '') == 'scroll_display_surface')
		]
	script_runtime['init_draw_circles'] = init_draw
	script_runtime['update_draw_circles'] = update_draw
	script_runtime['init_display_ops'] = init_display_ops
	script_runtime['update_display_ops'] = update_display_ops
	script_runtime['surface_ops'] = surface_ops
	script_runtime['print_calls'] = print_calls
	script_runtime['print_const_env_by_scope'] = print_const_env_by_scope
	script_runtime['print_expr_env_by_scope'] = print_expr_env_by_scope
	script_runtime['print_const_env_by_owner'] = print_const_env_by_owner
	script_runtime['print_expr_env_by_owner'] = print_expr_env_by_owner
	script_runtime['mirror_scripts'] = mirror_scripts
	return script_runtime

def _resolve_static_owner_camera_position (owner_name):
	'''Best-effort static owner position for export-time camera op fallback.'''
	if not isinstance(owner_name, str) or owner_name == '' or owner_name == '__world__':
		return None
	def _author_pos_from_object (_ob):
		try:
			# Script-facing fallback should mirror authored Blender location directly.
			return [float(_ob.location.x), float(-_ob.location.y)]
		except Exception:
			pass
		try:
			_pose, _rot = _gba_get_object_pose(_ob)
			return [float(_pose[0]), float(_pose[1])]
		except Exception:
			pass
		return None
	def _norm_owner_key (_name):
		try:
			s = str(_name)
		except Exception:
			return ''
		s = s.lstrip('_').lower()
		out = ''
		for ch in s:
			if ('a' <= ch <= 'z') or ('0' <= ch <= '9') or ch == '_':
				out += ch
		return out
	try:
		owner_candidates = list(_script_lookup_candidate_names(owner_name))
	except Exception:
		owner_candidates = [owner_name]
	if owner_name not in owner_candidates:
		owner_candidates.insert(0, owner_name)
	try:
		runtime_globals = __import__('builtins').globals()
	except Exception:
		runtime_globals = {}
	_spawn_overrides = runtime_globals.get('_gbc_spawn_owner_pos_overrides', {})
	if isinstance(_spawn_overrides, dict):
		for cand in owner_candidates:
			try:
				_pos = _resolve_script_lookup(_spawn_overrides, cand)
			except Exception:
				_pos = None
			if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
				try:
					_x = float(_pos[0]); _y = float(_pos[1])
					if (abs(_x) + abs(_y)) > 1e-6:
						return [_x, _y]
				except Exception:
					pass
	try:
		_objects = bpy.data.objects
	except Exception:
		_objects = None
	if _objects is not None:
		for cand in owner_candidates:
			try:
				_ob = _objects.get(cand)
			except Exception:
				_ob = None
			if _ob is None:
				continue
			try:
				_p = _author_pos_from_object(_ob)
				if isinstance(_p, (list, tuple)) and len(_p) >= 2:
					return [float(_p[0]), float(_p[1])]
			except Exception:
				try:
					_pos = GetObjectPosition(_ob)
					if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
						return [float(_pos[0]), float(_pos[1])]
				except Exception:
					pass
				continue
		# Fuzzy fallback for normalized script keys (example: "_Ground001"
		# should resolve authored object "Ground.001").
		target_norms = set()
		for cand in owner_candidates:
			norm = _norm_owner_key(cand)
			if norm != '':
				target_norms.add(norm)
		for norm in list(target_norms):
			for _ob in list(_objects):
				try:
					name_norm = _norm_owner_key(getattr(_ob, 'name', ''))
				except Exception:
					name_norm = ''
				if name_norm != norm:
					continue
				try:
					_p = _author_pos_from_object(_ob)
					if isinstance(_p, (list, tuple)) and len(_p) >= 2:
						return [float(_p[0]), float(_p[1])]
				except Exception:
					try:
						_pos = GetObjectPosition(_ob)
						if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
							return [float(_pos[0]), float(_pos[1])]
					except Exception:
						pass
					continue
	return None

def _runtime_expr_extra_env_for_display_op (op):
	if not isinstance(op, dict):
		return {}
	owner_name = str(op.get('owner_name') or '')
	scope_key = str(op.get('scope_key') or '')
	if owner_name == '' and scope_key == '':
		return {}
	try:
		runtime_globals = __import__('builtins').globals()
	except Exception:
		runtime_globals = {}
	all_script_locals = runtime_globals.get('scriptLocals', {})
	if not isinstance(all_script_locals, dict):
		all_script_locals = {}
	owner_candidates = []
	try:
		owner_candidates = list(_script_lookup_candidate_names(owner_name))
	except Exception:
		owner_candidates = [owner_name]
	if owner_name not in owner_candidates:
		owner_candidates.insert(0, owner_name)
	scope_key_obj = None
	if scope_key != '':
		try:
			scope_key_obj = ast.literal_eval(scope_key)
		except Exception:
			scope_key_obj = None
	owner_scopes = []
	for candidate in owner_candidates:
		scope = all_script_locals.get(candidate)
		if isinstance(scope, dict):
			owner_scopes.append(scope)
	# Fallback: include fuzzy owner-key matches if direct lookup misses.
	if owner_scopes == [] and owner_name != '':
		try:
			owner_norm = _normalize_script_lookup_key(owner_name)
		except Exception:
			owner_norm = owner_name.lower().replace(' ', '_')
		for key, scope in list(all_script_locals.items()):
			if not isinstance(key, str) or not isinstance(scope, dict):
				continue
			try:
				key_norm = _normalize_script_lookup_key(key)
			except Exception:
				key_norm = key.lower().replace(' ', '_')
			if (
				key_norm == owner_norm
				or key_norm.endswith('_' + owner_norm)
				or key_norm.endswith(owner_norm)
				or key_norm.startswith(owner_norm + '_')
				or key_norm.startswith(owner_norm)
			):
				owner_scopes.append(scope)
	def _resolve_exact_nested_scope (_scope_dict):
		if not isinstance(_scope_dict, dict) or scope_key == '':
			return None
		exact = _scope_dict.get(scope_key)
		if isinstance(exact, dict):
			return dict(exact)
		if scope_key_obj is not None:
			exact_obj = _scope_dict.get(scope_key_obj)
			if isinstance(exact_obj, dict):
				return dict(exact_obj)
		if any(isinstance(v, dict) for v in _scope_dict.values()):
			for nested_key, nested in _scope_dict.items():
				if not isinstance(nested, dict):
					continue
				if str(nested_key) == scope_key:
					return dict(nested)
				if scope_key_obj is not None and nested_key == scope_key_obj:
					return dict(nested)
		return None
	base_env = {}
	for scope in owner_scopes:
		exact = _resolve_exact_nested_scope(scope)
		if isinstance(exact, dict):
			base_env.update(exact)
			break
	# Legacy layout: scriptLocals[owner] = locals dict.
	if base_env == {}:
		for scope in owner_scopes:
			if isinstance(scope, dict) and not any(isinstance(v, dict) for v in scope.values()):
				base_env.update(dict(scope))
				break
	# Owner-level fallback: merge nested script locals (latest wins) so dynamic
	# camera expressions can still resolve names like `pos` when scope keys differ.
	merged = {}
	for scope in owner_scopes:
		if not isinstance(scope, dict):
			continue
		if any(isinstance(v, dict) for v in scope.values()):
			for nested in scope.values():
				if isinstance(nested, dict):
					merged.update(dict(nested))
		else:
			merged.update(dict(scope))
	if merged:
		base_env.update(merged)
	if scope_key != '':
		for owner_scope in all_script_locals.values():
			if not isinstance(owner_scope, dict):
				continue
			if scope_key in owner_scope and isinstance(owner_scope.get(scope_key), dict):
				base_env.update(dict(owner_scope.get(scope_key)))
				break
			if scope_key_obj is not None and scope_key_obj in owner_scope and isinstance(owner_scope.get(scope_key_obj), dict):
				base_env.update(dict(owner_scope.get(scope_key_obj)))
				break
	# Always provide core runtime helpers so camera expressions can resolve even
	# when scriptLocals scope keys differ from extracted op metadata.
	sim_runtime = runtime_globals.get('sim', runtime_globals.get('physics', None))
	rigid_bodies_runtime = runtime_globals.get('rigidBodiesIds', runtime_globals.get('rigidbodies', {}))
	rigid_bodies_named = runtime_globals.get('rigidBodies', runtime_globals.get('rbs', {}))
	colliders_runtime = runtime_globals.get('collidersIds', runtime_globals.get('colliders', {}))
	colliders_named = runtime_globals.get('cols', colliders_runtime)
	def _get_rigidbody_for_eval (_name):
		try:
			return _resolve_script_lookup_from_sources(_name, rigid_bodies_runtime, rigid_bodies_named)
		except Exception:
			return None
	def _get_collider_for_eval (_name):
		try:
			return _resolve_script_lookup_from_sources(_name, colliders_runtime, colliders_named)
		except Exception:
			return None
	base_env.setdefault('sim', sim_runtime)
	base_env.setdefault('physics', sim_runtime)
	base_env.setdefault('get_rigidbody', _get_rigidbody_for_eval)
	base_env.setdefault('get_collider', _get_collider_for_eval)
	# Synthesize owner-scoped bindings for common camera expressions like
	# `int(pos[0])` and `sim.get_rigid_body_position(this.rb)[0]`.
	if owner_name != '':
		rb = _get_rigidbody_for_eval(owner_name)
		col = _get_collider_for_eval(owner_name)
		if 'this' not in base_env:
			try:
				_this_obj = type('DisplayOpThis', (), {})()
				_this_obj.id = owner_name
				_this_obj.name = owner_name
				_this_obj.rb = rb
				_this_obj.col = col
				base_env['this'] = _this_obj
			except Exception:
				pass
		if 'rb' not in base_env and rb is not None:
			base_env['rb'] = rb
		if 'col' not in base_env and col is not None:
			base_env['col'] = col
		if 'pos' not in base_env and sim_runtime is not None and rb is not None and hasattr(sim_runtime, 'get_rigid_body_position'):
			try:
				_pos = sim_runtime.get_rigid_body_position(rb)
				if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
					base_env['pos'] = [float(_pos[0]), float(_pos[1])]
				else:
					base_env['pos'] = _pos
			except Exception:
				pass
		# Export-time fallback: when runtime physics handles are not available yet,
		# synthesize `pos` from authored object transforms so expressions like
		# `int(pos[0])` still resolve deterministically.
		if 'pos' not in base_env:
			try:
				_spawn_overrides = runtime_globals.get('_gbc_spawn_owner_pos_overrides', {})
				_spawn_pos = _resolve_script_lookup(_spawn_overrides, owner_name) if isinstance(_spawn_overrides, dict) else None
			except Exception:
				_spawn_pos = None
			if isinstance(_spawn_pos, (list, tuple)) and len(_spawn_pos) >= 2:
				try:
					base_env['pos'] = [float(_spawn_pos[0]), float(_spawn_pos[1])]
				except Exception:
					pass
		if 'pos' not in base_env:
			try:
				_bpy = globals().get('bpy', None)
				_owner_ob = getattr(getattr(_bpy, 'data', None), 'objects', {}).get(owner_name) if _bpy is not None else None
			except Exception:
				_owner_ob = None
			if _owner_ob is not None:
				try:
					if (
						getattr(_owner_ob, 'type', None) == 'EMPTY'
						and getattr(_owner_ob, 'empty_display_type', None) == 'IMAGE'
						and getattr(_owner_ob, 'data', None) is not None
					):
						_ctr = GetImageCenterPosition(_owner_ob)
						base_env['pos'] = [float(_ctr.x), float(_ctr.y)]
					else:
						base_env['pos'] = [float(_owner_ob.location.x), float(-_owner_ob.location.y)]
				except Exception:
					pass
	return base_env

def _trace_display_camera_eval (stage, op, frame, x_expr, y_expr, x_val, y_val, x_u16, y_u16, extra_env = None):
	try:
		_pos_present = False
		_pos_preview = None
		if isinstance(extra_env, dict):
			_pos_present = ('pos' in extra_env)
			if _pos_present:
				try:
					_pos_preview = extra_env.get('pos')
				except Exception:
					_pos_preview = None
		_append_gbc_trace_lines([
			'[gbc-trace] CameraEval'
			+ ':stage=' + str(stage)
			+ ',frame=' + str(int(frame or 0))
			+ ',owner=' + str(op.get('owner_name') or '')
			+ ',scope=' + str(op.get('scope_key') or '')
			+ ',pos_present=' + ('1' if _pos_present else '0')
			+ ',pos=' + repr(_pos_preview)
			+ ',x_expr=' + repr(x_expr)
			+ ',y_expr=' + repr(y_expr)
			+ ',x_val=' + repr(x_val)
			+ ',y_val=' + repr(y_val)
			+ ',x_u16=' + str(int(x_u16) & 0xFFFF)
			+ ',y_u16=' + str(int(y_u16) & 0xFFFF),
		])
	except Exception:
		pass

def _fallback_owner_camera_position (op, extra_env = None):
	if not isinstance(op, dict):
		return None
	owner_name = str(op.get('owner_name') or '')
	if owner_name == '':
		return None
	try:
		owner_candidates = list(_script_lookup_candidate_names(owner_name))
	except Exception:
		owner_candidates = [owner_name]
	if owner_name not in owner_candidates:
		owner_candidates.insert(0, owner_name)
	# First try runtime physics binding from eval env.
	try:
		env = extra_env if isinstance(extra_env, dict) else {}
		_sim = env.get('sim', env.get('physics', None))
		_rb = env.get('rb', None)
		if _rb is None and callable(env.get('get_rigidbody', None)):
			for cand in owner_candidates:
				_rb = env.get('get_rigidbody')(cand)
				if _rb is not None:
					break
		if _sim is not None and _rb is not None and hasattr(_sim, 'get_rigid_body_position'):
			_pos = _sim.get_rigid_body_position(_rb)
			if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
				return [float(_pos[0]), float(_pos[1])]
	except Exception:
		pass
	# Then try export-time spawn owner overrides.
	try:
		runtime_globals = __import__('builtins').globals()
		_spawn_overrides = runtime_globals.get('_gbc_spawn_owner_pos_overrides', {})
		_spawn_pos = None
		if isinstance(_spawn_overrides, dict):
			_spawn_pos = _resolve_script_lookup(_spawn_overrides, owner_name)
			if _spawn_pos is None:
				for cand in owner_candidates:
					_spawn_pos = _resolve_script_lookup(_spawn_overrides, cand)
					if _spawn_pos is not None:
						break
		if isinstance(_spawn_pos, (list, tuple)) and len(_spawn_pos) >= 2:
			return [float(_spawn_pos[0]), float(_spawn_pos[1])]
	except Exception:
		pass
	# Runtime object position fallback (works even when physics handles are not bound).
	try:
		runtime_globals = __import__('builtins').globals()
		_get_pos = runtime_globals.get('get_object_position', None)
		if callable(_get_pos):
			for cand in owner_candidates:
				try:
					_obj_pos = _get_pos(cand)
				except Exception:
					_obj_pos = None
				if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
					return [float(_obj_pos[0]), float(_obj_pos[1])]
		_obs = runtime_globals.get('obs', runtime_globals.get('objects', {}))
		if isinstance(_obs, dict):
			for cand in owner_candidates:
				_entry = _resolve_script_lookup(_obs, cand)
				if isinstance(_entry, dict):
					try:
						_obj_pos = _entry.get('pos', _entry.get('position', None))
					except Exception:
						_obj_pos = None
					if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
						return [float(_obj_pos[0]), float(_obj_pos[1])]
	except Exception:
		pass
	# Last resort: authored object position.
	try:
		_bpy = globals().get('bpy', None)
		_owner_ob = None
		_objects = getattr(getattr(_bpy, 'data', None), 'objects', None) if _bpy is not None else None
		if _objects is not None:
			for cand in owner_candidates:
				try:
					_owner_ob = _objects.get(cand)
				except Exception:
					_owner_ob = None
				if _owner_ob is not None:
					break
			if _owner_ob is None:
				try:
					owner_norm = _normalize_script_lookup_key(owner_name)
				except Exception:
					owner_norm = owner_name.lower().replace(' ', '_')
				try:
					for ob in list(_objects):
						name = str(getattr(ob, 'name', ''))
						try:
							name_norm = _normalize_script_lookup_key(name)
						except Exception:
							name_norm = name.lower().replace(' ', '_')
						if (
							name_norm == owner_norm
							or name_norm.endswith('_' + owner_norm)
							or name_norm.endswith(owner_norm)
							or name_norm.startswith(owner_norm + '_')
							or name_norm.startswith(owner_norm)
						):
							_owner_ob = ob
							break
				except Exception:
					pass
	except Exception:
		_owner_ob = None
	if _owner_ob is not None:
		try:
			if (
				getattr(_owner_ob, 'type', None) == 'EMPTY'
				and getattr(_owner_ob, 'empty_display_type', None) == 'IMAGE'
				and getattr(_owner_ob, 'data', None) is not None
			):
				_ctr = GetImageCenterPosition(_owner_ob)
				return [float(_ctr.x), float(_ctr.y)]
			return [float(_owner_ob.location.x), float(-_owner_ob.location.y)]
		except Exception:
			pass
	return None

def _inject_gbc_signed_position_wrappers (code : str):
	code = str(code or '')
	if '_js13k_gbc_signed_pos_wrapped' in code:
		return code
	prefix = (
		'_js13k_gbc_signed_pos_wrapped = True\n'
		'try:\n'
		'    sim = sim\n'
		'except:\n'
		'    try:\n'
		'        sim = physics\n'
		'    except:\n'
		'        sim = None\n'
		'_js13k_gbc_cam_x = int(globals().get("_js13k_gbc_cam_x", 0) or 0)\n'
		'_js13k_gbc_cam_y = int(globals().get("_js13k_gbc_cam_y", 0) or 0)\n'
		'_js13k_gbc_cam_x = int(_js13k_gbc_cam_x) & 0xFFFF\n'
		'_js13k_gbc_cam_y = int(_js13k_gbc_cam_y) & 0xFFFF\n'
		'def set_camera_position(x, y):\n'
		'    global _js13k_gbc_cam_x, _js13k_gbc_cam_y\n'
		'    try:\n'
		'        new_x = int(round(float(x)))\n'
		'    except:\n'
		'        new_x = int(_js13k_gbc_cam_x)\n'
		'    try:\n'
		'        new_y = int(round(float(y)))\n'
		'    except:\n'
		'        new_y = int(_js13k_gbc_cam_y)\n'
		'    new_x = int(new_x) & 0xFFFF\n'
		'    new_y = int(new_y) & 0xFFFF\n'
		'    _js13k_gbc_cam_x = int(new_x)\n'
		'    _js13k_gbc_cam_y = int(new_y)\n'
		'    globals()["_js13k_gbc_cam_x"] = int(_js13k_gbc_cam_x)\n'
		'    globals()["_js13k_gbc_cam_y"] = int(_js13k_gbc_cam_y)\n'
		'    try:\n'
		'        _off = globals().get("off", None)\n'
		'        if _off is not None:\n'
		'            _off.x = float(_js13k_gbc_cam_x)\n'
		'            _off.y = float(_js13k_gbc_cam_y)\n'
		'    except:\n'
		'        pass\n'
		'    return [float(_js13k_gbc_cam_x), float(_js13k_gbc_cam_y)]\n'
		'def _js13k_gbc_validate_cast_shape_args(*args, **kwargs):\n'
		'    if len(args) < 6:\n'
		'        raise TypeError("world.castShape requires at least 6 positional args: shapePos, shapeRot, shapeVel, shape, maxToi, stopAtPenetration")\n'
		'    if len(args) > 7:\n'
		'        raise TypeError("world.castShape accepts at most 7 positional args")\n'
		'    if kwargs:\n'
		'        allowed = {"collisionGroupFilter", "collision_group_filter"}\n'
		'        unknown = [k for k in kwargs if k not in allowed]\n'
		'        if len(unknown) > 0:\n'
		'            raise TypeError("world.castShape got unexpected keyword argument(s): " + ", ".join([str(k) for k in unknown]))\n'
		'def _js13k_gbc_normalize_cast_hit(_hit):\n'
		'    if _hit is None:\n'
		'        return None\n'
		'    try:\n'
		'        if isinstance(_hit, bool):\n'
		'            return _hit\n'
		'    except:\n'
		'        pass\n'
		'    try:\n'
		'        if isinstance(_hit, (int, float)):\n'
		'            return {"collider": int(_hit), "hit": True}\n'
		'    except:\n'
		'        pass\n'
		'    return _hit\n'
		'_js13k_gbc_user_cast_shape_guard = {"busy": False, "warned": False}\n'
		'def _js13k_gbc_user_cast_shape(shape_pos, shape_rot, shape_vel, shape, max_toi, stop_at_penetration, collision_group_filter = None):\n'
		'    try:\n'
		'        if bool(_js13k_gbc_user_cast_shape_guard.get("busy", False)):\n'
		'            return None\n'
		'        _js13k_gbc_user_cast_shape_guard["busy"] = True\n'
		'        _resolved_shape = shape\n'
		'        try:\n'
		'            _resolved_shape = _js13k_gbc_resolve_collider_handle(shape)\n'
		'        except:\n'
		'            pass\n'
		'        try:\n'
		'            cast_shape_guarded_fn = globals().get("_js13k_gbc_orig_cast_shape_guarded", None)\n'
		'            if callable(cast_shape_guarded_fn):\n'
		'                _hit = cast_shape_guarded_fn(shape_pos, shape_rot, shape_vel, _resolved_shape, max_toi, stop_at_penetration, collision_group_filter)\n'
		'                _hit = _js13k_gbc_normalize_cast_hit(_hit)\n'
		'                _js13k_gbc_cast_debug_log("user_cast_shape_guarded_out", {"hit": _hit})\n'
		'                if _hit is not None:\n'
		'                    return _hit\n'
		'        except RecursionError:\n'
		'            pass\n'
		'        except:\n'
		'            pass\n'
		'        try:\n'
		'            cast_shape_orig_fn = globals().get("_js13k_gbc_orig_cast_shape", None)\n'
		'            if callable(cast_shape_orig_fn):\n'
		'                _cast_pos = _js13k_gbc_bias_pos_for_cast(shape_pos)\n'
		'                _cast_vel = _js13k_gbc_bias_vel_for_cast(shape_vel)\n'
		'                _hit = cast_shape_orig_fn(_cast_pos, shape_rot, _cast_vel, _resolved_shape, max_toi, stop_at_penetration, collision_group_filter)\n'
		'                _hit = _js13k_gbc_normalize_cast_hit(_hit)\n'
		'                _js13k_gbc_cast_debug_log("user_cast_shape_orig_out", {"hit": _hit})\n'
		'                if _hit is not None:\n'
		'                    return _hit\n'
		'        except RecursionError:\n'
		'            pass\n'
		'        except:\n'
		'            _js13k_gbc_cast_debug_log("user_cast_shape_orig_error", {"shape": str(shape)})\n'
		'        _runtime_fns = []\n'
		'        try:\n'
		'            _sim_cast_shape = getattr(sim, "cast_shape", None)\n'
		'            if callable(_sim_cast_shape):\n'
		'                _runtime_fns.append(("sim.cast_shape", _sim_cast_shape))\n'
		'        except:\n'
		'            pass\n'
		'        try:\n'
		'            _sim_cast_shape_camel = getattr(sim, "castShape", None)\n'
		'            if callable(_sim_cast_shape_camel):\n'
		'                _runtime_fns.append(("sim.castShape", _sim_cast_shape_camel))\n'
		'        except:\n'
		'            pass\n'
		'        try:\n'
		'            _world = globals().get("world", None)\n'
		'            _world_cast_shape = getattr(_world, "castShape", None) if _world is not None else None\n'
		'            if callable(_world_cast_shape):\n'
		'                _runtime_fns.append(("world.castShape", _world_cast_shape))\n'
		'        except:\n'
		'            pass\n'
		'        _seen_runtime = set()\n'
		'        for _fn_name, _fn in _runtime_fns:\n'
		'            try:\n'
		'                _fn_id = id(_fn)\n'
		'                if _fn_id in _seen_runtime:\n'
		'                    continue\n'
		'                _seen_runtime.add(_fn_id)\n'
		'            except:\n'
		'                pass\n'
		'            try:\n'
		'                if _fn is _js13k_gbc_user_cast_shape:\n'
		'                    continue\n'
		'            except:\n'
		'                pass\n'
		'            try:\n'
		'                _hit = _fn(shape_pos, shape_rot, shape_vel, _resolved_shape, max_toi, stop_at_penetration, collision_group_filter)\n'
		'                _hit = _js13k_gbc_normalize_cast_hit(_hit)\n'
		'                if _hit is not None:\n'
		'                    _js13k_gbc_cast_debug_log("user_cast_shape_runtime_out", {"fn": _fn_name, "hit": _hit})\n'
		'                if _hit is not None:\n'
		'                    return _hit\n'
		'            except RecursionError:\n'
		'                pass\n'
		'            except:\n'
		'                _js13k_gbc_cast_debug_log("user_cast_shape_runtime_error", {"shape": str(shape), "fn": _fn_name})\n'
		'        if not bool(_js13k_gbc_user_cast_shape_guard.get("warned", False)):\n'
		'            _js13k_gbc_cast_debug_log("user_cast_shape_unavailable", {"shape": str(shape)})\n'
		'            _js13k_gbc_user_cast_shape_guard["warned"] = True\n'
		'        return None\n'
		'    finally:\n'
		'        _js13k_gbc_user_cast_shape_guard["busy"] = False\n'
		'_js13k_gbc_user_cast_collider_guard = {"busy": False, "warned": False}\n'
		'def _js13k_gbc_user_cast_collider(shape, shape_vel, shape_pos, shape_rot, collision_group_filter = None):\n'
		'    try:\n'
		'        if bool(_js13k_gbc_user_cast_collider_guard.get("busy", False)):\n'
		'            return None\n'
		'        _js13k_gbc_user_cast_collider_guard["busy"] = True\n'
		'        _resolved_shape = shape\n'
		'        try:\n'
		'            _resolved_shape = _js13k_gbc_resolve_collider_handle(shape)\n'
		'        except:\n'
		'            pass\n'
		'        _cast_pos = _js13k_gbc_bias_pos_for_cast(shape_pos)\n'
		'        _cast_vel = _js13k_gbc_bias_vel_for_cast(shape_vel)\n'
		'        _sim_cast_collider = None\n'
		'        try:\n'
		'            _sim_cast_collider = getattr(sim, "cast_collider", None)\n'
		'        except:\n'
		'            _sim_cast_collider = None\n'
		'        if not callable(_sim_cast_collider):\n'
		'            if not bool(_js13k_gbc_user_cast_collider_guard.get("warned", False)):\n'
		'                _js13k_gbc_cast_debug_log("user_cast_collider_unavailable", {"shape": str(shape)})\n'
		'                _js13k_gbc_user_cast_collider_guard["warned"] = True\n'
		'            return None\n'
		'        _hit = _sim_cast_collider(_resolved_shape, _cast_vel, _cast_pos, shape_rot, collision_group_filter)\n'
		'        _hit = _js13k_gbc_normalize_cast_hit(_hit)\n'
		'        _js13k_gbc_cast_debug_log("user_cast_collider_out", {"hit": _hit})\n'
		'        return _hit\n'
		'    except RecursionError:\n'
		'        return None\n'
		'    except:\n'
		'        _js13k_gbc_cast_debug_log("user_cast_collider_error", {"shape": str(shape)})\n'
		'        return None\n'
		'    finally:\n'
		'        _js13k_gbc_user_cast_collider_guard["busy"] = False\n'
		'def _js13k_gbc_bias_pos_for_cast(_pos):\n'
		'    try:\n'
		'        return [\n'
		'            (float(_pos[0]) + 32768.0) % 65536.0,\n'
		'            ((-float(_pos[1])) + 32768.0) % 65536.0,\n'
		'        ]\n'
		'    except:\n'
		'        return _pos\n'
		'def _js13k_gbc_bias_vel_for_cast(_vel):\n'
		'    try:\n'
		'        return [\n'
		'            float(_vel[0]),\n'
		'            -float(_vel[1]),\n'
		'        ]\n'
		'    except:\n'
		'        return _vel\n'
		'_js13k_gbc_cast_debug_count = 0\n'
		'_js13k_gbc_cast_debug_limit = 4000\n'
		'def _js13k_gbc_cast_debug_log(stage, payload):\n'
		'    global _js13k_gbc_cast_debug_count\n'
		'    try:\n'
		'        if int(_js13k_gbc_cast_debug_count) >= int(_js13k_gbc_cast_debug_limit):\n'
		'            return\n'
		'        print("[gbc-cast-debug]", stage, payload)\n'
		'        _js13k_gbc_cast_debug_count = int(_js13k_gbc_cast_debug_count) + 1\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "cast_shape") and not getattr(sim, "_js13k_gbc_cast_shape_validated", False):\n'
		'    _js13k_gbc_orig_cast_shape = sim.cast_shape\n'
		'    _js13k_gbc_orig_cast_collider = sim.cast_collider if hasattr(sim, "cast_collider") else None\n'
		'    def _js13k_gbc_cast_shape_checked(*args, **kwargs):\n'
		'        _js13k_gbc_validate_cast_shape_args(*args, **kwargs)\n'
		'        _args = list(args)\n'
		'        _orig_pos = _args[0]\n'
		'        _orig_vel = _args[2]\n'
		'        _args[0] = _js13k_gbc_bias_pos_for_cast(_args[0])\n'
		'        _args[2] = _js13k_gbc_bias_vel_for_cast(_args[2])\n'
		'        _js13k_gbc_cast_debug_log("in", {"orig_pos": _orig_pos, "orig_vel": _orig_vel, "cast_pos": _args[0], "cast_vel": _args[2], "shape": str(_args[3])})\n'
		'        if _js13k_gbc_orig_cast_collider is not None:\n'
		'            _cgf = None\n'
		'            if len(_args) > 6:\n'
		'                _cgf = _args[6]\n'
		'            elif "collisionGroupFilter" in kwargs:\n'
		'                _cgf = kwargs.get("collisionGroupFilter")\n'
		'            elif "collision_group_filter" in kwargs:\n'
		'                _cgf = kwargs.get("collision_group_filter")\n'
		'            try:\n'
		'                _hit = _js13k_gbc_orig_cast_collider(_args[3], _args[2], _args[0], _args[1], _cgf)\n'
		'                _js13k_gbc_cast_debug_log("cast_collider", {"hit": _hit, "cgf": _cgf})\n'
		'                if _hit is not None:\n'
		'                    return _hit\n'
		'            except:\n'
		'                _js13k_gbc_cast_debug_log("cast_collider_error", {"shape": str(_args[3])})\n'
		'                pass\n'
		'        _shape_hit = _js13k_gbc_orig_cast_shape(*tuple(_args), **kwargs)\n'
		'        _js13k_gbc_cast_debug_log("cast_shape", {"hit": _shape_hit})\n'
		'        return _shape_hit\n'
		'    try:\n'
		'        sim.cast_shape = _js13k_gbc_cast_shape_checked\n'
		'        sim._js13k_gbc_cast_shape_validated = True\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "cast_collider") and not hasattr(sim, "cast_shape"):\n'
		'    def _js13k_gbc_cast_shape_from_collider(*args, **kwargs):\n'
		'        _js13k_gbc_validate_cast_shape_args(*args, **kwargs)\n'
		'        shape_pos = args[0]\n'
		'        shape_rot = args[1]\n'
		'        shape_vel = args[2]\n'
		'        shape = args[3]\n'
		'        shape_pos = _js13k_gbc_bias_pos_for_cast(shape_pos)\n'
		'        shape_vel = _js13k_gbc_bias_vel_for_cast(shape_vel)\n'
		'        collision_group_filter = None\n'
		'        if len(args) > 6:\n'
		'            collision_group_filter = args[6]\n'
		'        elif "collisionGroupFilter" in kwargs:\n'
		'            collision_group_filter = kwargs.get("collisionGroupFilter")\n'
		'        elif "collision_group_filter" in kwargs:\n'
		'            collision_group_filter = kwargs.get("collision_group_filter")\n'
		'        _js13k_gbc_cast_debug_log("from_collider_in", {"shape": str(shape), "cast_pos": shape_pos, "cast_vel": shape_vel, "cgf": collision_group_filter})\n'
		'        _hit = sim.cast_collider(shape, shape_vel, shape_pos, shape_rot, collision_group_filter)\n'
		'        _js13k_gbc_cast_debug_log("from_collider_out", {"hit": _hit})\n'
		'        return _hit\n'
		'    try:\n'
		'        sim.cast_shape = _js13k_gbc_cast_shape_from_collider\n'
		'        sim._js13k_gbc_cast_shape_validated = True\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and (not hasattr(sim, "cast_shape")) and hasattr(sim, "cast_collider"):\n'
		'    class _GbcSimCastShapeProxy:\n'
		'        def __init__(self, _sim):\n'
		'            self._sim = _sim\n'
		'        def cast_shape(self, *args, **kwargs):\n'
		'            return _js13k_gbc_cast_shape_from_collider(*args, **kwargs)\n'
		'        def __getattr__(self, _name):\n'
		'            return getattr(self._sim, _name)\n'
		'    sim = _GbcSimCastShapeProxy(sim)\n'
		'if False and (sim is not None) and hasattr(sim, "cast_shape") and not getattr(sim, "_js13k_gbc_cast_shape_reentry_guarded", False):\n'
		'    _js13k_gbc_orig_cast_shape_guarded = sim.cast_shape\n'
		'    _js13k_gbc_cast_shape_guard_state = {"busy": False}\n'
		'    def _js13k_gbc_cast_shape_no_recurse(*args, **kwargs):\n'
		'        try:\n'
		'            if bool(_js13k_gbc_cast_shape_guard_state.get("busy", False)):\n'
		'                _js13k_gbc_cast_debug_log("cast_shape_recursion_blocked", {"shape": str(args[3]) if len(args) > 3 else "?"})\n'
		'                return None\n'
		'            _js13k_gbc_cast_shape_guard_state["busy"] = True\n'
		'            return _js13k_gbc_orig_cast_shape_guarded(*args, **kwargs)\n'
		'        finally:\n'
		'            _js13k_gbc_cast_shape_guard_state["busy"] = False\n'
		'    try:\n'
		'        sim.cast_shape = _js13k_gbc_cast_shape_no_recurse\n'
		'        sim._js13k_gbc_cast_shape_reentry_guarded = True\n'
		'    except:\n'
		'        pass\n'
		'_js13k_gbc_pos_bias = 32768.0\n'
		'def _js13k_gbc_bias_pos_for_set(_pos):\n'
		'    try:\n'
		'        return [\n'
		'            (float(_pos[0]) + _js13k_gbc_pos_bias) % 65536.0,\n'
		'            ((-float(_pos[1])) + _js13k_gbc_pos_bias) % 65536.0,\n'
		'        ]\n'
		'    except:\n'
		'        return _pos\n'
		'def _js13k_gbc_unbias_pos_for_get(_pos):\n'
		'    try:\n'
		'        return [\n'
		'            float(_pos[0]) - _js13k_gbc_pos_bias,\n'
		'            -(float(_pos[1]) - _js13k_gbc_pos_bias),\n'
		'        ]\n'
		'    except:\n'
		'        return [0.0, 0.0]\n'
		'def _js13k_gbc_resolve_collider_handle(_collider):\n'
		'    try:\n'
		'        if isinstance(_collider, (tuple, list)) and len(_collider) == 2:\n'
		'            int(_collider[0])\n'
		'            int(_collider[1])\n'
		'            return _collider\n'
		'    except:\n'
		'        pass\n'
		'    try:\n'
		'        if isinstance(_collider, str):\n'
		'            _parsed = ast.literal_eval(_collider)\n'
		'            if isinstance(_parsed, (tuple, list)) and len(_parsed) == 2:\n'
		'                _a = int(_parsed[0])\n'
		'                _b = int(_parsed[1])\n'
		'                return (_a, _b)\n'
		'    except:\n'
		'        pass\n'
		'    _key = ""\n'
		'    if isinstance(_collider, str):\n'
		'        _key = _collider\n'
		'    else:\n'
		'        try:\n'
		'            _key = str(getattr(_collider, "id"))\n'
		'        except:\n'
		'            try:\n'
		'                _key = str(_collider)\n'
		'            except:\n'
		'                _key = ""\n'
		'    if _key == "":\n'
		'        return _collider\n'
		'    _candidates = [_key]\n'
		'    try:\n'
		'        if _key.startswith("_"):\n'
		'            _candidates.append(_key[1:])\n'
		'        else:\n'
		'            _candidates.append("_" + _key)\n'
		'        if not _key.endswith(":0"):\n'
		'            _candidates.append(_key + ":0")\n'
		'            if _key.startswith("_"):\n'
		'                _candidates.append(_key[1:] + ":0")\n'
		'            else:\n'
		'                _candidates.append("_" + _key + ":0")\n'
		'        if _key.startswith("__gbc_spawn_"):\n'
		'            _suffix = _key[len("__gbc_spawn_"): ]\n'
		'            _phys = "__gbc_spawnphys_" + _suffix\n'
		'            _candidates.append(_phys)\n'
		'            _candidates.append("_" + _phys)\n'
		'            _candidates.append(_phys + ":0")\n'
		'            _candidates.append("_" + _phys + ":0")\n'
		'        elif _key.startswith("__gbc_spawnphys_"):\n'
		'            _suffix = _key[len("__gbc_spawnphys_"): ]\n'
		'            _draw = "__gbc_spawn_" + _suffix\n'
		'            _candidates.append(_draw)\n'
		'            _candidates.append("_" + _draw)\n'
		'            _candidates.append(_draw + ":0")\n'
		'            _candidates.append("_" + _draw + ":0")\n'
		'    except:\n'
		'        pass\n'
		'    _sources = []\n'
		'    for _src_name in ("collidersIds", "colliders"):\n'
		'        try:\n'
		'            _src = globals().get(_src_name, {})\n'
		'        except:\n'
		'            _src = {}\n'
		'        if isinstance(_src, dict):\n'
		'            _sources.append(_src)\n'
		'    for _src in _sources:\n'
		'        for _cand in _candidates:\n'
		'            try:\n'
		'                _v = _src.get(_cand, None)\n'
		'                if _v is not None:\n'
		'                    return _v\n'
		'            except:\n'
		'                pass\n'
		'    return _collider\n'
		'class _GbcMutableSimProxy:\n'
		'    def __init__(self, _sim):\n'
		'        self._sim = _sim\n'
		'    def __getattr__(self, _name):\n'
		'        return getattr(self._sim, _name)\n'
		'if (sim is not None) and not isinstance(sim, _GbcMutableSimProxy):\n'
		'    try:\n'
		'        sim = _GbcMutableSimProxy(sim)\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "get_rigid_body_position") and not getattr(sim, "_js13k_gbc_get_rbpos_safe", False):\n'
		'    _js13k_gbc_orig_get_rigid_body_position = sim.get_rigid_body_position\n'
		'    def _js13k_gbc_get_rigid_body_position_safe(rigidBody):\n'
		'        try:\n'
		'            return _js13k_gbc_unbias_pos_for_get(_js13k_gbc_orig_get_rigid_body_position(rigidBody))\n'
		'        except:\n'
		'            return [0.0, 0.0]\n'
		'    try:\n'
		'        sim.get_rigid_body_position = _js13k_gbc_get_rigid_body_position_safe\n'
		'        sim._js13k_gbc_get_rbpos_safe = True\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "set_rigid_body_position") and not getattr(sim, "_js13k_gbc_set_rbpos_safe", False):\n'
		'    _js13k_gbc_orig_set_rigid_body_position = sim.set_rigid_body_position\n'
		'    def _js13k_gbc_set_rigid_body_position_safe(rigidBody, pos, wakeUp = True):\n'
		'        return _js13k_gbc_orig_set_rigid_body_position(rigidBody, _js13k_gbc_bias_pos_for_set(pos), wakeUp)\n'
		'    try:\n'
		'        sim.set_rigid_body_position = _js13k_gbc_set_rigid_body_position_safe\n'
		'        sim._js13k_gbc_set_rbpos_safe = True\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "get_collider_position") and not getattr(sim, "_js13k_gbc_get_colpos_safe", False):\n'
		'    _js13k_gbc_orig_get_collider_position = sim.get_collider_position\n'
		'    def _js13k_gbc_get_collider_position_safe(collider):\n'
		'        try:\n'
		'            _orig_collider = collider\n'
		'            collider = _js13k_gbc_resolve_collider_handle(collider)\n'
		'            _raw_pos = _js13k_gbc_orig_get_collider_position(collider)\n'
		'            if _raw_pos is None:\n'
		'                _fallback_name = ""\n'
		'                if isinstance(_orig_collider, str):\n'
		'                    _fallback_name = _orig_collider\n'
		'                else:\n'
		'                    try:\n'
		'                        _fallback_name = str(getattr(_orig_collider, "id"))\n'
		'                    except:\n'
		'                        try:\n'
		'                            _fallback_name = str(_orig_collider)\n'
		'                        except:\n'
		'                            _fallback_name = ""\n'
		'                _get_pos = globals().get("get_object_position", None)\n'
		'                if callable(_get_pos) and _fallback_name != "":\n'
		'                    try:\n'
		'                        _p = _get_pos(_fallback_name)\n'
		'                        if _p is not None:\n'
		'                            return _p\n'
		'                    except:\n'
		'                        pass\n'
		'                return [0.0, 0.0]\n'
		'            return _js13k_gbc_unbias_pos_for_get(_raw_pos)\n'
		'        except:\n'
		'            return [0.0, 0.0]\n'
		'    try:\n'
		'        sim.get_collider_position = _js13k_gbc_get_collider_position_safe\n'
		'        sim._js13k_gbc_get_colpos_safe = True\n'
		'    except:\n'
		'        pass\n'
		'if False and (sim is not None) and hasattr(sim, "set_collider_position") and not getattr(sim, "_js13k_gbc_set_colpos_safe", False):\n'
		'    _js13k_gbc_orig_set_collider_position = sim.set_collider_position\n'
		'    def _js13k_gbc_set_collider_position_safe(collider, pos, wakeUp = True):\n'
		'        collider = _js13k_gbc_resolve_collider_handle(collider)\n'
		'        return _js13k_gbc_orig_set_collider_position(collider, _js13k_gbc_bias_pos_for_set(pos), wakeUp)\n'
		'    try:\n'
		'        sim.set_collider_position = _js13k_gbc_set_collider_position_safe\n'
		'        sim._js13k_gbc_set_colpos_safe = True\n'
		'    except:\n'
		'        pass\n'
	)
	out_code = str(code or '')
	try:
		out_code = re.sub(r'\bsim\s*\.\s*cast_collider\s*\(', '_js13k_gbc_user_cast_collider(', out_code)
		out_code = re.sub(r'\bphysics\s*\.\s*cast_collider\s*\(', '_js13k_gbc_user_cast_collider(', out_code)
	except Exception:
		pass
	return prefix + out_code

def _normalize_gb_script_code (code : str, is_init : bool, script_type : str = '', owner_name : str = ''):
	out = code
	if callable(_py2gb_normalize_gb_script_code):
		out = _py2gb_normalize_gb_script_code(code, is_init, script_type, owner_name)
	if script_type == 'gbc-py':
		out = _inject_gbc_signed_position_wrappers(out)
		# Keep position/rotation helpers callable even if user/runtime locals
		# accidentally shadow helper names with non-callables.
		try:
			out = re.sub(
				r'(?<!\.)\b(?:gbc_get_object_position|get_object_position)\s*\(',
				'_js13k_call_get_object_position(',
				str(out),
			)
			out = re.sub(
				r'(?<!\.)\b(?:gbc_get_object_rotation|get_object_rotation)\s*\(',
				'_js13k_call_get_object_rotation(',
				str(out),
			)
			# Route bare print() through a protected runtime alias so object
			# attributes/locals named "print" cannot break script logging.
			out = re.sub(
				r'(?<!\.)\bprint\s*\(',
				'_js13k_call_print(',
				str(out),
			)
			out = re.sub(
				r'(?<!\.)\b_js13k_print\s*\(',
				'_js13k_call_print(',
				str(out),
			)
		except Exception:
			pass
		try:
			out = _protect_runtime_binding_assignments(
				str(out),
				{
					'print',
					'_js13k_print',
					'get_object_position',
					'get_object_rotation',
					'gbc_get_object_position',
					'gbc_get_object_rotation',
					'_js13k_internal_get_object_position',
					'_js13k_internal_get_object_rotation',
					'_js13k_call_print',
					'_js13k_call_get_object_position',
					'_js13k_call_get_object_rotation',
				},
			)
		except Exception:
			pass
	return out

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
				raw_script_txt = scriptTxt
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init), _type, '__world__')
				script_entries.append({
					'code' : scriptTxt,
					'raw_code' : raw_script_txt,
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
				raw_script_txt = scriptTxt
				scriptTxt = _normalize_gb_script_code(scriptTxt, bool(is_init), _type, ob.name)
				script_entries.append({
					'code' : scriptTxt,
					'raw_code' : raw_script_txt,
					'is_init' : is_init,
					'script_obj' : script,
					'owner_name' : ob.name,
					'symbol_hint' : ob.name + '_' + getattr(script, 'name', 'script'),
				})
	exportType = prev_export
	if _py2gb_export_gba_py_assembly:
		runtime = _run_py2gb_export_with_resolved_logs(_py2gb_export_gba_py_assembly, script_entries, gba_out_path, strict_print_exprs = False)
		return _augment_runtime_with_dynamic_circles(runtime, script_entries)
	runtime = {'script_count' : 0, 'init_quit' : False, 'update_quit' : False, 'init_draw_circles' : [], 'update_draw_circles' : [], 'init_display_ops' : [], 'update_display_ops' : [], 'surface_ops' : [], 'builtin_only_quit' : True}
	return _augment_runtime_with_dynamic_circles(runtime, script_entries)

def ExportGbcPyAssembly (world, gbc_out_path : str):
	'''Collect gbc-py scripts from world and exported objects; write translated assembly next to the .gbc.'''
	global exportType
	_append_gbc_trace_lines([
		'[gbc-trace] ExportGbcPyAssembly:start out=' + str(gbc_out_path),
		'[gbc-trace] ExportGbcPyAssembly:blend=' + str(getattr(bpy.data, 'filepath', '')),
	])
	prev_export = exportType
	exportType = 'gbc'
	script_entries = []
	def _is_valid_gbc_attribute_name (_name):
		return isinstance(_name, str) and _name != '' and _name.isidentifier() and (not keyword.iskeyword(_name))
	def _collect_validated_gbc_script_attributes (_ob):
		attr_map = GetAttributes(_ob)
		if not isinstance(attr_map, dict) or attr_map == {}:
			return {}
		invalid_names = []
		for _name in list(attr_map.keys()):
			if not _is_valid_gbc_attribute_name(_name):
				invalid_names.append(str(_name))
		if invalid_names:
			raise RuntimeError(
				'GBC export: object "' + str(_ob.name) + '" has included attributes that are not valid variable names: '
				+ ', '.join(sorted(set(invalid_names)))
			)
		return dict(attr_map)
	def _validate_gbc_object_attributes_for_export (_ob):
		_collect_validated_gbc_script_attributes(_ob)
	def _build_gbc_local_this_attributes_prefix (_owner_name, _owner_attributes):
		lines = []
		reserved_attr_locals = {
			'this', 'sim', 'physics', 'objects', 'obs', 'rigidBodies', 'rbs', 'colliders', 'cols',
			'get_rigidbody', 'get_collider', 'get_object_position', 'get_object_rotation',
			'gbc_get_rigidbody', 'gbc_get_collider', 'gbc_get_object_position', 'gbc_get_object_rotation',
			'_js13k_internal_get_object_position', '_js13k_internal_get_object_rotation',
			'_js13k_pos_resolver', '_js13k_rot_resolver',
			'_js13k_print',
			'_js13k_call_print',
			'_js13k_call_get_object_position',
			'_js13k_call_get_object_rotation',
			'__js13k_helpers__',
			'print',
		}
		_owner_key = str(_owner_name or '')
		if _owner_key != '' and _owner_key != '__world__':
			lines.extend([
				'owner_key = %r' %(_owner_key),
				'try:',
				'    owner_key = str(this.id)',
				'except:',
				'    try:',
				'        owner_key = str(this.name)',
				'    except:',
				'        owner_key = %r' %(_owner_key),
				'owner_keys = [owner_key]',
				'try:',
				'    if isinstance(owner_key, str) and owner_key != "":',
				'        owner_keys.append("_" + owner_key)',
				'        owner_keys.append(owner_key + ":0")',
				'        owner_keys.append("_" + owner_key + ":0")',
				'        if owner_key.startswith("__gbc_spawn_"):',
				'            spawn_suffix = owner_key[len("__gbc_spawn_"): ]',
				'            phys_key = "__gbc_spawnphys_" + spawn_suffix',
				'            owner_keys.append(phys_key)',
				'            owner_keys.append("_" + phys_key)',
				'            owner_keys.append(phys_key + ":0")',
				'            owner_keys.append("_" + phys_key + ":0")',
				'            source_key = spawn_suffix',
				'            split_idx = source_key.find("_")',
				'            if split_idx > 0 and source_key[:split_idx].isdigit() and source_key[split_idx + 1:] != "":',
				'                source_key = source_key[split_idx + 1:]',
				'            owner_keys.append(source_key)',
				'            owner_keys.append("_" + source_key)',
				'            owner_keys.append(source_key + ":0")',
				'            owner_keys.append("_" + source_key + ":0")',
				'        elif owner_key.startswith("__gbc_spawnphys_"):',
				'            spawn_suffix = owner_key[len("__gbc_spawnphys_"): ]',
				'            draw_key = "__gbc_spawn_" + spawn_suffix',
				'            owner_keys.append(draw_key)',
				'            owner_keys.append("_" + draw_key)',
				'            owner_keys.append(draw_key + ":0")',
				'            owner_keys.append("_" + draw_key + ":0")',
				'            source_key = spawn_suffix',
				'            split_idx = source_key.find("_")',
				'            if split_idx > 0 and source_key[:split_idx].isdigit() and source_key[split_idx + 1:] != "":',
				'                source_key = source_key[split_idx + 1:]',
				'            owner_keys.append(source_key)',
				'            owner_keys.append("_" + source_key)',
				'            owner_keys.append(source_key + ":0")',
				'            owner_keys.append("_" + source_key + ":0")',
				'except:',
				'    owner_keys = [owner_key]',
				'try:',
				'    _rb_ids = globals().get("rigidBodiesIds", {})',
				'except:',
				'    _rb_ids = {}',
				'try:',
				'    _col_ids = globals().get("collidersIds", {})',
				'except:',
				'    _col_ids = {}',
				'rb = None',
				'for _key in owner_keys:',
				'    try:',
				'        rb = rb if rb is not None else get_rigidbody(_key)',
				'    except:',
				'        rb = rb',
				'    if rb is not None:',
				'        break',
				'    try:',
				'        rb = rb if rb is not None else rigidBodies[_key]',
				'    except:',
				'        rb = rb',
				'    if rb is not None:',
				'        break',
				'    try:',
				'        rb = rb if rb is not None else _rb_ids[_key]',
				'    except:',
				'        rb = rb',
				'    if rb is not None:',
				'        break',
				'col = None',
				'col_key_hit = None',
				'for _key in owner_keys:',
				'    try:',
				'        col = col if col is not None else get_collider(_key)',
				'    except:',
				'        col = col',
				'    if col is not None:',
				'        col_key_hit = _key',
				'        break',
				'    try:',
				'        col = col if col is not None else colliders[_key]',
				'    except:',
				'        col = col',
				'    if col is not None:',
				'        col_key_hit = _key',
				'        break',
				'    try:',
				'        col = col if col is not None else _col_ids[_key]',
				'    except:',
				'        col = col',
				'    if col is not None:',
				'        col_key_hit = _key',
				'        break',
				'if col is None:',
				'    _resolver = globals().get("_resolve_script_lookup_from_sources", None)',
				'    if callable(_resolver):',
				'        for _key in owner_keys:',
				'            try:',
				'                col = _resolver(_key, _col_ids, colliders)',
				'            except:',
				'                col = col',
				'            if col is not None:',
				'                col_key_hit = "resolved:" + str(_key)',
				'                break',
				# Keep local `col` stable for gbc-py lowered scripts (this.col -> col)
				# and make phase1 mirror lookups deterministic by owner id.
				'if isinstance(owner_key, str) and owner_key != "":',
				'    col = owner_key',
				'    if col_key_hit is None:',
				'        col_key_hit = "owner_key"',
				'    else:',
				'        col_key_hit = "owner_key+" + str(col_key_hit)',
				'try:',
				'    print("[gbc-col-debug]", "owner_key=", owner_key, "hit=", col_key_hit, "candidate_count=", len(owner_keys), "col_is_none=", (col is None))',
				'except:',
				'    pass',
				'try:',
				'    if col is None:',
				'        _col_ids_keys = []',
				'        try:',
				'            _col_ids_keys = list(getattr(_col_ids, "keys", lambda : [])())',
				'        except:',
				'            _col_ids_keys = []',
				'        print("[gbc-col-keys]", "owner_key=", owner_key, "keys=", _col_ids_keys[:10], "key_count=", len(_col_ids_keys))',
				'except:',
				'    pass',
				'try:',
				'    this.rb = rb',
				'except:',
				'    pass',
				'try:',
				'    this.col = col',
				'except:',
				'    pass',
			])
		if not isinstance(_owner_attributes, dict) or _owner_attributes == {}:
			return '\n'.join(lines).strip()
		for _name in sorted(_owner_attributes.keys()):
			if str(_name) in reserved_attr_locals:
				continue
			_default_expr = repr(_owner_attributes[_name])
			lines.extend([
				str(_name) + ' = ' + _default_expr,
				'try:',
				'    ' + str(_name) + ' = getattr(this, ' + repr(str(_name)) + ')',
				'except:',
				'    ' + str(_name) + ' = ' + str(_name),
			])
		return '\n'.join(lines).strip()
	def _rewrite_gbc_this_attribute_accesses_to_locals (_code, _owner_attributes):
		if not isinstance(_code, str) or _code.strip() == '':
			return str(_code or '')
		if not isinstance(_owner_attributes, dict) or _owner_attributes == {}:
			return str(_code)
		_attr_names = {str(_k) for _k in _owner_attributes.keys() if isinstance(_k, str) and _k != ''}
		if _attr_names == set():
			return str(_code)
		try:
			_tree = ast.parse(_code)
		except Exception:
			return str(_code)
		class _RewriteThisAttributeRefs(ast.NodeTransformer):
			def visit_Attribute (self, node):
				node = self.generic_visit(node)
				if (
					isinstance(node, ast.Attribute)
					and isinstance(node.value, ast.Name)
					and node.value.id == 'this'
					and isinstance(node.attr, str)
					and node.attr in _attr_names
				and isinstance(node.ctx, ast.Load)
				):
					return ast.copy_location(ast.Name(id = node.attr, ctx = node.ctx), node)
				return node
		try:
			_tree = _RewriteThisAttributeRefs().visit(_tree)
			_tree = ast.fix_missing_locations(_tree)
			return ast.unparse(_tree)
		except Exception:
			return str(_code)
	def _protect_runtime_binding_assignments (_code, _protected_names):
		if not isinstance(_code, str) or _code.strip() == '':
			return str(_code or '')
		protected = {str(_n) for _n in list(_protected_names or []) if isinstance(_n, str) and str(_n) != ''}
		if protected == set():
			return str(_code)
		def _mapped_name (_name):
			return '_js13k_user_shadow_' + str(_name)
		try:
			_tree = ast.parse(_code)
		except Exception:
			return str(_code)
		class _ProtectBindings(ast.NodeTransformer):
			def visit_Name (self, node):
				node = self.generic_visit(node)
				if isinstance(node, ast.Name) and isinstance(node.id, str) and node.id in protected and isinstance(node.ctx, (ast.Store, ast.Del)):
					return ast.copy_location(ast.Name(id = _mapped_name(node.id), ctx = node.ctx), node)
				return node
			def visit_FunctionDef (self, node):
				node = self.generic_visit(node)
				if isinstance(node.name, str) and node.name in protected:
					node.name = _mapped_name(node.name)
				return node
			def visit_AsyncFunctionDef (self, node):
				node = self.generic_visit(node)
				if isinstance(node.name, str) and node.name in protected:
					node.name = _mapped_name(node.name)
				return node
			def visit_ClassDef (self, node):
				node = self.generic_visit(node)
				if isinstance(node.name, str) and node.name in protected:
					node.name = _mapped_name(node.name)
				return node
			def visit_ExceptHandler (self, node):
				node = self.generic_visit(node)
				if isinstance(getattr(node, 'name', None), str) and node.name in protected:
					node.name = _mapped_name(node.name)
				return node
		try:
			_tree = _ProtectBindings().visit(_tree)
			_tree = ast.fix_missing_locations(_tree)
			return ast.unparse(_tree)
		except Exception:
			return str(_code)
	def _build_gbc_obs_prefix (_obs_data):
		_obs_map = dict(_obs_data) if isinstance(_obs_data, dict) else {}
		return (
			'_js13k_obs_export = ' + repr(_obs_map) + '\n'
			'_obs_existing = globals().get("obs", None)\n'
			'if isinstance(_obs_existing, dict):\n'
			'    obs = _obs_existing\n'
			'else:\n'
			'    obs = {}\n'
			'obs.update(_js13k_obs_export)\n'
			'_js13k_rigid_bodies = globals().get("rigidBodies", globals().get("rigidBodiesIds", {}))\n'
			'_js13k_colliders = globals().get("colliders", globals().get("collidersIds", {}))\n'
			'_js13k_rigid_bodies_ids = globals().get("rigidBodiesIds", _js13k_rigid_bodies)\n'
			'_js13k_colliders_ids = globals().get("collidersIds", _js13k_colliders)\n'
			'def _js13k_lookup_runtime_handle(_src, _name):\n'
			'    if not isinstance(_src, dict):\n'
			'        return None\n'
			'    if _name in _src:\n'
			'        _v = _src[_name]\n'
			'        if _v is not None:\n'
			'            return _v\n'
			'    if isinstance(_name, str):\n'
			'        if _name.startswith("_"):\n'
			'            _v = _src.get(_name[1:])\n'
			'            if _v is not None:\n'
			'                return _v\n'
			'        else:\n'
			'            _v = _src.get("_" + _name)\n'
			'            if _v is not None:\n'
			'                return _v\n'
			'        _name_norm = "".join([_c for _c in _name.lstrip("_").lower() if (("a" <= _c <= "z") or ("0" <= _c <= "9") or _c == "_")])\n'
			'        for _k, _v in list(_src.items()):\n'
			'            if not isinstance(_k, str):\n'
			'                continue\n'
			'            _k_norm = "".join([_c for _c in _k.lstrip("_").lower() if (("a" <= _c <= "z") or ("0" <= _c <= "9") or _c == "_")])\n'
			'            if _k_norm == _name_norm or _k_norm.endswith("_" + _name_norm) or _k_norm.endswith(_name_norm):\n'
			'                return _v\n'
			'    return None\n'
			'for _js13k_ob_name, _js13k_ob_data in obs.items():\n'
			'    if not isinstance(_js13k_ob_data, dict):\n'
			'        continue\n'
			'    _js13k_ob_data["rb"] = _js13k_lookup_runtime_handle(_js13k_rigid_bodies, _js13k_ob_name)\n'
			'    if _js13k_ob_data.get("rb", None) is None:\n'
			'        _js13k_ob_data["rb"] = _js13k_lookup_runtime_handle(_js13k_rigid_bodies_ids, _js13k_ob_name)\n'
			'    _js13k_ob_data["col"] = _js13k_lookup_runtime_handle(_js13k_colliders, _js13k_ob_name)\n'
			'    if _js13k_ob_data.get("col", None) is None:\n'
			'        _js13k_ob_data["col"] = _js13k_lookup_runtime_handle(_js13k_colliders_ids, _js13k_ob_name)\n'
			'objects = obs\n'
			'del _obs_existing\n'
			'del _js13k_rigid_bodies\n'
			'del _js13k_colliders\n'
			'del _js13k_rigid_bodies_ids\n'
			'del _js13k_colliders_ids\n'
			'del _js13k_lookup_runtime_handle\n'
			'del _js13k_obs_export\n'
		)
	in_prefab_coll = set()
	in_non_prefab_coll = set()
	for coll in bpy.data.collections:
		export_prefab = bool(getattr(coll, 'exportPrefab', False))
		for ob in coll.all_objects:
			if export_prefab:
				in_prefab_coll.add(ob)
			else:
				in_non_prefab_coll.add(ob)
	# Objects that exist only inside prefab template collections should not run
	# local gbc-py scripts unless actually spawned at runtime.
	template_only_obs = set(in_prefab_coll - in_non_prefab_coll)
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		_validate_gbc_object_attributes_for_export(ob)
	spawn_template_obs = set()
	template_spawn_instance_tags_by_ob = {}
	gbc_spawn_owner_pos_overrides = {}
	def _append_script_entry (_owner_name, _script_txt, _is_init, _is_global, _script, _symbol_hint, _owner_attributes = None):
		raw_script_txt = _script_txt
		norm_script_txt = _normalize_gb_script_code(_script_txt, bool(_is_init), 'gbc-py', _owner_name)
		source_line_offset = 0
		local_attr_prefix = ''
		rewrite_attributes = dict(_owner_attributes) if isinstance(_owner_attributes, dict) else {}
		if _owner_name != '__world__':
			rewrite_attributes.setdefault('rb', None)
			rewrite_attributes.setdefault('col', None)
			local_attr_prefix = _build_gbc_local_this_attributes_prefix(_owner_name, _owner_attributes)
			# Keep this.rb/this.col routed through the local rb/col bindings created
			# by _build_gbc_local_this_attributes_prefix so dictionary fallback
			# (rigidBodies/colliders) remains available when helper funcs are absent.
			# Do a regex pass first so parse failures don't skip the rewrite.
			try:
				norm_script_txt = re.sub(r'\bthis\s*\.\s*rb\b', 'rb', str(norm_script_txt))
				norm_script_txt = re.sub(r'\bthis\s*\.\s*col\b', 'col', str(norm_script_txt))
			except Exception:
				pass
			norm_script_txt = _rewrite_gbc_this_attribute_accesses_to_locals(norm_script_txt, rewrite_attributes)
		if local_attr_prefix != '':
			source_line_offset = len(local_attr_prefix.splitlines())
			if norm_script_txt.strip() == '':
				norm_script_txt = local_attr_prefix
			else:
				norm_script_txt = local_attr_prefix + '\n' + norm_script_txt
		script_entries.append({
			'code' : norm_script_txt,
			'raw_code' : raw_script_txt,
			'source_code' : raw_script_txt,
			'source_line_offset' : source_line_offset,
			'owner_attributes' : dict(_owner_attributes) if isinstance(_owner_attributes, dict) else {},
			'is_init' : _is_init,
			'is_global' : _is_global,
			'script_obj' : _script,
			'owner_name' : _owner_name,
			'symbol_hint' : _symbol_hint,
		})
	try:
		spawn_calls = []
		for call in _collect_gbc_spawn_prefab_requests():
			prefab_name = str(call.get('prefab_name', '') or '')
			if prefab_name == '':
				continue
			coll = bpy.data.collections.get(prefab_name)
			if not coll or not getattr(coll, 'exportPrefab', False):
				continue
			spawn_calls.append({
				'prefab_name' : prefab_name,
				'pos' : call.get('pos', None),
				'rot' : float(call.get('rot', 0.0) or 0.0),
			})
			for ob in coll.all_objects:
				spawn_template_obs.add(ob)
		# Scene collection instances implicitly spawn prefab children too.
		for inst_ob in list(getattr(bpy.data, 'objects', []) or []):
			if not getattr(inst_ob, 'exportOb', False) or inst_ob.hide_get():
				continue
			if getattr(inst_ob, 'instance_type', None) != 'COLLECTION':
				continue
			coll = getattr(inst_ob, 'instance_collection', None)
			if not coll or not getattr(coll, 'exportPrefab', False):
				continue
			try:
				wm_pos = inst_ob.matrix_world.to_translation()
				wm_rot = inst_ob.matrix_world.to_euler('XYZ')
				inst_x = float(wm_pos.x)
				inst_y = float(wm_pos.y)
				inst_rot = float(-math.degrees(wm_rot.z))
			except Exception:
				inst_x = float(getattr(inst_ob.location, 'x', 0.0))
				inst_y = float(getattr(inst_ob.location, 'y', 0.0))
				inst_rot = float(-math.degrees(getattr(inst_ob.rotation_euler, 'z', 0.0)))
			spawn_calls.append({
				'prefab_name' : str(coll.name),
				'pos' : [inst_x, inst_y],
				'rot' : float(inst_rot),
				# Keep scene instance fan-out stable even when two empties share
				# the same transform (for example stacked collection instances).
				'scene_instance_name' : str(getattr(inst_ob, 'name', '') or ''),
			})
			for ob in coll.all_objects:
				spawn_template_obs.add(ob)
		# Keep instance fan-out stable with BuildGbc's fallback dedupe behavior.
		deduped_spawn_calls = []
		seen_spawn_keys = set()
		for call in spawn_calls:
			prefab_name = str(call.get('prefab_name', '') or '')
			pos_val = call.get('pos', None)
			rot_val = float(call.get('rot', 0.0) or 0.0)
			scene_instance_name = str(call.get('scene_instance_name', '') or '')
			if pos_val is None:
				deduped_spawn_calls.append(call)
				continue
			x = float(pos_val[0]) if len(pos_val) > 0 else 0.0
			y = float(pos_val[1]) if len(pos_val) > 1 else 0.0
			key = (
				prefab_name,
				round(x, 4),
				round(y, 4),
				round(rot_val, 4),
				scene_instance_name,
			)
			if key in seen_spawn_keys:
				continue
			seen_spawn_keys.add(key)
			deduped_spawn_calls.append(call)
		for call_idx, call in enumerate(deduped_spawn_calls):
			prefab_name = str(call.get('prefab_name', '') or '')
			if prefab_name == '':
				continue
			coll = bpy.data.collections.get(prefab_name)
			if not coll or not getattr(coll, 'exportPrefab', False):
				continue
			call_pos = call.get('pos', None)
			call_pos_xy = None
			if isinstance(call_pos, (list, tuple)):
				try:
					call_pos_xy = [
						float(call_pos[0]) if len(call_pos) > 0 else 0.0,
						float(call_pos[1]) if len(call_pos) > 1 else 0.0,
					]
				except Exception:
					call_pos_xy = None
			for ob in coll.all_objects:
				tags = template_spawn_instance_tags_by_ob.setdefault(ob, [])
				tags.append(call_idx)
				if call_pos_xy is not None:
					spawn_owner = '__gbc_spawn_%i_%s' %(int(call_idx), ob.name)
					gbc_spawn_owner_pos_overrides[str(spawn_owner)] = list(call_pos_xy)
	except Exception:
		spawn_template_obs = set()
		template_spawn_instance_tags_by_ob = {}
		gbc_spawn_owner_pos_overrides = {}
	template_local_scripts_skipped = 0
	template_local_scripts_spawn_included = 0
	if world:
		for scriptInfo in GetScripts(world):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			is_global = bool(scriptInfo[4]) if len(scriptInfo) > 4 else False
			if _type == 'gbc-py':
				_append_script_entry(
					'__world__',
					scriptTxt,
					is_init,
					is_global,
					script,
					'world_' + getattr(script, 'name', 'script'),
				)
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		gbc_script_attributes = None
		if ob in template_only_obs and ob not in spawn_template_obs:
			for scriptInfo in GetScripts(ob):
				_type = scriptInfo[2]
				if _type == 'gbc-py':
					template_local_scripts_skipped += 1
			continue
		elif ob in template_only_obs and ob in spawn_template_obs:
			for scriptInfo in GetScripts(ob):
				_type = scriptInfo[2]
				if _type == 'gbc-py':
					spawn_tags = list(template_spawn_instance_tags_by_ob.get(ob, []))
					if not spawn_tags:
						spawn_tags = [None]
					template_local_scripts_spawn_included += len(spawn_tags)
		for scriptInfo in GetScripts(ob):
			scriptTxt = scriptInfo[0]
			is_init = scriptInfo[1]
			_type = scriptInfo[2]
			script = scriptInfo[3]
			is_global = bool(scriptInfo[4]) if len(scriptInfo) > 4 else False
			if _type == 'gbc-py':
				if gbc_script_attributes is None:
					gbc_script_attributes = _collect_validated_gbc_script_attributes(ob)
				if ob in template_only_obs and ob in spawn_template_obs:
					spawn_tags = list(template_spawn_instance_tags_by_ob.get(ob, []))
					if not spawn_tags:
						spawn_tags = [None]
					for tag in spawn_tags:
						if tag is None:
							owner_name = ob.name
							symbol_hint = ob.name + '_' + getattr(script, 'name', 'script')
						else:
							owner_name = '__gbc_spawn_%i_%s' %(int(tag), ob.name)
							symbol_hint = owner_name + '_' + getattr(script, 'name', 'script')
						_append_script_entry(
							owner_name,
							scriptTxt,
							is_init,
							is_global,
							script,
							symbol_hint,
							gbc_script_attributes,
						)
				else:
					_append_script_entry(
						ob.name,
						scriptTxt,
						is_init,
						is_global,
						script,
						ob.name + '_' + getattr(script, 'name', 'script'),
						gbc_script_attributes,
					)
	def _entry_has_spawn_prefab_call (_entry):
		raw = str(_entry.get('raw_code', _entry.get('code', '')) or '')
		try:
			tree = ast.parse(raw)
			for node in ast.walk(tree):
				if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'spawn_prefab':
					return True
		except Exception:
			return bool(re.search(r'\bspawn_prefab\s*\(', raw))
		return False
	spawn_calls = []
	for entry in script_entries:
		raw = str(entry.get('raw_code', entry.get('code', '')) or '')
		owner = str(entry.get('owner_name', '__world__'))
		hits = []
		try:
			tree = ast.parse(raw)
			for node in ast.walk(tree):
				if not isinstance(node, ast.Call):
					continue
				if isinstance(node.func, ast.Name) and node.func.id == 'spawn_prefab':
					hits.append(int(getattr(node, 'lineno', -1)))
		except Exception:
			# Fallback to loose text hit when code is syntactically invalid.
			if re.search(r'\bspawn_prefab\s*\(', raw):
				hits.append(-1)
		if hits:
			if any(h > 0 for h in hits):
				lines = ','.join([str(h) for h in hits if h > 0])
				spawn_calls.append(owner + '@L' + lines)
			else:
				spawn_calls.append(owner + '@<text-hit>')
	_append_gbc_trace_lines([
		'[gbc-trace] ExportGbcPyAssembly:scripts=' + str(len(script_entries)),
		'[gbc-trace] ExportGbcPyAssembly:template_local_scripts_skipped=' + str(template_local_scripts_skipped),
		'[gbc-trace] ExportGbcPyAssembly:template_local_scripts_spawn_included=' + str(template_local_scripts_spawn_included),
		'[gbc-trace] ExportGbcPyAssembly:spawn_prefab_callers=' + (', '.join(spawn_calls) if spawn_calls else '<none>'),
	])
	gbc_obs_data = {}
	def _add_gbc_obs_owner (_owner_name, _ob):
		if not isinstance(_owner_name, str) or _owner_name == '' or _owner_name == '__world__':
			return
		try:
			attr_map = GetAttributes(_ob)
		except Exception:
			attr_map = {}
		if not isinstance(attr_map, dict):
			attr_map = {}
		entry = {
			'id' : str(_owner_name),
			'surface' : str(_owner_name),
			'rb' : None,
			'col' : None,
		}
		override_pos = None
		try:
			override_pos = gbc_spawn_owner_pos_overrides.get(str(_owner_name), None)
		except Exception:
			override_pos = None
		if isinstance(override_pos, (list, tuple)) and len(override_pos) >= 2:
			try:
				_pos = [float(override_pos[0]), float(override_pos[1])]
				entry['pos'] = _pos
				entry['position'] = list(_pos)
			except Exception:
				pass
		if 'pos' in entry and 'position' in entry:
			for _attr_name, _attr_value in attr_map.items():
				entry[str(_attr_name)] = _attr_value
			gbc_obs_data[str(_owner_name)] = entry
			return
		try:
			_pos = [float(_ob.location.x), float(_ob.location.y)]
			if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
				entry['pos'] = _pos
				entry['position'] = list(_pos)
		except Exception:
			try:
				_pose, _rot = _gba_get_object_pose(_ob)
				if isinstance(_pose, (list, tuple)) and len(_pose) >= 2:
					_pos = [float(_pose[0]), float(_pose[1])]
					entry['pos'] = _pos
					entry['position'] = list(_pos)
			except Exception:
				pass
		for _attr_name, _attr_value in attr_map.items():
			entry[str(_attr_name)] = _attr_value
		gbc_obs_data[str(_owner_name)] = entry
	for ob in bpy.data.objects:
		if not ob.exportOb or ob.hide_get():
			continue
		if ob in template_only_obs and ob not in spawn_template_obs:
			continue
		_add_gbc_obs_owner(ob.name, ob)
		if ob in template_only_obs and ob in spawn_template_obs:
			for tag in list(template_spawn_instance_tags_by_ob.get(ob, [])):
				_add_gbc_obs_owner('__gbc_spawn_%i_%s' %(int(tag), ob.name), ob)
	global_members_prefix = _build_gbc_global_members_prefix(script_entries)
	obs_prefix = _build_gbc_obs_prefix(gbc_obs_data)
	shared_prefix_parts = []
	if obs_prefix.strip() != '':
		shared_prefix_parts.append(obs_prefix.strip())
	if global_members_prefix.strip() != '':
		shared_prefix_parts.append(global_members_prefix.strip())
	shared_members_prefix = ''
	if shared_prefix_parts:
		shared_members_prefix = '\n\n'.join(shared_prefix_parts).strip() + '\n'
	# Scripts marked "global" are definition providers for the shared prefix.
	# They normally should not execute as standalone runtime scripts each frame.
	# Exception: keep global scripts that explicitly call spawn_prefab(...), so
	# authors can drive prefab spawns from shared/global gbc-py scripts.
	runtime_script_entries = [
		entry for entry in script_entries
		if (not bool(entry.get('is_global'))) or _entry_has_spawn_prefab_call(entry)
	]
	_append_gbc_trace_lines([
		'[gbc-trace] ExportGbcPyAssembly:runtime_script_entries=' + str(len(runtime_script_entries)),
		'[gbc-trace] ExportGbcPyAssembly:py2gb_backend=' + ('available' if bool(_py2gb_export_gba_py_assembly) else 'missing'),
	])
	if shared_members_prefix != '':
		prefix_line_count = len(str(shared_members_prefix).splitlines())
		for entry in runtime_script_entries:
			code_txt = str(entry.get('code', '') or '')
			raw_code_txt = str(entry.get('raw_code', code_txt) or '')
			entry['source_line_offset'] = int(entry.get('source_line_offset', 0) or 0) + int(prefix_line_count)
			entry['code'] = shared_members_prefix + '\n' + code_txt if code_txt.strip() != '' else shared_members_prefix
			entry['raw_code'] = shared_members_prefix + '\n' + raw_code_txt if raw_code_txt.strip() != '' else shared_members_prefix
	# Final safety rewrite: make local scripts use rb/col locals instead of
	# this.rb/this.col so downstream gbc-py lowering sees canonical handles.
	for entry in runtime_script_entries:
		try:
			if str(entry.get('owner_name', '__world__')) == '__world__':
				continue
			entry['code'] = re.sub(r'\bthis\s*\.\s*rb\b', 'rb', str(entry.get('code', '') or ''))
			entry['code'] = re.sub(r'\bthis\s*\.\s*col\b', 'col', str(entry.get('code', '') or ''))
			# Keep analysis/debug source text untouched so print-expression extraction
			# can still resolve `this.rb/this.col` against runtime mirror `this`.
			entry['raw_code'] = str(entry.get('raw_code', '') or '')
			entry['source_code'] = str(entry.get('source_code', entry.get('raw_code', entry.get('code', ''))) or '')
		except Exception:
			pass
	# Dump final runtime script text (post-prefix/rewrite) for debugging.
	try:
		for _idx, _entry in enumerate(runtime_script_entries):
			_owner = str(_entry.get('owner_name', '__world__') or '__world__')
			_scope = str(_entry.get('symbol_hint', '') or '')
			_is_init = bool(_entry.get('is_init'))
			_is_global = bool(_entry.get('is_global'))
			_code = str(_entry.get('code', '') or '')
			_raw_code = str(_entry.get('raw_code', '') or '')
			_source_code = str(_entry.get('source_code', '') or '')
			_code_this_rb = len(re.findall(r'\bthis\s*\.\s*rb\b', _code))
			_code_this_col = len(re.findall(r'\bthis\s*\.\s*col\b', _code))
			_raw_this_rb = len(re.findall(r'\bthis\s*\.\s*rb\b', _raw_code))
			_raw_this_col = len(re.findall(r'\bthis\s*\.\s*col\b', _raw_code))
			_source_this_rb = len(re.findall(r'\bthis\s*\.\s*rb\b', _source_code))
			_source_this_col = len(re.findall(r'\bthis\s*\.\s*col\b', _source_code))
			_lines = str(_code).splitlines()
			_num_lines = len(_lines)
			_dump_lines = _lines[:200]
			numbered = []
			for _ln, _src_line in enumerate(_dump_lines, start = 1):
				numbered.append(f'{_ln:03d}: {_src_line}')
			if _num_lines > len(_dump_lines):
				numbered.append(f'... truncated {_num_lines - len(_dump_lines)} more lines ...')
			_header = (
				'[gbc-trace] RuntimeScriptEntry'
				+ f':index={_idx}'
				+ f',owner={_owner}'
				+ f',scope={_scope}'
				+ f',is_init={int(_is_init)}'
				+ f',is_global={int(_is_global)}'
				+ f',lines={_num_lines}'
				+ f',code_this_rb={_code_this_rb}'
				+ f',code_this_col={_code_this_col}'
				+ f',raw_this_rb={_raw_this_rb}'
				+ f',raw_this_col={_raw_this_col}'
				+ f',source_this_rb={_source_this_rb}'
				+ f',source_this_col={_source_this_col}'
			)
			_append_gbc_trace_lines([
				_header,
			] + [('[gbc-trace]   ' + row) for row in numbered])
	except Exception:
		pass
	exportType = prev_export
	if _py2gb_export_gba_py_assembly:
		runtime = _run_py2gb_export_with_resolved_logs(_py2gb_export_gba_py_assembly, runtime_script_entries, gbc_out_path, strict_print_exprs = True)
		runtime = _augment_runtime_with_dynamic_circles(runtime, runtime_script_entries)
		return runtime
	runtime = {'script_count' : 0, 'init_quit' : False, 'update_quit' : False, 'init_draw_circles' : [], 'update_draw_circles' : [], 'init_display_ops' : [], 'update_display_ops' : [], 'surface_ops' : [], 'builtin_only_quit' : True}
	runtime = _augment_runtime_with_dynamic_circles(runtime, runtime_script_entries)
	_append_gbc_trace_lines([
		'[gbc-trace] ExportGbcPyAssembly:end runtime_script_count=' + str(runtime.get('script_count', 0) if isinstance(runtime, dict) else 0),
	])
	return runtime

def GetBlenderData ():
	global ui, vars, clrs, datas, joints, pivots, prefabs, globals, initCode, svgsDatas, colliders, renderCode, pathsDatas, updateCode, attributes, uiMethods, exportedObs, rigidBodies, charControllers, particleSystems, templateScripts, prefabTemplateDatas, prefabPathsDatas, templateOnlyObs, collectionInstanceCopyCounts, exportTraceEvents
	_write_export_trace_probe('GetBlenderData:start')
	vars = []
	attributes = {}
	pivots = {}
	exportedObs = []
	exportTraceEvents = []
	datas = _TrackedExportList('datas')
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
	prefabTemplateDatas = _TrackedExportList('prefabTemplateDatas')
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
				elif _type == 'gbc-py':
					scriptTxt = _normalize_gb_script_code(scriptTxt, bool(isInit), _type, ob.name)
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
				elif _type == 'gbc-py':
					scriptTxt = _normalize_gb_script_code(scriptTxt, bool(isInit), _type, '__world__')
				if isInit:
					if script not in initCode:
						initCode.append(scriptTxt)
				else:
					if script not in updateCode:
						updateCode.append(scriptTxt)
	_write_export_trace_log()
	_write_export_trace_probe('GetBlenderData:end')
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
_gbc_spawn_owner_pos_overrides = {}

class _ThisObject:
	def __init__ (self, name):
		self.name = name
		# Keep Python mirror `this` compatible with DOM `this.id` in HTML runtime.
		self.id = name
	def get_position (self):
		return get_object_position(self.name)
	def get_rotation (self):
		return get_object_rotation(self.name)

mousePos = pygame.math.Vector2()
mousePosWorld = pygame.math.Vector2()
prevMousePos = pygame.math.Vector2()
prevMousePosWorld = pygame.math.Vector2()
off = pygame.math.Vector2()
_cameraPos = pygame.math.Vector2()

def set_camera_position (x, y):
	global off, _cameraPos
	try:
		_x = int(round(float(x)))
	except Exception:
		_x = int(round(float(_cameraPos.x)))
	try:
		_y = int(round(float(y)))
	except Exception:
		_y = int(round(float(_cameraPos.y)))
	_x = int(_x) & 0xFFFF
	_y = int(_y) & 0xFFFF
	_cameraPos.x = float(_x)
	_cameraPos.y = float(_y)
	off.x = float(_cameraPos.x)
	off.y = float(_cameraPos.y)
	return [_cameraPos.x, _cameraPos.y]

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

def _normalize_script_lookup_key (name):
	try:
		s = str(name)
	except:
		return ''
	s = s.lstrip('_').lower()
	out = ''
	for ch in s:
		if ('a' <= ch <= 'z') or ('0' <= ch <= '9') or ch == '_':
			out += ch
	return out

def _append_script_lookup_candidate (_out, _seen, _value):
	try:
		s = str(_value)
	except Exception:
		return
	if s == '' or s in _seen:
		return
	_seen.add(s)
	_out.append(s)

def _script_lookup_candidate_names (name):
	candidates = []
	seen = set()
	_append_script_lookup_candidate(candidates, seen, name)
	if not isinstance(name, str):
		return candidates
	base_name = str(name)
	def _append_template_source_candidates (_spawn_suffix):
		if not isinstance(_spawn_suffix, str) or _spawn_suffix == '':
			return
		source_name = _spawn_suffix
		sep_idx = source_name.find('_')
		if sep_idx > 0:
			prefix = source_name[:sep_idx]
			rest = source_name[sep_idx + 1:]
			if prefix.isdigit() and rest != '':
				source_name = rest
		_append_script_lookup_candidate(candidates, seen, source_name)
		_append_script_lookup_candidate(candidates, seen, '_' + source_name)
		_append_script_lookup_candidate(candidates, seen, source_name + ':0')
		_append_script_lookup_candidate(candidates, seen, '_' + source_name + ':0')
	if base_name.startswith('_'):
		_append_script_lookup_candidate(candidates, seen, base_name[1:])
	else:
		_append_script_lookup_candidate(candidates, seen, '_' + base_name)
	if ':' in base_name:
		_append_script_lookup_candidate(candidates, seen, base_name.split(':', 1)[0])
	if not base_name.endswith(':0'):
		_append_script_lookup_candidate(candidates, seen, base_name + ':0')
		if base_name.startswith('_'):
			_append_script_lookup_candidate(candidates, seen, base_name[1:] + ':0')
		else:
			_append_script_lookup_candidate(candidates, seen, '_' + base_name + ':0')
	if base_name.startswith('__gbc_spawn_'):
		suffix = base_name[len('__gbc_spawn_'):]
		phys_name = '__gbc_spawnphys_' + suffix
		_append_script_lookup_candidate(candidates, seen, phys_name)
		_append_script_lookup_candidate(candidates, seen, '_' + phys_name)
		_append_script_lookup_candidate(candidates, seen, phys_name + ':0')
		_append_script_lookup_candidate(candidates, seen, '_' + phys_name + ':0')
		_append_template_source_candidates(suffix)
	elif base_name.startswith('__gbc_spawnphys_'):
		suffix = base_name[len('__gbc_spawnphys_'):]
		draw_name = '__gbc_spawn_' + suffix
		_append_script_lookup_candidate(candidates, seen, draw_name)
		_append_script_lookup_candidate(candidates, seen, '_' + draw_name)
		_append_script_lookup_candidate(candidates, seen, draw_name + ':0')
		_append_script_lookup_candidate(candidates, seen, '_' + draw_name + ':0')
		_append_template_source_candidates(suffix)
	return candidates

def _resolve_script_lookup (sourceDict, name):
	src = sourceDict
	if not isinstance(src, dict):
		try:
			# _ScriptLookupDict and similar wrappers can expose the backing dict.
			_get_src = getattr(src, '_source_dict', None)
			if callable(_get_src):
				src = _get_src()
		except Exception:
			src = sourceDict
	if not isinstance(src, dict):
		try:
			if hasattr(src, 'items'):
				src = dict(src.items())
		except Exception:
			src = {}
	if not isinstance(src, dict):
		return None
	candidate_names = _script_lookup_candidate_names(name)
	for candidate in candidate_names:
		if candidate not in src:
			continue
		value = src[candidate]
		if value is not None:
			return value
	for candidate in candidate_names:
		if not isinstance(candidate, str):
			continue
		nameNorm = _normalize_script_lookup_key(candidate)
		if nameNorm == '':
			continue
		for k, v in list(src.items()):
			if not isinstance(k, str):
				continue
			kNorm = _normalize_script_lookup_key(k)
			if (
				kNorm == nameNorm
				or kNorm.endswith('_' + nameNorm)
				or kNorm.endswith(nameNorm)
				or kNorm.startswith(nameNorm + '_')
				or kNorm.startswith(nameNorm)
			):
				return v
	return None

def _resolve_script_lookup_from_sources (name, *sources):
	for src in list(sources or []):
		try:
			value = _resolve_script_lookup(src, name)
		except Exception:
			value = None
		if value is not None:
			return value
	return None

class _ScriptLookupDict:
	def __init__ (self, source):
		self._source = source
	def _source_dict (self):
		src = self._source() if callable(self._source) else self._source
		if isinstance(src, _ScriptLookupDict):
			# Guard against accidental wrapper cycles.
			return src._source_dict()
		if isinstance(src, dict):
			return src
		try:
			if hasattr(src, 'items'):
				return dict(src.items())
		except Exception:
			pass
		return {}
	def __getitem__ (self, name):
		src = self._source_dict()
		if name in src:
			return src[name]
		value = _resolve_script_lookup(src, name)
		return value
	def get (self, name, default = None):
		src = self._source_dict()
		if name in src:
			return src.get(name, default)
		value = _resolve_script_lookup(src, name)
		return default if value is None else value
	def __contains__ (self, name):
		src = self._source_dict()
		if name in src:
			return True
		return _resolve_script_lookup(src, name) is not None
	def keys (self):
		return self._source_dict().keys()
	def items (self):
		return self._source_dict().items()
	def values (self):
		return self._source_dict().values()
	def __iter__ (self):
		return iter(self._source_dict())
	def __len__ (self):
		return len(self._source_dict())

def _get_script_locals (instanceName, scriptKey, this):
	if instanceName not in scriptLocals:
		scriptLocals[instanceName] = {}
	instanceScriptLocals = scriptLocals[instanceName]
	if scriptKey not in instanceScriptLocals:
		instanceScriptLocals[scriptKey] = {}
	localsDict = instanceScriptLocals[scriptKey]
	localsDict['this'] = this
	localsDict['_currentInstanceName'] = instanceName
	localsDict['objects'] = localsDict.get('obs', globals().get('obs', {}))
	localsDict['rigidBodies'] = _ScriptLookupDict(lambda : rigidBodiesIds)
	localsDict['rbs'] = localsDict['rigidBodies']
	localsDict['colliders'] = _ScriptLookupDict(lambda : collidersIds)
	localsDict['cols'] = localsDict['colliders']
	localsDict['sim'] = sim
	localsDict['physics'] = sim
	def _safe_lookup_handle (_name, *sources):
		try:
			key = str(_name)
		except Exception:
			key = ''
		candidates = [key]
		if isinstance(key, str) and key != '':
			if key.startswith('_'):
				candidates.append(key[1:])
			else:
				candidates.append('_' + key)
			if not key.endswith(':0'):
				candidates.append(key + ':0')
				if key.startswith('_'):
					candidates.append(key[1:] + ':0')
				else:
					candidates.append('_' + key + ':0')
			if key.startswith('__gbc_spawn_'):
				suffix = key[len('__gbc_spawn_'):]
				phys = '__gbc_spawnphys_' + suffix
				candidates.extend([phys, '_' + phys, phys + ':0', '_' + phys + ':0'])
			elif key.startswith('__gbc_spawnphys_'):
				suffix = key[len('__gbc_spawnphys_'):]
				draw = '__gbc_spawn_' + suffix
				candidates.extend([draw, '_' + draw, draw + ':0', '_' + draw + ':0'])
		for src in list(sources or []):
			src_dict = src if isinstance(src, dict) else {}
			if not isinstance(src_dict, dict):
				try:
					if hasattr(src, 'items'):
						src_dict = dict(src.items())
				except Exception:
					src_dict = {}
			for cand in candidates:
				try:
					v = src_dict.get(cand, None)
				except Exception:
					v = None
				if v is not None:
					return v
			# Fuzzy fallback for generated runtime keys (for example spawned
			# __gbc_spawnphys_* proxies backing a template/source object name).
			try:
				v = _resolve_script_lookup(src_dict, key)
			except Exception:
				v = None
			if v is not None:
				return v
		return None
	def _safe_get_rigidbody (name):
		return _safe_lookup_handle(name, rigidBodiesIds, globals().get('rigidBodies', {}))
	def _safe_get_collider (name):
		return _safe_lookup_handle(name, collidersIds, globals().get('colliders', {}))
	def _safe_get_object_position (name):
		def _nonzero_or_none (_p):
			try:
				if isinstance(_p, (list, tuple)) and len(_p) >= 2:
					_x = float(_p[0]); _y = float(_p[1])
					if (abs(_x) + abs(_y)) > 1e-6:
						return [_x, _y]
			except Exception:
				pass
			return None
		_obs_pos_fn = globals().get('_runtime_obs_position_from_sources', None)
		_obs_pos = _obs_pos_fn(name, localsDict.get('objects', {}), localsDict.get('obs', {}), globals().get('obs', {}), globals().get('objects', {})) if callable(_obs_pos_fn) else None
		if _obs_pos is not None:
			return _obs_pos
		rb = _safe_get_rigidbody(name)
		if rb is not None:
			try:
				pos = _normalize_gbc_script_position(sim.get_rigid_body_position(rb))
				return _prefer_static_pos_when_dynamic_zero(name, pos)
			except Exception:
				pass
		col = _safe_get_collider(name)
		if col is not None:
			try:
				pos = _normalize_gbc_script_position(sim.get_collider_position(col))
				return _prefer_static_pos_when_dynamic_zero(name, pos)
			except Exception:
				pass
		_spawn_pos = _safe_lookup_handle(name, __import__('builtins').globals().get('_gbc_spawn_owner_pos_overrides', {}))
		if isinstance(_spawn_pos, (list, tuple)) and len(_spawn_pos) >= 2:
			try:
				_x = float(_spawn_pos[0]); _y = float(_spawn_pos[1])
				if (abs(_x) + abs(_y)) > 1e-6:
					return [_x, _y]
			except Exception:
				pass
		_fn = __import__('builtins').globals().get('get_object_position')
		if callable(_fn):
			try:
				_out = _fn(name)
				_nz = _nonzero_or_none(_out)
				if _nz is not None:
					return _nz
			except Exception:
				pass
		try:
			_obs = globals().get('obs', globals().get('objects', {}))
			if isinstance(_obs, dict):
				_entry = _resolve_script_lookup(_obs, str(name))
				if isinstance(_entry, dict):
					_obj_pos = _entry.get('pos', _entry.get('position', None))
					if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
						_nz = _nonzero_or_none(_obj_pos)
						if _nz is not None:
							return _nz
		except Exception:
			pass
		try:
			_static = _resolve_static_owner_camera_position(str(name))
			if isinstance(_static, (list, tuple)) and len(_static) >= 2:
				_nz = _nonzero_or_none(_static)
				if _nz is not None:
					return _nz
		except Exception:
			pass
		return [0.0, 0.0]
	def _safe_get_object_rotation (name):
		_fn = __import__('builtins').globals().get('get_object_rotation')
		if callable(_fn):
			return _fn(name)
		rb = _safe_get_rigidbody(name)
		if rb is not None:
			try:
				return sim.get_rigid_body_rotation(rb)
			except Exception:
				pass
		col = _safe_get_collider(name)
		if col is not None:
			try:
				return sim.get_collider_rotation(col)
			except Exception:
				pass
		return 0.0
	# Keep helper callables stable across frames even when script locals persist.
	localsDict['_js13k_print'] = __import__('builtins').print
	if not callable(localsDict.get('print', None)):
		localsDict['print'] = localsDict['_js13k_print']
	def _js13k_call_print (*args, sep = ' ', end = '\n', file = None, flush = False):
		for _fn in (localsDict.get('_js13k_print', None), localsDict.get('print', None), __import__('builtins').print):
			if callable(_fn):
				try:
					return _fn(*args, sep = sep, end = end, file = file, flush = flush)
				except Exception:
					continue
		return None
	def _js13k_call_get_object_position (_name):
		def _nonzero_or_none (_p):
			try:
				if isinstance(_p, (list, tuple)) and len(_p) >= 2:
					_x = float(_p[0]); _y = float(_p[1])
					if (abs(_x) + abs(_y)) > 1e-6:
						return [_x, -_y]
			except Exception:
				pass
			return None
		for _fn in (
			localsDict.get('_js13k_internal_get_object_position', None),
			localsDict.get('gbc_get_object_position', None),
			localsDict.get('get_object_position', None),
			_safe_get_object_position,
		):
			if callable(_fn):
				try:
					_out = _fn(_name)
					_nz = _nonzero_or_none(_out)
					if _nz is not None:
						return _nz
				except Exception:
					continue
		try:
			_fn = __import__('builtins').globals().get('get_object_position', None)
			if callable(_fn):
				_out = _fn(_name)
				_nz = _nonzero_or_none(_out)
				if _nz is not None:
					return _nz
		except Exception:
			pass
		try:
			_static = _resolve_static_owner_camera_position(str(_name))
			if isinstance(_static, (list, tuple)) and len(_static) >= 2:
				_nz = _nonzero_or_none(_static)
				if _nz is not None:
					return _nz
		except Exception:
			pass
		return [0.0, 0.0]
	def _js13k_call_get_object_rotation (_name):
		for _fn in (
			localsDict.get('_js13k_internal_get_object_rotation', None),
			localsDict.get('gbc_get_object_rotation', None),
			localsDict.get('get_object_rotation', None),
			_safe_get_object_rotation,
		):
			if callable(_fn):
				try:
					return _fn(_name)
				except Exception:
					continue
		return 0.0
	localsDict['_js13k_call_print'] = _js13k_call_print
	localsDict['_js13k_call_get_object_position'] = _js13k_call_get_object_position
	localsDict['_js13k_call_get_object_rotation'] = _js13k_call_get_object_rotation
	localsDict['get_rigidbody'] = _safe_get_rigidbody
	localsDict['get_collider'] = _safe_get_collider
	localsDict['get_object_position'] = _safe_get_object_position
	localsDict['get_object_rotation'] = _safe_get_object_rotation
	localsDict['gbc_get_rigidbody'] = _safe_get_rigidbody
	localsDict['gbc_get_collider'] = _safe_get_collider
	localsDict['gbc_get_object_position'] = _safe_get_object_position
	localsDict['gbc_get_object_rotation'] = _safe_get_object_rotation
	localsDict['_js13k_internal_get_object_position'] = _safe_get_object_position
	localsDict['_js13k_internal_get_object_rotation'] = _safe_get_object_rotation
	localsDict['_js13k_pos_resolver'] = _safe_get_object_position
	localsDict['_js13k_rot_resolver'] = _safe_get_object_rotation
	try:
		class _Js13kScriptHelpers:
			__slots__ = ('_pos_fn', '_rot_fn')
			def __init__ (self, _p, _r):
				object.__setattr__(self, '_pos_fn', _p)
				object.__setattr__(self, '_rot_fn', _r)
			def __setattr__ (self, _name, _value):
				# Prevent scripts from clobbering helper callables.
				if _name in ('get_object_position', 'get_object_rotation', '_pos_fn', '_rot_fn'):
					return
				object.__setattr__(self, _name, _value)
			def _trace_pos (self, _name, _source, _value):
				try:
					_g = globals()
					_seen = _g.get('_js13k_helper_pos_trace_seen', None)
					if not isinstance(_seen, set):
						_seen = set()
						_g['_js13k_helper_pos_trace_seen'] = _seen
					_sig = ('locals', str(_name), str(_source), repr(_value))
					if _sig in _seen:
						return
					_seen.add(_sig)
					_trace = _g.get('_append_gbc_trace_lines', None)
					if callable(_trace):
						_trace([
							'[gbc-trace] HelperGetPos'
							+ ':scope=locals'
							+ ',name=' + repr(str(_name))
							+ ',source=' + str(_source)
							+ ',out=' + repr(_value)
						])
				except Exception:
					pass
			def get_object_position (self, _name):
				try:
					_fn = globals().get('_runtime_obs_position_from_sources', None)
					_p = _fn(
						_name,
						localsDict.get('objects', {}),
						localsDict.get('obs', {}),
						globals().get('objects', {}),
						globals().get('obs', {}),
					) if callable(_fn) else None
					if _p is not None:
						_out = [float(_p[0]), float(_p[1])]
						self._trace_pos(_name, 'obs_sources', _out)
						return _out
				except Exception:
					pass
				_out = self._pos_fn(_name)
				self._trace_pos(_name, 'pos_fn_fallback', _out)
				return _out
			def get_object_rotation (self, _name):
				return self._rot_fn(_name)
		_helpers = _Js13kScriptHelpers(_safe_get_object_position, _safe_get_object_rotation)
		localsDict['__js13k_helpers__'] = _helpers
	except Exception:
		pass
	# Final safety net: recover callable bindings if a script/local clobbered them.
	try:
		if not callable(localsDict.get('get_object_position', None)):
			localsDict['get_object_position'] = _safe_get_object_position
		if not callable(localsDict.get('get_object_rotation', None)):
			localsDict['get_object_rotation'] = _safe_get_object_rotation
		_h = localsDict.get('__js13k_helpers__', None)
		_pos_ok = callable(getattr(_h, 'get_object_position', None)) if _h is not None else False
		_rot_ok = callable(getattr(_h, 'get_object_rotation', None)) if _h is not None else False
		if not (_pos_ok and _rot_ok):
			class _Js13kScriptHelpersFallback:
				__slots__ = ()
				def get_object_position (self, _name):
					return _safe_get_object_position(_name)
				def get_object_rotation (self, _name):
					return _safe_get_object_rotation(_name)
			localsDict['__js13k_helpers__'] = _Js13kScriptHelpersFallback()
	except Exception:
		pass
	return localsDict

def _exec_script (code, instanceName, this, phase, scriptKey):
	try:
		exec(code, globals(), _get_script_locals(instanceName, scriptKey, this))
	except Exception as err:
		print(f"[script:{phase}] {instanceName}: {err}")

def run_init_scripts (name):
	global _currentInstanceName
	this = _ThisObject(name)
	tid = instanceToTemplate.get(name)
	if tid and tid in templateScripts and templateScripts[tid].get('init'):
		_currentInstanceName = name
		for i, code in enumerate(templateScripts[tid]['init']):
			try:
				_exec_script(code, name, this, 'init', ('template', tid, 'init', i, id(code)))
			except: pass
		_currentInstanceName = None
	if name in scripts and scripts[name].get('init'):
		_currentInstanceName = name
		for i, code in enumerate(scripts[name]['init']):
			_exec_script(code, name, this, 'init', ('instance', name, 'init', i, id(code)))
		_currentInstanceName = None

def run_update_scripts ():
	global _currentInstanceName
	for name in list(liveObjectNames):
		this = _ThisObject(name)
		tid = instanceToTemplate.get(name)
		if tid and tid in templateScripts and templateScripts[tid].get('update'):
			_currentInstanceName = name
			for i, code in enumerate(templateScripts[tid]['update']):
				_exec_script(code, name, this, 'update', ('template', tid, 'update', i, id(code)))
			_currentInstanceName = None
		if name in scripts and scripts[name].get('update'):
			_currentInstanceName = name
			for i, code in enumerate(scripts[name]['update']):
				_exec_script(code, name, this, 'update', ('instance', name, 'update', i, id(code)))
			_currentInstanceName = None

def add_script (instanceName, code, type):
	if instanceName not in scripts:
		scripts[instanceName] = {'init': [], 'update': []}
	scripts[instanceName][type].append(code)
	if type == 'init':
		global _currentInstanceName
		_currentInstanceName = instanceName
		this = _ThisObject(instanceName)
		script_index = len(scripts[instanceName][type]) - 1
		_exec_script(code, instanceName, this, 'init', ('instance', instanceName, 'init', script_index, id(code)))
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

def _normalize_gbc_script_position (_pos):
	try:
		x = float(_pos[0])
		y = float(_pos[1])
	except Exception:
		return _pos
	# Some runtimes expose bias-encoded signed values directly.
	# Normalize those back into script-space coordinates.
	half_bias = float(_GBC_POSITION_BIAS) * 0.5
	if x < -half_bias:
		x = x + float(_GBC_POSITION_BIAS)
	elif x > half_bias:
		x = x - float(_GBC_POSITION_BIAS)
	if y < -half_bias:
		y = -(y + float(_GBC_POSITION_BIAS))
	elif y > half_bias:
		y = -(y - float(_GBC_POSITION_BIAS))
	return [x, y]

def _prefer_static_pos_when_dynamic_zero (_name, _dynamic_pos):
	try:
		dx = abs(float(_dynamic_pos[0])) + abs(float(_dynamic_pos[1]))
	except Exception:
		return _dynamic_pos
	if dx > 1e-6:
		return _dynamic_pos
	# If a resolved rigid-body/collider reports [0,0], prefer exported runtime
	# object position data for this owner before falling back further.
	try:
		_obs = globals().get('obs', globals().get('objects', {}))
		if isinstance(_obs, dict):
			_entry = _resolve_script_lookup(_obs, str(_name))
			if isinstance(_entry, dict):
				_obj_pos = _entry.get('pos', _entry.get('position', None))
				if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
					ox = float(_obj_pos[0]); oy = float(_obj_pos[1])
					if (abs(ox) + abs(oy)) > 1e-6:
						return [ox, oy]
	except Exception:
		pass
	# Spawn-owner overrides can be stale zeros; only trust non-zero entries.
	try:
		_spawn = __import__('builtins').globals().get('_gbc_spawn_owner_pos_overrides', {})
		if isinstance(_spawn, dict):
			_sp = _resolve_script_lookup(_spawn, str(_name))
			if isinstance(_sp, (list, tuple)) and len(_sp) >= 2:
				sx = float(_sp[0]); sy = float(_sp[1])
				if (abs(sx) + abs(sy)) > 1e-6:
					return [sx, sy]
	except Exception:
		pass
	try:
		static_pos = _resolve_static_owner_camera_position(str(_name))
	except Exception:
		static_pos = None
	if isinstance(static_pos, (list, tuple)) and len(static_pos) >= 2:
		try:
			sx = abs(float(static_pos[0])) + abs(float(static_pos[1]))
			if sx > 1e-6:
				return [float(static_pos[0]), float(static_pos[1])]
		except Exception:
			pass
	return _dynamic_pos

def _runtime_obs_position_from_sources (_name, *sources):
	try:
		candidates = []
		seen = set()
		def _append_cand (_v):
			try:
				_s = str(_v)
			except Exception:
				return
			if _s == '' or _s in seen:
				return
			seen.add(_s)
			candidates.append(_s)
		_append_cand(_name)
		try:
			for _cand in list(_script_lookup_candidate_names(_name) or []):
				_append_cand(_cand)
		except Exception:
			pass
		for _src in list(sources or []):
			src_dict = _src if isinstance(_src, dict) else None
			if not isinstance(src_dict, dict):
				try:
					if hasattr(_src, 'items'):
						src_dict = dict(_src.items())
				except Exception:
					src_dict = None
			if not isinstance(src_dict, dict):
				continue
			for _cand in candidates:
				_entry = src_dict.get(_cand, None)
				if not isinstance(_entry, dict):
					continue
				_obj_pos = _entry.get('pos', _entry.get('position', None))
				if not (isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2):
					continue
				try:
					return [float(_obj_pos[0]), float(_obj_pos[1])]
				except Exception:
					continue
		try:
			name_norm = _normalize_script_lookup_key(_name)
		except Exception:
			name_norm = ''
		if name_norm != '':
			for _src in list(sources or []):
				src_dict = _src if isinstance(_src, dict) else None
				if not isinstance(src_dict, dict):
					try:
						if hasattr(_src, 'items'):
							src_dict = dict(_src.items())
					except Exception:
						src_dict = None
				if not isinstance(src_dict, dict):
					continue
				for _k, _entry in list(src_dict.items()):
					if not isinstance(_k, str) or not isinstance(_entry, dict):
						continue
					if _normalize_script_lookup_key(_k) != name_norm:
						continue
					_obj_pos = _entry.get('pos', _entry.get('position', None))
					if not (isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2):
						continue
					try:
						return [float(_obj_pos[0]), float(_obj_pos[1])]
					except Exception:
						continue
		return None
	except Exception:
		return None

def _runtime_obs_position_nonzero (_name):
	try:
		_obs = globals().get('obs', globals().get('objects', {}))
		_objects = globals().get('objects', {})
		return _runtime_obs_position_from_sources(_name, _obs, _objects)
	except Exception:
		return None

def get_object_position (name):
	def _trace_return (_source, _value):
		try:
			_g = globals()
			_seen = _g.get('_js13k_get_object_position_trace_seen', None)
			if not isinstance(_seen, set):
				_seen = set()
				_g['_js13k_get_object_position_trace_seen'] = _seen
			_sig = (str(name), str(_source), repr(_value))
			if _sig in _seen:
				return
			_seen.add(_sig)
			_trace = _g.get('_append_gbc_trace_lines', None)
			if callable(_trace):
				_trace([
					'[gbc-trace] GetObjectPos'
					+ ':name=' + repr(str(name))
					+ ',source=' + str(_source)
					+ ',out=' + repr(_value)
				])
		except Exception:
			pass
	# In gbc-py wrapped execution, prefer authored/exported object position
	# first to avoid transient physics-handle misresolution.
	try:
		if bool(globals().get('_js13k_gbc_signed_pos_wrapped', False)):
			_obs_pos_fn = globals().get('_runtime_obs_position_from_sources', None)
			_obs_pos = _obs_pos_fn(
				name,
				globals().get('objects', {}),
				globals().get('obs', {}),
			) if callable(_obs_pos_fn) else None
			if _obs_pos is not None:
				_trace_return('gbc_wrapped_obs', _obs_pos)
				return _obs_pos
			_static = _resolve_static_owner_camera_position(str(name))
			if isinstance(_static, (list, tuple)) and len(_static) >= 2:
				_out = [float(_static[0]), float(_static[1])]
				_trace_return('gbc_wrapped_static', _out)
				return _out
	except Exception:
		pass
	_obs_pos_fn = globals().get('_runtime_obs_position_nonzero', None)
	_obs_pos = _obs_pos_fn(name) if callable(_obs_pos_fn) else None
	if _obs_pos is not None:
		_trace_return('obs_nonzero', _obs_pos)
		return _obs_pos
	rigid_body = _resolve_script_lookup_from_sources(name, rigidBodiesIds, globals().get('rigidBodies', {}))
	if rigid_body is not None:
		pos = _normalize_gbc_script_position(sim.get_rigid_body_position(rigid_body))
		_out = _prefer_static_pos_when_dynamic_zero(name, pos)
		_trace_return('rigid_body', _out)
		return _out
	collider = _resolve_script_lookup_from_sources(name, collidersIds, globals().get('colliders', {}))
	if collider is not None:
		pos = _normalize_gbc_script_position(sim.get_collider_position(collider))
		_out = _prefer_static_pos_when_dynamic_zero(name, pos)
		_trace_return('collider', _out)
		return _out
	# Runtime/exported object fallback (works when physics handles are missing).
	try:
		_obs = globals().get('obs', globals().get('objects', {}))
		if isinstance(_obs, dict):
			_entry = _resolve_script_lookup(_obs, str(name))
			if isinstance(_entry, dict):
				_obj_pos = _entry.get('pos', _entry.get('position', None))
				if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
					_out = [float(_obj_pos[0]), float(_obj_pos[1])]
					_trace_return('obs_fallback', _out)
					return _out
	except Exception:
		pass
	# For non-physics objects, always report authored object-space position.
	# (Do not use render-rect/camera-space fallbacks here.)
	try:
		static_pos = _resolve_static_owner_camera_position(str(name))
	except Exception:
		static_pos = None
	if isinstance(static_pos, (list, tuple)) and len(static_pos) >= 2:
		try:
			_out = [float(static_pos[0]), float(static_pos[1])]
			_trace_return('static_fallback', _out)
			return _out
		except Exception:
			pass
	raise ValueError('name needs to refer to a rigid body, collider, or exported object with an authored position')

def get_object_rotation (name):
	if name in rigidBodiesIds:
		return sim.get_rigid_body_rotation(rigidBodiesIds[name])
	elif name in collidersIds:
		return sim.get_collider_rotation(collidersIds[name])
	else:
		raise ValueError('name needs to refer to a rigid body or a collider found in rigidBodiesIds or collidersIds')

def _js13k_runtime_get_object_position (name):
	return get_object_position(name)

def _js13k_runtime_get_object_rotation (name):
	return get_object_rotation(name)

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
globalThis.rigidBodies = rigidBodiesIds;
globalThis.colliders = collidersIds;
globalThis.rbs = globalThis.rigidBodies;
globalThis.cols = globalThis.colliders;
function _lookup_physics_handle (dict, name)
{
	if (Object.prototype.hasOwnProperty.call(dict, name))
		return dict[name];
	if (typeof name === 'string')
	{
		var underscored = name.startsWith('_') ? name : '_' + name;
		if (Object.prototype.hasOwnProperty.call(dict, underscored))
			return dict[underscored];
		if (name.startsWith('_'))
		{
			var plain = name.slice(1);
			if (Object.prototype.hasOwnProperty.call(dict, plain))
				return dict[plain];
		}
	}
	return null;
}
globalThis.get_rigidbody = function (name)
{
	return _lookup_physics_handle(rigidBodiesIds, name);
};
globalThis.get_collider = function (name)
{
	return _lookup_physics_handle(collidersIds, name);
};
globalThis.sim = globalThis.sim || {};
globalThis.sim.set_linear_velocity = function (rigidBody, vel, wakeUp = true)
{
	if (!rigidBody || !vel || vel.length < 2 || typeof rigidBody.setLinvel !== 'function')
		return;
	rigidBody.setLinvel(new RAPIER.Vector2(Number(vel[0]) || 0, Number(vel[1]) || 0), wakeUp);
};
globalThis.sim.get_linear_velocity = function (rigidBody)
{
	if (!rigidBody || typeof rigidBody.linvel !== 'function')
		return [0, 0];
	var v = rigidBody.linvel();
	return [v.x, v.y];
};
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
	scope.objects = globalThis.obs || {};
	scope.rigidBodies = globalThis.rigidBodies || globalThis.rigidBodiesIds || {};
	scope.rbs = scope.rigidBodies;
	scope.colliders = globalThis.colliders || globalThis.collidersIds || {};
	scope.cols = scope.colliders;
	scope.get_rigidbody = globalThis.get_rigidbody || function (name)
	{
		var dict = globalThis.rigidBodies || globalThis.rigidBodiesIds || {};
		if (Object.prototype.hasOwnProperty.call(dict, name))
			return dict[name];
		if (typeof name === 'string')
		{
			if (Object.prototype.hasOwnProperty.call(dict, '_' + name))
				return dict['_' + name];
			if (name.startsWith('_') && Object.prototype.hasOwnProperty.call(dict, name.slice(1)))
				return dict[name.slice(1)];
		}
		return null;
	};
	scope.get_collider = globalThis.get_collider || function (name)
	{
		var dict = globalThis.colliders || globalThis.collidersIds || {};
		if (Object.prototype.hasOwnProperty.call(dict, name))
			return dict[name];
		if (typeof name === 'string')
		{
			if (Object.prototype.hasOwnProperty.call(dict, '_' + name))
				return dict['_' + name];
			if (name.startsWith('_') && Object.prototype.hasOwnProperty.call(dict, name.slice(1)))
				return dict[name.slice(1)];
		}
		return null;
	};
	scope.sim = globalThis.sim || {
		set_linear_velocity: function (rb, vel, wakeUp = true)
		{
			if (!rb || !vel || vel.length < 2 || typeof rb.setLinvel !== 'function')
				return;
			var V = globalThis.RAPIER && globalThis.RAPIER.Vector2;
			if (!V)
				return;
			rb.setLinvel(new V(Number(vel[0]) || 0, Number(vel[1]) || 0), wakeUp);
		},
		get_linear_velocity: function (rb)
		{
			if (!rb || typeof rb.linvel !== 'function')
				return [0, 0];
			var v = rb.linvel();
			return [v.x, v.y];
		},
	};
	scope.physics = scope.sim;
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
			// copy_node performs a deep clone, so prefab descendants from the
			// template can remain as visual-only children with stale IDs.
			// Always rebuild descendants from nodeDef so each child gets proper
			// instance IDs, scripts, and physics registrations.
			for (var c = spawnedNode.children.length - 1; c >= 0; c --)
				spawnedNode.children[c].remove();
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
	var posX = 0;
	var posY = 0;
	if (Array.isArray(pos))
	{
		posX = pos.length > 0 && pos[0] != null ? pos[0] : 0;
		posY = pos.length > 1 && pos[1] != null ? pos[1] : 0;
	}
	else if (pos && typeof pos === 'object')
	{
		posX = pos.x != null ? pos.x : 0;
		posY = pos.y != null ? pos.y : 0;
	}
	var rootWorld = [posX, posY];
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
def _run_py2gb_export_with_resolved_logs (export_fn, script_entries, out_path, strict_print_exprs : bool = False):
	start_time = time.time()
	stdout_buf = io.StringIO()
	stderr_buf = io.StringIO()
	const_env = {}
	for entry in list(script_entries or []):
		const_env.update(_collect_simple_const_env_from_script(entry.get('code', '')))
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
			print(_resolve_runtime_print_exprs(line, start_time = start_time, const_env = const_env, strict = strict_print_exprs))
	for raw in stderr_buf.getvalue().splitlines():
		line = raw.rstrip('\n')
		if line:
			print(_resolve_runtime_print_exprs(line, start_time = start_time, const_env = const_env, strict = strict_print_exprs))
	return result

def _resolve_runtime_print_exprs (text : str, frame : int = None, start_time : float = None, const_env : dict = None, extra_env : dict = None, strict : bool = False):
	'''Resolve <expr:...> print placeholders to runtime values.'''
	if not isinstance(text, str):
		text = str(text)
	had_expr_placeholder = ('<expr:' in text.lower())
	const_env = const_env if isinstance(const_env, dict) else {}
	extra_env = extra_env if isinstance(extra_env, dict) else {}
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
	class _RuntimePrintSimCompat:
		def __init__ (self):
			self._lin_vel = {}
			self._ang_vel = {}
			self._rb_pos = {}
			self._rb_rot = {}
		def _key (self, handle):
			try:
				if handle is None:
					return '__none__'
				return str(handle)
			except Exception:
				return '__unknown__'
		def set_linear_velocity (self, rigidBody, vel, wakeUp = True):
			try:
				vx = float(vel[0])
				vy = float(vel[1])
			except Exception:
				vx = 0.0
				vy = 0.0
			self._lin_vel[self._key(rigidBody)] = [vx, vy]
		def get_linear_velocity (self, rigidBody):
			return list(self._lin_vel.get(self._key(rigidBody), [0.0, 0.0]))
		def set_angular_velocity (self, rigidBody, angVel, wakeUp = True):
			try:
				self._ang_vel[self._key(rigidBody)] = float(angVel)
			except Exception:
				self._ang_vel[self._key(rigidBody)] = 0.0
		def get_angular_velocity (self, rigidBody):
			return float(self._ang_vel.get(self._key(rigidBody), 0.0))
		def set_rigid_body_position (self, rigidBody, pos, wakeUp = True):
			try:
				self._rb_pos[self._key(rigidBody)] = [float(pos[0]), float(pos[1])]
			except Exception:
				self._rb_pos[self._key(rigidBody)] = [0.0, 0.0]
		def get_rigid_body_position (self, rigidBody):
			return list(self._rb_pos.get(self._key(rigidBody), [0.0, 0.0]))
		def set_rigid_body_rotation (self, rigidBody, rot, wakeUp = True):
			try:
				self._rb_rot[self._key(rigidBody)] = float(rot)
			except Exception:
				self._rb_rot[self._key(rigidBody)] = 0.0
		def get_rigid_body_rotation (self, rigidBody):
			return float(self._rb_rot.get(self._key(rigidBody), 0.0))
		def __getattr__ (self, _name):
			if isinstance(_name, str) and _name.startswith('get_'):
				return (lambda *args, **kwargs: None)
			return (lambda *args, **kwargs: 0)
	compat_sim = _RuntimePrintSimCompat()
	def _eval_expr_text (expr):
		expr = str(expr).strip()
		def _coerce_numeric_like_in_containers (_val):
			if isinstance(_val, list):
				return [_coerce_numeric_like_in_containers(v) for v in _val]
			if isinstance(_val, tuple):
				return tuple(_coerce_numeric_like_in_containers(v) for v in _val)
			if isinstance(_val, dict):
				return {k : _coerce_numeric_like_in_containers(v) for k, v in _val.items()}
			if isinstance(_val, str):
				txt = _val.strip()
				if re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', txt):
					try:
						if re.fullmatch(r'[+-]?\d+', txt):
							return int(txt)
						return float(txt)
					except Exception:
						return _val
			return _val
		# Replace supported runtime function calls with numeric values first.
		expr_with_ticks = _replace_runtime_ticks_calls(expr, ticks)
		expr_eval = _replace_runtime_key_calls(expr_with_ticks)
		# Fast path: plain integer after replacement.
		if re.fullmatch(r'[+-]?\d+', expr_eval):
			return expr_eval
		key_state = _runtime_key_state_snapshot()
		try:
			runtime_globals = __import__('builtins').globals()
			rigid_bodies_runtime = extra_env.get('rigidBodiesIds', extra_env.get('rigidBodies', runtime_globals.get('rigidBodiesIds', runtime_globals.get('rigidBodies', {}))))
			if not isinstance(rigid_bodies_runtime, dict):
				rigid_bodies_runtime = {}
			colliders_runtime = extra_env.get('collidersIds', extra_env.get('colliders', runtime_globals.get('collidersIds', runtime_globals.get('colliders', {}))))
			if not isinstance(colliders_runtime, dict):
				colliders_runtime = {}
			# GBA/GBC print mirror can run with partial runtime state.
			# Always augment with exported object names to make physics lookups
			# robust against naming differences between script and runtime bindings.
			if callable(_py2gb_augment_runtime_physics_maps):
				try:
					rigid_bodies_runtime, colliders_runtime = _py2gb_augment_runtime_physics_maps(
						runtime_globals,
						rigid_bodies_runtime,
						colliders_runtime,
						GetVarNameForObject,
					)
				except Exception:
					pass
			rigid_bodies_named = dict(rigid_bodies_runtime)
			for k, v in list(rigid_bodies_runtime.items()):
				if isinstance(k, str) and k.startswith('_') and len(k) > 1:
					rigid_bodies_named.setdefault(k[1:], v)
			colliders_named = dict(colliders_runtime)
			for k, v in list(colliders_runtime.items()):
				if isinstance(k, str) and k.startswith('_') and len(k) > 1:
					colliders_named.setdefault(k[1:], v)
			sim_runtime = extra_env.get('sim', extra_env.get('physics', runtime_globals.get('sim', runtime_globals.get('physics', None))))
			if sim_runtime is None:
				all_script_locals = runtime_globals.get('scriptLocals', {})
				if isinstance(all_script_locals, dict):
					for scope in all_script_locals.values():
						if isinstance(scope, dict):
							_candidate = scope.get('sim', scope.get('physics', None))
							if _candidate is not None:
								sim_runtime = _candidate
								break
			if sim_runtime is None or not hasattr(sim_runtime, 'get_linear_velocity'):
				sim_runtime = compat_sim
			def _lookup_runtime_handle (_dict, _name):
				if not isinstance(_dict, dict):
					return None
				def _norm (_s):
					try:
						s = str(_s)
					except Exception:
						return ''
					s = s.lstrip('_').lower()
					out = ''
					for ch in s:
						if ('a' <= ch <= 'z') or ('0' <= ch <= '9') or ch == '_':
							out += ch
					return out
				try:
					candidates = _script_lookup_candidate_names(_name)
				except Exception:
					candidates = [_name]
				for candidate in list(candidates or []):
					try:
						if candidate in _dict:
							val = _dict[candidate]
							if val is not None:
								return val
					except Exception:
						pass
				for candidate in list(candidates or []):
					if not isinstance(candidate, str):
						continue
					name_norm = _norm(candidate)
					if name_norm == '':
						continue
					for k, v in list(_dict.items()):
						if not isinstance(k, str):
							continue
						k_norm = _norm(k)
						if (
							k_norm == name_norm
							or k_norm.endswith('_' + name_norm)
							or k_norm.endswith(name_norm)
							or k_norm.startswith(name_norm + '_')
							or k_norm.startswith(name_norm)
						):
							return v
				return None
			class _EvalLocals(dict):
				def __missing__ (self, key):
					return None
			def _get_rigidbody_for_print (_name):
				val = _lookup_runtime_handle(rigid_bodies_named, _name)
				if val is None:
					val = _lookup_runtime_handle(rigid_bodies_runtime, _name)
				if val is None and isinstance(_name, str) and _name != '':
					return _name
				return val
			def _get_collider_for_print (_name):
				val = _lookup_runtime_handle(colliders_named, _name)
				if val is None:
					val = _lookup_runtime_handle(colliders_runtime, _name)
				if val is None and isinstance(_name, str) and _name != '':
					return _name
				return val
			protected_names = set((
				'int', 'float', 'type', 'str', 'repr', 'len', 'list', 'tuple', 'dict',
				'round', 'abs', 'max', 'min', 'bool', 'hasattr', 'getattr', 'callable',
				'keys', 'js13k_get_pressed',
			))
			for _nm in (
				'obs', 'objects',
				'rigidBodies', 'rigidBodiesIds', 'get_rigidbody',
				'rbs',
				'colliders', 'collidersIds', 'get_collider',
				'cols',
				'sim', 'physics',
			):
				if _is_runtime_script_binding_name(_nm):
					protected_names.add(_nm)
			eval_locals = _EvalLocals({
				'int' : int,
				'float' : float,
				'type' : type,
				'str' : str,
				'repr' : repr,
				'len' : len,
				'list' : list,
				'tuple' : tuple,
				'dict' : dict,
				'round' : round,
				'abs' : abs,
				'max' : max,
				'min' : min,
				'bool' : bool,
				'hasattr' : hasattr,
				'getattr' : getattr,
				'callable' : callable,
				'keys' : key_state,
				'js13k_get_pressed' : (lambda : key_state),
				'objects' : extra_env.get('objects', runtime_globals.get('objects', runtime_globals.get('obs', {}))),
				'rigidBodies' : rigid_bodies_named,
				'rbs' : rigid_bodies_named,
				'rigidBodiesIds' : rigid_bodies_runtime,
				'colliders' : colliders_named,
				'cols' : colliders_named,
				'collidersIds' : colliders_runtime,
				'sim' : sim_runtime,
				'physics' : sim_runtime,
				'get_rigidbody' : (lambda name : _get_rigidbody_for_print(name)),
				'get_collider' : (lambda name : _get_collider_for_print(name)),
				'js13k_vec_update' : (lambda seq, idx, rhs, op = 'set': (
					(lambda _lst: (
						_lst.__setitem__(
							(int(idx) if int(idx) >= 0 else int(idx) + len(_lst)),
							(
								rhs if op == 'set' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] + rhs) if op == 'add' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] - rhs) if op == 'sub' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] * rhs) if op == 'mul' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] / rhs) if op == 'div' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] // rhs) if op == 'floordiv' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] % rhs) if op == 'mod' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] ** rhs) if op == 'pow' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] << rhs) if op == 'lshift' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] >> rhs) if op == 'rshift' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] & rhs) if op == 'and' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] | rhs) if op == 'or' else
								(_lst[int(idx) if int(idx) >= 0 else int(idx) + len(_lst)] ^ rhs) if op == 'xor' else
								rhs
							)
						),
						_lst
					)[1]
					)(list(seq if isinstance(seq, (list, tuple)) else []))
				)),
			})
			eval_locals['this'] = extra_env.get('this', runtime_globals.get('this', None))
			for k, v in const_env.items():
				if re.fullmatch(r'[A-Za-z_]\w*', str(k)) and _is_simple_const_value(v):
					name = str(k)
					if name in protected_names:
						continue
					eval_locals[name] = v
			for k, v in extra_env.items():
				name = str(k)
				if re.fullmatch(r'[A-Za-z_]\w*', name) and not name.startswith('__'):
					if name in protected_names:
						continue
					# Keep runtime key-state helpers authoritative for print eval.
					if name == 'keys':
						if not isinstance(v, (list, tuple)):
							continue
					if name == 'js13k_get_pressed' and not callable(v):
						continue
					eval_locals[name] = v
			for name in ('attributes', 'pivots', 'instanceToTemplate', 'liveObjectNames'):
				if name in runtime_globals:
					eval_locals[name] = runtime_globals[name]
			val = eval(
				expr_eval,
				{'__builtins__' : {}},
				eval_locals,
			)
			if val is None and re.fullmatch(r'[A-Za-z_]\w*', expr_eval) and expr_eval not in eval_locals:
				# Unresolved simple names should probe runtime globals/scopes before
				# falling back to literal text.
				name = expr_eval
				if name in extra_env:
					return str(extra_env[name])
				all_script_locals = __import__('builtins').globals().get('scriptLocals', {})
				if isinstance(all_script_locals, dict):
					for scope in all_script_locals.values():
						if isinstance(scope, dict):
							# New layout: scriptLocals[owner][scriptKey] = locals dict.
							if any(isinstance(v, dict) for v in scope.values()):
								for nested in scope.values():
									if isinstance(nested, dict) and name in nested:
										return str(nested[name])
							elif name in scope:
								# Legacy layout: scriptLocals[owner] = locals dict.
								return str(scope[name])
				runtime_globals = __import__('builtins').globals()
				if name in runtime_globals:
					return str(runtime_globals[name])
				# Mirror print eval is best-effort; unresolved names can happen when
				# the mirror cannot execute a runtime-only call path.
				if strict:
					return 'None'
				return expr_eval
			if isinstance(val, (int, float, bool, str)):
				return str(val)
			if isinstance(val, (list, tuple, dict)):
				return str(_coerce_numeric_like_in_containers(val))
			return str(val)
		except Exception:
			# Best-effort lookup for simple names from script locals/global runtime state.
			if re.fullmatch(r'[A-Za-z_]\w*', expr_eval):
				name = expr_eval
				if name in extra_env:
					return str(extra_env[name])
				all_script_locals = __import__('builtins').globals().get('scriptLocals', {})
				if isinstance(all_script_locals, dict):
					for scope in all_script_locals.values():
						if isinstance(scope, dict):
							if any(isinstance(v, dict) for v in scope.values()):
								for nested in scope.values():
									if isinstance(nested, dict) and name in nested:
										return str(nested[name])
							elif name in scope:
								return str(scope[name])
				runtime_globals = __import__('builtins').globals()
				if name in runtime_globals:
					return str(runtime_globals[name])
				if strict:
					return 'None'
			if strict and not re.fullmatch(r'[A-Za-z_]\w*', expr_eval):
				raise RuntimeError(f"Invalid script print expression: {expr!r}")
			# Keep runtime print mirroring non-fatal for dynamic/unavailable symbols.
			return expr_eval
	def _replace_runtime_expr_placeholders (_text):
		src = str(_text)
		src_lower = src.lower()
		out = []
		i = 0
		while True:
			start = src_lower.find('<expr:', i)
			if start < 0:
				out.append(src[i:])
				break
			out.append(src[i:start])
			j = start + len('<expr:')
			k = j
			paren_depth = 0
			bracket_depth = 0
			brace_depth = 0
			in_quote = None
			escape = False
			close_idx = -1
			while k < len(src):
				ch = src[k]
				if in_quote is not None:
					if escape:
						escape = False
					elif ch == '\\':
						escape = True
					elif ch == in_quote:
						in_quote = None
				else:
					if ch == "'" or ch == '"':
						in_quote = ch
					elif ch == '(':
						paren_depth += 1
					elif ch == ')' and paren_depth > 0:
						paren_depth -= 1
					elif ch == '[':
						bracket_depth += 1
					elif ch == ']' and bracket_depth > 0:
						bracket_depth -= 1
					elif ch == '{':
						brace_depth += 1
					elif ch == '}' and brace_depth > 0:
						brace_depth -= 1
					elif ch == '>' and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
						close_idx = k
						break
				k += 1
			if close_idx < 0:
				# Leave unmatched placeholder text intact for strict-mode error handling.
				out.append(src[start:])
				break
			expr = src[j:close_idx].strip()
			out.append(_eval_expr_text(expr))
			i = close_idx + 1
		return ''.join(out)
	def _replace_simple_runtime_expr_placeholders (_text):
		return re.sub(
			r'(?i)<expr:\s*([^>]*)\s*>',
			(lambda m: _eval_expr_text(m.group(1))),
			str(_text),
		)
	def _normalize_runtime_print_text (_text):
		txt = str(_text)
		src = txt.strip()
		if src == '':
			return txt
		def _coerce_numeric_like (_val):
			if isinstance(_val, list):
				return [_coerce_numeric_like(v) for v in _val]
			if isinstance(_val, tuple):
				return tuple(_coerce_numeric_like(v) for v in _val)
			if isinstance(_val, dict):
				return {k : _coerce_numeric_like(v) for k, v in _val.items()}
			if isinstance(_val, str):
				num = _val.strip()
				if re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', num):
					try:
						if re.fullmatch(r'[+-]?\d+', num):
							return int(num)
						return float(num)
					except Exception:
						return _val
			return _val
		try:
			val = ast.literal_eval(src)
		except Exception:
			return txt
		val = _coerce_numeric_like(val)
		if isinstance(val, str):
			return val
		return str(val)
	_prev = None
	while text != _prev:
		_prev = text
		text = _replace_runtime_expr_placeholders(text)
	# Fallback for any residual simple placeholders (e.g. quoted '<expr:...>').
	if '<expr:' in text.lower():
		text = _replace_simple_runtime_expr_placeholders(text)
	# Last-resort cleanup if any expression wrapper still leaks through.
	if '<expr:' in text.lower():
		if strict:
			raise RuntimeError(f"Invalid script print output placeholder: {text!r}")
		text = re.sub(r'(?i)<expr:\s*', '', text)
		text = text.replace('>', '')
		text = _replace_runtime_ticks_calls(text, ticks)
		text = _replace_runtime_key_calls(text)
	else:
		text = _replace_runtime_ticks_calls(text, ticks)
		text = _replace_runtime_key_calls(text)
	if had_expr_placeholder:
		text = _normalize_runtime_print_text(text)
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

def _start_gba_update_print_mirror (proc, script_runtime, script_label : str = 'gba-py', strict_print_exprs : bool = False, runtime_env = None, mirror_step = None):
	print_calls = list((script_runtime or {}).get('print_calls') or [])
	print_const_env_by_scope = dict((script_runtime or {}).get('print_const_env_by_scope') or {})
	print_expr_env_by_scope = dict((script_runtime or {}).get('print_expr_env_by_scope') or {})
	print_const_env_by_owner = dict((script_runtime or {}).get('print_const_env_by_owner') or {})
	print_expr_env_by_owner = dict((script_runtime or {}).get('print_expr_env_by_owner') or {})
	mirror_scripts_raw = list((script_runtime or {}).get('mirror_scripts') or [])
	mirror_scripts = [s for s in mirror_scripts_raw if isinstance(s, dict) and isinstance(s.get('code'), str)]
	mirror_init_scripts = [s for s in mirror_scripts if bool(s.get('is_init'))]
	mirror_update_scripts = [s for s in mirror_scripts if not bool(s.get('is_init'))]
	realtime_print_pairs = set()
	for script_info in mirror_scripts:
		realtime_print_pairs.add((
			bool(script_info.get('is_init')),
			str(script_info.get('owner_name') or '__world__'),
		))
	_compiled_script_cache = {}
	init_calls = [p for p in print_calls if p.get('is_init')]
	update_calls = [p for p in print_calls if not p.get('is_init')]
	# Mirror-executed scripts now print in real time. Keep replay only for any
	# owner/phase pair that does not have executable mirror code.
	init_calls = [
		p for p in init_calls
		if (bool(p.get('is_init')), str(p.get('owner_name') or '__world__')) not in realtime_print_pairs
	]
	update_calls = [
		p for p in update_calls
		if (bool(p.get('is_init')), str(p.get('owner_name') or '__world__')) not in realtime_print_pairs
	]
	if not init_calls and not update_calls and not mirror_init_scripts and not mirror_update_scripts:
		return
	runtime_env = runtime_env if isinstance(runtime_env, dict) else {}
	def _runner():
		frame = 0
		init_printed = False
		mirror_logged_errors = set()
		class _ProtectedMirrorLocals:
			"""Mapping view that blocks non-callable writes to protected callables."""
			__slots__ = ('_store', '_protected_callable_keys')
			def __init__ (self, _store, _protected = None):
				self._store = _store if isinstance(_store, dict) else {}
				self._protected_callable_keys = set(_protected or [])
			def __getitem__ (self, _k):
				return self._store[_k]
			def __setitem__ (self, _k, _v):
				try:
					if isinstance(_k, str) and _k in self._protected_callable_keys:
						_prev = self._store.get(_k, None)
						if (callable(_prev) or (_prev is None)) and (not callable(_v)):
							return
				except Exception:
					pass
				self._store[_k] = _v
			def __delitem__ (self, _k):
				if isinstance(_k, str) and _k in self._protected_callable_keys:
					return
				del self._store[_k]
			def __contains__ (self, _k):
				return _k in self._store
			def get (self, _k, _default = None):
				return self._store.get(_k, _default)
			def keys (self):
				return self._store.keys()
		def _log_mirror_script_error (kind, owner, scope_key, frame_val, err, code_txt = '', source_code = '', source_line_offset = 0, is_non_local : bool = False, env_snapshot = None):
			try:
				err_text = f'{type(err).__name__}: {err}'
			except Exception:
				err_text = str(err)
			try:
				_frame_key = int(frame_val) if frame_val is not None else -1
			except Exception:
				_frame_key = -1
			key = (str(kind), str(owner), str(scope_key), str(err_text), _frame_key)
			if key in mirror_logged_errors:
				return
			mirror_logged_errors.add(key)
			phase = 'update' if str(kind) == 'exec' else str(kind)
			script_name = str(scope_key)
			try:
				parsed_scope = ast.literal_eval(scope_key) if isinstance(scope_key, str) else scope_key
			except Exception:
				parsed_scope = None
			if isinstance(parsed_scope, (list, tuple)) and len(parsed_scope) >= 3:
				script_name = str(parsed_scope[2])
			owner_pref = str(owner) + '_'
			if script_name.startswith(owner_pref):
				script_name = script_name[len(owner_pref) :]
			line_no = None
			display_line_no = None
			func_name = None
			tb = getattr(err, '__traceback__', None)
			while tb is not None:
				try:
					filename = str(tb.tb_frame.f_code.co_filename)
				except Exception:
					filename = ''
				if filename.startswith('<mirror:'):
					line_no = int(tb.tb_lineno)
					try:
						co_name = str(tb.tb_frame.f_code.co_name)
					except Exception:
						co_name = ''
					if co_name and co_name != '<module>':
						func_name = co_name
				tb = tb.tb_next
			try:
				off = int(source_line_offset or 0)
			except Exception:
				off = 0
			if line_no is not None:
				display_line_no = max(1, line_no - off)
			src_line = ''
			caret_line = ''
			code_lines = []
			try:
				code_lines = str(code_txt).splitlines()
			except Exception:
				code_lines = []
			transformed_line = ''
			try:
				if line_no is not None and 1 <= line_no <= len(code_lines):
					transformed_line = code_lines[line_no - 1]
			except Exception:
				transformed_line = ''
			try:
				if str(source_code).strip() != '':
					lines = str(source_code).splitlines()
					if display_line_no is not None and 1 <= display_line_no <= len(lines):
						src_line = lines[display_line_no - 1]
					# Align to authored line by matching transformed failing line nearby.
					if transformed_line != '' and src_line.strip() != transformed_line.strip() and display_line_no is not None:
						for delta in (1, -1, 2, -2, 3, -3):
							cand = display_line_no + delta
							if 1 <= cand <= len(lines) and lines[cand - 1].strip() == transformed_line.strip():
								display_line_no = cand
								src_line = lines[cand - 1]
								break
				if src_line == '':
					if line_no is not None and 1 <= line_no <= len(code_lines):
						src_line = code_lines[line_no - 1]
			except Exception:
				src_line = ''
			if src_line:
				caret_idx = -1
				caret_width = 1
				try:
					err_kind = str(type(err).__name__)
				except Exception:
					err_kind = ''
				try:
					err_msg = str(err)
				except Exception:
					err_msg = ''
				try:
					# Prefer precise offsets if the exception provides one (for parse/syntax errors).
					if hasattr(err, 'offset') and getattr(err, 'offset', None) is not None:
						caret_idx = max(0, int(getattr(err, 'offset', 1)) - 1)
						caret_width = 1
				except Exception:
					pass
				if caret_idx < 0:
					attr_match = None
					if err_kind == 'AttributeError':
						try:
							attr_match = re.search(r"has no attribute '([^']+)'", err_msg)
						except Exception:
							attr_match = None
					if attr_match is not None:
						attr_name = str(attr_match.group(1))
						try:
							obj_attr = re.search(r'\b([A-Za-z_]\w*)\.' + re.escape(attr_name) + r'\b', src_line)
						except Exception:
							obj_attr = None
						if obj_attr is not None:
							caret_idx = int(obj_attr.start())
							caret_width = max(1, int(obj_attr.end() - obj_attr.start()))
						else:
							caret_idx = src_line.find(attr_name)
							if caret_idx >= 0:
								caret_width = max(1, len(attr_name))
				if caret_idx < 0:
					cast_idx = src_line.find('cast_shape')
					if cast_idx >= 0:
						caret_idx = cast_idx
						caret_width = len('cast_shape')
				if caret_idx < 0:
					caret_idx = max(0, len(src_line) - len(src_line.lstrip(' ')))
				caret_line = (' ' * max(0, int(caret_idx))) + ('^' * max(1, int(caret_width)))
			try:
				line_label = display_line_no if display_line_no is not None else (line_no if line_no is not None else '?')
				if is_non_local:
					header = f'[{script_label}:{phase}:error] Non-local script {script_name}, line {line_label}'
				else:
					header = f'[{script_label}:{phase}:error] Object {owner}, script {script_name}, line {line_label}'
				if func_name and not is_non_local:
					header += f', in {func_name}'
				detail_lines = [header]
				if src_line:
					detail_lines.append(src_line)
				if caret_line:
					detail_lines.append(caret_line)
				detail_lines.append(err_text)
				# Extra diagnostics for persistent callable-shadowing failures.
				try:
					_err_msg = str(err)
				except Exception:
					_err_msg = ''
				if isinstance(err, TypeError) and ('object is not callable' in _err_msg):
					try:
						_env = env_snapshot if isinstance(env_snapshot, dict) else {}
					except Exception:
						_env = {}
					try:
						_h = _env.get('__js13k_helpers__', None)
					except Exception:
						_h = None
					def _type_name (_v):
						try:
							return type(_v).__name__
						except Exception:
							return '<unknown>'
					try:
						_helpers_pos = getattr(_h, 'get_object_position', None) if _h is not None else None
					except Exception:
						_helpers_pos = None
					detail_lines.append(
						'[gbc-py:debug] callable-types '
						+ 'print=' + _type_name(_env.get('print', None))
						+ ', _js13k_print=' + _type_name(_env.get('_js13k_print', None))
						+ ', _js13k_call_print=' + _type_name(_env.get('_js13k_call_print', None))
						+ ', get_object_position=' + _type_name(_env.get('get_object_position', None))
						+ ', _js13k_internal_get_object_position=' + _type_name(_env.get('_js13k_internal_get_object_position', None))
						+ ', _js13k_call_get_object_position=' + _type_name(_env.get('_js13k_call_get_object_position', None))
						+ ', __js13k_helpers__=' + _type_name(_h)
						+ ', __js13k_helpers__.get_object_position=' + _type_name(_helpers_pos)
					)
				for _line in detail_lines:
					print(_line)
			except Exception:
				pass
		per_script_locals = __import__('builtins').globals().get('scriptLocals', {})
		if not isinstance(per_script_locals, dict):
			per_script_locals = {}
		mirror_script_locals = {}
		mirror_owner_attrs_by_scope = {}
		mirror_owner_attrs_by_owner = {}
		for _mirror_info in mirror_scripts:
			if not isinstance(_mirror_info, dict):
				continue
			_owner_attrs = _mirror_info.get('owner_attributes', {})
			if not isinstance(_owner_attrs, dict) or _owner_attrs == {}:
				continue
			_scope_key = _mirror_info.get('scope_key')
			if _scope_key is not None:
				mirror_owner_attrs_by_scope[_scope_key] = dict(_owner_attrs)
			_owner_name = str(_mirror_info.get('owner_name') or '__world__')
			_owner_bucket = mirror_owner_attrs_by_owner.setdefault(_owner_name, {})
			for _attr_name, _attr_value in _owner_attrs.items():
				if isinstance(_attr_name, str) and _attr_name not in _owner_bucket:
					_owner_bucket[_attr_name] = _attr_value
		def _owner_scopes (owner):
			out = {}
			owner_scope = per_script_locals.get(owner, {})
			if isinstance(owner_scope, dict):
				# New layout: scriptLocals[owner][scriptKey] = locals dict.
				if any(isinstance(v, dict) for v in owner_scope.values()):
					for k, v in owner_scope.items():
						if isinstance(v, dict):
							out[k] = v
				# Legacy layout: scriptLocals[owner] = locals dict.
				else:
					out['__legacy__'] = owner_scope
			mirror_scope = mirror_script_locals.get(owner, {})
			if isinstance(mirror_scope, dict):
				for k, v in mirror_scope.items():
					if isinstance(v, dict):
						out[k] = v
			return out
		def _trace_mirror_this_binding (_tag, _owner, _scope_key, _frame, _this_obj, _rb_ids, _rb_named):
			try:
				def _sample_keys (_src):
					try:
						if isinstance(_src, dict):
							keys = [str(k) for k in list(_src.keys())]
						elif hasattr(_src, 'keys'):
							keys = [str(k) for k in list(_src.keys())]
						else:
							keys = []
					except Exception:
						keys = []
					keys = sorted(keys)
					if len(keys) > 8:
						keys = keys[:8] + ['...']
					return '[' + ', '.join(keys) + ']'
				try:
					this_id = str(getattr(_this_obj, 'id', _owner))
				except Exception:
					this_id = str(_owner)
				_append_gbc_trace_lines([
					'[gbc-trace] MirrorThisBind'
					+ f':tag={_tag}'
					+ f',owner={_owner}'
					+ f',scope={_scope_key}'
					+ f',frame={_frame}'
					+ f',this.id={this_id}'
					+ f',this.rb={repr(getattr(_this_obj, "rb", None))}'
					+ f',rb_ids_lookup={repr(_resolve_script_lookup(_rb_ids, this_id))}'
					+ f',rb_named_lookup={repr(_resolve_script_lookup(_rb_named, this_id))}'
					+ f',rb_ids_keys={_sample_keys(_rb_ids)}'
					+ f',rb_named_keys={_sample_keys(_rb_named)}'
				])
			except Exception:
				pass
		def _eval_env_for_owner(owner, frame = None, scope_key = None):
			env = {}
			# Runtime scripts share globals; mirror eval should expose world-scope
			# bindings (for example global gbc-py vars) to local owner scripts.
			if owner != '__world__':
				world_scopes = _owner_scopes('__world__')
				for world_scope in world_scopes.values():
					if isinstance(world_scope, dict):
						env.update(world_scope)
			owner_scopes = _owner_scopes(owner)
			if scope_key is not None:
				scope = owner_scopes.get(scope_key)
				if isinstance(scope, dict):
					env.update(scope)
			if not env:
				# Fallback for cases where scope key is absent (legacy runtime/export path).
				for scope in owner_scopes.values():
					if isinstance(scope, dict):
						env.update(scope)
						break
			if runtime_env:
				# Mirror/runtime physics bindings must win over per-script locals.
				for k in ('sim', 'physics', 'rigidBodies', 'rigidBodiesIds', 'colliders', 'collidersIds'):
					if k in runtime_env:
						env[k] = runtime_env[k]
				for k, v in runtime_env.items():
					if k not in env:
						env[k] = v
			def _mirror_lookup_handle (_name, *sources):
				try:
					key = str(_name)
				except Exception:
					key = ''
				candidates = [key]
				if isinstance(key, str) and key != '':
					if key.startswith('_'):
						candidates.append(key[1:])
					else:
						candidates.append('_' + key)
					if not key.endswith(':0'):
						candidates.append(key + ':0')
						if key.startswith('_'):
							candidates.append(key[1:] + ':0')
						else:
							candidates.append('_' + key + ':0')
					if key.startswith('__gbc_spawn_'):
						suffix = key[len('__gbc_spawn_'):]
						phys = '__gbc_spawnphys_' + suffix
						candidates.extend([phys, '_' + phys, phys + ':0', '_' + phys + ':0'])
					elif key.startswith('__gbc_spawnphys_'):
						suffix = key[len('__gbc_spawnphys_'):]
						draw = '__gbc_spawn_' + suffix
						candidates.extend([draw, '_' + draw, draw + ':0', '_' + draw + ':0'])
				for src in list(sources or []):
					src_dict = src if isinstance(src, dict) else {}
					if not isinstance(src_dict, dict):
						try:
							if hasattr(src, 'items'):
								src_dict = dict(src.items())
						except Exception:
							src_dict = {}
					for cand in candidates:
						try:
							v = src_dict.get(cand, None)
						except Exception:
							v = None
						if v is not None:
							return v
					# Fuzzy fallback for generated runtime keys (for example
					# __gbc_spawnphys_* proxies looked up by source owner name).
					try:
						v = _resolve_script_lookup(src_dict, key)
					except Exception:
						v = None
					if v is not None:
						return v
				return None
			def _mirror_get_rigidbody (_name):
				return _mirror_lookup_handle(_name, env.get('rigidBodiesIds', {}), env.get('rigidBodies', {}))
			def _mirror_get_collider (_name):
				return _mirror_lookup_handle(_name, env.get('collidersIds', {}), env.get('colliders', {}))
			def _mirror_get_object_position (_name):
				def _nonzero_or_none (_p):
					try:
						if isinstance(_p, (list, tuple)) and len(_p) >= 2:
							_x = float(_p[0]); _y = float(_p[1])
							if (abs(_x) + abs(_y)) > 1e-6:
								return [_x, _y]
					except Exception:
						pass
					return None
				_obs_pos_fn = globals().get('_runtime_obs_position_from_sources', None)
				_obs_pos = _obs_pos_fn(_name, env.get('objects', {}), env.get('obs', {}), globals().get('obs', {}), globals().get('objects', {})) if callable(_obs_pos_fn) else None
				if _obs_pos is not None:
					return _obs_pos
				_rb = _mirror_get_rigidbody(_name)
				if _rb is not None:
					try:
						_pos = _normalize_gbc_script_position(env.get('sim').get_rigid_body_position(_rb))
						return _prefer_static_pos_when_dynamic_zero(_name, _pos)
					except Exception:
						pass
				_col = _mirror_get_collider(_name)
				if _col is not None:
					try:
						_pos = _normalize_gbc_script_position(env.get('sim').get_collider_position(_col))
						return _prefer_static_pos_when_dynamic_zero(_name, _pos)
					except Exception:
						pass
				_spawn_pos = _mirror_lookup_handle(_name, __import__('builtins').globals().get('_gbc_spawn_owner_pos_overrides', {}))
				if isinstance(_spawn_pos, (list, tuple)) and len(_spawn_pos) >= 2:
					try:
						_x = float(_spawn_pos[0]); _y = float(_spawn_pos[1])
						if (abs(_x) + abs(_y)) > 1e-6:
							return [_x, _y]
					except Exception:
						pass
				_fn = __import__('builtins').globals().get('get_object_position')
				if callable(_fn):
					try:
						_out = _fn(_name)
						_nz = _nonzero_or_none(_out)
						if _nz is not None:
							return _nz
					except Exception:
						pass
				try:
					_obs = env.get('obs', env.get('objects', globals().get('obs', globals().get('objects', {}))))
					if isinstance(_obs, dict):
						_entry = _resolve_script_lookup(_obs, str(_name))
						if isinstance(_entry, dict):
							_obj_pos = _entry.get('pos', _entry.get('position', None))
							if isinstance(_obj_pos, (list, tuple)) and len(_obj_pos) >= 2:
								_nz = _nonzero_or_none(_obj_pos)
								if _nz is not None:
									return _nz
				except Exception:
					pass
				try:
					_static = _resolve_static_owner_camera_position(str(_name))
					if isinstance(_static, (list, tuple)) and len(_static) >= 2:
						_nz = _nonzero_or_none(_static)
						if _nz is not None:
							return _nz
				except Exception:
					pass
				return [0.0, 0.0]
			def _mirror_get_object_rotation (_name):
				_fn = __import__('builtins').globals().get('get_object_rotation')
				if callable(_fn):
					return _fn(_name)
				_rb = _mirror_get_rigidbody(_name)
				if _rb is not None:
					try:
						return env.get('sim').get_rigid_body_rotation(_rb)
					except Exception:
						pass
				_col = _mirror_get_collider(_name)
				if _col is not None:
					try:
						return env.get('sim').get_collider_rotation(_col)
					except Exception:
						pass
				return 0.0
			# Keep helper bindings callable even when per-script locals persist.
			env['get_rigidbody'] = _mirror_get_rigidbody
			env['get_collider'] = _mirror_get_collider
			env['get_object_position'] = _mirror_get_object_position
			env['get_object_rotation'] = _mirror_get_object_rotation
			env['gbc_get_rigidbody'] = _mirror_get_rigidbody
			env['gbc_get_collider'] = _mirror_get_collider
			env['gbc_get_object_position'] = _mirror_get_object_position
			env['gbc_get_object_rotation'] = _mirror_get_object_rotation
			env['_js13k_internal_get_object_position'] = _mirror_get_object_position
			env['_js13k_internal_get_object_rotation'] = _mirror_get_object_rotation
			env['_js13k_pos_resolver'] = _mirror_get_object_position
			env['_js13k_rot_resolver'] = _mirror_get_object_rotation
			try:
				class _Js13kMirrorHelpers:
					__slots__ = ('_pos_fn', '_rot_fn')
					def __init__ (self, _p, _r):
						object.__setattr__(self, '_pos_fn', _p)
						object.__setattr__(self, '_rot_fn', _r)
					def __setattr__ (self, _name, _value):
						if _name in ('get_object_position', 'get_object_rotation', '_pos_fn', '_rot_fn'):
							return
						object.__setattr__(self, _name, _value)
					def _trace_pos (self, _name, _source, _value):
						try:
							_g = globals()
							_seen = _g.get('_js13k_helper_pos_trace_seen', None)
							if not isinstance(_seen, set):
								_seen = set()
								_g['_js13k_helper_pos_trace_seen'] = _seen
							_sig = ('mirror', str(_name), str(_source), repr(_value))
							if _sig in _seen:
								return
							_seen.add(_sig)
							_trace = _g.get('_append_gbc_trace_lines', None)
							if callable(_trace):
								_trace([
									'[gbc-trace] HelperGetPos'
									+ ':scope=mirror'
									+ ',name=' + repr(str(_name))
									+ ',source=' + str(_source)
									+ ',out=' + repr(_value)
								])
						except Exception:
							pass
					def get_object_position (self, _name):
						try:
							_fn = globals().get('_runtime_obs_position_from_sources', None)
							_p = _fn(
								_name,
								env.get('objects', {}),
								env.get('obs', {}),
								globals().get('objects', {}),
								globals().get('obs', {}),
							) if callable(_fn) else None
							if _p is not None:
								_out = [float(_p[0]), float(_p[1])]
								self._trace_pos(_name, 'obs_sources', _out)
								return _out
						except Exception:
							pass
						_out = self._pos_fn(_name)
						self._trace_pos(_name, 'pos_fn_fallback', _out)
						return _out
					def get_object_rotation (self, _name):
						return self._rot_fn(_name)
				_helpers = _Js13kMirrorHelpers(_mirror_get_object_position, _mirror_get_object_rotation)
				env['__js13k_helpers__'] = _helpers
			except Exception:
				pass
			if owner != '__world__':
				this_obj = env.get('this')
				if this_obj is None:
					this_obj = type('MirrorThis', (), {})()
					this_obj.id = owner
				elif isinstance(this_obj, dict):
					this_dict = dict(this_obj)
					shadow_this = type('MirrorThis', (), {})()
					for attr_name, attr_value in this_dict.items():
						if isinstance(attr_name, str) and attr_name.isidentifier():
							try:
								setattr(shadow_this, attr_name, attr_value)
							except Exception:
								pass
					this_obj = shadow_this
				elif not hasattr(this_obj, 'id'):
					try:
						this_obj.id = owner
					except Exception:
						pass
				if not hasattr(this_obj, 'rb'):
					this_obj.rb = None
				if not hasattr(this_obj, 'col'):
					this_obj.col = None
				try:
					rigid_bodies_ids = env.get('rigidBodiesIds', {})
					rigid_bodies_named = env.get('rigidBodies', {})
					this_obj.rb = _resolve_script_lookup_from_sources(owner, rigid_bodies_ids, rigid_bodies_named)
				except Exception:
					pass
				try:
					colliders_ids = env.get('collidersIds', {})
					colliders_named = env.get('colliders', {})
					this_obj.col = _resolve_script_lookup_from_sources(owner, colliders_ids, colliders_named)
				except Exception:
					pass
				owner_attrs_fallback = dict(mirror_owner_attrs_by_owner.get(str(owner), {}))
				if scope_key is not None:
					scope_owner_attrs = mirror_owner_attrs_by_scope.get(scope_key, {})
					if isinstance(scope_owner_attrs, dict):
						owner_attrs_fallback.update(scope_owner_attrs)
				for attr_name, attr_value in owner_attrs_fallback.items():
					if isinstance(attr_name, str) and attr_name.isidentifier():
						try:
							if not hasattr(this_obj, attr_name):
								setattr(this_obj, attr_name, attr_value)
						except Exception:
							pass
				env['this'] = this_obj
				_trace_mirror_this_binding('eval-env', owner, scope_key, frame, this_obj, rigid_bodies_ids, rigid_bodies_named)
			# Keep mirror-eval aligned with fixed-step handheld runtime semantics.
			if frame is not None:
				dt = 1.0 / 60.0
				env.setdefault('dt', dt)
				env.setdefault('deltaTime', dt)
				env.setdefault('frame', int(frame))
			# Final safety net for persisted mirror locals: re-assert callable
			# helper/print bindings right before script compile/exec.
			try:
				if not callable(env.get('_js13k_print', None)):
					env['_js13k_print'] = _mirror_runtime_print
				if not callable(env.get('_js13k_call_print', None)):
					env['_js13k_call_print'] = _mirror_runtime_print
				if not callable(env.get('print', None)):
					env['print'] = _mirror_runtime_print
				if not callable(env.get('get_object_position', None)):
					env['get_object_position'] = _mirror_get_object_position
				if not callable(env.get('get_object_rotation', None)):
					env['get_object_rotation'] = _mirror_get_object_rotation
				if not callable(env.get('_js13k_call_get_object_position', None)):
					env['_js13k_call_get_object_position'] = _mirror_get_object_position
				if not callable(env.get('_js13k_call_get_object_rotation', None)):
					env['_js13k_call_get_object_rotation'] = _mirror_get_object_rotation
				_h = env.get('__js13k_helpers__', None)
				_pos_ok = callable(getattr(_h, 'get_object_position', None)) if _h is not None else False
				_rot_ok = callable(getattr(_h, 'get_object_rotation', None)) if _h is not None else False
				if not (_pos_ok and _rot_ok):
					class _Js13kMirrorHelpersFallback:
						__slots__ = ()
						def get_object_position (self, _name):
							return _mirror_get_object_position(_name)
						def get_object_rotation (self, _name):
							return _mirror_get_object_rotation(_name)
					env['__js13k_helpers__'] = _Js13kMirrorHelpersFallback()
			except Exception:
				pass
			return env
		def _mirror_ticks_ms (_frame = None):
			if _frame is None:
				return 0
			try:
				return int(round((max(0, int(_frame) - 1) * 1000.0) / 60.0))
			except Exception:
				return 0
		class _MirrorPygameShim:
			K_LEFT = _RUNTIME_KEY_INDEX['LEFT']
			K_RIGHT = _RUNTIME_KEY_INDEX['RIGHT']
			K_DOWN = _RUNTIME_KEY_INDEX['DOWN']
			K_UP = _RUNTIME_KEY_INDEX['UP']
			K_A = _RUNTIME_KEY_INDEX['A']
			K_B = _RUNTIME_KEY_INDEX['B']
			K_START = _RUNTIME_KEY_INDEX['START']
			K_SELECT = _RUNTIME_KEY_INDEX['SELECT']
			class _NoopSurface:
				def __getattr__ (self, _name):
					return (lambda *args, **kwargs: None)
			class _DisplayShim:
				def __init__ (self, surface):
					self._surface = surface
				def get_surface (self):
					return self._surface
			class _DrawShim:
				@staticmethod
				def circle (*_args, **_kwargs):
					return None
			def __init__ (self):
				self._surface = self._NoopSurface()
				self.display = self._DisplayShim(self._surface)
				self.draw = self._DrawShim()
			class time:
				@staticmethod
				def get_ticks ():
					return _mirror_ticks_ms(frame)
			class key:
				@staticmethod
				def get_pressed ():
					return _runtime_key_state_snapshot()
			def __getattr__ (self, _name):
				return (lambda *args, **kwargs: None)
		def _run_mirror_script (script_info, frame = None):
			if not isinstance(script_info, dict):
				return
			owner = script_info.get('owner_name') or '__world__'
			scope_key = script_info.get('scope_key')
			code_txt = str(script_info.get('code', '') or '')
			source_code_txt = str(script_info.get('source_code', code_txt) or '')
			source_line_offset = int(script_info.get('source_line_offset', 0) or 0)
			if code_txt.strip() == '':
				return
			# Defensive runtime rewrite: keep print() callable even if script/env
			# defines a non-callable `print` symbol.
			try:
				code_txt = re.sub(
					r'__js13k_helpers__\s*\.\s*get_object_position\s*\(',
					'_js13k_call_get_object_position(',
					str(code_txt),
				)
				code_txt = re.sub(
					r'__js13k_helpers__\s*\.\s*get_object_rotation\s*\(',
					'_js13k_call_get_object_rotation(',
					str(code_txt),
				)
				code_txt = re.sub(
					r'(?<!\.)\b(?:gbc_get_object_position|get_object_position)\s*\(',
					'_js13k_call_get_object_position(',
					str(code_txt),
				)
				code_txt = re.sub(
					r'(?<!\.)\b(?:gbc_get_object_rotation|get_object_rotation)\s*\(',
					'_js13k_call_get_object_rotation(',
					str(code_txt),
				)
				code_txt = re.sub(r'(?<!\.)\bprint\s*\(', '_js13k_call_print(', str(code_txt))
				code_txt = re.sub(r'(?<!\.)\b_js13k_print\s*\(', '_js13k_call_print(', str(code_txt))
				code_txt = _protect_runtime_binding_assignments(
					str(code_txt),
					{
						'print',
						'_js13k_print',
						'get_object_position',
						'get_object_rotation',
						'gbc_get_object_position',
						'gbc_get_object_rotation',
						'_js13k_internal_get_object_position',
						'_js13k_internal_get_object_rotation',
						'_js13k_call_print',
						'_js13k_call_get_object_position',
						'_js13k_call_get_object_rotation',
					},
				)
			except Exception:
				pass
			cache_key = (scope_key, code_txt)
			code_obj = _compiled_script_cache.get(cache_key)
			if code_obj is None:
				try:
					code_obj = compile(code_txt, f'<mirror:{owner}:{scope_key}>', 'exec')
				except Exception as err:
					_log_mirror_script_error(
						'compile',
						owner,
						scope_key,
						frame,
						err,
						code_txt = code_txt,
						source_code = source_code_txt,
						source_line_offset = source_line_offset,
						is_non_local = bool(script_info.get('is_global')),
						env_snapshot = None,
					)
					try:
						numbered = []
						for ln, src_line in enumerate(str(code_txt).splitlines(), start = 1):
							numbered.append(f'{ln:03d}: {src_line}')
						_append_gbc_trace_lines([
							'[gbc-trace] MirrorScriptSource'
							+ f':label={script_label}'
							+ f',owner={owner}'
							+ f',scope={scope_key}'
							+ f',frame={frame}',
						] + [('[gbc-trace]   ' + row) for row in numbered])
					except Exception:
						pass
					return
				_compiled_script_cache[cache_key] = code_obj
			env = _eval_env_for_owner(owner, frame = frame, scope_key = scope_key)
			protected_callable_keys = {
				'print',
				'_js13k_print',
				'_js13k_call_print',
				'get_object_position',
				'get_object_rotation',
				'_js13k_internal_get_object_position',
				'_js13k_internal_get_object_rotation',
				'_js13k_call_get_object_position',
				'_js13k_call_get_object_rotation',
				'gbc_get_object_position',
				'gbc_get_object_rotation',
			}
			if owner != '__world__':
				try:
					this_obj = env.get('this')
					if this_obj is None:
						this_obj = type('MirrorThis', (), {})()
					if isinstance(this_obj, dict):
						this_dict = dict(this_obj)
						shadow_this = type('MirrorThis', (), {})()
						for attr_name, attr_value in this_dict.items():
							if isinstance(attr_name, str) and attr_name.isidentifier():
								try:
									setattr(shadow_this, attr_name, attr_value)
								except Exception:
									pass
						this_obj = shadow_this
					if not hasattr(this_obj, 'id'):
						this_obj.id = owner
					if not hasattr(this_obj, 'rb'):
						this_obj.rb = None
					if not hasattr(this_obj, 'col'):
						this_obj.col = None
					rigid_bodies_ids = env.get('rigidBodiesIds', {})
					rigid_bodies_named = env.get('rigidBodies', {})
					this_obj.rb = _resolve_script_lookup_from_sources(owner, rigid_bodies_ids, rigid_bodies_named)
					colliders_ids = env.get('collidersIds', {})
					colliders_named = env.get('colliders', {})
					this_obj.col = _resolve_script_lookup_from_sources(owner, colliders_ids, colliders_named)
					owner_attributes = script_info.get('owner_attributes', {})
					if isinstance(owner_attributes, dict):
						for attr_name, attr_value in owner_attributes.items():
							if isinstance(attr_name, str) and attr_name.isidentifier():
								try:
									if not hasattr(this_obj, attr_name):
										setattr(this_obj, attr_name, attr_value)
								except Exception:
									pass
					# Per-script locals can carry a stale/null "this"; force the
					# owner-bound mirror object so this.rb/this.col are always valid.
					env['this'] = this_obj
					_trace_mirror_this_binding('run-script', owner, scope_key, frame, this_obj, rigid_bodies_ids, rigid_bodies_named)
				except Exception:
					pass
			env.setdefault('pygame', _MirrorPygameShim())
			env.setdefault('math', math)
			env.setdefault('random', __import__('random'))
			# Mirror runtime does not materialize prefabs; keep spawn calls non-fatal.
			env.setdefault('spawn_prefab', (lambda *args, **kwargs: None))
			builtins_mod = __import__('builtins')
			env.setdefault('__builtins__', builtins_mod)
			def _format_gbc_cast_debug_text (_txt):
				try:
					match = re.match(r'^\[gbc-cast-debug\]\s+([A-Za-z0-9_]+)(?:\s+(.*))?$', str(_txt or ''))
				except Exception:
					match = None
				if match is None:
					return _txt
				stage = str(match.group(1) or '').strip()
				payload_text = str(match.group(2) or '').strip()
				payload = None
				if payload_text != '':
					try:
						payload = ast.literal_eval(payload_text)
					except Exception:
						payload = None
				if stage == 'cast_shape_recursion_blocked_user':
					shape = '?'
					if isinstance(payload, dict):
						try:
							shape = str(payload.get('shape', '?'))
						except Exception:
							shape = '?'
					return f"[physics] Ignored recursive world.castShape() call from user script to avoid stack overflow (shape={shape})."
				if stage == 'cast_shape_recursion_blocked':
					shape = '?'
					if isinstance(payload, dict):
						try:
							shape = str(payload.get('shape', '?'))
						except Exception:
							shape = '?'
					return f"[physics] Ignored recursive world.castShape() call in runtime wrapper (shape={shape})."
				if payload_text != '':
					return f"[physics] cast debug ({stage}): {payload_text}"
				return f"[physics] cast debug ({stage})"
			def _mirror_runtime_print (*args, sep = ' ', end = '\n', file = None, flush = False):
				# Preserve direct file-directed prints without mirror prefixing.
				if file is not None:
					try:
						return builtins_mod.print(*args, sep = sep, end = end, file = file, flush = flush)
					except Exception:
						return None
				try:
					text = sep.join([str(a) for a in list(args or [])]) + str(end)
				except Exception:
					try:
						text = str(args)
					except Exception:
						text = ''
				text = str(text).rstrip('\n')
				text = _format_gbc_cast_debug_text(text)
				phase = 'init' if bool(script_info.get('is_init')) else 'update'
				prefix = f"[{script_label}:{phase}:runtime] {owner}"
				if phase == 'update':
					prefix += f" [f={int(frame or 0)}]"
				return builtins_mod.print(f"{prefix} {text}", flush = flush)
			# Route script print() through mirror logger for stable runtime-prefixed output.
			env['_js13k_print'] = _mirror_runtime_print
			env['print'] = _mirror_runtime_print
			def _js13k_call_print (*args, sep = ' ', end = '\n', file = None, flush = False):
				for _fn in (env.get('_js13k_print', None), env.get('print', None), builtins_mod.print):
					if callable(_fn):
						try:
							return _fn(*args, sep = sep, end = end, file = file, flush = flush)
						except Exception:
							continue
				return None
			def _js13k_call_get_object_position (_name):
				def _nonzero_or_none (_p):
					try:
						if isinstance(_p, (list, tuple)) and len(_p) >= 2:
							_x = float(_p[0]); _y = float(_p[1])
							if (abs(_x) + abs(_y)) > 1e-6:
								return [_x, -_y]
					except Exception:
						pass
					return None
				for _fn in (
					env.get('_js13k_internal_get_object_position', None),
					env.get('gbc_get_object_position', None),
					env.get('get_object_position', None),
				):
					if callable(_fn):
						try:
							_out = _fn(_name)
							_nz = _nonzero_or_none(_out)
							if _nz is not None:
								return _nz
						except Exception:
							continue
				try:
					_fn = __import__('builtins').globals().get('get_object_position', None)
					if callable(_fn):
						_out = _fn(_name)
						_nz = _nonzero_or_none(_out)
						if _nz is not None:
							return _nz
				except Exception:
					pass
				try:
					_static = _resolve_static_owner_camera_position(str(_name))
					if isinstance(_static, (list, tuple)) and len(_static) >= 2:
						_nz = _nonzero_or_none(_static)
						if _nz is not None:
							return _nz
				except Exception:
					pass
				return [0.0, 0.0]
			def _js13k_call_get_object_rotation (_name):
				for _fn in (
					env.get('_js13k_internal_get_object_rotation', None),
					env.get('gbc_get_object_rotation', None),
					env.get('get_object_rotation', None),
				):
					if callable(_fn):
						try:
							return _fn(_name)
						except Exception:
							continue
				return 0.0
			env['_js13k_call_print'] = _js13k_call_print
			env['_js13k_call_get_object_position'] = _js13k_call_get_object_position
			env['_js13k_call_get_object_rotation'] = _js13k_call_get_object_rotation
			def _sync_owner_attr_locals_into_this ():
				if owner == '__world__':
					return
				owner_attributes = script_info.get('owner_attributes', {})
				if not isinstance(owner_attributes, dict) or owner_attributes == {}:
					return
				this_obj = env.get('this')
				if this_obj is None:
					return
				for attr_name in owner_attributes.keys():
					if not (isinstance(attr_name, str) and attr_name.isidentifier()):
						continue
					if attr_name not in env:
						continue
					try:
						setattr(this_obj, attr_name, env.get(attr_name))
					except Exception:
						pass
			try:
				exec_locals = _ProtectedMirrorLocals(env, protected_callable_keys)
				exec(code_obj, env, exec_locals)
			except Exception as err:
				_sync_owner_attr_locals_into_this()
				_log_mirror_script_error(
					'exec',
					owner,
					scope_key,
					frame,
					err,
					code_txt = code_txt,
					source_code = source_code_txt,
					source_line_offset = source_line_offset,
					is_non_local = bool(script_info.get('is_global')),
					env_snapshot = env,
				)
				# Preserve partial mirror state so strict print placeholder
				# resolution can still read globals initialized before failure.
				owner_store = mirror_script_locals.setdefault(owner, {})
				owner_store[scope_key] = env
				return
			_sync_owner_attr_locals_into_this()
			owner_store = mirror_script_locals.setdefault(owner, {})
			owner_store[scope_key] = env
		def _const_env_for_owner (owner, scope_key = None):
			env = {}
			world_consts = print_const_env_by_owner.get('__world__')
			if isinstance(world_consts, dict):
				env.update(world_consts)
			owner_consts = print_const_env_by_owner.get(owner)
			if isinstance(owner_consts, dict):
				env.update(owner_consts)
			if scope_key is not None:
				scope_consts = print_const_env_by_scope.get(scope_key)
				if isinstance(scope_consts, dict):
					# Per-script bindings must override owner-wide fallbacks.
					env.update(scope_consts)
			return env
		def _expr_env_for_owner (owner, scope_key = None):
			env = {}
			world_expr = print_expr_env_by_owner.get('__world__')
			if isinstance(world_expr, dict):
				env.update(world_expr)
			owner_expr = print_expr_env_by_owner.get(owner)
			if isinstance(owner_expr, dict):
				env.update(owner_expr)
			if scope_key is not None:
				scope_expr = print_expr_env_by_scope.get(scope_key)
				if isinstance(scope_expr, dict):
					# Per-script expressions must override owner-wide fallbacks.
					env.update(scope_expr)
			return env
		def _expand_text_placeholders (text, owner, scope_key = None):
			txt = str(text)
			expr_env = _expr_env_for_owner(owner, scope_key = scope_key)
			def _replace_name_expr (m):
				name = m.group(1)
				if _is_runtime_script_binding_name(name):
					return m.group(0)
				if name not in expr_env:
					return m.group(0)
				val = expr_env.get(name)
				if isinstance(val, str):
					inner = re.fullmatch(r'(?i)<expr:\s*(.*?)\s*>', val.strip())
					if inner:
						expr_text = inner.group(1).strip()
						# Do not inline call-heavy expressions (for example
						# sim.cast_shape(...)) into print placeholders. Let runtime
						# mirror locals resolve the variable value directly.
						if '(' in expr_text:
							return m.group(0)
						return '<expr:' + expr_text + '>'
					return '<expr:' + val + '>'
				if _is_simple_const_value(val):
					return '<expr:' + repr(val) + '>'
				return m.group(0)
			return re.sub(r'(?i)<expr:\s*([A-Za-z_]\w*)\s*>', _replace_name_expr, txt)
		def _should_emit (info, frame):
			cond = info.get('condition')
			if cond is None or cond == '':
				return True
			owner = info.get('owner_name') or '__world__'
			scope_key = info.get('scope_key')
			val = _eval_runtime_expr_value(
				cond,
				frame = frame,
				const_env = _const_env_for_owner(owner, scope_key = scope_key),
				extra_env = _eval_env_for_owner(owner, frame = frame, scope_key = scope_key),
			)
			if val is None:
				return False
			return abs(float(val)) > 1e-9
		try:
			_probe_env = _eval_env_for_owner('__world__')
			_probe_sim = _probe_env.get('sim', _probe_env.get('physics'))
			# When we can execute real script updates in the mirror, disable the
			# legacy interpreted velocity fallback to avoid conflicting control.
			if mirror_update_scripts and hasattr(_probe_sim, 'velocity_script'):
				try:
					_probe_sim.velocity_script = None
				except Exception:
					pass
			print(f"[{script_label}:mirror] sim={type(_probe_sim).__name__}")
		except Exception:
			pass
		while proc.poll() is None:
			frame += 1
			if frame == 1:
				for script_info in mirror_init_scripts:
					_run_mirror_script(script_info, frame = frame)
			if callable(mirror_step) and frame > 1:
				_step_probe_owner = '__world__'
				_step_probe_scope = None
				if update_calls:
					_step_probe_owner = update_calls[0].get('owner_name') or '__world__'
					_step_probe_scope = update_calls[0].get('scope_key')
				_step_probe_sim = None
				_pre_vs = None
				_pre_vy = None
				_pre_y = None
				try:
					_step_probe_env = _eval_env_for_owner(_step_probe_owner, frame = frame, scope_key = _step_probe_scope)
					_step_probe_sim = _step_probe_env.get('sim', _step_probe_env.get('physics'))
					if _step_probe_sim is not None:
						_pre_vs = getattr(_step_probe_sim, 'velocity_script', None)
						_pre_vy = getattr(_step_probe_sim, 'vy', None)
						_pre_y = getattr(_step_probe_sim, 'y', None)
				except Exception:
					pass
				try:
					mirror_step()
				except Exception:
					pass
				try:
					_post_vs = getattr(_step_probe_sim, 'velocity_script', None) if _step_probe_sim is not None else None
					_post_vy = getattr(_step_probe_sim, 'vy', None) if _step_probe_sim is not None else None
					_post_y = getattr(_step_probe_sim, 'y', None) if _step_probe_sim is not None else None
				except Exception:
					pass
			if not init_printed:
				for info in init_calls:
					if not _should_emit(info, frame):
						continue
					owner = info.get('owner_name') or '__world__'
					scope_key = info.get('scope_key')
					text = _expand_text_placeholders(str(info.get('text', '')), owner, scope_key = scope_key).rstrip('\n')
					text = _resolve_runtime_print_exprs(
						text,
						frame = frame,
						const_env = _const_env_for_owner(owner, scope_key = scope_key),
						extra_env = _eval_env_for_owner(owner, frame = frame, scope_key = scope_key),
						strict = strict_print_exprs,
					)
					print(f"[{script_label}:init:runtime] {owner} {text}")
				init_printed = True
			for script_info in mirror_update_scripts:
				_run_mirror_script(script_info, frame = frame)
			for info in update_calls:
				if not _should_emit(info, frame):
					continue
				owner = info.get('owner_name') or '__world__'
				scope_key = info.get('scope_key')
				text = _expand_text_placeholders(str(info.get('text', '')), owner, scope_key = scope_key).rstrip('\n')
				text = _resolve_runtime_print_exprs(
					text,
					frame = frame,
					const_env = _const_env_for_owner(owner, scope_key = scope_key),
					extra_env = _eval_env_for_owner(owner, frame = frame, scope_key = scope_key),
					strict = strict_print_exprs,
				)
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
_GBC_POSITION_BIAS = 32768
_GBC_POSITION_MASK = 0xFFFF
_GBC_PHASE1_VELOCITY_ACCUM_DENOM = 60
_GBC_PHASE1_GRAVITY_ACCUM_DENOM = 60
_GBC_RUNTIME_MAX_OAM = 40
_GBC_RUNTIME_MAX_METASPRITE_TILES = 40
_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES = 8

def _gbc_clamp_signed_byte (v):
	v = int(v)
	if v > 127:
		return 127
	if v < -128:
		return -128
	return v

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

def _gbc_encode_metasprite_rgba (rgba, sprite_w_px : int, sprite_h_px : int, palette4 = None, max_tiles : int = 16, max_palettes : int = 8):
	try:
		import numpy as np
	except ImportError:
		raise RuntimeError('GBC export requires NumPy.')
	if rgba is None:
		return (bytes([0] * 16), 1, 1, [_GBC_DEFAULT_BG_COLORS[: 4]], [0])
	max_tiles = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(max_tiles)))
	max_palettes = max(1, min(8, int(max_palettes)))
	max_span_tiles = max(1, int(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES))
	sprite_w_px = max(8, min(max_span_tiles * 8, int(sprite_w_px)))
	sprite_h_px = max(8, min(max_span_tiles * 8, int(sprite_h_px)))
	tiles_w = max(1, min(max_span_tiles, int(math.ceil(sprite_w_px / 8.0))))
	tiles_h = max(1, min(max_span_tiles, int(math.ceil(sprite_h_px / 8.0))))
	while tiles_w * tiles_h > max_tiles:
		if tiles_w >= tiles_h and tiles_w > 1:
			tiles_w -= 1
		elif tiles_h > 1:
			tiles_h -= 1
		else:
			break
	resized = _gba_nn_resize_rgba(rgba, tiles_w * 8, tiles_h * 8).copy()
	if resized.shape[0] != tiles_h * 8 or resized.shape[1] != tiles_w * 8:
		return (bytes([0] * 16), 1, 1, [_GBC_DEFAULT_BG_COLORS[: 4]], [0])
	default_pal_u8 = np.array(_GBC_DEFAULT_BG_COLORS[: 4], dtype = np.uint8)
	def _normalize_palette4_u8 (pal):
		if pal is None:
			return default_pal_u8.copy()
		try:
			arr = np.array(pal, dtype = np.int16)
		except Exception:
			return default_pal_u8.copy()
		if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] < 4:
			return default_pal_u8.copy()
		arr = np.clip(arr[: 4], 0, 255).astype(np.uint8)
		return arr
	def _build_local_palette4_u8 (opaque_rgb):
		if opaque_rgb is None or opaque_rgb.shape[0] <= 0:
			return default_pal_u8.copy()
		pal4 = _gbc_quantize_palette4(opaque_rgb, lock_extremes = True)
		pal4_u8 = np.array(pal4, dtype = np.uint8)
		if pal4_u8.shape != (4, 3):
			return default_pal_u8.copy()
		pal4_u8[0] = default_pal_u8[0]
		return pal4_u8
	def _palette_err_for_opaque (opaque_rgb, pal4_u8):
		if opaque_rgb is None or opaque_rgb.shape[0] <= 0:
			return 0.0
		_, err = _gbc_quantize_indices_for_palette(opaque_rgb, pal4_u8[1 : 4])
		return float(err)
	def _encode_tile_with_palette (tile_rgba, pal4_u8):
		alpha = np.clip(tile_rgba[:, :, 3], 0.0, 1.0)
		rgb255 = np.clip(tile_rgba[:, :, :3], 0.0, 1.0) * 255.0
		idx = np.zeros((8, 8), dtype = np.uint8)
		for y in range(8):
			for x in range(8):
				if alpha[y, x] <= 0.2:
					idx[y, x] = 0
					continue
				d = pal4_u8[1 : 4].astype(np.float32) - rgb255[y, x]
				err = np.sum(d * d, axis = 1)
				idx[y, x] = int(1 + int(np.argmin(err)))
		return idx
	user_pal = _normalize_palette4_u8(palette4)
	palette4_has_entries = False
	if palette4 is not None:
		try:
			palette4_has_entries = len(palette4) >= 4
		except Exception:
			palette4_has_entries = False
	if palette4_has_entries:
		palette_bank = [user_pal]
	else:
		palette_bank = []
	tile_rgba = []
	tile_opaque_rgb = []
	tile_local_pal = []
	for ty in range(tiles_h):
		for tx in range(tiles_w):
			tile = resized[ty * 8 : (ty + 1) * 8, tx * 8 : (tx + 1) * 8, :]
			tile_rgba.append(tile)
			alpha = np.clip(tile[:, :, 3], 0.0, 1.0)
			rgb = (np.clip(tile[:, :, :3], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
			opaque = rgb[alpha > 0.2]
			tile_opaque_rgb.append(opaque)
			tile_local_pal.append(_build_local_palette4_u8(opaque))
	if not palette_bank:
		palette_bank = [tile_local_pal[0] if tile_local_pal else default_pal_u8.copy()]
	while len(palette_bank) < max_palettes:
		worst_i = -1
		worst_err = -1.0
		for i, opaque in enumerate(tile_opaque_rgb):
			best_err = None
			for pal4 in palette_bank:
				err = _palette_err_for_opaque(opaque, pal4)
				if best_err is None or err < best_err:
					best_err = err
			if best_err is not None and best_err > worst_err:
				worst_err = best_err
				worst_i = i
		if worst_i == -1 or worst_err <= 0.0:
			break
		candidate = tile_local_pal[worst_i]
		if any(np.array_equal(candidate, p) for p in palette_bank):
			break
		palette_bank.append(candidate)
	for _ in range(2):
		assignments = []
		for opaque in tile_opaque_rgb:
			best_idx = 0
			best_err = None
			for pi, pal4 in enumerate(palette_bank):
				err = _palette_err_for_opaque(opaque, pal4)
				if best_err is None or err < best_err:
					best_err = err
					best_idx = pi
			assignments.append(best_idx)
		for pi in range(len(palette_bank)):
			group = [tile_opaque_rgb[i] for i, a in enumerate(assignments) if a == pi and tile_opaque_rgb[i].shape[0] > 0]
			if not group:
				continue
			joined = np.concatenate(group, axis = 0)
			palette_bank[pi] = _build_local_palette4_u8(joined)
	out = bytearray()
	tile_palette_idx = []
	for i, tile in enumerate(tile_rgba):
		opaque = tile_opaque_rgb[i]
		best_idx = 0
		best_err = None
		for pi, pal4 in enumerate(palette_bank):
			err = _palette_err_for_opaque(opaque, pal4)
			if best_err is None or err < best_err:
				best_err = err
				best_idx = pi
		tile_palette_idx.append(int(best_idx))
		idx = _encode_tile_with_palette(tile, palette_bank[best_idx])
		out.extend(_gbc_tile_to_2bpp(idx))
	palette_bank_out = []
	for pal4 in palette_bank:
		palette_bank_out.append([
			(int(pal4[0][0]), int(pal4[0][1]), int(pal4[0][2])),
			(int(pal4[1][0]), int(pal4[1][1]), int(pal4[1][2])),
			(int(pal4[2][0]), int(pal4[2][1]), int(pal4[2][2])),
			(int(pal4[3][0]), int(pal4[3][1]), int(pal4[3][2])),
		])
	return (bytes(out), tiles_w, tiles_h, palette_bank_out, tile_palette_idx)

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

def _gbc_build_dynamic_physics_program (bg_data_addr : int, bg_tile_data_len : int, bg_tilemap_len : int, bg_attrmap_len : int, sprite_data_addr : int, sprite_tile_count : int, sprite_tiles_w : int, sprite_tiles_h : int, init_x : int, init_y : int, bg_palette_bytes : bytes, obj_palette_bytes : bytes, collider_data_addr : int = 0, collider_count : int = 0, grav_step_x : int = 0, grav_step_y : int = 1, init_vx : int = 0, init_vy : int = 0, velocity_script = None, init_scroll_x : int = 0, init_scroll_y : int = 0, scroll_step_x : int = 0, scroll_step_y : int = 0, sprite_tile_palette_idxs = None, collision_w_px : int = None, collision_h_px : int = None, collision_off_x_px : int = 0, collision_off_y_px : int = 0, camera_follow_mode : bool = False, camera_follow_center_x : int = 0, camera_follow_center_y : int = 0):
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
	def emit_subpixel_axis_step(pos_addr, pos_hi_addr, vel_addr, sub_acc_addr, invert_dir = False):
		emit(0xFA, vel_addr & 0xFF, (vel_addr >> 8) & 0xFF)  # ld a,(vel)
		emit(0xB7)  # or a
		jr_vel_zero = jr(0x28)  # jr z, done
		emit(0xCB, 0x7F)  # bit 7,a
		jr_vel_neg = jr(0x20)  # jr nz, neg_path
		# Positive velocity path.
		emit(0x47)  # ld b,a (|vel|)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0x80)  # add a,b
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		pos_loop_addr = len(code)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFE, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # cp vel_accum
		jr_pos_done = jr(0x38)  # jr c, pos_done
		emit(0xD6, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # sub vel_accum
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
		if not invert_dir:
			emit(0x3C)  # inc a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			jr_pos_no_carry = jr(0x20)  # jr nz, pos_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3C)  # inc a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		else:
			emit(0x3D)  # dec a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			emit(0xFE, 0xFF)  # cp $FF (borrow from low byte)
			jr_pos_no_carry = jr(0x20)  # jr nz, pos_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3D)  # dec a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		pos_after_hi_addr = len(code)
		patch_jr(jr_pos_no_carry, pos_after_hi_addr)
		jr_pos_loop = jr(0x18)  # jr pos_loop
		patch_jr(jr_pos_loop, pos_loop_addr)
		pos_done_addr = len(code)
		patch_jr(jr_pos_done, pos_done_addr)
		jr_axis_done = jr(0x18)  # jr axis_done
		# Negative velocity path.
		neg_path_addr = len(code)
		patch_jr(jr_vel_neg, neg_path_addr)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		emit(0x47)  # ld b,a (|vel|)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0x80)  # add a,b
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		neg_loop_addr = len(code)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFE, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # cp vel_accum
		jr_neg_done = jr(0x38)  # jr c, neg_done
		emit(0xD6, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # sub vel_accum
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
		if not invert_dir:
			emit(0x3D)  # dec a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			emit(0xFE, 0xFF)  # cp $FF (borrow from low byte)
			jr_neg_no_borrow = jr(0x20)  # jr nz, neg_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3D)  # dec a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		else:
			emit(0x3C)  # inc a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			jr_neg_no_borrow = jr(0x20)  # jr nz, neg_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3C)  # inc a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		neg_after_hi_addr = len(code)
		patch_jr(jr_neg_no_borrow, neg_after_hi_addr)
		jr_neg_loop = jr(0x18)  # jr neg_loop
		patch_jr(jr_neg_loop, neg_loop_addr)
		neg_done_addr = len(code)
		patch_jr(jr_neg_done, neg_done_addr)
		axis_done_addr = len(code)
		patch_jr(jr_axis_done, axis_done_addr)
		patch_jr(jr_vel_zero, axis_done_addr)
	init_x = max(0, min(65535, int(init_x)))
	init_y = max(0, min(65535, int(init_y)))
	init_vx = int(init_vx)
	init_vy = int(init_vy)
	grav_step_x = int(grav_step_x)
	grav_step_y = int(grav_step_y)
	camera_follow_mode = bool(camera_follow_mode)
	camera_follow_center_x = int(camera_follow_center_x)
	camera_follow_center_y = int(camera_follow_center_y)
	if camera_follow_mode:
		# scroll = center - world_pos ; SCX/SCY receive -scroll each frame.
		init_scroll_x = int(camera_follow_center_x - int(init_x))
		init_scroll_y = int(camera_follow_center_y - int(init_y))
		scroll_step_x = 0
		scroll_step_y = 0
	script_spec = velocity_script if isinstance(velocity_script, dict) else None
	script_base_vx = 0
	script_left_delta = 0
	script_right_delta = 0
	script_jump_y = None
	script_jump_vy_max = None
	if script_spec is not None:
		# Script-space X is opposite phase1 internal X (step uses invert_dir = True).
		script_base_vx = _gbc_clamp_signed_byte(-int(script_spec.get('base_vx', 0)))
		script_left_delta = _gbc_clamp_signed_byte(-int(script_spec.get('left_delta', 0)))
		script_right_delta = _gbc_clamp_signed_byte(-int(script_spec.get('right_delta', 0)))
		if script_spec.get('jump_y', None) is not None:
			script_jump_y = _gbc_clamp_signed_byte(int(script_spec.get('jump_y', 0)))
		if script_spec.get('jump_vy_max', None) is not None:
			script_jump_vy_max = _gbc_clamp_signed_byte(int(script_spec.get('jump_vy_max', 0)))
	collider_count = max(0, min(31, int(collider_count)))
	sprite_tile_count = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(sprite_tile_count)))
	sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(sprite_tiles_w)))
	sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(sprite_tiles_h)))
	if sprite_tiles_w * sprite_tiles_h > sprite_tile_count:
		sprite_tiles_h = max(1, sprite_tile_count // sprite_tiles_w)
	sprite_w_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, sprite_tiles_w * 8))
	sprite_h_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, sprite_tiles_h * 8))
	if collision_w_px is None:
		collision_w_px = int(sprite_w_px)
	if collision_h_px is None:
		collision_h_px = int(sprite_h_px)
	collision_w_px = max(1, min(255, int(collision_w_px)))
	collision_h_px = max(1, min(255, int(collision_h_px)))
	collision_off_x_px = max(-127, min(127, int(collision_off_x_px)))
	collision_off_y_px = max(-127, min(127, int(collision_off_y_px)))
	collision_off_x_u8 = int(collision_off_x_px) & 0xFF
	collision_off_y_u8 = int(collision_off_y_px) & 0xFF
	sprite_tile_palette_idxs = [max(0, min(7, int(v))) for v in list(sprite_tile_palette_idxs or [])]
	oam_left_visible_min = (256 - int(sprite_w_px)) & 0xFF
	oam_top_visible_min = (256 - int(sprite_h_px)) & 0xFF
	offscreen_bottom_y = max(145, min(252, 144 + sprite_tiles_h * 8))
	y_addr = 0xC110
	vy_addr = 0xC111
	x_addr = 0xC112
	vx_addr = 0xC113
	gacc_y_addr = 0xC114
	gacc_x_addr = 0xC115
	dead_addr = 0xC116
	y_hi_addr = 0xC117
	x_hi_addr = 0xC118
	scroll_x_addr = 0xC119
	scroll_y_addr = 0xC11A
	x_subacc_addr = 0xC11B
	y_subacc_addr = 0xC11C
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
	ld_a_imm((init_y >> 8) & 0xFF)
	emit(0xEA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)
	ld_a_imm(init_vy)
	emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
	ld_a_imm(init_x)
	emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	ld_a_imm((init_x >> 8) & 0xFF)
	emit(0xEA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)
	ld_a_imm(init_vx)
	emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
	ld_a_imm(0)
	emit(0xEA, dead_addr & 0xFF, (dead_addr >> 8) & 0xFF)
	ld_a_imm(init_scroll_x)
	emit(0xEA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	ld_a_imm(init_scroll_y)
	emit(0xEA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	ld_a_imm(int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2))
	emit(0xEA, x_subacc_addr & 0xFF, (x_subacc_addr >> 8) & 0xFF)
	ld_a_imm(int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2))
	emit(0xEA, y_subacc_addr & 0xFF, (y_subacc_addr >> 8) & 0xFF)
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			ld_a_imm(init_y + init_scroll_y + row * 8 + 16)
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)  # OAM y
			ld_a_imm(init_x + init_scroll_x + col * 8 + 8)
			emit(0xEA, (base + 1) & 0xFF, ((base + 1) >> 8) & 0xFF)  # OAM x
			ld_a_imm(idx)
			emit(0xEA, (base + 2) & 0xFF, ((base + 2) >> 8) & 0xFF)  # tile idx
			pal_idx = sprite_tile_palette_idxs[idx] if idx < len(sprite_tile_palette_idxs) else 0
			ld_a_imm(0x08 | (pal_idx & 0x07))  # OBJ tile bank 1 + palette
			emit(0xEA, (base + 3) & 0xFF, ((base + 3) >> 8) & 0xFF)
	ld_a_imm((-int(init_scroll_y)) & 0xFF); ldh_imm_a(0x42)
	ld_a_imm((-int(init_scroll_x)) & 0xFF); ldh_imm_a(0x43)
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
	# Runtime display scroll: either scripted scroll profile or follow-camera mode.
	if camera_follow_mode:
		# scroll_x = center_x - x
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		emit(0xC6, int(camera_follow_center_x) & 0xFF)
		emit(0xEA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
		# scroll_y = center_y - y
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		emit(0xC6, int(camera_follow_center_y) & 0xFF)
		emit(0xEA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	else:
		emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
		emit(0xC6, int(scroll_step_x) & 0xFF)
		emit(0xEA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
		emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		ldh_imm_a(0x43)  # SCX = -scroll_x
		emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
		emit(0xC6, int(scroll_step_y) & 0xFF)
		emit(0xEA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
		emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		ldh_imm_a(0x42)  # SCY = -scroll_y
	# Program hardware scroll registers from current scroll vars.
	emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	emit(0x2F)  # cpl
	emit(0x3C)  # inc a
	ldh_imm_a(0x43)  # SCX = -scroll_x
	emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	emit(0x2F)  # cpl
	emit(0x3C)  # inc a
	ldh_imm_a(0x42)  # SCY = -scroll_y
	# Integrate gravity to velocity with a 1/60 accumulator every frame.
	if grav_step_x != 0:
		grav_mag_x = max(1, abs(int(grav_step_x)))
		emit(0xFA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # ld a,(gacc_x)
		emit(0xC6, grav_mag_x & 0xFF)  # add a, grav_mag_x
		emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # store acc
		emit(0xFE, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # cp gravity_accum
		jr_x_no_v = jr(0x38)  # jr c, no_vx_step
		emit(0xD6, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # sub gravity_accum
		emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
		emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(vx)
		if grav_step_x > 0:
			emit(0xFE, 0x7F)  # cp +127
			jr_x_sat = jr(0x28)  # jr z, keep max
			emit(0x3C)  # inc a
			x_sat_done = len(code)
			patch_jr(jr_x_sat, x_sat_done)
		else:
			emit(0xFE, 0x80)  # cp -128
			jr_x_sat = jr(0x28)  # jr z, keep min
			emit(0x3D)  # dec a
			x_sat_done = len(code)
			patch_jr(jr_x_sat, x_sat_done)
		emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # (vx)=a
		x_no_v_addr = len(code)
		patch_jr(jr_x_no_v, x_no_v_addr)
	if grav_step_y != 0:
		grav_mag_y = max(1, abs(int(grav_step_y)))
		emit(0xFA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # ld a,(gacc_y)
		emit(0xC6, grav_mag_y & 0xFF)  # add a, grav_mag_y
		emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # store acc
		emit(0xFE, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # cp gravity_accum
		jr_y_no_v = jr(0x38)  # jr c, no_vy_step
		emit(0xD6, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # sub gravity_accum
		emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
		emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
		if grav_step_y > 0:
			emit(0xFE, 0x7F)  # cp +127
			jr_y_sat = jr(0x28)  # jr z, keep max
			emit(0x3C)  # inc a
			y_sat_done = len(code)
			patch_jr(jr_y_sat, y_sat_done)
		else:
			emit(0xFE, 0x80)  # cp -128
			jr_y_sat = jr(0x28)  # jr z, keep min
			emit(0x3D)  # dec a
			y_sat_done = len(code)
			patch_jr(jr_y_sat, y_sat_done)
		emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # (vy)=a
		y_no_v_addr = len(code)
		patch_jr(jr_y_no_v, y_no_v_addr)
	if script_spec is not None:
		# Apply interpreted gbc-py velocity script each frame.
		ld_a_imm(script_base_vx)
		emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
		if script_right_delta != 0:
			ld_a_imm(0x20)  # P1: direction keys
			ldh_imm_a(0x00)
			emit(0xF0, 0x00)  # ldh a,(rP1)
			emit(0xE6, 0x01)  # and $01 (right; active low)
			emit(0xFE, 0x00)  # cp $00 (pressed)
			jr_right_skip = jr(0x20)  # jr nz, skip_right
			emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
			emit(0xC6, int(script_right_delta) & 0xFF)  # add a,delta (byte-wrapped)
			emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
			right_skip_addr = len(code)
			patch_jr(jr_right_skip, right_skip_addr)
		if script_left_delta != 0:
			ld_a_imm(0x20)  # P1: direction keys
			ldh_imm_a(0x00)
			emit(0xF0, 0x00)  # ldh a,(rP1)
			emit(0xE6, 0x02)  # and $02 (left; active low)
			emit(0xFE, 0x00)  # cp $00 (pressed)
			jr_left_skip = jr(0x20)  # jr nz, skip_left
			emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
			emit(0xC6, int(script_left_delta) & 0xFF)  # add a,delta (byte-wrapped)
			emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
			left_skip_addr = len(code)
			patch_jr(jr_left_skip, left_skip_addr)
		if script_jump_y is not None:
			ld_a_imm(0x10)  # P1: action keys
			ldh_imm_a(0x00)
			emit(0xF0, 0x00)  # ldh a,(rP1)
			emit(0xE6, 0x01)  # and $01 (A; active low)
			emit(0xFE, 0x00)  # cp $00 (pressed)
			jr_not_a = jr(0x20)  # jr nz, no_jump
			jr_jump_guard_skip = None
			if script_jump_vy_max is not None:
				# Script condition `vel[1] <= n` uses script-space Y-up velocity.
				# Internal phase1 stores Y-down velocity, so compare `vy >= -n`.
				jump_internal_min_vy = int(-int(script_jump_vy_max))
				emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
				emit(0xEE, 0x80)  # xor $80 (signed -> unsigned bias)
				emit(0xFE, (int(jump_internal_min_vy) ^ 0x80) & 0xFF)  # cp (min_vy^$80)
				jr_jump_guard_skip = jr(0x38)  # jr c, no_jump (vy < min_vy)
			ld_a_imm((-int(script_jump_y)) & 0xFF)  # script-space up -> internal down
			emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
			ld_a_imm(0x00)
			emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
			no_jump_addr = len(code)
			patch_jr(jr_not_a, no_jump_addr)
			if jr_jump_guard_skip is not None:
				patch_jr(jr_jump_guard_skip, no_jump_addr)
	# Integrate velocity to position every frame with rounded subpixel accumulation.
	emit_subpixel_axis_step(x_addr, x_hi_addr, vx_addr, x_subacc_addr, invert_dir = True)
	emit_subpixel_axis_step(y_addr, y_hi_addr, vy_addr, y_subacc_addr)
	# Runtime collider pass: resolve downward contacts against authored collider AABBs.
	if collider_count > 0:
		emit(0xFA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)  # ld a,(x_hi)
		emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
		jr_skip_collider_world_x = jr(0x20)  # jr nz, no collider step
		emit(0xFA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)  # ld a,(y_hi)
		emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
		jr_skip_collider_world_y = jr(0x20)  # jr nz, no collider step
		# Do not resolve floor contacts once the body has exited below the screen.
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
		emit(0xFE, int(offscreen_bottom_y) & 0xFF)  # cp offscreen_bottom_y
		jr_skip_collider_offscreen_bottom = jr(0x30)  # jr nc, no collider step
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
		emit(0xC6, collision_off_x_u8)  # add a, collision_off_x (signed byte)
		emit(0xC6, collision_w_px & 0xFF)  # add a, collision_w
		emit(0xBA)  # cp d
		jr_collider_next_x_before = jr(0x38)  # jr c, next
		jr_collider_next_x_touch = jr(0x28)  # jr z, next
		emit(0x7A)  # ld a,d
		emit(0x80)  # add a,b ; a = collider_right
		emit(0x47)  # ld b,a
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)  # ld a,(x)
		emit(0xC6, collision_off_x_u8)  # add a, collision_off_x (signed byte)
		emit(0xB8)  # cp b
		jr_collider_next_x_after = jr(0x30)  # jr nc, next
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
		emit(0xC6, collision_off_y_u8)  # add a, collision_off_y (signed byte)
		emit(0xBB)  # cp e
		jr_collider_next_y_below_top = jr(0x30)  # jr nc, next
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
		emit(0xC6, collision_off_y_u8)  # add a, collision_off_y (signed byte)
		emit(0xC6, collision_h_px & 0xFF)  # add a, collision_h
		emit(0xBB)  # cp e
		jr_collider_next_y_above_top = jr(0x38)  # jr c, next
		# Hit: snap sprite on top of collider and clear fall velocity.
		emit(0x7B)  # ld a,e
		emit(0xD6, collision_h_px & 0xFF)  # sub collision_h
		jr_store_hit_y = jr(0x30)  # jr nc, store_y
		emit(0xAF)  # xor a
		store_hit_y_addr = len(code)
		emit(0xD6, collision_off_y_u8)  # sub collision_off_y (signed byte)
		jr_store_hit_y_off = jr(0x30)  # jr nc, store_y
		emit(0xAF)  # xor a
		store_hit_y_final_addr = len(code)
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
		patch_jr(jr_store_hit_y_off, store_hit_y_final_addr)
		collider_skip_addr = len(code)
		patch_jr(jr_skip_collider_world_x, collider_skip_addr)
		patch_jr(jr_skip_collider_world_y, collider_skip_addr)
		patch_jr(jr_skip_collider_offscreen_bottom, collider_skip_addr)
		patch_jr(jr_skip_collider_pass, collider_skip_addr)
		patch_jr(jr_skip_collider_neg, collider_skip_addr)
	# Hide sprite when body is outside the local 0..255 OAM addressable area.
	emit(0xFA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)
	emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
	jr_oam_x_hi_pos = jr(0x28)  # jr z, x_hi_pos
	emit(0xFE, 0x7F)  # cp $7F (negative local x range)
	jr_oam_hide_x_hi = jr(0x20)  # jr nz, hide sprite
	emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	emit(0xFE, oam_left_visible_min)  # cp (x >= -sprite_w in signed-local space)
	jr_oam_hide_left = jr(0x38)  # jr c, hide sprite
	jr_oam_x_ok = jr(0x18)  # jr x_done
	oam_x_hi_pos_addr = len(code)
	patch_jr(jr_oam_x_hi_pos, oam_x_hi_pos_addr)
	emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
	emit(0xFE, 160)  # cp 160
	jr_oam_hide_right = jr(0x30)  # jr nc, hide sprite
	oam_x_done_addr = len(code)
	patch_jr(jr_oam_x_ok, oam_x_done_addr)
	emit(0xFA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)
	emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
	jr_oam_y_hi_pos = jr(0x28)  # jr z, y_hi_pos
	emit(0xFE, 0x7F)  # cp $7F (negative local y range)
	jr_oam_hide_y_hi = jr(0x20)  # jr nz, hide sprite
	emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	emit(0xFE, oam_top_visible_min)  # cp (y >= -sprite_h in signed-local space)
	jr_oam_hide_top = jr(0x38)  # jr c, hide sprite
	jr_oam_y_ok = jr(0x18)  # jr y_done
	oam_y_hi_pos_addr = len(code)
	patch_jr(jr_oam_y_hi_pos, oam_y_hi_pos_addr)
	emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
	emit(0xFE, 144)  # cp 144
	jr_oam_hide_bottom = jr(0x30)  # jr nc, hide sprite
	oam_y_done_addr = len(code)
	patch_jr(jr_oam_y_ok, oam_y_done_addr)
	jr_oam_visible = jr(0x18)  # jr draw sprite
	oam_hide_addr = len(code)
	patch_jr(jr_oam_hide_x_hi, oam_hide_addr)
	patch_jr(jr_oam_hide_left, oam_hide_addr)
	patch_jr(jr_oam_hide_y_hi, oam_hide_addr)
	patch_jr(jr_oam_hide_top, oam_hide_addr)
	patch_jr(jr_oam_hide_right, oam_hide_addr)
	patch_jr(jr_oam_hide_bottom, oam_hide_addr)
	emit(0xAF)  # hide y for every tile
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)
	emit(0xC9)
	oam_visible_addr = len(code)
	patch_jr(jr_oam_visible, oam_visible_addr)
	for row in range(sprite_tiles_h):
		for col in range(sprite_tiles_w):
			idx = row * sprite_tiles_w + col
			if idx >= sprite_tile_count:
				continue
			base = 0xFE00 + idx * 4
			emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
			emit(0x47)  # ld b,a (base y)
			emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
			emit(0x80)  # add a,b
			emit(0xC6, (16 + row * 8) & 0xFF)
			emit(0xEA, base & 0xFF, (base >> 8) & 0xFF)
			emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
			emit(0x47)  # ld b,a (base x)
			emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
			emit(0x80)  # add a,b
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
	patch_call(call_copy_bg_patch, copy_bg_addr)
	patch_call(call_copy_sprite_patch, copy_addr)
	patch_call(call_wait_patch, wait_vblank_addr)
	patch_call(call_update_patch, update_addr)
	patch_call(call_copy_bg_tiles_patch, copy_addr)
	patch_call(call_copy_bg_map_patch, copy_addr)
	patch_call(call_copy_bg_attr_patch, copy_addr)
	return bytes(code)

def _gbc_build_dynamic_physics_rom (canvas_160x144, sprite_tile_bytes : bytes, sprite_tiles_w : int, sprite_tiles_h : int, init_x : int, init_y : int, bg_palette_bank, obj_palette_bank, collider_rects = None, grav_step_x : int = 0, grav_step_y : int = 1, init_vx : int = 0, init_vy : int = 0, velocity_script = None, init_scroll_x : int = 0, init_scroll_y : int = 0, scroll_step_x : int = 0, scroll_step_y : int = 0, sprite_tile_palette_idxs = None, collision_w_px : int = None, collision_h_px : int = None, collision_off_x_px : int = 0, collision_off_y_px : int = 0, camera_follow_mode : bool = False, camera_follow_center_x : int = 0, camera_follow_center_y : int = 0):
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
	obj_palette_bytes = _gbc_palette_bytes_from_palette_bank(obj_palette_bank)
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
	sprite_tile_count = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int((len(sprite_tile_bytes) if sprite_tile_bytes else 0) // 16)))
	collider_count = len(collider_payload) // 4
	probe = _gbc_build_dynamic_physics_program(0, tile_data_len, tilemap_len, attrmap_len, 0, sprite_tile_count, sprite_tiles_w, sprite_tiles_h, init_x, init_y, bg_palette_bytes, obj_palette_bytes, collider_data_addr = 0, collider_count = collider_count, grav_step_x = grav_step_x, grav_step_y = grav_step_y, init_vx = init_vx, init_vy = init_vy, velocity_script = velocity_script, init_scroll_x = init_scroll_x, init_scroll_y = init_scroll_y, scroll_step_x = scroll_step_x, scroll_step_y = scroll_step_y, sprite_tile_palette_idxs = sprite_tile_palette_idxs, collision_w_px = collision_w_px, collision_h_px = collision_h_px, collision_off_x_px = collision_off_x_px, collision_off_y_px = collision_off_y_px, camera_follow_mode = camera_follow_mode, camera_follow_center_x = camera_follow_center_x, camera_follow_center_y = camera_follow_center_y)
	bg_data_addr = code_start + len(probe)
	if bg_data_addr & 0xF:
		bg_data_addr += 0x10 - (bg_data_addr & 0xF)
	sprite_data_addr = bg_data_addr + len(bg_payload)
	collider_data_addr = sprite_data_addr + sprite_tile_count * 16
	code = _gbc_build_dynamic_physics_program(bg_data_addr, tile_data_len, tilemap_len, attrmap_len, sprite_data_addr, sprite_tile_count, sprite_tiles_w, sprite_tiles_h, init_x, init_y, bg_palette_bytes, obj_palette_bytes, collider_data_addr = collider_data_addr, collider_count = collider_count, grav_step_x = grav_step_x, grav_step_y = grav_step_y, init_vx = init_vx, init_vy = init_vy, velocity_script = velocity_script, init_scroll_x = init_scroll_x, init_scroll_y = init_scroll_y, scroll_step_x = scroll_step_x, scroll_step_y = scroll_step_y, sprite_tile_palette_idxs = sprite_tile_palette_idxs, collision_w_px = collision_w_px, collision_h_px = collision_h_px, collision_off_x_px = collision_off_x_px, collision_off_y_px = collision_off_y_px, camera_follow_mode = camera_follow_mode, camera_follow_center_x = camera_follow_center_x, camera_follow_center_y = camera_follow_center_y)
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
	print('GBC export: runtime mode = dynamic physics phase1, runtime colliders =', collider_count)
	return bytes(rom)

def _gbc_build_dynamic_physics_program_multi (bg_data_addr : int, bg_tile_data_len : int, bg_tilemap_len : int, bg_attrmap_len : int, sprite_data_addr : int, sprite_tile_count : int, bodies, bg_palette_bytes : bytes, obj_palette_bytes : bytes, collider_data_addr : int = 0, collider_count : int = 0, init_scroll_x : int = 0, init_scroll_y : int = 0, scroll_step_x : int = 0, scroll_step_y : int = 0):
	code = bytearray()
	if bodies is None:
		bodies = []
	else:
		bodies = list(bodies)
	scroll_x_addr = 0xC0F0
	scroll_y_addr = 0xC0F1
	def emit(*vals):
		code.extend(vals)
	def jr(op):
		emit(op, 0x00)
		return len(code) - 1
	def patch_jr(pos, target):
		disp = int(target) - int(pos + 1)
		if disp < -128 or disp > 127:
			raise RuntimeError('GBC export: dynamic multi-body branch offset out of range.')
		code[pos] = disp & 0xFF
	def patch_abs(pos, target):
		abs_addr = 0x150 + int(target)
		code[pos] = abs_addr & 0xFF
		code[pos + 1] = (abs_addr >> 8) & 0xFF
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
	def emit_subpixel_axis_step(pos_addr, pos_hi_addr, vel_addr, sub_acc_addr, invert_dir = False):
		emit(0xFA, vel_addr & 0xFF, (vel_addr >> 8) & 0xFF)  # ld a,(vel)
		emit(0xB7)  # or a
		jr_vel_zero = jr(0x28)  # jr z, done
		emit(0xCB, 0x7F)  # bit 7,a
		jr_vel_neg = jr(0x20)  # jr nz, neg_path
		emit(0x47)  # ld b,a (|vel|)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0x80)  # add a,b
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		pos_loop_addr = len(code)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFE, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # cp vel_accum
		jr_pos_done = jr(0x38)  # jr c, pos_done
		emit(0xD6, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # sub vel_accum
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
		if not invert_dir:
			emit(0x3C)  # inc a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			jr_pos_no_carry = jr(0x20)  # jr nz, pos_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3C)  # inc a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		else:
			emit(0x3D)  # dec a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			emit(0xFE, 0xFF)  # cp $FF (borrow from low byte)
			jr_pos_no_carry = jr(0x20)  # jr nz, pos_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3D)  # dec a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		pos_after_hi_addr = len(code)
		patch_jr(jr_pos_no_carry, pos_after_hi_addr)
		jr_pos_loop = jr(0x18)  # jr pos_loop
		patch_jr(jr_pos_loop, pos_loop_addr)
		pos_done_addr = len(code)
		patch_jr(jr_pos_done, pos_done_addr)
		jr_axis_done = jr(0x18)  # jr axis_done
		neg_path_addr = len(code)
		patch_jr(jr_vel_neg, neg_path_addr)
		emit(0x2F)  # cpl
		emit(0x3C)  # inc a
		emit(0x47)  # ld b,a (|vel|)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0x80)  # add a,b
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		neg_loop_addr = len(code)
		emit(0xFA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFE, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # cp vel_accum
		jr_neg_done = jr(0x38)  # jr c, neg_done
		emit(0xD6, int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM) & 0xFF)  # sub vel_accum
		emit(0xEA, sub_acc_addr & 0xFF, (sub_acc_addr >> 8) & 0xFF)
		emit(0xFA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
		if not invert_dir:
			emit(0x3D)  # dec a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			emit(0xFE, 0xFF)  # cp $FF (borrow from low byte)
			jr_neg_no_borrow = jr(0x20)  # jr nz, neg_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3D)  # dec a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		else:
			emit(0x3C)  # inc a
			emit(0xEA, pos_addr & 0xFF, (pos_addr >> 8) & 0xFF)
			jr_neg_no_borrow = jr(0x20)  # jr nz, neg_after_hi
			emit(0xFA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
			emit(0x3C)  # inc a
			emit(0xEA, pos_hi_addr & 0xFF, (pos_hi_addr >> 8) & 0xFF)
		neg_after_hi_addr = len(code)
		patch_jr(jr_neg_no_borrow, neg_after_hi_addr)
		jr_neg_loop = jr(0x18)  # jr neg_loop
		patch_jr(jr_neg_loop, neg_loop_addr)
		neg_done_addr = len(code)
		patch_jr(jr_neg_done, neg_done_addr)
		axis_done_addr = len(code)
		patch_jr(jr_axis_done, axis_done_addr)
		patch_jr(jr_vel_zero, axis_done_addr)
	collider_count = max(0, min(31, int(collider_count)))
	emit(0xF3)  # di
	emit(0x31, 0xFE, 0xFF)  # ld sp, $FFFE
	emit(0xAF)  # xor a
	ldh_imm_a(0x40)  # LCDC off
	# CGB BG palette 0..7.
	ld_a_imm(0x80)
	ldh_imm_a(0x68)
	for b in (bg_palette_bytes or bytes()):
		ld_a_imm(b); ldh_imm_a(0x69)
	# CGB OBJ palette 0..7.
	ld_a_imm(0x80)
	ldh_imm_a(0x6A)
	for b in (obj_palette_bytes or bytes()):
		ld_a_imm(b); ldh_imm_a(0x6B)
	# Copy static BG once.
	ld_hl_imm(bg_data_addr)
	emit(0xCD, 0x00, 0x00)  # call copy_bg
	call_copy_bg_patch = len(code) - 2
	# Copy sprite tiles into VRAM bank 1.
	if sprite_tile_count > 0:
		ld_a_imm(0x01)
		ldh_imm_a(0x4F)  # VBK = 1
		ld_hl_imm(sprite_data_addr)
		ld_de_imm(0x8000)
		ld_bc_imm(int(sprite_tile_count) * 16)
		emit(0xCD, 0x00, 0x00)  # call copy_bc
		call_copy_sprite_patch = len(code) - 2
	else:
		call_copy_sprite_patch = None
	emit(0xAF)
	ldh_imm_a(0x4F)  # VBK = 0
	ld_a_imm(init_scroll_x); emit(0xEA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	ld_a_imm(init_scroll_y); emit(0xEA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	# Seed body state and OAM metasprites.
	for body_idx, body in enumerate(bodies):
		base = 0xC100 + body_idx * 8
		y_addr = base + 0
		vy_addr = base + 1
		x_addr = base + 2
		vx_addr = base + 3
		gacc_y_addr = base + 4
		gacc_x_addr = base + 5
		y_hi_addr = base + 6
		x_hi_addr = base + 7
		x_subacc_addr = 0xC200 + body_idx
		y_subacc_addr = 0xC240 + body_idx
		init_x = max(0, min(65535, int(body.get('init_x', 0))))
		init_y = max(0, min(65535, int(body.get('init_y', 0))))
		init_vx = int(body.get('init_vx', 0))
		init_vy = int(body.get('init_vy', 0))
		ld_a_imm(init_y); emit(0xEA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
		ld_a_imm((init_y >> 8) & 0xFF); emit(0xEA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)
		ld_a_imm(init_vy); emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
		ld_a_imm(init_x); emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
		ld_a_imm((init_x >> 8) & 0xFF); emit(0xEA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)
		ld_a_imm(init_vx); emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
		ld_a_imm(0); emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
		ld_a_imm(0); emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
		ld_a_imm(int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2)); emit(0xEA, x_subacc_addr & 0xFF, (x_subacc_addr >> 8) & 0xFF)
		ld_a_imm(int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2)); emit(0xEA, y_subacc_addr & 0xFF, (y_subacc_addr >> 8) & 0xFF)
		sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(body.get('sprite_tiles_w', 1))))
		sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(body.get('sprite_tiles_h', 1))))
		sprite_tile_count_for_body = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(body.get('sprite_tile_count', sprite_tiles_w * sprite_tiles_h))))
		if sprite_tiles_w * sprite_tiles_h > sprite_tile_count_for_body:
			sprite_tiles_h = max(1, sprite_tile_count_for_body // sprite_tiles_w)
		sprite_tile_base = max(0, min(255, int(body.get('sprite_tile_base', 0))))
		oam_base = max(0, min(_GBC_RUNTIME_MAX_OAM - 1, int(body.get('oam_base', 0))))
		sprite_tile_palette_idxs = [max(0, min(7, int(v))) for v in list(body.get('sprite_tile_palette_idxs', []))]
		palette_idx = max(0, min(7, int(body.get('palette_idx', 0))))
		for row in range(sprite_tiles_h):
			for col in range(sprite_tiles_w):
				tile_idx = row * sprite_tiles_w + col
				if tile_idx >= sprite_tile_count_for_body:
					continue
				base_oam = oam_base + tile_idx
				if base_oam >= _GBC_RUNTIME_MAX_OAM:
					continue
				oam_addr = 0xFE00 + base_oam * 4
				ld_a_imm(init_y + init_scroll_y + row * 8 + 16)
				emit(0xEA, oam_addr & 0xFF, (oam_addr >> 8) & 0xFF)  # OAM y
				ld_a_imm(init_x + init_scroll_x + col * 8 + 8)
				emit(0xEA, (oam_addr + 1) & 0xFF, ((oam_addr + 1) >> 8) & 0xFF)  # OAM x
				ld_a_imm(sprite_tile_base + tile_idx)
				emit(0xEA, (oam_addr + 2) & 0xFF, ((oam_addr + 2) >> 8) & 0xFF)  # tile idx
				attr = 0x08 | (int(sprite_tile_palette_idxs[tile_idx]) & 0x07) if tile_idx < len(sprite_tile_palette_idxs) else (0x08 | (palette_idx & 0x07))
				ld_a_imm(attr)
				emit(0xEA, (oam_addr + 3) & 0xFF, ((oam_addr + 3) >> 8) & 0xFF)  # attrs
	ld_a_imm((-int(init_scroll_y)) & 0xFF); ldh_imm_a(0x42)
	ld_a_imm((-int(init_scroll_x)) & 0xFF); ldh_imm_a(0x43)
	ld_a_imm(0x93)  # LCDC on with OBJ
	ldh_imm_a(0x40)
	emit(0xFB)  # ei
	main_loop_addr = len(code)
	emit(0xCD, 0x00, 0x00)  # call wait_vblank
	call_wait_patch = len(code) - 2
	emit(0xCD, 0x00, 0x00)  # call update_bodies
	call_update_patch = len(code) - 2
	# Use absolute jump here because update_bodies can grow large with many
	# runtime bodies and exceed JR displacement limits.
	emit(0xC3, 0x00, 0x00)  # jp main_loop
	jp_loop_patch = len(code) - 2
	update_addr = len(code)
	# Runtime display scroll shared across all bodies.
	emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	emit(0xC6, int(scroll_step_x) & 0xFF)
	emit(0xEA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
	emit(0x2F)  # cpl
	emit(0x3C)  # inc a
	ldh_imm_a(0x43)  # SCX = -scroll_x
	emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	emit(0xC6, int(scroll_step_y) & 0xFF)
	emit(0xEA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
	emit(0x2F)  # cpl
	emit(0x3C)  # inc a
	ldh_imm_a(0x42)  # SCY = -scroll_y
	for body_idx, body in enumerate(bodies):
		base = 0xC100 + body_idx * 8
		y_addr = base + 0
		vy_addr = base + 1
		x_addr = base + 2
		vx_addr = base + 3
		gacc_y_addr = base + 4
		gacc_x_addr = base + 5
		y_hi_addr = base + 6
		x_hi_addr = base + 7
		sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(body.get('sprite_tiles_w', 1))))
		sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(body.get('sprite_tiles_h', 1))))
		sprite_tile_count_for_body = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(body.get('sprite_tile_count', sprite_tiles_w * sprite_tiles_h))))
		if sprite_tiles_w * sprite_tiles_h > sprite_tile_count_for_body:
			sprite_tiles_h = max(1, sprite_tile_count_for_body // sprite_tiles_w)
		sprite_w_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, sprite_tiles_w * 8))
		sprite_h_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, sprite_tiles_h * 8))
		offscreen_bottom_y = max(145, min(252, 144 + int(sprite_h_px)))
		oam_left_visible_min = (256 - int(sprite_w_px)) & 0xFF
		oam_top_visible_min = (256 - int(sprite_h_px)) & 0xFF
		grav_step_x = int(body.get('grav_step_x', 0))
		grav_step_y = int(body.get('grav_step_y', 1))
		script_spec = body.get('velocity_script') if isinstance(body.get('velocity_script'), dict) else None
		script_base_vx = 0
		script_left_delta = 0
		script_right_delta = 0
		script_jump_y = None
		script_jump_vy_max = None
		if script_spec is not None:
			# Script-space X is opposite phase1 internal X (step uses invert_dir = True).
			script_base_vx = _gbc_clamp_signed_byte(-int(script_spec.get('base_vx', 0)))
			script_left_delta = _gbc_clamp_signed_byte(-int(script_spec.get('left_delta', 0)))
			script_right_delta = _gbc_clamp_signed_byte(-int(script_spec.get('right_delta', 0)))
			if script_spec.get('jump_y', None) is not None:
				script_jump_y = _gbc_clamp_signed_byte(int(script_spec.get('jump_y', 0)))
			if script_spec.get('jump_vy_max', None) is not None:
				script_jump_vy_max = _gbc_clamp_signed_byte(int(script_spec.get('jump_vy_max', 0)))
		if grav_step_x != 0:
			grav_mag_x = max(1, abs(int(grav_step_x)))
			emit(0xFA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # ld a,(gacc_x)
			emit(0xC6, grav_mag_x & 0xFF)  # add a, grav_mag_x
			emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)  # store acc
			emit(0xFE, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # cp gravity_accum
			jr_x_no_v = jr(0x38)  # jr c, no_vx_step
			emit(0xD6, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # sub gravity_accum
			emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
			emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(vx)
			if grav_step_x > 0:
				emit(0xFE, 0x7F)  # cp +127
				jr_x_sat = jr(0x28)  # jr z, keep max
				emit(0x3C)  # inc a
				x_sat_done = len(code)
				patch_jr(jr_x_sat, x_sat_done)
			else:
				emit(0xFE, 0x80)  # cp -128
				jr_x_sat = jr(0x28)  # jr z, keep min
				emit(0x3D)  # dec a
				x_sat_done = len(code)
				patch_jr(jr_x_sat, x_sat_done)
			emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # (vx)=a
			x_no_v_addr = len(code)
			patch_jr(jr_x_no_v, x_no_v_addr)
		if script_spec is not None:
			ld_a_imm(script_base_vx)
			emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
			if script_right_delta != 0:
				ld_a_imm(0x20)  # P1: direction keys
				ldh_imm_a(0x00)
				emit(0xF0, 0x00)  # ldh a,(rP1)
				emit(0xE6, 0x01)  # and $01 (right; active low)
				emit(0xFE, 0x00)  # cp $00 (pressed)
				jr_right_skip = jr(0x20)  # jr nz, skip_right
				emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
				emit(0xC6, int(script_right_delta) & 0xFF)  # add a,delta (byte-wrapped)
				emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
				right_skip_addr = len(code)
				patch_jr(jr_right_skip, right_skip_addr)
			if script_left_delta != 0:
				ld_a_imm(0x20)  # P1: direction keys
				ldh_imm_a(0x00)
				emit(0xF0, 0x00)  # ldh a,(rP1)
				emit(0xE6, 0x02)  # and $02 (left; active low)
				emit(0xFE, 0x00)  # cp $00 (pressed)
				jr_left_skip = jr(0x20)  # jr nz, skip_left
				emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
				emit(0xC6, int(script_left_delta) & 0xFF)  # add a,delta (byte-wrapped)
				emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
				left_skip_addr = len(code)
				patch_jr(jr_left_skip, left_skip_addr)
			if script_jump_y is not None:
				ld_a_imm(0x10)  # P1: action keys
				ldh_imm_a(0x00)
				emit(0xF0, 0x00)  # ldh a,(rP1)
				emit(0xE6, 0x01)  # and $01 (A; active low)
				emit(0xFE, 0x00)  # cp $00 (pressed)
				jr_not_a = jr(0x20)  # jr nz, no_jump
				jr_jump_guard_skip = None
				if script_jump_vy_max is not None:
					# Script condition `vel[1] <= n` uses script-space Y-up velocity.
					# Internal phase1 stores Y-down velocity, so compare `vy >= -n`.
					jump_internal_min_vy = int(-int(script_jump_vy_max))
					emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
					emit(0xEE, 0x80)  # xor $80 (signed -> unsigned bias)
					emit(0xFE, (int(jump_internal_min_vy) ^ 0x80) & 0xFF)  # cp (min_vy^$80)
					jr_jump_guard_skip = jr(0x38)  # jr c, no_jump (vy < min_vy)
				ld_a_imm((-int(script_jump_y)) & 0xFF)
				emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
				ld_a_imm(0x00)
				emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
				no_jump_addr = len(code)
				patch_jr(jr_not_a, no_jump_addr)
				if jr_jump_guard_skip is not None:
					patch_jr(jr_jump_guard_skip, no_jump_addr)
		# x += round(vx / 60) using subpixel accumulation.
		emit_subpixel_axis_step(x_addr, x_hi_addr, vx_addr, x_subacc_addr, invert_dir = True)
		if grav_step_y != 0:
			grav_mag_y = max(1, abs(int(grav_step_y)))
			emit(0xFA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # ld a,(gacc_y)
			emit(0xC6, grav_mag_y & 0xFF)  # add a, grav_mag_y
			emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)  # store acc
			emit(0xFE, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # cp gravity_accum
			jr_y_no_v = jr(0x38)  # jr c, no_vy_step
			emit(0xD6, int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM) & 0xFF)  # sub gravity_accum
			emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
			emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
			if grav_step_y > 0:
				emit(0xFE, 0x7F)  # cp +127
				jr_y_sat = jr(0x28)  # jr z, keep max
				emit(0x3C)  # inc a
				y_sat_done = len(code)
				patch_jr(jr_y_sat, y_sat_done)
			else:
				emit(0xFE, 0x80)  # cp -128
				jr_y_sat = jr(0x28)  # jr z, keep min
				emit(0x3D)  # dec a
				y_sat_done = len(code)
				patch_jr(jr_y_sat, y_sat_done)
			emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # (vy)=a
			y_no_v_addr = len(code)
			patch_jr(jr_y_no_v, y_no_v_addr)
		# y += round(vy / 60) using subpixel accumulation.
		emit_subpixel_axis_step(y_addr, y_hi_addr, vy_addr, y_subacc_addr)
		if collider_count > 0:
			# Runtime collider pass: resolve downward contacts against authored collider AABBs.
			emit(0xFA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)  # ld a,(x_hi)
			emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
			jr_skip_collider_world_x = jr(0x20)  # jr nz, no collider step
			emit(0xFA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)  # ld a,(y_hi)
			emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
			jr_skip_collider_world_y = jr(0x20)  # jr nz, no collider step
			# Ignore collider snaps once the body has gone offscreen at the bottom.
			emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
			emit(0xFE, int(offscreen_bottom_y) & 0xFF)  # cp offscreen_bottom_y
			jr_skip_collider_offscreen_bottom = jr(0x30)  # jr nc, no collider step
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
			patch_jr(jr_skip_collider_world_x, collider_skip_addr)
			patch_jr(jr_skip_collider_world_y, collider_skip_addr)
			patch_jr(jr_skip_collider_offscreen_bottom, collider_skip_addr)
			patch_jr(jr_skip_collider_pass, collider_skip_addr)
			patch_jr(jr_skip_collider_neg, collider_skip_addr)
		if len(bodies) > 1:
			# Runtime body-body floor pass: resolve downward contacts against
			# other dynamic body AABBs so spawned dynamic prefabs can land on
			# Player and vice-versa in multi-body mode.
			emit(0xFA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)  # ld a,(x_hi)
			emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
			jr_skip_body_pair_world_x = jr(0x20)  # jr nz, no body-body step
			emit(0xFA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)  # ld a,(y_hi)
			emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
			jr_skip_body_pair_world_y = jr(0x20)  # jr nz, no body-body step
			# Ignore body snaps once the body has gone offscreen at the bottom.
			emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
			emit(0xFE, int(offscreen_bottom_y) & 0xFF)  # cp offscreen_bottom_y
			jr_skip_body_pair_offscreen_bottom = jr(0x30)  # jr nc, no body-body step
			emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(vy)
			emit(0xB7)  # or a
			jr_body_pair_check_vx_zero = jr(0x28)  # jr z, evaluate horizontal velocity gate
			emit(0xCB, 0x7F)  # bit 7,a
			jr_body_pair_check_vx_neg = jr(0x20)  # jr nz, evaluate horizontal velocity gate
			emit(0x18, 0x00)  # jr body_pair_eval (vy > 0)
			jr_body_pair_eval_from_vy = len(code) - 1
			body_pair_check_vx_addr = len(code)
			patch_jr(jr_body_pair_check_vx_zero, body_pair_check_vx_addr)
			patch_jr(jr_body_pair_check_vx_neg, body_pair_check_vx_addr)
			emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(vx)
			emit(0xB7)  # or a
			jr_body_pair_check_vx_nonzero = jr(0x20)  # jr nz, body_pair_eval
			emit(0xC3, 0x00, 0x00)  # jp body_pair_done
			jp_body_pair_skip_patch = len(code) - 2
			body_pair_eval_addr = len(code)
			patch_jr(jr_body_pair_eval_from_vy, body_pair_eval_addr)
			patch_jr(jr_body_pair_check_vx_nonzero, body_pair_eval_addr)
			patch_jr(jr_skip_body_pair_world_x, body_pair_eval_addr)
			patch_jr(jr_skip_body_pair_world_y, body_pair_eval_addr)
			patch_jr(jr_skip_body_pair_offscreen_bottom, body_pair_eval_addr)
			jp_body_pair_done_patches = []
			self_mass_q = max(1, min(255, int(body.get('mass_q', 1))))
			for other_idx, other_body in enumerate(bodies):
				if other_idx == body_idx:
					continue
				other_mass_q = max(1, min(255, int(other_body.get('mass_q', 1))))
				vertical_push_shift = _gbc_pair_transfer_shift(self_mass_q, other_mass_q, damping = 0.5)
				horizontal_push_shift = _gbc_pair_transfer_shift(self_mass_q, other_mass_q, damping = 1.0)
				other_base = 0xC100 + other_idx * 8
				other_y_addr = other_base + 0
				other_vy_addr = other_base + 1
				other_x_addr = other_base + 2
				other_vx_addr = other_base + 3
				other_gacc_y_addr = other_base + 4
				other_gacc_x_addr = other_base + 5
				other_y_hi_addr = other_base + 6
				other_x_hi_addr = other_base + 7
				other_sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(other_body.get('sprite_tiles_w', 1))))
				other_sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(other_body.get('sprite_tiles_h', 1))))
				other_sprite_w_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, other_sprite_tiles_w * 8))
				emit(0xFA, other_x_hi_addr & 0xFF, (other_x_hi_addr >> 8) & 0xFF)  # ld a,(other_x_hi)
				emit(0xFE, 0x80)  # cp $80
				emit(0xC2, 0x00, 0x00)  # jp nz, next pair
				jp_next_pair_other_x_hi = len(code) - 2
				emit(0xFA, other_y_hi_addr & 0xFF, (other_y_hi_addr >> 8) & 0xFF)  # ld a,(other_y_hi)
				emit(0xFE, 0x80)  # cp $80
				emit(0xC2, 0x00, 0x00)  # jp nz, next pair
				jp_next_pair_other_y_hi = len(code) - 2
				emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)  # ld a,(x)
				emit(0xC6, sprite_w_px & 0xFF)  # add a,sprite_w
				emit(0x47)  # ld b,a (self_right)
				emit(0xFA, other_x_addr & 0xFF, (other_x_addr >> 8) & 0xFF)  # ld a,(other_x)
				emit(0xB8)  # cp b (other_x - self_right)
				emit(0xD2, 0x00, 0x00)  # jp nc, next (self_right <= other_x)
				jp_next_pair_x_before = len(code) - 2
				emit(0xFA, other_x_addr & 0xFF, (other_x_addr >> 8) & 0xFF)  # ld a,(other_x)
				emit(0xC6, other_sprite_w_px & 0xFF)  # add a,other_w
				emit(0x47)  # ld b,a (other_right)
				emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)  # ld a,(x)
				emit(0xB8)  # cp b (self_x - other_right)
				emit(0xD2, 0x00, 0x00)  # jp nc, next (self_x >= other_right)
				jp_next_pair_x_after = len(code) - 2
				emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
				emit(0x47)  # ld b,a
				emit(0xFA, other_y_addr & 0xFF, (other_y_addr >> 8) & 0xFF)  # ld a,(other_y)
				emit(0xB8)  # cp b (other_y - self_y)
				emit(0xDA, 0x00, 0x00)  # jp c, next (other_y < self_y)
				jp_next_pair_y_not_above = len(code) - 2
				jr_next_pair_y_touch = jr(0x28)  # jr z, side-contact eval (other_y == self_y)
				emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)  # ld a,(y)
				emit(0xC6, sprite_h_px & 0xFF)  # add a,self_h
				emit(0x47)  # ld b,a (self_bottom)
				emit(0xFA, other_y_addr & 0xFF, (other_y_addr >> 8) & 0xFF)  # ld a,(other_y)
				emit(0xB8)  # cp b (other_y - self_bottom)
				emit(0xD2, 0x00, 0x00)  # jp nc, next (self_bottom <= other_y)
				jp_next_pair_y_above_top = len(code) - 2
				# If penetration is deep, this is likely side contact with slight
				# vertical offset; route to side-resolve instead of top-snap.
				emit(0x57)  # ld d,a (other_y)
				emit(0x78)  # ld a,b (self_bottom)
				emit(0x92)  # sub d (penetration = self_bottom - other_y)
				emit(0xFE, 0x06)  # cp 6px
				emit(0xD2, 0x00, 0x00)  # jp nc, side-contact eval
				jp_pair_deep_overlap_side_patch = len(code) - 2
				# Hit: snap current body on top of other body and clear fall velocity.
				emit(0xFA, other_y_addr & 0xFF, (other_y_addr >> 8) & 0xFF)  # ld a,(other_y)
				emit(0xD6, sprite_h_px & 0xFF)  # sub self_h
				jr_store_pair_hit_y = jr(0x30)  # jr nc, store_y
				emit(0xAF)  # xor a
				store_pair_hit_y_addr = len(code)
				emit(0xEA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
				# Transfer a reduced downward impulse to the impacted body so
				# dynamic-dynamic stacks can push each other (not just Player).
				emit(0xFA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)  # ld a,(self_vy)
				for _ in range(max(0, int(vertical_push_shift))):
					emit(0xCB, 0x3F)  # srl a
				emit(0x47)  # ld b,a (candidate other_vy)
				emit(0xFA, other_vy_addr & 0xFF, (other_vy_addr >> 8) & 0xFF)  # ld a,(other_vy)
				emit(0xCB, 0x7F)  # bit 7,a
				jr_pair_keep_other_vy = jr(0x20)  # jr nz, keep candidate
				emit(0xB8)  # cp b ; keep larger downward speed only
				jr_pair_skip_transfer = jr(0x30)  # jr nc, skip transfer
				pair_keep_other_vy_addr = len(code)
				patch_jr(jr_pair_keep_other_vy, pair_keep_other_vy_addr)
				emit(0x78)  # ld a,b
				emit(0xEA, other_vy_addr & 0xFF, (other_vy_addr >> 8) & 0xFF)
				emit(0xAF)  # xor a
				emit(0xEA, other_gacc_y_addr & 0xFF, (other_gacc_y_addr >> 8) & 0xFF)
				pair_skip_transfer_addr = len(code)
				patch_jr(jr_pair_skip_transfer, pair_skip_transfer_addr)
				emit(0xAF)  # xor a
				emit(0xEA, vy_addr & 0xFF, (vy_addr >> 8) & 0xFF)
				emit(0xEA, gacc_y_addr & 0xFF, (gacc_y_addr >> 8) & 0xFF)
				emit(0xC3, 0x00, 0x00)  # jp body_pair_done
				jp_body_pair_done_patches.append(len(code) - 2)
				side_pair_eval_addr = len(code)
				patch_jr(jr_next_pair_y_touch, side_pair_eval_addr)
				patch_abs(jp_pair_deep_overlap_side_patch, side_pair_eval_addr)
				jp_side_pair_next_if_vx_zero = None
				jr_side_pair_store_right_x = None
				side_pair_store_right_x_addr = None
				if script_spec is None:
					# Avoid reciprocal side-solves from passive bodies; this prevents
					# jitter/teleport artifacts when player pushes dynamic props.
					emit(0xC3, 0x00, 0x00)  # jp next_pair
					jp_side_pair_unscripted_next = len(code) - 2
				else:
					jp_side_pair_unscripted_next = None
					emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(self_vx)
					emit(0xB7)  # or a
					emit(0xCA, 0x00, 0x00)  # jp z, next pair
					jp_side_pair_next_if_vx_zero = len(code) - 2
					emit(0xCB, 0x7F)  # bit 7,a
					# Runtime X uses invert_dir=True; negative vx moves right.
					jr_side_pair_left = jr(0x28)  # jr z, left-moving resolve
					# Right-moving side contact: clamp self to the left side of other.
					emit(0xFA, other_x_addr & 0xFF, (other_x_addr >> 8) & 0xFF)  # ld a,(other_x)
					emit(0xD6, int(sprite_w_px) & 0xFF)  # sub self_w
					jr_side_pair_store_right_x = jr(0x30)  # jr nc, store x
					emit(0xAF)  # xor a
					side_pair_store_right_x_addr = len(code)
					emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
					# Transfer rightward push using mass-scaled self velocity.
					emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(self_vx)
					emit(0x2F)  # cpl
					emit(0x3C)  # inc a (|self_vx|, expected right-moving)
					for _ in range(max(0, int(horizontal_push_shift))):
						emit(0xCB, 0x3F)  # srl a
					emit(0xB7)  # or a
					jr_side_pair_right_impulse_nonzero = jr(0x20)  # jr nz, keep
					emit(0x3C)  # inc a (minimum push 1)
					side_pair_right_impulse_nonzero_addr = len(code)
					patch_jr(jr_side_pair_right_impulse_nonzero, side_pair_right_impulse_nonzero_addr)
					emit(0x2F)  # cpl
					emit(0x3C)  # inc a (back to signed negative)
					emit(0xEA, other_vx_addr & 0xFF, (other_vx_addr >> 8) & 0xFF)
					emit(0xAF)  # xor a
					emit(0xEA, other_gacc_x_addr & 0xFF, (other_gacc_x_addr >> 8) & 0xFF)
					emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
					emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
					emit(0xC3, 0x00, 0x00)  # jp body_pair_done
					jp_body_pair_done_patches.append(len(code) - 2)
					side_pair_left_addr = len(code)
					patch_jr(jr_side_pair_left, side_pair_left_addr)
					# Left-moving side contact: clamp self to the right side of other.
					emit(0xFA, other_x_addr & 0xFF, (other_x_addr >> 8) & 0xFF)
					emit(0xC6, int(other_sprite_w_px) & 0xFF)  # add other_w
					emit(0xEA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
					# Transfer leftward push using mass-scaled self velocity.
					emit(0xFA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)  # ld a,(self_vx)
					for _ in range(max(0, int(horizontal_push_shift))):
						emit(0xCB, 0x3F)  # srl a
					emit(0xB7)  # or a
					jr_side_pair_left_impulse_nonzero = jr(0x20)  # jr nz, keep
					emit(0x3C)  # inc a (minimum push 1)
					side_pair_left_impulse_nonzero_addr = len(code)
					patch_jr(jr_side_pair_left_impulse_nonzero, side_pair_left_impulse_nonzero_addr)
					emit(0xEA, other_vx_addr & 0xFF, (other_vx_addr >> 8) & 0xFF)
					emit(0xAF)  # xor a
					emit(0xEA, other_gacc_x_addr & 0xFF, (other_gacc_x_addr >> 8) & 0xFF)
					emit(0xEA, vx_addr & 0xFF, (vx_addr >> 8) & 0xFF)
					emit(0xEA, gacc_x_addr & 0xFF, (gacc_x_addr >> 8) & 0xFF)
					emit(0xC3, 0x00, 0x00)  # jp body_pair_done
					jp_body_pair_done_patches.append(len(code) - 2)
				next_pair_addr = len(code)
				patch_abs(jp_next_pair_other_x_hi, next_pair_addr)
				patch_abs(jp_next_pair_other_y_hi, next_pair_addr)
				patch_abs(jp_next_pair_x_before, next_pair_addr)
				patch_abs(jp_next_pair_x_after, next_pair_addr)
				patch_abs(jp_next_pair_y_not_above, next_pair_addr)
				patch_abs(jp_next_pair_y_above_top, next_pair_addr)
				patch_jr(jr_store_pair_hit_y, store_pair_hit_y_addr)
				if jp_side_pair_unscripted_next is not None:
					patch_abs(jp_side_pair_unscripted_next, next_pair_addr)
				if jp_side_pair_next_if_vx_zero is not None:
					patch_abs(jp_side_pair_next_if_vx_zero, next_pair_addr)
				if jr_side_pair_store_right_x is not None and side_pair_store_right_x_addr is not None:
					patch_jr(jr_side_pair_store_right_x, side_pair_store_right_x_addr)
			body_pair_done_addr = len(code)
			for patch_pos in jp_body_pair_done_patches:
				patch_abs(patch_pos, body_pair_done_addr)
			patch_abs(jp_body_pair_skip_patch, body_pair_done_addr)
		# Update metasprite OAM from solved body position.
		oam_base = max(0, min(_GBC_RUNTIME_MAX_OAM - 1, int(body.get('oam_base', 0))))
		emit(0xFA, x_hi_addr & 0xFF, (x_hi_addr >> 8) & 0xFF)
		emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
		jr_oam_x_hi_pos = jr(0x28)  # jr z, x_hi_pos
		emit(0xFE, 0x7F)  # cp $7F (negative local x range)
		jr_oam_hide_x_hi = jr(0x20)  # jr nz, hide sprite
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
		emit(0xFE, oam_left_visible_min)  # cp (x >= -sprite_w in signed-local space)
		jr_oam_hide_left = jr(0x38)  # jr c, hide sprite
		jr_oam_x_ok = jr(0x18)  # jr x_done
		oam_x_hi_pos_addr = len(code)
		patch_jr(jr_oam_x_hi_pos, oam_x_hi_pos_addr)
		emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
		emit(0xFE, 160)  # cp 160
		jr_oam_hide_right = jr(0x30)  # jr nc, hide sprite
		oam_x_done_addr = len(code)
		patch_jr(jr_oam_x_ok, oam_x_done_addr)
		emit(0xFA, y_hi_addr & 0xFF, (y_hi_addr >> 8) & 0xFF)
		emit(0xFE, 0x80)  # cp $80 (screen-origin biased hi byte)
		jr_oam_y_hi_pos = jr(0x28)  # jr z, y_hi_pos
		emit(0xFE, 0x7F)  # cp $7F (negative local y range)
		jr_oam_hide_y_hi = jr(0x20)  # jr nz, hide sprite
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
		emit(0xFE, oam_top_visible_min)  # cp (y >= -sprite_h in signed-local space)
		jr_oam_hide_top = jr(0x38)  # jr c, hide sprite
		jr_oam_y_ok = jr(0x18)  # jr y_done
		oam_y_hi_pos_addr = len(code)
		patch_jr(jr_oam_y_hi_pos, oam_y_hi_pos_addr)
		emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
		emit(0xFE, 144)  # cp 144
		jr_oam_hide_bottom = jr(0x30)  # jr nc, hide sprite
		oam_y_done_addr = len(code)
		patch_jr(jr_oam_y_ok, oam_y_done_addr)
		jr_oam_draw = jr(0x18)  # jr draw sprite
		oam_hide_addr = len(code)
		patch_jr(jr_oam_hide_x_hi, oam_hide_addr)
		patch_jr(jr_oam_hide_left, oam_hide_addr)
		patch_jr(jr_oam_hide_y_hi, oam_hide_addr)
		patch_jr(jr_oam_hide_top, oam_hide_addr)
		patch_jr(jr_oam_hide_right, oam_hide_addr)
		patch_jr(jr_oam_hide_bottom, oam_hide_addr)
		emit(0xAF)  # hide y for every tile
		for row in range(sprite_tiles_h):
			for col in range(sprite_tiles_w):
				tile_idx = row * sprite_tiles_w + col
				if tile_idx >= sprite_tile_count_for_body:
					continue
				base_oam = oam_base + tile_idx
				if base_oam >= _GBC_RUNTIME_MAX_OAM:
					continue
				oam_addr = 0xFE00 + base_oam * 4
				emit(0xEA, oam_addr & 0xFF, (oam_addr >> 8) & 0xFF)
		emit(0xC3, 0x00, 0x00)  # jp oam_done
		jp_oam_done = len(code) - 2
		oam_draw_addr = len(code)
		patch_jr(jr_oam_draw, oam_draw_addr)
		for row in range(sprite_tiles_h):
			for col in range(sprite_tiles_w):
				tile_idx = row * sprite_tiles_w + col
				if tile_idx >= sprite_tile_count_for_body:
					continue
				base_oam = oam_base + tile_idx
				if base_oam >= _GBC_RUNTIME_MAX_OAM:
					continue
				oam_addr = 0xFE00 + base_oam * 4
				emit(0xFA, y_addr & 0xFF, (y_addr >> 8) & 0xFF)
				emit(0x47)  # ld b,a (base y)
				emit(0xFA, scroll_y_addr & 0xFF, (scroll_y_addr >> 8) & 0xFF)
				emit(0x80)  # add a,b
				emit(0xC6, (16 + row * 8) & 0xFF)
				emit(0xEA, oam_addr & 0xFF, (oam_addr >> 8) & 0xFF)
				emit(0xFA, x_addr & 0xFF, (x_addr >> 8) & 0xFF)
				emit(0x47)  # ld b,a (base x)
				emit(0xFA, scroll_x_addr & 0xFF, (scroll_x_addr >> 8) & 0xFF)
				emit(0x80)  # add a,b
				emit(0xC6, (8 + col * 8) & 0xFF)
				emit(0xEA, (oam_addr + 1) & 0xFF, ((oam_addr + 1) >> 8) & 0xFF)
		oam_done_addr = len(code)
		patch_abs(jp_oam_done, oam_done_addr)
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
	patch_call(jp_loop_patch, main_loop_addr)
	patch_call(call_copy_bg_patch, copy_bg_addr)
	if call_copy_sprite_patch is not None:
		patch_call(call_copy_sprite_patch, copy_addr)
	patch_call(call_wait_patch, wait_vblank_addr)
	patch_call(call_update_patch, update_addr)
	patch_call(call_copy_bg_tiles_patch, copy_addr)
	patch_call(call_copy_bg_map_patch, copy_addr)
	patch_call(call_copy_bg_attr_patch, copy_addr)
	return bytes(code)

def _gbc_build_dynamic_physics_rom_multi (canvas_160x144, body_specs, bg_palette_bank, collider_rects = None, init_scroll_x : int = 0, init_scroll_y : int = 0, scroll_step_x : int = 0, scroll_step_y : int = 0):
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
	if body_specs is None:
		body_specs = []
	else:
		body_specs = list(body_specs)
	bodies = []
	total_tile_count = 0
	total_oam_count = 0
	palette_bank_obj = []
	def _norm_pal4 (pal4):
		default_pal = _GBC_DEFAULT_BG_COLORS[: 4]
		if pal4 is None:
			return [tuple(c) for c in default_pal]
		try:
			out = []
			for i in range(4):
				c = pal4[i] if i < len(pal4) else default_pal[i]
				out.append((int(c[0]), int(c[1]), int(c[2])))
			return out
		except Exception:
			return [tuple(c) for c in default_pal]
	def _palette_distance (a, b):
		total = 0
		for i in range(4):
			ca = a[i] if i < len(a) else a[-1]
			cb = b[i] if i < len(b) else b[-1]
			total += abs(int(ca[0]) - int(cb[0])) + abs(int(ca[1]) - int(cb[1])) + abs(int(ca[2]) - int(cb[2]))
		return int(total)
	for spec in body_specs:
		tile_bytes_raw = spec.get('sprite_tile_bytes', None)
		tile_bytes = b'' if tile_bytes_raw is None else bytes(tile_bytes_raw)
		tile_count = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(len(tile_bytes) // 16)))
		sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(spec.get('sprite_tiles_w', 1))))
		sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(spec.get('sprite_tiles_h', 1))))
		if sprite_tiles_w * sprite_tiles_h > tile_count:
			sprite_tiles_h = max(1, tile_count // sprite_tiles_w)
		oam_need = max(1, min(_GBC_RUNTIME_MAX_OAM, sprite_tiles_w * sprite_tiles_h))
		if total_tile_count + tile_count > 255:
			print('GBC export: clamping multi-body sprites to fit VRAM tiles at 255 (from', len(body_specs), 'requested bodies).')
			break
		if total_oam_count + oam_need > _GBC_RUNTIME_MAX_OAM:
			print('GBC export: clamping multi-body sprites to fit OAM at 40 entries (from', len(body_specs), 'requested bodies).')
			break
		spec_palette_bank = list(spec.get('palette_bank', []) or [])
		if not spec_palette_bank:
			spec_palette_bank = [spec.get('palette4', _GBC_DEFAULT_BG_COLORS[: 4])]
		spec_palette_bank = [_norm_pal4(p) for p in spec_palette_bank]
		pal_local_to_global = {}
		for local_i, pal4 in enumerate(spec_palette_bank):
			exact_idx = None
			for gi, gp in enumerate(palette_bank_obj):
				if gp == pal4:
					exact_idx = gi
					break
			if exact_idx is not None:
				pal_local_to_global[local_i] = exact_idx
				continue
			if len(palette_bank_obj) < 8:
				palette_bank_obj.append(pal4)
				pal_local_to_global[local_i] = len(palette_bank_obj) - 1
				continue
			best_idx = 0
			best_dist = None
			for gi, gp in enumerate(palette_bank_obj):
				dist = _palette_distance(gp, pal4)
				if best_dist is None or dist < best_dist:
					best_dist = dist
					best_idx = gi
			pal_local_to_global[local_i] = best_idx
		palette_idx = int(pal_local_to_global.get(0, 0))
		spec_tile_palette_idx = [int(v) for v in list(spec.get('tile_palette_idx', []) or [])]
		sprite_tile_palette_idxs = []
		for ti in range(tile_count):
			local_idx = spec_tile_palette_idx[ti] if ti < len(spec_tile_palette_idx) else 0
			sprite_tile_palette_idxs.append(int(pal_local_to_global.get(local_idx, palette_idx)))
		body = {
			'init_x' : int(spec.get('init_x', 0)),
			'init_y' : int(spec.get('init_y', 0)),
			'init_vx' : int(spec.get('init_vx', 0)),
			'init_vy' : int(spec.get('init_vy', 0)),
			'grav_step_x' : int(spec.get('grav_step_x', 0)),
			'grav_step_y' : int(spec.get('grav_step_y', 1)),
			'velocity_script' : spec.get('velocity_script', None),
			'sprite_tile_bytes' : tile_bytes,
			'sprite_tile_count' : tile_count,
			'sprite_tiles_w' : sprite_tiles_w,
			'sprite_tiles_h' : sprite_tiles_h,
			'sprite_tile_base' : total_tile_count,
			'oam_base' : total_oam_count,
			'palette_idx' : palette_idx,
			'sprite_tile_palette_idxs' : sprite_tile_palette_idxs,
			'mass_q' : max(1, min(255, int(spec.get('mass_q', 1)))),
		}
		bodies.append(body)
		total_tile_count += tile_count
		total_oam_count += oam_need
	if not bodies:
		raise RuntimeError('GBC dynamic multi-body export requires at least one valid runtime body.')
	while len(palette_bank_obj) < 8:
		palette_bank_obj.append([tuple(c) for c in _GBC_DEFAULT_BG_COLORS[: 4]])
	obj_palette_bytes = _gbc_palette_bytes_from_palette_bank(palette_bank_obj)
	bg_payload = tile_data + tilemap + attrmap
	sprite_payload = bytearray()
	for body in bodies:
		tile_bytes_raw = body.get('sprite_tile_bytes', None)
		tile_bytes = b'' if tile_bytes_raw is None else bytes(tile_bytes_raw)
		need = int(body.get('sprite_tile_count', 1)) * 16
		if len(tile_bytes) < need:
			tile_bytes = tile_bytes + b'\x00' * (need - len(tile_bytes))
		sprite_payload.extend(tile_bytes[: need])
	if collider_rects is None:
		collider_rects = []
	else:
		collider_rects = list(collider_rects)
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
	collider_count = len(collider_payload) // 4
	probe = _gbc_build_dynamic_physics_program_multi(0, tile_data_len, tilemap_len, attrmap_len, 0, total_tile_count, bodies, bg_palette_bytes, obj_palette_bytes, collider_data_addr = 0, collider_count = collider_count, init_scroll_x = init_scroll_x, init_scroll_y = init_scroll_y, scroll_step_x = scroll_step_x, scroll_step_y = scroll_step_y)
	bg_data_addr = code_start + len(probe)
	if bg_data_addr & 0xF:
		bg_data_addr += 0x10 - (bg_data_addr & 0xF)
	sprite_data_addr = bg_data_addr + len(bg_payload)
	collider_data_addr = sprite_data_addr + len(sprite_payload)
	code = _gbc_build_dynamic_physics_program_multi(bg_data_addr, tile_data_len, tilemap_len, attrmap_len, sprite_data_addr, total_tile_count, bodies, bg_palette_bytes, obj_palette_bytes, collider_data_addr = collider_data_addr, collider_count = collider_count, init_scroll_x = init_scroll_x, init_scroll_y = init_scroll_y, scroll_step_x = scroll_step_x, scroll_step_y = scroll_step_y)
	total_need = collider_data_addr + len(collider_payload)
	if total_need > rom_size:
		raise RuntimeError('GBC dynamic multi-body export exceeds 32KB ROM size.')
	rom = bytearray(rom_size)
	rom[0x100 : 0x104] = bytes([0x00, 0xC3, 0x50, 0x01])
	rom[0x104 : 0x134] = _GBC_NINTENDO_LOGO
	title = b'JS13KGBCDYNMULT'
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
	if sprite_payload:
		rom[sprite_data_addr : sprite_data_addr + len(sprite_payload)] = bytes(sprite_payload)
	if collider_payload:
		rom[collider_data_addr : collider_data_addr + len(collider_payload)] = bytes(collider_payload)
	_gbc_compute_header_checksums(rom)
	print('GBC export: runtime mode = dynamic physics multi-body, bodies =', len(bodies), ', runtime colliders =', collider_count)
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

def _gbc_to_gba_cover_point (x : float, y : float):
	scale, x0, y0 = _gba_cover_transform(240, 160, 160, 144)
	if abs(scale) <= 1e-12:
		return float(x), float(y)
	return (float(x) + float(x0)) / float(scale), (float(y) + float(y0)) / float(scale)

def _gba_to_gbc_cover_len (v : float):
	scale, _, _ = _gba_cover_transform(240, 160, 160, 144)
	return max(1, int(round(float(v) * scale)))

def _gbc_to_gba_cover_len (v : float):
	scale, _, _ = _gba_cover_transform(240, 160, 160, 144)
	if abs(scale) <= 1e-12:
		return float(v)
	return float(v) / float(scale)

def _gbc_collider_attaches_to_rigid (collider_ob, rigid_ob):
	if collider_ob is None or rigid_ob is None:
		return False
	if collider_ob == rigid_ob:
		return True
	rigid_name = str(getattr(rigid_ob, 'name', '') or '')
	for i in range(MAX_ATTACH_COLLIDER_CNT):
		if not bool(getattr(collider_ob, 'attach%i' % i, False)):
			continue
		attach_ob = getattr(collider_ob, 'attachTo%i' % i, None)
		if attach_ob == rigid_ob:
			return True
		if attach_ob is not None and str(getattr(attach_ob, 'name', '') or '') == rigid_name:
			return True
	return False

def _gbc_estimate_collider_area (ob):
	shape = str(getattr(ob, 'colliderShapeType', '') or '')
	if shape in ('cuboid', 'roundCuboid'):
		size = getattr(ob, 'colliderSize', (0.0, 0.0))
		return abs(float(size[0]) * float(size[1]))
	if shape == 'ball':
		r = abs(float(getattr(ob, 'colliderRadius', 0.0)))
		return math.pi * r * r
	if shape == 'capsule':
		r = abs(float(getattr(ob, 'colliderCapsuleRadius', 0.0)))
		h = abs(float(getattr(ob, 'colliderCapsuleHeight', 0.0)))
		return (2.0 * r * h) + (math.pi * r * r)
	if shape in ('triangle', 'roundTriangle'):
		p0 = getattr(ob, 'colliderTrianglePnt0', (0.0, 0.0))
		p1 = getattr(ob, 'colliderTrianglePnt1', (0.0, 0.0))
		p2 = getattr(ob, 'colliderTrianglePnt2', (0.0, 0.0))
		return abs(
			(float(p0[0]) * (float(p1[1]) - float(p2[1])) +
			float(p1[0]) * (float(p2[1]) - float(p0[1])) +
			float(p2[0]) * (float(p0[1]) - float(p1[1]))) * 0.5
		)
	if shape == 'segment':
		p0 = getattr(ob, 'colliderSegmentPnt0', (0.0, 0.0))
		p1 = getattr(ob, 'colliderSegmentPnt1', (0.0, 0.0))
		dx = float(p1[0]) - float(p0[0])
		dy = float(p1[1]) - float(p0[1])
		return max(0.0, math.sqrt(dx * dx + dy * dy) * 0.25)
	if shape in ('polyline', 'trimesh', 'convexHull', 'roundConvexHull'):
		points = []
		if shape == 'polyline':
			for i in range(MAX_SHAPE_PNTS):
				if bool(getattr(ob, 'useColliderPolylinePnt%i' % i, False)):
					p = getattr(ob, 'colliderPolylinePnt%i' % i, None)
					if p is not None:
						points.append((float(p[0]), float(p[1])))
		elif shape == 'trimesh':
			for i in range(MAX_SHAPE_PNTS):
				if bool(getattr(ob, 'useColliderTrimeshPnt%i' % i, False)):
					p = getattr(ob, 'colliderTrimeshPnt%i' % i, None)
					if p is not None:
						points.append((float(p[0]), float(p[1])))
		else:
			for i in range(MAX_SHAPE_PNTS):
				if bool(getattr(ob, 'useColliderConvexHullPnt%i' % i, False)):
					p = getattr(ob, 'colliderConvexHullPnt%i' % i, None)
					if p is not None:
						points.append((float(p[0]), float(p[1])))
		if len(points) >= 2:
			xs = [p[0] for p in points]
			ys = [p[1] for p in points]
			return abs((max(xs) - min(xs)) * (max(ys) - min(ys)))
		return 0.0
	if shape == 'heightfield':
		heights = []
		for i in range(MAX_SHAPE_PNTS):
			if bool(getattr(ob, 'useColliderHeight%i' % i, False)):
				heights.append(abs(float(getattr(ob, 'colliderHeight%i' % i, 0.0))))
		scale = getattr(ob, 'colliderHeightfieldScale', (1.0, 1.0))
		scale_x = abs(float(scale[0])) if len(scale) > 0 else 1.0
		scale_y = abs(float(scale[1])) if len(scale) > 1 else 1.0
		if heights:
			return max(0.0, (sum(heights) / max(1, len(heights))) * scale_x * scale_y)
		return max(0.0, scale_x * scale_y)
	if shape == 'halfspace':
		return 16.0
	return 0.0

def _gbc_estimate_runtime_body_mass (scene_obs, rigid_ob):
	mass = 0.0
	for ob in list(scene_obs or []):
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		if not getattr(ob, 'colliderExists', False):
			continue
		if not getattr(ob, 'colliderEnable', True):
			continue
		if getattr(ob, 'isSensor', False):
			continue
		if not _gbc_collider_attaches_to_rigid(ob, rigid_ob):
			continue
		density = float(getattr(ob, 'density', 1.0))
		if density <= 0.0:
			density = 1.0
		area = float(_gbc_estimate_collider_area(ob))
		if area <= 0.0:
			area = 0.25
		mass += area * density
	if mass <= 0.0:
		# Bodies without colliders should still be movable.
		return 0.05
	return float(mass)

def _gbc_mass_to_q8 (mass):
	return max(1, min(255, int(round(max(0.05, float(mass)) * 4.0))))

def _gbc_pair_transfer_shift (src_mass_q : int, dst_mass_q : int, damping : float = 1.0):
	src = max(1.0, float(src_mass_q))
	dst = max(1.0, float(dst_mass_q))
	desired = max(0.0, min(1.0, (src / (src + dst)) * float(damping)))
	best_shift = 0
	best_err = 1e9
	for shift in range(0, 5):
		factor = 1.0 / float(1 << shift)
		err = abs(factor - desired)
		if err < best_err:
			best_err = err
			best_shift = shift
	return int(best_shift)

def _gbc_collect_runtime_colliders (scene_obs, ignored_name : str = None, ignored_names = None, scroll_x_gba : float = 0.0, scroll_y_gba : float = 0.0, preconverted_names = None, debug_rows = None, debug_include_ignored : bool = False, rect_meta = None):
	rects = []
	def _safe_abs_scale_xy (_ob):
		try:
			sc = getattr(_ob, 'scale', (1.0, 1.0, 1.0))
			sx = abs(float(sc[0])) if len(sc) > 0 else 1.0
			sy = abs(float(sc[1])) if len(sc) > 1 else 1.0
			return max(1e-9, sx), max(1e-9, sy)
		except Exception:
			return 1.0, 1.0
	def _collider_center_raw (ob):
		# Collider centers follow physics object origins (ob.location), not
		# image blit origins (GetImagePosition top-left semantics).
		base_x = float(ob.location.x)
		base_y = -float(ob.location.y)
		off = getattr(ob, 'colliderPosOff', (0.0, 0.0))
		try:
			off_x = float(off[0]) if len(off) > 0 else 0.0
			off_y = float(off[1]) if len(off) > 1 else 0.0
		except Exception:
			off_x = 0.0
			off_y = 0.0
		rot_z = 0.0
		try:
			rot_z = float(ob.rotation_euler.z)
		except Exception:
			rot_z = 0.0
		rot_off = Rotate2DByAngle(Vector((off_x, off_y, 0.0)), rot_z)
		cx = float(base_x + rot_off.x)
		cy = float(base_y - rot_off.y)
		return cx, cy, {
			'base' : [base_x, base_y],
			'off' : [off_x, off_y],
			'rot_off' : [float(rot_off.x), float(rot_off.y)],
			'rot_deg' : float(math.degrees(rot_z)),
		}
	ignored = set()
	if isinstance(ignored_name, str) and ignored_name:
		ignored.add(ignored_name)
	for name in list(ignored_names or []):
		if isinstance(name, str) and name:
			ignored.add(name)
	preconverted = set()
	for name in list(preconverted_names or []):
		if isinstance(name, str) and name:
			preconverted.add(name)
	for ob in scene_obs or []:
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		is_ignored = (ob.name in ignored)
		if is_ignored and not bool(debug_include_ignored):
			continue
		if not getattr(ob, 'colliderExists', False):
			continue
		if not getattr(ob, 'colliderEnable', True):
			continue
		if getattr(ob, 'isSensor', False):
			continue
		shape = str(getattr(ob, 'colliderShapeType', ''))
		cx_raw, cy_raw, center_debug = _collider_center_raw(ob)
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
		sx, sy = _safe_abs_scale_xy(ob)
		w = float(w) * float(sx)
		h = float(h) * float(sy)
		# Approximate authored collider rotation by expanding to an axis-aligned box.
		try:
			rot_total = float(ob.rotation_euler.z) + float(getattr(ob, 'colliderRotOff', 0.0))
		except Exception:
			rot_total = 0.0
		if shape in ('cuboid', 'roundCuboid', 'capsule') and abs(rot_total) > 1e-7:
			ca = abs(math.cos(rot_total))
			sa = abs(math.sin(rot_total))
			w0 = float(w)
			h0 = float(h)
			w = (w0 * ca) + (h0 * sa)
			h = (w0 * sa) + (h0 * ca)
		if ob.name in preconverted:
			cx = float(cx_raw) + float(scroll_x_gba)
			cy = float(cy_raw) + float(scroll_y_gba)
		else:
			cx, cy = _gbc_to_gba_cover_point(cx_raw, cy_raw)
			cx += float(scroll_x_gba)
			cy += float(scroll_y_gba)
			w = _gbc_to_gba_cover_len(w)
			h = _gbc_to_gba_cover_len(h)
		cx_gbc, cy_gbc = _gba_to_gbc_cover_point(cx, cy)
		w_gbc = _gba_to_gbc_cover_len(w)
		h_gbc = _gba_to_gbc_cover_len(h)
		left = int(round(cx_gbc - w_gbc * 0.5))
		top = int(round(cy_gbc - h_gbc * 0.5))
		left = max(0, min(255, left))
		top = max(0, min(255, top))
		w_gbc = max(1, min(255 - left, int(w_gbc)))
		h_gbc = max(1, min(255 - top, int(h_gbc)))
		if not is_ignored:
			rects.append((left, top, w_gbc, h_gbc))
			if isinstance(rect_meta, list):
				rect_meta.append({
					'name' : str(ob.name),
					'preconverted' : bool(ob.name in preconverted),
					'rect' : [left, top, w_gbc, h_gbc],
				})
		if isinstance(debug_rows, list):
			debug_rows.append(
				str(ob.name) +
				':ign=' + ('1' if is_ignored else '0') +
				':pre=' + ('1' if ob.name in preconverted else '0') +
				',base=' + str([TryChangeToInt(center_debug['base'][0]), TryChangeToInt(center_debug['base'][1])]) +
				',off=' + str([TryChangeToInt(center_debug['off'][0]), TryChangeToInt(center_debug['off'][1])]) +
				',roff=' + str([TryChangeToInt(center_debug['rot_off'][0]), TryChangeToInt(center_debug['rot_off'][1])]) +
				',rot=' + str(TryChangeToInt(center_debug['rot_deg'])) +
				',raw=' + str([TryChangeToInt(cx_raw), TryChangeToInt(cy_raw)]) +
				',gba=' + str([TryChangeToInt(cx), TryChangeToInt(cy)]) +
				',gbc=' + str([left, top, w_gbc, h_gbc])
			)
	return rects

class _GbcPhase1MirrorSim:
	def __init__ (self, x : int, y : int, vx : int, vy : int, grav_step_x : int, grav_step_y : int, sprite_w_px : int, sprite_h_px : int, collider_rects, offscreen_bottom_y : int, velocity_script = None, collider_positions = None, owner_collider_positions = None, collider_rect_meta = None, collision_w_px : int = None, collision_h_px : int = None, collision_off_x_px : int = 0, collision_off_y_px : int = 0, script_world_offset = None):
		self.x = max(0, min(65535, int(x)))
		self.y = max(0, min(65535, int(y)))
		self.vx = int(vx)
		self.vy = int(vy)
		self.gacc_x = 0
		self.gacc_y = 0
		self.grav_step_x = int(grav_step_x)
		self.grav_step_y = int(grav_step_y)
		self.sprite_w_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, int(sprite_w_px)))
		self.sprite_h_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, int(sprite_h_px)))
		self.collider_rects = list(collider_rects or [])
		self.offscreen_bottom_y = max(145, min(252, int(offscreen_bottom_y)))
		self.velocity_script = velocity_script if isinstance(velocity_script, dict) else None
		self.collider_positions = dict(collider_positions) if isinstance(collider_positions, dict) else {}
		self.owner_collider_positions = dict(owner_collider_positions) if isinstance(owner_collider_positions, dict) else {}
		self.collider_rect_meta = list(collider_rect_meta) if isinstance(collider_rect_meta, list) else []
		self.collision_w_px = max(1, int(collision_w_px if collision_w_px is not None else self.sprite_w_px))
		self.collision_h_px = max(1, int(collision_h_px if collision_h_px is not None else self.sprite_h_px))
		self.collision_off_x_px = int(collision_off_x_px)
		self.collision_off_y_px = int(collision_off_y_px)
		self.script_world_offset_x = 0.0
		self.script_world_offset_y = 0.0
		try:
			if isinstance(script_world_offset, (list, tuple)) and len(script_world_offset) >= 2:
				self.script_world_offset_x = float(script_world_offset[0])
				self.script_world_offset_y = float(script_world_offset[1])
		except Exception:
			self.script_world_offset_x = 0.0
			self.script_world_offset_y = 0.0
		self.x_subacc = int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2)
		self.y_subacc = int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM // 2)
		self._collision_trace_seen = set()
		self.dead = False
	def _to_local (self, v):
		return int(v) - _GBC_POSITION_BIAS
	def _get_collider_label (self, idx):
		try:
			if int(idx) < 0 or int(idx) >= len(self.collider_rect_meta):
				return ''
			meta = self.collider_rect_meta[int(idx)]
			if isinstance(meta, dict):
				return str(meta.get('name', '') or '')
		except Exception:
			pass
		return ''
	def _trace_collision_contact (self, source, idx, player_rect, collider_rect):
		try:
			sig = (str(source), int(idx))
			if sig in self._collision_trace_seen:
				return
			self._collision_trace_seen.add(sig)
			_g = __import__('builtins').globals()
			_trace = _g.get('_append_gbc_trace_lines', None)
			if not callable(_trace):
				return
			ax, ay, aw, ah = [float(v) for v in player_rect]
			bx, by, bw, bh = [float(v) for v in collider_rect]
			pen_left = (ax + aw) - bx
			pen_right = (bx + bw) - ax
			pen_top = (ay + ah) - by
			pen_bottom = (by + bh) - ay
			pens = {
				'left' : float(pen_left),
				'right' : float(pen_right),
				'top' : float(pen_top),
				'bottom' : float(pen_bottom),
			}
			overlap_side = min(pens.keys(), key = lambda k : abs(pens[k]))
			label = self._get_collider_label(idx)
			_trace([
				'[gbc-trace] Phase1Contact'
				+ ':source=' + str(source)
				+ ',collider_idx=' + str(int(idx))
				+ ',collider_name=' + repr(label)
				+ ',player=' + str([TryChangeToInt(ax), TryChangeToInt(ay), TryChangeToInt(aw), TryChangeToInt(ah)])
				+ ',collider=' + str([TryChangeToInt(bx), TryChangeToInt(by), TryChangeToInt(bw), TryChangeToInt(bh)])
				+ ',pen=' + str({
					'left' : TryChangeToInt(pen_left),
					'right' : TryChangeToInt(pen_right),
					'top' : TryChangeToInt(pen_top),
					'bottom' : TryChangeToInt(pen_bottom),
				})
				+ ',side=' + str(overlap_side)
			])
		except Exception:
			pass
	def _step_gravity_axis (self, step, acc, vel):
		if step == 0:
			return acc, vel
		mag = max(1, abs(int(step)))
		acc = int(acc) + mag
		if acc >= int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM):
			acc -= int(_GBC_PHASE1_GRAVITY_ACCUM_DENOM)
			vel += 1 if step > 0 else -1
			# Runtime stores velocity as signed 8-bit; clamp to avoid wrap-induced flips.
			if vel > 127:
				vel = 127
			elif vel < -128:
				vel = -128
		return int(acc), int(vel)
	def _step_velocity_axis (self, pos, vel, sub_acc, invert_dir : bool = False):
		vel = int(vel)
		sub_acc = int(sub_acc)
		if vel == 0:
			return int(pos), int(sub_acc)
		sub_acc += abs(vel)
		while sub_acc >= int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM):
			sub_acc -= int(_GBC_PHASE1_VELOCITY_ACCUM_DENOM)
			delta = (1 if vel > 0 else -1)
			if invert_dir:
				delta = -delta
			pos = (int(pos) + int(delta)) & 0xFFFF
		return int(pos), int(sub_acc)
	def _is_supported (self):
		local_y = self._to_local(self.y)
		local_x = self._to_local(self.x)
		col_x = int(local_x) + int(self.collision_off_x_px)
		col_y = int(local_y) + int(self.collision_off_y_px)
		feet_y = int(col_y) + int(self.collision_h_px)
		for cx, cy, cw, _ch in self.collider_rects:
			if feet_y != int(cy):
				continue
			right = int(cx) + int(cw)
			if (int(col_x) + int(self.collision_w_px)) <= int(cx):
				continue
			if int(col_x) >= right:
				continue
			return True
		return False
	def step (self):
		if self.dead:
			return
		self.gacc_x, self.vx = self._step_gravity_axis(self.grav_step_x, self.gacc_x, self.vx)
		if isinstance(self.velocity_script, dict):
			keys = _runtime_key_state_snapshot()
			# Script-space X is opposite phase1 internal X (step uses invert_dir = True).
			vx = _gbc_clamp_signed_byte(-int(self.velocity_script.get('base_vx', 0)))
			right_delta = _gbc_clamp_signed_byte(-int(self.velocity_script.get('right_delta', 0)))
			left_delta = _gbc_clamp_signed_byte(-int(self.velocity_script.get('left_delta', 0)))
			if bool(len(keys) > _RUNTIME_KEY_INDEX['RIGHT'] and keys[_RUNTIME_KEY_INDEX['RIGHT']]):
				vx = _gbc_clamp_signed_byte(vx + right_delta)
			if bool(len(keys) > _RUNTIME_KEY_INDEX['LEFT'] and keys[_RUNTIME_KEY_INDEX['LEFT']]):
				vx = _gbc_clamp_signed_byte(vx + left_delta)
			self.vx = int(vx)
			jump_y = self.velocity_script.get('jump_y', None)
			if jump_y is not None and bool(len(keys) > _RUNTIME_KEY_INDEX['A'] and keys[_RUNTIME_KEY_INDEX['A']]):
				jump_vy_max = self.velocity_script.get('jump_vy_max', None)
				can_jump = True
				if jump_vy_max is not None:
					# Match script-space guard semantics: vel[1] is Y-up.
					script_vy = int(-int(self.vy))
					can_jump = bool(script_vy <= int(jump_vy_max))
				if can_jump:
					# Script-space Y is up, internal velocity is Y-down.
					self.vy = int(-int(jump_y))
					self.gacc_y = 0
		self.x, self.x_subacc = self._step_velocity_axis(self.x, self.vx, self.x_subacc, invert_dir = True)
		# Keep resting bodies stable on top of colliders instead of re-accelerating each frame.
		if self.vy >= 0 and self._is_supported():
			self.vy = 0
			self.gacc_y = 0
		else:
			self.gacc_y, self.vy = self._step_gravity_axis(self.grav_step_y, self.gacc_y, self.vy)
			self.y, self.y_subacc = self._step_velocity_axis(self.y, self.vy, self.y_subacc)
		# Match phase1 runtime: only resolve downward contacts.
		if self.vy > 0:
			local_x = self._to_local(self.x)
			local_y = self._to_local(self.y)
			col_x = int(local_x) + int(self.collision_off_x_px)
			col_y = int(local_y) + int(self.collision_off_y_px)
			if local_y >= int(self.offscreen_bottom_y):
				return
			for idx, (cx, cy, cw, _ch) in enumerate(self.collider_rects):
				right = int(cx) + int(cw)
				if (col_x + self.collision_w_px) <= int(cx):
					continue
				if col_x >= right:
					continue
				if col_y >= int(cy):
					continue
				if (col_y + self.collision_h_px) < int(cy):
					continue
				self._trace_collision_contact(
					'step_downward_resolve',
					idx,
					[col_x, col_y, self.collision_w_px, self.collision_h_px],
					[cx, cy, cw, _ch],
				)
				self.y = (_GBC_POSITION_BIAS + max(0, int(cy) - self.collision_h_px - self.collision_off_y_px)) & _GBC_POSITION_MASK
				self.vy = 0
				self.gacc_y = 0
				break
	def set_linear_velocity (self, _rigidBody, vel, wakeUp = True):
		try:
			# Mirror script-facing convention:
			# X is inverted in phase1 internals, Y is script-up/internal-down.
			self.vx = _gbc_clamp_signed_byte(int(round(-float(vel[0]))))
			self.vy = _gbc_clamp_signed_byte(int(round(-float(vel[1]))))
		except Exception:
			pass
	def get_linear_velocity (self, _rigidBody):
		# Mirror script-facing velocities as integer steps to avoid feedback when
		# scripts read-then-write velocity every frame.
		return [-float(self.vx), -float(self.vy)]
	def set_rigid_body_position (self, _rigidBody, pos, wakeUp = True):
		try:
			local_x = float(pos[0]) - float(self.script_world_offset_x)
			local_y = float(pos[1]) - float(self.script_world_offset_y)
			self.x = (int(round(local_x)) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
			self.y = (int(round(-local_y)) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
		except Exception:
			pass
	def get_rigid_body_position (self, _rigidBody):
		return [
			float(self.x - _GBC_POSITION_BIAS) + float(self.script_world_offset_x),
			-float(self.y - _GBC_POSITION_BIAS) + float(self.script_world_offset_y),
		]
	def set_collider_position (self, _collider, pos, wakeUp = True):
		try:
			key = str(_collider)
		except Exception:
			key = ''
		if key != '' and key in self.collider_positions:
			try:
				self.collider_positions[key] = [float(pos[0]), float(pos[1])]
				return None
			except Exception:
				pass
		return self.set_rigid_body_position(_collider, pos, wakeUp)
	def get_collider_position (self, _collider):
		try:
			key = str(_collider)
		except Exception:
			key = ''
		def _parse_handle_pair (_v):
			try:
				if isinstance(_v, str):
					parsed = ast.literal_eval(_v)
				else:
					parsed = _v
				if isinstance(parsed, (tuple, list)) and len(parsed) == 2:
					return (int(parsed[0]), int(parsed[1]))
			except Exception:
				return None
			return None
		def _trace_colpos (_source, _lookup_key, _pos):
			try:
				_g = __import__('builtins').globals()
				_seen = _g.get('_gbc_phase1_colpos_trace_seen', None)
				if not isinstance(_seen, set):
					_seen = set()
					_g['_gbc_phase1_colpos_trace_seen'] = _seen
				_sig = (str(_source), str(_lookup_key), repr(_pos))
				if _sig in _seen:
					return
				_seen.add(_sig)
				_trace = _g.get('_append_gbc_trace_lines', None)
				if callable(_trace):
					_trace([
						'[gbc-trace] Phase1ColPos'
						+ f':source={_source}'
						+ f',input={repr(key)}'
						+ f',lookup={repr(_lookup_key)}'
						+ f',out={repr(_pos)}'
					])
			except Exception:
				pass
		if key != '':
			handle_pair = _parse_handle_pair(key)
			if handle_pair is not None:
				for _k, _p in list(getattr(self, 'collider_positions', {}).items()):
					if _parse_handle_pair(_k) == handle_pair:
						try:
							out = [float(_p[0]), float(_p[1])]
							_trace_colpos('tuple_pair_collider_map', _k, out)
							return out
						except Exception:
							pass
				_named_cols = getattr(self, 'named_colliders', {})
				if isinstance(_named_cols, dict):
					for _owner_key, _h in list(_named_cols.items()):
						if _parse_handle_pair(_h) != handle_pair:
							continue
						try:
							owner_txt = str(_owner_key)
						except Exception:
							owner_txt = ''
						if owner_txt == '':
							continue
						for _cand in list(_script_lookup_candidate_names(owner_txt)):
							if _cand in self.owner_collider_positions:
								try:
									p = self.owner_collider_positions[_cand]
									out = [float(p[0]), float(p[1])]
									_trace_colpos('tuple_pair_owner_map', _cand, out)
									return out
								except Exception:
									pass
							if _cand in self.collider_positions:
								try:
									p = self.collider_positions[_cand]
									out = [float(p[0]), float(p[1])]
									_trace_colpos('tuple_pair_handle_map', _cand, out)
									return out
								except Exception:
									pass
						try:
							_get_pos = __import__('builtins').globals().get('get_object_position', None)
							if callable(_get_pos):
								p = _get_pos(owner_txt)
								if p is not None:
									out = [float(p[0]), float(p[1])]
									_trace_colpos('tuple_pair_owner_object_pos', owner_txt, out)
									return out
						except Exception:
							pass
			# Owner-bound scripts often pass symbolic object keys (for example
			# __gbc_spawn_* draw-proxy names). Prefer authored collider position
			# mapped by owner key before touching runtime-handle fallbacks.
			if key in self.owner_collider_positions:
				try:
					p = self.owner_collider_positions[key]
					out = [float(p[0]), float(p[1])]
					_trace_colpos('owner_map_direct', key, out)
					return out
				except Exception:
					out = [0.0, 0.0]
					_trace_colpos('owner_map_direct_err', key, out)
					return out
			candidates = [key]
			if key.startswith('_'):
				candidates.append(key[1:])
			else:
				candidates.append('_' + key)
			if not key.endswith(':0'):
				candidates.append(key + ':0')
				if key.startswith('_'):
					candidates.append(key[1:] + ':0')
				else:
					candidates.append('_' + key + ':0')
			for cand in candidates:
				if cand in self.owner_collider_positions:
					try:
						p = self.owner_collider_positions[cand]
						out = [float(p[0]), float(p[1])]
						_trace_colpos('owner_map_candidate', cand, out)
						return out
					except Exception:
						out = [0.0, 0.0]
						_trace_colpos('owner_map_candidate_err', cand, out)
						return out
				if cand in self.collider_positions:
					try:
						p = self.collider_positions[cand]
						out = [float(p[0]), float(p[1])]
						_trace_colpos('handle_map', cand, out)
						return out
					except Exception:
						out = [0.0, 0.0]
						_trace_colpos('handle_map_err', cand, out)
						return out
				# Last key-based fallback: resolve visual/runtime object position
				# by owner key so missing collider handles don't collapse to body pos.
				try:
					_spawn_pos_overrides = __import__('builtins').globals().get('_gbc_spawn_owner_pos_overrides', {})
					if isinstance(_spawn_pos_overrides, dict):
						_sp = _spawn_pos_overrides.get(cand, None)
						if _sp is None and isinstance(cand, str) and cand.startswith('__gbc_spawnphys_'):
							_sp = _spawn_pos_overrides.get('__gbc_spawn_' + cand[len('__gbc_spawnphys_'):], None)
						if _sp is None and isinstance(cand, str):
							# Fuzzy fallback for spawn owner maps when exact draw/proxy
							# key differs between script owner and stored override key.
							_suffix = ''
							if cand.startswith('__gbc_spawn_'):
								_suffix = cand[len('__gbc_spawn_'):]
							elif cand.startswith('__gbc_spawnphys_'):
								_suffix = cand[len('__gbc_spawnphys_'):]
							if _suffix != '':
								_source = _suffix
								_sep = _source.find('_')
								if _sep > 0 and _source[:_sep].isdigit() and _source[_sep + 1:] != '':
									_source = _source[_sep + 1:]
								for _k, _v in list(_spawn_pos_overrides.items()):
									if not isinstance(_k, str):
										continue
									if _k.endswith('_' + _suffix):
										_sp = _v
										break
									if _source != '' and _k.endswith('_' + _source):
										_sp = _v
										break
						if isinstance(_sp, (list, tuple)) and len(_sp) >= 2:
							out = [float(_sp[0]), float(_sp[1])]
							_trace_colpos('spawn_owner_pos', cand, out)
							return out
				except Exception:
					pass
				try:
					_get_pos = __import__('builtins').globals().get('get_object_position', None)
					if callable(_get_pos):
						p = _get_pos(cand)
						if p is not None:
							out = [float(p[0]), float(p[1])]
							_trace_colpos('object_pos', cand, out)
							return out
				except Exception:
					pass
		# Never use dynamic body fallback for spawned owner collider keys; that
		# path produces misleading moving-body coordinates for static spawn proxies.
		try:
			if isinstance(key, str) and (key.startswith('__gbc_spawn_') or key.startswith('__gbc_spawnphys_')):
				src = ''
				if key.startswith('__gbc_spawn_'):
					src = key[len('__gbc_spawn_'):]
				else:
					src = key[len('__gbc_spawnphys_'):]
				src_with_idx = str(src)
				if src != '':
					sep_idx = src.find('_')
					if sep_idx > 0 and src[:sep_idx].isdigit() and src[sep_idx + 1:] != '':
						src = src[sep_idx + 1:]
					try:
						_spawn_pos_overrides = __import__('builtins').globals().get('_gbc_spawn_owner_pos_overrides', {})
						if isinstance(_spawn_pos_overrides, dict):
							_sp = _spawn_pos_overrides.get(key, None)
							if _sp is None and src_with_idx != '':
								for _k, _v in list(_spawn_pos_overrides.items()):
									if not isinstance(_k, str):
										continue
									if _k.endswith('_' + src_with_idx):
										_sp = _v
										break
							if _sp is None and src != '':
								for _k, _v in list(_spawn_pos_overrides.items()):
									if not isinstance(_k, str):
										continue
									if _k.endswith('_' + src):
										_sp = _v
										break
							if isinstance(_sp, (list, tuple)) and len(_sp) >= 2:
								out = [float(_sp[0]), float(_sp[1])]
								_trace_colpos('spawn_terminal_owner_pos', src, out)
								return out
					except Exception:
						pass
					_get_pos = __import__('builtins').globals().get('get_object_position', None)
					if callable(_get_pos):
						p = _get_pos(src)
						if p is not None:
							out = [float(p[0]), float(p[1])]
							_trace_colpos('spawn_source_terminal', src, out)
							return out
				out = [0.0, 0.0]
				_trace_colpos('spawn_no_body_fallback', key, out)
				return out
		except Exception:
			pass
		# For unresolved owner-like string keys (for example "_Ground001"),
		# prefer authored static pose over dynamic sprite/body fallback.
		try:
			if isinstance(key, str) and key != '':
				_pos = _resolve_static_owner_camera_position(key)
				if isinstance(_pos, (list, tuple)) and len(_pos) >= 2:
					out = [float(_pos[0]), float(_pos[1])]
					_trace_colpos('owner_static_terminal', key, out)
					return out
		except Exception:
			pass
		try:
			if isinstance(key, str) and key != '':
				out = [0.0, 0.0]
				_trace_colpos('owner_string_no_body_fallback', key, out)
				return out
		except Exception:
			pass
		# Tuple-like collider handles (for example "(1, 0)") should never
		# fall back to sprite body position; resolve by reverse owner lookup.
		try:
			is_tuple_handle = (
				isinstance(key, str)
				and len(key) >= 5
				and key[0] == '('
				and key[-1] == ')'
				and ',' in key
			)
		except Exception:
			is_tuple_handle = False
		if is_tuple_handle:
			try:
				_col_ids = __import__('builtins').globals().get('collidersIds', {})
			except Exception:
				_col_ids = {}
			if isinstance(_col_ids, dict):
				for _owner_key, _owner_handle in list(_col_ids.items()):
					try:
						if str(_owner_handle) != key:
							continue
					except Exception:
						continue
					try:
						owner_txt = str(_owner_key)
					except Exception:
						owner_txt = ''
					if owner_txt == '':
						continue
					for _cand in list(_script_lookup_candidate_names(owner_txt)):
						if _cand in self.owner_collider_positions:
							try:
								p = self.owner_collider_positions[_cand]
								out = [float(p[0]), float(p[1])]
								_trace_colpos('tuple_owner_reverse_map', _cand, out)
								return out
							except Exception:
								pass
						if _cand in self.collider_positions:
							try:
								p = self.collider_positions[_cand]
								out = [float(p[0]), float(p[1])]
								_trace_colpos('tuple_handle_reverse_map', _cand, out)
								return out
							except Exception:
								pass
					try:
						_get_pos = __import__('builtins').globals().get('get_object_position', None)
						if callable(_get_pos):
							p = _get_pos(owner_txt)
							if p is not None:
								out = [float(p[0]), float(p[1])]
								_trace_colpos('tuple_owner_object_pos', owner_txt, out)
								return out
					except Exception:
						pass
			out = [0.0, 0.0]
			_trace_colpos('tuple_no_body_fallback', key, out)
			return out
		out = self.get_rigid_body_position(_collider)
		_trace_colpos('body_fallback', key, out)
		return out
	def set_rigid_body_rotation (self, _rigidBody, rot, wakeUp = True):
		return None
	def get_rigid_body_rotation (self, _rigidBody):
		return 0.0
	def set_collider_rotation (self, _collider, rot, wakeUp = True):
		return None
	def get_collider_rotation (self, _collider):
		return 0.0
	def set_angular_velocity (self, _rigidBody, angVel, wakeUp = True):
		return None
	def get_angular_velocity (self, _rigidBody):
		return 0.0
	def _coerce_vec2 (self, val, fallback = None):
		if fallback is None:
			fallback = [0.0, 0.0]
		try:
			return [float(val[0]), float(val[1])]
		except Exception:
			try:
				return [float(fallback[0]), float(fallback[1])]
			except Exception:
				return [0.0, 0.0]
	def _cast_hit_entry (self, collider_idx, toi, x, y):
		return {
			'collider' : collider_idx,
			'toi' : float(toi),
			'witness1' : [float(x), float(y)],
			'witness2' : [float(x), float(y)],
			'normal1' : [0.0, 0.0],
			'normal2' : [0.0, 0.0],
		}
	def _aabb_overlaps (self, ax, ay, aw, ah, bx, by, bw, bh):
		return (
			(float(ax) < (float(bx) + float(bw)))
			and ((float(ax) + float(aw)) > float(bx))
			and (float(ay) < (float(by) + float(bh)))
			and ((float(ay) + float(ah)) > float(by))
		)
	def cast_collider (self, shape, shapeVel, shapePos, shapeRot, collisionGroupFilter = None):
		start = self._coerce_vec2(shapePos, [0.0, 0.0])
		vel = self._coerce_vec2(shapeVel, [0.0, 0.0])
		# Mirror scripts use Y-up; collider rects use Y-down.
		start_x = float(start[0]) + float(self.collision_off_x_px)
		start_y = -float(start[1]) + float(self.collision_off_y_px)
		dx = float(vel[0])
		dy = -float(vel[1])
		shape_w = float(self.collision_w_px)
		shape_h = float(self.collision_h_px)
		for idx, (cx, cy, cw, ch) in enumerate(self.collider_rects):
			if self._aabb_overlaps(start_x, start_y, shape_w, shape_h, cx, cy, cw, ch):
				self._trace_collision_contact(
					'cast_start_overlap',
					idx,
					[start_x, start_y, shape_w, shape_h],
					[cx, cy, cw, ch],
				)
				return self._cast_hit_entry(idx, 0.0, start_x, start_y)
		max_delta = max(abs(dx), abs(dy), 1.0)
		steps = max(1, int(math.ceil(max_delta)))
		for step_i in range(1, steps + 1):
			t = float(step_i) / float(steps)
			px = start_x + (dx * t)
			py = start_y + (dy * t)
			for idx, (cx, cy, cw, ch) in enumerate(self.collider_rects):
				if self._aabb_overlaps(px, py, shape_w, shape_h, cx, cy, cw, ch):
					self._trace_collision_contact(
						'cast_step_overlap',
						idx,
						[px, py, shape_w, shape_h],
						[cx, cy, cw, ch],
					)
					return self._cast_hit_entry(idx, t, px, py)
		return None
	def __getattr__ (self, _name):
		# Keep phase1 print-mirror API permissive like script compat shims:
		# unknown physics helpers (e.g. cast_collider) should be callable.
		if isinstance(_name, str) and (
			_name.startswith('get_')
			or _name.startswith('cast_')
			or _name.startswith('cast')
		):
			return (lambda *args, **kwargs: None)
		return (lambda *args, **kwargs: 0)

def _build_gbc_phase1_print_env (sprite_ob, sprite_tiles_w : int, sprite_tiles_h : int, init_x : int, init_y : int, init_vx : int, init_vy : int, grav_step_x : int, grav_step_y : int, collider_rects, velocity_script = None, physics_scene_obs = None, runtime_handle_env = None, collider_rect_meta = None, collision_w_px : int = None, collision_h_px : int = None, collision_off_x_px : int = 0, collision_off_y_px : int = 0, script_world_offset = None):
	if sprite_ob is None:
		return {}
	sprite_w_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, int(sprite_tiles_w) * 8))
	sprite_h_px = max(8, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES * 8, int(sprite_tiles_h) * 8))
	offscreen_bottom_y = max(145, min(252, 144 + int(sprite_tiles_h) * 8))
	collider_positions = {}
	owner_collider_positions = {}
	def _authored_collider_position (_ob):
		try:
			pos, _rot = _gba_get_object_pose(_ob)
		except Exception:
			return [0.0, 0.0]
		try:
			off = getattr(_ob, 'colliderPosOff', (0.0, 0.0))
			off_x = float(off[0]) if len(off) > 0 else 0.0
			off_y = float(off[1]) if len(off) > 1 else 0.0
		except Exception:
			off_x = 0.0
			off_y = 0.0
		return [float(pos[0]) + off_x, -(float(pos[1]) - off_y)]
	sim = _GbcPhase1MirrorSim(
		x = init_x,
		y = init_y,
		vx = init_vx,
		vy = init_vy,
		grav_step_x = grav_step_x,
		grav_step_y = grav_step_y,
		sprite_w_px = sprite_w_px,
		sprite_h_px = sprite_h_px,
		collider_rects = collider_rects,
		offscreen_bottom_y = offscreen_bottom_y,
		velocity_script = velocity_script,
		collider_positions = collider_positions,
		owner_collider_positions = owner_collider_positions,
		collider_rect_meta = collider_rect_meta,
		collision_w_px = collision_w_px,
		collision_h_px = collision_h_px,
		collision_off_x_px = collision_off_x_px,
		collision_off_y_px = collision_off_y_px,
		script_world_offset = script_world_offset,
	)
	handle = str(GetVarNameForObject(sprite_ob))
	rigid_bodies_named = {}
	if isinstance(runtime_handle_env, dict):
		try:
			_rb_src = runtime_handle_env.get('rigidBodiesIds', runtime_handle_env.get('rigidBodies', {}))
			if isinstance(_rb_src, dict):
				rigid_bodies_named.update(_rb_src)
		except Exception:
			pass
	for key in [handle, '_' + handle, str(sprite_ob.name), '_' + str(sprite_ob.name)]:
		if key:
			rigid_bodies_named.setdefault(key, handle)
	colliders_named = {}
	if isinstance(runtime_handle_env, dict):
		try:
			_col_src = runtime_handle_env.get('collidersIds', runtime_handle_env.get('colliders', {}))
			if isinstance(_col_src, dict):
				colliders_named.update(_col_src)
		except Exception:
			pass
	def _set_collider_aliases (_ob):
		if _ob is None:
			return
		try:
			ob_var = str(GetVarNameForObject(_ob))
		except Exception:
			ob_var = str(getattr(_ob, 'name', '') or '')
		ob_name = str(getattr(_ob, 'name', '') or '')
		if ob_var == '' and ob_name == '':
			return
		col_handle = (ob_var if ob_var != '' else ob_name)
		alias_keys = [ob_var, '_' + ob_var, ob_name, '_' + ob_name]
		for base_key in list(alias_keys):
			if isinstance(base_key, str) and base_key != '' and not base_key.endswith(':0'):
				alias_keys.append(base_key + ':0')
		apos = _authored_collider_position(_ob)
		owner_aliases = []
		for base_name in [ob_var, ob_name]:
			if not (isinstance(base_name, str) and base_name != ''):
				continue
			owner_aliases.append(base_name)
			try:
				for cand in list(_script_lookup_candidate_names(base_name) or []):
					if isinstance(cand, str) and cand != '':
						owner_aliases.append(cand)
			except Exception:
				pass
		for key in alias_keys:
			if isinstance(key, str) and key != '':
				colliders_named.setdefault(key, col_handle)
				collider_positions.setdefault(key, apos)
				try:
					mapped_handle = colliders_named.get(key, None)
				except Exception:
					mapped_handle = None
				if mapped_handle is not None:
					try:
						collider_positions.setdefault(str(mapped_handle), apos)
					except Exception:
						pass
		for owner_key in owner_aliases:
			if isinstance(owner_key, str) and owner_key != '':
				owner_collider_positions.setdefault(owner_key, apos)
	_set_collider_aliases(sprite_ob)
	for _ob in list(physics_scene_obs or []):
		if not getattr(_ob, 'exportOb', False) or _ob.hide_get():
			continue
		_set_collider_aliases(_ob)
	def _wrap_flip_y_getter (_fn):
		def _wrapped (*args, **kwargs):
			try:
				_pos = _fn(*args, **kwargs)
				return [float(_pos[0]), -float(_pos[1])]
			except Exception:
				return [0.0, 0.0]
		return _wrapped
	if hasattr(sim, 'get_rigid_body_position'):
		try:
			sim.get_rigid_body_position = _wrap_flip_y_getter(sim.get_rigid_body_position)
		except Exception:
			pass
	if hasattr(sim, 'get_collider_position'):
		try:
			sim.get_collider_position = _wrap_flip_y_getter(sim.get_collider_position)
		except Exception:
			pass
	sim.named_colliders = colliders_named
	sim.named_rigid_bodies = rigid_bodies_named
	return {
		'objects' : {},
		'sim' : sim,
		'physics' : sim,
		'rigidBodies' : rigid_bodies_named,
		'rbs' : rigid_bodies_named,
		'rigidBodiesIds' : rigid_bodies_named,
		'colliders' : colliders_named,
		'cols' : colliders_named,
		'collidersIds' : colliders_named,
	}

def _ast_numeric_literal (node):
	try:
		v = ast.literal_eval(node)
	except Exception:
		return None
	if isinstance(v, (int, float)):
		return float(v)
	return None

def _ast_numeric_vec2_literal (node):
	if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < 2:
		return None
	vx = _ast_numeric_literal(node.elts[0])
	vy = _ast_numeric_literal(node.elts[1])
	if vx is None or vy is None:
		return None
	return [float(vx), float(vy)]

def _ast_is_this_id_expr (node):
	if hasattr(ast, 'Index') and isinstance(node, ast.Index):
		node = node.value
	return (
		isinstance(node, ast.Attribute)
		and isinstance(node.value, ast.Name)
		and node.value.id == 'this'
		and node.attr == 'id'
	)

def _script_owner_matches_target_keys (owner_name, target_keys):
	if not isinstance(owner_name, str) or owner_name == '':
		return False
	owner_token = owner_name.lstrip('_')
	for key in list(target_keys or []):
		if not isinstance(key, str) or key == '':
			continue
		if key.lstrip('_') == owner_token:
			return True
	return False

def _build_ast_literal_expr_node (_value):
	try:
		parsed = ast.parse(repr(_value), mode = 'eval')
		return parsed.body
	except Exception:
		return None

def _rewrite_this_attributes_with_object_values (_code, _ob):
	if not isinstance(_code, str) or _code.strip() == '':
		return str(_code or '')
	try:
		attributes = GetAttributes(_ob)
	except Exception:
		attributes = {}
	if not isinstance(attributes, dict) or attributes == {}:
		return str(_code)
	try:
		tree = ast.parse(_code)
	except Exception:
		return str(_code)
	class _RewriteThisAttributeLiterals(ast.NodeTransformer):
		def visit_Attribute (self, node):
			node = self.generic_visit(node)
			if (
				isinstance(node, ast.Attribute)
				and isinstance(node.value, ast.Name)
				and node.value.id == 'this'
				and isinstance(node.attr, str)
				and node.attr in attributes
				and isinstance(node.ctx, ast.Load)
			):
				lit = _build_ast_literal_expr_node(attributes.get(node.attr))
				if lit is not None:
					return ast.copy_location(lit, node)
			return node
	try:
		tree = _RewriteThisAttributeLiterals().visit(tree)
		tree = ast.fix_missing_locations(tree)
		return ast.unparse(tree)
	except Exception:
		return str(_code)

def _extract_rigidbody_name_expr (node):
	if isinstance(node, ast.Name):
		return ('name_ref', node.id)
	if (
		isinstance(node, ast.Attribute)
		and isinstance(node.value, ast.Name)
		and node.value.id == 'this'
		and node.attr == 'rb'
	):
		# Accept direct this.rb references in gbc-py scripts so
		# phase-1 velocity extraction can match object-local control code.
		return ('this_id', None)
	if isinstance(node, ast.Subscript):
		base = node.value
		if isinstance(base, ast.Name) and base.id in ('rigidBodies', 'rigidBodiesIds'):
			key = None
			if isinstance(node.slice, ast.Constant):
				key = node.slice.value
			elif hasattr(ast, 'Index') and isinstance(node.slice, ast.Index) and isinstance(node.slice.value, ast.Constant):
				key = node.slice.value.value
			elif _ast_is_this_id_expr(node.slice):
				return ('this_id', None)
			if isinstance(key, str):
				return ('key', key)
	if isinstance(node, ast.Call):
		if isinstance(node.func, ast.Name) and node.func.id == 'get_rigidbody' and len(node.args or []) >= 1:
			arg0 = node.args[0]
			if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
				return ('key', arg0.value)
			if _ast_is_this_id_expr(arg0):
				return ('this_id', None)
	return (None, None)

def _extract_gbc_phase1_init_velocity_from_code (code : str, target_keys : set, allow_this_id : bool = False):
	try:
		tree = ast.parse(code or '')
	except Exception:
		return None
	target_keys = set([str(k) for k in (target_keys or set()) if isinstance(k, str) and k])
	if not target_keys:
		return None
	aliases = {}
	vel_aliases = {}
	for stmt in _walk_statically_reachable_stmts(getattr(tree, 'body', [])):
		if isinstance(stmt, ast.Assign):
			rb_kind = None
			rb_value = None
			if stmt.value is not None:
				rb_kind, rb_value = _extract_rigidbody_name_expr(stmt.value)
			vel_value = _ast_numeric_vec2_literal(stmt.value) if stmt.value is not None else None
			for target in list(stmt.targets or []):
				if isinstance(target, ast.Name):
					if rb_kind in ('name_ref', 'key', 'this_id'):
						aliases[target.id] = (rb_kind, rb_value)
					else:
						aliases.pop(target.id, None)
					if vel_value is not None:
						vel_aliases[target.id] = [float(vel_value[0]), float(vel_value[1])]
					else:
						vel_aliases.pop(target.id, None)
			continue
		if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
			rb_kind = None
			rb_value = None
			if stmt.value is not None:
				rb_kind, rb_value = _extract_rigidbody_name_expr(stmt.value)
			if rb_kind in ('name_ref', 'key', 'this_id'):
				aliases[stmt.target.id] = (rb_kind, rb_value)
			else:
				aliases.pop(stmt.target.id, None)
			vel_value = _ast_numeric_vec2_literal(stmt.value) if stmt.value is not None else None
			if vel_value is not None:
				vel_aliases[stmt.target.id] = [float(vel_value[0]), float(vel_value[1])]
			else:
				vel_aliases.pop(stmt.target.id, None)
			continue
		if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
			aliases.pop(stmt.target.id, None)
			vel_aliases.pop(stmt.target.id, None)
			continue
		if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
			call = stmt.value
			func = call.func
			if not (isinstance(func, ast.Attribute) and func.attr == 'set_linear_velocity'):
				continue
			if not (isinstance(func.value, ast.Name) and func.value.id in ('sim', 'physics')):
				continue
			if len(call.args or []) < 2:
				continue
			rb_kind, rb_value = _extract_rigidbody_name_expr(call.args[0])
			if rb_kind == 'name_ref' and rb_value in aliases:
				rb_kind, rb_value = aliases[rb_value]
			if rb_kind == 'this_id':
				if not bool(allow_this_id):
					continue
			else:
				if rb_kind != 'key' or not isinstance(rb_value, str):
					continue
				if rb_value not in target_keys:
					continue
			vel = call.args[1]
			if isinstance(vel, ast.Name) and vel.id in vel_aliases:
				vx = float(vel_aliases[vel.id][0])
				vy = float(vel_aliases[vel.id][1])
			else:
				vel_value = _ast_numeric_vec2_literal(vel)
				if vel_value is None:
					continue
				vx = float(vel_value[0])
				vy = float(vel_value[1])
			if vx is None or vy is None:
				continue
			# gbc-py scripts use screen-space Y where positive is down, so
			# set_linear_velocity input Y is flipped before simulation.
			return (int(round(vx)), int(round(-vy)))
	return None

def _extract_gbc_phase1_init_velocity (world, sprite_ob):
	if sprite_ob is None:
		return (0, 0)
	target_keys = set()
	sprite_name = str(getattr(sprite_ob, 'name', '') or '')
	if sprite_name:
		target_keys.add(sprite_name)
		target_keys.add('_' + sprite_name)
	try:
		sprite_var = GetVarNameForObject(sprite_ob)
		if isinstance(sprite_var, str) and sprite_var:
			target_keys.add(sprite_var)
			target_keys.add('_' + sprite_var)
	except Exception:
		pass
	init_codes = []
	update_codes = []
	if world is not None:
		for scriptInfo in list(GetScripts(world) or []):
			scriptTxt = scriptInfo[0]
			isInit = bool(scriptInfo[1])
			_type = scriptInfo[2]
			if _type != 'gbc-py':
				continue
			if isInit:
				init_codes.append((scriptTxt, False))
			else:
				update_codes.append((scriptTxt, False))
	for ob in list(getattr(bpy.data, 'objects', []) or []):
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		allow_this_id = _script_owner_matches_target_keys(str(getattr(ob, 'name', '') or ''), target_keys)
		for scriptInfo in list(GetScripts(ob) or []):
			scriptTxt = scriptInfo[0]
			isInit = bool(scriptInfo[1])
			_type = scriptInfo[2]
			if _type != 'gbc-py':
				continue
			scriptTxt = _rewrite_this_attributes_with_object_values(scriptTxt, ob)
			if isInit:
				init_codes.append((scriptTxt, allow_this_id))
			else:
				update_codes.append((scriptTxt, allow_this_id))
	for code, allow_this_id in init_codes:
		match = _extract_gbc_phase1_init_velocity_from_code(code, target_keys, allow_this_id = allow_this_id)
		if match is not None:
			return match
	# Phase-1 runtime does not execute gbc-py update scripts, but if authors
	# place a constant velocity set there, use it as startup seed fallback.
	for code, allow_this_id in update_codes:
		match = _extract_gbc_phase1_init_velocity_from_code(code, target_keys, allow_this_id = allow_this_id)
		if match is not None:
			return match
	return (0, 0)

def _extract_gbc_phase1_velocity_script (world, sprite_ob):
	def _ast_small_int (_node, _consts):
		if isinstance(_node, ast.Constant):
			try:
				return int(round(float(_node.value)))
			except Exception:
				return None
		if isinstance(_node, ast.Name):
			return _consts.get(_node.id)
		if isinstance(_node, ast.UnaryOp) and isinstance(_node.op, ast.USub):
			v = _ast_small_int(_node.operand, _consts)
			return (-v) if isinstance(v, int) else None
		if isinstance(_node, ast.UnaryOp) and isinstance(_node.op, ast.UAdd):
			v = _ast_small_int(_node.operand, _consts)
			return v if isinstance(v, int) else None
		return None
	def _subscript_key_name (_node):
		if not isinstance(_node, ast.Subscript):
			return None
		key = _node.slice
		if hasattr(ast, 'Index') and isinstance(key, ast.Index):
			key = key.value
		if isinstance(key, ast.Attribute) and isinstance(key.value, ast.Name) and key.value.id == 'pygame':
			return key.attr
		return None
	def _subscript_const_index (_node):
		if not isinstance(_node, ast.Subscript):
			return None
		idx = _node.slice
		if hasattr(ast, 'Index') and isinstance(idx, ast.Index):
			idx = idx.value
		if isinstance(idx, ast.Constant) and isinstance(idx.value, int):
			return int(idx.value)
		return None
	def _extract_jump_test_details (_test, _keys_aliases, _vel_alias_name, _consts):
		'''Parse jump tests like `keys[K_A]` and `keys[K_A] and vel[1] <= 0`.'''
		parts = []
		if isinstance(_test, ast.BoolOp) and isinstance(_test.op, ast.And):
			parts = list(_test.values or [])
		else:
			parts = [_test]
		key_name = None
		jump_vy_max = None
		for part in parts:
			part_key = _subscript_key_name(part)
			if part_key is not None:
				if isinstance(getattr(part, 'value', None), ast.Name) and part.value.id in _keys_aliases:
					key_name = part_key
					continue
				return (None, None)
			if isinstance(part, ast.Compare) and len(list(part.ops or [])) == 1 and len(list(part.comparators or [])) == 1:
				op = part.ops[0]
				lhs = part.left
				rhs = part.comparators[0]
				lhs_idx = _subscript_const_index(lhs)
				rhs_idx = _subscript_const_index(rhs)
				lhs_is_vel_y = isinstance(lhs, ast.Subscript) and isinstance(lhs.value, ast.Name) and lhs.value.id == _vel_alias_name and lhs_idx == 1
				rhs_is_vel_y = isinstance(rhs, ast.Subscript) and isinstance(rhs.value, ast.Name) and rhs.value.id == _vel_alias_name and rhs_idx == 1
				if lhs_is_vel_y and isinstance(op, (ast.Lt, ast.LtE)):
					c = _ast_small_int(rhs, _consts)
					if isinstance(c, int):
						upper = (c - 1) if isinstance(op, ast.Lt) else c
						jump_vy_max = upper if jump_vy_max is None else min(jump_vy_max, upper)
						continue
				if rhs_is_vel_y and isinstance(op, (ast.Gt, ast.GtE)):
					c = _ast_small_int(lhs, _consts)
					if isinstance(c, int):
						upper = (c - 1) if isinstance(op, ast.Gt) else c
						jump_vy_max = upper if jump_vy_max is None else min(jump_vy_max, upper)
						continue
			# Unknown dynamic guard: don't infer this branch for phase-1 script extraction.
			return (None, None)
		return (key_name, jump_vy_max)
	def _parse_update_code (_code, _target_keys, _allow_this_id = False):
		try:
			tree = ast.parse(_code or '')
		except Exception:
			return None
		aliases = {}
		consts = {}
		keys_aliases = set()
		vel_alias_name = None
		base_vx = 0
		base_vx_found = False
		base_vy = 0
		base_vy_found = False
		left_delta = 0
		right_delta = 0
		jump_y = None
		jump_vy_max = None
		target_hit = False
		for stmt in _walk_statically_reachable_stmts(getattr(tree, 'body', [])):
			if isinstance(stmt, ast.Assign):
				v = _ast_small_int(stmt.value, consts)
				for target in list(stmt.targets or []):
					if isinstance(target, ast.Name):
						if isinstance(v, int):
							consts[target.id] = v
						else:
							consts.pop(target.id, None)
						if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
							func = stmt.value.func
							if isinstance(func.value, ast.Name) and func.value.id == 'pygame' and func.attr == 'key':
								pass
						if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
							func = stmt.value.func
							if isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
								pass
					if isinstance(target, ast.Name):
						rb_kind, rb_value = _extract_rigidbody_name_expr(stmt.value)
						if rb_kind in ('name_ref', 'key', 'this_id'):
							aliases[target.id] = (rb_kind, rb_value)
						elif not (isinstance(stmt.value, ast.List) and len(stmt.value.elts) >= 2):
							aliases.pop(target.id, None)
					if isinstance(target, ast.Name):
						if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
							func = stmt.value.func
							if isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name) and func.value.value.id == 'pygame' and func.value.attr == 'key' and func.attr == 'get_pressed':
								keys_aliases.add(target.id)
						if isinstance(stmt.value, ast.List) and len(stmt.value.elts) >= 2:
							vel_alias_name = target.id
							vx_candidate = _ast_small_int(stmt.value.elts[0], consts)
							vy_candidate = _ast_small_int(stmt.value.elts[1], consts)
							if isinstance(vx_candidate, int):
								base_vx = vx_candidate
								base_vx_found = True
							if isinstance(vy_candidate, int):
								base_vy = vy_candidate
								base_vy_found = True
						elif vel_alias_name == target.id:
							vel_alias_name = None
			elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
				v = _ast_small_int(stmt.value, consts) if stmt.value is not None else None
				if isinstance(v, int):
					consts[stmt.target.id] = v
				else:
					consts.pop(stmt.target.id, None)
			elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
				call = stmt.value
				func = call.func
				if isinstance(func, ast.Attribute) and func.attr == 'set_linear_velocity' and isinstance(func.value, ast.Name) and func.value.id in ('sim', 'physics'):
					if len(call.args or []) >= 2:
						rb_kind, rb_value = _extract_rigidbody_name_expr(call.args[0])
						if rb_kind == 'name_ref' and rb_value in aliases:
							rb_kind, rb_value = aliases[rb_value]
						if (rb_kind == 'this_id' and bool(_allow_this_id)) or (rb_kind == 'key' and isinstance(rb_value, str) and rb_value in _target_keys):
							target_hit = True
							if isinstance(call.args[1], ast.Name):
								vel_alias_name = call.args[1].id
							else:
								vel_lit = _ast_numeric_vec2_literal(call.args[1])
								if vel_lit is not None:
									base_vx = int(round(float(vel_lit[0])))
									base_vx_found = True
									base_vy = int(round(float(vel_lit[1])))
									base_vy_found = True
			elif isinstance(stmt, ast.If):
				key_name, jump_guard_vy_max = _extract_jump_test_details(stmt.test, keys_aliases, vel_alias_name, consts)
				if key_name is None:
					continue
				for inner in _walk_statically_reachable_stmts(list(stmt.body or [])):
					if isinstance(inner, ast.AugAssign) and isinstance(inner.target, ast.Subscript):
						tgt = inner.target
						if not (isinstance(tgt.value, ast.Name) and tgt.value.id == vel_alias_name):
							continue
						idx = tgt.slice
						if hasattr(ast, 'Index') and isinstance(idx, ast.Index):
							idx = idx.value
						if not (isinstance(idx, ast.Constant) and isinstance(idx.value, int)):
							continue
						d = _ast_small_int(inner.value, consts)
						if not isinstance(d, int):
							continue
						if isinstance(inner.op, ast.Sub):
							d = -d
						if idx.value == 0:
							if key_name == 'K_LEFT':
								left_delta += d
							elif key_name == 'K_RIGHT':
								right_delta += d
					elif isinstance(inner, ast.Assign):
						for tgt in list(inner.targets or []):
							if not isinstance(tgt, ast.Subscript):
								continue
							if not (isinstance(tgt.value, ast.Name) and tgt.value.id == vel_alias_name):
								continue
							idx = tgt.slice
							if hasattr(ast, 'Index') and isinstance(idx, ast.Index):
								idx = idx.value
							if not (isinstance(idx, ast.Constant) and isinstance(idx.value, int) and idx.value == 1):
								continue
							j = _ast_small_int(inner.value, consts)
							if isinstance(j, int) and key_name == 'K_A':
								jump_y = j
								if isinstance(jump_guard_vy_max, int):
									if jump_vy_max is None:
										jump_vy_max = int(jump_guard_vy_max)
									else:
										jump_vy_max = min(int(jump_vy_max), int(jump_guard_vy_max))
		if not target_hit:
			return None
		if not base_vx_found:
			base_vx = 0
		if not base_vy_found:
			base_vy = 0
		return {
			'base_vx' : _gbc_clamp_signed_byte(int(base_vx)),
			'base_vy' : _gbc_clamp_signed_byte(int(base_vy)),
			'left_delta' : _gbc_clamp_signed_byte(int(left_delta)),
			'right_delta' : _gbc_clamp_signed_byte(int(right_delta)),
			'jump_y' : None if jump_y is None else _gbc_clamp_signed_byte(int(jump_y)),
			'jump_vy_max' : None if jump_vy_max is None else _gbc_clamp_signed_byte(int(jump_vy_max)),
		}
	if sprite_ob is None:
		return None
	target_keys = set()
	sprite_name = str(getattr(sprite_ob, 'name', '') or '')
	if sprite_name:
		target_keys.add(sprite_name)
		target_keys.add('_' + sprite_name)
	try:
		sprite_var = GetVarNameForObject(sprite_ob)
		if isinstance(sprite_var, str) and sprite_var:
			target_keys.add(sprite_var)
			target_keys.add('_' + sprite_var)
	except Exception:
		pass
	if not target_keys:
		return None
	update_codes = []
	init_codes = []
	if world is not None:
		for scriptInfo in list(GetScripts(world) or []):
			scriptTxt = scriptInfo[0]
			isInit = bool(scriptInfo[1])
			_type = scriptInfo[2]
			if _type != 'gbc-py':
				continue
			if isInit:
				init_codes.append((scriptTxt, False))
			else:
				update_codes.append((scriptTxt, False))
	for ob in list(getattr(bpy.data, 'objects', []) or []):
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		allow_this_id = _script_owner_matches_target_keys(str(getattr(ob, 'name', '') or ''), target_keys)
		for scriptInfo in list(GetScripts(ob) or []):
			scriptTxt = scriptInfo[0]
			isInit = bool(scriptInfo[1])
			_type = scriptInfo[2]
			if _type != 'gbc-py':
				continue
			scriptTxt = _rewrite_this_attributes_with_object_values(scriptTxt, ob)
			if isInit:
				init_codes.append((scriptTxt, allow_this_id))
			else:
				update_codes.append((scriptTxt, allow_this_id))
	for code, allow_this_id in (update_codes + init_codes):
		spec = _parse_update_code(code, target_keys, _allow_this_id = allow_this_id)
		if isinstance(spec, dict):
			return spec
	return None

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

def _gba_scroll_rgba_in_place (surf, dx : int, dy : int):
	if surf is None:
		return
	try:
		dx = int(dx)
		dy = int(dy)
	except Exception:
		return
	if dx == 0 and dy == 0:
		return
	h, w = surf.shape[0], surf.shape[1]
	dst_x0 = max(0, dx)
	dst_y0 = max(0, dy)
	dst_x1 = min(w, w + dx)
	dst_y1 = min(h, h + dy)
	if dst_x0 >= dst_x1 or dst_y0 >= dst_y1:
		return
	src_x0 = dst_x0 - dx
	src_y0 = dst_y0 - dy
	src_x1 = src_x0 + (dst_x1 - dst_x0)
	src_y1 = src_y0 + (dst_y1 - dst_y0)
	src = surf.copy()
	surf[dst_y0 : dst_y1, dst_x0 : dst_x1] = src[src_y0 : src_y1, src_x0 : src_x1]

def _gba_normalize_display_scroll_delta (dx : int, dy : int):
	# Display scroll deltas should not be wrapped by viewport size; preserve
	# full signed intent so camera-style movement can cross 16-bit ranges.
	try:
		dx_i = int(dx)
	except Exception:
		dx_i = 0
	try:
		dy_i = int(dy)
	except Exception:
		dy_i = 0
	return dx_i, dy_i

def _gbc_wrap_u16 (_v):
	try:
		return int(_v) & 0xFFFF
	except Exception:
		return 0

def _gbc_delta_u16 (_prev, _curr):
	prev = _gbc_wrap_u16(_prev)
	curr = _gbc_wrap_u16(_curr)
	delta = (curr - prev) & 0xFFFF
	if delta >= 0x8000:
		delta -= 0x10000
	return int(delta)

def _gbc_u16_to_signed (_v):
	v = _gbc_wrap_u16(_v)
	if v >= 0x8000:
		v -= 0x10000
	return int(v)

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
		cond = op.get('condition')
		if cond is not None and cond != '':
			cond_val = _eval_runtime_expr_value(cond, frame = frame, start_time = start_time)
			if cond_val is None or abs(float(cond_val)) <= 1e-9:
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
		elif _type == 'transform_surface_member' and member:
			src_owner = op.get('src_owner_name') or owner_name
			src_member = op.get('src_member')
			src = owner_members.get(src_owner, {}).get(src_member) if src_member else None
			if src is None:
				continue
			method = str(op.get('method') or '').strip().lower()
			transformed = src.copy()
			if method in ('scale', 'smoothscale'):
				size = op.get('size') or [src.shape[1], src.shape[0]]
				w_val = _eval_runtime_expr_value(size[0], frame = frame, start_time = start_time) if len(size) > 0 else src.shape[1]
				h_val = _eval_runtime_expr_value(size[1], frame = frame, start_time = start_time) if len(size) > 1 else src.shape[0]
				try:
					w = max(1, int(round(float(w_val))))
				except Exception:
					w = src.shape[1]
				try:
					h = max(1, int(round(float(h_val))))
				except Exception:
					h = src.shape[0]
				transformed = _gba_nn_resize_rgba(src, w, h)
			elif method == 'rotozoom':
				angle_val = _eval_runtime_expr_value(op.get('angle', 0.0), frame = frame, start_time = start_time)
				scale_val = _eval_runtime_expr_value(op.get('scale', 1.0), frame = frame, start_time = start_time)
				try:
					angle_deg = float(0.0 if angle_val is None else angle_val)
				except Exception:
					angle_deg = 0.0
				try:
					scale_factor = float(1.0 if scale_val is None else scale_val)
				except Exception:
					scale_factor = 1.0
				if abs(angle_deg) > 1e-10:
					transformed = _gba_rotate_rgba_degrees(transformed, angle_deg)
				if abs(scale_factor - 1.0) > 1e-10:
					tw = max(1, int(round(transformed.shape[1] * abs(scale_factor))))
					th = max(1, int(round(transformed.shape[0] * abs(scale_factor))))
					transformed = _gba_nn_resize_rgba(transformed, tw, th)
			members[member] = transformed
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
		elif _type == 'scroll_surface_member' and member:
			surf = members.get(member)
			if surf is None:
				continue
			dx_val = _eval_runtime_expr_value(op.get('dx', 0.0), frame = frame, start_time = start_time)
			dy_val = _eval_runtime_expr_value(op.get('dy', 0.0), frame = frame, start_time = start_time)
			try:
				dx = int(round(float(0.0 if dx_val is None else dx_val)))
				dy = int(round(float(0.0 if dy_val is None else dy_val)))
			except Exception:
				continue
			_gba_scroll_rgba_in_place(surf, dx, dy)
		elif _type == 'blit_surface_member' and member:
			dst = members.get(member)
			if dst is None:
				continue
			src_owner = op.get('src_owner_name') or owner_name
			src_member = op.get('src_member')
			src = owner_members.get(src_owner, {}).get(src_member) if src_member else None
			if src is None:
				continue
			x_val = _eval_runtime_expr_value(op.get('x', 0.0), frame = frame, start_time = start_time)
			y_val = _eval_runtime_expr_value(op.get('y', 0.0), frame = frame, start_time = start_time)
			try:
				x = int(round(float(0.0 if x_val is None else x_val)))
				y = int(round(float(0.0 if y_val is None else y_val)))
			except Exception:
				continue
			_gba_blit_rgba(dst, src, x, y, (1.0, 1.0, 1.0), 1.0)
	for owner_name in list(image_surfaces.keys()):
		override = owner_members.get(owner_name, {}).get('surface')
		if override is not None:
			image_surfaces[owner_name] = override
	return image_surfaces

def _gba_apply_display_op (canvas, op, owner_members = None, frame : int = None, start_time : float = None, camera_state = None):
	if not isinstance(op, dict):
		return
	extra_env = _runtime_expr_extra_env_for_display_op(op)
	cond = op.get('condition')
	if cond is not None and cond != '':
		cond_val = _eval_runtime_expr_value(cond, frame = frame, start_time = start_time, extra_env = extra_env)
		if cond_val is None or abs(float(cond_val)) <= 1e-9:
			return
	op_type = str(op.get('op') or '')
	if op_type == 'scroll_display_surface':
		dx_val = _eval_runtime_expr_value(op.get('dx', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		dy_val = _eval_runtime_expr_value(op.get('dy', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		try:
			dx = int(round(float(0.0 if dx_val is None else dx_val)))
			dy = int(round(float(0.0 if dy_val is None else dy_val)))
		except Exception:
			return
		dx, dy = _gba_normalize_display_scroll_delta(dx, dy)
		_gba_scroll_rgba_in_place(canvas, dx, dy)
		return
	if op_type == 'set_display_camera_pos':
		x_val = _eval_runtime_expr_value(op.get('x', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		y_val = _eval_runtime_expr_value(op.get('y', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		if x_val is None or y_val is None:
			_fallback_pos = _fallback_owner_camera_position(op, extra_env = extra_env)
			if isinstance(_fallback_pos, (list, tuple)) and len(_fallback_pos) >= 2:
				if x_val is None:
					x_val = float(_fallback_pos[0])
				if y_val is None:
					y_val = float(_fallback_pos[1])
		try:
			new_x = _gbc_wrap_u16(int(round(float(0.0 if x_val is None else x_val))))
			new_y = _gbc_wrap_u16(int(round(float(0.0 if y_val is None else y_val))))
		except Exception:
			return
		_trace_display_camera_eval(
			'apply_display_op',
			op,
			frame,
			op.get('x', 0.0),
			op.get('y', 0.0),
			x_val,
			y_val,
			new_x,
			new_y,
			extra_env = extra_env,
		)
		prev_x = _gbc_wrap_u16(0)
		prev_y = _gbc_wrap_u16(0)
		if isinstance(camera_state, dict):
			try:
				prev_x = _gbc_wrap_u16(camera_state.get('x', 0))
			except Exception:
				prev_x = _gbc_wrap_u16(0)
			try:
				prev_y = _gbc_wrap_u16(camera_state.get('y', 0))
			except Exception:
				prev_y = _gbc_wrap_u16(0)
		if isinstance(camera_state, dict):
			camera_state['x'] = _gbc_wrap_u16(new_x)
			camera_state['y'] = _gbc_wrap_u16(new_y)
		return
	if op_type == 'blit_display_surface':
		src_owner = op.get('src_owner_name')
		src_member = op.get('src_member')
		src = owner_members.get(src_owner, {}).get(src_member) if isinstance(owner_members, dict) and src_member else None
		if src is None:
			return
		x_val = _eval_runtime_expr_value(op.get('x', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		y_val = _eval_runtime_expr_value(op.get('y', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		try:
			x = int(round(float(0.0 if x_val is None else x_val)))
			y = int(round(float(0.0 if y_val is None else y_val)))
		except Exception:
			return
		cam_x = 0
		cam_y = 0
		if isinstance(camera_state, dict):
			cam_x = _gbc_u16_to_signed(camera_state.get('x', 0))
			cam_y = _gbc_u16_to_signed(camera_state.get('y', 0))
		x -= int(cam_x)
		y -= int(cam_y)
		_gba_blit_rgba(canvas, src, x, y, (1.0, 1.0, 1.0), 1.0)

def _gba_apply_display_draw_circles (canvas, script_runtime, image_surfaces = None, frame : int = None, start_time : float = None, camera_offset = None):
	if canvas is None:
		return canvas
	runtime = script_runtime or {}
	owner_members = {}
	initial_x = _gbc_wrap_u16(0)
	initial_y = _gbc_wrap_u16(0)
	if isinstance(camera_offset, (list, tuple)) and len(camera_offset) >= 2:
		try:
			initial_x = _gbc_wrap_u16(int(round(float(camera_offset[0]))))
		except Exception:
			initial_x = _gbc_wrap_u16(0)
		try:
			initial_y = _gbc_wrap_u16(int(round(float(camera_offset[1]))))
		except Exception:
			initial_y = _gbc_wrap_u16(0)
	camera_state = {'x' : int(initial_x), 'y' : int(initial_y)}
	camera_offset_signed = (
		float(_gbc_u16_to_signed(initial_x)),
		float(_gbc_u16_to_signed(initial_y)),
	)
	for owner_name, surf in (image_surfaces or {}).items():
		owner_members[owner_name] = {'surface' : surf}
	for circle in list(runtime.get('init_draw_circles') or []):
		_gba_draw_circle_from_script(canvas, circle, frame = frame, start_time = start_time, camera_offset = camera_offset_signed)
	for circle in list(runtime.get('update_draw_circles') or []):
		_gba_draw_circle_from_script(canvas, circle, frame = frame, start_time = start_time, camera_offset = camera_offset_signed)
	for op in list(runtime.get('init_display_ops') or []):
		_gba_apply_display_op(canvas, op, owner_members = owner_members, frame = frame, start_time = start_time, camera_state = camera_state)
	for op in list(runtime.get('update_display_ops') or []):
		_gba_apply_display_op(canvas, op, owner_members = owner_members, frame = frame, start_time = start_time, camera_state = camera_state)
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
	cam_x, cam_y = _gba_eval_display_camera_pos(script_runtime, frame = frame, include_update = True)
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
		_gba_blit_rgba(canvas, scaled, int(pos.x - cam_x), int(pos.y - cam_y), tint, ob.color[3])
	_gba_apply_display_draw_circles(
		canvas,
		script_runtime,
		image_surfaces = image_surfaces,
		frame = frame,
		camera_offset = [cam_x, cam_y],
	)
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

def _build_runtime_print_physics_env (world, scene_obs, use_gbc_signed_positions : bool = False, gbc_script_world_offset = None):
	if not bool(getattr(world, 'usePhysics', True)):
		return {}
	py_rapier = _gba_try_import_pyrapier2d()
	if not py_rapier:
		return {}
	physics_obs = [ob for ob in (scene_obs or []) if ob.exportOb and not ob.hide_get() and (getattr(ob, 'rigidBodyExists', False) or getattr(ob, 'colliderExists', False))]
	if not physics_obs:
		return {}
	try:
		sim = py_rapier.Simulation()
		sim.set_length_unit(float(world.unitLen))
		gravity = [0.0, 0.0]
		if bpy.context.scene.use_gravity:
			g = list(bpy.context.scene.gravity)
			gravity = [float(g[0]), float(g[1])]
		sim.set_gravity(gravity[0], gravity[1])
	except Exception:
		return {}
	rigid_bodies_by_name = {}
	rigid_bodies_named = {}
	colliders_named = {}
	for ob in physics_obs:
		if not getattr(ob, 'rigidBodyExists', False):
			continue
		try:
			pos, rot_deg = _gba_get_object_pose(ob)
			_type = RIGID_BODY_TYPES.index(ob.rigidBodyType) if ob.rigidBodyType in RIGID_BODY_TYPES else 0
			handle = sim.add_rigid_body(
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
		except Exception:
			continue
		rigid_bodies_by_name[ob.name] = handle
		for key in [ob.name, '_' + ob.name]:
			rigid_bodies_named.setdefault(key, handle)
		try:
			var_name = GetVarNameForObject(ob)
		except Exception:
			var_name = ''
		if isinstance(var_name, str) and var_name:
			for key in [var_name, '_' + var_name]:
				rigid_bodies_named.setdefault(key, handle)
	for ob in physics_obs:
		membership, filter_mask = _gba_get_collision_groups(ob)
		attach_targets = []
		for i in range(MAX_ATTACH_COLLIDER_CNT):
			if getattr(ob, 'attach%i' %i):
				attach_ob = getattr(ob, 'attachTo%i' %i)
				if attach_ob and attach_ob.name in rigid_bodies_by_name:
					attach_targets.append(rigid_bodies_by_name[attach_ob.name])
		if ob.name in rigid_bodies_by_name and not attach_targets:
			attach_targets = [rigid_bodies_by_name[ob.name]]
		if not getattr(ob, 'colliderExists', False):
			continue
		targets = attach_targets or [None]
		for idx, attach_to in enumerate(targets):
			try:
				collider_handle = _gba_add_cuboid_collider_for_object(sim, ob, membership, filter_mask, attach_to = attach_to)
			except Exception:
				continue
			if idx == 0:
				colliders_named.setdefault(ob.name, collider_handle)
				colliders_named.setdefault('_' + ob.name, collider_handle)
			else:
				key = ob.name + str(idx)
				colliders_named.setdefault(key, collider_handle)
				colliders_named.setdefault('_' + key, collider_handle)
	if use_gbc_signed_positions:
		offset_x = 0.0
		offset_y = 0.0
		try:
			if isinstance(gbc_script_world_offset, (list, tuple)) and len(gbc_script_world_offset) >= 2:
				offset_x = float(gbc_script_world_offset[0])
				offset_y = float(gbc_script_world_offset[1])
		except Exception:
			offset_x = 0.0
			offset_y = 0.0
		def _wrap_get_pos (_fn):
			def _wrapped (*args, **kwargs):
				try:
					pos = _fn(*args, **kwargs)
					return [
						(float(pos[0]) - float(_GBC_POSITION_BIAS)) + float(offset_x),
						(float(pos[1]) - float(_GBC_POSITION_BIAS)) - float(offset_y),
					]
				except Exception:
					return [0.0, 0.0]
			return _wrapped
		def _wrap_set_pos (_fn):
			def _wrapped (*args, **kwargs):
				args_list = list(args)
				if len(args_list) >= 2:
					try:
						pos = args_list[1]
						local_x = float(pos[0]) - float(offset_x)
						local_y = float(pos[1]) - float(offset_y)
						args_list[1] = [
							(local_x + float(_GBC_POSITION_BIAS)) % 65536.0,
							((-local_y) + float(_GBC_POSITION_BIAS)) % 65536.0,
						]
					except Exception:
						pass
				return _fn(*tuple(args_list), **kwargs)
			return _wrapped
		if hasattr(sim, 'get_rigid_body_position'):
			try:
				sim.get_rigid_body_position = _wrap_get_pos(sim.get_rigid_body_position)
			except Exception:
				pass
		if hasattr(sim, 'set_rigid_body_position'):
			try:
				sim.set_rigid_body_position = _wrap_set_pos(sim.set_rigid_body_position)
			except Exception:
				pass
		if hasattr(sim, 'get_collider_position'):
			try:
				sim.get_collider_position = _wrap_get_pos(sim.get_collider_position)
			except Exception:
				pass
		if hasattr(sim, 'set_collider_position'):
			try:
				sim.set_collider_position = _wrap_set_pos(sim.set_collider_position)
			except Exception:
				pass
	return {
		'objects' : {},
		'sim' : sim,
		'physics' : sim,
		'rigidBodies' : rigid_bodies_named,
		'rbs' : rigid_bodies_named,
		'rigidBodiesIds' : rigid_bodies_named,
		'colliders' : colliders_named,
		'cols' : colliders_named,
		'collidersIds' : colliders_named,
	}

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
		# Runtime physics/object transforms use image center coordinates.
		# Derive center from GetImagePosition so image-position math stays
		# consistent across export paths.
		pos = GetImageCenterPosition(ob)
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
	if list(runtime.get('update_display_ops') or []):
		return True
	for op in list(runtime.get('surface_ops') or []):
		if not bool(op.get('is_init', True)):
			return True
	return False

def _gba_eval_display_scroll_offset (script_runtime, frame : int = 1, start_time : float = None, include_update : bool = False):
	runtime = script_runtime or {}
	ops = []
	ops.extend(list(runtime.get('init_display_ops') or []))
	if include_update:
		ops.extend(list(runtime.get('update_display_ops') or []))
	dx_total = 0
	dy_total = 0
	camera_x = _gbc_wrap_u16(0)
	camera_y = _gbc_wrap_u16(0)
	for op in ops:
		if not isinstance(op, dict):
			continue
		extra_env = _runtime_expr_extra_env_for_display_op(op)
		op_type = str(op.get('op') or '')
		cond = op.get('condition')
		if cond is not None and cond != '':
			cond_val = _eval_runtime_expr_value(cond, frame = frame, start_time = start_time, extra_env = extra_env)
			if cond_val is None or abs(float(cond_val)) <= 1e-9:
				continue
		if op_type == 'scroll_display_surface':
			dx_val = _eval_runtime_expr_value(op.get('dx', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
			dy_val = _eval_runtime_expr_value(op.get('dy', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
			try:
				dx = int(round(float(0.0 if dx_val is None else dx_val)))
				dy = int(round(float(0.0 if dy_val is None else dy_val)))
			except Exception:
				continue
			dx, dy = _gba_normalize_display_scroll_delta(dx, dy)
			dx_total += dx
			dy_total += dy
			continue
		if op_type == 'set_display_camera_pos':
			x_val = _eval_runtime_expr_value(op.get('x', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
			y_val = _eval_runtime_expr_value(op.get('y', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
			if x_val is None or y_val is None:
				_fallback_pos = _fallback_owner_camera_position(op, extra_env = extra_env)
				if isinstance(_fallback_pos, (list, tuple)) and len(_fallback_pos) >= 2:
					if x_val is None:
						x_val = float(_fallback_pos[0])
					if y_val is None:
						y_val = float(_fallback_pos[1])
			try:
				new_x = _gbc_wrap_u16(int(round(float(0.0 if x_val is None else x_val))))
				new_y = _gbc_wrap_u16(int(round(float(0.0 if y_val is None else y_val))))
			except Exception:
				continue
			dx = -_gbc_delta_u16(camera_x, new_x)
			dy = -_gbc_delta_u16(camera_y, new_y)
			camera_x = _gbc_wrap_u16(new_x)
			camera_y = _gbc_wrap_u16(new_y)
			dx_total += dx
			dy_total += dy
	return int(dx_total), int(dy_total)

def _gba_eval_display_camera_pos (script_runtime, frame : int = 1, start_time : float = None, include_update : bool = True):
	runtime = script_runtime or {}
	ops = []
	ops.extend(list(runtime.get('init_display_ops') or []))
	if include_update:
		ops.extend(list(runtime.get('update_display_ops') or []))
	camera_x = _gbc_wrap_u16(0)
	camera_y = _gbc_wrap_u16(0)
	for op in ops:
		if not isinstance(op, dict):
			continue
		extra_env = _runtime_expr_extra_env_for_display_op(op)
		if str(op.get('op') or '') != 'set_display_camera_pos':
			continue
		cond = op.get('condition')
		if cond is not None and cond != '':
			cond_val = _eval_runtime_expr_value(cond, frame = frame, start_time = start_time, extra_env = extra_env)
			if cond_val is None or abs(float(cond_val)) <= 1e-9:
				continue
		x_val = _eval_runtime_expr_value(op.get('x', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		y_val = _eval_runtime_expr_value(op.get('y', 0.0), frame = frame, start_time = start_time, extra_env = extra_env)
		if x_val is None or y_val is None:
			_fallback_pos = _fallback_owner_camera_position(op, extra_env = extra_env)
			if isinstance(_fallback_pos, (list, tuple)) and len(_fallback_pos) >= 2:
				if x_val is None:
					x_val = float(_fallback_pos[0])
				if y_val is None:
					y_val = float(_fallback_pos[1])
		try:
			camera_x = _gbc_wrap_u16(int(round(float(0.0 if x_val is None else x_val))))
			camera_y = _gbc_wrap_u16(int(round(float(0.0 if y_val is None else y_val))))
		except Exception:
			continue
		_trace_display_camera_eval(
			'eval_display_camera_pos',
			op,
			frame,
			op.get('x', 0.0),
			op.get('y', 0.0),
			x_val,
			y_val,
			camera_x,
			camera_y,
			extra_env = extra_env,
		)
	return _gbc_u16_to_signed(camera_x), _gbc_u16_to_signed(camera_y)

def _gba_has_set_camera_ops (script_runtime):
	runtime = script_runtime or {}
	for _op in list(runtime.get('init_display_ops') or []):
		if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
			return True
	for _op in list(runtime.get('update_display_ops') or []):
		if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
			return True
	return False

def _gbc_shift_collider_rects_by_camera (rects, cam_x : int = 0, cam_y : int = 0):
	try:
		cx = int(round(float(cam_x)))
	except Exception:
		cx = 0
	try:
		cy = int(round(float(cam_y)))
	except Exception:
		cy = 0
	out = []
	for rect in list(rects or []):
		try:
			x, y, w, h = [int(v) for v in rect]
		except Exception:
			continue
		out.append([int(x - cx), int(y - cy), int(w), int(h)])
	return out

def _gba_get_runtime_display_scroll_profile (script_runtime, frame : int = 1, start_time : float = None):
	runtime = script_runtime or {}
	has_camera_ops = False
	for _op in list(runtime.get('init_display_ops') or []):
		if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
			has_camera_ops = True
			break
	if not has_camera_ops:
		for _op in list(runtime.get('update_display_ops') or []):
			if isinstance(_op, dict) and str(_op.get('op') or '') == 'set_display_camera_pos':
				has_camera_ops = True
				break
	if has_camera_ops:
		# set_camera_position is an absolute camera command. We cannot replay full
		# per-frame script evaluation in the fixed-step phase1 runtime, so bake
		# the resolved frame-1 camera offset into init scroll and disable drift.
		total_dx, total_dy = _gba_eval_display_scroll_offset(
			script_runtime,
			frame = frame,
			start_time = start_time,
			include_update = True,
		)
		return {
			'init_dx' : int(total_dx),
			'init_dy' : int(total_dy),
			'step_dx' : 0,
			'step_dy' : 0,
		}
	init_dx, init_dy = _gba_eval_display_scroll_offset(
		script_runtime,
		frame = frame,
		start_time = start_time,
		include_update = False,
	)
	total_dx, total_dy = _gba_eval_display_scroll_offset(
		script_runtime,
		frame = frame,
		start_time = start_time,
		include_update = True,
	)
	return {
		'init_dx' : int(init_dx),
		'init_dy' : int(init_dy),
		'step_dx' : int(total_dx - init_dx),
		'step_dy' : int(total_dy - init_dy),
	}

def _gba_runtime_without_display_scroll (script_runtime):
	runtime = dict(script_runtime or {})
	runtime['init_display_ops'] = [
		op for op in list(runtime.get('init_display_ops') or [])
		if not (
			isinstance(op, dict)
			and str(op.get('op') or '') in ('scroll_display_surface', 'set_display_camera_pos')
		)
	]
	runtime['update_display_ops'] = [
		op for op in list(runtime.get('update_display_ops') or [])
		if not (
			isinstance(op, dict)
			and str(op.get('op') or '') in ('scroll_display_surface', 'set_display_camera_pos')
		)
	]
	return runtime

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
		r'\n\t\.weak py2gb(?:a)?_builtin_print\n\t\.thumb_func\npy2gb(?:a)?_builtin_print:\n\tbx\tlr\n',
		'\n',
		script_asm,
		flags = re.MULTILINE,
	)
	init_calls = '\n'.join('\tbl\t' + sym for sym in init_symbols) if init_symbols else '\t@ no init script calls'
	update_calls = '\n'.join('\tbl\t' + sym for sym in update_symbols) if update_symbols else '\t@ no update script calls'
	main_loop_body = '\n'.join([
		'\tbl\tpy2gb_wait_vblank',
		'\t@ no baked frame playback; keep VRAM live between updates',
		'\tbl\tpy2gb_call_update',
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
\tbl\tpy2gb_blit_frame
\tbl\tpy2gb_call_init
gba_main_loop:
{main_loop_body}
\tb\tgba_main_loop

.thumb_func
py2gb_wait_vblank:
\tldr\tr1, =0x04000006
py2gb_wait_vblank_end:
\tldrh\tr0, [r1]
\tcmp\tr0, #160
\tbhs\tpy2gb_wait_vblank_end
py2gb_wait_vblank_start:
\tldrh\tr0, [r1]
\tcmp\tr0, #160
\tblo\tpy2gb_wait_vblank_start
\tbx\tlr

.thumb_func
py2gb_blit_frame:
\tpush\t{{r4-r7, lr}}
\tldr\tr6, =0x0203FFFC
\tldr\tr1, [r6]
\tldr\tr2, =0x06000000
\tldr\tr3, =240 * 160 * 2
py2gb_blit_copy_loop:
\tldr\tr4, [r1]
\tstr\tr4, [r2]
\tadds\tr1, #4
\tadds\tr2, #4
\tsubs\tr3, #4
\tbne\tpy2gb_blit_copy_loop
\tldr\tr0, =0x{frame_stride:08X}
\tadds\tr1, r0
\tldr\tr0, =0x{frame_end_rom:08X}
\tcmp\tr1, r0
\tblo\tpy2gb_blit_store
\tldr\tr1, =0x{frame_base_rom:08X}
py2gb_blit_store:
\tstr\tr1, [r6]
\tpop\t{{r4-r7, pc}}

.thumb_func
py2gb_call_init:
\tpush\t{{lr}}
{init_calls}
\tpop\t{{pc}}

.thumb_func
py2gb_call_update:
\tpush\t{{lr}}
{update_calls}
\tpop\t{{pc}}

.global py2gb_builtin_print
.global py2gba_builtin_print
.thumb_func
py2gb_builtin_print:
py2gba_builtin_print:
\tpush\t{{r1-r7, lr}}
\tldr\tr1, =0x04FFF780
\tldr\tr2, =0x0000C0DE
\tstrh\tr2, [r1]
\tldrh\tr2, [r1]
\tldr\tr3, =0x00001DEA
\tcmp\tr2, r3
\tbne\tpy2gb_print_done
\tldr\tr1, =0x04FFF600
\tadds\tr2, r0, #0
\tmovs\tr6, #0
py2gb_print_copy:
\tcmp\tr6, #255
\tbhs\tpy2gb_print_copy_end
\tldrb\tr3, [r2]
\tstrb\tr3, [r1]
\tadds\tr2, #1
\tadds\tr1, #1
\tadds\tr6, #1
\tcmp\tr3, #0
\tbne\tpy2gb_print_copy
\tb\tpy2gb_print_after_copy
py2gb_print_copy_end:
\tmovs\tr3, #0
\tstrb\tr3, [r1]
py2gb_print_after_copy:
\tsubs\tr1, #1
\tldr\tr4, =py2gb_print_counter
\tldrb\tr5, [r4]
\tadds\tr5, #1
\tstrb\tr5, [r4]
\tmovs\tr3, #32
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tmovs\tr3, #91
\tstrb\tr3, [r1]
\tadds\tr1, #1
\tldr\tr6, =py2gb_hex_chars
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
py2gb_print_done:
\tpop\t{{r1-r7, pc}}

\t.align 2
py2gb_print_counter:
\t.word 0
py2gb_hex_chars:
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

def _extend_runtime_print_scene_with_offscene_script_physics (scene_obs, script_type):
	out = list(scene_obs or [])
	seen = set(out)
	for ob in bpy.data.objects:
		if ob in seen:
			continue
		if not getattr(ob, 'exportOb', False) or ob.hide_get():
			continue
		if not (getattr(ob, 'rigidBodyExists', False) or getattr(ob, 'colliderExists', False)):
			continue
		has_matching_script = False
		for scriptInfo in GetScripts(ob):
			if str(scriptInfo[2]) == str(script_type):
				has_matching_script = True
				break
		if not has_matching_script:
			continue
		out.append(ob)
		seen.add(ob)
	return out

def _gb_runtime_is_stubbed (script_runtime):
	asm_path = (script_runtime or {}).get('assembly_path')
	if not asm_path or not os.path.isfile(asm_path):
		return False
	try:
		asm_txt = open(asm_path, 'r', encoding = 'utf-8').read(512)
	except Exception:
		return False
	return ('py2gb pygame-aware stub backend' in asm_txt) or ('py2gba pygame-aware stub backend' in asm_txt)

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
					'GBA dynamic physics requires a full py2gb compiler/runtime; the current py2gb backend is a pygame stub. '
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
			runtime_print_scene_obs = _extend_runtime_print_scene_with_offscene_script_physics(scene_obs, 'gba-py')
			runtime_print_env = _build_runtime_print_physics_env(world, runtime_print_scene_obs)
			mirror_step = None
			sim_runtime = runtime_print_env.get('sim')
			if sim_runtime is not None and hasattr(sim_runtime, 'step'):
				mirror_step = sim_runtime.step
			_start_gba_update_print_mirror(
				proc,
				script_runtime,
				strict_print_exprs = False,
				runtime_env = runtime_print_env,
				mirror_step = mirror_step,
			)
		except FileNotFoundError:
			print('mgba-qt not found in PATH; open the ROM manually:', rom_path)
	finally:
		PostBuild ()

def BuildGbc (world):
	PreBuild ()
	try:
		_append_gbc_trace_lines([
			'[gbc-trace] BuildGbc:start blend=' + str(getattr(bpy.data, 'filepath', '')),
			'[gbc-trace] BuildGbc:cwd=' + str(os.getcwd()),
		])
		try:
			import numpy
		except ImportError:
			raise RuntimeError('GBC export needs NumPy.')
		scene_obs_all = list(bpy.context.scene.collection.all_objects)
		instanced_template_obs = GetInstancedCollectionTemplateObjects(bpy.context.scene)
		in_prefab_coll = set()
		in_non_prefab_coll = set()
		for coll in bpy.data.collections:
			export_prefab = bool(getattr(coll, 'exportPrefab', False))
			for ob in coll.all_objects:
				if export_prefab:
					in_prefab_coll.add(ob)
				else:
					in_non_prefab_coll.add(ob)
		# Match main export behavior: template-only prefab objects should not be
		# rendered/exported directly unless they are explicitly instanced copies.
		template_only_obs = set(in_prefab_coll - in_non_prefab_coll)
		scene_obs = [
			ob for ob in scene_obs_all
			if ob not in instanced_template_obs and ob not in template_only_obs
		]
		scene_instance_obs = [
			ob for ob in scene_obs
			if getattr(ob, 'instance_type', None) == 'COLLECTION' and getattr(ob, 'instance_collection', None)
		]
		_append_gbc_trace_lines([
			'[gbc-trace] BuildGbc:scene_objects_all=' + str(len(scene_obs_all)),
			'[gbc-trace] BuildGbc:scene_objects_filtered=' + str(len(scene_obs)),
			'[gbc-trace] BuildGbc:template_only_count=' + str(len(template_only_obs)),
			'[gbc-trace] BuildGbc:instanced_template_count=' + str(len(instanced_template_obs)),
			'[gbc-trace] BuildGbc:collection_instance_count=' + str(len(scene_instance_obs)),
			'[gbc-trace] BuildGbc:collection_instances=' + (
				', '.join([str(ob.name) + '->' + str(getattr(getattr(ob, 'instance_collection', None), 'name', '?')) for ob in scene_instance_obs])
				if scene_instance_obs else '<none>'
			),
		])
		gbc_imgs = []
		for ob in scene_obs:
			if not ob.exportOb or ob.hide_get():
				continue
			if ob.type != 'EMPTY' or ob.empty_display_type != 'IMAGE' or not ob.data or not ob.data.filepath:
				continue
			gbc_imgs.append(ob)
		scene_gbc_imgs = list(gbc_imgs)
		fallback_spawn_entries = []
		fallback_spawn_source_names = {}
		fallback_spawn_physics_source_names = {}
		fallback_spawn_owner_direct_overrides = {}
		fallback_draw_template_obs = []
		fallback_surface_source_obs = []
		fallback_spawn_physics_obs = []
		fallback_spawn_physics_debug = []
		if True:
			# Fallback path: when gbc-py backend is unavailable, honor direct
			# spawn_prefab("CollectionName", ...) calls by baking explicit prefab
			# spawns when the call arguments are statically resolvable.
			fallback_spawn_calls = list(_collect_gbc_spawn_prefab_requests()) if (not bool(_py2gb_export_gba_py_assembly)) else []
			# Auto-spawn scene collection instances so prefab templates referenced
			# by instance empties render even without explicit spawn_prefab calls.
			for inst_ob in scene_instance_obs:
				if not getattr(inst_ob, 'exportOb', False) or inst_ob.hide_get():
					continue
				if getattr(inst_ob, 'instance_type', None) != 'COLLECTION':
					continue
				inst_coll = getattr(inst_ob, 'instance_collection', None)
				if not inst_coll or not getattr(inst_coll, 'exportPrefab', False):
					continue
				try:
					wm_pos = inst_ob.matrix_world.to_translation()
					wm_rot = inst_ob.matrix_world.to_euler('XYZ')
					world = bpy.data.worlds[0]
					scale = float(getattr(world, 'exportScale', 1.0))
					off = Vector(getattr(world, 'exportOff', [0.0, 0.0]))
					inst_x = float(wm_pos.x * scale + off.x)
					inst_y_down = float(-wm_pos.y * scale + off.y)
					# spawn_prefab fallback call positions use script-space Y-up.
					inst_y = float(-inst_y_down)
					inst_rot = float(-math.degrees(wm_rot.z))
				except Exception:
					world = bpy.data.worlds[0]
					scale = float(getattr(world, 'exportScale', 1.0))
					off = Vector(getattr(world, 'exportOff', [0.0, 0.0]))
					loc = getattr(inst_ob, 'location', Vector((0.0, 0.0, 0.0)))
					inst_x = float(float(loc.x) * scale + off.x)
					inst_y_down = float(-float(loc.y) * scale + off.y)
					inst_y = float(-inst_y_down)
					inst_rot = float(-math.degrees(getattr(inst_ob.rotation_euler, 'z', 0.0)))
				fallback_spawn_calls.append({
					'prefab_name' : str(inst_coll.name),
					'pos' : [inst_x, inst_y],
					'rot' : float(inst_rot),
					# Preserve one fallback spawn per scene instance empty.
					'scene_instance_name' : str(getattr(inst_ob, 'name', '') or ''),
				})
			raw_spawn_call_count = len(fallback_spawn_calls)
			deduped_spawn_calls = []
			seen_spawn_keys = set()
			for call in fallback_spawn_calls:
				prefab_name = str(call.get('prefab_name', '') or '')
				pos_val = call.get('pos', None)
				rot_val = float(call.get('rot', 0.0) or 0.0)
				scene_instance_name = str(call.get('scene_instance_name', '') or '')
				if pos_val is None:
					# Dynamic/unresolved calls cannot be safely deduped by pose.
					deduped_spawn_calls.append(call)
					continue
				x = float(pos_val[0]) if len(pos_val) > 0 else 0.0
				y = float(pos_val[1]) if len(pos_val) > 1 else 0.0
				key = (
					prefab_name,
					round(x, 4),
					round(y, 4),
					round(rot_val, 4),
					scene_instance_name,
				)
				if key in seen_spawn_keys:
					continue
				seen_spawn_keys.add(key)
				deduped_spawn_calls.append(call)
			fallback_spawn_calls = deduped_spawn_calls
			requested_prefabs = sorted({ str(call.get('prefab_name', '') or '') for call in fallback_spawn_calls if str(call.get('prefab_name', '') or '') != '' })
			added = []
			baked = []
			if fallback_spawn_calls:
				seen = set(gbc_imgs)
				for call_idx, call in enumerate(fallback_spawn_calls):
					prefab_name = str(call.get('prefab_name', '') or '')
					if prefab_name == '':
						continue
					spawn_pos = call.get('pos', None)
					try:
						spawn_x = float(spawn_pos[0]) if (spawn_pos is not None and len(spawn_pos) > 0) else 0.0
						spawn_y = float(spawn_pos[1]) if (spawn_pos is not None and len(spawn_pos) > 1) else 0.0
					except Exception:
						spawn_x = 0.0
						spawn_y = 0.0
					# Seed direct spawn-owner coordinates even when draw/physics proxy
					# baking is skipped; phase1 print mirror can consume these keys.
					fallback_spawn_owner_direct_overrides['__gbc_spawn_%i_%s' %(call_idx, prefab_name)] = [spawn_x, spawn_y]
					fallback_spawn_owner_direct_overrides['__gbc_spawnphys_%i_%s' %(call_idx, prefab_name)] = [spawn_x, spawn_y]
					coll = bpy.data.collections.get(prefab_name)
					if not coll or not getattr(coll, 'exportPrefab', False):
						continue
					prefab_imgs = []
					prefab_export_obs = []
					for ob in coll.all_objects:
						if not ob.exportOb or ob.hide_get():
							continue
						prefab_export_obs.append(ob)
						if ob.type != 'EMPTY' or ob.empty_display_type != 'IMAGE' or not ob.data or not ob.data.filepath:
							continue
						prefab_imgs.append(ob)
					for ob in prefab_export_obs:
						ob_name = str(getattr(ob, 'name', '') or '')
						if ob_name != '':
							fallback_spawn_owner_direct_overrides['__gbc_spawn_%i_%s' %(call_idx, ob_name)] = [spawn_x, spawn_y]
							fallback_spawn_owner_direct_overrides['__gbc_spawnphys_%i_%s' %(call_idx, ob_name)] = [spawn_x, spawn_y]
					if not prefab_imgs:
						continue
					# Fallback spawn calls use gbc/js-style screen-space rotation
					# (clockwise-positive in Y-down space). The compositor's software
					# rotate path is counterclockwise-positive, so mirror sign here.
					spawn_rot = -float(call.get('rot', 0.0) or 0.0)
					if spawn_pos is None:
						# If static position cannot be resolved, preserve old behavior
						# by including the template objects at their authored coords.
						for ob in prefab_imgs:
							if ob in seen:
								continue
							gbc_imgs.append(ob)
							seen.add(ob)
							fallback_draw_template_obs.append(ob)
							added.append(ob.name)
						continue
					image_obs_by_name = {ob.name : ob for ob in prefab_imgs}
					coll_set = set(coll.all_objects)
					root_candidates = [ob for ob in prefab_export_obs if ob.parent not in coll_set or ob.parent is None]
					anchor_ob = root_candidates[0] if root_candidates else prefab_export_obs[0]
					scene_instance_name = str(call.get('scene_instance_name', '') or '')
					def _get_fallback_pose (src_ob):
						# GBC rendering uses screen-space Y-down coordinates, so authored
						# Blender Z rotation must be mirrored to preserve visual direction.
						rot_deg = -math.degrees(src_ob.rotation_euler.z)
						if src_ob.type == 'EMPTY' and src_ob.empty_display_type == 'IMAGE' and getattr(src_ob, 'data', None):
							return GetImageCenterPosition(src_ob), float(rot_deg)
						return Vector((float(src_ob.location.x), float(-src_ob.location.y), 0.0)), float(rot_deg)
					if scene_instance_name != '':
						# Scene collection instances should anchor prefab children to the
						# collection origin/instance offset, not the first root object.
						try:
							inst_off = getattr(coll, 'instance_offset', Vector((0.0, 0.0, 0.0)))
							anchor_pos = Vector((float(inst_off[0]), float(-inst_off[1]), 0.0))
						except Exception:
							anchor_pos = Vector((0.0, 0.0, 0.0))
						anchor_rot = 0.0
					else:
						anchor_pos, anchor_rot = _get_fallback_pose(anchor_ob)
					req_x_gbc = float(spawn_pos[0]) if len(spawn_pos) > 0 else 0.0
					req_y_gbc = -float(spawn_pos[1]) if len(spawn_pos) > 1 else 0.0
					# Fallback spawn calls come from gbc-py scripts; map their GBC
					# screen-space coords into the 240x160 composite space.
					req_x, req_y = _gbc_to_gba_cover_point(req_x_gbc, req_y_gbc)
					def _rotated_bbox_origin_offset (_w, _h, _angle_deg):
						if abs(float(_angle_deg)) < 1e-7:
							return (0.0, 0.0)
						w = max(1.0, float(_w))
						h = max(1.0, float(_h))
						rad = math.radians(float(_angle_deg))
						cos_a = math.cos(rad)
						sin_a = math.sin(rad)
						cx = (w - 1.0) * 0.5
						cy = (h - 1.0) * 0.5
						def _rot_fwd (px, py):
							dx = float(px) - cx
							dy = float(py) - cy
							return (
								dx * cos_a + dy * sin_a + cx,
								-dx * sin_a + dy * cos_a + cy,
							)
						minx = float('inf')
						miny = float('inf')
						for px, py in ((0.0, 0.0), (w - 1.0, 0.0), (w - 1.0, h - 1.0), (0.0, h - 1.0)):
							qx, qy = _rot_fwd(px, py)
							minx = min(minx, qx)
							miny = min(miny, qy)
						ox0 = float(math.floor(minx + 1e-9))
						oy0 = float(math.floor(miny + 1e-9))
						return (ox0, oy0)
					def _image_center_to_topleft (_src_ob, _center_x, _center_y, _world_rot_deg):
						size = _src_ob.scale * _src_ob.empty_display_size
						try:
							_img_data = getattr(_src_ob, 'data', None)
							_img_size = Vector(list(_img_data.size) + [0]) if _img_data else None
						except Exception:
							_img_size = None
						if _img_size is not None and _img_size.x != 0 and _img_size.y != 0:
							if _img_size.x > _img_size.y:
								size.x *= _img_size.x / _img_size.y
							else:
								size.y *= _img_size.y / _img_size.x
						# Match compositor dimensions exactly.
						tw = max(1, int(round(abs(float(size.x)))))
						th = max(1, int(round(abs(float(size.y)))))
						ox0, oy0 = _rotated_bbox_origin_offset(tw, th, float(_world_rot_deg))
						cx = (float(tw) - 1.0) * 0.5
						cy = (float(th) - 1.0) * 0.5
						# _gba_rotate_rgba_degrees keeps source center at (cx - ox0, cy - oy0)
						# in rotated output space, so place that point at requested center.
						return Vector((float(_center_x) - cx + ox0, float(_center_y) - cy + oy0, 0.0))
					def _spawn_proxy_for_template_node (template_id, world_x, world_y, world_rot):
						src_ob = image_obs_by_name.get(template_id)
						if src_ob is None:
							return
						proxy = type('SpawnImageProxy', (), {})()
						proxy.name = '__gbc_spawn_%i_%s' %(call_idx, src_ob.name)
						proxy.type = 'EMPTY'
						proxy.empty_display_type = 'IMAGE'
						proxy.data = src_ob.data
						proxy.scale = src_ob.scale
						proxy.empty_display_size = src_ob.empty_display_size
						proxy.empty_image_offset = getattr(src_ob, 'empty_image_offset', [0.0, 0.0])
						proxy.tint = src_ob.tint
						proxy.color = src_ob.color
						# Keep helper rotation aligned with draw overrides.
						proxy_rot_deg = float(world_rot)
						proxy.rotation_euler = Vector((0.0, 0.0, math.radians(proxy_rot_deg)))
						# Keep proxy.location at spawned center; derive draw top-left via
						# GetImagePosition, then add rotated-bbox origin offset to match
						# _gba_rotate_rgba_degrees expansion behavior.
						proxy.location = Vector((float(world_x), float(-world_y), 0.0))
						draw_pos = _image_center_to_topleft(src_ob, world_x, world_y, proxy_rot_deg)
						fallback_spawn_entries.append((proxy, {
							'x' : float(draw_pos.x),
							'y' : float(draw_pos.y),
							'rot_deg' : float(world_rot),
						}))
						fallback_spawn_source_names[proxy.name] = src_ob.name
						baked.append(proxy.name + '<-' + src_ob.name + '@gba(' + str(TryChangeToInt(draw_pos.x)) + ',' + str(TryChangeToInt(draw_pos.y)) + ')')
						if src_ob not in fallback_surface_source_obs:
							fallback_surface_source_obs.append(src_ob)
					def _spawn_proxy_for_physics (src_ob, world_x, world_y, world_rot):
						proxy = type('SpawnPhysicsProxy', (), {})()
						proxy.name = '__gbc_spawnphys_%i_%s' %(call_idx, src_ob.name)
						proxy.drawProxyName = '__gbc_spawn_%i_%s' %(call_idx, src_ob.name)
						proxy.exportOb = True
						proxy.type = src_ob.type
						proxy.empty_display_type = getattr(src_ob, 'empty_display_type', '')
						proxy.data = getattr(src_ob, 'data', None)
						proxy.scale = src_ob.scale
						proxy.empty_display_size = getattr(src_ob, 'empty_display_size', 1.0)
						proxy.empty_image_offset = getattr(src_ob, 'empty_image_offset', [0.0, 0.0])
						proxy.tint = getattr(src_ob, 'tint', [1.0, 1.0, 1.0])
						proxy.color = getattr(src_ob, 'color', [1.0, 1.0, 1.0, 1.0])
						# Keep proxy helper rotation sign aligned with draw overrides.
						proxy_rot_deg = float(world_rot)
						proxy.rotation_euler = Vector((0.0, 0.0, math.radians(proxy_rot_deg)))
						# Keep physics proxy origin at spawned center.
						loc_x = float(world_x)
						loc_y = -float(world_y)
						proxy.location = Vector((loc_x, loc_y, 0.0))
						proxy.rigidBodyExists = bool(getattr(src_ob, 'rigidBodyExists', False))
						proxy.rigidBodyEnable = bool(getattr(src_ob, 'rigidBodyEnable', True))
						proxy.rigidBodyType = str(getattr(src_ob, 'rigidBodyType', ''))
						proxy.gravityScale = float(getattr(src_ob, 'gravityScale', 1.0))
						proxy.dominance = int(getattr(src_ob, 'dominance', 0))
						proxy.canRot = bool(getattr(src_ob, 'canRot', True))
						proxy.linearDrag = float(getattr(src_ob, 'linearDrag', 0.0))
						proxy.angDrag = float(getattr(src_ob, 'angDrag', 0.0))
						proxy.canSleep = bool(getattr(src_ob, 'canSleep', True))
						proxy.continuousCollideDetect = bool(getattr(src_ob, 'continuousCollideDetect', False))
						proxy.colliderExists = bool(getattr(src_ob, 'colliderExists', False))
						proxy.colliderEnable = bool(getattr(src_ob, 'colliderEnable', True))
						proxy.colliderShapeType = str(getattr(src_ob, 'colliderShapeType', ''))
						proxy.colliderSize = list(getattr(src_ob, 'colliderSize', [0.0, 0.0]))
						proxy.colliderRadius = float(getattr(src_ob, 'colliderRadius', 0.0))
						proxy.colliderCapsuleRadius = float(getattr(src_ob, 'colliderCapsuleRadius', 0.0))
						proxy.colliderCapsuleHeight = float(getattr(src_ob, 'colliderCapsuleHeight', 0.0))
						proxy.colliderIsVertical = bool(getattr(src_ob, 'colliderIsVertical', True))
						proxy.colliderPosOff = list(getattr(src_ob, 'colliderPosOff', [0.0, 0.0]))
						proxy.colliderRotOff = float(getattr(src_ob, 'colliderRotOff', 0.0))
						proxy.isSensor = bool(getattr(src_ob, 'isSensor', False))
						proxy.density = float(getattr(src_ob, 'density', 1.0))
						proxy.bounciness = float(getattr(src_ob, 'bounciness', 0.0))
						proxy.bouncinessCombineRule = str(getattr(src_ob, 'bouncinessCombineRule', BOUNCINESS_COMBINE_RULES[0]))
						proxy.collisionGroupMembership = list(getattr(src_ob, 'collisionGroupMembership', [True] * 16))
						proxy.collisionGroupFilter = list(getattr(src_ob, 'collisionGroupFilter', [True] * 16))
						proxy.bound_box = getattr(src_ob, 'bound_box', [(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
						for i in range(MAX_ATTACH_COLLIDER_CNT):
							setattr(proxy, 'attach%i' %i, bool(getattr(src_ob, 'attach%i' %i, False)))
							setattr(proxy, 'attachTo%i' %i, getattr(src_ob, 'attachTo%i' %i, None))
						proxy.hide_get = (lambda : False)
						fallback_spawn_physics_obs.append(proxy)
						fallback_spawn_physics_source_names[proxy.name] = src_ob.name
						fallback_spawn_physics_debug.append(
							proxy.name + '<-' + src_ob.name +
							':rb=' + ('1' if bool(getattr(src_ob, 'rigidBodyExists', False)) else '0') +
							',co=' + ('1' if bool(getattr(src_ob, 'colliderExists', False)) else '0') +
							',rot=' + str(TryChangeToInt(proxy_rot_deg))
						)
					for ob in prefab_export_obs:
						src_pos, src_rot = _get_fallback_pose(ob)
						dx = float(src_pos.x) - float(anchor_pos.x)
						dy = float(src_pos.y) - float(anchor_pos.y)
						rad = math.radians(spawn_rot)
						cos_r = math.cos(rad)
						sin_r = math.sin(rad)
						world_x = req_x + dx * cos_r - dy * sin_r
						world_y = req_y + dx * sin_r + dy * cos_r
						world_rot = spawn_rot + (src_rot - anchor_rot)
						_spawn_proxy_for_template_node(ob.name, world_x, world_y, world_rot)
						if bool(getattr(ob, 'rigidBodyExists', False)) or bool(getattr(ob, 'colliderExists', False)):
							_spawn_proxy_for_physics(ob, world_x, world_y, world_rot)
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_call_count_raw=' + str(raw_spawn_call_count),
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_call_count_deduped=' + str(len(fallback_spawn_calls)),
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_requests=' + (', '.join(sorted(requested_prefabs)) if requested_prefabs else '<none>'),
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_added=' + (', '.join(added) if added else '<none>'),
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_baked=' + (', '.join(baked) if baked else '<none>'),
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_calls=' + (
					', '.join([
						str(call.get('prefab_name', '?')) + '@pos=' + (str(call.get('pos')) if call.get('pos', None) is not None else '<dynamic>') + ',rot=' + str(call.get('rot', 0.0))
						for call in fallback_spawn_calls
					]) if fallback_spawn_calls else '<none>'
				),
			])
		if not gbc_imgs:
			print('GBC export: no image empties with Export object enabled; wrote blank screen.')
		gbc_imgs.sort(key = lambda o: o.location.z)
		image_source_obs = list(gbc_imgs)
		for ob in fallback_surface_source_obs:
			if ob not in image_source_obs:
				image_source_obs.append(ob)
		for ob in image_source_obs:
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
		_append_gbc_trace_lines([
			'[gbc-trace] BuildGbc:after ExportGbcPyAssembly',
		])
		try:
			_init_ops = [op for op in list((script_runtime or {}).get('init_display_ops') or []) if isinstance(op, dict)]
			_update_ops = [op for op in list((script_runtime or {}).get('update_display_ops') or []) if isinstance(op, dict)]
			def _fmt_ops (_ops):
				rows = []
				for _op in _ops[:8]:
					_t = str(_op.get('op') or '')
					if _t == 'set_display_camera_pos':
						rows.append(_t + '(x=' + repr(_op.get('x')) + ',y=' + repr(_op.get('y')) + ')')
					elif _t == 'scroll_display_surface':
						rows.append(_t + '(dx=' + repr(_op.get('dx')) + ',dy=' + repr(_op.get('dy')) + ')')
					else:
						rows.append(_t)
				if len(_ops) > 8:
					rows.append('...+' + str(len(_ops) - 8))
				return rows
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:display_ops:init_count=' + str(len(_init_ops)) + ',ops=' + (', '.join(_fmt_ops(_init_ops)) if _init_ops else '<none>'),
				'[gbc-trace] BuildGbc:display_ops:update_count=' + str(len(_update_ops)) + ',ops=' + (', '.join(_fmt_ops(_update_ops)) if _update_ops else '<none>'),
			])
		except Exception:
			pass
		image_surfaces = {}
		for ob in image_source_obs:
			pix = _gba_load_saved_image_rgba(ob)
			if pix is not None:
				image_surfaces[ob.name] = pix
		composite_imgs = list(scene_gbc_imgs)
		for ob in fallback_draw_template_obs:
			if ob not in composite_imgs:
				composite_imgs.append(ob)
		composite_transform_overrides = {}
		def _gbc_authored_image_pos_to_gba (ob):
			pos = GetImagePosition(ob)
			return _gbc_to_gba_cover_point(float(pos.x), float(pos.y))
		for ob in composite_imgs:
			x_gba, y_gba = _gbc_authored_image_pos_to_gba(ob)
			composite_transform_overrides[ob.name] = {
				'x' : float(x_gba),
				'y' : float(y_gba),
				# Mirror Blender Z rotation for the Y-down GBC composite render.
				'rot_deg' : float(-math.degrees(ob.rotation_euler.z)),
			}
		try:
			pose_rows = []
			for ob in composite_imgs:
				if not (ob.type == 'EMPTY' and ob.empty_display_type == 'IMAGE' and getattr(ob, 'data', None)):
					continue
				tl = GetImagePosition(ob)
				ctr = GetImageCenterPosition(ob)
				off = list(getattr(ob, 'empty_image_offset', [0.0, 0.0]))
				pose_rows.append(
					str(ob.name)
					+ ':off=' + str([TryChangeToInt(float(off[0]) if len(off) > 0 else 0.0), TryChangeToInt(float(off[1]) if len(off) > 1 else 0.0)])
					+ ',loc=' + str([TryChangeToInt(float(ob.location.x)), TryChangeToInt(float(-ob.location.y))])
					+ ',tl=' + str([TryChangeToInt(float(tl.x)), TryChangeToInt(float(tl.y))])
					+ ',ctr=' + str([TryChangeToInt(float(ctr.x)), TryChangeToInt(float(ctr.y))])
				)
			if pose_rows:
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:image_pose_debug=' + ', '.join(pose_rows),
				])
		except Exception:
			pass
		fallback_spawn_draw_debug = []
		global _gbc_spawn_owner_pos_overrides
		_gbc_spawn_owner_pos_overrides = {}
		_gbc_spawn_owner_pos_overrides.update(dict(fallback_spawn_owner_direct_overrides))
		if fallback_spawn_entries:
			for proxy_ob, override in fallback_spawn_entries:
				composite_imgs.append(proxy_ob)
				composite_transform_overrides[proxy_ob.name] = dict(override)
				source_name = fallback_spawn_source_names.get(proxy_ob.name)
				if source_name in image_surfaces:
					image_surfaces[proxy_ob.name] = image_surfaces[source_name]
				surf = image_surfaces.get(proxy_ob.name)
				has_surface = surf is not None
				surf_w = int(surf.shape[1]) if has_surface else 0
				surf_h = int(surf.shape[0]) if has_surface else 0
				size = proxy_ob.scale * proxy_ob.empty_display_size
				img_size = Vector(list(proxy_ob.data.size) + [0])
				if img_size.x > img_size.y:
					size.x *= img_size.x / img_size.y
				else:
					size.y *= img_size.y / img_size.x
				tw = max(1, int(round(abs(size.x))))
				th = max(1, int(round(abs(size.y))))
				x_gba = float(override.get('x', 0.0))
				y_gba = float(override.get('y', 0.0))
				x_gbc, y_gbc = _gba_to_gbc_cover_point(x_gba, y_gba)
				# Script-space positions are X-right, Y-up (negative is down).
				_gbc_spawn_owner_pos_overrides[str(proxy_ob.name)] = [float(x_gbc), float(-y_gbc)]
				w_gbc = _gba_to_gbc_cover_len(tw)
				h_gbc = _gba_to_gbc_cover_len(th)
				visible = not ((x_gbc + w_gbc) <= 0 or x_gbc >= 160 or (y_gbc + h_gbc) <= 0 or y_gbc >= 144)
				fallback_spawn_draw_debug.append(
					proxy_ob.name + ':surf=' + ('1' if has_surface else '0') +
					',src=' + str(source_name if source_name is not None else '?') +
					',src_wh=' + str(surf_w) + 'x' + str(surf_h) +
					',gba_xy=' + str([TryChangeToInt(x_gba), TryChangeToInt(y_gba)]) +
					',rot=' + str(TryChangeToInt(float(override.get('rot_deg', 0.0)))) +
					',gbc_xy=' + str([TryChangeToInt(x_gbc), TryChangeToInt(y_gbc)]) +
					',gbc_wh=' + str([TryChangeToInt(w_gbc), TryChangeToInt(h_gbc)]) +
					',visible=' + ('1' if visible else '0')
				)
		if fallback_spawn_draw_debug:
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_draw_debug=' + ', '.join(fallback_spawn_draw_debug),
			])
		if fallback_spawn_physics_debug:
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:fallback_spawn_prefab_physics_debug=' + ', '.join(fallback_spawn_physics_debug),
			])
		physics_scene_obs = list(scene_obs)
		if fallback_spawn_physics_obs:
			physics_scene_obs.extend(fallback_spawn_physics_obs)
		runtime_print_scene_obs = _extend_runtime_print_scene_with_offscene_script_physics(physics_scene_obs, 'gbc-py')
		physics_image_obs = list(composite_imgs)
		for ph_ob in fallback_spawn_physics_obs:
			if ph_ob.type == 'EMPTY' and ph_ob.empty_display_type == 'IMAGE' and getattr(ph_ob, 'data', None):
				src_name = fallback_spawn_physics_source_names.get(ph_ob.name)
				if src_name in image_surfaces:
					image_surfaces[ph_ob.name] = image_surfaces[src_name]
				physics_image_obs.append(ph_ob)
		fallback_proxy_names = set()
		for proxy_ob, _override in fallback_spawn_entries:
			fallback_proxy_names.add(str(proxy_ob.name))
		for ph_ob in fallback_spawn_physics_obs:
			fallback_proxy_names.add(str(ph_ob.name))
		def _get_runtime_sprite_pos_gba (sprite_ob):
			name = str(sprite_ob.name)
			if name in composite_transform_overrides:
				override = composite_transform_overrides.get(name) or {}
				x = float(override.get('x', 0.0))
				y = float(override.get('y', 0.0))
				try:
					cam_xy = _gba_eval_display_camera_pos(script_runtime, frame = 1, include_update = True)
					x -= float(cam_xy[0])
					y -= float(cam_xy[1])
				except Exception:
					pass
				return x, y
			if name in fallback_proxy_names:
				pos = GetImagePosition(sprite_ob)
				x = float(pos.x)
				y = float(pos.y)
				try:
					cam_xy = _gba_eval_display_camera_pos(script_runtime, frame = 1, include_update = True)
					x -= float(cam_xy[0])
					y -= float(cam_xy[1])
				except Exception:
					pass
				return x, y
			x, y = _gbc_authored_image_pos_to_gba(sprite_ob)
			try:
				cam_xy = _gba_eval_display_camera_pos(script_runtime, frame = 1, include_update = True)
				x -= float(cam_xy[0])
				y -= float(cam_xy[1])
			except Exception:
				pass
			return x, y
		has_physics = bool(getattr(world, 'usePhysics', True)) and _gb_scene_has_physics(physics_scene_obs)
		use_multi_body_runtime = False
		if has_physics:
			scroll_profile = _gba_get_runtime_display_scroll_profile(script_runtime, frame = 1)
			camera_ops_present = _gba_has_set_camera_ops(script_runtime)
			camera_follow_mode = False
			try:
				for _op in list((script_runtime or {}).get('update_display_ops') or []):
					if not isinstance(_op, dict):
						continue
					if str(_op.get('op') or '') != 'set_display_camera_pos':
						continue
					if str(_op.get('camera_follow_owner') or '') != '':
						camera_follow_mode = True
						break
			except Exception:
				camera_follow_mode = False
			camera_offset_x = 0
			camera_offset_y = 0
			if camera_ops_present:
				try:
					camera_offset_x, camera_offset_y = _gba_eval_display_camera_pos(script_runtime, frame = 1, include_update = True)
				except Exception:
					camera_offset_x, camera_offset_y = (0, 0)
				# Phase1 hardware scroll registers are 8-bit; keep camera in
				# world-space offsets instead of register scrolling to avoid wrap.
				scroll_profile = {
					'init_dx' : 0,
					'init_dy' : 0,
					'step_dx' : 0,
					'step_dy' : 0,
				}
			phase1_transform_overrides = composite_transform_overrides
			if (not camera_follow_mode) and camera_ops_present and (int(camera_offset_x) != 0 or int(camera_offset_y) != 0):
				phase1_transform_overrides = {}
				for _name, _ov in list((composite_transform_overrides or {}).items()):
					if not isinstance(_ov, dict):
						continue
					ov2 = dict(_ov)
					try:
						ov2['x'] = float(_ov.get('x', 0.0)) - float(camera_offset_x)
					except Exception:
						ov2['x'] = float(_ov.get('x', 0.0))
					try:
						ov2['y'] = float(_ov.get('y', 0.0)) - float(camera_offset_y)
					except Exception:
						ov2['y'] = float(_ov.get('y', 0.0))
					phase1_transform_overrides[_name] = ov2
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:scroll_profile:init_dx=' + str(int(scroll_profile.get('init_dx', 0)))
				+ ',init_dy=' + str(int(scroll_profile.get('init_dy', 0)))
				+ ',step_dx=' + str(int(scroll_profile.get('step_dx', 0)))
				+ ',step_dy=' + str(int(scroll_profile.get('step_dy', 0))),
				'[gbc-trace] BuildGbc:camera_offset_bake:x=' + str(int(camera_offset_x)) + ',y=' + str(int(camera_offset_y)) + ',camera_ops=' + ('1' if camera_ops_present else '0'),
				'[gbc-trace] BuildGbc:camera_follow_mode=' + ('1' if camera_follow_mode else '0'),
			])
			bake_runtime = _gba_runtime_without_display_scroll(script_runtime)
			rigid_sprite_obs = [
				ob for ob in physics_image_obs
				if (
					getattr(ob, 'rigidBodyExists', False) and
					getattr(ob, 'rigidBodyEnable', True) and
					str(getattr(ob, 'rigidBodyType', '')) == 'dynamic'
				)
			]
			_append_gbc_trace_lines([
				'[gbc-trace] BuildGbc:physics_scene_obs=' + str(len(physics_scene_obs)),
				'[gbc-trace] BuildGbc:physics_image_obs=' + str(len(physics_image_obs)),
				'[gbc-trace] BuildGbc:rigid_sprite_obs=' + str(len(rigid_sprite_obs)),
				'[gbc-trace] BuildGbc:rigid_sprite_names=' + (
					', '.join([str(ob.name) for ob in rigid_sprite_obs]) if rigid_sprite_obs else '<none>'
				),
				'[gbc-trace] BuildGbc:dynamic_sprite_sources=' + (
					', '.join([
						str(ob.name) + '<' + str(getattr(ob, 'rigidBodyType', '?')) + '>'
						for ob in physics_image_obs
						if getattr(ob, 'rigidBodyExists', False) and getattr(ob, 'rigidBodyEnable', True)
					]) if physics_image_obs else '<none>'
				),
			])
			if not rigid_sprite_obs:
				raise RuntimeError('GBC dynamic physics phase1 requires at least one exported image empty with an enabled rigid body.')
			gravity_x = 0.0
			gravity_y = 0.0
			if bpy.context.scene.use_gravity:
				g = list(bpy.context.scene.gravity)
				gravity_x = float(g[0])
				gravity_y = float(g[1])
			if len(rigid_sprite_obs) > 1:
				use_multi_body_runtime = True
				rigid_names = set()
				for s in rigid_sprite_obs:
					rigid_names.add(s.name)
					draw_name = str(getattr(s, 'drawProxyName', '') or '')
					if draw_name != '':
						rigid_names.add(draw_name)
				bg_imgs = [ob for ob in composite_imgs if ob.name not in rigid_names]
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:multi_body_rigid_names=' + (', '.join(sorted(rigid_names)) if rigid_names else '<none>'),
					'[gbc-trace] BuildGbc:multi_body_bg_imgs=' + (', '.join([str(ob.name) for ob in bg_imgs]) if bg_imgs else '<none>'),
				])
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
					transform_overrides = phase1_transform_overrides,
					script_runtime = bake_runtime,
					frame = 1,
				)
				canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
				_, _, _, bg_palette_bank = _gbc_encode_tiles_and_map(canvas_gbc)
				body_specs = []
				body_mass_q = {}
				for rigid_ob in rigid_sprite_obs:
					body_mass_q[str(getattr(rigid_ob, 'name', '') or '')] = _gbc_mass_to_q8(
						_gbc_estimate_runtime_body_mass(physics_scene_obs, rigid_ob)
					)
				for sprite_ob in rigid_sprite_obs:
					sprite_rgba = _gba_apply_tint_opacity_to_rgba(image_surfaces.get(sprite_ob.name), list(sprite_ob.tint), sprite_ob.color[3])
					sprite_pal = _gbc_palette4_from_rgba(sprite_rgba)
					sprite_w, sprite_h = _gba_get_image_size(sprite_ob)
					sprite_w = _gba_to_gbc_cover_len(sprite_w)
					sprite_h = _gba_to_gbc_cover_len(sprite_h)
					sprite_name = str(getattr(sprite_ob, 'name', '') or '')
					sprite_max_tiles = 9 if sprite_name.startswith('__gbc_spawnphys_') else 16
					init_x_src, init_y_src = _get_runtime_sprite_pos_gba(sprite_ob)
					init_x_local, init_y_local = _gba_to_gbc_cover_point(float(init_x_src), float(init_y_src))
					init_x = (int(init_x_local) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
					init_y = (int(init_y_local) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
					init_vx, init_vy = _extract_gbc_phase1_init_velocity(world, sprite_ob)
					velocity_script = _extract_gbc_phase1_velocity_script(world, sprite_ob)
					# Preserve detail for the controlled/scripted actor, but keep
					# fallback/spawned rigid bodies lean so we can fit more bodies
					# within the hard 40-entry OAM runtime budget.
					needs_large_sprite = int(round(sprite_w)) > 32 or int(round(sprite_h)) > 32
					if isinstance(velocity_script, dict):
						sprite_max_tiles = _GBC_RUNTIME_MAX_METASPRITE_TILES if needs_large_sprite else 16
					elif sprite_name.startswith('__gbc_spawnphys_'):
						sprite_max_tiles = 6
					else:
						sprite_max_tiles = _GBC_RUNTIME_MAX_METASPRITE_TILES if needs_large_sprite else 9
					sprite_tile, sprite_tiles_w, sprite_tiles_h, sprite_pal_bank, sprite_tile_pal_idx = _gbc_encode_metasprite_rgba(
						sprite_rgba,
						int(round(sprite_w)),
						int(round(sprite_h)),
						palette4 = sprite_pal,
						max_tiles = sprite_max_tiles,
					)
					gravity_scale = float(getattr(sprite_ob, 'gravityScale', 1.0))
					effective_x = gravity_x * gravity_scale
					effective_down = -gravity_y * gravity_scale
					grav_step_x = int(round(effective_x))
					grav_step_y = int(round(effective_down))
					if abs(effective_x) > 1e-6 and grav_step_x == 0:
						grav_step_x = 1 if effective_x > 0 else -1
					if abs(effective_down) > 1e-6 and grav_step_y == 0:
						grav_step_y = 1 if effective_down > 0 else -1
					mass_q = int(body_mass_q.get(sprite_name, 1))
					body_specs.append({
						'name' : sprite_ob.name,
						'sprite_tile_bytes' : sprite_tile,
						'sprite_tiles_w' : sprite_tiles_w,
						'sprite_tiles_h' : sprite_tiles_h,
						'palette_bank' : sprite_pal_bank,
						'tile_palette_idx' : sprite_tile_pal_idx,
						'palette4' : sprite_pal,
						'init_x' : init_x,
						'init_y' : init_y,
						'init_vx' : int(init_vx),
						'init_vy' : int(init_vy),
						'grav_step_x' : int(grav_step_x),
						'grav_step_y' : int(grav_step_y),
						'velocity_script' : velocity_script,
						'mass_q' : int(mass_q),
					})
				body_specs_runtime = list(body_specs)
				dropped_body_specs = []
				total_tile_count = 0
				total_oam_count = 0
				for i, spec in enumerate(body_specs):
					tile_bytes_raw = spec.get('sprite_tile_bytes', None)
					tile_bytes = b'' if tile_bytes_raw is None else bytes(tile_bytes_raw)
					tile_count = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_TILES, int(len(tile_bytes) // 16)))
					sprite_tiles_w = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(spec.get('sprite_tiles_w', 1))))
					sprite_tiles_h = max(1, min(_GBC_RUNTIME_MAX_METASPRITE_SPAN_TILES, int(spec.get('sprite_tiles_h', 1))))
					if sprite_tiles_w * sprite_tiles_h > tile_count:
						sprite_tiles_h = max(1, tile_count // sprite_tiles_w)
					oam_need = max(1, min(_GBC_RUNTIME_MAX_OAM, sprite_tiles_w * sprite_tiles_h))
					if total_tile_count + tile_count > 255 or total_oam_count + oam_need > _GBC_RUNTIME_MAX_OAM:
						dropped_body_specs = body_specs[i :]
						body_specs_runtime = body_specs[: i]
						break
					total_tile_count += tile_count
					total_oam_count += oam_need
				if not body_specs_runtime:
					raise RuntimeError('GBC dynamic multi-body export has no bodies within OAM/VRAM budget.')
				active_body_names = set([str(spec.get('name', '')) for spec in body_specs_runtime])
				active_rigid_names = set(active_body_names)
				for s in rigid_sprite_obs:
					if str(s.name) not in active_body_names:
						continue
					draw_name = str(getattr(s, 'drawProxyName', '') or '')
					if draw_name != '':
						active_rigid_names.add(draw_name)
				if dropped_body_specs:
					bg_imgs = [ob for ob in composite_imgs if ob.name not in active_rigid_names]
					canvas_gba_space = _gba_composite_scene(
						world,
						bg_imgs,
						image_surfaces = image_surfaces,
						transform_overrides = phase1_transform_overrides,
						script_runtime = bake_runtime,
						frame = 1,
					)
					canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
					_, _, _, bg_palette_bank = _gbc_encode_tiles_and_map(canvas_gbc)
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:multi_body_specs=' + (
						', '.join([
							str(spec.get('name', '?')) +
							':iv=' + str([spec.get('init_vx', 0), spec.get('init_vy', 0)]) +
							',g=' + str([spec.get('grav_step_x', 0), spec.get('grav_step_y', 0)]) +
							',vs=' + ('1' if isinstance(spec.get('velocity_script', None), dict) else '0') +
							',m=' + str(spec.get('mass_q', 1))
							for spec in body_specs_runtime
						]) if body_specs else '<none>'
					),
					'[gbc-trace] BuildGbc:multi_body_runtime_bodies=' + (
						', '.join([str(spec.get('name', '?')) for spec in body_specs_runtime]) if body_specs_runtime else '<none>'
					),
					'[gbc-trace] BuildGbc:multi_body_runtime_dropped=' + (
						', '.join([str(spec.get('name', '?')) for spec in dropped_body_specs]) if dropped_body_specs else '<none>'
					),
					'[gbc-trace] BuildGbc:multi_body_rigid_names_runtime=' + (
						', '.join(sorted(active_rigid_names)) if active_rigid_names else '<none>'
					),
					'[gbc-trace] BuildGbc:multi_body_bg_imgs_runtime=' + (
						', '.join([str(ob.name) for ob in bg_imgs]) if bg_imgs else '<none>'
					),
				])
				collider_debug_rows = []
				collider_rects = _gbc_collect_runtime_colliders(
					physics_scene_obs,
					ignored_names = active_body_names,
					preconverted_names = fallback_proxy_names,
					debug_rows = collider_debug_rows,
				)
				if (not camera_follow_mode) and camera_ops_present and (int(camera_offset_x) != 0 or int(camera_offset_y) != 0):
					collider_rects = _gbc_shift_collider_rects_by_camera(collider_rects, camera_offset_x, camera_offset_y)
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:multi_body_collider_debug=' + (', '.join(collider_debug_rows) if collider_debug_rows else '<none>'),
				])
				rom = _gbc_build_dynamic_physics_rom_multi(
					canvas_gbc,
					body_specs_runtime,
					bg_palette_bank,
					collider_rects = collider_rects,
					init_scroll_x = scroll_profile.get('init_dx', 0),
					init_scroll_y = scroll_profile.get('init_dy', 0),
					scroll_step_x = scroll_profile.get('step_dx', 0),
					scroll_step_y = scroll_profile.get('step_dy', 0),
				)
			else:
				sprite_ob = None
				for ob in rigid_sprite_obs:
					if getattr(ob, 'rigidBodyType', '') == 'dynamic':
						sprite_ob = ob
						break
				if sprite_ob is None and rigid_sprite_obs:
					sprite_ob = rigid_sprite_obs[0]
				sprite_names = {sprite_ob.name}
				draw_name = str(getattr(sprite_ob, 'drawProxyName', '') or '')
				if draw_name != '':
					sprite_names.add(draw_name)
				bg_imgs = [ob for ob in composite_imgs if ob.name not in sprite_names]
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:single_body_sprite_names=' + (', '.join(sorted(sprite_names)) if sprite_names else '<none>'),
					'[gbc-trace] BuildGbc:single_body_bg_imgs=' + (', '.join([str(ob.name) for ob in bg_imgs]) if bg_imgs else '<none>'),
				])
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
					transform_overrides = phase1_transform_overrides,
					script_runtime = bake_runtime,
					frame = 1,
				)
				canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
				_, _, _, bg_palette_bank = _gbc_encode_tiles_and_map(canvas_gbc)
				sprite_rgba = _gba_apply_tint_opacity_to_rgba(image_surfaces.get(sprite_ob.name), list(sprite_ob.tint), sprite_ob.color[3])
				sprite_pal = _gbc_palette4_from_rgba(sprite_rgba)
				sprite_w, sprite_h = _gba_get_image_size(sprite_ob)
				sprite_w = _gba_to_gbc_cover_len(sprite_w)
				sprite_h = _gba_to_gbc_cover_len(sprite_h)
				collision_w_px = int(round(sprite_w))
				collision_h_px = int(round(sprite_h))
				collision_off_x_px = 0
				collision_off_y_px = 0
				# Use the same helper as runtime world-collider export so player-vs-world
				# contact uses identical rect size/placement semantics.
				try:
					sprite_self_rects = _gbc_collect_runtime_colliders(
						[sprite_ob],
						preconverted_names = fallback_proxy_names,
					)
				except Exception:
					sprite_self_rects = []
				if len(sprite_self_rects) > 0:
					try:
						col_left, col_top, col_w, col_h = [int(v) for v in sprite_self_rects[0]]
						collision_w_px = max(1, int(col_w))
						collision_h_px = max(1, int(col_h))
						init_x_src_tmp, init_y_src_tmp = _get_runtime_sprite_pos_gba(sprite_ob)
						sprite_x_gbc, sprite_y_gbc = _gba_to_gbc_cover_point(float(init_x_src_tmp), float(init_y_src_tmp))
						collision_off_x_px = int(col_left - int(sprite_x_gbc))
						collision_off_y_px = int(col_top - int(sprite_y_gbc))
					except Exception:
						collision_off_x_px = 0
						collision_off_y_px = 0
				sprite_name = str(getattr(sprite_ob, 'name', '') or '')
				needs_large_sprite = int(round(sprite_w)) > 32 or int(round(sprite_h)) > 32
				sprite_max_tiles = _GBC_RUNTIME_MAX_METASPRITE_TILES if needs_large_sprite else (9 if sprite_name.startswith('__gbc_spawnphys_') else 16)
				sprite_tile, sprite_tiles_w, sprite_tiles_h, sprite_pal_bank, sprite_tile_pal_idx = _gbc_encode_metasprite_rgba(
					sprite_rgba,
					int(round(sprite_w)),
					int(round(sprite_h)),
					palette4 = sprite_pal,
					max_tiles = sprite_max_tiles,
				)
				init_x_src, init_y_src = _get_runtime_sprite_pos_gba(sprite_ob)
				init_x_local, init_y_local = _gba_to_gbc_cover_point(float(init_x_src), float(init_y_src))
				init_x = (int(init_x_local) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
				init_y = (int(init_y_local) + _GBC_POSITION_BIAS) & _GBC_POSITION_MASK
				init_vx, init_vy = _extract_gbc_phase1_init_velocity(world, sprite_ob)
				velocity_script = _extract_gbc_phase1_velocity_script(world, sprite_ob)
				init_vx = int(init_vx)
				init_vy = int(init_vy)
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
				grav_step_x = int(grav_step_x)
				grav_step_y = int(grav_step_y)
				collider_debug_rows = []
				collider_rect_meta = []
				collider_rects = _gbc_collect_runtime_colliders(
					physics_scene_obs,
					ignored_name = sprite_ob.name,
					preconverted_names = fallback_proxy_names,
					debug_rows = collider_debug_rows,
					debug_include_ignored = True,
					rect_meta = collider_rect_meta,
				)
				if (not camera_follow_mode) and camera_ops_present and (int(camera_offset_x) != 0 or int(camera_offset_y) != 0):
					collider_rects = _gbc_shift_collider_rects_by_camera(collider_rects, camera_offset_x, camera_offset_y)
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:single_body_collider_debug=' + (', '.join(collider_debug_rows) if collider_debug_rows else '<none>'),
				])
				player_w_px = int(collision_w_px)
				player_h_px = int(collision_h_px)
				probe_rows = []
				for idx, rect in enumerate(list(collider_rects or [])):
					try:
						cx, cy, cw, ch = [int(v) for v in rect]
					except Exception:
						continue
					collider_name = ''
					try:
						if idx < len(collider_rect_meta) and isinstance(collider_rect_meta[idx], dict):
							collider_name = str(collider_rect_meta[idx].get('name', '') or '')
					except Exception:
						collider_name = ''
					# If the player's top-left enters this AABB, axis-aligned overlap begins.
					contact_aabb = [
						cx - player_w_px - int(collision_off_x_px),
						cy - player_h_px - int(collision_off_y_px),
						cx + cw - int(collision_off_x_px),
						cy + ch - int(collision_off_y_px),
					]
					probe_rows.append(
						str(idx) +
						':' + (collider_name if collider_name != '' else '<unnamed>') +
						':rect=' + str([cx, cy, cw, ch]) +
						':player_tl_contact_aabb=' + str(contact_aabb)
					)
				_append_gbc_trace_lines([
					'[gbc-trace] BuildGbc:phase1_contact_probe:sprite_wh=' + str([player_w_px, player_h_px]),
					'[gbc-trace] BuildGbc:phase1_contact_probe:sprite_off=' + str([int(collision_off_x_px), int(collision_off_y_px)]),
					'[gbc-trace] BuildGbc:phase1_contact_probe:rows=' + (', '.join(probe_rows) if probe_rows else '<none>'),
				])
				if init_vx != 0 or init_vy != 0:
					print('GBC export: phase1 seeded sprite velocity from gbc-py script =', [init_vx, init_vy])
				else:
					print('GBC export: phase1 found no constant gbc-py set_linear_velocity seed for sprite; defaulting to [0, 0].')
				if isinstance(velocity_script, dict):
					print('GBC export: phase1 interpreted gbc-py velocity script =', velocity_script)
				rom = _gbc_build_dynamic_physics_rom(
					canvas_gbc,
					sprite_tile,
					sprite_tiles_w,
					sprite_tiles_h,
					init_x,
					init_y,
					bg_palette_bank,
					sprite_pal_bank,
					collider_rects = collider_rects,
					grav_step_x = grav_step_x,
					grav_step_y = grav_step_y,
					init_vx = init_vx,
					init_vy = init_vy,
					velocity_script = velocity_script,
					init_scroll_x = scroll_profile.get('init_dx', 0),
					init_scroll_y = scroll_profile.get('init_dy', 0),
					scroll_step_x = scroll_profile.get('step_dx', 0),
					scroll_step_y = scroll_profile.get('step_dy', 0),
					sprite_tile_palette_idxs = sprite_tile_pal_idx,
					collision_w_px = collision_w_px,
					collision_h_px = collision_h_px,
					collision_off_x_px = collision_off_x_px,
					collision_off_y_px = collision_off_y_px,
					camera_follow_mode = camera_follow_mode,
					camera_follow_center_x = 0,
					camera_follow_center_y = 0,
				)
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
				composite_imgs,
				image_surfaces = image_surfaces,
				transform_overrides = composite_transform_overrides,
				script_runtime = script_runtime,
				frame = 1,
			)
			canvas_gbc = _gba_resize_cover_rgba(canvas_gba_space, 160, 144)
			rom = _gbc_build_rom(canvas_gbc)
			print('GBC export: baked playback disabled; runtime is dynamic-only.')
		MakeFolderForFile(out)
		open(out, 'wb').write(rom)
		print('Saved GBC ROM:', out, '(%i bytes)' %len(rom))
		_append_gbc_trace_lines([
			'[gbc-trace] BuildGbc:end rom=' + str(out),
		])
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
			if has_physics:
				if use_multi_body_runtime:
					runtime_print_env = _build_runtime_print_physics_env(
						world,
						runtime_print_scene_obs,
						use_gbc_signed_positions = True,
						gbc_script_world_offset = [float(camera_offset_x), float(-camera_offset_y)],
					)
				else:
					phase1_runtime_handles = _build_runtime_print_physics_env(
						world,
						runtime_print_scene_obs,
						use_gbc_signed_positions = True,
						gbc_script_world_offset = [float(camera_offset_x), float(-camera_offset_y)],
					)
					phase1_script_world_offset = [float(camera_offset_x), float(-camera_offset_y)]
					try:
						owner_keys = []
						try:
							owner_keys.append(str(GetVarNameForObject(sprite_ob)))
						except Exception:
							pass
						try:
							owner_keys.append(str(getattr(sprite_ob, 'name', '')))
						except Exception:
							pass
						sprite_world = None
						for _owner_key in owner_keys:
							if not (isinstance(_owner_key, str) and _owner_key != ''):
								continue
							_p = _resolve_static_owner_camera_position(_owner_key)
							if isinstance(_p, (list, tuple)) and len(_p) >= 2:
								sprite_world = [float(_p[0]), float(_p[1])]
								break
						if sprite_world is not None:
							local_x = float(int(init_x) - _GBC_POSITION_BIAS)
							local_y = -float(int(init_y) - _GBC_POSITION_BIAS)
							phase1_script_world_offset = [
								float(sprite_world[0]) - float(local_x),
								float(sprite_world[1]) - float(local_y),
							]
					except Exception:
						pass
					runtime_print_env = _build_gbc_phase1_print_env(
						sprite_ob,
						sprite_tiles_w,
						sprite_tiles_h,
						init_x,
						init_y,
						init_vx,
						init_vy,
						grav_step_x,
						grav_step_y,
						collider_rects,
						velocity_script = velocity_script if has_physics else None,
						physics_scene_obs = runtime_print_scene_obs,
						runtime_handle_env = phase1_runtime_handles,
						collider_rect_meta = collider_rect_meta,
						collision_w_px = collision_w_px,
						collision_h_px = collision_h_px,
						collision_off_x_px = collision_off_x_px,
						collision_off_y_px = collision_off_y_px,
						script_world_offset = phase1_script_world_offset,
					)
			else:
				runtime_print_env = _build_runtime_print_physics_env(world, runtime_print_scene_obs)
			mirror_step = None
			sim_runtime = runtime_print_env.get('sim')
			if sim_runtime is not None and hasattr(sim_runtime, 'step'):
				mirror_step = sim_runtime.step
			_start_gba_update_print_mirror(
				proc,
				script_runtime,
				script_label = 'gbc-py',
				strict_print_exprs = True,
				runtime_env = runtime_print_env,
				mirror_step = mirror_step,
			)
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
	if hasattr(bpy.context, 'world'):
		world = bpy.context.world
	else:
		world = None
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
bpy.types.Collection.exportPrefab = bpy.props.BoolProperty(name = 'Export prefab', default = True, update = lambda ob, ctx : OnUpdateProperty (ob, ctx, 'exportPrefab'))

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
		bpy.types.World,
		'scriptIsGlobal%i' %i,
		bpy.props.BoolProperty(name = 'Is global')
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
			row.prop(ctx.world, 'scriptIsGlobal%i' %i)
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