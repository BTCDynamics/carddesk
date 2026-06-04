from urllib.parse import quote


def build_reference_search_query(staged_card):
    parts = [
        staged_card.year,
        staged_card.brand,
        staged_card.set_name,
        staged_card.player_name,
        f"#{staged_card.card_number}" if staged_card.card_number else None,
        staged_card.variation,
    ]

    return " ".join(str(part).strip() for part in parts if part).strip()


def build_reference_links(staged_card):
    query = build_reference_search_query(staged_card)
    encoded = quote(query, safe="")

    return {
        "query": query,
        "google_images": f"https://www.google.com/search?tbm=isch&q={encoded}",
        "ebay": f"https://www.ebay.com/sch/i.html?_nkw={encoded}",
        "comc": f"https://www.comc.com/Cards,sr,{encoded}",
        "sports_cards_pro": f"https://www.sportscardspro.com/search-products?q={encoded}",
    }







