import os, sys, json, string, atexit, webbrowser, subprocess
_thisDir = os.path.split(os.path.abspath(__file__))[0]
sys.path.append(_thisDir)

isLinux = False
if sys.platform == 'win32':
	BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe'
elif sys.platform == 'darwin':
	BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
else:
	BLENDER = 'blender'
	for arg in sys.argv:
		if 'blender' in arg:
			BLENDER = arg
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
		cmd = [BLENDER]
		for arg in sys.argv:
			if arg.endswith('.blend'):
				cmd.append(arg)
				break
		cmd += ['--python-exit-code', '1', '--python', __file__, '--python', os.path.join(_thisDir, 'blender-curve-to-svg', 'curve_to_svg.py')]
		exArgs = []
		for arg in sys.argv:
			if arg.startswith('--'):
				exArgs.append(arg)
		if exArgs:
			cmd.append('--')
			cmd += exArgs
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
				scripts.append((txt.as_string(), getattr(ob, 'initScript' + str(i))))
	return scripts

def Clamp (n : float, min : float, max : float):
	if n < min:
		return min
	elif n > max:
		return max
	else:
		return n

def Multiply (v : list, multiply : list):
	output = []
	for i, elmt in enumerate(v):
		output.append(elmt * multiply[i])
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

def GetCurveRectMinMax (ob):
	bounds = [(ob.matrix_world @ Vector(corner)) for corner in ob.bound_box]
	box = []
	box.append(min([bounds[0][0], bounds[1][0], bounds[2][0], bounds[3][0]]))
	box.append(min([bounds[0][1], bounds[1][1], bounds[4][1], bounds[5][1]]))
	box.append(max([bounds[4][0], bounds[5][0], bounds[6][0], bounds[7][0]]))
	box.append(max([bounds[2][1], bounds[3][1], bounds[6][1], bounds[7][1]]))
	_min = Vector((box[0], box[1]))
	_max = Vector((box[2], box[3]))
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
	if collection == None:
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
	color_ = ClampComponents(Round(Multiply(color, [255, 255, 255, 255])), [0, 0, 0, 0], [255, 255, 255, 255])
	indexOfColor = IndexOfValue(color_, colors)
	keyOfColor = ''
	if indexOfColor == -1:
		keyOfColor = string.ascii_letters[len(colors)]
		colors[keyOfColor] = color_
	else:
		keyOfColor = string.ascii_letters[indexOfColor]
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

DEFAULT_COLOR = [0, 0, 0, 0]
exportedObs = []
datas = []
colors = {}
pathsDatas = []
initCode = []
updateCode = []
userJS = ''

def ExportObject (ob):
	if ob.hide_get() or ob in exportedObs:
		return
	world = bpy.data.worlds[0]
	SCALE = world.exportScale
	offX = world.exportOffsetX
	offY = world.exportOffsetY
	off = Vector((offX, offY))
	sx, sy, sz = ob.scale * SCALE
	if ob.type == 'EMPTY' and len(ob.children) > 0:
		if HandleCopyObject(ob, GetObjectPosition(ob)):
			return
		for child in ob.children:
			ExportObject (child)
		firstAndLastChildIdsTxt = ''
		firstAndLastChildIdsTxt += ob.children[0].name + ';' + ob.children[-1].name
		datas.append([ob.name, firstAndLastChildIdsTxt])
	elif ob.type == 'LIGHT':
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
		bpy.ops.object.select_all(action = 'DESELECT')
		ob.select_set(True)
		bpy.ops.curve.export_svg()
		svgTxt = open('/tmp/Output.svg', 'r').read()
		indexOfName = svgTxt.find(ob.name)
		indexOfGroupStart = svgTxt.rfind('\n', 0, indexOfName)
		groupEndIndicator = '</g>'
		indexOfGroupEnd = svgTxt.find(groupEndIndicator, indexOfGroupStart) + len(groupEndIndicator)
		group = svgTxt[indexOfGroupStart : indexOfGroupEnd]
		parentGroupIndicator = '\n  <g'
		indexOfParentGroupStart = svgTxt.find(parentGroupIndicator)
		indexOfParentGroupContents = svgTxt.find('\n', indexOfParentGroupStart + len(parentGroupIndicator))
		indexOfParentGroupEnd = svgTxt.rfind('</g')
		min, max = GetCurveRectMinMax(ob)
		scale = Vector((sx, sy))
		min *= scale
		min += off
		if HandleCopyObject(ob, min):
			return
		max *= scale
		max += off
		data = []
		svgTxt = svgTxt[: indexOfParentGroupContents] + group + svgTxt[indexOfParentGroupEnd :]
		pathDataIndicator = ' d="'
		indexOfPathDataStart = svgTxt.find(pathDataIndicator) + len(pathDataIndicator)
		indexOfPathDataEnd = svgTxt.find('"', indexOfPathDataStart)
		pathData = svgTxt[indexOfPathDataStart : indexOfPathDataEnd]
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
			vector = Vector((x, y))
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
		if ob.useSvgStroke:
			strokeWidth = ob.svgStrokeWidth
		jiggleDist = ob.jiggleDist * int(ob.useJiggle)
		x = min.x - strokeWidth / 2 - jiggleDist
		y = -max.y + strokeWidth / 2 + jiggleDist
		size = max - min
		size += Vector((1, 1)) * (strokeWidth + jiggleDist * 2)
		if ob.roundPosAndSize:
			x = int(round(x))
			y = int(round(y))
			size = Round(size)
			size = Vector(size)
		data.append(x)
		data.append(y)
		data.append(size.x)
		data.append(size.y)
		materialColor = DEFAULT_COLOR
		if len(ob.material_slots) > 0:
			materialColor = ob.material_slots[0].material.diffuse_color
		data.append(GetColor(materialColor))
		data.append(round(strokeWidth))
		data.append(GetColor(ob.svgStrokeColor))
		data.append(ob.name)
		pathsDatas.append(''.join(pathData))
		data.append(ob.data.splines[0].use_cyclic_u)
		data.append(round(ob.location.z))
		data.append(ob.collide)
		data.append(ob.jiggleDist * int(ob.useJiggle))
		data.append(ob.jiggleDur)
		data.append(ob.jiggleFrames * int(ob.useJiggle))
		data.append(ob.rotAngRange[0])
		data.append(ob.rotAngRange[1])
		data.append(ob.rotDur * int(ob.useRotate))
		data.append(ob.rotPingPong)
		data.append(ob.scaleXRange[0])
		data.append(ob.scaleXRange[1])
		data.append(ob.scaleYRange[0])
		data.append(ob.scaleYRange[1])
		data.append(ob.scaleDur * int(ob.useScale))
		data.append(ob.scaleHaltDurAtMin * int(ob.useScale))
		data.append(ob.scaleHaltDurAtMax * int(ob.useScale))
		data.append(ob.scalePingPong)
		data.append(ob.origin[0])
		data.append(ob.origin[1])
		data.append(ob.fillHatchDensity[0] * int(ob.useFillHatch[0]))
		data.append(ob.fillHatchDensity[1] * int(ob.useFillHatch[1]))
		data.append(ob.fillHatchRandDensity[0] / 100 * int(ob.useFillHatch[0]))
		data.append(ob.fillHatchRandDensity[1] / 100 * int(ob.useFillHatch[1]))
		data.append(ob.fillHatchAng[0] * int(ob.useFillHatch[0]))
		data.append(ob.fillHatchAng[1] * int(ob.useFillHatch[1]))
		data.append(ob.fillHatchWidth[0] * int(ob.useFillHatch[0]))
		data.append(ob.fillHatchWidth[1] * int(ob.useFillHatch[1]))
		data.append(ob.strokeHatchDensity[0] * int(ob.useStrokeHatch[0]))
		data.append(ob.strokeHatchDensity[1] * int(ob.useStrokeHatch[1]))
		data.append(ob.strokeHatchRandDensity[0] / 100 * int(ob.useStrokeHatch[0]))
		data.append(ob.strokeHatchRandDensity[1] / 100 * int(ob.useStrokeHatch[1]))
		data.append(ob.strokeHatchAng[0] * int(ob.useStrokeHatch[0]))
		data.append(ob.strokeHatchAng[1] * int(ob.useStrokeHatch[1]))
		data.append(ob.strokeHatchWidth[0] * int(ob.useStrokeHatch[0]))
		data.append(ob.strokeHatchWidth[1] * int(ob.useStrokeHatch[1]))
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
		data.append(ob.cycleDur)
		datas.append(data)
	exportedObs.append(ob)

def HandleMakeObjectMove (ob):
	if ob.moveSpeed != 0:
		waypoint1Pos = GetObjectPosition(ob.waypoint1)
		waypoint2Pos = GetObjectPosition(ob.waypoint2)
		move = Vector(Round(Vector((waypoint2Pos[0] - waypoint1Pos[0], waypoint2Pos[1] - waypoint1Pos[1]))))
		datas.append([ob.name, int(move[0]), int(move[1]), int(round(move.length / ob.moveSpeed * 1000))])

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
			datas.append([obNameWithoutPeriod, ob.name, int(pos[0]), int(pos[1])])
			exportedObs.append(ob)
			HandleMakeObjectMove (ob)
			return True
	HandleMakeObjectMove (ob)
	return False

def GetBlenderData ():
	global datas, colors, userJS, initCode, pathsDatas, updateCode, exportedObs
	exportedObs = []
	userJS = ''
	datas = []
	colors = {}
	pathsDatas = []
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
		Build (context.world)
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
		row.prop(context.world, 'invalidHtml')
		if context.world.js13kb:
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

JS_SUFFIX = '''
i=0
d=JSON.parse(D)
c=JSON.parse(C)
for(v of d)
{
	l=v.length
	if(l>10)
	{
		a=[]
		for(e of p.split('\\n')[i])
			a.push(e.charCodeAt(0))
		$.draw_svg([v[0],v[1]],[v[2],v[3]],c[v[4]],v[5],c[v[6]],v[7],a,v[8],v[9],v[10],v[11],v[12],v[13],[v[14],v[15]],v[16],v[17],[v[18],v[19]],[v[20],v[21]],v[22],v[23],v[24],v[25],[v[26],v[27]],[v[28],v[29]],[v[30],v[31]],[v[32],v[33]],[v[34],v[35]],[v[36],v[37]],[v[38],v[39]],[v[40],v[41]],[v[42],v[43]],v[44],v[45],v[46],v[47],v[48],v[49])
		i++
	}
	else if(l>5)
		$.add_radial_gradient(v[0],[v[1],v[2]],v[3],v[4],c[v[5]],c[v[6]],c[v[7]],v[8],v[9])
	else if(l>2)
	{
		if(typeof(v[1]) === 'string')
			$.copy_node(v[0],v[1],[v[2],v[3]])
		else
			$.make_object_move(v[0],[v[1],v[2]],v[3])
	}
	else
		$.add_group(v[0],v[1])
}
$.main()
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
	return rotate(from, clamp(signed_ang(from, to), -maxAng, maxAng) / (180 / Math.PI));
}
function get_pos_and_size (elmt)
{
	return [[parseInt(elmt.getAttribute('x')), parseInt(elmt.getAttribute('y'))], [parseInt(elmt.getAttribute('width')), parseInt(elmt.getAttribute('height'))]]
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
JS_API = '''
class api
{
	get_svg_path (pathValues, cyclic)
	{
		var path = 'M ' + pathValues[0] + ',' + pathValues[1] + ' ';
		for (var i = 2; i < pathValues.length; i += 2)
		{
			if ((i - 2) % 6 == 0)
				path += 'C ';
			path += '' + pathValues[i] + ',' + pathValues[i + 1] + ' '
		}
		if (cyclic)
			path += 'Z';
		return path
	}
	make_object_move (id, move, duration)
	{
		var ob = document.getElementById(id);
		ob.setAttribute('movex', move[0]);
		ob.setAttribute('movey', move[1]);
		ob.setAttribute('duration', duration);
	}
	copy_node (id, newId, pos)
	{
		var copy = document.getElementById(id).cloneNode(true);
		copy.id = newId;
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
	add_radial_gradient (id, pos, zIdx, diameter, color, color2, color3, colorPositions, subtractive)
	{
		var group = document.createElement('g');
		group.id = id;
		group.setAttribute('x', pos[0]);
		group.setAttribute('y', pos[1]);
		var mixMode = 'lighter';
		if (subtractive)
			mixMode = 'darker';
		group.style = 'position:absolute;background-image:radial-gradient(rgba(' + color[0] + ',' + color[1] + ',' + color[2] + ',' + color[3] + ') ' + colorPositions[0] + '%, rgba(' + color2[0] + ',' + color2[1] + ',' + color2[2] + ',' + color2[3] + ') ' + colorPositions[1] + '%, rgba(' + color3[0] + ',' + color3[1] + ',' + color3[2] + ',' + color3[3] + ') ' + colorPositions[2] + '%);width:' + diameter + 'px;height:' + diameter + 'px;z-index:' + zIdx + ';mix-blend-mode:plus-' + mixMode;
		document.body.appendChild(group);
	}
	draw_svg (pos, size, fillColor, lineWidth, lineColor, id, pathValues, cyclic, zIdx, collide, jiggleDist, jiggleDur, jiggleFrames, rotAngRange, rotDur, rotPingPong, scaleXRange, scaleYRange, scaleDur, scaleHaltDurAtMin, scaleHaltDurAtMax, scalePingPong, origin, fillHatchDensity, fillHatchRandDensity, fillHatchAng, fillHatchWidth, lineHatchDensity, lineHatchRandDensity, lineHatchAng, lineHatchWidth, mirrorX, mirrorY, capType, joinType, dashArr, cycleDur)
	{
		var fillColorTxt = 'rgb(' + fillColor[0] + ' ' + fillColor[1] + ' ' + fillColor[2] + ')';
		var lineColorTxt = 'rgb(' + lineColor[0] + ' ' + lineColor[1] + ' ' + lineColor[2] + ')';
		var svg = document.createElement('svg');
		svg.setAttribute('fill-opacity', fillColor[3] / 255);
		svg.id = id;
		svg.style = 'z-index:' + zIdx + ';position:absolute';
		svg.setAttribute('transform-origin', origin[0] + '% ' + origin[1] + '%');
		svg.setAttribute('collide', collide);
		svg.setAttribute('x', pos[0]);
		svg.setAttribute('y', pos[1]);
		svg.setAttribute('width', size[0]);
		svg.setAttribute('height', size[1]);
		var trs = 'translate(' + pos[0] + ',' + pos[1] + ')';
		svg.setAttribute('transform', trs);
		var path_ = document.createElement('path');
		path_.id = id + ' ';
		path_.style = 'fill:' + fillColorTxt + ';stroke-width:' + lineWidth + ';stroke:' + lineColorTxt;
		path_.setAttribute('d', $.get_svg_path(pathValues, cyclic));
		svg.appendChild(path_);
		document.body.innerHTML += svg.outerHTML;
		var off = lineWidth / 2 + jiggleDist;
		var min = 32 - off;
		svg.setAttribute('viewbox', min + ' ' + min + ' ' + (size[0] + off * 2) + ' ' + (size[1] + off * 2));
		svg = document.getElementById(id);
		path_ = document.getElementById(id + ' ');
		var svgRect = svg.getBoundingClientRect();
		var pathRect = path_.getBoundingClientRect();
		path_.setAttribute('transform', 'translate(' + (svgRect.x - pathRect.x + off) + ' ' + (svgRect.y - pathRect.y + off) + ')');
		var pathAnims = [];
		if (jiggleFrames > 0)
		{
			var anim = document.createElement('animate');
			anim.setAttribute('attributename', 'd');
			anim.setAttribute('repeatcount', 'indefinite');
			anim.setAttribute('dur', jiggleDur + 's');
			var frames = '';
			var firstFrame = '';
			for (var i = 0; i < jiggleFrames; i ++)
			{
				var pathValues_ = pathValues.slice();
				for (var i2 = 0; i2 < pathValues.length; i2 += 2)
				{
					off = normalize(random_vector(1));
					off = [off[0] * jiggleDist, off[1] * jiggleDist];
					pathValues_[i2] += off[0];
					pathValues_[i2 + 1] += off[1];
				}
				var frame = $.get_svg_path(pathValues_, cyclic);
				if (i == 0)
				{
					firstFrame = frame;
					anim.setAttribute('from', frame);
					anim.setAttribute('to', frame);
				}
				frames += frame + ';';
			}
			anim.setAttribute('values', frames + firstFrame);
			path_.appendChild(anim);
		}
		if (rotDur > 0)
		{
			var anim = document.createElement('animatetransform');
			anim.setAttribute('attributename', 'transform');
			anim.setAttribute('type', 'rotate');
			anim.setAttribute('repeatcount', 'indefinite');
			anim.setAttribute('dur', rotDur + 's');
			var firstFrame = rotAngRange[0];
			anim.setAttribute('from', firstFrame);
			var frames = firstFrame + ';' + rotAngRange[1];
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
			var anim = document.createElement('animatetransform');
			anim.setAttribute('attributename', 'transform');
			anim.setAttribute('repeatcount', 'indefinite');
			if (scalePingPong)
				totalScaleDur += scaleDur;
			anim.setAttribute('dur', totalScaleDur + 's');
			var firstFrame = scaleXRange[0] + ' ' + scaleYRange[0];
			anim.setAttribute('from', firstFrame);
			var thirdFrame = scaleXRange[1] + ' ' + scaleYRange[1];
			var frames = firstFrame + ';' + firstFrame + ';' + thirdFrame + ';' + thirdFrame;
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
			var anim = document.createElement('animate');
			anim.setAttribute('attributename', 'stroke-dashoffset');
			anim.setAttribute('repeatcount', 'indefinite');
			var pathLen = path_.getTotalLength();
			anim.setAttribute('dur', cycleDur + 's');
			anim.setAttribute('from', 0);
			anim.setAttribute('to', pathLen);
			anim.setAttribute('values', '0;' + pathLen);
			path_.appendChild(anim);
		}
		document.getElementById(id + ' ').remove();
		svg.appendChild(path_);
		var capTypes = ['butt', 'round', 'square'];
		svg.setAttribute('stroke-linecap', capTypes[capType]);
		var joinTypes = ['arcs', 'bevel', 'miter', 'miter-clip', 'round'];
		svg.setAttribute('stroke-linejoin', joinTypes[joinType]);
		svg.setAttribute('stroke-dasharray', dashArr);
		if (magnitude(fillHatchDensity) > 0)
		{
			var args = [fillColor, true, svg, path_]; 
			if (fillHatchDensity[0] > 0)
				$.hatch ('_' + id, ...args, fillHatchDensity[0], fillHatchRandDensity[0], fillHatchAng[0], fillHatchWidth[0]);
			if (fillHatchDensity[1] > 0)
				$.hatch ('|' + id, ...args, fillHatchDensity[1], fillHatchRandDensity[1], fillHatchAng[1], fillHatchWidth[1]);
			lineColor[3] = 255;
		}
		if (magnitude(lineHatchDensity) > 0)
		{
			var args = [lineColor, false, svg, path_]; 
			if (lineHatchDensity[0] > 0)
				$.hatch ('@' + id, ...args, lineHatchDensity[0], lineHatchRandDensity[0], lineHatchAng[0], lineHatchWidth[0]);
			if (lineHatchDensity[1] > 0)
				$.hatch ('$' + id, ...args, lineHatchDensity[1], lineHatchRandDensity[1], lineHatchAng[1], lineHatchWidth[1]);
			lineColor[3] = 255;
		}
		svg.setAttribute('stroke-opacity', lineColor[3] / 255);
		if (mirrorX)
		{
			svg = $.copy_node(id, '~' + id, pos);
			svg.setAttribute('transform', trs + ',scale(-1 1)');
			svg.setAttribute('transform-origin', 50 - (origin[0] - 50) + '% ' + origin[1] + '%');
		}
		if (mirrorY)
		{
			svg = $.copy_node(id, '`' + id, pos);
			svg.setAttribute('transform', trs + ',scale(1 -1)');
			svg.setAttribute('transform-origin', origin[0] + '% ' + (50 - (origin[1] - 50)) + '%');
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
		var path_ = path.cloneNode();
		var pathTxt = '';
		var x = 0;
		var interval = 15 / density * luminance;
		for (var i = 0; i < 99; i ++)
		{
			var off = random(-interval * randDensity, interval * randDensity);
			pathTxt += 'M ' + (x + off) + ' 0 L ' + (x + off) + ' ' + 999 + ' ';
			x += interval;
		}
		path_.setAttribute('d', pathTxt);
		path_.style = 'stroke-width:' + (width * (1 - luminance)) + ';stroke:black';
		pattern.appendChild(path_);
		svg.appendChild(pattern);
		path_ = path.cloneNode(true);
		if (useFIll)
			path_.style.fill = 'url(#' + id + ')';
		else
			path_.style.stroke = 'url(#' + id + ')';
		svg.innerHTML += path_.outerHTML;
	}
	main ()
	{
		// Init
		const f = ts => {
			$.dt = (ts - $.prev) / 1000;
			$.prev = ts;
			window.requestAnimationFrame(f);
			// Update
		};
		window.requestAnimationFrame(ts => {
			$.prev = ts;
			window.requestAnimationFrame(f)
		});
	}
}
$ = new api
'''

def GenJsAPI (world):
	global datas, userJS, colors
	js = [JS, JS_API, userJS]
	js = '\n'.join(js)
	js = js.replace('// Init', '\n'.join(initCode))
	js = js.replace('// Update', '\n'.join(updateCode))
	datas = json.dumps(datas).replace(' ', '')
	colors = json.dumps(colors).replace(' ', '')
	if world.minify:
		jsTmp = '/tmp/js13kjam API.js'
		js += 'D=`' + datas + '`\np=`' + '\n'.join(pathsDatas) + '`;\nC=`' + colors + '`\n' + JS_SUFFIX
		open(jsTmp, 'w').write(js)
		subprocess.run(['python', 'tinifyjs/Main.py', '-i=' + jsTmp, '-o=' + jsTmp, '-d'])
		js = open(jsTmp, 'r').read()
	else:
		js += '\nD=`' + datas + '`;\np=`' + '\n'.join(pathsDatas) + '`;\nC=`' + colors + '`\n' + JS_SUFFIX.replace('\t', '')
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
		'<script>',
		js,
		'</script>',
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

def Build (world):
	global SERVER_PROC
	if SERVER_PROC:
		SERVER_PROC.kill()
	for ob in bpy.data.objects:
		if '_Clone' in ob.name:
			for child in ob.children:
				bpy.data.objects.remove(child, do_unlink = True)
			bpy.data.objects.remove(ob, do_unlink = True)
	blenderInfo = GetBlenderData()
	datas = blenderInfo[0]
	html = GenHtml(world, datas)
	open('/tmp/index.html', 'w').write(html)
	if world.js13kb:
		if os.path.isfile('/usr/bin/zip'):
			cmd = ['zip', '-9', 'index.html.zip', 'index.html']
			print(cmd)
			subprocess.check_call(cmd, cwd='/tmp')

			zip = open('/tmp/index.html.zip','rb').read()
			buildInfo['zip-size'] = len(zip)
			if world.exportZip:
				out = os.path.expanduser(world.exportZip)
				if not out.endswith('.zip'):
					out += '.zip'
				buildInfo['zip'] = out
				print('Saving:', out)
				open(out, 'wb').write(zip)
			else:
				buildInfo['zip'] = '/tmp/index.html.zip'
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
		SERVER_PROC = subprocess.Popen(cmd, cwd = '/tmp')

		atexit.register(lambda: SERVER_PROC.kill())
		webbrowser.open('http://localhost:6969')

	if os.path.isfile('SlimeJump.py'):
		import SlimeJump as slimeJump
		slimeJump.GenLevel ()
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

CAP_TYPES = ['butt', 'round', 'square']
CAP_TYPE_ITEMS = [('butt', 'butt', ''), ('round', 'round', ''), ('square', 'square', '')]
JOIN_TYPES = ['arcs', 'bevl', 'miter', 'miter-clip', 'round']
JOIN_TYPE_ITEMS = [('arcs', 'arcs', ''), ('bevel', 'bevel', ''), ('miter', 'miter', ''), ('miter-clip', 'miter-clip', ''), ('round', 'round', '')]

bpy.types.World.exportScale = bpy.props.FloatProperty(name = 'Scale', default = 1)
bpy.types.World.exportOffsetX = bpy.props.IntProperty(name = 'Offset X')
bpy.types.World.exportOffsetY = bpy.props.IntProperty(name = 'Offset Y')
bpy.types.World.exportHtml = bpy.props.StringProperty(name = 'Export .html')
bpy.types.World.exportZip = bpy.props.StringProperty(name = 'Export .zip')
bpy.types.World.minify = bpy.props.BoolProperty(name = 'Minifiy')
bpy.types.World.js13kb = bpy.props.BoolProperty(name = 'js13k: Error on export if output is over 13kb')
bpy.types.World.invalidHtml = bpy.props.BoolProperty(name = 'Save space with invalid html wrapper')
bpy.types.Object.roundPosAndSize = bpy.props.BoolProperty(name = 'Round position and size', default = True)
bpy.types.Object.origin = bpy.props.FloatVectorProperty(name = 'Origin', size = 2, default = [50, 50])
bpy.types.Object.collide = bpy.props.BoolProperty(name = 'Collide')
bpy.types.Object.useSvgStroke = bpy.props.BoolProperty(name = 'Use svg stroke')
bpy.types.Object.svgStrokeWidth = bpy.props.FloatProperty(name = 'Svg stroke width')
bpy.types.Object.svgStrokeColor = bpy.props.FloatVectorProperty(name = 'Svg stroke color', subtype = 'COLOR', size = 4, default = [0, 0, 0, 0])
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
bpy.types.Object.moveSpeed = bpy.props.FloatProperty(name = 'Move speed')
bpy.types.Object.waypoint1 = bpy.props.PointerProperty(name = 'Waypoint 1', type = bpy.types.Object)
bpy.types.Object.waypoint2 = bpy.props.PointerProperty(name = 'Waypoint 2', type = bpy.types.Object)
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
		if ob.type == 'CURVE':
			self.layout.prop(ob, 'roundPosAndSize')
			self.layout.prop(ob, 'origin')
			self.layout.prop(ob, 'collide')
			self.layout.prop(ob, 'useSvgStroke')
			self.layout.prop(ob, 'svgStrokeWidth')
			self.layout.prop(ob, 'svgStrokeColor')
			self.layout.prop(ob, 'capType')
			self.layout.prop(ob, 'joinType')
			self.layout.prop(ob, 'dashLengthsAndSpaces')
			self.layout.prop(ob, 'useFillHatch')
			self.layout.prop(ob, 'fillHatchDensity')
			self.layout.prop(ob, 'fillHatchRandDensity')
			self.layout.prop(ob, 'fillHatchAng')
			self.layout.prop(ob, 'fillHatchWidth')
			self.layout.prop(ob, 'useStrokeHatch')
			self.layout.prop(ob, 'strokeHatchDensity')
			self.layout.prop(ob, 'strokeHatchRandDensity')
			self.layout.prop(ob, 'strokeHatchAng')
			self.layout.prop(ob, 'strokeHatchWidth')
			self.layout.prop(ob, 'mirrorX')
			self.layout.prop(ob, 'mirrorY')
			self.layout.label(text = 'Animation')
			self.layout.label(text = 'Jiggle')
			self.layout.prop(ob, 'useJiggle')
			self.layout.prop(ob, 'jiggleDist')
			self.layout.prop(ob, 'jiggleDur')
			self.layout.prop(ob, 'jiggleFrames')
			self.layout.label(text = 'Rotate')
			self.layout.prop(ob, 'useRotate')
			self.layout.prop(ob, 'rotPingPong')
			self.layout.prop(ob, 'rotAngRange')
			self.layout.prop(ob, 'rotDur')
			self.layout.label(text = 'Scale')
			self.layout.prop(ob, 'useScale')
			self.layout.prop(ob, 'scalePingPong')
			self.layout.prop(ob, 'scaleXRange')
			self.layout.prop(ob, 'scaleYRange')
			self.layout.prop(ob, 'scaleDur')
			self.layout.prop(ob, 'scaleHaltDurAtMin')
			self.layout.prop(ob, 'scaleHaltDurAtMax')
			self.layout.label(text = 'Cycle')
			self.layout.prop(ob, 'cycleDur')
		self.layout.label(text = 'Movement')
		self.layout.prop(ob, 'moveSpeed')
		self.layout.prop(ob, 'waypoint1')
		self.layout.prop(ob, 'waypoint2')
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
			bpy.data.worlds[0].exportHtml = arg.split('=')[-1]
		elif arg == '--minifiy':
			bpy.data.worlds[0].minify = True
		elif arg == '--js13k':
			bpy.data.worlds[0].minify = True
			bpy.data.worlds[0].js13kb = True
			bpy.data.worlds[0].invalidHtml = True
	bpy.app.timers.register(Update)
	if '--build' in sys.argv:
		Build (bpy.data.worlds[0])