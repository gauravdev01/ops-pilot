from app.domain import ChildService, changed_function


def test_changed_function() -> None:
    assert isinstance(changed_function(), ChildService)


def test_items(client) -> None:
    client.post("/api/items")
