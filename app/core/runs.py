from collections import OrderedDict


class RunOwners:
    """Remembers which user created each recent run, so users can only rate their own answers."""

    def __init__(self, max_runs: int = 5000):
        self._owners: OrderedDict[str, str] = OrderedDict()
        self._max_runs = max_runs

    def add(self, run_id: str, username: str) -> None:
        self._owners[run_id] = username
        if len(self._owners) > self._max_runs:
            self._owners.popitem(last=False)

    def owner(self, run_id: str) -> str | None:
        return self._owners.get(run_id)
