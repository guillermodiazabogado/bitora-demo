# BITORA V4.9 Segmentation Model

Segments store deterministic JSON rules.

Initial supported filters:
- accreditation status;
- accreditation type;
- activity reservation.

Recipient previews apply:
- event scope;
- organization scope through event ownership;
- deduplication;
- channel recipient availability;
- consent checks;
- suppression checks.

Snapshots are stored at campaign validation time so later participant changes do not silently alter approved campaigns.
