"""Chapter 13.8 Donor Lab (DDE-046): ingest, classify placeholder, Feature DNA stub.

Network discovery/fan-out is DDE-066 (EDR-0015). Licence classifier + taint
propagation into tasks/diffs is DDE-047. This package owns the durable
`donor_artifacts` / `feature_dna` mutation sites for human pin-by-URI and
fixture ingest.
"""

from engine.donor.service import DonorLabService, IngestResult

__all__ = ["DonorLabService", "IngestResult"]
