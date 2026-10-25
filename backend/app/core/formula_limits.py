"""Bound expression work before executing administrator-authored formulas."""
import ast
import re
from fastapi import HTTPException


def bounded_formula_tree(expression):
    if not isinstance(expression, str) or len(expression) > 1000:
        raise HTTPException(400, 'Formula exceeds the expression size limit')
    try:
        tree = ast.parse(expression, mode='eval')
    except (SyntaxError, ValueError, RecursionError):
        raise HTTPException(400, 'Invalid formula expression') from None
    nodes = list(ast.walk(tree))
    parents = {child: parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    if len(nodes) > 128:
        raise HTTPException(400, 'Formula is too complex')
    for node in nodes:
        if isinstance(node, ast.Constant):
            parent = parents.get(node)
            decimal_argument = isinstance(node.value,str) and isinstance(parent,ast.Call) and isinstance(parent.func,ast.Name) and parent.func.id=='Decimal' and bool(re.fullmatch(r'[-+]?\d{1,15}(?:\.\d{1,15})?',node.value))
            if not decimal_argument and (not isinstance(node.value, (int, float)) or abs(node.value) > 10**15):
                raise HTTPException(400, 'Formula requires bounded numeric constants')
        if isinstance(node, ast.Pow):
            raise HTTPException(400, 'Exponentiation is not supported in formulas')
    return tree
