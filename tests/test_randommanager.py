import os.path
import pandas as pd
import pytest
from modules.randommanager import RandomManager
from tests.helpers.helpers import remove_file, not_raises

random_filename = "test.random"
photo_header = "photo"
id_header = "id_column"


def test_init():
    remove_file(random_filename)
    random = RandomManager(random_filename, get_photos_pd(), id_header).get_random("")
    check_random(random, 1)


def test_read():
    random = RandomManager(random_filename, get_photos_pd(), id_header).get_random(
        pytest.last_random
    )
    check_random(random, 2)


def test_full():
    random = RandomManager(random_filename, get_photos_pd(), id_header).get_random(
        pytest.last_random
    )
    check_random(random, 3)


def test_after():
    random = RandomManager(random_filename, get_photos_pd(), id_header).get_random(
        pytest.last_random
    )
    check_random(random, 1)


def test_random():
    mock_random = ""
    last_random = -1
    remove_file(random_filename)
    for iteration in range(0, 10):
        random = f"id_{RandomManager(random_filename, get_photos_pd(), id_header).get_random(mock_random) + 1}"
        mock_random = random
        assert last_random != random
        last_random = random
    remove_file(random_filename)


def test_random_one_element():
    last_random = -1
    mock_random = ""
    photos = [
        {id_header: "id_1", photo_header: "Photo1"},
    ]

    for iteration in range(0, 10):
        with not_raises(Exception):
            random = RandomManager(
                random_filename, pd.DataFrame(photos), id_header
            ).get_random(mock_random)
        mock_random = f"id_{random}"
        if last_random > 0:
            assert last_random == random
        last_random = random
    remove_file(random_filename)


def test_no_save():
    RandomManager(random_filename, get_photos_pd(), id_header).get_random(
        pytest.last_random, no_save=True
    )

    assert not os.path.exists(random_filename)


def check_random(random: int, value: int):
    pytest.last_random = random
    assert random >= 0
    assert random in range(0, 3)
    assert os.path.exists(random_filename)
    with open(random_filename) as file:
        line = file.readline()
        first_line = file.readline()
        second_line = file.readline()
        third_line = file.readline()
    assert line == ",id_column,random\n"
    assert first_line.split(",")[0] == "0"
    assert first_line.split(",")[1] == "id_1"
    assert second_line.split(",")[0] == "1"
    assert second_line.split(",")[1] == "id_2"
    assert third_line.split(",")[0] == "2"
    assert third_line.split(",")[1] == "id_3"
    assert (
        first_line.replace("\n", "").split(",")[2] == "1"
        or second_line.replace("\n", "").split(",")[2] == "1"
        or third_line.replace("\n", "").split(",")[2] == "1"
    )
    assert (
        int(first_line.replace("\n", "").split(",")[2])
        + int(second_line.replace("\n", "").split(",")[2])
        + int(third_line.replace("\n", "").split(",")[2])
        == value
    )


def get_photos_pd():
    photos = [
        {id_header: "id_1", photo_header: "Photo1"},
        {id_header: "id_2", photo_header: "Photo2"},
        {id_header: "id_3", photo_header: "Photo3"},
    ]
    return pd.DataFrame(photos)
