"""Chapter 13.8 Donor Lab (DDE-046/047): ingest, classify, Feature DNA, taint.

Network discovery/fan-out is DDE-066 (EDR-0015). This package owns the
durable `donor_artifacts` / `feature_dna` / `donor_taints` mutation sites
for human pin-by-URI, fixture ingest, and provenance propagation.
"""

from engine.donor.service import DonorLabService, IngestResult
from engine.donor.taint import DonorTaintService

__all__ = ["DonorLabService", "DonorTaintService", "IngestResult"]
