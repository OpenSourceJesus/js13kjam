import os, sys, subprocess, atexit, webbrowser, base64, string, json
_thisdir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisdir)

isLinux = isWindows = c3gz = c3zip = None
if sys.platform == 'win32':
	BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe'
	c3zip = 'https://github.com/c3lang/c3c/releases/download/latest/c3-windows.zip'
	isWindows = True
elif sys.platform == 'darwin':
	BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
else:
	BLENDER = 'blender'
	isLinux = True

EMSDK = os.path.join(_thisdir, 'emsdk')
if '--install-wasm' in sys.argv and not os.path.isdir(EMSDK):
	cmd = [
		'git','copy','--depth','1',
		'https://github.com/emscripten-core/emsdk.git',
	]
	print(cmd)
	subprocess.check_call(cmd)

if isWindows:
	EMCC = os.path.join(EMSDK, 'upstream/emscripten/emcc.exe')
else:
	EMCC = 'wasm-ld'

try:
	import bpy
	from mathutils import *
except:
	bpy = None

if __name__ == '__main__':
	if bpy:
		pass
	elif '--c3demo' in sys.argv:
		# Runs simple test without blender
		Build ()
		sys.exit()

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

# blender #
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

def GetSafeName (ob):
	return ob.name.replace('é', 'e').lower().replace('(', '_').replace(')', '_').replace('.', '_').replace(' ', '_')

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
# 		return Vector((int(v.x), int(v.y)))
# 	else:
# 		return Vector((int(v.x), int(v.y), int(v.z)))

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
userJsLibAPI = ''

def ExportObject (ob, html = None, useHtml = False):
	global datas
	if ob.hide_get() or ob in exportedObs:
		return
	world = bpy.data.worlds[0]
	resX = world.export_res_x
	resY = world.export_res_y
	SCALE = world.export_scale
	offX = world.export_offset_x
	offY = world.export_offset_y
	off = Vector(( offX, offY ))
	sname = GetSafeName(ob)
	x, y, z = ob.location * SCALE
	y = -y
	z = -z
	x += offX
	y += offY
	z += offY
	sx, sy, sz = ob.scale * SCALE
	idx = len(meshes + curves + empties)
	scripts = []
	if ob.type == 'EMPTY' and len(ob.children) > 0:
		empties.append(ob)
		if HandleCopyObject(ob, idx):
			return
		firstAndLastChildIdsTxt = ''
		firstAndLastChildIdsTxt += str(ob.children[0].name) + ',' + str(ob.children[-1].name)
		datas.append([ob.name, firstAndLastChildIdsTxt])
		for child in ob.children:
			ExportObject (child)
	elif ob.type == 'CURVE':
		curves.append(ob)
		if HandleCopyObject(ob, idx):
			return
		data = []
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
		data.append(round(min.x))
		data.append(round(min.y))
		size = max - min
		data.append(round(size.x))
		data.append(round(size.y))
		if len(ob.material_slots) > 0:
			materialColor = ob.material_slots[0].material.diffuse_color
		else:
			materialColor = DEFAULT_COLOR
		data.append(round(materialColor[0] * 255))
		data.append(round(materialColor[1] * 255))
		data.append(round(materialColor[2] * 255))
		svgText_ = svgText_[: indexOfParentGroupContents] + group + svgText_[indexOfParentGroupEnd :]
		pathDataIndicator = ' d="'
		indexOfPathDataStart = svgText_.find(pathDataIndicator) + len(pathDataIndicator)
		indexOfPathDataEnd = svgText_.find('"', indexOfPathDataStart)
		pathData = svgText_[indexOfPathDataStart : indexOfPathDataEnd]
		pathData = pathData.replace('.0', '')
		pathData_ = []
		pathDataLen = 0
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
			pathDataLen += 2
		minPathValue *= SCALE
		offset = -minPathValue
		for i, pathValue in enumerate(pathData_):
			pathData_[i] = int(pathValue + offset[i % 2])
		for i, quantizeTypeEnumItem in enumerate(QUANTIZE_TYPES_ENUM_ITEMS):
			if quantizeTypeEnumItem[0] == ob.quantizeType:
				quantizeType = i
				break
		strokeWidth = 0
		if ob.useSvgStroke:
			strokeWidth = ob.svgStrokeWidth
		data.append(strokeWidth)
		data.append(round(ob.svgStrokeColor[0] * 255))
		data.append(round(ob.svgStrokeColor[1] * 255))
		data.append(round(ob.svgStrokeColor[2] * 255))
		data.append(ob.name)
		data.append(pathData_)
		data.append(round(ob.location.z))
		data.append(ob.data.splines[0].use_cyclic_u)
		data.append(ob.collide)
		data.append(quantizeType)
		datas.append(data)
	exportedObs.append(ob)

def HandleCopyObject (ob, idx):
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
			datas.append([obNameWithoutPeriod])
			exportedObs.append(ob)
			return True
	return False

def GetBlenderData (world, html = None, useHtml = False, methods = {}):
	global datas
	global meshes
	global curves
	global empties
	global svgText
	global initCode
	global updateCode
	global exportedObs
	global userJsLibAPI
	for ob in bpy.data.objects:
		if '_Clone' in ob.name:
			for child in ob.children:
				bpy.data.objects.remove(child, do_unlink = True)
			bpy.data.objects.remove(ob, do_unlink = True)
	exportedObs = []
	userJsLibAPI = ''
	meshes = []
	curves = []
	empties = []
	datas = []
	initCode = []
	updateCode = []
	for ob in bpy.data.objects:
		ExportObject (ob, useHtml, html)
	for ob in bpy.data.objects:
		for script in GetScripts(ob, True):
			userJsLibAPI += script
		for scriptInfo in GetScripts(ob, False):
			script = scriptInfo[0]
			isInit = scriptInfo[1]
			if isInit:
				initCode.append(script)
			else:
				updateCode.append(script)
	return (datas, initCode, updateCode, userJsLibAPI)

_BUILD_INFO = {
	'native': None,
	'html'  : None,
	'native-size':None,
	'html-size':None,
	'zip'     : None,
	'zip-size': None,
}

@bpy.utils.register_class
class C3Export (bpy.types.Operator):
	bl_idname = 'c3.export'
	bl_label = 'C3 Export EXE'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		exe = BuildLinux(context.world)
		_BUILD_INFO['native'] = exe
		_BUILD_INFO['native-size'] = len(open(exe, 'rb').read())
		return { 'FINISHED' }

@bpy.utils.register_class
class C3Export (bpy.types.Operator):
	bl_idname = 'c3.export_wasm'
	bl_label = 'C3 Export WASM'

	@classmethod
	def poll (cls, context):
		return True

	def execute (self, context):
		exe = Build(context.world)
		return { 'FINISHED' }

@bpy.utils.register_class
class C3WorldPanel (bpy.types.Panel):
	bl_idname = 'WORLD_PT_C3World_Panel'
	bl_label = 'C3 Export'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'world'

	def draw(self, context):
		row = self.layout.row()
		row.prop(context.world, 'export_res_x')
		row.prop(context.world, 'export_res_y')
		row.prop(context.world, 'export_scale')
		row = self.layout.row()
		row.prop(context.world, 'export_offset_x')
		row.prop(context.world, 'export_offset_y')
		self.layout.prop(context.world, 'export_opt')
		self.layout.prop(context.world, 'export_html')

		self.layout.operator('c3.export_wasm', icon = 'CONSOLE')
		self.layout.operator('c3.export', icon = 'CONSOLE')
		if _BUILD_INFO['native-size']:
			self.layout.label(text = 'exe KB=%s' %( _BUILD_INFO['native-size']//1024 ))

@bpy.utils.register_class
class JS13KB_Panel (bpy.types.Panel):
	bl_idname = "WORLD_PT_JS13KB_Panel"
	bl_label = "js13kgames.com"
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	bl_context = "world"

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
					self.layout.label(text = "zip bytes=%s" %( _BUILD_INFO['zip-size'] ))
				else:
					self.layout.label(text = "zip KB=%s" %( _BUILD_INFO['zip-size']//1024 ))
				self.layout.label(text = 'html-size=%s' % _BUILD_INFO['html-size'])
				self.layout.label(text = 'jslib-size=%s' % _BUILD_INFO['jslib-size'])
				self.layout.label(text = 'jslib-gz-size=%s' % _BUILD_INFO['jslib-gz-size'])
		if _BUILD_INFO['html-size']:
			if _BUILD_INFO['html-size'] < 1024*16:
				self.layout.label(text = "wasm bytes=%s" %( _BUILD_INFO['html-size'] ))
			else:
				self.layout.label(text = "wasm KB=%s" %( _BUILD_INFO['html-size']//1024 ))

def BuildLinux (world):
	global WORLD
	WORLD = world
	o = GetBlenderData(world)
	o = '\n'.join(o)
	#print(o)
	tmp = '/tmp/c3blender.c3'
	open(tmp, 'w').write(o)
	bin = Build(input = tmp)
	return bin

JS_DECOMP = '''
var $d=async(u,t)=>{
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
	$d($1).then((r)=>{
		WebAssembly.instantiate(r,{env:$.proxy()}).then((c)=>{$.reset(r)});
	});
});
'''
JS_LIB_COLOR_HELPERS = '''
function color_hex_unpacked(r, g, b, a){
	r=r.toString(16).padStart(2,'0');
	g=g.toString(16).padStart(2,'0');
	b=b.toString(16).padStart(2,'0');
	a=a.toString(16).padStart(2,'0');
	return "#"+r+g+b+a
}
function getColorFromMemory(buf,ptr){
	const [r, g, b, a]=new Uint8Array(buf,ptr,4);
	return color_hex_unpacked(r, g, b, a)
}
'''
JS_LIB_API_ENV = '''
function make_environment(e){
	return new Proxy(e,{
		get(t,p,r) {
			if(e[p]!==undefined){return e[p].bind(e)}
			return(...args)=>{throw p}
		}
	})
}
'''
JS_LIB_API_ENV_MINI = '''
function make_environment(e){
	return new Proxy(e,{
		get(t,p,r){return e[p].bind(e)}
	});
}
'''
JS_LIB_API = '''
function wasm_memory ()
{
	return $.wasm.instance.exports.memory.buffer;
}
function get_svg_path (pathData, pathDataLen, cyclic)
{
	var path = 'M ' + pathData[0] + ',' + pathData[1] + ' ';
	for (var i = 2; i < pathDataLen; i += 2)
	{
		if (i - 2 % 6 == 0)
			path += 'C ';
		path += '' + pathData[i] + ',' + pathData[i + 1] + ' ';
	}
	if (cyclic)
		path += 'Z';
	return path;
}
function get_pos_and_size (elmt)
{
	var posXTxt = elmt.getAttribute('x');
	var posX = parseFloat(posXTxt);
	var posYTxt = elmt.getAttribute('y');
	var posY = parseFloat(posYTxt);
	var sizeXTxt = elmt.getAttribute('width');
	var sizeX = parseFloat(sizeXTxt);
	var sizeYTxt = elmt.getAttribute('height');
	var sizeY = parseFloat(sizeYTxt);
	return [ [ posX, posY ], [ sizeX, sizeY ] ]
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
	var t = inv_lerp(inFrom, inTo, n);
	return lerp(outFrom, outTo, t);
}
function overlaps (pos, size, pos2, size2)
{
	return !(pos[0] + size[0] < pos2[0]
		|| pos[0] > pos2[0] + size2[0]
		|| pos[1] + size[1] < pos2[1]
		|| pos[1] > pos2[1] + size2[1])
}
function copy_node (id, pos)
{
	var copy = document.getElementById(id).cloneNode(true);
	copy.setAttribute('x', pos[0]);
	copy.setAttribute('y', pos[1]);
	document.body.appendChild(copy);
	return copy;
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
function add_group (id, firstAndLastChildIds)
{
	var children = firstAndLastChildIds.split(',');
	var html = document.body.innerHTML;
	var indexOfFirstChild = html.indexOf(children[1]);
	indexOfLastChild = html.indexOf('</svg>', indexOfFirstChild) + 6;
	var indexOfLastChild = html.indexOf(children[0]);
	indexOfLastChild = html.lastIndexOf('<', indexOfLastChild);
	document.body.innerHTML = html.slice(0, indexOfFirstChild) + '</g>' + html.slice(indexOfFirstChild);
	document.body.innerHTML = html.slice(0, indexOfLastChild) + '<g id="' + id + '">' + html.slice(indexOfLastChild);
}
function draw_svg (pos, size, fillColor, lineWidth, lineColor, id, pathData, zIndex, cyclic, collide, quantizeType)
{
	var fillColorTxt = 'transparent';
	if (fillColor[3] > 0)
		fillColorTxt = 'rgb(' + fillColor[0] + ' ' + fillColor[1] + ' ' + fillColor[2] + ')';
	var lineColorTxt = 'transparent';
	if (lineWidth > 0)
		lineColorTxt = 'rgb(' + lineColor[0] + ' ' + lineColor[1] + ' ' + lineColor[2] + ')';
	var prefix = '<svg xmlns="www.w3.org/2000/svg"id="' + id + '"viewBox="0 0 ' + (size[0] + lineWidth * 2) + ' ' + (size[1] + lineWidth * 2) + '"style="z-index:' + zIndex + ';position:absolute"collide=' + collide + ' x=' + pos[0] + ' y=' + pos[1] + ' width=' + size[0] + ' height=' + size[1] + ' transform="scale(1,-1)translate(' + pos[0] + ',' + pos[1] + ')"><g><path style="fill:' + fillColorTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineColorTxt + '" d="';
	var suffix = '"/></g></svg>';
	document.body.innerHTML += prefix + pathData + suffix;
}

class api{
	proxy(){
		return make_environment(this)
	}
	reset(bytes){
		// Init
		this.elts=[];
		this.bytes=new Uint8Array(bytes);
		this.canvas=document.getElementById(id);
		const f=(ts)=>{
			this.dt=(ts-this.prev)/1000;
			this.prev=ts;
			this.entryFunction();
			window.requestAnimationFrame(f)
		};
		window.requestAnimationFrame((ts)=>{
			this.prev=ts;
			window.requestAnimationFrame(f)
			// Update
		});
	}
'''
c3dom_api = {
	'html_new_text' : '''
	html_new_text(ptr, r, g, b, h, id)
	{
		var e = document.createElement('pre');
		e.style = 'position:absolute;left:' + r + '; top:' + g + '; font-size:' + b;
		e.hidden = h;
		e.id=cstr_by_ptr(wasm_memory(), id);
		document.body.append(e);
		e.append(cstr_by_ptr(wasm_memory(), ptr));
		return this.elts.push(e) - 1
	}
	''',
	'html_css_string' : '''
	html_css_string(idx,a,b){
		a=cstr_by_ptr(wasm_memory(),a);
		this.elts[idx].style[a]=cstr_by_ptr(wasm_memory(),b)
	}
	''',
	'html_css_int' : '''
	html_css_int(idx,a,b){
		a=cstr_by_ptr(wasm_memory(),a);
		this.elts[idx].style[a]=b
	}
	''',
	'html_set_text' : '''
	html_set_text(idx,ptr){
		this.elts[idx].firstChild.nodeValue=cstr_by_ptr(wasm_memory(),ptr)
	}
	''',
	'html_add_char' : '''
	html_add_char(idx,c){
		this.elts[idx].append(String.fromCharCode(c))
	}
	''',
	'html_css_scale' : '''
	html_css_scale(idx,z){
		this.elts[idx].style.transform='scale('+z+')'
	}
	''',
	'html_css_scale_y' : '''
	html_css_scale_y(idx,z){
		this.elts[idx].style.transform='scaleY('+z+')'
	}
	''',
	'html_set_position' : '''
	html_set_position(idx,x,y){
		var elt = this.elts[idx];
		elt.style.left = x;
		elt.style.top = y
	}
	''',
	'html_css_zindex' : '''
	html_css_zindex(idx,z){
		this.elts[idx].style.zIndex=z
	}
	''',
	'html_bind_onclick' : '''
	html_bind_onclick(idx,f,oidx){
		var elt=this.elts[idx];
		elt._onclick_=$.wasm.instance.exports.__indirect_function_table.get(f);
		elt.onclick=function(){
			self=elt;
			elt._onclick_(oidx)
		}
	}
	''',
	'html_eval' : '''
	html_eval(ptr){
		var _=cstr_by_ptr(wasm_memory(),ptr);
		eval(_)
	}
	''',
	'html_canvas_clear' : '''
	html_canvas_clear(){
		this.ctx.clearRect(0,0,this.canvas.width,this.canvas.height)
	}
	''',
	'html_canvas_resize' : '''
	html_canvas_resize(w,h){
		this.canvas.width=w;
		this.canvas.height=h
	}
	''',
	'wasm_memory' : '''
	wasm_memory(idx){
		return this.bytes[idx]
	}
	''',
	'wasm_size' : '''
	wasm_size(){
		return this.bytes.length
	}
	''',
	'random' : '''
	random(){
		return Math.random()
	}
	''',
}
raylib_like_api = {
	'raylib_js_set_entry' : '''
	_(f){
		this.entryFunction=$.wasm.instance.exports.__indirect_function_table.get(f)
	}
	''',
	'InitWindow' : '''
	InitWindow(w,h,ptr){
		this.canvas.width=w;
		this.canvas.height=h;
		document.title=cstr_by_ptr(wasm_memory(),ptr)
	}
	''',
	'GetScreenWidth' : '''
	GetScreenWidth(){
		return this.canvas.width
	}
	''',
	'GetScreenHeight' : '''
	GetScreenHeight(){
		return this.canvas.height
	}
	''',
	'GetFrameTime' : '''
	GetFrameTime(){
		return Math.min(this.dt,1/30/2)
	}
	''',
	'DrawRectangleV' : '''
	DrawRectangleV(pptr,sptr,cptr){
		const buf=wasm_memory();
		const p=new Float32Array(buf,pptr,2);
		const s=new Float32Array(buf,sptr,2);
		this.ctx.sStyle = getColorFromMemory(buf, cptr);
		this.ctx.fillRect(p[0],p[1],s[0],s[1])
	}
	''',
	'DrawSplineLinearWASM' : '''
	DrawSplineLinearWASM(ptr,l,t,fill,r, g, b, a){
		const buf=wasm_memory();
		const p=new Float32Array(buf,ptr,l*2);
		this.ctx.strokeStyle='black';
		if(fill)this.ctx.fillStyle='rgba('+r+','+g+','+b+','+a+')';
		this.ctx.lineWidth=t;
		this.ctx.beginPath();
		this.ctx.moveTo(p[0],p[1]);
		for(var i=2;i<p.length;i+=2)
			this.ctx.lineTo(p[i],p[i+1]);
		if(fill){
			this.ctx.closePath();
			this.ctx.fill()
		}
		this.ctx.stroke()
	}
	''',
	'DrawCircleWASM' : '''
	DrawCircleWASM(x,y,rad,ptr){
		const buf=wasm_memory();
		const [r, g, b, a]=new Uint8Array(buf, ptr, 4);
		this.ctx.strokeStyle = 'black';
		this.ctx.beginPath();
		this.ctx.arc(x,y,rad,0,2*Math.PI,false);
		this.ctx.fillStyle = color_hex_unpacked(r, g, b, a);
		this.ctx.closePath();
		this.ctx.stroke()
	}
	''',
	'ClearBackground' : '''
	ClearBackground(ptr) {
		this.ctx.fillStyle = getColorFromMemory(wasm_memory(), ptr);
		this.ctx.fillRect(0,0,this.canvas.width,this.canvas.height)
	}
	''',
	'GetRandomValue' : '''
	GetRandomValue(min,max) {
		return min+Math.floor(Math.random()*(max-min+1))
	}
	''',
	'ColorFromHSV' : '''
	ColorFromHSV(result_ptr, hue, saturation, value) {
		const buffer = wasm_memory();
		const result = new Uint8Array(buffer, result_ptr, 4);

		// Red channel
		let k = (5.0 + hue/60.0)%6;
		let t = 4.0 - k;
		k = (t < k)? t : k;
		k = (k < 1)? k : 1;
		k = (k > 0)? k : 0;
		result[0] = Math.floor((value - value*saturation*k)*255.0);

		// Green channel
		k = (3.0 + hue/60.0)%6;
		t = 4.0 - k;
		k = (t < k)? t : k;
		k = (k < 1)? k : 1;
		k = (k > 0)? k : 0;
		result[1] = Math.floor((value - value*saturation*k)*255.0);

		// Blue channel
		k = (1.0 + hue/60.0)%6;
		t = 4.0 - k;
		k = (t < k)? t : k;
		k = (k < 1)? k : 1;
		k = (k > 0)? k : 0;
		result[2] = Math.floor((value - value*saturation*k)*255.0);

		result[3] = 255;
	}
	''',
}

raylib_like_api_mini = {}
c3dom_api_mini = {}
def GenMiniAPI ():
	syms = list(string.ascii_lowercase)
	symsTier = 1
	for fName in raylib_like_api:
		code = raylib_like_api[fName].strip()
		if code.startswith(fName):
			if len(syms) == 0:
				for char in string.ascii_lowercase:
					sym = char
					for i in range(symsTier):
						sym += char
					syms.append(sym)
				symsTier += 1
			sym = syms.pop()
			code = sym + code[len(fName) :]
			raylib_like_api_mini[fName] = { 'sym' : sym, 'code' : code.replace('\t','') }
		else:
			# Hard coded syms
			sym = code.split('(')[0]
			raylib_like_api_mini[fName] = {'sym' : sym, 'code' : code.replace('\t','') }
	for fName in c3dom_api:
		code = c3dom_api[fName].strip()
		assert code.startswith(fName)
		if len(syms) == 0:
			for char in string.ascii_lowercase:
				sym = char
				for i in range(symsTier):
					sym += char
				syms.append(sym)
			symsTier += 1
		sym = syms.pop()
		code = sym + code[len(fName) :]
		c3dom_api_mini[fName] = { 'sym' : sym, 'code' : code.replace('\t','') }

GenMiniAPI ()

def GenJsAPI (world, userMethods):
	global userJsLibAPI
	skip = []
	if not IsInAnyElement('raylib::color_from_hsv', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('ColorFromHSV')
	if not IsInAnyElement('draw_circle_wasm', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('DrawCircleWASM')
	if not IsInAnyElement('raylib::draw_rectangle_v', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('DrawRectangleV')
	if not IsInAnyElement('raylib::clear_background', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('ClearBackground')
	if not IsInAnyElement('raylib::get_random_value', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('GetRandomValue')
	if not IsInAnyElement('draw_spline_wasm', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('DrawSplineLinearWASM')
	if not IsInAnyElement('raylib::get_screen_width', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('GetScreenWidth')
	if not IsInAnyElement('raylib::get_screen_height', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('GetScreenHeight')
	if not IsInAnyElement('draw_svg', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('draw_svg')
	if not IsInAnyElement('add_group', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('add_group')
	if not IsInAnyElement('copy_node', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('copy_node')
	if not IsInAnyElement('clamp', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('clamp')
	if not IsInAnyElement('get_pos_and_size', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('get_pos_and_size')
	if not IsInAnyElement('lerp', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('lerp')
	if not IsInAnyElement('inv_lerp', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('inv_lerp')
	if not IsInAnyElement('remap', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('remap')
	if not IsInAnyElement('get_svg_path', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('get_svg_path')
	if not IsInAnyElement('overlaps', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('overlaps')
	if not IsInAnyElement('random', [ userJsLibAPI, initCode, updateCode ]):
		skip.append('random')
	if world.js13kb:
		js = [ userJsLibAPI, JS_LIB_API_ENV_MINI, JS_LIB_API ]
	else:
		js = [ userJsLibAPI, JS_LIB_API_ENV, JS_LIB_API ]
	for fName in raylib_like_api:
		if fName in skip:
			print('Skipping:', fName)
			continue
		else:
			js.append(raylib_like_api[fName])
	for fName in userMethods:
		fudge = fName.replace('(', '(_,')
		js += [
			fudge + '{',
				'self=this.elts[_]',
				'this._%s;' % fName,
			'}',
			'_' + fName + '{',
			userMethods[fName],
			'}',
		]
	js.append('}')
	js.append('new api()')
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	if 'getColorFromMemory' in js or 'color_hex_unpacked' in js:
		js = JS_LIB_COLOR_HELPERS + js
	if world.minify:
		for methodName in raylib_like_api_mini:
			if methodName != 'raylib_js_set_entry':
				js = js.replace(methodName, raylib_like_api_mini[methodName]['sym'])
		rmap = {
			'const ': 'var ', 'entryFunction' : 'ef', 'make_environment' : 'me', 
			'color_hex_unpacked' : 'cu', 'getColorFromMemory' : 'gm', 
			'cstr_by_ptr' : 'cp', 'cstrlen' : 'cl',
			'this.canvas' : 'this._a',
			'window.requestAnimationFrame' : 'self.requestAnimationFrame',
		}
		for rep in rmap:
			if rep in js:
				js = js.replace(rep, rmap[rep])
	return js

def GenHtml (world, dataFile, userHTML = None, background = '', userMethods = {}, debug = '--debug' in sys.argv):
	global initCode
	global updateCode
	global userJsLibAPI
	cmd = [ 'gzip', '--keep', '--force', '--verbose', '--best', dataFile ]
	print(cmd)
	subprocess.check_call(cmd)
	
	wa = open(dataFile,'rb').read()
	w = open(dataFile +'.gz','rb').read()
	b = base64.b64encode(w).decode('utf-8')
	jsTmp = '/tmp/api.js'
	jsLib = GenJsAPI(world, userMethods)
	open(jsTmp, 'w').write(jsLib)
	if world.minify:
		jsLib = subprocess.run(('uglifyjs -m -- ' + jsTmp).split(), capture_output = True).stdout
		open(jsTmp, 'wb').write(jsLib)
		if os.path.isfile('SlimeJump.py'):
			import SlimeJump as slimJump
			slimJump.Minify (jsTmp)
	cmd = [ 'gzip', '--keep', '--force', '--verbose', '--best', jsTmp ]
	print(cmd)
	subprocess.check_call(cmd)
	
	js = open(jsTmp + '.gz', 'rb').read()
	jsB = base64.b64encode(js).decode('utf-8')
	if debug:
		background = 'red'
	if background:
		background = 'style="background-color:%s"' %background
	if world.invalid_html:
		o = [
			'<canvas id=$><script>',
			'$1="%s"' % b,
			'$0="%s"' % jsB,
			#JS_DECOMP.replace('\t','').replace('var ', '').replace('\n',''), # Breaks invalid canvas above
			JS_DECOMP.replace('\t','').replace('var ', ''), 
			'</script>',
		]
		hsize = len('\n'.join(o))
	else:
		o = [
			'<!DOCTYPE html>',
			'<html>',
			'<body %s style="width:600px;height:300px;overflow:hidden;">' %background,
			'<canvas id="$"></canvas>',
			'<script>', 
			'var $0="%s"' % jsB,
			'var $1="%s"' % b,
			JS_DECOMP.replace('\t',''), 
			'</script>',
		]
		if userHTML:
			o += userHTML
		hsize = len('\n'.join(o)) + len('</body></html>')
	_BUILD_INFO['html-size'] = hsize
	_BUILD_INFO['jslib-size'] = len(jsLib)
	_BUILD_INFO['jslib-gz-size'] = len(js)
	if debug:
		if world.invalid_html:
			o.append('</canvas>')
		o += [
			'<pre>',
			'jslib bytes=%s' % len(jsLib),
			'jslib.gz bytes=%s' % len(js),
			'jslib.base64 bytes=%s' % len(jsB),
			'wasm bytes=%s' % len(wa),
			'gzip bytes=%s' % len(w),
			'base64 bytes=%s' % len(b),
			'html bytes=%s' %(hsize - (len(b) + len(jsB))),
			'total bytes=%s' % hsize,
			'C3 optimization=%s' % WORLD.export_opt,
		]
		for ob in bpy.data.objects:
			if ob.type == 'GPENCIL':
				o.append('%s = %s' %(ob.name, ob.data.grease_quantize))
		o.append('</pre>')
	if not world.invalid_html:
		o += [
			'</body>',
			'</html>',
		]
	return '\n'.join(o)

SERVER_PROC = None
WORLD = None
def Build (world):
	global SERVER_PROC, WORLD
	WORLD = world
	if SERVER_PROC:
		SERVER_PROC.kill()
	userHTML = []
	userMethods = {}
	blenderInfo = GetBlenderData(world, html = userHTML, methods = userMethods)
	datas = blenderInfo[0]
	bytes = json.dumps(datas)
	print(bytes)
	tmp = '/tmp/js13kjam Data'
	open(tmp, 'w').write(bytes)
	html = GenHtml(world, tmp, userHTML, userMethods = userMethods)
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

bpy.types.Material.export_trifan = bpy.props.BoolProperty(name = 'Triangle fan')
bpy.types.Material.export_tristrip = bpy.props.BoolProperty(name = 'Triangle strip')

bpy.types.World.export_res_x = bpy.props.IntProperty(name = 'Resolution X', default = 800)
bpy.types.World.export_res_y = bpy.props.IntProperty(name = 'Resolution Y', default = 600)
bpy.types.World.export_scale = bpy.props.FloatProperty(name = 'Scale', default = 100)
bpy.types.World.export_offset_x = bpy.props.IntProperty(name = 'Offset X', default = 100)
bpy.types.World.export_offset_y = bpy.props.IntProperty(name = 'Offset Y', default = 100)

bpy.types.World.export_html = bpy.props.StringProperty(name = 'C3 export (.html)')
bpy.types.World.export_zip = bpy.props.StringProperty(name = 'C3 export (.zip)')
bpy.types.World.minify = bpy.props.BoolProperty(name = 'Minifiy')
bpy.types.World.js13kb = bpy.props.BoolProperty(name = 'js13k: Error on export if output is over 13KB')
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
bpy.types.Object.hide = bpy.props.BoolProperty(name = 'Hide')
bpy.types.Object.collide = bpy.props.BoolProperty(name = 'Collide')
QUANTIZE_TYPES_ENUM_ITEMS = [ ('UInt8', 'UInt8', ''),
	('UInt16', 'UInt16', ''),
	('UInt32', 'UInt32', '') ]
bpy.types.Object.quantizeType = bpy.props.EnumProperty(
	name = 'Svg quantize type',
	description = '',
	items = QUANTIZE_TYPES_ENUM_ITEMS
)
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
		self.layout.prop(ob, 'hide')
		self.layout.prop(ob, 'collide')
		self.layout.prop(ob, 'quantizeType')
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

@bpy.utils.register_class
class C3MaterialPanel (bpy.types.Panel):
	bl_idname = 'OBJECT_PT_Material_Panel'
	bl_label = 'C3 Material Settings'
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = 'material'

	def draw (self, context):
		if not context.active_object:
			return
		ob = context.active_object
		if not ob.type == 'GPENCIL' or not ob.data.materials:
			return
		mat = ob.data.materials[ ob.active_material_index ]
		self.layout.prop(mat, 'export_trifan')
		self.layout.prop(mat, 'export_tristrip')

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
	for ob in bpy.data.objects:
		if ob.type in [ 'MESH', 'CURVE', 'EMPTY' ]:
			ob.name = ob.name.replace('é', 'e').replace('(', '_').replace(')', '_')
	if '--test' in sys.argv or test:
		import c3blendgen
		if test:
			getattr(c3blendgen, test)(q, o)
		else:
			c3blendgen.gen_test_scene (q, o)
	if '--wasm' in sys.argv:
		Build (bpy.data.worlds[0])
	elif '--linux' in sys.argv:
		BuildLinux (bpy.data.worlds[0])