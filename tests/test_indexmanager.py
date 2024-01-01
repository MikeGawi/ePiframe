import os.path
from modules.indexmanager import IndexManager
from tests.helpers.helpers import remove_file

index_filename = "test_index.index"
index_test = 111
id_test = "test_id"


def test_index_manager_init():
    remove_file(index_filename)
    index_manager = IndexManager(index_filename)
    assert index_manager.get_index() == -1
    assert not index_manager.get_id()


def test_index_manager_save():
    index_manager = IndexManager(index_filename)
    index_manager.set_index(index_test)
    index_manager.set_id(id_test)

    assert index_manager.get_index() == index_test
    assert index_manager.get_id() == id_test
    remove_file(index_filename)
    index_manager.save()

    assert os.path.exists(index_filename)


def test_index_manager_read():
    index_manager = IndexManager(index_filename)
    assert index_manager.get_index() == index_test
    assert index_manager.get_id() == id_test


def test_index_manager_min():
    index_manager = IndexManager(index_filename)
    assert index_manager.get_index() == index_test
    index_manager.check_index(index_test - 10)
    assert index_manager.get_index() == 0


def test_index_manager_max():
    index_manager = IndexManager(index_filename)
    assert index_manager.get_index() == index_test
    index_manager.check_index(index_test + 10)
    assert index_manager.get_index() == index_test

    remove_file(index_filename)


def test_legacy_index_manager_init():
    remove_file(index_filename)
    with open(index_filename, "w") as file_data:
        file_data.write(str(id_test))
        file_data.write("\n")
        file_data.write(str(index_test))
    index_manager = IndexManager(index_filename)
    assert index_manager.get_index() == index_test
    assert index_manager.get_id() == id_test
    remove_file(index_filename)
