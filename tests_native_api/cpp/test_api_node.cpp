#include "test_api_node.h"

#include "../addons/debug_draw_3d/native_api/cpp/dd3d_cpp_api.hpp"
#include "../src/utils/compiler.h"

GODOT_WARNING_DISABLE()
#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/classes/random_number_generator.hpp>
#include <godot_cpp/classes/time.hpp>
#include <godot_cpp/variant/utility_functions.hpp>
GODOT_WARNING_RESTORE()
using namespace godot;

void DD3DTestCppApiNode::_bind_methods() {
}

DD3DTestCppApiNode::DD3DTestCppApiNode() {
}

void DD3DTestCppApiNode::_ready() {
}

float timer_cubes = 0;
void DD3DTestCppApiNode::_process(double p_delta) {
	DebugDraw3D::draw_sphere(Vector3(1, 1, 1), 2, Color(1, 1, 0), 0);

	// Lots of boxes to check performance..
	int x_size = 50;
	int y_size = 50;
	int z_size = 3;
	float mul = 1;
	float cubes_max_time = 1.25;
	// auto cfg = DebugDraw3D::new_scoped_config();

	if (true) {
		x_size = 100;
		y_size = 100;
		z_size = 100;
		mul = 4;
		cubes_max_time = 60;
	}

	if (timer_cubes < 0) {
		uint64_t _start_time = Time::get_singleton()->get_ticks_usec();
		Ref<RandomNumberGenerator> rng;
		rng.instantiate();
		for (int x = 0; x < x_size; x++)
			for (int y = 0; y < y_size; y++)
				for (int z = 0; z < z_size; z++) {
					Vector3 size = Vector3(1, 1, 1);
					// cfg.set_thickness(rng->randf_range(0, 0.1));
					// var size = Vector3(randf_range(0.1, 100), randf_range(0.1, 100), randf_range(0.1, 100))
					DebugDraw3D::draw_box(Vector3(x * mul, (-4 - z) * mul, y * mul), Quaternion(), size, Color(0, 0, 0, 0), false, cubes_max_time);
				}
		UtilityFunctions::print("Draw Cubes C++: ", (Time::get_singleton()->get_ticks_usec() - _start_time) / 1000.0, "ms");
		timer_cubes = cubes_max_time;
	}

	timer_cubes -= p_delta;
}
