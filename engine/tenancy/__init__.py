"""Tenancy authority package (Chapter 13.9, DDE-051).

`engine.tenancy` owns the authorization half of the scope chain
(`Principal -> Organization/Tenant -> Project -> ...`): identity
resolution from authenticated principals, grant rows, and their coverage
checks. It writes only `principal_grants`; Project Truth and domain state
stay with their Chapter 3.8 owners.
"""
