from .base import BaseService


class ChildService(BaseService):
    def run(self) -> str:
        return "child"


class GrandChildService(ChildService):
    def run(self) -> str:
        return "grandchild"


def changed_function() -> ChildService:
    return ChildService()
