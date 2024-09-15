#!/usr/bin/env python3

from SCons.Script.SConscript import SConsEnvironment
from patches import unity_tools

import SCons
import os, shutil, json, re, hashlib
import lib_utils

def insert_lines_at_mark(lines: list, mark: str, insert_lines: list):
    insert_mark = mark
    insert_index = -1
    for idx, line in enumerate(lines):
        if line.endswith(mark):
            insert_index = idx
            break
    lines.pop(insert_index)
    lines[insert_index:insert_index] = insert_lines


def get_api_functions(headers: list) -> dict:
    classes = {}

    for header in headers:
        print(header)
        text_data = lib_utils.read_all_text(header)
        lines = text_data.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines = [line.strip() for line in lines if len(line.strip())]

        functions = {}
        current_class = ""

        is_singleton = False
        is_refcounted = False

        for idx, line in enumerate(lines):
            docs = []
            if lines[idx - 1] == "*/":
                doc_idx = idx - 1
                while lines[doc_idx] != "/**":
                    doc_idx -= 1
                docs = [line.replace("*", "", 1).strip() if line.startswith("*") else line for line in lines[doc_idx+1:idx-1]]
            
            class_prefixes = ["NAPI_CLASS ", "NAPI_CLASS_SINGLETON ", "NAPI_CLASS_REF "]
            class_prefix = ""
            for p in class_prefixes:
                if line.startswith(p):
                    class_prefix = p
                    break
            if len(class_prefix):
                is_singleton = line.startswith("NAPI_CLASS_SINGLETON ")
                is_refcounted = line.startswith("NAPI_CLASS_REF ")
                current_class = re.search(r"\w+", line[len(class_prefix):])[0].strip()

                functions = {}
                classes[current_class] = {"functions": functions, "singleton": is_singleton, "refcounted": is_refcounted, "docs": docs}
                continue

            if line.startswith("NAPI "):
                func_name_match = re.search(r'\b(\w+)\s*\(', line)
                fun_name = func_name_match.group(1).strip()
                ret_type = line[:line.index(fun_name)].replace("NAPI ","").strip()

                is_self_return = False
                if is_refcounted:
                    if ret_type == f"Ref<{current_class}>":
                        ret_type = "void"
                        is_self_return = True

                args_str = line[line.find("(") + 1 : line.rfind(")")]
                args = []

                if not is_singleton:
                    args.append("void *inst")

                if len(args_str):
                    #args = [a.strip() for a in args]
                    tmp_args_str = args_str
                    while len(tmp_args_str):
                        found_comma = False
                        nesting = 0
                        for idx, c in enumerate(tmp_args_str):
                            if c in ["(", "[", "{", "<"]:
                                nesting += 1
                            if c in [")", "]", "}", ">"]:
                                nesting -= 1
                            if nesting == 0 and c == ",":
                                args.append(tmp_args_str[:idx].strip())
                                tmp_args_str = tmp_args_str[idx + 1:]
                                found_comma = True
                                break
                            if nesting < 0:
                                raise Exception("There are more closing brackets than opening ones:\n" + tmp_args_str)
                        if nesting > 0:
                            raise Exception("There are more opening brackets than closing ones:\n" + tmp_args_str)
                        
                        if not found_comma:
                            args.append(tmp_args_str)
                            break

                args_dict = []
                for a in args:
                    arg_name_match = re.search(r'\b(\w+)\s*=', a)
                    if arg_name_match:
                        new_dict = {
                                "name": arg_name_match.group(1).strip(),
                                "type": a[:a.index(arg_name_match.group(1))].strip(),
                                "default": a[a.find("=") + 1:].strip()
                            }
                        new_dict["c_type"] = new_dict["type"].replace("&", "").strip()
                        args_dict.append(new_dict)
                    else:
                        arg_name_match = re.search(r'\b(\w+)$', a)
                        new_dict = {
                                "name": arg_name_match.group(1).strip(),
                                "type": a[:a.index(arg_name_match.group(1))].strip()
                            }
                        new_dict["c_type"] = new_dict["type"].replace("&", "").strip()
                        args_dict.append(new_dict)

                fun_dict = {"return": ret_type, "self_return": is_self_return, "args": args_dict, "name": fun_name, "docs": docs}
                functions[f"{current_class}_{fun_name}"] = fun_dict
    return classes


def generate_native_api(c_api_template: str, out_folder: str, src_out: list) -> dict:
    classes = get_api_functions([
        "src/3d/config_scope_3d.h",
        "src/3d/debug_draw_3d.h"
    ])

    new_funcs = []
    new_func_regs = []
    for cls in classes:
        is_singleton = classes[cls]["singleton"]
        is_refcounted = classes[cls]["refcounted"]
        functions = classes[cls]["functions"]
        for func_name in functions:
            func = functions[func_name]
            func_orig_name = func["name"]
            ret_type = func["return"]

            if is_refcounted:
                if ret_type == "self":
                    ret_type = "void"
            args = func["args"]

            new_funcs.append(f"{ret_type} {func_name}({", ".join([f"{a["type"]} {a["name"]}" for a in args])}) {{")
            if is_singleton:
                if ret_type != "void":
                    new_funcs.append(f"\treturn {cls}::get_singleton()->{func_orig_name}({", ".join([a["name"] for a in args])});")
                else:
                    new_funcs.append(f"\t{cls}::get_singleton()->{func_orig_name}({", ".join([a["name"] for a in args])});")
            new_funcs.append(f"}}")
            new_funcs.append("")

            new_func_regs.append(f"\t\tADD_FUNC({func_name});")

    c_api_temp_data = lib_utils.read_all_text(c_api_template)
    c_api_lines = c_api_temp_data.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    insert_lines_at_mark(c_api_lines, "// GENERATOR_DD3D_FUNCTIONS_DEFINES", new_funcs)
    insert_lines_at_mark(c_api_lines, "// GENERATOR_DD3D_FUNCTIONS_REGISTERS", new_func_regs)
    c_api_file_name, c_api_file_ext = os.path.splitext(os.path.basename(c_api_template))

    c_api_gen_path = os.path.join("gen", f"{c_api_file_name}.gen{c_api_file_ext}")
    lib_utils.write_all_text(os.path.join("src", c_api_gen_path), "\n".join(c_api_lines))
    src_out.append(c_api_gen_path)

    api_dict = {"hash": hashlib.sha1(json.dumps(classes, sort_keys=True).encode()).hexdigest(), "classes": classes}
    lib_utils.write_all_text(os.path.join(out_folder, "api.json"), json.dumps(api_dict, indent="  "))

    return api_dict


def gen_cpp_api(env: SConsEnvironment, api: dict, out_folder: str, additional_include_classes: list = []) -> bool:
    os.makedirs(out_folder, exist_ok=True)
    classes = api["classes"]
    namespaces = {}

    for cls in classes:
        functions = classes[cls]["functions"]

        for func_name in functions:
            func: dict = functions[func_name]
            func_orig_name = func["name"]
            ret = func["return"]
            args = func["args"]

            if cls not in namespaces:
                namespaces[cls] = []

            def get_default_ret_val(ret_type: str):
                if ret_type.endswith("*") or ret_type.startswith("Ref<"):
                    return "nullptr"

                return "{}"

            docs = func["docs"]
            if len(docs):
                docs = [" * " + line for line in docs]
                docs.insert(0, "/**")
                docs.insert(len(docs), " */")

            new_lines = docs
            new_lines.append(f"static {ret} {func_orig_name}({", ".join([f"{a["type"]} {a["name"]}" for a in args])}) {{")
            new_lines.append(f"\tstatic {ret}(*{func_name})({", ".join([a["type"] for a in args])}) = nullptr;")
            def_ret_val = get_default_ret_val(ret)
            call_args = ", ".join([a["name"] for a in args])
            if ret != "void":
                new_lines.append(f"\tLOAD_AND_CALL_FUNC_POINTER_RET({func_name}, {def_ret_val}{", " if len(args) else ""}{call_args});")
            else:
                new_lines.append(f"\tLOAD_AND_CALL_FUNC_POINTER({func_name}, {call_args});")
            new_lines.append(f"}}")
            new_lines.append("")

            namespaces[cls] += new_lines
        

    shutil.copyfile("src/native_api/c_api_shared.hpp", os.path.join(out_folder, "c_api_shared.hpp"))
    text_data = lib_utils.read_all_text("src/native_api/templates/cpp/dd3d_cpp_api.hpp")
    lines = text_data.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    result_arr = [""]
    for key in namespaces:
        docs:list = classes[key]["docs"]
        if len(docs):
            docs = [" * " + line for line in docs]
            docs.insert(0, "/**")
            docs.insert(len(docs), " */")
        result_arr = result_arr + docs
        result_arr.append(f"namespace {key} {{")
        result_arr += namespaces[key]
        result_arr.append(f"}} // namespace {key}")
        result_arr.append("")

    insert_lines_at_mark(lines, "// GENERATOR_DD3D_API_INCLUDES", [f"#include <godot_cpp/classes/{i}.hpp>" for i in additional_include_classes])
    insert_lines_at_mark(lines, "// GENERATOR_DD3D_API_FUNCTIONS", result_arr)
    return lib_utils.write_all_text(os.path.join(out_folder, "dd3d_cpp_api.hpp"), "\n".join(lines))


def gen_apis(env: SConsEnvironment, c_api_template: str, out_folder: str, src_out: list):
    print("Generating native API!")
    os.makedirs(out_folder, exist_ok=True)

    api = generate_native_api(c_api_template, out_folder, src_out)
    if api == None:
        print("Couldn't get the Native API")
        return 110

    if not gen_cpp_api(env, api, os.path.join(out_folder, "cpp"), [
        "camera3d"
    ]):
        return 111
    return 0
