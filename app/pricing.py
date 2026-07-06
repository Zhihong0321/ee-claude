"""Official Anthropic list pricing, used to estimate turn cost regardless of
which LLM proxy actually served the request (token counts come from the
provider; cost is always priced at Anthropic's official rates).
"""

# model -> (input, output, cache_read, cache_write_5m) USD per 1M tokens
_PRICING: dict[str, tuple[float, float, float, float]] = {
    "claude-sonnet-5": (3.00, 15.00, 0.30, 3.75),
    "claude-opus-4-8": (5.00, 25.00, 0.50, 6.25),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
    "claude-fable-5": (10.00, 50.00, 1.00, 12.50),
    "claude-mythos-5": (10.00, 50.00, 1.00, 12.50),
}
_DEFAULT_PRICING = _PRICING["claude-sonnet-5"]


def estimate_cost_usd(model: str | None, usage: dict | None) -> float | None:
    """Estimate USD cost for one turn's token usage at official Anthropic rates."""
    if not usage:
        return None
    input_price, output_price, cache_read_price, cache_write_price = _PRICING.get(
        model or "", _DEFAULT_PRICING
    )
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    cache_write = usage.get("cache_creation_input_tokens") or 0
    cost = (
        input_tokens * input_price
        + output_tokens * output_price
        + cache_read * cache_read_price
        + cache_write * cache_write_price
    ) / 1_000_000
    return round(cost, 6)
