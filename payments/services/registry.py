_PROVIDERS = {}


def register(key: str, cls):
    _PROVIDERS[key] = cls


def get_provider(key: str):
    return _PROVIDERS.get(key)
