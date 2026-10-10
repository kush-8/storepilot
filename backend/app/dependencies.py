"""Lazy runtime composition and injectable service boundary for offline API tests."""

from functools import lru_cache

from app.agents.workflow.service import create_workflow


@lru_cache(maxsize=1)
def _runtime():
    return create_workflow()


class LazyWorkflow:
    def ask(self, *args, **kwargs):
        return _runtime().ask(*args, **kwargs)

    @property
    def data(self):
        return _runtime().data


def get_workflow():
    # Guards and login remain available before a model key or vector index is configured.
    return LazyWorkflow()
