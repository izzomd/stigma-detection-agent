def flags_to_cards(flags: list[dict]) -> list[dict]:
    cards = []
    for flag in flags:
        confidence = flag.get("confidence", 0.0)
        if confidence >= 0.85:
            indicator = "critical"
        elif confidence >= 0.5:
            indicator = "warning"
        else:
            indicator = "info"

        cards.append({
            "summary": f"Stigmatizing language detected: \"{flag.get('flagged_span', '')}\"",
            "indicator": indicator,
            "detail": flag.get("reason", ""),
            "flagged_span": flag.get("flagged_span", ""),
            "category": flag.get("category", ""),
            "confidence": confidence,
            "suggested_rewrite": flag.get("suggested_rewrite", ""),
        })

    return cards
