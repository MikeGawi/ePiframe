BLACK = 0
WHITE = 1

DESATURATED_PALETTE = [
    [0, 0, 0],
    [255, 255, 255],
    [0, 255, 0],
    [0, 0, 255],
    [255, 0, 0],
    [255, 255, 0],
    [255, 140, 0],
    [255, 255, 255],
]


class InkyBase:
    BLACK = 0
    WHITE = 1

    def __init__(self, colour=None):
        if colour:
            print(f"{colour=}")
        print("__init__")

    def set_border(self, border_color=None):
        if border_color is not None:
            print(f"{border_color=}")
        print("set_border")

    def set_image(self, image, saturation=None):
        if saturation:
            print(f"{saturation=}")
        assert image
        print("set_image")

    def show(self):
        print("show")


class InkyPHAT(InkyBase):
    BLACK = 1
    WHITE = 0

    pass


class InkyWHAT(InkyBase):
    pass


class Inky(InkyBase):
    pass
