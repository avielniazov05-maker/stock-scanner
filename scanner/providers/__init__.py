from .sample import SampleProvider

def get_provider(name: str):
    if name == "sample":
        return SampleProvider()
    raise ValueError(f"ספק לא מוכר: {name}")
