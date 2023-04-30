class EPD:
    def __init__(self):
        print("__init__")

    @staticmethod
    def init():
        print("init")

    @staticmethod
    def getbuffer(image):
        assert image
        return "image"

    @staticmethod
    def display(image, image2=None):
        assert image
        print(f"{image}1")
        if image2:
            print(f"{image}2")
        print("display")

    @staticmethod
    def Clear():
        print("Clear")

    @staticmethod
    def sleep():
        print("sleep")
