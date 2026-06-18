import ast
import operator

from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import error, result

TYPE = "custom_sql"

# Restricted assertion grammar: comparisons, boolean logic, and arithmetic over the
# provided names/constants only. Replaces eval() — which, even with __builtins__
# emptied, could reach object internals via attribute access (e.g. result.__class__).
_COMPARISONS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
}
_BINARY_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}


def _eval_node(node: ast.AST, names: dict):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, names) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("unsupported boolean operator")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, names)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        op = _BINARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("unsupported binary operator")
        return op(_eval_node(node.left, names), _eval_node(node.right, names))
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, names)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _COMPARISONS.get(type(op_node))
            if op is None:
                raise ValueError("unsupported comparison operator")
            right = _eval_node(comparator, names)
            if not op(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        raise ValueError(f"unknown name: {node.id}")
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"unsupported expression: {type(node).__name__}")


def _evaluate_assertion(expr: str, names: dict) -> bool:
    """Safely evaluate a comparison assertion against the provided names.

    Raises on any construct outside the allowed grammar (calls, attribute access,
    subscripts, names not in `names`), or on a syntax error.
    """
    return bool(_eval_node(ast.parse(expr, mode="eval"), names))


def run(connector: DatabaseConnector, test: dict) -> dict:
    query = test.get("query", "").strip()
    assertion = test.get("assertion", "").strip()

    if not query:
        return error(test, TYPE, "No query provided")
    if not assertion:
        return error(test, TYPE, "No assertion provided")

    df = connector.execute_query(query)

    if df.empty or df.shape[1] == 0:
        return error(test, TYPE, "Query returned no results")

    # The result value is the first cell of the first row. It is used locally to evaluate
    # the assertion, but it is a potential raw record value — see the exposure rule below.
    raw = df.iloc[0, 0]
    value = raw.item() if hasattr(raw, "item") else raw  # numpy scalar -> native Python
    col_name = df.columns[0]

    try:
        names = {col_name: value, "result": value}
        passed = _evaluate_assertion(assertion, names)
    except Exception as e:
        return error(test, TYPE, f"Assertion evaluation failed: {e}")

    # Data-residency: the query result value is NOT transmitted or stored — only the
    # pass/fail outcome and the (operator-authored) assertion text leave. Surfacing a
    # chosen result value is a deliberate feature to be designed later.
    status = "PASSED" if passed else "FAILED"
    outcome = "passed" if passed else "failed"
    return result(
        test, TYPE, status,
        {"result_column": col_name, "assertion": assertion},
        f"Assertion '{assertion}' {outcome}",
    )
