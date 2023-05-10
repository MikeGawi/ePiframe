from typing import List
from PIL import Image, ImageDraw, ImageFont, ImageColor
import math
from modules.weathermanager import WeatherManager


class WeatherStampManager:

    __POSITION_VALUES = [0, 1, 2, 3]

    __FONTS = {
        "WEATHER_FONT": "static/fonts/weathericons-regular-webfont.ttf",
        "NORMAL_FONT": "static/fonts/NotoSans-SemiCondensed.ttf",
    }

    __COLORS = {"WHITE": 255, "BLACK": 0}

    __MARGIN = 10
    __SPACE = 5

    __ICONS = {
        "01d": "\uf00d",
        "01n": "\uf02e",
        "10d": "\uf015",
        "10n": "\uf015",
        "09d": "\uf017",
        "13d": "\uf01b",
        "13n": "\uf01b",
        "50d": "\uf021",
        "50n": "\uf021",
        "09n": "\uf013",
        "02d": "\uf002",
        "03d": "\uf002",
        "04d": "\uf002",
        "02n": "\uf086",
        "03n": "\uf086",
        "04n": "\uf086",
        "11d": "\uf01e",
        "11n": "\uf01e",
    }

    __DEGREES = "\u00b0"

    __ERROR_VALUE_TEXT = "Configuration position should be one of {}"
    __ERROR_COLOR_VALUE_TEXT = "Configuration font_color should be one of {}"

    def __init__(
        self,
        output_file: str,
        width: int,
        height: int,
        horizontal: bool,
        font: int,
        color: str,
        position: int,
        rotation: int,
    ):
        self.__output_file = output_file
        self.__width = width
        self.__height = height
        self.__font = font
        self.__position = position
        self.__color = color
        self.__horizontal = horizontal
        self.__rotation = rotation

    @classmethod
    def verify_position(cls, value: str):
        if not int(value) in cls.__POSITION_VALUES:
            raise Exception(cls.__ERROR_VALUE_TEXT.format(cls.__POSITION_VALUES))

    @classmethod
    def get_positions(cls) -> List[int]:
        return cls.__POSITION_VALUES

    @classmethod
    def verify_color(cls, value: str):
        if value not in [color.lower() for color in cls.__COLORS.keys()]:
            raise Exception(
                cls.__ERROR_COLOR_VALUE_TEXT.format(
                    [color.lower() for color in cls.__COLORS.keys()]
                )
            )

    @classmethod
    def get_colors(cls) -> List[str]:
        return [color.lower() for color in cls.__COLORS.keys()]

    def compose(self, temp: float, units: str, icon: str):
        image = Image.open(self.__output_file)
        image = self.__set_horizontal(image)
        width, height = image.size
        draw = ImageDraw.Draw(image)

        font_temperature = ImageFont.truetype(self.__FONTS["NORMAL_FONT"], self.__font)
        weather_font = ImageFont.truetype(self.__FONTS["WEATHER_FONT"], self.__font)

        text_weather = self.__ICONS[icon]
        size_weather = draw.textlength(text_weather, font=weather_font)

        text_temperature = self.__get_text_temperature(temp, units)
        size_temperature = draw.textlength(text_temperature, font=font_temperature)

        x = self.__MARGIN
        y = self.__MARGIN

        if self.__position in [1, 3]:
            x = width - size_weather - self.__SPACE - size_temperature - self.__MARGIN

        if self.__position in [2, 3]:
            y = height - self.__MARGIN - self.__font

        fill_color = self.__COLORS[self.__color.upper()]
        stroke_color = (self.__COLORS["WHITE"] + self.__COLORS["BLACK"]) - fill_color

        stroke = self.__get_stroke(image, stroke_color)
        fill = ImageColor.getcolor(self.__color, image.mode)

        draw.text(
            (x, y),
            text_weather,
            font=weather_font,
            fill=fill,
            stroke_width=2,
            stroke_fill=stroke,
        )
        draw.text(
            (x + size_weather + self.__SPACE, y),
            text_temperature,
            font=font_temperature,
            fill=fill,
            stroke_width=2,
            stroke_fill=stroke,
        )

        image = self.__process_horizontal(image)
        image.save(self.__output_file)

    def __set_horizontal(self, image: Image) -> Image:
        if not self.__horizontal:
            image = image.transpose(
                Image.ROTATE_90 if self.__rotation == 90 else Image.ROTATE_270
            )
        return image

    def __get_text_temperature(self, temp: float, units: str) -> str:
        return "{}{}{}".format(
            int(math.ceil(temp)),
            self.__DEGREES,
            "C" if WeatherManager.is_metric(units) else "F",
        )

    def __get_stroke(self, image: Image, stroke_color) -> ImageColor:
        return ImageColor.getcolor(
            {value: key for key, value in self.__COLORS.items()}[stroke_color],
            image.mode,
        )

    def __process_horizontal(self, image: Image) -> Image:
        if not self.__horizontal:
            image = image.transpose(
                Image.ROTATE_270 if self.__rotation == 90 else Image.ROTATE_90
            )
        return image
