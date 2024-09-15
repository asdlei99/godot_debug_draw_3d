#pragma once

#include "utils/compiler.h"

GODOT_WARNING_DISABLE()
#include <godot_cpp/classes/node.hpp>
GODOT_WARNING_RESTORE()
using namespace godot;

class DD3DTestCppApiNode : public Node {
	GDCLASS(DD3DTestCppApiNode, Node)
protected:
	static void _bind_methods();

public:
	DD3DTestCppApiNode();
	virtual void _ready() override;
	virtual void _process(double p_delta) override;
};
