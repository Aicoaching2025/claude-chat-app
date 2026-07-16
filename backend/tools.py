"""The one client-side tool this app defines: a calculator.

Web search is handled by Anthropic's server-side web_search tool (declared in
agent_loop.py) — Claude issues the query and Anthropic executes it, so there's
no client dispatch for it here. calculator is the example of a tool *we*
must execute and report back on.
"""

from __future__ import annotations

import ast
import operator

CALCULATOR_TOOL_DEF = {
    "name": "calculator",
    "description": (
        "Evaluate a basic arithmetic expression. Supports +, -, *, /, "
        "parentheses, and decimals. Use this whenever a numeric computation "
        "is needed rather than doing math yourself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A math expression, e.g. '12.5 * (3 + 7)'",
            }
        },
        "required": ["expression"],
    },
}

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"unsupported expression element: {ast.dump(node)}")


def safe_eval(expression: str) -> float:
    """Evaluate an arithmetic expression without using eval().

    Only numeric literals and +, -, *, /, **, parentheses are reachable —
    the AST walk has no path to name lookups, attribute access, or calls, so
    there's nothing here for untrusted (model-supplied) input to exploit.
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body)


def run_calculator(expression: str) -> str:
    try:
        result = safe_eval(expression)
        return str(result)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as e:
        return f"Error evaluating '{expression}': {e}"


TOOL_DISPATCH = {
    "calculator": lambda inp: run_calculator(inp["expression"]),
}
