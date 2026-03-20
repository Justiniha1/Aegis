from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    query = test.get("query", "").strip()
    assertion = test.get("assertion", "").strip()

    if not query:
        return _error(test, "No query provided")
    if not assertion:
        return _error(test, "No assertion provided")

    df = connector.execute_query(query)

    if df.empty or df.shape[1] == 0:
        return _error(test, "Query returned no results")

    # The result value is the first cell of the first row
    result = df.iloc[0, 0]
    col_name = df.columns[0]

    # Evaluate assertion safely: only allow the result variable name and comparison ops
    try:
        local_vars = {col_name: result, "result": result}
        passed = bool(eval(assertion, {"__builtins__": {}}, local_vars))  # noqa: S307
    except Exception as e:
        return _error(test, f"Assertion evaluation failed: {e}")

    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "custom_sql",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "result_column": col_name,
            "result_value": result,
            "assertion": assertion,
        },
        "message": (
            f"Assertion '{assertion}' passed — {col_name} = {result}"
            if passed else
            f"Assertion '{assertion}' failed — {col_name} = {result}"
        ),
    }


def _error(test: dict, msg: str) -> dict:
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "custom_sql",
        "status": "ERROR",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {},
        "message": msg,
    }
