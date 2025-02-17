import os, sys, subprocess, atexit, webbrowser, base64
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

def IsCircle (ob):
	if len(ob.data.vertices) == 32 and len(ob.data.polygons) == 1:
		return True
	else:
		return False

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

def HasScript (ob, isMethod : bool):
	type = 'runtime'
	if isMethod:
		type = 'method'
	for i in range(MAX_SCRIPTS_PER_OBJECT):
		txt = getattr(ob, type + 'Script' + str(i))
		if txt != None:
			return True
	return False

# def CurveToMesh (curve):
# 	deg = bpy.context.evaluated_depsgraph_get()
# 	mesh = bpy.data.meshes.new_from_object(curve.evaluated_get(deg), depsgraph = deg)
# 	ob = bpy.data.objects.new(curve.name + "_Mesh", mesh)
# 	bpy.context.collection.objects.link(ob)
# 	ob.matrix_world = curve.matrix_world
# 	return ob

# def ToVector2 (v : Vector):
# 	return Vector((v.x, v.y))

def ToVector3 (v : Vector):
	return Vector(( v.x, v.y, 0 ))

# def Abs (v : Vector, is2d : bool = False):
# 	if is2d:
# 		return Vector((abs(v.x), abs(v.y)))
# 	else:
# 		return Vector((abs(v.x), abs(v.y), abs(v.z)))

# def Round (v : Vector, is2d : bool = False):
# 	if is2d:
# 		return Vector((round(v.x), round(v.y)))
# 	else:
# 		return Vector((round(v.x), round(v.y), round(v.z)))

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

def Divide (v : Vector, v2 : Vector, use2D : bool = False):
	if use2D:
		return Vector(( v.x / v2.x, v.y / v2.y ))
	else:
		return Vector(( v.x / v2.x, v.y / v2.y, v.z / v2.z ))

def ToNormalizedPoint (minMax : [],  v : Vector):
	return Divide(Vector(( 1, 1 )), (minMax[1] - minMax[0]), True) * (v - minMax[0])

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

def IsInAnyElement (o, arr : list):
	for elmt in arr:
		if o in elmt:
			return True
	return False

def Copy (ob, copyData = True, copyActions = True, collection = None):
	copy = ob.copy()
	if copyData:
		copy.data = copy.data.copy()
	if copyActions and copy.animation_data:
		copy.animation_data.action = copy.animation_data.action.copy()
	if collection == None:
		collection = bpy.context.collection
	collection.objects.link(copy)
	for child in ob.children:
		childCopy = Copy(child, copyData, copyActions, collection)
		childCopy.parent = copy
	return copy

DEFAULT_COLOR = [ 0, 0, 0, 0 ]
exportedObs = []
meshes = []
curves = []
empties = []
initCode = []
updateCode = []
datas = []
svgText = ''
userJsAPI = ''

def ExportObject (ob, html = None):
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
	z += offY
	sx, sy, sz = ob.scale * SCALE
	if ob.type == 'EMPTY' and len(ob.children) > 0:
		empties.append(ob)
		if HandleCopyObject(ob, Vector((x, y))):
			return
		for child in ob.children:
			ExportObject (child)
		firstAndLastChildIdsTxt = ''
		firstAndLastChildIdsTxt += ob.children[0].name + ';' + ob.children[-1].name
		datas.append([ob.name, firstAndLastChildIdsTxt])
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
		min *= Vector((sx, sy))
		max *= Vector((sx, sy))
		min += off
		max += off
		if HandleCopyObject(ob, min):
			return
		data = []
		data.append(round(min.x))
		data.append(round(min.y))
		size = max - min
		data.append(round(size.x))
		data.append(round(size.y))
		materialColor = DEFAULT_COLOR
		if len(ob.material_slots) > 0:
			materialColor = ob.material_slots[0].material.diffuse_color
		data.append(round(materialColor[0] * 255))
		data.append(round(materialColor[1] * 255))
		data.append(round(materialColor[2] * 255))
		data.append(round(materialColor[3] * 255))
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
		for i, pathValue in enumerate(pathData_):
			pathData_[i] = int(pathValue + offset[i % 2])
		strokeWidth = 0
		if ob.useSvgStroke:
			strokeWidth = ob.svgStrokeWidth
		data.append(strokeWidth)
		data.append(round(ob.svgStrokeColor[0] * 255))
		data.append(round(ob.svgStrokeColor[1] * 255))
		data.append(round(ob.svgStrokeColor[2] * 255))
		data.append(ob.name)
		data.append(str(pathData_)[1 : -1].replace(', ', ' '))
		data.append(ob.data.splines[0].use_cyclic_u)
		data.append(round(ob.location.z))
		data.append(ob.collide)
		datas.append(data)
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
			datas.append([obNameWithoutPeriod, round(pos[0]), round(pos[1])])
			exportedObs.append(ob)
			return True
	return False

def GetBlenderData (world, html = None, methods = {}):
	global datas
	global meshes
	global curves
	global empties
	global svgText
	global initCode
	global userJsAPI
	global updateCode
	global exportedObs
	for ob in bpy.data.objects:
		if '_Clone' in ob.name:
			for child in ob.children:
				bpy.data.objects.remove(child, do_unlink = True)
			bpy.data.objects.remove(ob, do_unlink = True)
	exportedObs = []
	userJsAPI = ''
	meshes = []
	curves = []
	empties = []
	datas = []
	initCode = []
	updateCode = []
	for ob in bpy.data.objects:
		ExportObject (ob, html)
	for ob in bpy.data.objects:
		for script in GetScripts(ob, True):
			userJsAPI += script
		for scriptInfo in GetScripts(ob, False):
			script = scriptInfo[0]
			isInit = scriptInfo[1]
			if isInit:
				initCode.append(script)
			else:
				updateCode.append(script)
	return (datas, initCode, updateCode, userJsAPI)

_BUILD_INFO = {
	'native': None,
	'html'  : None,
	'native-size':None,
	'html-size':None,
	'zip'     : None,
	'zip-size': None,
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

	def draw(self, context):
		row = self.layout.row()
		row.prop(context.world, 'export_scale')
		row = self.layout.row()
		row.prop(context.world, 'export_offset_x')
		row.prop(context.world, 'export_offset_y')
		self.layout.prop(context.world, 'export_opt')
		self.layout.prop(context.world, 'export_html')
		self.layout.operator('world.export', icon = 'CONSOLE')
		if _BUILD_INFO['native-size']:
			self.layout.label(text = 'exe kb=%s' %( _BUILD_INFO['native-size'] / 1024 ))

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
			if _BUILD_INFO['zip-size']:
				self.layout.label(text = _BUILD_INFO['zip'])
				if _BUILD_INFO['zip-size'] <= 1024*13:
					self.layout.label(text = 'zip bytes=%s' %( _BUILD_INFO['zip-size'] ))
				else:
					self.layout.label(text = 'zip KB=%s' %( _BUILD_INFO['zip-size'] / 1024 ))
				self.layout.label(text = 'html-size=%s' % _BUILD_INFO['html-size'])
				self.layout.label(text = 'js-size=%s' % _BUILD_INFO['js-size'])
				self.layout.label(text = 'js-gz-size=%s' % _BUILD_INFO['js-gz-size'])
		if _BUILD_INFO['html-size']:
			if _BUILD_INFO['html-size'] < 1024*16:
				self.layout.label(text = 'html bytes=%s' %( _BUILD_INFO['html-size'] ))
			else:
				self.layout.label(text = 'html KB=%s' %( _BUILD_INFO['html-size'] / 1024 ))

JS_DECOMP = '''var $d=async(u,t)=>{
	var d=new DecompressionStream('gzip')
	var r=await fetch('data:application/octet-stream;base64,'+u)
	var b=await r.blob()
	var s=b.stream().pipeThrough(d)
	var o=await new Response(s).blob()
	if(t) return await o.text()
	else return await o.arrayBuffer()
}
$d($0,1).then((j)=>{
	$=eval(j)
	for(var v of $1.split('['))
	{
		v=v.split(',')
		var l=v.length
		if(l>3)
		{
			var d=v[13].split(' ')
			var p=[]
			for(var e of d)
				p.push(parseInt(e))
			$.draw_svg([parseInt(v[0]),parseInt(v[1])],[parseInt(v[2]),parseInt(v[3])],[parseInt(v[4]),parseInt(v[5]),parseInt(v[6]),parseInt(v[7])],v[8],[parseInt(v[9]),parseInt(v[10]),parseInt(v[11])],v[12],$.get_svg_path(p,v[14]!=''),parseInt(v[15]),v[16]!='',v[17]!='')
		}
		else if(l>2)
			$.copy_node(v[0],[parseInt(v[1]),parseInt(v[2])])
		else
			$.add_group(v[0],v[1])
	}
	$.main(document.body.innerHTML)
})'''
JS_API = '''
class api
{
	get_svg_path (pathData, cyclic)
	{
		var path = 'M ' + pathData[0] + ',' + pathData[1] + ' ';
		for (var i = 2; i < pathData.length; i += 2)
		{
			if (i - 2 % 6 == 0)
				path += 'C ';
			path += '' + pathData[i] + ',' + pathData[i + 1] + ' ';
		}
		if (cyclic)
			path += 'Z';
		return path;
	}
	get_pos_and_size (elmt)
	{
		return [[parseFloat(elmt.getAttribute('x')), parseFloat(elmt.getAttribute('y'))], [parseFloat(elmt.getAttribute('width')), parseFloat(elmt.getAttribute('height'))]]
	}
	lerp (min, max, t)
	{
		return min + t * (max - min)
	}
	clamp (n, min, max)
	{
		return Math.min(Math.max(n, min), max);
	}
	inv_lerp (from, to, n)
	{
		return (n - from) / (to - from);
	}
	remap (inFrom, inTo, outFrom, outTo, n)
	{
		return lerp(outFrom, outTo, inv_lerp(inFrom, inTo, n));
	}
	overlaps (pos, size, pos2, size2)
	{
		return !(pos[0] + size[0] < pos2[0]
			|| pos[0] > pos2[0] + size2[0]
			|| pos[1] + size[1] < pos2[1]
			|| pos[1] > pos2[1] + size2[1])
	}
	copy_node (id, pos)
	{
		var copy = document.getElementById(id).cloneNode(true);
		copy.setAttribute('x', pos[0]);
		copy.setAttribute('y', pos[1]);
		document.body.appendChild(copy);
		return copy;
	}
	random_vector_2d (mD)
	{
		var dt = random(0, mD);
		var ag = random(0, 2 * Math.PI);
		return [ Math.cos(ag) * dt, Math.sin(ag) * dt ];
	}
	random (min, max)
	{
		return Math.random() * (max - min) + min;
	}
	add_group (id, firstAndLastChildIds)
	{
		var children = firstAndLastChildIds.split(';');
		var html = document.body.innerHTML;
		var indexOfFirstChild = html.lastIndexOf('<svg', html.indexOf(children[0]));
		var indexOfLastChild = html.indexOf('</svg>', html.indexOf(children[1])) + 6;
		document.body.innerHTML = html.slice(0, indexOfFirstChild) + '<g id="' + id + '">' + html.slice(indexOfFirstChild, indexOfLastChild) + '</g>' + html.slice(indexOfLastChild);
	}
	draw_svg (pos, size, fillColor, lineWidth, lineColor, id, pathData, zIndex, collide)
	{
		var fillColorTxt = 'transparent';
		if (fillColor[3] > 0)
			fillColorTxt = 'rgb(' + fillColor[0] + ' ' + fillColor[1] + ' ' + fillColor[2] + ')';
		var lineColorTxt = 'transparent';
		if (lineWidth > 0)
			lineColorTxt = 'rgb(' + lineColor[0] + ' ' + lineColor[1] + ' ' + lineColor[2] + ')';
		document.body.innerHTML += '<svg xmlns="www.w3.org/2000/svg"id="' + id + '"viewBox="0 0 ' + (size[0] + lineWidth * 2) + ' ' + (size[1] + lineWidth * 2) + '"style="z-index:' + zIndex + ';position:absolute"collide=' + collide + ' x=' + pos[0] + ' y=' + pos[1] + ' width=' + size[0] + ' height=' + size[1] + ' transform="scale(1,-1)translate(' + pos[0] + ',' + pos[1] + ')"><g><path style="fill:' + fillColorTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineColorTxt + '" d="' + pathData + '"/></g></svg>';
	}
	main (bytes)
	{
		// Init
		this.bytes=new Uint8Array(bytes);
		const f=(ts)=>{
			this.dt=(ts-this.prev)/1000;
			this.prev=ts;
			window.requestAnimationFrame(f)
		};
		window.requestAnimationFrame((ts)=>{
			this.prev=ts;
			window.requestAnimationFrame(f)
			// Update
		});
	}
}
new api
'''

def GenJsAPI ():
	global userJsAPI
	skip = []
	if not IsInAnyElement('draw_svg', [ userJsAPI, initCode, updateCode ]):
		skip.append('draw_svg')
	if not IsInAnyElement('add_group', [ userJsAPI, initCode, updateCode ]):
		skip.append('add_group')
	if not IsInAnyElement('copy_node', [ userJsAPI, initCode, updateCode ]):
		skip.append('copy_node')
	if not IsInAnyElement('clamp', [ userJsAPI, initCode, updateCode ]):
		skip.append('clamp')
	if not IsInAnyElement('get_pos_and_size', [ userJsAPI, initCode, updateCode ]):
		skip.append('get_pos_and_size')
	if not IsInAnyElement('lerp', [ userJsAPI, initCode, updateCode ]):
		skip.append('lerp')
	if not IsInAnyElement('inv_lerp', [ userJsAPI, initCode, updateCode ]):
		skip.append('inv_lerp')
	if not IsInAnyElement('remap', [ userJsAPI, initCode, updateCode ]):
		skip.append('remap')
	if not IsInAnyElement('get_svg_path', [ userJsAPI, initCode, updateCode ]):
		skip.append('get_svg_path')
	if not IsInAnyElement('overlaps', [ userJsAPI, initCode, updateCode ]):
		skip.append('overlaps')
	if not IsInAnyElement('random', [ userJsAPI, initCode, updateCode ]):
		skip.append('random')
	js = [ userJsAPI, JS_API ]
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	return js

def GenHtml (world, datas, background = ''):
	global initCode
	global updateCode
	global userJsAPI
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
	
	js = open(jsTmp + '.gz', 'rb').read()
	jsB = base64.b64encode(js).decode('utf-8')
	if background:
		background = 'background-color:%s;' %background
	o = [
		'<!DOCTYPE html>',
		'<html>',
		'<body style="%swidth:600px;height:300px;overflow:hidden;">' %background,
		'<script>', 
		'var $0="%s";' %jsB,
		'var $1="%s";' %datas,
		JS_DECOMP,
		'</script>',
	]
	hSize = len('\n'.join(o))
	_BUILD_INFO['js-size'] = len(js)
	_BUILD_INFO['js-gz-size'] = len(js)
	if not world.invalid_html:
		o += [
			'</body>',
			'</html>',
		]
		hSize += len('</body></html>')
	_BUILD_INFO['html-size'] = hSize
	return '\n'.join(o)

SERVER_PROC = None
WORLD = None
def Build (world):
	global SERVER_PROC, WORLD
	WORLD = world
	if SERVER_PROC:
		SERVER_PROC.kill()
	blenderInfo = GetBlenderData(world)
	datas = blenderInfo[0]
	datas = str(datas)[2 :].replace(', ', ',').replace('.0', '').replace(']', '').replace('\'', '').replace(',[', '[').replace('True', 'T').replace('False', '')
	html = GenHtml(world, datas)
	open('/tmp/index.html', 'w').write(html)
	if world.js13kb:
		if os.path.isfile('/usr/bin/zip'):
			cmd = [ 'zip', '-9', 'index.html.zip', 'index.html' ]
			print(cmd)
			subprocess.check_call(cmd, cwd='/tmp')

			zip = open('/tmp/index.html.zip','rb').read()
			_BUILD_INFO['zip-size'] = len(zip)
			if world.export_zip:
				out = os.path.expanduser(world.export_zip)
				if not out.endswith('.zip'):
					out += '.zip'
				_BUILD_INFO['zip'] = out
				print('saving:', out)
				open(out, 'wb').write(zip)
			else:
				_BUILD_INFO['zip'] = '/tmp/index.html.zip'
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
bpy.types.World.export_opt = bpy.props.EnumProperty(
	name = 'Optimize',
	items = [
		('O0', 'O0', 'Safe, no optimizations, emit debug info.'), 
		('O1', 'O1', 'Safe, high optimization, emit debug info.'), 
		('O2', 'O2', 'Unsafe, high optimization, emit debug info.'), 
		('O3', 'O3', 'Unsafe, high optimization, single module, emit debug info.'), 
		('O4', 'O4', 'Unsafe, highest optimization, relaxed maths, single module, emit debug info, no panic messages.'),
		('O5', 'O5', 'Unsafe, highest optimization, fast maths, single module, emit debug info, no panic messages, no backtrace.'),
		('Os', 'Os', 'Unsafe, high optimization, small code, single module, no debug info, no panic messages.'),
		('Oz', 'Oz', 'Unsafe, high optimization, tiny code, single module, no debug info, no panic messages, no backtrace.'),
	]
)
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
		elif arg.startswith('--O'):
			bpy.data.worlds[0].export_opt = arg[2 :]
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