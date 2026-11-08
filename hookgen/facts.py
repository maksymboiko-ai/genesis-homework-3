"""Product facts the copy must not contradict. Anything not listed here is an unverified claim."""

DEFAULT_FACTS = """\
Brand: SockLock
Product: socks with a small magnet in each cuff, so a pair clicks together and stays together in the washer and dryer.
Offer: subscription. First box is 5 pairs for $29. After that a new delivery arrives once a quarter (every 3 months).
Funnel: the ad leads to a short quiz (sock size, style) and a personal offer.
Market: United States (English).
Do NOT invent: discounts, free shipping, guarantees, statistics/percentages, awards, celebrity or press mentions, materials not listed here.
"""

# Dollar amounts that may appear in copy because they are facts above.
ALLOWED_DOLLAR_AMOUNTS = {"$29"}

# Claims we never allow unless the facts above are changed.
BANNED_PHRASES = [
    "free shipping",
    "money-back",
    "money back",
    "guarantee",
    "% off",
    "percent off",
    "discount",
    "award",
    "as seen on",
    "clinically",
    "doctor",
    "patented",
    "lifetime",
]
