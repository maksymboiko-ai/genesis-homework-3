"""Fixture output for MOCK_LLM=1 (UI work and tests without an API key)."""

from .schema import Generation, Variant

_POOL = [
    ("pain", "Laundry day ate another sock. Again.", "WHERE DO THEY GO?!",
     "So I found socks that literally can't split up.", "Close-up: one lonely sock on the dryer door."),
    ("demo", "Watch this. Click.", "*click* = never lose a sock",
     "That little click is a magnet in the cuff.", "Two cuffs snap together in slow motion."),
    ("question", "Do you own a drawer of single socks?", "The single-sock drawer...",
     "Mine's empty now, and here's why.", "Hand pulls open a drawer full of mismatched socks."),
    ("humor", "My dryer has been stealing from me for years.", "Dryer: 47. Me: 0.",
     "So I locked my socks together. Literally.", "Person interrogating a dryer with a desk lamp."),
    ("ugc_confession", "Okay, I bought magnetic socks and I'm obsessed.", "I was skeptical too",
     "Here's what nobody tells you about them.", "Selfie video in a laundry room, holding a pair."),
    ("contrarian", "You're not losing socks. You're folding wrong.", "Stop matching socks",
     "Actually, stop folding them at all.", "Person tossing an unfolded pair straight into a drawer."),
    ("callout", "Parents of three, this one's for you.", "Moms: stop matching socks",
     "Because nobody has time to pair 40 tiny socks.", "Mountain of kids' laundry on a couch."),
    ("before_after", "Before: sock chaos. After: one click.", "Before vs after laundry",
     "The difference is a tiny magnet.", "Split screen: messy pile vs neat clicked pairs."),
    ("curiosity", "There's a magnet hidden in these socks.", "Wait, a magnet??",
     "And it fixes the most annoying chore.", "Fingers revealing the cuff, magnet glinting."),
    ("gift", "The gift for the person who complains about laundry.", "Best weird gift of 2026",
     "Five pairs that never split up.", "Gift box opening, socks clicked together inside."),
]


def mock_generation(n: int) -> Generation:
    variants = []
    for i in range(n):
        t, hook, screen, bridge, visual = _POOL[i % len(_POOL)]
        variants.append(Variant(hook_type=t, hook_vo=hook if i < len(_POOL) else f"{hook} (take {i // len(_POOL) + 1})",
                                on_screen_text=screen, bridge_line=bridge, visual_note=visual,
                                rationale="Mock variant for offline mode."))
    return Generation(winning_angle="Mock: the original wins on a relatable laundry pain point.", variants=variants)
