#!/usr/bin/env python3
"""reflexion.py — turn a corrected failure into a durable lesson.

The episodic half of HDS memory (Reflexion-style): when a generation is rejected
and then fixed, the rejection is worth remembering. This module decides WHAT to
record; agent wiring calls AIExperienceModule.register_failure with the result,
and the recall side reminds the model of past mistakes before it writes again.

Kept apart from the pipeline flow so it stays os-free (cage-writable) and its
pure decision logic is acceptance-testable without a model or the filesystem.
"""
from typing import Dict, Optional


def lesson_from_error(task_id: str, error: str, attempts: int) -> Optional[Dict]:
    """
    Distill a corrected failure into a lesson dict or None.

    Args:
        task_id (str): The unique identifier for the task.
        error (str): The error message from the failed attempt.
        attempts (int): The number of attempts made to complete the task.

    Returns:
        Optional[Dict]: A dictionary containing lesson details or None if conditions are not met.
    """
    e = error.strip()
    
    # If attempts <= 1 or the error is empty, return None
    if attempts <= 1 or not e:
        return None
    
    # Extract the first non-empty line of the error
    anti_pattern_rule = next((line.strip() for line in e.splitlines() if line.strip()), "")
    
    # Return the lesson details
    return {
        'task_id': task_id,
        'error_trace': e[:200],
        'ai_self_analysis': f'Corrected after {attempts} attempts',
        'anti_pattern_rule': anti_pattern_rule
    }
