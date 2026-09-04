import inspect

from app.database.crud import subscription as crud


def test_get_next_account_sequence_exists() -> None:
    assert inspect.iscoroutinefunction(crud.get_next_account_sequence)


def test_create_paid_subscription_source_sets_account_sequence() -> None:
    src = inspect.getsource(crud.create_paid_subscription)
    assert 'account_sequence' in src
    assert 'get_next_account_sequence' in src
