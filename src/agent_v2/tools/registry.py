"""Tool registry for agent_v2 tools."""
import inspect
from typing import Callable, Dict, Any, List, Optional

_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(name: str = None, description: str = None):
    """Decorator to register a tool function.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description for LLM (defaults to docstring)
    """
    def decorator(func: Callable):
        tool_name = name or func.__name__

        # Auto-generate schema from function signature
        sig = inspect.signature(func)
        params = {}
        required = []

        # Extract param descriptions from docstring if available
        param_docs = _parse_docstring_params(func.__doc__ or "")

        for param_name, param in sig.parameters.items():
            param_type = param.annotation
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object"
            }

            param_desc = param_docs.get(param_name, f"Parameter {param_name}")
            params[param_name] = {
                "type": type_map.get(param_type, "string"),
                "description": param_desc
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description or _get_short_description(func.__doc__) or f"Execute {tool_name}",
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


def _parse_docstring_params(docstring: str) -> Dict[str, str]:
    """Parse parameter descriptions from docstring."""
    params = {}
    lines = docstring.split('\n')
    in_args = False
    current_param = None

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith('args:'):
            in_args = True
            continue
        if in_args:
            if stripped.lower().startswith('returns:') or stripped.lower().startswith('raises:'):
                break
            if ':' in stripped and not stripped.startswith(' '):
                parts = stripped.split(':', 1)
                current_param = parts[0].strip()
                params[current_param] = parts[1].strip() if len(parts) > 1 else ""

    return params


def _get_short_description(docstring: str) -> Optional[str]:
    """Get first line of docstring as short description."""
    if not docstring:
        return None
    lines = docstring.strip().split('\n')
    return lines[0].strip() if lines else None


def get_tool_schemas(tool_names: List[str] = None) -> List[dict]:
    """Get tool schemas for LLM.

    Args:
        tool_names: Specific tools to get (None = all tools)
    """
    if tool_names is None:
        return [v["schema"] for v in _TOOL_REGISTRY.values()]
    return [_TOOL_REGISTRY[name]["schema"] for name in tool_names if name in _TOOL_REGISTRY]


def get_tool_names() -> List[str]:
    """Get all registered tool names."""
    return list(_TOOL_REGISTRY.keys())


def get_tool_schema(name: str) -> Optional[dict]:
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


def clear_registry():
    """Clear all registered tools (useful for testing)."""
    _TOOL_REGISTRY.clear()
