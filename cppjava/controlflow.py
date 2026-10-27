"""Conservative completion analysis shared by checking and unreachable lowering."""
from . import ast as A


def sequence(statements):
    outcomes = {'normal'}
    for stmt in statements:
        if 'normal' not in outcomes:
            break
        outcomes = (outcomes - {'normal'}) | completion(stmt)
    return outcomes


def completion(stmt):
    if isinstance(stmt, A.ReturnStmt):
        return {'return'}
    if isinstance(stmt, A.BreakStmt):
        return {'break'}
    if isinstance(stmt, A.ContinueStmt):
        return {'continue'}
    if isinstance(stmt, A.Block):
        return sequence(stmt.statements)
    if isinstance(stmt, A.IfStmt):
        # Keep both branches: Java's return analysis does not fold if constants.
        return completion(stmt.then_branch) | (completion(stmt.else_branch) if stmt.else_branch else {'normal'})
    if isinstance(stmt, (A.ForStmt, A.WhileStmt, A.DoWhileStmt)):
        truth = stmt.condition.annotations.get('constant_truth') if stmt.condition else True
        body = completion(stmt.body)
        result = body - {'normal', 'continue', 'break'}
        if not isinstance(stmt, A.DoWhileStmt) and truth is False:
            return {'normal'}
        if 'break' in body or truth is not True and (not isinstance(stmt, A.DoWhileStmt) or body & {'normal', 'continue'}):
            result.add('normal')
        return result
    if isinstance(stmt, A.SwitchStmt):
        results = set() if any(c.value is None for c in stmt.cases) else {'normal'}
        following = {'normal'}
        for case in reversed(stmt.cases):
            exits = sequence(case.statements)
            if 'normal' in exits:
                exits = (exits - {'normal'}) | following
            following = exits
            results |= exits
        return (results - {'break'}) | ({'normal'} if 'break' in results else set())
    return {'normal'}
