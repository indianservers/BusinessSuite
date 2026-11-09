"""Shared existing salary formula/ordering implementation for preview and payroll."""
import ast
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException
from app.models.payroll import SalaryComponent, SalaryStructure, SalaryStructureComponent

ALLOWED_FORMULA_FUNCS = {"min": min, "max": max, "round": round, "Decimal": Decimal}
ALLOWED_FORMULA_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.UAdd, ast.USub,
)


def _safe_formula_value(expression: str, variables: dict[str, Decimal], component_code: str) -> Decimal:
    from app.core.formula_limits import bounded_formula_tree
    bounded_formula_tree(expression)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: {exc.msg}")

    allowed_names = set(variables) | set(ALLOWED_FORMULA_FUNCS)
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_FORMULA_NODES):
            raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unsupported expression")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unknown name {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FORMULA_FUNCS:
                raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unsupported function")
    try:
        value = eval(
            compile(tree, "<salary_formula>", "eval"),
            {"__builtins__": {}},
            {**ALLOWED_FORMULA_FUNCS, **variables},
        )
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: {exc}")


def _formula_dependencies(expression: Optional[str]) -> set[str]:
    if not expression:
        return set()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return set()
    return {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id not in ALLOWED_FORMULA_FUNCS
        and node.id not in {"ctc_monthly", "ctc_annual", "gross", "basic"}
    }


def _active_formula_expression(component: SalaryComponent) -> Optional[str]:
    active_rules = [
        rule for rule in component.formula_rules
        if rule.validation_status in {"Active", "Approved"} and not rule.effective_to
    ]
    if active_rules:
        active_rules.sort(key=lambda rule: (rule.dependency_order or 100, rule.id), reverse=False)
        return active_rules[0].formula_expression
    return component.formula_expression


def _component_monthly_amount(item: SalaryStructureComponent, monthly_ctc: Decimal, extra_variables: Optional[dict[str, Decimal]] = None) -> Decimal:
    component = item.component
    variables = {
        "ctc_monthly": monthly_ctc,
        "ctc_annual": monthly_ctc * Decimal("12"),
    }
    if extra_variables:
        variables.update(extra_variables)
    item_expression = getattr(item, "formula_expression", None)
    if component and (component.calculation_type == "Formula" or item_expression):
        expression = item_expression or _active_formula_expression(component)
        if expression:
            value = _safe_formula_value(expression, variables, component.code)
            item_min = getattr(item, "min_amount", None)
            item_max = getattr(item, "max_amount", None)
            minimum = item_min if item_min is not None else component.min_amount
            maximum = item_max if item_max is not None else component.max_amount
            if minimum is not None:
                value = max(value, Decimal(minimum))
            if maximum is not None:
                value = min(value, Decimal(maximum))
            return value.quantize(Decimal("0.01"))
    if item.amount is not None and Decimal(item.amount) != Decimal("0"):
        return Decimal(item.amount)
    if item.percentage is not None:
        return (monthly_ctc * Decimal(item.percentage) / Decimal("100")).quantize(Decimal("0.01"))
    if component and component.calculation_type == "Percentage" and component.amount:
        return (monthly_ctc * Decimal(component.amount) / Decimal("100")).quantize(Decimal("0.01"))
    return Decimal(component.amount or 0) if component else Decimal("0")


def _ordered_structure_components(structure: SalaryStructure) -> tuple[list[SalaryStructureComponent], list[str]]:
    items = [item for item in structure.components if item.component]
    by_code = {item.component.code: item for item in items}
    dependencies = {
        item.component.code: {dep for dep in _formula_dependencies(getattr(item, "formula_expression", None) or _active_formula_expression(item.component)) if dep in by_code}
        for item in items
    }
    ordered: list[SalaryStructureComponent] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    warnings: list[str] = []

    def visit(code: str) -> None:
        if code in visited:
            return
        if code in visiting:
            raise HTTPException(status_code=400, detail=f"Circular salary formula dependency detected at {code}")
        visiting.add(code)
        for dependency in sorted(dependencies.get(code, set())):
            visit(dependency)
        visiting.remove(code)
        visited.add(code)
        ordered.append(by_code[code])

    for item in sorted(items, key=lambda row: (row.order_sequence or 100, row.component.display_sequence or 100, row.component.code)):
        visit(item.component.code)
    for code, deps in dependencies.items():
        if deps:
            warnings.append(f"{code} depends on {', '.join(sorted(deps))}")
    return ordered, warnings
