# -*- coding: utf-8 -*-

import json
import os
import sys
import subprocess

print("欢迎使用 AI-Agent 安装程序")
print("正在加载程序依赖...")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENAI_VERSION = "openai==1.13.3"

DEFAULT_CONFIG = {
    "api_key": "___api-key___",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-3.5-turbo",
    "max_steps": 10,
    "temperature": 0.1
}

RUN_BAT = r'''@echo off
cd /d "%~dp0"
python main_agent.py
if errorlevel 1 pause
'''

RUN_SH = r'''#!/bin/sh
cd "$(dirname "$0")"
python3 main_agent.py
'''

MAIN_AGENT_CODE = r'''# -*- coding: utf-8 -*-

import importlib.util
import json
import os
import sys

from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SKILL_DIR = os.path.join(BASE_DIR, "skills")
DEFAULT_CONFIG = {
    "api_key": "___api-key___",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-3.5-turbo",
    "max_steps": 10,
    "temperature": 0.1
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        print("已生成 config.json，请填写 API 配置后重新运行。")
        sys.exit(0)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except Exception as e:
        print("读取 config.json 失败：{}".format(e))
        sys.exit(1)
    if not isinstance(user_config, dict):
        print("config.json 必须是 JSON 对象。")
        sys.exit(1)
    config = DEFAULT_CONFIG.copy()
    config.update(user_config)
    try:
        config["max_steps"] = max(1, int(config["max_steps"]))
        config["temperature"] = max(0.0, float(config["temperature"]))
    except Exception:
        print("config.json 配置格式错误。")
        sys.exit(1)
    for key in ("api_key", "base_url", "model_name"):
        if not config.get(key) or str(config[key]).startswith("___"):
            print("错误：请先在 config.json 中填写 {}。".format(key))
            sys.exit(1)
    return config


def load_skills():
    os.makedirs(SKILL_DIR, exist_ok=True)
    init_path = os.path.join(SKILL_DIR, "__init__.py")
    if not os.path.exists(init_path):
        open(init_path, "w", encoding="utf-8").write("# skill module\n")
    tools, tool_map = [], {}
    for filename in sorted(os.listdir(SKILL_DIR)):
        if not (filename.startswith("skill_") and filename.endswith(".py")):
            continue
        try:
            path = os.path.join(SKILL_DIR, filename)
            spec = importlib.util.spec_from_file_location(filename[:-3], path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "TOOL_DEF"):
                tools.append(module.TOOL_DEF)
            if hasattr(module, "TOOL_DEFS"):
                tools.extend(module.TOOL_DEFS)
            if hasattr(module, "TOOL_FUNC"):
                tool_map.update(module.TOOL_FUNC)
            print("已加载 Skill：{}".format(filename))
        except Exception as e:
            print("加载 Skill 失败：{}，错误：{}".format(filename, e))
    return tools, tool_map


CONFIG = load_config()
ALL_TOOLS, ALL_TOOL_MAP = load_skills()
try:
    CLIENT = OpenAI(api_key=CONFIG["api_key"], base_url=CONFIG["base_url"])
except Exception as e:
    print("创建 API 客户端失败：{}".format(e))
    sys.exit(1)

SYSTEM_PROMPT = "你是一个插件化 AI Agent。需要操作时调用工具，不需要工具时直接回答，不要编造工具返回结果。"


def run_agent(user_query):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_query}]
    for _ in range(CONFIG["max_steps"]):
        request = {"model": CONFIG["model_name"], "messages": messages, "temperature": CONFIG["temperature"]}
        if ALL_TOOLS:
            request["tools"] = ALL_TOOLS
            request["tool_choice"] = "auto"
        try:
            response = CLIENT.chat.completions.create(**request)
            if not response.choices:
                return "API 返回结果为空。"
        except Exception as e:
            return "API 调用失败：{}".format(e)
        message = response.choices[0].message
        assistant = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant["tool_calls"] = [{
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments}
            } for call in message.tool_calls]
        messages.append(assistant)
        if not message.tool_calls:
            return message.content or ""
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments)
                function = ALL_TOOL_MAP.get(call.function.name)
                result = "不存在工具：{}".format(call.function.name) if function is None else function(**args)
            except Exception as e:
                result = "工具执行失败：{}".format(e)
            if not isinstance(result, str):
                result = str(result)
            print("调用工具：{}，返回：{}".format(call.function.name, result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "达到最大思考轮数，程序终止。"


def main():
    print("===== AI Agent 启动 =====")
    print("已加载工具：{}".format(list(ALL_TOOL_MAP.keys())))
    print("输入 quit 退出。\n")
    while True:
        try:
            user_input = input("你：").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if user_input.lower() == "quit":
            break
        if user_input:
            print("\nAgent：{}\n".format(run_agent(user_input)))


if __name__ == "__main__":
    main()
'''

SKILL_CALC = r'''# -*- coding: utf-8 -*-
import ast
import operator

TOOL_DEF = {"type": "function", "function": {"name": "calculate", "description": "执行基础数学计算，例如：(12+34)*2", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}

def node(value):
    if isinstance(value, ast.Expression): return node(value.body)
    if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)): return value.value
    if isinstance(value, ast.Num): return value.n
    if isinstance(value, ast.BinOp) and type(value.op) in OPS:
        right = node(value.right)
        if isinstance(value.op, ast.Pow) and abs(right) > 100: raise ValueError("指数过大")
        return OPS[type(value.op)](node(value.left), right)
    if isinstance(value, ast.UnaryOp) and type(value.op) in OPS: return OPS[type(value.op)](node(value.operand))
    raise ValueError("表达式中包含不允许的内容")

def calculate(expression):
    try:
        if not isinstance(expression, str) or len(expression) > 200: return "计算错误：表达式无效或过长"
        return "计算结果={}".format(node(ast.parse(expression, mode="eval")))
    except Exception as e: return "计算错误：{}".format(e)

TOOL_FUNC = {"calculate": calculate}
'''

SKILL_FILE = r'''# -*- coding: utf-8 -*-
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_DEFS = [
 {"type":"function","function":{"name":"read_file","description":"读取 config.json 或 skills 目录内的文本文件","parameters":{"type":"object","properties":{"filepath":{"type":"string"}},"required":["filepath"]}}},
 {"type":"function","function":{"name":"write_file","description":"写入 config.json 或 skills 目录内的文本文件，写入前必须输入 YES","parameters":{"type":"object","properties":{"filepath":{"type":"string"},"content":{"type":"string"}},"required":["filepath","content"]}}}
]

def safe_path(filepath):
    if not isinstance(filepath, str) or not filepath.strip(): raise ValueError("文件路径无效")
    base = os.path.abspath(BASE_DIR)
    full = os.path.abspath(os.path.join(BASE_DIR, filepath.replace("/", os.sep)))
    if not (full == base or full.startswith(base + os.sep)): raise ValueError("禁止访问项目目录之外的文件")
    return full

def rel(full): return os.path.relpath(full, BASE_DIR).replace(os.sep, "/")
def allowed(path): return path.lower() == "config.json" or path.lower().startswith("skills/")

def read_file(filepath):
    try:
        full = safe_path(filepath); path = rel(full)
        if not allowed(path): return "只允许读取 config.json 或 skills 目录内的文件"
        if not os.path.isfile(full): return "文件不存在：{}".format(filepath)
        with open(full, "r", encoding="utf-8") as f: return f.read(5000)
    except Exception as e: return "读取失败：{}".format(e)

def write_file(filepath, content):
    try:
        full = safe_path(filepath); path = rel(full)
        if not allowed(path): return "只允许修改 config.json 或 skills 目录内的文件"
        if os.path.basename(full).lower() in ("install.py", "main_agent.py", "app.py"): return "禁止修改核心文件"
        print("即将写入：{}，请输入大写 YES 确认：".format(path))
        if input("> ").strip() != "YES": return "用户取消写入操作"
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f: f.write(content)
        return "成功写入 {}，字符数 {}".format(path, len(content))
    except Exception as e: return "写入失败：{}".format(e)

TOOL_FUNC = {"read_file": read_file, "write_file": write_file}
'''

README = """# Python Skill-Agent\n\n运行 `python install.py` 安装，填写 `config.json` 后运行 `python main_agent.py`。\n\n输入 `quit` 退出。\n"""


def check_python_version():
    print("当前 Python 版本：{}.{}.{}".format(*sys.version_info[:3]))
    if sys.version_info[:2] < (3, 8):
        print("错误：需要 Python 3.8 或更高版本。"); sys.exit(1)


def check_pip():
    try: subprocess.check_call([sys.executable, "-m", "pip", "--version"])
    except Exception as e:
        print("pip 不可用：{}".format(e)); sys.exit(1)


def safe_path(relative):
    base = os.path.abspath(PROJECT_DIR)
    full = os.path.abspath(os.path.join(PROJECT_DIR, relative.replace("/", os.sep)))
    if not (full == base or full.startswith(base + os.sep)): raise ValueError("路径越界")
    return full


def write_if_missing(relative, content):
    try:
        path = safe_path(relative); os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path): print("跳过已存在文件：{}".format(relative)); return True
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        print("已生成：{}".format(relative)); return True
    except Exception as e:
        print("生成失败：{}：{}".format(relative, e)); return False


def create_config():
    path = safe_path("config.json")
    if os.path.exists(path): print("跳过已存在文件：config.json"); return True
    with open(path, "w", encoding="utf-8") as f: json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    print("已生成：config.json"); return True


def install_package(package):
    print("正在安装：{}".format(package))
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", package])
        return True
    except Exception as e:
        print("依赖安装失败：{}".format(e)); return False


def main():
    print("==== AI-Agent 项目安装程序 ====\n")
    check_python_version(); check_pip()
    files = [("main_agent.py", MAIN_AGENT_CODE), ("skills/__init__.py", "# skill module\n"), ("skills/skill_calc.py", SKILL_CALC), ("skills/skill_file.py", SKILL_FILE), ("README.md", README), ("run.bat", RUN_BAT), ("run.sh", RUN_SH)]
    if not all(write_if_missing(path, content) for path, content in files) or not create_config():
        print("项目文件生成失败。"); sys.exit(1)
    if install_package(OPENAI_VERSION):
        print("安装完成，请修改 config.json 后运行 python main_agent.py")
    else:
        print("项目文件已生成，请手动执行：{} -m pip install {}".format(sys.executable, OPENAI_VERSION))


if __name__ == "__main__":
    main()
