# we import conduit_core here only, everything else imports from here

try:
    import conduit_core
except ImportError as exc:
    raise ImportError(
        "conduit_core is not built. Build the extension; "
        "PYTHONPATH must include /build-py."
    ) from exc

City = conduit_core.City
Route = conduit_core.Route
Snap = conduit_core.Snap

def load_city(path: str) -> City:
    return conduit_core.load_city(path)