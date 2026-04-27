import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


class GbcTranspileError(Exception):
	def __init__(self, message: str, line: Optional[int] = None):
		super().__init__(message)
		self.message = str(message)
		self.line = int(line) if isinstance(line, int) else None


@dataclass(frozen = True)
class CompilerSemanticsSpec:
	version: str = 'v1'
	numeric_width_bits: int = 8
	signed_wraparound: bool = True
	truthy_zero_is_false: bool = True
	strict_compiler_mode_default: bool = True
	notes: Tuple[str, ...] = (
		'Frontend accepts Python AST and lowers into a restricted IR.',
		'Name-bound values map to deterministic WRAM-like slots.',
		'Control flow lowers to direct branch labels in generated GBZ80.',
		'Unsupported syntax raises compile errors in strict mode.',
	)


COMPILER_SEMANTICS_SPEC = CompilerSemanticsSpec()


@dataclass
class IrExpr:
	pass


@dataclass
class IrConst(IrExpr):
	value: object


@dataclass
class IrName(IrExpr):
	name: str


@dataclass
class IrAttr(IrExpr):
	base: IrExpr
	attr: str


@dataclass
class IrSubscript(IrExpr):
	base: IrExpr
	index: IrExpr


@dataclass
class IrList(IrExpr):
	items: List[IrExpr] = field(default_factory = list)


@dataclass
class IrCall(IrExpr):
	func: IrExpr
	args: List[IrExpr] = field(default_factory = list)


@dataclass
class IrUnary(IrExpr):
	op: str
	value: IrExpr


@dataclass
class IrCompare(IrExpr):
	left: IrExpr
	op: str
	right: IrExpr


@dataclass
class IrBoolAnd(IrExpr):
	parts: List[IrExpr] = field(default_factory = list)


@dataclass
class IrBoolOr(IrExpr):
	parts: List[IrExpr] = field(default_factory = list)


@dataclass
class IrBinOp(IrExpr):
	left: IrExpr
	op: str
	right: IrExpr


@dataclass
class IrStmt:
	line: int = 0


@dataclass
class IrAssign(IrStmt):
	target: IrExpr = None
	value: IrExpr = None


@dataclass
class IrAugAssign(IrStmt):
	target: IrExpr = None
	op: str = '+'
	value: IrExpr = None


@dataclass
class IrExprStmt(IrStmt):
	value: IrExpr = None


@dataclass
class IrIf(IrStmt):
	test: IrExpr = None
	body: List[IrStmt] = field(default_factory = list)
	orelse: List[IrStmt] = field(default_factory = list)


@dataclass
class IrBasicBlock:
	name: str
	stmts: List[IrStmt] = field(default_factory = list)
	next_blocks: List[str] = field(default_factory = list)


@dataclass
class IrProgram:
	script_name: str
	entry_block: str
	blocks: Dict[str, IrBasicBlock]


class Gbz80Emitter:
	def __init__ (self, base_addr: int = 0x150):
		self.base_addr = int(base_addr)
		self.code = bytearray()
		self.labels: Dict[str, int] = {}
		self.jr_fixups: List[Tuple[int, str]] = []
		self.abs_fixups: List[Tuple[int, str]] = []
		self.asm_lines: List[str] = []

	def mark (self, label: str):
		self.labels[str(label)] = len(self.code)
		self.asm_lines.append(str(label) + ':')

	def emit (self, *bytes_: int):
		for b in bytes_:
			self.code.append(int(b) & 0xFF)

	def ld_a_imm (self, v: int):
		self.emit(0x3E, int(v) & 0xFF)
		self.asm_lines.append('  ld a, $%02x' % (int(v) & 0xFF))

	def ld_hl_imm (self, v: int):
		iv = int(v) & 0xFFFF
		self.emit(0x21, iv & 0xFF, (iv >> 8) & 0xFF)
		self.asm_lines.append('  ld hl, $%04x' % iv)

	def ld_hl_a (self):
		self.emit(0x77)
		self.asm_lines.append('  ld [hl], a')

	def ld_a_hl (self):
		self.emit(0x7E)
		self.asm_lines.append('  ld a, [hl]')

	def add_a_imm (self, v: int):
		self.emit(0xC6, int(v) & 0xFF)
		self.asm_lines.append('  add a, $%02x' % (int(v) & 0xFF))

	def sub_a_imm (self, v: int):
		self.emit(0xD6, int(v) & 0xFF)
		self.asm_lines.append('  sub a, $%02x' % (int(v) & 0xFF))

	def cp_a_imm (self, v: int):
		self.emit(0xFE, int(v) & 0xFF)
		self.asm_lines.append('  cp a, $%02x' % (int(v) & 0xFF))

	def and_a (self):
		self.emit(0xA7)
		self.asm_lines.append('  and a')

	def xor_a_imm (self, v: int):
		self.emit(0xEE, int(v) & 0xFF)
		self.asm_lines.append('  xor a, $%02x' % (int(v) & 0xFF))

	def jr (self, label: str):
		pos = len(self.code)
		self.emit(0x18, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr ' + str(label))

	def jr_z (self, label: str):
		pos = len(self.code)
		self.emit(0x28, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr z, ' + str(label))

	def jr_nz (self, label: str):
		pos = len(self.code)
		self.emit(0x20, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr nz, ' + str(label))

	def jp (self, label: str):
		pos = len(self.code)
		self.emit(0xC3, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp ' + str(label))

	def resolve (self):
		for at, label in self.jr_fixups:
			if label not in self.labels:
				raise RuntimeError('Unknown JR label: ' + str(label))
			target = self.labels[label]
			disp = int(target - (at + 1))
			if disp < -128 or disp > 127:
				raise RuntimeError('JR out of range for label: ' + str(label))
			self.code[at] = disp & 0xFF
		for at, label in self.abs_fixups:
			if label not in self.labels:
				raise RuntimeError('Unknown JP label: ' + str(label))
			abs_addr = self.base_addr + int(self.labels[label])
			self.code[at] = abs_addr & 0xFF
			self.code[at + 1] = (abs_addr >> 8) & 0xFF


def _unsupported_error (node, what: str, strict_compiler_mode: bool):
	if strict_compiler_mode:
		raise GbcTranspileError(
			'Unsupported syntax in strict compiler mode: ' + str(what),
			getattr(node, 'lineno', None),
		)


def _to_ir_expr (node, strict_compiler_mode: bool = False) -> IrExpr:
	if isinstance(node, ast.Constant):
		return IrConst(node.value)
	if isinstance(node, ast.Name):
		return IrName(node.id)
	if isinstance(node, ast.Attribute):
		return IrAttr(_to_ir_expr(node.value, strict_compiler_mode = strict_compiler_mode), node.attr)
	if isinstance(node, ast.Subscript):
		idx = node.slice
		if hasattr(ast, 'Index') and isinstance(idx, ast.Index):
			idx = idx.value
		return IrSubscript(
			_to_ir_expr(node.value, strict_compiler_mode = strict_compiler_mode),
			_to_ir_expr(idx, strict_compiler_mode = strict_compiler_mode),
		)
	if isinstance(node, ast.List):
		return IrList([_to_ir_expr(x, strict_compiler_mode = strict_compiler_mode) for x in list(node.elts or [])])
	if isinstance(node, ast.Tuple):
		return IrList([_to_ir_expr(x, strict_compiler_mode = strict_compiler_mode) for x in list(node.elts or [])])
	if isinstance(node, ast.Call):
		return IrCall(
			_to_ir_expr(node.func, strict_compiler_mode = strict_compiler_mode),
			[_to_ir_expr(a, strict_compiler_mode = strict_compiler_mode) for a in list(node.args or [])],
		)
	if isinstance(node, ast.UnaryOp):
		if isinstance(node.op, ast.USub):
			return IrUnary('-', _to_ir_expr(node.operand, strict_compiler_mode = strict_compiler_mode))
		if isinstance(node.op, ast.UAdd):
			return IrUnary('+', _to_ir_expr(node.operand, strict_compiler_mode = strict_compiler_mode))
		if isinstance(node.op, ast.Not):
			return IrUnary('not', _to_ir_expr(node.operand, strict_compiler_mode = strict_compiler_mode))
	if isinstance(node, ast.BinOp):
		op_name = None
		if isinstance(node.op, ast.Add):
			op_name = '+'
		elif isinstance(node.op, ast.Sub):
			op_name = '-'
		elif isinstance(node.op, ast.Mult):
			op_name = '*'
		elif isinstance(node.op, ast.FloorDiv):
			op_name = '//'
		elif isinstance(node.op, ast.Mod):
			op_name = '%'
		if op_name is not None:
			return IrBinOp(
				_to_ir_expr(node.left, strict_compiler_mode = strict_compiler_mode),
				op_name,
				_to_ir_expr(node.right, strict_compiler_mode = strict_compiler_mode),
			)
		_unsupported_error(node, type(node.op).__name__, strict_compiler_mode)
		return IrConst(None)
	if isinstance(node, ast.Compare) and len(list(node.ops or [])) >= 1 and len(list(node.comparators or [])) >= 1:
		left = node.left
		parts = []
		for op, right in zip(list(node.ops), list(node.comparators)):
			op_name = '=='
			if isinstance(op, ast.Lt):
				op_name = '<'
			elif isinstance(op, ast.LtE):
				op_name = '<='
			elif isinstance(op, ast.Gt):
				op_name = '>'
			elif isinstance(op, ast.GtE):
				op_name = '>='
			elif isinstance(op, ast.NotEq):
				op_name = '!='
			elif not isinstance(op, ast.Eq):
				_unsupported_error(node, type(op).__name__, strict_compiler_mode)
				return IrConst(None)
			parts.append(
				IrCompare(
					_to_ir_expr(left, strict_compiler_mode = strict_compiler_mode),
					op_name,
					_to_ir_expr(right, strict_compiler_mode = strict_compiler_mode),
				),
			)
			left = right
		return parts[0] if len(parts) == 1 else IrBoolAnd(parts = parts)
	if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
		return IrBoolAnd([_to_ir_expr(v, strict_compiler_mode = strict_compiler_mode) for v in list(node.values or [])])
	if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
		return IrBoolOr([_to_ir_expr(v, strict_compiler_mode = strict_compiler_mode) for v in list(node.values or [])])
	_unsupported_error(node, type(node).__name__, strict_compiler_mode)
	return IrConst(None)


def _to_ir_stmt (stmt, strict_compiler_mode: bool = False) -> Optional[IrStmt]:
	line = int(getattr(stmt, 'lineno', 0) or 0)
	if isinstance(stmt, ast.Assign) and len(list(stmt.targets or [])) == 1:
		return IrAssign(
			line = line,
			target = _to_ir_expr(stmt.targets[0], strict_compiler_mode = strict_compiler_mode),
			value = _to_ir_expr(stmt.value, strict_compiler_mode = strict_compiler_mode),
		)
	if isinstance(stmt, ast.AugAssign):
		op = '+'
		if isinstance(stmt.op, ast.Sub):
			op = '-'
		elif isinstance(stmt.op, ast.Add):
			op = '+'
		else:
			_unsupported_error(stmt, type(stmt.op).__name__, strict_compiler_mode)
		return IrAugAssign(
			line = line,
			target = _to_ir_expr(stmt.target, strict_compiler_mode = strict_compiler_mode),
			op = op,
			value = _to_ir_expr(stmt.value, strict_compiler_mode = strict_compiler_mode),
		)
	if isinstance(stmt, ast.Expr):
		return IrExprStmt(line = line, value = _to_ir_expr(stmt.value, strict_compiler_mode = strict_compiler_mode))
	if isinstance(stmt, ast.If):
		return IrIf(
			line = line,
			test = _to_ir_expr(stmt.test, strict_compiler_mode = strict_compiler_mode),
			body = [s for s in [_to_ir_stmt(x, strict_compiler_mode = strict_compiler_mode) for x in list(stmt.body or [])] if s is not None],
			orelse = [s for s in [_to_ir_stmt(x, strict_compiler_mode = strict_compiler_mode) for x in list(stmt.orelse or [])] if s is not None],
		)
	_unsupported_error(stmt, type(stmt).__name__, strict_compiler_mode)
	return None


def _check_unsupported_nodes (tree, strict_compiler_mode: bool = False):
	for node in ast.walk(tree):
		if isinstance(node, (ast.Import, ast.ImportFrom)):
			raise GbcTranspileError('Imports are not supported in gbc transpiler', getattr(node, 'lineno', None))
		if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
			raise GbcTranspileError('Async and generators are not supported in gbc transpiler', getattr(node, 'lineno', None))
		if isinstance(node, ast.Try):
			raise GbcTranspileError('try/except/finally is not supported in gbc transpiler', getattr(node, 'lineno', None))
		if isinstance(node, ast.Call):
			if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', '__import__'):
				raise GbcTranspileError('Dynamic eval/exec/import is not supported in gbc transpiler', getattr(node, 'lineno', None))
		if strict_compiler_mode:
			if isinstance(node, ast.Call) and len(list(getattr(node, 'keywords', []) or [])) > 0:
				raise GbcTranspileError('Keyword call arguments are not supported in strict compiler mode', getattr(node, 'lineno', None))
			if isinstance(node, (ast.Lambda, ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
				raise GbcTranspileError('Comprehensions/lambdas are not supported in strict compiler mode', getattr(node, 'lineno', None))
			if isinstance(node, ast.With):
				raise GbcTranspileError('with is not supported in strict compiler mode', getattr(node, 'lineno', None))
			if isinstance(node, ast.Delete):
				raise GbcTranspileError('del is not supported in strict compiler mode', getattr(node, 'lineno', None))


def build_ir_program (code: str, script_name: str = '<script>', strict_compiler_mode: bool = False) -> IrProgram:
	tree = ast.parse(code or '')
	_check_unsupported_nodes(tree, strict_compiler_mode = strict_compiler_mode)
	entry = IrBasicBlock(name = 'entry')
	for stmt in list(tree.body or []):
		ir_stmt = _to_ir_stmt(stmt, strict_compiler_mode = strict_compiler_mode)
		if ir_stmt is not None:
			entry.stmts.append(ir_stmt)
	return IrProgram(script_name = str(script_name), entry_block = 'entry', blocks = {'entry': entry})


def _small_int (expr: IrExpr, consts: Dict[str, int]) -> Optional[int]:
	if isinstance(expr, IrConst):
		try:
			return int(round(float(expr.value)))
		except Exception:
			return None
	if isinstance(expr, IrName):
		return consts.get(expr.name)
	if isinstance(expr, IrAttr) and isinstance(expr.base, IrName):
		if expr.base.name == 'this':
			return consts.get('this.' + str(expr.attr))
		return consts.get(str(expr.base.name) + '.' + str(expr.attr))
	if isinstance(expr, IrUnary) and expr.op in ('+', '-'):
		v = _small_int(expr.value, consts)
		if not isinstance(v, int):
			return None
		return v if expr.op == '+' else -v
	if isinstance(expr, IrBinOp):
		lv = _small_int(expr.left, consts)
		rv = _small_int(expr.right, consts)
		if not (isinstance(lv, int) and isinstance(rv, int)):
			return None
		try:
			if expr.op == '+':
				return int(lv + rv)
			if expr.op == '-':
				return int(lv - rv)
			if expr.op == '*':
				return int(lv * rv)
			if expr.op == '//':
				return int(lv // rv) if rv != 0 else None
			if expr.op == '%':
				return int(lv % rv) if rv != 0 else None
		except Exception:
			return None
	return None


def _subscript_const_index (expr: IrExpr) -> Optional[int]:
	if not isinstance(expr, IrSubscript):
		return None
	return _small_int(expr.index, {})


def _subscript_key_name (expr: IrExpr) -> Optional[str]:
	if not isinstance(expr, IrSubscript):
		return None
	idx = expr.index
	if isinstance(idx, IrAttr) and isinstance(idx.base, IrName) and idx.base.name == 'pygame':
		return idx.attr
	return None


def _is_name (expr: IrExpr, name: str) -> bool:
	return isinstance(expr, IrName) and expr.name == str(name)


def _extract_rigidbody_ref (expr: IrExpr):
	if isinstance(expr, IrName):
		return ('name_ref', expr.name)
	if isinstance(expr, IrAttr) and isinstance(expr.base, IrName) and expr.base.name == 'this' and expr.attr == 'rb':
		return ('this_id', None)
	if isinstance(expr, IrCall) and isinstance(expr.func, IrName) and expr.func.name == 'get_rigidbody' and len(expr.args) >= 1:
		arg0 = expr.args[0]
		if isinstance(arg0, IrConst) and isinstance(arg0.value, str):
			return ('key', arg0.value)
		if isinstance(arg0, IrAttr) and isinstance(arg0.base, IrName) and arg0.base.name == 'this' and arg0.attr == 'id':
			return ('this_id', None)
	if isinstance(expr, IrSubscript) and isinstance(expr.base, IrName) and expr.base.name in ('rigidBodies', 'rigidBodiesIds'):
		if isinstance(expr.index, IrConst) and isinstance(expr.index.value, str):
			return ('key', expr.index.value)
	return (None, None)


def _vec2_literal (expr: IrExpr, consts: Dict[str, int]):
	if isinstance(expr, IrConst) and isinstance(expr.value, (tuple, list)) and len(expr.value) >= 2:
		try:
			return [float(expr.value[0]), float(expr.value[1])]
		except Exception:
			return None
	if isinstance(expr, IrList) and len(expr.items) >= 2:
		x = _small_int(expr.items[0], consts)
		y = _small_int(expr.items[1], consts)
		if isinstance(x, int) and isinstance(y, int):
			return [float(x), float(y)]
	return None


@dataclass
class VelocityCompileResult:
	velocity_script: Optional[Dict[str, int]]
	init_velocity: Optional[Tuple[int, int]]
	ir: IrProgram
	asm_bytes: bytes
	asm_listing: List[str]
	symbol_map: Dict[str, int] = field(default_factory = dict)
	diagnostics: List[str] = field(default_factory = list)


def _extract_jump_guard (test_expr: IrExpr, keys_aliases: set, vel_alias_name: Optional[str], consts: Dict[str, int]):
	parts = []
	if isinstance(test_expr, IrBoolAnd):
		parts = list(test_expr.parts)
	else:
		parts = [test_expr]
	key_name = None
	jump_vy_max = None
	for part in parts:
		part_key = _subscript_key_name(part)
		if part_key is not None:
			if isinstance(part, IrSubscript) and isinstance(part.base, IrName) and part.base.name in keys_aliases:
				key_name = part_key
				continue
			return (None, None)
		if isinstance(part, IrCompare):
			lhs = part.left
			rhs = part.right
			lhs_idx = _subscript_const_index(lhs)
			rhs_idx = _subscript_const_index(rhs)
			lhs_is_vel_y = isinstance(lhs, IrSubscript) and isinstance(lhs.base, IrName) and lhs.base.name == vel_alias_name and lhs_idx == 1
			rhs_is_vel_y = isinstance(rhs, IrSubscript) and isinstance(rhs.base, IrName) and rhs.base.name == vel_alias_name and rhs_idx == 1
			if lhs_is_vel_y and part.op in ('<', '<='):
				c = _small_int(rhs, consts)
				if isinstance(c, int):
					upper = c - 1 if part.op == '<' else c
					jump_vy_max = upper if jump_vy_max is None else min(jump_vy_max, upper)
					continue
			if rhs_is_vel_y and part.op in ('>', '>='):
				c = _small_int(lhs, consts)
				if isinstance(c, int):
					upper = c - 1 if part.op == '>' else c
					jump_vy_max = upper if jump_vy_max is None else min(jump_vy_max, upper)
					continue
		return (None, None)
	return (key_name, jump_vy_max)


def _collect_jump_assignments (
	stmt: IrIf,
	vel_alias_name: Optional[str],
	consts: Dict[str, int],
	key_name: Optional[str],
	jump_y: Optional[int],
	jump_vy_max: Optional[int],
	jump_release_cut: bool,
	jump_edge_trigger: bool,
	saw_jump_assign: bool,
	unresolved_jump_assign: bool,
):
	def _is_vel_y_target (_target):
		if not isinstance(_target, IrSubscript):
			return False
		if not (isinstance(_target.base, IrName) and _target.base.name == vel_alias_name):
			return False
		idx = _subscript_const_index(_target)
		return bool(idx == 1)
	def _orelse_has_release_cut (_stmts):
		for _stmt in list(_stmts or []):
			if isinstance(_stmt, IrAssign):
				if _is_vel_y_target(_stmt.target):
					j = _small_int(_stmt.value, consts)
					if isinstance(j, int) and int(j) == 0:
						return True
			elif isinstance(_stmt, IrIf):
				if _orelse_has_release_cut(_stmt.body) or _orelse_has_release_cut(_stmt.orelse):
					return True
		return False
	def _is_edge_guard_not_expr (_expr):
		# Keep edge-trigger detection generic: any unary `not <state>` guard
		# inside the jump-pressed branch can indicate "press once until release".
		if not (isinstance(_expr, IrUnary) and _expr.op == 'not'):
			return False
		v = _expr.value
		return isinstance(v, (IrAttr, IrName))
	for inner in list(stmt.body):
		if isinstance(inner, IrAugAssign):
			continue
		if isinstance(inner, IrAssign):
			if not _is_vel_y_target(inner.target):
				continue
			if key_name == 'K_A':
				saw_jump_assign = True
			j = _small_int(inner.value, consts)
			if isinstance(j, int) and key_name == 'K_A':
				jump_y = j
			elif key_name == 'K_A':
				unresolved_jump_assign = True
		elif isinstance(inner, IrIf):
			# Support edge-trigger style:
			# if jumpInput:
			#   if not this.prevJumpInput: vel[1] = 60
			if _is_edge_guard_not_expr(inner.test):
				jump_edge_trigger = True
			for nested in list(inner.body):
				if not isinstance(nested, IrAssign):
					continue
				if not isinstance(nested.target, IrSubscript):
					continue
				if not (isinstance(nested.target.base, IrName) and nested.target.base.name == vel_alias_name):
					continue
				idx = _subscript_const_index(nested.target)
				if idx != 1:
					continue
				if key_name == 'K_A':
					saw_jump_assign = True
				j = _small_int(nested.value, consts)
				if isinstance(j, int) and key_name == 'K_A':
					jump_y = j
				elif key_name == 'K_A':
					unresolved_jump_assign = True
	if key_name == 'K_A' and _orelse_has_release_cut(stmt.orelse):
		jump_release_cut = True
	return (
		jump_y,
		jump_vy_max,
		jump_release_cut,
		jump_edge_trigger,
		saw_jump_assign,
		unresolved_jump_assign,
	)


def compile_velocity_script (
	code: str,
	target_keys: Sequence[str],
	allow_this_id: bool = False,
	script_name: str = '<script>',
	strict_compiler_mode: bool = False,
	symbol_constants: Optional[Dict[str, int]] = None,
) -> VelocityCompileResult:
	target_keys_set = set([str(k) for k in list(target_keys or []) if isinstance(k, str) and k != ''])
	ir = build_ir_program(code, script_name = script_name, strict_compiler_mode = bool(strict_compiler_mode))
	aliases: Dict[str, Tuple[str, Optional[str]]] = {}
	consts: Dict[str, int] = {}
	if isinstance(symbol_constants, dict):
		for k, v in symbol_constants.items():
			if not isinstance(k, str) or k == '':
				continue
			try:
				consts[k] = int(round(float(v)))
			except Exception:
				continue
	keys_aliases = set()
	key_bool_alias: Dict[str, str] = {}
	vel_alias_name = None
	vel_aliases: Dict[str, List[float]] = {}
	base_vx = 0
	base_vy = 0
	base_vx_found = False
	base_vy_found = False
	left_delta = 0
	right_delta = 0
	up_delta = 0
	down_delta = 0
	jump_y = None
	jump_vy_max = None
	jump_release_cut = False
	jump_edge_trigger = False
	saw_left_assign = False
	saw_right_assign = False
	saw_up_assign = False
	saw_down_assign = False
	unresolved_left_assign = False
	unresolved_right_assign = False
	unresolved_up_assign = False
	unresolved_down_assign = False
	saw_jump_assign = False
	unresolved_jump_assign = False
	target_hit = False
	init_velocity = None
	for stmt in list(ir.blocks[ir.entry_block].stmts):
		if isinstance(stmt, IrAssign):
			v = _small_int(stmt.value, consts)
			if isinstance(stmt.target, IrName):
				name = stmt.target.name
				if isinstance(v, int):
					consts[name] = v
				else:
					consts.pop(name, None)
				if isinstance(stmt.value, IrCall) and isinstance(stmt.value.func, IrAttr):
					f = stmt.value.func
					if isinstance(f.base, IrAttr) and isinstance(f.base.base, IrName) and f.base.base.name == 'pygame' and f.base.attr == 'key' and f.attr == 'get_pressed':
						keys_aliases.add(name)
				if isinstance(stmt.value, IrList) and len(stmt.value.items) >= 2:
					vel_alias_name = name
					vx_candidate = _small_int(stmt.value.items[0], consts)
					vy_candidate = _small_int(stmt.value.items[1], consts)
					if isinstance(vx_candidate, int):
						base_vx = int(vx_candidate)
						base_vx_found = True
					if isinstance(vy_candidate, int):
						base_vy = int(vy_candidate)
						base_vy_found = True
				rb_kind, rb_value = _extract_rigidbody_ref(stmt.value)
				if rb_kind in ('name_ref', 'key', 'this_id'):
					aliases[name] = (rb_kind, rb_value)
				else:
					aliases.pop(name, None)
				vec = _vec2_literal(stmt.value, consts)
				if vec is not None:
					vel_aliases[name] = [float(vec[0]), float(vec[1])]
				else:
					vel_aliases.pop(name, None)
				if isinstance(stmt.value, IrSubscript):
					k = _subscript_key_name(stmt.value)
					if k is not None and isinstance(stmt.value.base, IrName) and stmt.value.base.name in keys_aliases:
						key_bool_alias[name] = k
					else:
						key_bool_alias.pop(name, None)
			elif isinstance(stmt.target, IrAttr) and isinstance(stmt.target.base, IrName):
				attr_key = str(stmt.target.base.name) + '.' + str(stmt.target.attr)
				if isinstance(v, int):
					consts[attr_key] = v
				else:
					consts.pop(attr_key, None)
		elif isinstance(stmt, IrAugAssign):
			if isinstance(stmt.target, IrSubscript) and isinstance(stmt.target.base, IrName) and stmt.target.base.name == vel_alias_name:
				d = _small_int(stmt.value, consts)
				idx = _subscript_const_index(stmt.target)
				if isinstance(d, int) and isinstance(idx, int) and idx in (0, 1):
					if stmt.op == '-':
						d = -d
					# key deltas are inferred in enclosing if blocks; direct top-level
					# aug-assign on vel components is treated as baseline motion.
					if idx == 0:
						base_vx += d
						base_vx_found = True
					else:
						base_vy += d
						base_vy_found = True
		elif isinstance(stmt, IrExprStmt) and isinstance(stmt.value, IrCall):
			call = stmt.value
			if (
				isinstance(call.func, IrAttr)
				and call.func.attr in ('set_linear_velocity', 'set_rigid_body_velocity')
				and isinstance(call.func.base, IrName)
				and call.func.base.name in ('sim', 'physics')
			):
				if len(call.args) >= 2:
					rb_kind, rb_value = _extract_rigidbody_ref(call.args[0])
					if rb_kind == 'name_ref' and rb_value in aliases:
						rb_kind, rb_value = aliases[rb_value]
					target_match = False
					if rb_kind == 'this_id':
						target_match = bool(allow_this_id)
					elif rb_kind == 'key' and isinstance(rb_value, str) and rb_value in target_keys_set:
						target_match = True
					if target_match:
						target_hit = True
						if isinstance(call.args[1], IrName):
							vel_alias_name = call.args[1].name
						elif isinstance(call.args[1], IrList) and len(call.args[1].items) >= 2:
							vx_candidate = _small_int(call.args[1].items[0], consts)
							vy_candidate = _small_int(call.args[1].items[1], consts)
							if isinstance(vx_candidate, int) and isinstance(vy_candidate, int):
								base_vx = int(vx_candidate)
								base_vy = int(vy_candidate)
								base_vx_found = True
								base_vy_found = True
								init_velocity = (int(base_vx), int(-base_vy))
						if isinstance(call.args[1], IrName) and call.args[1].name in vel_aliases:
							init_velocity = (
								int(round(float(vel_aliases[call.args[1].name][0]))),
								int(round(-float(vel_aliases[call.args[1].name][1]))),
							)
		elif isinstance(stmt, IrIf):
			key_name, guard_max = _extract_jump_guard(stmt.test, keys_aliases, vel_alias_name, consts)
			if key_name is None and isinstance(stmt.test, IrName):
				key_name = key_bool_alias.get(stmt.test.name)
			if key_name is None:
				continue
			for inner in list(stmt.body):
				if isinstance(inner, IrAugAssign):
					if not (isinstance(inner.target, IrSubscript) and isinstance(inner.target.base, IrName) and inner.target.base.name == vel_alias_name):
						continue
					idx = _subscript_const_index(inner.target)
					d = _small_int(inner.value, consts)
					if not isinstance(idx, int):
						continue
					if isinstance(d, int) and inner.op == '-':
						d = -d
					if idx == 0:
						if key_name == 'K_LEFT':
							saw_left_assign = True
							if isinstance(d, int):
								left_delta += d
							else:
								unresolved_left_assign = True
						elif key_name == 'K_RIGHT':
							saw_right_assign = True
							if isinstance(d, int):
								right_delta += d
							else:
								unresolved_right_assign = True
					elif idx == 1:
						if key_name == 'K_UP':
							saw_up_assign = True
							if isinstance(d, int):
								up_delta += d
							else:
								unresolved_up_assign = True
						elif key_name == 'K_DOWN':
							saw_down_assign = True
							if isinstance(d, int):
								down_delta += d
							else:
								unresolved_down_assign = True
			(
				jump_y,
				jump_vy_max,
				jump_release_cut,
				jump_edge_trigger,
				saw_jump_assign,
				unresolved_jump_assign,
			) = _collect_jump_assignments(
				stmt,
				vel_alias_name = vel_alias_name,
				consts = consts,
				key_name = key_name,
				jump_y = jump_y,
				jump_vy_max = jump_vy_max,
				jump_release_cut = jump_release_cut,
				jump_edge_trigger = jump_edge_trigger,
				saw_jump_assign = saw_jump_assign,
				unresolved_jump_assign = unresolved_jump_assign,
			)
			if key_name == 'K_A' and isinstance(guard_max, int):
				jump_vy_max = guard_max if jump_vy_max is None else min(int(jump_vy_max), int(guard_max))
	if not target_hit:
		return VelocityCompileResult(
			velocity_script = None,
			init_velocity = None,
			ir = ir,
			asm_bytes = b'',
			asm_listing = [],
			symbol_map = {},
			diagnostics = ['No matching set_linear_velocity/set_rigid_body_velocity target found for script.'],
		)
	dynamic_reasons = []
	if saw_left_assign and unresolved_left_assign:
		dynamic_reasons.append('left_delta')
	if saw_right_assign and unresolved_right_assign:
		dynamic_reasons.append('right_delta')
	if saw_up_assign and unresolved_up_assign:
		dynamic_reasons.append('up_delta')
	if saw_down_assign and unresolved_down_assign:
		dynamic_reasons.append('down_delta')
	if saw_jump_assign and unresolved_jump_assign:
		dynamic_reasons.append('jump_y')
	if dynamic_reasons != []:
		return VelocityCompileResult(
			velocity_script = None,
			init_velocity = None,
			ir = ir,
			asm_bytes = b'',
			asm_listing = [],
			symbol_map = {},
			diagnostics = [
				'Velocity script uses unresolved non-constant terms for: ' + ', '.join(dynamic_reasons) + '.',
			],
		)
	if not base_vx_found:
		base_vx = 0
	if not base_vy_found:
		base_vy = 0
	velocity_script = {
		'base_vx': int(base_vx),
		'base_vy': int(base_vy),
		'left_delta': int(left_delta),
		'right_delta': int(right_delta),
		'up_delta': int(up_delta),
		'down_delta': int(down_delta),
		'jump_y': None if jump_y is None else int(jump_y),
		'jump_vy_max': None if jump_vy_max is None else int(jump_vy_max),
		'jump_release_cut': bool(jump_release_cut),
		'jump_edge_trigger': bool(jump_edge_trigger),
	}
	if init_velocity is None:
		init_velocity = (int(base_vx), int(-base_vy))
	asm_bytes, asm_listing, symbol_map = lower_ir_to_gbz80(ir)
	return VelocityCompileResult(
		velocity_script = velocity_script,
		init_velocity = init_velocity,
		ir = ir,
		asm_bytes = asm_bytes,
		asm_listing = asm_listing,
		symbol_map = symbol_map,
		diagnostics = [
			'Compiler spec=' + str(COMPILER_SEMANTICS_SPEC.version),
			'Strict mode=' + ('on' if bool(strict_compiler_mode) else 'off'),
		],
	)


def _slot_addr_for_name (name: str) -> int:
	return 0xC400 + (sum([ord(ch) for ch in str(name)]) & 0x7F)


def _emit_load_expr_to_a (emitter: Gbz80Emitter, expr: IrExpr, consts: Dict[str, int]) -> bool:
	if isinstance(expr, IrConst):
		try:
			emitter.ld_a_imm(int(round(float(expr.value))))
			return True
		except Exception:
			return False
	if isinstance(expr, IrName):
		slot = _slot_addr_for_name(expr.name)
		emitter.ld_hl_imm(slot)
		emitter.ld_a_hl()
		return True
	if isinstance(expr, IrUnary) and expr.op in ('+', '-'):
		if not _emit_load_expr_to_a(emitter, expr.value, consts):
			return False
		if expr.op == '-':
			# A = -A (8-bit two's complement).
			emitter.xor_a_imm(0xFF)
			emitter.add_a_imm(1)
		return True
	if isinstance(expr, IrBinOp):
		rv = _small_int(expr.right, consts)
		if rv is None:
			return False
		if not _emit_load_expr_to_a(emitter, expr.left, consts):
			return False
		if expr.op == '+':
			emitter.add_a_imm(rv)
			return True
		if expr.op == '-':
			emitter.sub_a_imm(rv)
			return True
	return False


def _emit_truthy_test (emitter: Gbz80Emitter, expr: IrExpr, consts: Dict[str, int], false_label: str):
	if isinstance(expr, IrBoolAnd):
		for part in list(expr.parts):
			_emit_truthy_test(emitter, part, consts, false_label)
		return
	if isinstance(expr, IrBoolOr):
		end_label = false_label + '_or_ok'
		for part in list(expr.parts):
			_emit_load_expr_to_a(emitter, part, consts)
			emitter.and_a()
			emitter.jr_nz(end_label)
		emitter.jr(false_label)
		emitter.mark(end_label)
		return
	if isinstance(expr, IrUnary) and expr.op == 'not':
		if _emit_load_expr_to_a(emitter, expr.value, consts):
			emitter.and_a()
			emitter.jr_nz(false_label)
		return
	if isinstance(expr, IrCompare):
		rv = _small_int(expr.right, consts)
		if rv is None:
			if not _emit_load_expr_to_a(emitter, expr.left, consts):
				emitter.jr(false_label)
				return
			emitter.and_a()
			emitter.jr_z(false_label)
			return
		if not _emit_load_expr_to_a(emitter, expr.left, consts):
			emitter.jr(false_label)
			return
		emitter.cp_a_imm(rv)
		if expr.op == '==':
			emitter.jr_nz(false_label)
		elif expr.op == '!=':
			pass
		elif expr.op in ('<', '<=', '>', '>='):
			# Conservative lowering for signed compare in v1 backend:
			# only strict equality/inequality is branch-accurate for now.
			# Non-equality compares are left as non-zero truthy fallback.
			emitter.and_a()
			emitter.jr_z(false_label)
		return
	if not _emit_load_expr_to_a(emitter, expr, consts):
		emitter.jr(false_label)
		return
	emitter.and_a()
	emitter.jr_z(false_label)


def lower_ir_to_gbz80 (program: IrProgram) -> Tuple[bytes, List[str], Dict[str, int]]:
	emitter = Gbz80Emitter()
	emitter.mark('entry')
	consts: Dict[str, int] = {}
	label_counter = 0

	def _emit_stmt (_stmt: IrStmt):
		nonlocal label_counter
		if isinstance(_stmt, IrAssign) and isinstance(_stmt.target, IrName):
			if _emit_load_expr_to_a(emitter, _stmt.value, consts):
				slot = _slot_addr_for_name(_stmt.target.name)
				emitter.ld_hl_imm(slot)
				emitter.ld_hl_a()
				v = _small_int(_stmt.value, consts)
				if isinstance(v, int):
					consts[_stmt.target.name] = int(v)
				else:
					consts.pop(_stmt.target.name, None)
			return
		if isinstance(_stmt, IrAugAssign) and isinstance(_stmt.target, IrName):
			slot = _slot_addr_for_name(_stmt.target.name)
			emitter.ld_hl_imm(slot)
			emitter.ld_a_hl()
			d = _small_int(_stmt.value, consts)
			if isinstance(d, int):
				if _stmt.op == '+':
					emitter.add_a_imm(d)
				elif _stmt.op == '-':
					emitter.sub_a_imm(d)
				emitter.ld_hl_imm(slot)
				emitter.ld_hl_a()
				prev = consts.get(_stmt.target.name)
				if isinstance(prev, int):
					consts[_stmt.target.name] = int(prev + d) if _stmt.op == '+' else int(prev - d)
				else:
					consts.pop(_stmt.target.name, None)
			return
		if isinstance(_stmt, IrExprStmt):
			_emit_load_expr_to_a(emitter, _stmt.value, consts)
			return
		if isinstance(_stmt, IrIf):
			label_counter += 1
			else_label = 'if_else_' + str(label_counter)
			end_label = 'if_end_' + str(label_counter)
			_emit_truthy_test(emitter, _stmt.test, consts, else_label)
			for inner in list(_stmt.body):
				_emit_stmt(inner)
			emitter.jr(end_label)
			emitter.mark(else_label)
			for inner in list(_stmt.orelse):
				_emit_stmt(inner)
			emitter.mark(end_label)
			return

	for stmt in list(program.blocks.get(program.entry_block, IrBasicBlock('entry')).stmts):
		_emit_stmt(stmt)
	emitter.emit(0xC9)
	emitter.asm_lines.append('  ret')
	emitter.resolve()
	symbol_map = {k : int(emitter.base_addr + v) for k, v in emitter.labels.items()}
	return bytes(emitter.code), list(emitter.asm_lines), symbol_map


@dataclass(frozen = True)
class GbcAotAbiSpec:
	version: str = 'aot-v1'
	base_addr_default: int = 0x150
	wram_global_base: int = 0xC400
	wram_param_base: int = 0xC780
	wram_temp_base: int = 0xC7C0
	wram_return_addr: int = 0xC7FE
	max_globals: int = 96
	max_locals_per_function: int = 48
	max_params_per_function: int = 8
	# Fixed runtime API vector for explicit host-backed hooks.
	runtime_call_map: Tuple[Tuple[str, int], ...] = (
		('gbc_read_input', 0x02A0),
		('gbc_key_left', 0x02A4),
		('gbc_key_right', 0x02A8),
		('gbc_key_up', 0x02AC),
		('gbc_key_down', 0x02B0),
		('gbc_key_a', 0x02B4),
		('gbc_key_b', 0x02B8),
		('gbc_key_start', 0x02BC),
		('gbc_key_select', 0x02C0),
		('gbc_get_vel_x', 0x02C4),
		('gbc_get_vel_y', 0x02C8),
		('gbc_set_vel_xy', 0x02CC),
	)


GBC_AOT_ABI_SPEC = GbcAotAbiSpec()


@dataclass
class GbcGeneralCompileResult:
	asm_bytes: bytes
	asm_listing: List[str]
	symbol_map: Dict[str, int]
	diagnostics: List[str] = field(default_factory = list)
	init_entry_label: str = '__entry_init'
	update_entry_label: str = '__entry_update'
	init_offset: Optional[int] = None
	update_offset: Optional[int] = None


class _AotEmitter:
	def __init__ (self, base_addr: int = 0x150):
		self.base_addr = int(base_addr)
		self.code = bytearray()
		self.labels: Dict[str, int] = {}
		self.jr_fixups: List[Tuple[int, str]] = []
		self.abs_fixups: List[Tuple[int, str]] = []
		self.asm_lines: List[str] = []

	def mark (self, label: str):
		self.labels[str(label)] = len(self.code)
		self.asm_lines.append(str(label) + ':')

	def emit (self, *bytes_: int):
		for b in bytes_:
			self.code.append(int(b) & 0xFF)

	def ld_a_imm (self, v: int):
		self.emit(0x3E, int(v) & 0xFF)
		self.asm_lines.append('  ld a, $%02x' % (int(v) & 0xFF))

	def ld_a_addr (self, addr: int):
		self.emit(0xFA, int(addr) & 0xFF, (int(addr) >> 8) & 0xFF)
		self.asm_lines.append('  ld a, [$%04x]' % (int(addr) & 0xFFFF))

	def ld_addr_a (self, addr: int):
		self.emit(0xEA, int(addr) & 0xFF, (int(addr) >> 8) & 0xFF)
		self.asm_lines.append('  ld [$%04x], a' % (int(addr) & 0xFFFF))

	def ld_b_a (self):
		self.emit(0x47)
		self.asm_lines.append('  ld b, a')

	def ld_c_a (self):
		self.emit(0x4F)
		self.asm_lines.append('  ld c, a')

	def ld_a_b (self):
		self.emit(0x78)
		self.asm_lines.append('  ld a, b')

	def ld_a_c (self):
		self.emit(0x79)
		self.asm_lines.append('  ld a, c')

	def add_a_b (self):
		self.emit(0x80)
		self.asm_lines.append('  add a, b')

	def add_a_c (self):
		self.emit(0x81)
		self.asm_lines.append('  add a, c')

	def sub_a_b (self):
		self.emit(0x90)
		self.asm_lines.append('  sub a, b')

	def sub_a_c (self):
		self.emit(0x91)
		self.asm_lines.append('  sub a, c')

	def cp_a_b (self):
		self.emit(0xB8)
		self.asm_lines.append('  cp a, b')

	def cp_a_c (self):
		self.emit(0xB9)
		self.asm_lines.append('  cp a, c')

	def cp_a_imm (self, v: int):
		self.emit(0xFE, int(v) & 0xFF)
		self.asm_lines.append('  cp a, $%02x' % (int(v) & 0xFF))

	def xor_a_imm (self, v: int):
		self.emit(0xEE, int(v) & 0xFF)
		self.asm_lines.append('  xor a, $%02x' % (int(v) & 0xFF))

	def and_a (self):
		self.emit(0xA7)
		self.asm_lines.append('  and a')

	def or_a (self):
		self.emit(0xB7)
		self.asm_lines.append('  or a')

	def inc_a (self):
		self.emit(0x3C)
		self.asm_lines.append('  inc a')

	def dec_a (self):
		self.emit(0x3D)
		self.asm_lines.append('  dec a')

	def cpl (self):
		self.emit(0x2F)
		self.asm_lines.append('  cpl')

	def push_af (self):
		self.emit(0xF5)
		self.asm_lines.append('  push af')

	def push_bc (self):
		self.emit(0xC5)
		self.asm_lines.append('  push bc')

	def push_de (self):
		self.emit(0xD5)
		self.asm_lines.append('  push de')

	def push_hl (self):
		self.emit(0xE5)
		self.asm_lines.append('  push hl')

	def pop_hl (self):
		self.emit(0xE1)
		self.asm_lines.append('  pop hl')

	def pop_de (self):
		self.emit(0xD1)
		self.asm_lines.append('  pop de')

	def pop_bc (self):
		self.emit(0xC1)
		self.asm_lines.append('  pop bc')

	def pop_af (self):
		self.emit(0xF1)
		self.asm_lines.append('  pop af')

	def jr (self, label: str):
		pos = len(self.code)
		self.emit(0x18, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr ' + str(label))

	def jr_z (self, label: str):
		pos = len(self.code)
		self.emit(0x28, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr z, ' + str(label))

	def jr_nz (self, label: str):
		pos = len(self.code)
		self.emit(0x20, 0x00)
		self.jr_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jr nz, ' + str(label))

	def jp (self, label: str):
		pos = len(self.code)
		self.emit(0xC3, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp ' + str(label))

	def jp_z (self, label: str):
		pos = len(self.code)
		self.emit(0xCA, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp z, ' + str(label))

	def jp_nz (self, label: str):
		pos = len(self.code)
		self.emit(0xC2, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp nz, ' + str(label))

	def jp_c (self, label: str):
		pos = len(self.code)
		self.emit(0xDA, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp c, ' + str(label))

	def jp_nc (self, label: str):
		pos = len(self.code)
		self.emit(0xD2, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  jp nc, ' + str(label))

	def call_label (self, label: str):
		pos = len(self.code)
		self.emit(0xCD, 0x00, 0x00)
		self.abs_fixups.append((pos + 1, str(label)))
		self.asm_lines.append('  call ' + str(label))

	def call_abs (self, abs_addr: int):
		self.emit(0xCD, int(abs_addr) & 0xFF, (int(abs_addr) >> 8) & 0xFF)
		self.asm_lines.append('  call $%04x' % (int(abs_addr) & 0xFFFF))

	def ret (self):
		self.emit(0xC9)
		self.asm_lines.append('  ret')

	def resolve (self):
		for at, label in self.jr_fixups:
			if label not in self.labels:
				raise GbcTranspileError('Unknown JR label: ' + str(label))
			target = self.labels[label]
			disp = int(target - (at + 1))
			if disp < -128 or disp > 127:
				raise GbcTranspileError('JR out of range for label: ' + str(label))
			self.code[at] = disp & 0xFF
		for at, label in self.abs_fixups:
			if label not in self.labels:
				raise GbcTranspileError('Unknown JP/CALL label: ' + str(label))
			abs_addr = self.base_addr + int(self.labels[label])
			self.code[at] = abs_addr & 0xFF
			self.code[at + 1] = (abs_addr >> 8) & 0xFF


def _scan_assigned_names (stmts) -> Set[str]:
	out: Set[str] = set()

	class _Scan(ast.NodeVisitor):
		def visit_Assign (self, node):
			for t in list(getattr(node, 'targets', []) or []):
				if isinstance(t, ast.Name):
					out.add(str(t.id))
			self.generic_visit(node)

		def visit_AugAssign (self, node):
			t = getattr(node, 'target', None)
			if isinstance(t, ast.Name):
				out.add(str(t.id))
			self.generic_visit(node)

	visitor = _Scan()
	for s in list(stmts or []):
		visitor.visit(s)
	return out


class _GeneralAotCompiler:
	def __init__ (self, code: str, abi: GbcAotAbiSpec, base_addr: int, symbol_prefix: str):
		self.code = str(code or '')
		self.abi = abi
		self.base_addr = int(base_addr)
		self.symbol_prefix = str(symbol_prefix or 'gbc_script')
		self.tree = ast.parse(self.code)
		self.emitter = _AotEmitter(base_addr = self.base_addr)
		self.label_counter = 0
		self.global_slots: Dict[str, int] = {}
		self.temp0_addr = int(self.abi.wram_temp_base)
		self.temp1_addr = int(self.abi.wram_temp_base + 1)
		self.func_defs: Dict[str, ast.FunctionDef] = {}
		self.func_params: Dict[str, List[str]] = {}
		self.func_locals: Dict[str, Dict[str, int]] = {}
		self.top_level_stmts = []
		self.runtime_calls = dict(self.abi.runtime_call_map)
		self.function_labels: Dict[str, str] = {}
		self.break_stack: List[str] = []
		self.continue_stack: List[str] = []
		self.current_func_epilogue_label: Optional[str] = None
		self.current_func_locals: Dict[str, int] = {}
		self.current_func_global_names: Set[str] = set()
		self.current_func_name: str = '<top>'
		self.init_entry_label = '__entry_init'
		self.update_entry_label = '__entry_update'

	def _next_label (self, stem: str) -> str:
		self.label_counter += 1
		return '%s_%d' % (str(stem), int(self.label_counter))

	def _disallow_node (self, node, what: str):
		line = getattr(node, 'lineno', None)
		raise GbcTranspileError('Unsupported in general AOT subset: ' + str(what), line = int(line) if isinstance(line, int) else None)

	def _validate_tree (self):
		for node in ast.walk(self.tree):
			if isinstance(node, (ast.Import, ast.ImportFrom, ast.AsyncFunctionDef, ast.Try, ast.With, ast.Delete, ast.Lambda, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom)):
				self._disallow_node(node, type(node).__name__)
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', '__import__'):
				self._disallow_node(node, node.func.id)
			if isinstance(node, ast.Call) and len(list(getattr(node, 'keywords', []) or [])) > 0:
				self._disallow_node(node, 'keyword args')
		for stmt in list(getattr(self.tree, 'body', []) or []):
			if isinstance(stmt, ast.FunctionDef):
				continue
			if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.If, ast.While, ast.Expr, ast.Pass)):
				continue
			self._disallow_node(stmt, type(stmt).__name__)

	def _allocate_global_slots (self):
		names: Set[str] = set()
		for stmt in list(getattr(self.tree, 'body', []) or []):
			if isinstance(stmt, ast.FunctionDef):
				self.func_defs[str(stmt.name)] = stmt
				self.func_params[str(stmt.name)] = [str(a.arg) for a in list(getattr(stmt.args, 'args', []) or [])]
				if len(self.func_params[str(stmt.name)]) > int(self.abi.max_params_per_function):
					self._disallow_node(stmt, 'too many parameters')
			else:
				self.top_level_stmts.append(stmt)
		names |= _scan_assigned_names(self.top_level_stmts)
		for fn in list(self.func_defs.values()):
			names |= _scan_assigned_names(getattr(fn, 'body', []))
		for n in sorted(list(names)):
			if len(self.global_slots) >= int(self.abi.max_globals):
				raise GbcTranspileError('Too many global variables for AOT ABI.')
			self.global_slots[n] = int(self.abi.wram_global_base + len(self.global_slots))
		for fn_name, fn in self.func_defs.items():
			param_names = list(self.func_params.get(fn_name, []))
			local_names = sorted(list(_scan_assigned_names(getattr(fn, 'body', []))))
			slot_map: Dict[str, int] = {}
			start = int(self.abi.wram_global_base + int(self.abi.max_globals) + len(self.func_locals) * int(self.abi.max_locals_per_function))
			i = 0
			for p in param_names + local_names:
				if p in slot_map:
					continue
				if i >= int(self.abi.max_locals_per_function):
					raise GbcTranspileError('Too many locals in function: ' + str(fn_name))
				slot_map[p] = start + i
				i += 1
			self.func_locals[fn_name] = slot_map
			self.function_labels[fn_name] = 'fn_' + str(self.symbol_prefix) + '_' + str(fn_name)

	def _slot_for_name (self, name: str) -> int:
		s = str(name)
		if s in self.current_func_locals:
			return int(self.current_func_locals[s])
		return int(self.global_slots.setdefault(s, int(self.abi.wram_global_base + (sum([ord(ch) for ch in s]) & 0x7F))))

	def _emit_load_expr_to_a (self, expr):
		if isinstance(expr, ast.Constant):
			v = expr.value
			if isinstance(v, bool):
				self.emitter.ld_a_imm(1 if bool(v) else 0)
				return
			if isinstance(v, (int, float)):
				self.emitter.ld_a_imm(int(round(float(v))))
				return
			self._disallow_node(expr, 'non-numeric constant')
		if isinstance(expr, ast.Name):
			self.emitter.ld_a_addr(self._slot_for_name(expr.id))
			return
		if isinstance(expr, ast.UnaryOp):
			if isinstance(expr.op, ast.Not):
				self._emit_load_expr_to_a(expr.operand)
				self.emitter.and_a()
				false_l = self._next_label('not_false')
				done_l = self._next_label('not_done')
				self.emitter.jp_z(false_l)
				self.emitter.ld_a_imm(0)
				self.emitter.jp(done_l)
				self.emitter.mark(false_l)
				self.emitter.ld_a_imm(1)
				self.emitter.mark(done_l)
				return
			if isinstance(expr.op, ast.USub):
				self._emit_load_expr_to_a(expr.operand)
				self.emitter.xor_a_imm(0xFF)
				self.emitter.inc_a()
				return
			if isinstance(expr.op, ast.UAdd):
				self._emit_load_expr_to_a(expr.operand)
				return
		if isinstance(expr, ast.BinOp):
			self._emit_load_expr_to_a(expr.left)
			self.emitter.ld_c_a()
			self._emit_load_expr_to_a(expr.right)
			self.emitter.ld_b_a()
			self.emitter.ld_a_c()
			if isinstance(expr.op, ast.Add):
				self.emitter.add_a_b()
				return
			if isinstance(expr.op, ast.Sub):
				self.emitter.sub_a_b()
				return
			self._disallow_node(expr, type(expr.op).__name__)
		if isinstance(expr, ast.Call):
			self._emit_call(expr, keep_result = True)
			return
		if isinstance(expr, ast.Compare) and len(list(expr.ops or [])) == 1 and len(list(expr.comparators or [])) == 1:
			truth_false = self._next_label('cmp_false')
			truth_done = self._next_label('cmp_done')
			self._emit_cond_jump_false(expr, truth_false)
			self.emitter.ld_a_imm(1)
			self.emitter.jp(truth_done)
			self.emitter.mark(truth_false)
			self.emitter.ld_a_imm(0)
			self.emitter.mark(truth_done)
			return
		self._disallow_node(expr, type(expr).__name__)

	def _emit_cmp_signed (self, left_expr, right_expr):
		self._emit_load_expr_to_a(left_expr)
		self.emitter.xor_a_imm(0x80)
		self.emitter.ld_c_a()
		self._emit_load_expr_to_a(right_expr)
		self.emitter.xor_a_imm(0x80)
		self.emitter.ld_b_a()
		self.emitter.ld_a_c()
		self.emitter.cp_a_b()

	def _emit_cond_jump_false (self, expr, false_label: str):
		if isinstance(expr, ast.BoolOp):
			if isinstance(expr.op, ast.And):
				for p in list(expr.values or []):
					self._emit_cond_jump_false(p, false_label)
				return
			if isinstance(expr.op, ast.Or):
				done_l = self._next_label('or_done')
				for p in list(expr.values or [])[: -1]:
					skip_false = self._next_label('or_skip')
					self._emit_cond_jump_false(p, skip_false)
					self.emitter.jp(done_l)
					self.emitter.mark(skip_false)
				tail = list(expr.values or [])[-1] if list(expr.values or []) != [] else None
				if tail is None:
					self.emitter.jp(false_label)
				else:
					self._emit_cond_jump_false(tail, false_label)
				self.emitter.mark(done_l)
				return
		if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
			self._emit_load_expr_to_a(expr.operand)
			self.emitter.and_a()
			self.emitter.jp_nz(false_label)
			return
		if isinstance(expr, ast.Compare) and len(list(expr.ops or [])) == 1 and len(list(expr.comparators or [])) == 1:
			op = expr.ops[0]
			l = expr.left
			r = expr.comparators[0]
			self._emit_cmp_signed(l, r)
			if isinstance(op, ast.Eq):
				self.emitter.jp_nz(false_label)
				return
			if isinstance(op, ast.NotEq):
				self.emitter.jp_z(false_label)
				return
			if isinstance(op, ast.Lt):
				self.emitter.jp_nc(false_label)
				return
			if isinstance(op, ast.LtE):
				ok_label = self._next_label('lte_ok')
				self.emitter.jp_c(ok_label)
				self.emitter.jp_z(ok_label)
				self.emitter.jp(false_label)
				self.emitter.mark(ok_label)
				return
			if isinstance(op, ast.Gt):
				self.emitter.jp_c(false_label)
				self.emitter.jp_z(false_label)
				return
			if isinstance(op, ast.GtE):
				self.emitter.jp_c(false_label)
				return
			self._disallow_node(expr, type(op).__name__)
		self._emit_load_expr_to_a(expr)
		self.emitter.and_a()
		self.emitter.jp_z(false_label)

	def _emit_call (self, call_node: ast.Call, keep_result: bool = True):
		fn = call_node.func
		if isinstance(fn, ast.Name):
			fn_name = str(fn.id)
			if fn_name in self.runtime_calls:
				for i, arg in enumerate(list(call_node.args or [])):
					param_addr = int(self.abi.wram_param_base + i)
					self._emit_load_expr_to_a(arg)
					self.emitter.ld_addr_a(param_addr)
				self.emitter.call_abs(int(self.runtime_calls[fn_name]))
			elif fn_name in self.function_labels:
				for i, arg in enumerate(list(call_node.args or [])):
					param_addr = int(self.abi.wram_param_base + i)
					self._emit_load_expr_to_a(arg)
					self.emitter.ld_addr_a(param_addr)
				self.emitter.call_label(self.function_labels[fn_name])
			else:
				self._disallow_node(call_node, 'call to ' + fn_name)
		else:
			self._disallow_node(call_node, 'indirect call')
		if keep_result:
			self.emitter.ld_addr_a(int(self.abi.wram_return_addr))

	def _emit_stmt (self, stmt):
		if isinstance(stmt, ast.Pass):
			return
		if isinstance(stmt, ast.Assign) and len(list(stmt.targets or [])) == 1:
			t = stmt.targets[0]
			if not isinstance(t, ast.Name):
				self._disallow_node(stmt, 'non-name assignment target')
			self._emit_load_expr_to_a(stmt.value)
			self.emitter.ld_addr_a(self._slot_for_name(t.id))
			return
		if isinstance(stmt, ast.AugAssign):
			if not isinstance(stmt.target, ast.Name):
				self._disallow_node(stmt, 'non-name augassign')
			slot = self._slot_for_name(stmt.target.id)
			self.emitter.ld_a_addr(slot)
			self.emitter.ld_c_a()
			self._emit_load_expr_to_a(stmt.value)
			self.emitter.ld_b_a()
			self.emitter.ld_a_c()
			if isinstance(stmt.op, ast.Add):
				self.emitter.add_a_b()
			elif isinstance(stmt.op, ast.Sub):
				self.emitter.sub_a_b()
			else:
				self._disallow_node(stmt, type(stmt.op).__name__)
			self.emitter.ld_addr_a(slot)
			return
		if isinstance(stmt, ast.Expr):
			v = stmt.value
			if isinstance(v, ast.Call):
				self._emit_call(v, keep_result = False)
				return
			self._emit_load_expr_to_a(v)
			return
		if isinstance(stmt, ast.If):
			else_l = self._next_label('if_else')
			end_l = self._next_label('if_end')
			self._emit_cond_jump_false(stmt.test, else_l)
			for inner in list(stmt.body or []):
				self._emit_stmt(inner)
			self.emitter.jp(end_l)
			self.emitter.mark(else_l)
			for inner in list(stmt.orelse or []):
				self._emit_stmt(inner)
			self.emitter.mark(end_l)
			return
		if isinstance(stmt, ast.While):
			loop_l = self._next_label('while_loop')
			end_l = self._next_label('while_end')
			self.continue_stack.append(loop_l)
			self.break_stack.append(end_l)
			self.emitter.mark(loop_l)
			self._emit_cond_jump_false(stmt.test, end_l)
			for inner in list(stmt.body or []):
				self._emit_stmt(inner)
			self.emitter.jp(loop_l)
			self.emitter.mark(end_l)
			self.break_stack.pop()
			self.continue_stack.pop()
			return
		if isinstance(stmt, ast.Break):
			if self.break_stack == []:
				self._disallow_node(stmt, 'break outside loop')
			self.emitter.jp(self.break_stack[-1])
			return
		if isinstance(stmt, ast.Continue):
			if self.continue_stack == []:
				self._disallow_node(stmt, 'continue outside loop')
			self.emitter.jp(self.continue_stack[-1])
			return
		if isinstance(stmt, ast.Return):
			if stmt.value is None:
				self.emitter.ld_a_imm(0)
			else:
				self._emit_load_expr_to_a(stmt.value)
			self.emitter.ld_addr_a(int(self.abi.wram_return_addr))
			if self.current_func_epilogue_label is None:
				self._disallow_node(stmt, 'return outside function')
			self.emitter.jp(self.current_func_epilogue_label)
			return
		self._disallow_node(stmt, type(stmt).__name__)

	def _emit_function (self, fn_name: str, fn_node: ast.FunctionDef):
		fn_label = self.function_labels[fn_name]
		self.current_func_name = fn_name
		self.current_func_locals = dict(self.func_locals.get(fn_name, {}))
		self.current_func_epilogue_label = self._next_label(fn_name + '_epilogue')
		self.emitter.mark(fn_label)
		self.emitter.push_af()
		self.emitter.push_bc()
		self.emitter.push_de()
		self.emitter.push_hl()
		for i, p in enumerate(list(self.func_params.get(fn_name, []))):
			dst = self._slot_for_name(p)
			src = int(self.abi.wram_param_base + i)
			self.emitter.ld_a_addr(src)
			self.emitter.ld_addr_a(dst)
		for inner in list(getattr(fn_node, 'body', []) or []):
			self._emit_stmt(inner)
		self.emitter.ld_a_imm(0)
		self.emitter.ld_addr_a(int(self.abi.wram_return_addr))
		self.emitter.mark(self.current_func_epilogue_label)
		self.emitter.ld_a_addr(int(self.abi.wram_return_addr))
		self.emitter.pop_hl()
		self.emitter.pop_de()
		self.emitter.pop_bc()
		self.emitter.pop_af()
		self.emitter.ret()
		self.current_func_epilogue_label = None
		self.current_func_locals = {}

	def compile (self) -> GbcGeneralCompileResult:
		self._validate_tree()
		self._allocate_global_slots()
		self.emitter.mark(self.init_entry_label)
		for s in list(self.top_level_stmts):
			self._emit_stmt(s)
		if 'init' in self.function_labels:
			self.emitter.call_label(self.function_labels['init'])
		self.emitter.ret()
		self.emitter.mark(self.update_entry_label)
		if 'update' in self.function_labels:
			self.emitter.call_label(self.function_labels['update'])
		else:
			for s in list(self.top_level_stmts):
				self._emit_stmt(s)
		self.emitter.ret()
		for fn_name in sorted(list(self.func_defs.keys())):
			self._emit_function(fn_name, self.func_defs[fn_name])
		self.emitter.resolve()
		symbol_map = {k : int(self.emitter.base_addr + v) for k, v in self.emitter.labels.items()}
		init_off = self.emitter.labels.get(self.init_entry_label, None)
		update_off = self.emitter.labels.get(self.update_entry_label, None)
		return GbcGeneralCompileResult(
			asm_bytes = bytes(self.emitter.code),
			asm_listing = list(self.emitter.asm_lines),
			symbol_map = symbol_map,
			diagnostics = [
				'AOT ABI=' + str(self.abi.version),
				'globals=' + str(len(self.global_slots)),
				'functions=' + str(len(self.func_defs)),
			],
			init_entry_label = self.init_entry_label,
			update_entry_label = self.update_entry_label,
			init_offset = int(init_off) if isinstance(init_off, int) else None,
			update_offset = int(update_off) if isinstance(update_off, int) else None,
		)


def compile_general_script (
	code: str,
	base_addr: int = 0x150,
	symbol_prefix: str = 'gbc_script',
	abi_spec: GbcAotAbiSpec = GBC_AOT_ABI_SPEC,
) -> GbcGeneralCompileResult:
	compiler = _GeneralAotCompiler(
		code = str(code or ''),
		abi = abi_spec,
		base_addr = int(base_addr),
		symbol_prefix = str(symbol_prefix or 'gbc_script'),
	)
	return compiler.compile()


@dataclass
class GbcCFunctionCompileResult:
	c_source: str
	diagnostics: List[str] = field(default_factory = list)


class _GeneralCFunctionTranspiler:
	def __init__ (self, code: str, function_name: str, this_var_name: str = 'js13k_this'):
		self.code = str(code or '')
		self.function_name = str(function_name or 'gbc_script_fn')
		self.this_var_name = str(this_var_name or 'js13k_this')
		self.tree = ast.parse(self.code)
		self.indent = 0
		self.lines: List[str] = []
		self.local_symbols: Set[str] = set()
		self.local_symbol_types: Dict[str, str] = {}
		self.diagnostics: List[str] = []

	def _disallow_node (self, node, what: str):
		line = getattr(node, 'lineno', None)
		raise GbcTranspileError(
			'Unsupported in C transpiler subset: ' + str(what),
			line = int(line) if isinstance(line, int) else None,
		)

	def _validate_tree (self):
		for node in ast.walk(self.tree):
			if isinstance(node, (ast.Import, ast.ImportFrom, ast.AsyncFunctionDef, ast.Try, ast.With, ast.Delete, ast.Lambda, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Await, ast.Yield, ast.YieldFrom)):
				self._disallow_node(node, type(node).__name__)
			if isinstance(node, ast.Call) and len(list(getattr(node, 'keywords', []) or [])) > 0:
				self._disallow_node(node, 'keyword args')
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec', 'compile', '__import__'):
				self._disallow_node(node, node.func.id)
		for stmt in list(getattr(self.tree, 'body', []) or []):
			if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.If, ast.While, ast.Expr, ast.Pass, ast.FunctionDef, ast.Return, ast.Break, ast.Continue)):
				continue
			self._disallow_node(stmt, type(stmt).__name__)

	def _safe_ident (self, txt: str) -> str:
		out = ''.join([(ch if (ch.isalnum() or ch == '_') else '_') for ch in str(txt or '')])
		out = out.strip('_')
		if out == '':
			out = 'v'
		if out[0].isdigit():
			out = '_' + out
		return out

	def _c_string_literal (self, txt: str) -> str:
		s = str(txt or '')
		s = s.replace('\\', '\\\\')
		s = s.replace('"', '\\"')
		s = s.replace('\n', '\\n')
		s = s.replace('\r', '\\r')
		s = s.replace('\t', '\\t')
		return '"' + s + '"'

	def _expr_to_c (self, expr) -> str:
		if isinstance(expr, ast.Constant):
			if isinstance(expr.value, bool):
				return '1' if bool(expr.value) else '0'
			if isinstance(expr.value, (int, float)):
				return str(int(round(float(expr.value))))
			if isinstance(expr.value, str):
				return self._c_string_literal(expr.value)
			if expr.value is None:
				return '0'
			self._disallow_node(expr, 'non-numeric constant')
		if isinstance(expr, ast.Name):
			if expr.id == 'this':
				return self.this_var_name
			return self._safe_ident(expr.id)
		if isinstance(expr, ast.Attribute):
			if isinstance(expr.value, ast.Name) and expr.value.id == 'this':
				return self.this_var_name + '->' + self._safe_ident(expr.attr)
			base = self._expr_to_c(expr.value)
			return self._safe_ident(str(base) + '_' + str(expr.attr))
		if isinstance(expr, ast.Subscript):
			base = self._expr_to_c(expr.value)
			idx = expr.slice
			if hasattr(ast, 'Index') and isinstance(idx, ast.Index):
				idx = idx.value
			return '(' + base + '[' + self._expr_to_c(idx) + '])'
		if isinstance(expr, ast.List):
			items = [self._expr_to_c(x) for x in list(expr.elts or [])]
			return '((int32_t[]){' + ', '.join(items) + '})'
		if isinstance(expr, ast.Tuple):
			items = [self._expr_to_c(x) for x in list(expr.elts or [])]
			return '((int32_t[]){' + ', '.join(items) + '})'
		if isinstance(expr, ast.UnaryOp):
			if isinstance(expr.op, ast.Not):
				return '(!(' + self._expr_to_c(expr.operand) + '))'
			if isinstance(expr.op, ast.USub):
				return '(-(' + self._expr_to_c(expr.operand) + '))'
			if isinstance(expr.op, ast.UAdd):
				return '(+(' + self._expr_to_c(expr.operand) + '))'
		if isinstance(expr, ast.BoolOp):
			parts = [self._expr_to_c(v) for v in list(expr.values or [])]
			if parts == []:
				return '0'
			joiner = ' && ' if isinstance(expr.op, ast.And) else ' || '
			return '(' + joiner.join(['(' + p + ')' for p in parts]) + ')'
		if isinstance(expr, ast.BinOp):
			l = self._expr_to_c(expr.left)
			r = self._expr_to_c(expr.right)
			if isinstance(expr.op, ast.Add):
				return '((' + l + ') + (' + r + '))'
			if isinstance(expr.op, ast.Sub):
				return '((' + l + ') - (' + r + '))'
			if isinstance(expr.op, ast.Mult):
				return '((' + l + ') * (' + r + '))'
			if isinstance(expr.op, ast.Div):
				return '((' + l + ') / (' + r + '))'
			if isinstance(expr.op, ast.FloorDiv):
				return '((' + l + ') / (' + r + '))'
			if isinstance(expr.op, ast.Mod):
				return '((' + l + ') % (' + r + '))'
			self._disallow_node(expr, type(expr.op).__name__)
		if isinstance(expr, ast.Compare) and len(list(expr.ops or [])) == 1 and len(list(expr.comparators or [])) == 1:
			op = expr.ops[0]
			l = self._expr_to_c(expr.left)
			r = self._expr_to_c(expr.comparators[0])
			if isinstance(op, ast.Eq):
				return '((' + l + ') == (' + r + '))'
			if isinstance(op, ast.NotEq):
				return '((' + l + ') != (' + r + '))'
			if isinstance(op, ast.Lt):
				return '((' + l + ') < (' + r + '))'
			if isinstance(op, ast.LtE):
				return '((' + l + ') <= (' + r + '))'
			if isinstance(op, ast.Gt):
				return '((' + l + ') > (' + r + '))'
			if isinstance(op, ast.GtE):
				return '((' + l + ') >= (' + r + '))'
			self._disallow_node(expr, type(op).__name__)
		if isinstance(expr, ast.Call):
			fn = expr.func
			if isinstance(fn, ast.Name):
				fn_name = self._safe_ident(fn.id)
			elif isinstance(fn, ast.Attribute):
				fn_name = self._safe_ident(self._expr_to_c(fn))
			else:
				self._disallow_node(expr, 'indirect call')
			if fn_name == 'print':
				fn_name = 'js13k_print'
			args = [self._expr_to_c(a) for a in list(expr.args or [])]
			return fn_name + '(' + ', '.join(args) + ')'
		self._disallow_node(expr, type(expr).__name__)
		return '0'

	def _target_to_c_lvalue (self, target) -> str:
		if isinstance(target, ast.Name):
			if target.id == 'this':
				self._disallow_node(target, 'assign to this')
			return self._safe_ident(target.id)
		if isinstance(target, ast.Attribute):
			if isinstance(target.value, ast.Name) and target.value.id == 'this':
				return self.this_var_name + '->' + self._safe_ident(target.attr)
			return self._safe_ident(self._expr_to_c(target))
		if isinstance(target, ast.Subscript):
			return self._expr_to_c(target)
		self._disallow_node(target, 'assignment target')
		return '/*unsupported_target*/'

	def _collect_local_symbols (self, stmts):
		for stmt in list(stmts or []):
			if isinstance(stmt, ast.Assign):
				for t in list(stmt.targets or []):
					if isinstance(t, (ast.Name, ast.Attribute)):
						if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'this':
							continue
						name = self._target_to_c_lvalue(t)
						self.local_symbols.add(name)
						if isinstance(stmt.value, (ast.List, ast.Tuple)):
							self.local_symbol_types[name] = 'int32_t*'
						elif isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
							self.local_symbol_types[name] = 'const char*'
						else:
							self.local_symbol_types.setdefault(name, 'int32_t')
			elif isinstance(stmt, ast.AugAssign):
				if isinstance(stmt.target, (ast.Name, ast.Attribute)):
					if isinstance(stmt.target, ast.Attribute) and isinstance(stmt.target.value, ast.Name) and stmt.target.value.id == 'this':
						continue
					name = self._target_to_c_lvalue(stmt.target)
					self.local_symbols.add(name)
					self.local_symbol_types.setdefault(name, 'int32_t')
			elif isinstance(stmt, (ast.If, ast.While)):
				self._collect_local_symbols(getattr(stmt, 'body', []))
				self._collect_local_symbols(getattr(stmt, 'orelse', []))
			elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Subscript):
				b = stmt.value.base
				if isinstance(b, (ast.Name, ast.Attribute)):
					if isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name) and b.value.id == 'this':
						continue
					name = self._target_to_c_lvalue(b)
					self.local_symbols.add(name)
					self.local_symbol_types[name] = 'int32_t*'

	def _emit_line (self, txt: str):
		self.lines.append(('\t' * max(0, int(self.indent))) + str(txt))

	def _emit_stmt (self, stmt):
		if isinstance(stmt, ast.Pass):
			self._emit_line(';')
			return
		if isinstance(stmt, ast.Assign) and len(list(stmt.targets or [])) >= 1:
			rhs = self._expr_to_c(stmt.value)
			for t in list(stmt.targets or []):
				self._emit_line(self._target_to_c_lvalue(t) + ' = ' + rhs + ';')
			return
		if isinstance(stmt, ast.AugAssign):
			lhs = self._target_to_c_lvalue(stmt.target)
			rhs = self._expr_to_c(stmt.value)
			if isinstance(stmt.op, ast.Add):
				self._emit_line(lhs + ' += ' + rhs + ';')
			elif isinstance(stmt.op, ast.Sub):
				self._emit_line(lhs + ' -= ' + rhs + ';')
			else:
				self._disallow_node(stmt, type(stmt.op).__name__)
			return
		if isinstance(stmt, ast.Expr):
			self._emit_line(self._expr_to_c(stmt.value) + ';')
			return
		if isinstance(stmt, ast.If):
			self._emit_line('if (' + self._expr_to_c(stmt.test) + ') {')
			self.indent += 1
			for inner in list(stmt.body or []):
				self._emit_stmt(inner)
			self.indent -= 1
			if list(stmt.orelse or []) != []:
				self._emit_line('} else {')
				self.indent += 1
				for inner in list(stmt.orelse or []):
					self._emit_stmt(inner)
				self.indent -= 1
			self._emit_line('}')
			return
		if isinstance(stmt, ast.While):
			self._emit_line('while (' + self._expr_to_c(stmt.test) + ') {')
			self.indent += 1
			for inner in list(stmt.body or []):
				self._emit_stmt(inner)
			self.indent -= 1
			self._emit_line('}')
			return
		if isinstance(stmt, ast.Break):
			self._emit_line('break;')
			return
		if isinstance(stmt, ast.Continue):
			self._emit_line('continue;')
			return
		if isinstance(stmt, ast.Return):
			if stmt.value is None:
				self._emit_line('return 0;')
			else:
				self._emit_line('return ' + self._expr_to_c(stmt.value) + ';')
			return
		if isinstance(stmt, ast.FunctionDef):
			self._disallow_node(stmt, 'nested FunctionDef')
		self._disallow_node(stmt, type(stmt).__name__)

	def _emit_function_def (self, fn_node: ast.FunctionDef):
		fn_name = self._safe_ident(fn_node.name)
		params = ['int32_t ' + self._safe_ident(a.arg) for a in list(getattr(fn_node.args, 'args', []) or [])]
		self._emit_line('int32_t ' + fn_name + ' (' + ', '.join(params) + ') {')
		self.indent += 1
		inner_locals: Set[str] = set()
		for inner in list(getattr(fn_node, 'body', []) or []):
			if isinstance(inner, ast.Assign):
				for t in list(inner.targets or []):
					if isinstance(t, (ast.Name, ast.Attribute)):
						if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == 'this':
							continue
						inner_locals.add(self._target_to_c_lvalue(t))
			elif isinstance(inner, ast.AugAssign):
				if isinstance(inner.target, (ast.Name, ast.Attribute)):
					if isinstance(inner.target, ast.Attribute) and isinstance(inner.target.value, ast.Name) and inner.target.value.id == 'this':
						continue
					inner_locals.add(self._target_to_c_lvalue(inner.target))
		for name in sorted(list(inner_locals)):
			if name in [self._safe_ident(a.arg) for a in list(getattr(fn_node.args, 'args', []) or [])]:
				continue
			self._emit_line('int32_t ' + name + ' = 0;')
		if inner_locals != set():
			self._emit_line('')
		for inner in list(getattr(fn_node, 'body', []) or []):
			if isinstance(inner, ast.FunctionDef):
				self._disallow_node(inner, 'nested FunctionDef')
			self._emit_stmt(inner)
		self._emit_line('return 0;')
		self.indent -= 1
		self._emit_line('}')

	def transpile (self) -> GbcCFunctionCompileResult:
		self._validate_tree()
		body = list(getattr(self.tree, 'body', []) or [])
		top_level_fn_defs = [s for s in body if isinstance(s, ast.FunctionDef)]
		top_level_stmts = [s for s in body if not isinstance(s, ast.FunctionDef)]
		self._collect_local_symbols(top_level_stmts)
		self.lines = []
		for fn in top_level_fn_defs:
			self._emit_function_def(fn)
			self._emit_line('')
		self._emit_line('int32_t ' + self._safe_ident(self.function_name) + ' (void) {')
		self.indent += 1
		for sym in sorted(list(self.local_symbols)):
			if sym == self._safe_ident(self.function_name):
				continue
			if sym == self.this_var_name:
				continue
			decl_t = str(self.local_symbol_types.get(sym, 'int32_t'))
			if decl_t == 'int32_t*':
				self._emit_line('int32_t *' + sym + ' = 0;')
			elif decl_t == 'const char*':
				self._emit_line('const char *' + sym + ' = 0;')
			else:
				self._emit_line('int32_t ' + sym + ' = 0;')
		if self.local_symbols != set():
			self._emit_line('')
		for stmt in top_level_stmts:
			self._emit_stmt(stmt)
		self._emit_line('return 0;')
		self.indent -= 1
		self._emit_line('}')
		return GbcCFunctionCompileResult(
			c_source = '\n'.join(self.lines) + '\n',
			diagnostics = [
				'C subset transpiler: statements=' + str(len(body)),
				'C subset transpiler: locals=' + str(len(self.local_symbols)),
			],
		)


def compile_script_to_c_function (
	code: str,
	function_name: str = 'gbc_script_fn',
	this_var_name: str = 'js13k_this',
) -> GbcCFunctionCompileResult:
	transpiler = _GeneralCFunctionTranspiler(
		code = str(code or ''),
		function_name = str(function_name or 'gbc_script_fn'),
		this_var_name = str(this_var_name or 'js13k_this'),
	)
	return transpiler.transpile()
