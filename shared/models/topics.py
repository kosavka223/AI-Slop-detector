class Topics:
    EMAILS_RAW = "emails.raw"                  # ingestion -> parser (не твой)
    EMAILS_PARSED = "emails.parsed"            # parser -> анализаторы (не твой)
    ANALYSIS_TEXT = "analysis.text"            # анализаторы -> aggregator
    ANALYSIS_HTML = "analysis.html"
    ANALYSIS_IMAGES = "analysis.images"
    ANALYSIS_LINKS_META = "analysis.links-meta"
    ANALYSIS_AGGREGATED = "analysis.aggregated"    # aggregator -> decision-engine (ТВОЙ)
    VERDICTS = "verdicts.final"                    # decision-engine -> output (ТВОЙ)
    DLQ = "dead-letter-queue"                      # все -> DLQ