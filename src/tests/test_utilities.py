import pytest

from src.utilities import get_page_slice


@pytest.mark.parametrize(
    ("page", "items_length", "items_per_page", "expected"),
    [
        (1, 15, 10, (0, 10)),
        (2, 15, 10, (10, None)),
        (1, 15, 50, (0, None)),
    ],
)
def test_page_slice(page, items_length, items_per_page, expected):
    assert get_page_slice(page, items_length, items_per_page) == expected
