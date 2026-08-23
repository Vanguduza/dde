"""Chapter 11.5 domain invariant engine.

The production mutation call sites live in `engine.invariants.service`;
`engine.invariants.states` pins the definition lifecycle;
`engine.invariants.predicates` compiles the declarative predicate body
into parameterised SQL and judges collected rows purely.
"""

from __future__ import annotations
