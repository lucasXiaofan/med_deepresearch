"""Tool registry for agent tools."""
import inspect
from typing import Callable, Dict, Any

_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(name: str = None, description: str = None):
    """Decorator to register a tool function."""
    def decorator(func: Callable):
        tool_name = name or func.__name__

        # Auto-generate schema from function signature
        sig = inspect.signature(func)
        params = {}
        required = []

        for param_name, param in sig.parameters.items():
            param_type = param.annotation
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean"
            }

            params[param_name] = {
                "type": type_map.get(param_type, "string"),
                "description": f"Parameter {param_name}"
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description or func.__doc__ or f"Execute {tool_name}",
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": required
                }
            }
        }

        _TOOL_REGISTRY[tool_name] = {
            "schema": schema,
            "function": func
        }

        return func

    return decorator


def get_tool_schemas():
    """Get all tool schemas for LLM."""
    return [v["schema"] for v in _TOOL_REGISTRY.values()]


def get_tool_names():
    """Get all registered tool names."""
    return list(_TOOL_REGISTRY.keys())


def get_tool_schema(name: str) -> dict:
    """Get schema for a specific tool."""
    if name in _TOOL_REGISTRY:
        return _TOOL_REGISTRY[name]["schema"]
    return None


def execute_tool(name: str, args: dict) -> str:
    """Execute a registered tool by name."""
    if name not in _TOOL_REGISTRY:
        return f"Error: Tool '{name}' not found"

    try:
        result = _TOOL_REGISTRY[name]["function"](**args)
        return str(result) if result is not None else "Success"
    except Exception as e:
        return f"Error: {str(e)}"
