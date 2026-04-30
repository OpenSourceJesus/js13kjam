import pathlib
import unittest


class GbcPureZgbRuntimeRegressionTests(unittest.TestCase):
	def _read_main_py(self):
		root = pathlib.Path(__file__).resolve().parents[1]
		return (root / 'Main.py').read_text(encoding = 'utf-8')

	def test_buildgbc_defaults_to_pure_zgb_runtime(self):
		src = self._read_main_py()
		self.assertIn('_GBC_PURE_ZGB_RUNTIME = str(', src)
		self.assertIn("os.environ.get('JS13K_GBC_PURE_ZGB_RUNTIME', '1')", src)
		self.assertIn('BuildGbc:pure_zgb_runtime=1', src)
		self.assertIn('BuildGbc:phase1_runtime_bypassed=1', src)

	def test_generated_zgb_runtime_uses_sprite_manager_and_zgb_physics_fields(self):
		src = self._read_main_py()
		self.assertIn('SpriteManagerAdd(', src)
		self.assertIn('} SPRITES;', src)
		self.assertIn('js13k_runtime_vel_x', src)
		self.assertIn('js13k_runtime_vel_y', src)
		self.assertIn('GRAVITY', src)
		self.assertIn('sim_set_linear_velocity', src)
		self.assertIn('sim_get_linear_velocity', src)

	def test_generated_runtime_uses_joypad_bits(self):
		src = self._read_main_py()
		self.assertIn('UINT8 keys = joypad();', src)
		self.assertIn('(keys & J_LEFT)', src)
		self.assertIn('(keys & J_A)', src)

	def test_owner_start_binds_runtime_handles(self):
		src = self._read_main_py()
		self.assertIn('->rb = ', src)
		self.assertIn('->col = ', src)

	def test_phase1_dynamic_rom_builder_not_selected_in_pure_runtime(self):
		src = self._read_main_py()
		self.assertIn('if has_physics and bool(_GBC_PURE_ZGB_RUNTIME):', src)
		self.assertIn('has_physics = False', src)
		self.assertIn('_gbc_build_dynamic_physics_rom(', src)
		self.assertIn('_gbc_build_dynamic_physics_rom_multi(', src)

	def test_neogeo_export_is_wired_into_world_properties_and_ui(self):
		src = self._read_main_py()
		self.assertIn("('neogeo', 'neogeo', '')", src)
		self.assertIn("('neogeo-py', 'neogeo-py'", src)
		self.assertIn("bpy.types.World.neoGeoPath = bpy.props.StringProperty(name = 'Export .neo'", src)
		self.assertIn("bl_idname = 'world.neogeo_export'", src)
		self.assertIn("BuildNeoGeo (ctx.world)", src)
		self.assertIn('Neo Geo export: runtime transpiler backend is placeholder/stub or missing update symbols;', src)
		self.assertIn('using baked frame fallback.', src)

	def test_transpiler_auto_rewrites_pygame_keys_to_joypad(self):
		root = pathlib.Path(__file__).resolve().parents[1]
		src = (root / 'GbcPyTranspiler.py').read_text(encoding = 'utf-8')
		self.assertIn('_JOY_TO_PYGAME_KEY', src)
		self.assertIn('_PYGAME_TO_JOY_KEY', src)
		self.assertIn('return _PYGAME_TO_JOY_KEY.get(str(expr.attr)', src)
		self.assertIn("return 'joypad()'", src)
		self.assertIn("if isinstance(expr.op, ast.BitAnd):", src)


if __name__ == '__main__':
	unittest.main()
