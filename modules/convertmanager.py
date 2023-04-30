from __future__ import annotations

import os
import subprocess
from typing import List, Optional
from typing import TYPE_CHECKING

from misc.constants import Constants
from modules.displaymanager import DisplayManager

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager


class ConvertManager:
    __ERROR_VALUE_TEXT = "Configuration background_color should be one of {}"

    __INVERT_FLAG = "-negate "
    __ROTATE_CODE = "-rotate {} "
    __BACK_COLORS = [Constants.BACK_BLACK, Constants.BACK_WHITE, Constants.BACK_PHOTO]
    __GRAYSCALE_FLAG = "-colorspace Gray "
    __COLORS_FLAG = "-colors {} "

    __AUTO_GAMMA_ENH = "-auto-gamma "
    __AUTO_LEVEL_ENH = "-channel rgb -auto-level "
    __NORMALIZE_ENH = "-normalize "
    __BRIGHT_CONTRAST_ENH = "-brightness-contrast {},{} "

    __FILE_MARK = "[]"
    __GET_PHOTO_SIZE_CODE = "{} " + __FILE_MARK + ' -format "%w,%h" info:'
    __GET_PHOTO_FORMAT_CODE = "{} " + __FILE_MARK + ' -format "%m" info:'
    __GET_PHOTO_COMMENT_CODE = "{} " + __FILE_MARK + ' -format "%c" info:'
    __GET_PHOTO_EXIF_CODE = (
        "{} " + __FILE_MARK + ' -quiet -format "%[EXIF:Orientation]" info:'
    )

    __PHOTO_ORIENT_CODE = "{} " + __FILE_MARK + " -auto-orient " + __FILE_MARK

    # Don't use blur! Blur will kill Raspberry Pi Zero.
    # Resizing to huge and then scaling to small will add some blur, and it's 10x faster than blur operation.
    __PHOTO_BACK_CODE = (
        "( -clone 0 -gravity center -sample x{} -scale {}% -resize {}x{}^ -crop {}x+0+0 +repage ) ( "
        "-clone 0 -sample {}x{} ) -delete 0 -gravity center -compose over -composite "
    )
    __PHOTO_RESIZE_CODE = "-sample {}x{} "

    # options for ImageMagick converter
    # https://legacy.imagemagick.org/Usage/quantize/
    __CONVERT_OPTIONS = {
        "1": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity "
        "center -extent {}x{} -type bilevel -write {} ) {} NULL:",
        "2": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg {}-background {} -gravity center -extent {}x{} "
        "-type bilevel -write {} ) {} NULL:",
        "3": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -remap pattern:gray50 {}-background {} -gravity "
        "center -extent {}x{} -type bilevel -write {} ) {} NULL:",
        "4": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}-dither FloydSteinberg -ordered-dither o4x4 {}-background {} -gravity "
        "center -extent {}x{} -type bilevel -write {} ) {} NULL:",
        "5": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}{}-background {} -gravity center -extent {}x{} -type bilevel -write {} ) {"
        "} NULL:",
        "6": "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}-colors 2 +dither {}-background {} -gravity center -extent {}x{} -type "
        "bilevel -write {} ) {} NULL:",
    }

    __ROTATION = [90, 270]

    __HDMI_CODE = (
        "{} "
        + __FILE_MARK
        + " -limit thread 1 {} ( +clone {}{}{}-background {} -gravity center -extent {}x{} {}-write {} ) {} NULL:"
    )

    __THUMB_SIZE = "200x120"
    __THUMB_1ST_PART = (
        "( +clone -background white -gravity center -sample {}x{} -extent {}x{} -thumbnail "
        + __THUMB_SIZE
        + " -write {} +delete )"
    )
    __THUMB_2ND_PART = "( +clone -thumbnail " + __THUMB_SIZE + " -write {} )"

    @classmethod
    def verify_background_color(cls, value):
        if not value.strip().lower() in cls.__BACK_COLORS:
            raise Exception(cls.__ERROR_VALUE_TEXT.format(cls.__BACK_COLORS))

    @classmethod
    def get_background_colors(cls) -> List[str]:
        return cls.__BACK_COLORS

    @classmethod
    def get_convert_options(cls) -> List[str]:
        return list(cls.__CONVERT_OPTIONS.keys())

    @classmethod
    def get_rotation(cls) -> List[int]:
        return list(cls.__ROTATION)

    def __convert_option(
        self,
        original_width: int,
        original_height: int,
        target: str,
        config: ConfigManager,
        hdmi: bool,
    ) -> str:
        option = int(config.get("convert_option"))
        width = config.getint("image_width")
        height = config.getint("image_height")
        back = config.get("background_color")

        if int(option) > len(self.__CONVERT_OPTIONS) or int(option) < 1:
            option = 1

        # space at the end as those flag are optional
        negate = self.__INVERT_FLAG if config.getint("invert_colors") == 1 else ""
        rotate = (
            self.__ROTATE_CODE.format(config.getint("rotation"))
            if config.getint("horizontal") == 0
            else ""
        )

        if config.getint("horizontal") == 1 and config.getint("turned") == 1:
            rotate = self.__ROTATE_CODE.format(180)

        back = back.strip().lower()

        if back not in self.__BACK_COLORS:
            back = Constants.BACK_WHITE

        if back == Constants.BACK_PHOTO:
            back = Constants.BACK_WHITE
            # this takes more time to progress
            aspect_ratio = int(original_width) / int(original_height)
            new_height = max(int(width / aspect_ratio), height)
            scale = round(aspect_ratio * 10.0, 2)
            code = self.__PHOTO_BACK_CODE.format(
                new_height, scale, width, new_height, width, width, height
            )
        else:
            code = self.__PHOTO_RESIZE_CODE.format(width, height)

        if bool(config.getint("auto_gamma")):
            code += self.__AUTO_GAMMA_ENH
        if bool(config.getint("auto_level")):
            code += self.__AUTO_LEVEL_ENH
        if bool(config.getint("normalize")):
            code += self.__NORMALIZE_ENH
        if bool(config.getint("grayscale")):
            code += self.__GRAYSCALE_FLAG
        code += self.__BRIGHT_CONTRAST_ENH.format(
            config.getint("brightness"), config.getint("contrast")
        )

        thumb1st = self.__THUMB_1ST_PART.format(
            width,
            height,
            width,
            height,
            os.path.join(
                config.get("photo_convert_path"),
                config.get("thumb_photo_download_name"),
            ),
        )
        thumb2nd = self.__THUMB_2ND_PART.format(
            os.path.join(
                config.get("photo_convert_path"),
                config.get("thumb_photo_convert_filename"),
            )
        )

        return_value = self._get_convert_code(
            back,
            code,
            config,
            hdmi,
            height,
            negate,
            option,
            rotate,
            target,
            thumb1st,
            thumb2nd,
            width,
        )

        print(return_value.replace("(", "\(").replace(")", "\)"))
        return return_value

    def _get_convert_code(
        self,
        back,
        code,
        config,
        hdmi,
        height,
        negate,
        option,
        rotate,
        target,
        thumb1st,
        thumb2nd,
        width,
    ):
        if hdmi or not DisplayManager.should_convert(config.get("epaper_color")):
            colors = (
                self.__COLORS_FLAG.format(config.getint("colors_num"))
                if config.get("colors_num") and hdmi
                else ""
            )
            return_value = self.__HDMI_CODE.format(
                config.get("convert_bin_path"),
                thumb1st,
                rotate,
                code,
                negate,
                back,
                width,
                height,
                colors,
                target,
                thumb2nd,
            )
        else:
            return_value = self.__CONVERT_OPTIONS[str(option)].format(
                config.get("convert_bin_path"),
                thumb1st,
                rotate,
                code,
                negate,
                back,
                width,
                height,
                target,
                thumb2nd,
            )
        return return_value

    def __subproc(self, argument: str, source_file: str) -> (str, str):
        arguments = argument.split()
        process = subprocess.Popen(
            [arg.replace(self.__FILE_MARK, source_file) for arg in arguments],
            stdout=subprocess.PIPE,
        )
        process.wait()
        return process.communicate()

    def convert_image(
        self,
        original_width: int,
        original_height: int,
        source_file: str,
        target: str,
        config: ConfigManager,
        hdmi: bool = False,
    ) -> bytes:
        out, error = self.__subproc(
            self.__convert_option(
                original_width, original_height, target, config, hdmi
            ),
            source_file,
        )
        return error

    def orient_image(self, binary: str, file: str, first_frame: str) -> Optional[bytes]:
        orientation_error, orientation = self.get_image_orientation(
            binary, file, first_frame
        )
        error = None
        if orientation:
            out, error = self.__subproc(self.__PHOTO_ORIENT_CODE.format(binary), file)
        return error

    def get_image_size(
        self, binary: str, srcfile: str, first_frame: str
    ) -> (str, str, str):
        out, error = self.__subproc(
            self.__GET_PHOTO_SIZE_CODE.format(binary), srcfile + first_frame
        )
        width_height = str(out.decode()).replace('"', "").split(",") if out else ""
        width = width_height[0] if width_height and len(width_height) > 1 else ""
        height = width_height[1] if width_height and len(width_height) > 1 else ""
        return error, width, height

    def get_image_format(
        self, binary: str, srcfile: str, first_frame: str
    ) -> (str, str):
        out, error = self.__subproc(
            self.__GET_PHOTO_FORMAT_CODE.format(binary), srcfile + first_frame
        )
        format_name = str(out.decode()).replace('"', "") if out else ""
        return error, format_name

    def get_image_orientation(
        self, binary: str, source_file: str, first_frame: str
    ) -> (str, str):
        out, error = self.__subproc(
            self.__GET_PHOTO_EXIF_CODE.format(binary), source_file + first_frame
        )
        orientation = str(out.decode()).replace('"', "") if out else ""
        return error, orientation

    def get_image_comment(self, binary: str, source_file: str) -> (str, str):
        out, error = self.__subproc(
            self.__GET_PHOTO_COMMENT_CODE.format(binary), source_file
        )
        comment = str(out.decode()).replace('"', "") if out else ""
        return error, comment
