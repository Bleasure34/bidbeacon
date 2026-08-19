"""BidBeacon engine: turns public federal contract data into niche daily digests.

Pipeline: ingest (SAM.gov public extract) -> filter (niche profile) ->
digest (markdown/HTML) -> prospects (USAspending awardees per niche).
All sources are public-domain federal data, accessed anonymously at $0.
"""
__version__ = "0.1.0"
