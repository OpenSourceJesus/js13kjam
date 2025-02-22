import os, sys, subprocess, atexit, webbrowser, base64, json, string
_thisdir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisdir)

isLinux = None
if sys.platform == 'win32':
	BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe'
elif sys.platform == 'darwin':
	BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
else:
	BLENDER = 'blender'
	isLinux = True

try:
	import bpy
	from mathutils import *
except:
	bpy = None

if __name__ == '__main__':
	if bpy:
		pass
	else:
		cmd = [ BLENDER ]
		for arg in sys.argv:
			if arg.endswith('.blend'):
				cmd.append(arg)
				break
		cmd += [ '--python-exit-code', '1', '--python', __file__, '--python', os.path.join(_thisdir, 'blender-curve-to-svg', 'curve_to_svg.py') ]
		exargs = []
		for arg in sys.argv:
			if arg.startswith('--'):
				exargs.append(arg)
		if exargs:
			cmd.append('--')
			cmd += exargs
		print(cmd)
		subprocess.check_call(cmd)
		sys.exit()

MAX_SCRIPTS_PER_OBJECT = 16
if not bpy:
	if isLinux:
		if not os.path.isfile('/usr/bin/blender'):
			print('Did you install blender?')
			print('snap install blender')
	else:
		print('Download blender from: https://blender.org')
	sys.exit()

def GetScripts (ob, isAPI : bool):
	scripts = []
	type = 'runtime'
	if isAPI:
		type = 'api'
	for i in range(MAX_SCRIPTS_PER_OBJECT):
		if getattr(ob, type + 'Script%sDisable' %i):
			continue
		txt = getattr(ob, type + 'Script' + str(i))
		if txt != None:
			if isAPI:
				scripts.append(txt.as_string())
			else:
				scripts.append(( txt.as_string(), getattr(ob, 'initScript' + str(i)) ))
	return scripts

# def CurveToMesh (curve):
# 	deg = bpy.context.evaluated_depsgraph_get()
# 	mesh = bpy.data.meshes.new_from_object(curve.evaluated_get(deg), depsgraph = deg)
# 	ob = bpy.data.objects.new(curve.name + "_Mesh", mesh)
# 	bpy.context.collection.objects.link(ob)
# 	ob.matrix_world = curve.matrix_world
# 	return ob

# def ToVec2 (v : Vector):
# 	return Vector((v.x, v.y))

def Clamp (n : float, min : float, max : float):
	if n < min:
		return min
	elif n > max:
		return max
	else:
		return n

# def ToVec3 (v : Vector):
# 	return Vector(( v.x, v.y, 0 ))

# def Abs (v : Vector, is2d : bool = False):
# 	if is2d:
# 		return Vector((abs(v.x), abs(v.y)))
# 	else:
# 		return Vector((abs(v.x), abs(v.y), abs(v.z)))

def Multiply (v : list, multiply : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt * multiply[i])
	return output

def Round (v : list):
	output = []
	for elmt in v:
		output.append(round(elmt))
	return output

def ClampComponents (v : list, min : list, max : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(Clamp(elmt, min[i], max[i]))
	return output

def GetMinComponents (v : Vector, v2 : Vector, use2D : bool = False):
	if use2D:
		return Vector(( min(v.x, v2.x), min(v.y, v2.y) ))
	else:
		return Vector(( min(v.x, v2.x), min(v.y, v2.y), min(v.z, v2.z) ))

def GetMaxComponents (v : Vector, v2 : Vector, use2D : bool = False):
	if use2D:
		return Vector(( max(v.x, v2.x), max(v.y, v2.y) ))
	else:
		return Vector(( max(v.x, v2.x), max(v.y, v2.y), max(v.z, v2.z) ))

# def Divide (v : Vector, v2 : Vector, use2D : bool = False):
# 	if use2D:
# 		return Vector(( v.x / v2.x, v.y / v2.y ))
# 	else:
# 		return Vector(( v.x / v2.x, v.y / v2.y, v.z / v2.z ))

# def ToNormalizedPoint (minMax : [],  v : Vector):
# 	return Divide(Vector(( 1, 1 )), (minMax[1] - minMax[0]), True) * (v - minMax[0])

def GetCurveRectMinMax (ob):
	bounds = [( ob.matrix_world @ Vector(corner) ) for corner in ob.bound_box]
	box = []
	box.append(min([ bounds[0][0], bounds[1][0], bounds[2][0], bounds[3][0] ]))
	box.append(min([ bounds[0][1], bounds[1][1], bounds[4][1], bounds[5][1] ]))
	box.append(max([ bounds[4][0], bounds[5][0], bounds[6][0], bounds[7][0] ]))
	box.append(max([ bounds[2][1], bounds[3][1], bounds[6][1], bounds[7][1] ]))
	_min = Vector(( box[0], box[1] ))
	_max = Vector(( box[2], box[3] ))
	return _min, _max

# def IndexOf_Array (o, arr : list):
# 	for i, elmt in enumerate(arr):
# 		if o == elmt:
# 			return i
# 	return -1

def IndexOfValue (o, d : dict):
	for i, value in enumerate(d.values()):
		if o == value:
			return i
	return -1

def IsInAnyElement (o, arr : list):
	for elmt in arr:
		if o in elmt:
			return True
	return False

# def Copy (ob, copyData = True, copyActions = True, collection = None):
# 	copy = ob.copy()
# 	if copyData:
# 		copy.data = copy.data.copy()
# 	if copyActions and copy.animation_data:
# 		copy.animation_data.action = copy.animation_data.action.copy()
# 	if collection == None:
# 		collection = bpy.context.collection
# 	collection.objects.link(copy)
# 	for child in ob.children:
# 		childCopy = Copy(child, copyData, copyActions, collection)
# 		childCopy.parent = copy
# 	return copy

def ToByteString (n):
	n = round(n)
	n = Clamp(n, 0, 255)
	byteStr = chr(n)
	if byteStr in '\n\r[,':
		byteStr = chr(n - 1)
	elif byteStr in '"\'':
		byteStr = '\\' + byteStr
	return byteStr

def GetSvgPathData (pathValues : list, cyclic : bool):
	path = 'M ' + pathValues[0] + ',' + pathValues[1] + ' '
	for i in range(2, len(pathValues), 2):
		if (i - 2) % 6 == 0:
			path += 'C '
		path += '' + pathValues[i] + ',' + pathValues[i + 1] + ' '
	if cyclic:
		path += 'Z'
	return path

DEFAULT_COLOR = [ 0, 0, 0, 0 ]
colors = {}
exportedObs = []
meshes = []
curves = []
empties = []
initCode = []
updateCode = []
datas = []
svgText = ''
userJS = ''

def ExportObject (ob):
	if ob.hide_get() or ob in exportedObs:
		return
	world = bpy.data.worlds[0]
	SCALE = world.export_scale
	offX = world.export_offset_x
	offY = world.export_offset_y
	off = Vector(( offX, offY ))
	x, y, z = ob.location * SCALE
	y = -y
	z = -z
	x += offX
	y += offY
	sx, sy, sz = ob.scale * SCALE
	if ob.type == 'EMPTY' and len(ob.children) > 0:
		empties.append(ob)
		if HandleCopyObject(ob, Vector((x, y))):
			return
		for child in ob.children:
			ExportObject (child)
		firstAndLastChildIdsTxt = ''
		firstAndLastChildIdsTxt += ob.children[0].name + ';' + ob.children[-1].name
		datas.append(','.join([ob.name, firstAndLastChildIdsTxt]))
	elif ob.type == 'CURVE':
		curves.append(ob)
		bpy.ops.object.select_all(action = 'DESELECT')
		ob.select_set(True)
		bpy.ops.curve.export_svg()
		svgText = open('/tmp/Output.svg', 'r').read()
		svgText_ = svgText
		indexOfName = svgText_.find(ob.name)
		indexOfGroupStart = svgText_.rfind('\n', 0, indexOfName)
		groupEndIndicator = '</g>'
		indexOfGroupEnd = svgText_.find(groupEndIndicator, indexOfGroupStart) + len(groupEndIndicator)
		group = svgText_[indexOfGroupStart : indexOfGroupEnd]
		parentGroupIndicator = '\n  <g'
		indexOfParentGroupStart = svgText_.find(parentGroupIndicator)
		indexOfParentGroupContents = svgText_.find('\n', indexOfParentGroupStart + len(parentGroupIndicator))
		indexOfParentGroupEnd = svgText_.rfind('</g')
		min, max = GetCurveRectMinMax(ob)
		scale = Vector(( sx, sy ))
		min *= scale
		min += off
		if HandleCopyObject(ob, min):
			return
		max *= scale
		max += off
		data = []
		svgText_ = svgText_[: indexOfParentGroupContents] + group + svgText_[indexOfParentGroupEnd :]
		pathDataIndicator = ' d="'
		indexOfPathDataStart = svgText_.find(pathDataIndicator) + len(pathDataIndicator)
		indexOfPathDataEnd = svgText_.find('"', indexOfPathDataStart)
		pathData = svgText_[indexOfPathDataStart : indexOfPathDataEnd]
		pathData = pathData.replace('.0', '')
		pathData_ = []
		vectors = pathData.split(' ')
		minPathValue = Vector(( float('inf'), float('inf') ))
		for vector in vectors:
			if len(vector) == 1:
				continue
			components = vector.split(',')
			x = int(components[0])
			y = int(components[1])
			vector = Vector(( x, y ))
			minPathValue = GetMinComponents(minPathValue, vector, True)
			pathData_.append(x)
			pathData_.append(y)
		minPathValue *= SCALE
		offset = -minPathValue
		for i, pathDataValue in enumerate(pathData_):
			pathData_[i] = ToByteString(pathDataValue + offset[i % 2])
		data.append(str(round(min.x)))
		data.append(str(round(min.y)))
		size = max - min
		data.append(str(round(size.x)))
		data.append(str(round(size.y)))
		materialColor = DEFAULT_COLOR
		if len(ob.material_slots) > 0:
			materialColor = ob.material_slots[0].material.diffuse_color
		materialColor = ClampComponents(Round(Multiply(materialColor, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
		indexOfMaterialColor = IndexOfValue(materialColor, colors)
		keyOfMaterialColor = ''
		if indexOfMaterialColor == -1:
			keyOfMaterialColor = string.ascii_letters[len(colors)]
			colors[keyOfMaterialColor] = materialColor
		else:
			keyOfMaterialColor = string.ascii_letters[indexOfMaterialColor]
		data.append(keyOfMaterialColor)
		strokeWidth = 0
		if ob.useSvgStroke:
			strokeWidth = ob.svgStrokeWidth
		data.append(ToByteString(strokeWidth))
		strokeColor = ClampComponents(Round(Multiply(ob.svgStrokeColor, [255, 255, 255])), [0, 0, 0], [255, 255, 255])
		indexOfStrokeColor = IndexOfValue(strokeColor, colors)
		keyOfStrokeColor = ''
		if indexOfStrokeColor == -1:
			keyOfStrokeColor = string.ascii_letters[len(colors)]
			colors[keyOfStrokeColor] = strokeColor
		else:
			keyOfStrokeColor = string.ascii_letters[indexOfStrokeColor]
		data.append(keyOfStrokeColor)
		data.append(ob.name)
		data.append(''.join(pathData_))
		data.append(str(ob.data.splines[0].use_cyclic_u))
		data.append(ToByteString(ob.location.z))
		data.append(str(ob.collide))
		datas.append(','.join(data))
	exportedObs.append(ob)

def HandleCopyObject (ob, pos):
	for exportedOb in exportedObs:
		indexOfPeriod = ob.name.find('.')
		if indexOfPeriod == -1:
			obNameWithoutPeriod = ob.name
		else:
			obNameWithoutPeriod = ob.name[: indexOfPeriod]
		indexOfPeriod = exportedOb.name.find('.')
		if indexOfPeriod == -1:
			exportedObNameWithoutPeriod = exportedOb.name
		else:
			exportedObNameWithoutPeriod = exportedOb.name[: indexOfPeriod]
		if obNameWithoutPeriod == exportedObNameWithoutPeriod:
			datas.append(','.join([obNameWithoutPeriod, str(round(pos[0])), str(round(pos[1]))]))
			exportedObs.append(ob)
			return True
	return False

def GetBlenderData ():
	global datas
	global colors
	global meshes
	global curves
	global empties
	global svgText
	global initCode
	global userJS
	global updateCode
	global exportedObs
	for ob in bpy.data.objects:
		if '_Clone' in ob.name:
			for child in ob.children:
				bpy.data.objects.remove(child, do_unlink = True)
			bpy.data.objects.remove(ob, do_unlink = True)
	exportedObs = []
	userJS = ''
	colors = {}
	meshes = []
	curves = []
	empties = []
	datas = []
	initCode = []
	updateCode = []
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

@bpy.utils.register_class
class Export (bpy.types.Operator):
	bl_idname = 'world.export'
	bl_label = 'Export'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		exe = Build(context.world)
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
		row.prop(context.world, 'export_scale')
		row = self.layout.row()
		row.prop(context.world, 'export_offset_x')
		row.prop(context.world, 'export_offset_y')
		self.layout.prop(context.world, 'export_html')
		self.layout.operator('world.export', icon = 'CONSOLE')

@bpy.utils.register_class
class JS13KB_Panel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_JS13KB_Panel'
	bl_label = 'js13kgames.com'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw (self, context):
		self.layout.prop(context.world, 'js13kb')
		row = self.layout.row()
		row.prop(context.world, 'minify')
		row.prop(context.world, 'invalid_html')
		if context.world.js13kb:
			self.layout.prop(context.world, 'export_zip')
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

HTML = '''
$d=async(u,t)=>{
	d=new DecompressionStream('gzip')
	r=await fetch('data:application/octet-stream;base64,'+u)
	b=await r.blob()
	s=b.stream().pipeThrough(d)
	o=await new Response(s).blob()
	return await o.text()
}
$d($0,1).then((j)=>{
	$d($1,1).then((d)=>{
		$d($2,1).then((c)=>{
			console.log(d)
			$=eval(j)
			for(v of d.split('['))
			{
				v=v.split(',')
				l=v.length
				if(l>3)
				{
					z=JSON.parse(c)
					var a=v[8]
					var p=[]
					for(var e of a)
						p.push(e.charCodeAt(0))
					$.draw_svg([parseInt(v[0]),parseInt(v[1])],[parseInt(v[2]),parseInt(v[3])],z[v[4]],v[5].charCodeAt(0),z[v[6]],v[7],$.get_svg_path(p,v[9]!=''),v[10].charCodeAt(0),v[11]!='')
				}
				else if(l>2)
					$.copy_node(v[0],[parseInt(v[1]),parseInt(v[2])])
				else
					$.add_group(v[0],v[1])
			}
			$.main(j)
		})
	})
})
'''
JS = '''
function get_pos_and_size (elmt)
{
	return [[parseFloat(elmt.getAttribute('x')), parseFloat(elmt.getAttribute('y'))], [parseFloat(elmt.getAttribute('width')), parseFloat(elmt.getAttribute('height'))]]
}
function lerp (min, max, t)
{
	return min + t * (max - min)
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
function overlaps (pos, size, pos2, size2)
{
	return !(pos[0] + size[0] < pos2[0]
		|| pos[0] > pos2[0] + size2[0]
		|| pos[1] + size[1] < pos2[1]
		|| pos[1] > pos2[1] + size2[1])
}
function random_vector_2d (mD)
{
	var dt = random(0, mD);
	var ag = random(0, 2 * Math.PI);
	return [ Math.cos(ag) * dt, Math.sin(ag) * dt ];
}
function random (min, max)
{
	return Math.random() * (max - min) + min;
}
function copy_node (id, pos)
{
	return $.copy_node(id, pos);
}
function add_group (id, firstAndLastChildIds)
{
	$.add_group (id, firstAndLastChildIds);
}
'''
JS_API = '''
class api
{
	bytes = []

	get_svg_path (pathValues, cyclic)
	{
		var path = 'M ' + pathValues[0] + ',' + pathValues[1] + ' '
		for (var i = 2; i < pathValues.length; i += 2)
		{
			if ((i - 2) % 6 == 0)
				path += 'C '
			path += '' + pathValues[i] + ',' + pathValues[i + 1] + ' '
		}
		if (cyclic)
			path += 'Z'
		return path
	}
	copy_node (id, pos)
	{
		var copy = document.getElementById(id).cloneNode(true);
		copy.setAttribute('x', pos[0]);
		copy.setAttribute('y', pos[1]);
		document.body.appendChild(copy);
		return copy;
	}
	add_group (id, firstAndLastChildIds)
	{
		var children = firstAndLastChildIds.split(';');
		var html = document.body.innerHTML;
		var indexOfFirstChild = html.lastIndexOf('<svg', html.indexOf('id="' + children[0]));
		var indexOfLastChild = html.indexOf('</svg>', html.indexOf('id="' + children[1])) + 6;
		document.body.innerHTML = html.slice(0, indexOfFirstChild) + '<g id="' + id + '">' + html.slice(indexOfFirstChild, indexOfLastChild) + '</g>' + html.slice(indexOfLastChild);
	}
	draw_svg (pos, size, fillColor, lineWidth, lineColor, id, path, zIndex, collide)
	{
		var fillColorTxt = 'transparent';
		if (fillColor[3] > 0)
			fillColorTxt = 'rgb(' + fillColor[0] + ' ' + fillColor[1] + ' ' + fillColor[2] + ')';
		var lineColorTxt = 'transparent';d
		if (lineWidth > 0)
			lineColorTxt = 'rgb(' + lineColor[0] + ' ' + lineColor[1] + ' ' + lineColor[2] + ')';
		document.body.innerHTML += '<svg xmlns="www.w3.org/2000/svg"id="' + id + '"viewBox="0 0 ' + (size[0] + lineWidth * 2) + ' ' + (size[1] + lineWidth * 2) + '"style="z-index:' + zIndex + ';position:absolute"collide=' + collide + ' x=' + pos[0] + ' y=' + pos[1] + ' width=' + size[0] + ' height=' + size[1] + ' transform="scale(1,-1)translate(' + pos[0] + ',' + pos[1] + ')"><g><path style="fill:' + fillColorTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineColorTxt + '" d="' + path + '"/></g></svg>';
	}
	main (bytes)
	{
		this.bytes=new Uint8Array(bytes);
		// Init
		const f=(ts)=>{
			this.dt=(ts-this.prev)/1000;
			this.prev=ts;
			window.requestAnimationFrame(f)
			// Update
		};
		window.requestAnimationFrame((ts)=>{
			this.prev=ts;
			window.requestAnimationFrame(f)
		});
	}
}
var $=new api
'''

def GenJsAPI ():
	global userJS
	skip = []
	if not IsInAnyElement('draw_svg', [ userJS, initCode, updateCode ]):
		skip.append('draw_svg')
	if not IsInAnyElement('add_group', [ userJS, initCode, updateCode ]):
		skip.append('add_group')
	if not IsInAnyElement('copy_node', [ userJS, initCode, updateCode ]):
		skip.append('copy_node')
	if not IsInAnyElement('clamp', [ userJS, initCode, updateCode ]):
		skip.append('clamp')
	if not IsInAnyElement('get_pos_and_size', [ userJS, initCode, updateCode ]):
		skip.append('get_pos_and_size')
	if not IsInAnyElement('lerp', [ userJS, initCode, updateCode ]):
		skip.append('lerp')
	if not IsInAnyElement('inv_lerp', [ userJS, initCode, updateCode ]):
		skip.append('inv_lerp')
	if not IsInAnyElement('remap', [ userJS, initCode, updateCode ]):
		skip.append('remap')
	if not IsInAnyElement('get_svg_path', [ userJS, initCode, updateCode ]):
		skip.append('get_svg_path')
	if not IsInAnyElement('overlaps', [ userJS, initCode, updateCode ]):
		skip.append('overlaps')
	if not IsInAnyElement('random', [ userJS, initCode, updateCode ]):
		skip.append('random')
	js = [ userJS, JS, JS_API ]
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	return js

def GenHtml (world, datas, background = ''):
	global userJS
	global colors
	global initCode
	global updateCode
	jsTmp = '/tmp/api.js'
	js = GenJsAPI()
	open(jsTmp, 'w').write(js)
	if world.minify:
		js = subprocess.run(('uglifyjs -m -- ' + jsTmp).split(), capture_output = True).stdout
		open(jsTmp, 'wb').write(js)
		if os.path.isfile('SlimeJump.py'):
			import SlimeJump as slimJump
			slimJump.Minify (jsTmp)
	cmd = [ 'gzip', '--keep', '--force', '--verbose', '--best', jsTmp ]
	print(cmd)
	subprocess.check_call(cmd)
	
	jsZipped = open(jsTmp + '.gz', 'rb').read()
	jsB = base64.b64encode(jsZipped).decode('utf-8')
	dataFilePath = '/tmp/js13kjam Data'
	open(dataFilePath, 'w').write(''.join(datas))
	cmd = [ 'gzip', '--keep', '--force', '--verbose', '--best', dataFilePath ]
	print(cmd)
	subprocess.check_call(cmd)

	datas = open(dataFilePath + '.gz', 'rb').read()
	datas = base64.b64encode(datas).decode('utf-8')
	colorsFilePath = '/tmp/js13kjam Colors'
	colors = json.dumps(colors)
	open(colorsFilePath, 'w').write(colors)
	cmd = [ 'gzip', '--keep', '--force', '--verbose', '--best', colorsFilePath ]
	print(cmd)
	subprocess.check_call(cmd)

	colors = open(colorsFilePath + '.gz', 'rb').read()
	colors = base64.b64encode(colors).decode('utf-8')
	if background:
		background = 'background-color:%s;' %background
	o = [
		'<!DOCTYPE html>',
		'<html>',
		'<body style="%swidth:600px;height:300px;overflow:hidden;">' %background,
		'<script>', 
		'var $0="%s";' %jsB,
		'var $1="%s";' %datas,
		'var $2="%s";' %colors,
		HTML,
		'</script>',
	]
	htmlSize = len('\n'.join(o))
	buildInfo['js-size'] = len(js)
	buildInfo['js-gz-size'] = len(jsZipped)
	if not world.invalid_html:
		o += [
			'</body>',
			'</html>',
		]
		htmlSize += len('</body></html>')
	buildInfo['html-size'] = htmlSize
	return '\n'.join(o)

SERVER_PROC = None

def Build (world):
	global SERVER_PROC
	if SERVER_PROC:
		SERVER_PROC.kill()
	blenderInfo = GetBlenderData()
	datas = blenderInfo[0]
	datas = '['.join(datas).replace(', ', ',').replace('.0', '').replace(']', '').replace('\'', '').replace(',[', '[').replace('True', 'T').replace('False', '')
	html = GenHtml(world, datas)
	open('/tmp/index.html', 'w').write(html)
	if world.js13kb:
		if os.path.isfile('/usr/bin/zip'):
			cmd = [ 'zip', '-9', 'index.html.zip', 'index.html' ]
			print(cmd)
			subprocess.check_call(cmd, cwd='/tmp')

			zip = open('/tmp/index.html.zip','rb').read()
			buildInfo['zip-size'] = len(zip)
			if world.export_zip:
				out = os.path.expanduser(world.export_zip)
				if not out.endswith('.zip'):
					out += '.zip'
				buildInfo['zip'] = out
				print('saving:', out)
				open(out, 'wb').write(zip)
			else:
				buildInfo['zip'] = '/tmp/index.html.zip'
		else:
			if len(html.encode('utf-8')) > 1024 * 13:
				raise SyntaxError('Final HTML is over 13kb')

	if world.export_html:
		out = os.path.expanduser(world.export_html)
		print('saving:', out)
		open(out,'w').write(html)
		webbrowser.open(out)

	else:
		cmd = [ 'python', '-m', 'http.server', '6969' ]
		SERVER_PROC = subprocess.Popen(cmd, cwd = '/tmp')

		atexit.register(lambda: SERVER_PROC.kill())
		webbrowser.open('http://localhost:6969')

	return html

def Update ():
	for ob in bpy.data.objects:
		if len(ob.material_slots) == 0 or ob.material_slots[0].material == None:
			continue
		mat = ob.material_slots[0].material
		mat.use_nodes = False
		indexOfPeriod = mat.name.find('.')
		if indexOfPeriod != -1:
			origName = mat.name[: indexOfPeriod]
			for ob2 in bpy.data.objects:
				if len(ob2.material_slots) > 0 and ob2.material_slots[0].material.name == origName:
					ob.material_slots[0].material = ob2.material_slots[0].material
			bpy.data.materials.remove(mat)
	for txt in bpy.data.texts:
		indexOfPeriod = txt.name.find('.')
		if indexOfPeriod != -1:
			for ob in bpy.data.objects:
				for i in range(MAX_SCRIPTS_PER_OBJECT):
					attachedTxt = getattr(ob, 'apiScript' + str(i))
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: indexOfPeriod]:
								setattr(ob, 'apiScript' + str(i), origTxt)
								break
					attachedTxt = getattr(ob, 'runtimeScript' + str(i))
					if attachedTxt == txt:
						for origTxt in bpy.data.texts:
							if origTxt.name == txt.name[: indexOfPeriod]:
								setattr(ob, 'runtimeScript' + str(i), origTxt)
								break
			bpy.data.texts.remove(txt)
	return 0.1

bpy.types.World.export_scale = bpy.props.FloatProperty(name = 'Scale', default = 1)
bpy.types.World.export_offset_x = bpy.props.IntProperty(name = 'Offset X', default = 0)
bpy.types.World.export_offset_y = bpy.props.IntProperty(name = 'Offset Y', default = 0)
bpy.types.World.export_html = bpy.props.StringProperty(name = 'Export (.html)')
bpy.types.World.export_zip = bpy.props.StringProperty(name = 'Export (.zip)')
bpy.types.World.minify = bpy.props.BoolProperty(name = 'Minifiy')
bpy.types.World.js13kb = bpy.props.BoolProperty(name = 'js13k: Error on export if output is over 13kb')
bpy.types.World.invalid_html = bpy.props.BoolProperty(name = 'Save space with invalid html wrapper')
bpy.types.Object.collide = bpy.props.BoolProperty(name = 'Collide')
bpy.types.Object.useSvgStroke = bpy.props.BoolProperty(name = 'Use svg stroke')
bpy.types.Object.svgStrokeWidth = bpy.props.FloatProperty(name='Svg stroke width', default = 0)
bpy.types.Object.svgStrokeColor = bpy.props.FloatVectorProperty(name='Svg stroke color', subtype = 'COLOR', default = [0, 0, 0])

for i in range(MAX_SCRIPTS_PER_OBJECT):
	setattr(
		bpy.types.Object,
		'apiScript' + str(i),
		bpy.props.PointerProperty(name = 'API script%s' % i, type = bpy.types.Text),
	)
	setattr(
		bpy.types.Object,
		'apiScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable'),
	)
	setattr(
		bpy.types.Object,
		'runtimeScript' + str(i),
		bpy.props.PointerProperty(name = 'Runtime script%s' % i, type = bpy.types.Text),
	)
	setattr(
		bpy.types.Object,
		'runtimeScript%sDisable' %i,
		bpy.props.BoolProperty(name = 'Disable'),
	)
	setattr(
		bpy.types.Object,
		'initScript' + str(i),
		bpy.props.BoolProperty(name = 'Is init'),
	)

@bpy.utils.register_class
class ScriptsPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Object_Panel'
	bl_label = 'Object'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'object'

	def draw (self, context):
		if not context.active_object:
			return
		ob = context.active_object
		self.layout.prop(ob, 'collide')
		self.layout.prop(ob, 'useSvgStroke')
		self.layout.prop(ob, 'svgStrokeWidth')
		self.layout.prop(ob, 'svgStrokeColor')
		self.layout.label(text = 'Scripts')
		foundUnassignedScript = False
		for i in range(MAX_SCRIPTS_PER_OBJECT):
			hasProperty = getattr(ob, 'apiScript' + str(i)) != None
			if hasProperty or not foundUnassignedScript:
				row = self.layout.row()
				row.prop(ob, 'apiScript' + str(i))
				row.prop(ob, 'apiScript%sDisable' %i)
			if not foundUnassignedScript:
				foundUnassignedScript = not hasProperty
		foundUnassignedScript = False
		for i in range(MAX_SCRIPTS_PER_OBJECT):
			hasProperty = getattr(ob, 'runtimeScript' + str(i)) != None
			if hasProperty or not foundUnassignedScript:
				row = self.layout.row()
				row.prop(ob, 'runtimeScript' + str(i))
				row.prop(ob, 'initScript' + str(i))
				row.prop(ob, 'runtimeScript%sDisable' %i)
			if not foundUnassignedScript:
				foundUnassignedScript = not hasProperty

if __name__ == '__main__':
	q = o = test = None
	for arg in sys.argv:
		if arg.endswith('bits'):
			q = arg.split('--')[-1]
		elif arg.startswith('--stroke-opt='):
			o = arg.split('=')[-1]
		elif arg.startswith('--test='):
			test = arg.split('=')[-1]
		elif arg.startswith('--output='):
			bpy.data.worlds[0].export_html = arg.split('=')[-1]
		elif arg == '--minifiy':
			bpy.data.worlds[0].minify = True
		elif arg == '--js13k':
			bpy.data.worlds[0].minify = True
			bpy.data.worlds[0].js13kb = True
			bpy.data.worlds[0].invalid_html = True
	bpy.app.timers.register(Update)
	if '--build' in sys.argv:
		Build (bpy.data.worlds[0])