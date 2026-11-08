"""Request/response shapes. Structure is enforced here; content rules live in checks.py."""

from pydantic import BaseModel, Field

HOOK_TYPES = {
    "pain": "names the frustration directly (lost socks, mismatched pairs)",
    "curiosity": "opens a loop the viewer wants closed",
    "question": "asks the viewer something they answer 'yes' to",
    "humor": "a joke or absurd exaggeration about the problem",
    "contrarian": "challenges a common belief",
    "ugc_confession": "first-person confession, sounds like a real customer",
    "demo": "leads with the product doing the thing (the click)",
    "before_after": "contrasts life before and after",
    "callout": "names the audience (parents, roommates, laundry haters)",
    "gift": "frames it as a gift",
}

LIMITS = {
    "hook_vo_words": 15,
    "on_screen_chars": 42,
    "bridge_words": 25,
    "visual_words": 25,
    "n_min": 3,
    "n_max": 20,
}


class Variant(BaseModel):
    hook_type: str
    hook_vo: str = Field(description="Spoken first line, first 3 seconds")
    on_screen_text: str = Field(description="Text overlay shown during the hook")
    bridge_line: str = Field(description="Line that connects the new hook to the unchanged body of the script")
    visual_note: str = Field(description="What the designer shows in the first 3 seconds")
    rationale: str = Field(description="Why this could beat the original, one short sentence")


class Generation(BaseModel):
    winning_angle: str = Field(description="One sentence: why the original script works")
    variants: list[Variant]


class GenerateRequest(BaseModel):
    script: str
    n_variants: int = 10
    hook_types: list[str] | None = None
    notes: str | None = None
    facts: str | None = None
