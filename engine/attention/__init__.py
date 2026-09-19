"""EDR-0019 Epic I operator attention plane.

This does not replace `attention_items`, which remains the governance attention
authority. It adds the missing layer in front of it: scoring, deduplication and
a budget, so a repeating failure collapses into one item instead of flooding the
operator.
"""
