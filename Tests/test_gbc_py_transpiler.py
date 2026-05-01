import unittest

from GbcPyTranspiler import GbcTranspileError, compile_general_script, compile_script_to_c_function, compile_velocity_script


class GbcPyTranspilerTests(unittest.TestCase):
	def test_general_aot_compiles_init_and_update_entries(self):
		code = """
counter = 0
def init():
    counter = 1
def update():
    if counter < 10:
        counter += 1
"""
		result = compile_general_script(code, base_addr = 0x150, symbol_prefix = "unit")
		self.assertGreater(len(result.asm_bytes), 0)
		self.assertIsInstance(result.symbol_map, dict)
		self.assertTrue("__entry_init" in result.symbol_map)
		self.assertTrue("__entry_update" in result.symbol_map)
		self.assertIsInstance(result.init_offset, int)
		self.assertIsInstance(result.update_offset, int)

	def test_general_aot_rejects_imports(self):
		with self.assertRaises(GbcTranspileError):
			compile_general_script("import os\nx = 1\n")

	def test_general_aot_supports_while_break_continue(self):
		code = """
x = 0
def update():
    while x < 8:
        x += 1
        if x == 3:
            continue
        if x > 6:
            break
"""
		result = compile_general_script(code, base_addr = 0x150, symbol_prefix = "flow")
		self.assertGreater(len(result.asm_bytes), 0)
		self.assertTrue(any("while_" in row or "if_" in row for row in result.asm_listing))

	def test_edge_trigger_jump_is_extracted(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= 60
if keys[pygame.K_RIGHT]:
    vel[0] += 60
jumpInput = keys[pygame.K_A]
if jumpInput:
    if not this.prevJumpInput:
        vel[1] = 60
elif this.prevJumpInput and vel[1] > 0:
    vel[1] = 0
this.prevJumpInput = jumpInput
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			script_name = 'Player',
		)
		self.assertIsInstance(result.velocity_script, dict)
		self.assertEqual(result.velocity_script.get('left_delta'), -60)
		self.assertEqual(result.velocity_script.get('right_delta'), 60)
		self.assertEqual(result.velocity_script.get('jump_y'), 60)
		self.assertTrue(bool(result.velocity_script.get('jump_release_cut', False)))
		self.assertTrue(bool(result.velocity_script.get('jump_edge_trigger', False)))
		self.assertGreater(len(result.asm_bytes), 0)
		self.assertTrue(any('ret' in row for row in result.asm_listing))

	def test_imports_are_rejected(self):
		with self.assertRaises(GbcTranspileError):
			compile_velocity_script(
				"import os\nsim.set_linear_velocity(this.rb, [0, 0])\n",
				target_keys = ['Player'],
				allow_this_id = True,
			)

	def test_non_matching_target_returns_no_profile(self):
		code = "sim.set_linear_velocity(get_rigidbody('Enemy'), [3, 4])"
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = False,
		)
		self.assertIsNone(result.velocity_script)
		self.assertIsNone(result.init_velocity)

	def test_lowering_snapshot_is_stable(self):
		code = """
x = 3
if keys[pygame.K_A]:
    y = 7
sim.set_linear_velocity(this.rb, [0, 0])
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
		)
		# The lowering intentionally ends with a fixed epilogue.
		self.assertTrue(result.asm_listing[-1].strip() == 'ret')
		self.assertEqual(result.asm_bytes[-1], 0xC9)

	def test_strict_mode_rejects_lambda(self):
		with self.assertRaises(GbcTranspileError):
			compile_velocity_script(
				"x = (lambda a: a + 1)(3)\nsim.set_linear_velocity(this.rb, [0, 0])\n",
				target_keys = ['Player'],
				allow_this_id = True,
				strict_compiler_mode = True,
			)

	def test_codegen_emits_symbol_map_and_diagnostics(self):
		code = """
x = 1
y = x + 2
if y == 3:
    y = y + 1
sim.set_linear_velocity(this.rb, [0, 0])
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			strict_compiler_mode = True,
		)
		self.assertIsInstance(result.symbol_map, dict)
		self.assertTrue('entry' in result.symbol_map)
		self.assertTrue(any('Compiler spec=' in d for d in result.diagnostics))

	def test_chained_compare_lowers(self):
		code = """
x = 2
if 1 < x < 3:
    x = x + 1
sim.set_linear_velocity(this.rb, [0, 0])
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			strict_compiler_mode = True,
		)
		self.assertGreater(len(result.asm_bytes), 0)
		self.assertTrue(any('if_else_' in row or 'if_end_' in row for row in result.asm_listing))

	def test_edge_trigger_detects_rewritten_prev_jump_local(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= 60
if keys[pygame.K_RIGHT]:
    vel[0] += 60
jumpInput = keys[pygame.K_A]
if jumpInput:
    if not prevJumpInput:
        vel[1] = 60
elif prevJumpInput and vel[1] > 0:
    vel[1] = 0
prevJumpInput = jumpInput
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			strict_compiler_mode = True,
		)
		self.assertTrue(bool(result.velocity_script.get('jump_edge_trigger', False)))
		self.assertTrue(bool(result.velocity_script.get('jump_release_cut', False)))

	def test_edge_trigger_detects_namespaced_prev_jump_local(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
jumpInput = keys[pygame.K_A]
if jumpInput:
    if not Player_prevJumpInput:
        vel[1] = 60
elif Player_prevJumpInput and vel[1] > 0:
    vel[1] = 0
Player_prevJumpInput = jumpInput
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			strict_compiler_mode = True,
		)
		self.assertTrue(bool(result.velocity_script.get('jump_edge_trigger', False)))

	def test_dynamic_this_speed_terms_are_rejected_for_velocity_profile(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= this.moveSpeed
if keys[pygame.K_RIGHT]:
    vel[0] += this.moveSpeed
jumpInput = keys[pygame.K_A]
if jumpInput:
    if not this.prevJumpInput:
        vel[1] = this.jumpSpeed
elif this.prevJumpInput and vel[1] > 0:
    vel[1] = 0
this.prevJumpInput = jumpInput
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
		)
		self.assertIsNone(result.velocity_script)
		self.assertTrue(any('unresolved non-constant terms' in d for d in result.diagnostics))

	def test_dynamic_this_speed_terms_resolve_with_symbol_constants(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= this.moveSpeed
if keys[pygame.K_RIGHT]:
    vel[0] += this.moveSpeed
jumpInput = keys[pygame.K_A]
if jumpInput:
    if not this.prevJumpInput:
        vel[1] = this.jumpSpeed
elif this.prevJumpInput and vel[1] > 0:
    vel[1] = 0
this.prevJumpInput = jumpInput
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
			symbol_constants = {'this.moveSpeed': 42, 'this.jumpSpeed': 77},
		)
		self.assertIsInstance(result.velocity_script, dict)
		self.assertEqual(result.velocity_script.get('left_delta'), -42)
		self.assertEqual(result.velocity_script.get('right_delta'), 42)
		self.assertEqual(result.velocity_script.get('jump_y'), 77)

	def test_set_rigid_body_velocity_alias_is_supported(self):
		code = """
vel = [0, sim.get_linear_velocity(this.rb)[1]]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= 12
if keys[pygame.K_RIGHT]:
    vel[0] += 12
if keys[pygame.K_A]:
    vel[1] = 33
sim.set_rigid_body_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
		)
		self.assertIsInstance(result.velocity_script, dict)
		self.assertEqual(result.velocity_script.get('left_delta'), -12)
		self.assertEqual(result.velocity_script.get('right_delta'), 12)
		self.assertEqual(result.velocity_script.get('jump_y'), 33)

	def test_vertical_directional_deltas_are_extracted(self):
		code = """
vel = [0, 0]
keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    vel[0] -= 70
if keys[pygame.K_RIGHT]:
    vel[0] += 70
if keys[pygame.K_DOWN]:
    vel[1] -= 70
if keys[pygame.K_UP]:
    vel[1] += 70
sim.set_linear_velocity(this.rb, vel)
"""
		result = compile_velocity_script(
			code,
			target_keys = ['Player'],
			allow_this_id = True,
		)
		self.assertIsInstance(result.velocity_script, dict)
		self.assertEqual(result.velocity_script.get('left_delta'), -70)
		self.assertEqual(result.velocity_script.get('right_delta'), 70)
		self.assertEqual(result.velocity_script.get('down_delta'), -70)
		self.assertEqual(result.velocity_script.get('up_delta'), 70)

	def test_neogeo_c_transpile_appends_zero_attach_for_sim_add_cuboid_collider(self):
		code = 'sim.add_cuboid_collider(1, [0, 0], 0, 1, 1, [10, 10], 0, 1, 0, 0)'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'th')
		self.assertIn('sim_add_cuboid_collider(1, ((int32_t[]){0, 0}), 0, 1, 1, ((int32_t[]){10, 10}), 0, 1, 0, 0, 0)', out.c_source)

	def test_neogeo_c_transpile_set_gravity_uses_milli(self):
		code = 'sim.set_gravity(0, -0.4)'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'th')
		self.assertIn('sim_set_gravity_milli(0, -400)', out.c_source)

	def test_neogeo_c_transpile_physics_set_gravity_uses_milli(self):
		code = 'physics.set_gravity(0, -9.81)'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'th')
		self.assertIn('sim_set_gravity_milli(0, -9810)', out.c_source)

	def test_neogeo_c_transpile_get_rigid_body_position_declares_int32_ptr(self):
		code = 'pos = sim.get_rigid_body_position(this.rb)\nsim.step()'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'js13k_this_Player')
		self.assertIn('int32_t *pos = 0;', out.c_source)
		self.assertIn('pos = sim_get_rigid_body_position(js13k_this_Player->rb);', out.c_source)

	def test_neogeo_print_style_emits_stdio_helpers(self):
		code = 'print(1, 2)\nprint("hi")\nprint()'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'th', print_style = 'neo')
		self.assertIn('js13k_print_i(1)', out.c_source)
		self.assertIn('js13k_print_sep()', out.c_source)
		self.assertIn('js13k_print_i(2)', out.c_source)
		self.assertIn('js13k_print_s("hi")', out.c_source)
		self.assertIn('(js13k_print_end(), (int32_t)0)', out.c_source)

	def test_neogeo_print_iv2_for_position_vector_local(self):
		code = (
			'pos = sim.get_rigid_body_position(this.rb)\n'
			'print(this.rb, pos)\n'
		)
		out = compile_script_to_c_function(
			code,
			function_name = 'fn',
			this_var_name = 'js13k_this_Player',
			print_style = 'neo',
		)
		self.assertIn('js13k_print_i(js13k_this_Player->rb)', out.c_source)
		self.assertIn('js13k_print_iv2(pos)', out.c_source)

	def test_legacy_print_style_keeps_js13k_print(self):
		code = 'print(42)'
		out = compile_script_to_c_function(code, function_name = 'fn', this_var_name = 'th')
		self.assertIn('js13k_print(42);', out.c_source)


if __name__ == '__main__':
	unittest.main()
