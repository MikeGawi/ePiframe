import pytest
from tests.helpers.helpers import not_raises


def test_not_raises():
    with pytest.raises(Exception) as exception:
        with not_raises(Exception):
            raise Exception()

    assert (
        str(exception.value)
        == "Did raise exception <class 'Exception'> when it should not!"
    )


def test_not_raises_wrong():
    with pytest.raises(Exception) as exception:
        with not_raises(Warning):
            raise Exception()

    assert str(exception.value) == "An unexpected exception Exception() raised."
