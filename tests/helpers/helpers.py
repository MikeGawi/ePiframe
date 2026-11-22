import os
from contextlib import contextmanager


@contextmanager
def not_raises(ExpectedException):
    try:
        yield

    except ExpectedException as err:
        raise AssertionError(
            "Did raise exception {0} when it should not!".format(
                repr(ExpectedException)
            )
        )

    except Exception as err:
        raise AssertionError("An unexpected exception {0} raised.".format(repr(err)))


def remove_file(file: str):
    if os.path.exists(file):
        os.remove(file)


def set_file(lines, filename):
    remove_file(filename)
    with open(filename, "w") as file:
        file.write(lines)
