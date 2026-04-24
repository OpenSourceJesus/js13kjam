import pathlib
import re
import unittest


class GbcCameraScrollRegressionTests(unittest.TestCase):
	def _read_main_py(self):
		root = pathlib.Path(__file__).resolve().parents[1]
		return (root / 'Main.py').read_text(encoding = 'utf-8')

	def test_runtime_set_camera_position_does_not_modulo_wrap(self):
		src = self._read_main_py()
		match = re.search(
			r'def set_camera_position \(x, y\):\n(?P<body>.*?)(?:\n\ndef |\nclass |\Z)',
			src,
			flags = re.DOTALL,
		)
		self.assertIsNotNone(match, 'Expected runtime set_camera_position() in Main.py')
		body = str(match.group('body'))
		self.assertNotIn('% 65536', body)
		self.assertNotIn('& 0xFFFF', body)

	def test_scx_scy_writes_use_clamped_i16_helper(self):
		src = self._read_main_py()
		self.assertGreaterEqual(src.count('def _emit_hw_scroll_from_i16_clamped'), 2)
		self.assertIn('_emit_hw_scroll_from_i16_clamped(scroll_x_addr, scroll_x_hi_addr, 0x43)', src)
		self.assertIn('_emit_hw_scroll_from_i16_clamped(scroll_y_addr, scroll_y_hi_addr, 0x42)', src)

	def test_phase1_print_colliders_do_not_apply_camera_scroll(self):
		src = self._read_main_py()
		self.assertIn('scroll_x_gba = 0.0', src)
		self.assertIn('scroll_y_gba = 0.0', src)
		self.assertIn('Camera scroll is already represented by script_world_offset', src)

	def test_phase1_print_env_uses_runtime_collision_box(self):
		src = self._read_main_py()
		self.assertIn("'collision_w_px' : int(collision_w_px)", src)
		self.assertIn("'collision_h_px' : int(collision_h_px)", src)
		self.assertIn("'collision_off_x_px' : int(collision_off_x_px)", src)
		self.assertIn("'collision_off_y_px' : int(collision_off_y_px)", src)
		self.assertIn('collision_w_px = int(_player_spec.get(\'collision_w_px\'', src)
		self.assertIn('collision_h_px = int(_player_spec.get(\'collision_h_px\'', src)

	def test_phase1_get_rigid_body_position_prefers_live_object_pose(self):
		src = self._read_main_py()
		self.assertIn('_get_pos = _g.get(\'get_object_position\', None)', src)
		self.assertIn('_p = _get_pos(_name)', src)
		self.assertIn('def _nonzero_or_none (_p):', src)
		self.assertIn('_nz = _nonzero_or_none(_p)', src)
		self.assertIn('Phase1GetRbPos:src=live', src)
		self.assertIn('Phase1GetRbPos:src=fallback', src)

	def test_camera_ops_keep_runtime_print_env(self):
		src = self._read_main_py()
		self.assertIn("if camera_ops_present:", src)
		self.assertIn("'[gbc-trace] BuildGbc:phase1_print_env_active=0'", src)
		self.assertIn("reason=camera_ops_present", src)
		self.assertIn('def _is_dead_runtime_rb (_h):', src)
		self.assertIn('def _runtime_rb_unusable (_rb, _rb_ids, _rb_named, _owner_name):', src)
		self.assertIn("BuildGbc:phase1_print_env_fallback=1", src)
		self.assertIn("reason=runtime_rb_unusable", src)

	def test_camera_ops_runtime_env_does_not_force_signed_position_shim(self):
		src = self._read_main_py()
		self.assertIn('use_gbc_signed_positions = (not bool(camera_ops_present))', src)

	def test_injected_sim_getters_use_safe_unbias_heuristic(self):
		src = self._read_main_py()
		self.assertIn('if (sim is not None) and hasattr(sim, "get_rigid_body_position")', src)
		self.assertIn('if (sim is not None) and hasattr(sim, "get_collider_position")', src)
		self.assertIn('if x < -_half:', src)
		self.assertIn('elif x > _half:', src)
		self.assertIn('if y < -_half:', src)
		self.assertIn('elif y > _half:', src)

	def test_runtime_print_env_wraps_getters_with_normalizer(self):
		src = self._read_main_py()
		self.assertIn('def _wrap_script_pos_normalize (_fn):', src)
		self.assertIn("RuntimeGetPosNormalize:raw=", src)
		self.assertIn("sim._gbc_script_pos_norm_rb_wrapped = True", src)
		self.assertIn("sim._gbc_script_pos_norm_col_wrapped = True", src)

	def test_mirror_eval_uses_sim_proxy_with_position_normalizer(self):
		src = self._read_main_py()
		self.assertIn('class _MirrorScriptSimProxy:', src)
		self.assertIn('MirrorSimPosNormalize:kind=', src)
		self.assertIn("env['sim'] = _sim_obj", src)
		self.assertIn("env['physics'] = _sim_obj", src)

	def test_mirror_this_col_uses_fuzzy_collider_lookup(self):
		src = self._read_main_py()
		self.assertIn("this_obj.col = _resolve_script_lookup_from_sources(", src)
		self.assertIn("if isinstance(_entry, dict) and _entry.get('col', None) is not None:", src)
		self.assertIn("getattr(env.get('sim', None), 'named_colliders', {})", src)
		self.assertIn("if env.get('col', None) is None:", src)
		self.assertIn("env['col'] = _owner_txt", src)
		self.assertIn("this_obj.col = getattr(this_obj, 'rb', None)", src)

	def test_runtime_print_text_applies_final_position_normalization(self):
		src = self._read_main_py()
		self.assertIn('RuntimePrintTextNormalize:raw=', src)
		self.assertIn('text = _normalize_runtime_print_text(text)', src)
		self.assertIn('if isinstance(val, (list, tuple)) and len(val) >= 2:', src)

	def test_mirror_runtime_print_normalizes_position_args(self):
		src = self._read_main_py()
		self.assertIn('def _norm_print_arg (_v):', src)
		self.assertIn('MirrorRuntimePrintNormalize:raw=', src)
		self.assertIn('args = tuple(_norm_print_arg(_a) for _a in list(args or []))', src)
		self.assertIn('kind=str', src)

	def test_runtime_print_text_normalizes_coordinate_substrings(self):
		src = self._read_main_py()
		self.assertIn('pos=[-32678.0, -32728.0]', src)
		self.assertIn('_gbc_print_text_norm_sub_trace_count', src)
		self.assertIn('out_txt = re.sub(', src)

	def test_js13k_call_print_path_is_instrumented_and_normalized(self):
		src = self._read_main_py()
		self.assertIn('def _norm_call_print_arg (_v):', src)
		self.assertIn('Js13kCallPrintNormalize:raw=', src)
		self.assertIn('Js13kCallPrintDispatch', src)
		self.assertIn('Js13kCallPrintNormalizeFail', src)
		self.assertIn('_bias = 32768.0', src)
		self.assertIn('_half = _bias * 0.5', src)
		self.assertIn("',err=' + repr(str(_norm_err))", src)
		self.assertIn('Js13kCallPrintOwnerFallback', src)
		self.assertIn('Js13kCallPrintOwnerDynamic', src)
		self.assertIn('Js13kCallPrintOwnerIntegrated', src)
		self.assertIn('_gbc_js13k_call_print_pose_state', src)
		self.assertIn('_live = _js13k_call_get_object_position(owner)', src)
		self.assertIn("for _rb_map in (", src)
		self.assertIn("_v_env = env.get('vel', None)", src)
		self.assertIn("_vel_src = 'none'", src)
		self.assertIn(",vel_src=' + str(_vel_src)", src)
		self.assertIn("_vel = [float(_v_env[0]), float(_v_env[1])]", src)
		self.assertIn("_vel_src = 'env.vel'", src)
		self.assertIn('def _js13k_call_print (*args, sep = \' \', end = \'\\n\', file = None, flush = False):', src)
		self.assertIn('if (_col_hit is None) and _is_zero_pair(_args[2]):', src)
		self.assertIn('_live = sim.get_rigid_body_position(_rb)', src)
		self.assertIn('def _resolve_rb_handle(self, rigidBody):', src)
		self.assertIn('rigidBody = self._resolve_rb_handle(rigidBody)', src)
		self.assertIn('if rigidBody is None:', src)
		self.assertIn('return [0.0, 0.0]', src)
		self.assertIn('def _live_owner_pos (_rb_hint = None):', src)
		self.assertIn('_rb_cands.extend([(0, 0), [0, 0], str(owner)])', src)
		self.assertIn("_xg = getattr(_sim_cand, 'x', None)", src)
		self.assertIn("_cache = _g.get('_gbc_last_phase1_rb_pos', None)", src)
		self.assertIn('Js13kCallPrintDirectPosRepair', src)
		self.assertIn('Js13kCallPrintZeroPosRepair', src)

	def test_position_normalizer_uses_bias_fallback_when_constant_missing(self):
		src = self._read_main_py()
		self.assertIn("bias = float(globals().get('_GBC_POSITION_BIAS', 32768.0))", src)
		self.assertIn('half_bias = float(bias) * 0.5', src)


if __name__ == '__main__':
	unittest.main()
