from .sample import SampleProvider

def get_provider(name: str, cfg: dict | None = None):
    if name == "sample":
        return SampleProvider()
    if name == "yahoo_free":
        from .yahoo_free import YahooFreeProvider
        return YahooFreeProvider(cfg["filter"], cfg["params"].get("avg_volume_days", 50))
    raise ValueError(f"ספק לא מוכר: {name}")
