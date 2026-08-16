#!/usr/bin/env python3
"""cage_help.py — turn a terse cage verdict into one actionable sentence.

Give-ups are dominated by cage-unsatisfiable rejections (measured, see
hds_failures). The verdict the model gets back is terse ("R-AST: … rejected
(CRITICAL: forbidden_call)"). This appends a plain instruction on HOW to satisfy
the rule, so the self-correction loop has something to act on — and it reads
better for a human too.
"""


def explain(verdict: str) -> str:
    """
    Return ONE actionable sentence for the first pattern found in verdict,
    checked IN THIS ORDER; if none match return ''.

    Parameters:
        verdict (str): The verdict string to check for patterns.

    Returns:
        str: An actionable sentence or an empty string if no pattern matches.
    """
    patterns = [
        ('R-PRESERVE', 'Do not delete any existing declaration; re-emit every function unchanged, or patch only the one you change.'),
        ('R-STUB', 'An empty function must declare it is a placeholder: raise NotImplementedError or add a TODO comment.'),
        ('R-PATCH', 'The patch target does not exist in the file; emit the function with the exact name requested.'),
        ('forbidden_import', 'That import is banned. For os, only os.system/popen/exec/spawn/fork are forbidden - os.path and os.environ are allowed.'),
        ('forbidden_call', 'That call is banned (eval/exec/getattr, or an os.system-style process spawn). Do the task without it.'),
        ('implicitly has an', 'Add an explicit type to every parameter and the return value.')
    ]

    for pattern, message in patterns:
        if pattern in verdict:
            return message

    return ''
