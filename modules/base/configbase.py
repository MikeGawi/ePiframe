import configparser
import itertools
import os
import shutil
from typing import List
from misc.configproperty import ConfigProperty
from abc import ABC, abstractmethod


class ConfigBase(ABC):

    __ERROR_PARSE = "Error parsing {} configuration entry"
    __ERROR_SAVE = "Error saving config file!"

    __COMMENT_IND_OK = "# "
    __COMMENT_IND_NOK = "; "
    __SECTION_IND = "["
    __REPLACE_IND = " "
    __VALUE_IND = "="

    __FILE_WRITE_FLAG = "w"

    SETTINGS = []

    def __init__(self, path: str, default_path: str, outer_class=None):
        self.__CONFIG_STRING = {}
        self.config = configparser.ConfigParser()
        self.__path = path
        self.__default_path = default_path
        self.__load_default_file()
        save = self.read_config()
        self.main_class = outer_class

        self.__COMMENTS = {}
        with open(self.__default_path) as file_values:
            self.__parse(file_values)

        self.load_settings()
        self.__get_properties()
        self.__convert()
        self.__save(save)

    def __parse(self, file_values):
        parse = str()
        for line in file_values:
            parse = self.__parse_line(line, parse)

    def __parse_line(self, line, parse):
        if line.startswith(self.__COMMENT_IND_OK):
            parse = self.__parse_comment(line, parse)
        elif (
            str.strip(line)
            and not line.startswith(self.__SECTION_IND)
            and not line.startswith(self.__COMMENT_IND_NOK)
        ):
            self.__COMMENTS[line.split(self.__VALUE_IND)[0]] = str.lstrip(parse)
            parse = str()

        return parse

    def __parse_comment(self, line, parse):
        return (
            parse
            + (" " if parse else "")
            + str.strip(line).replace(self.__COMMENT_IND_OK, self.__REPLACE_IND)
        )

    def __get_properties(self):
        for property_name in self.__CONFIG_STRING.keys():
            try:
                self.get_property(property_name)
            except Exception:
                self.SETTINGS.append(ConfigProperty(property_name, self))

    def __convert(self):
        for property_name in self.SETTINGS:
            property_name.convert()

    def __save(self, save):
        if save:
            self.save()

    def get_path(self) -> str:
        return self.__path

    def get_default_path(self) -> str:
        return self.__default_path

    @abstractmethod
    def load_settings(self):
        raise NotImplementedError

    def legacy_convert(self):
        pass

    def read_config(self):
        return_value = False
        if not os.path.exists(self.__path):
            shutil.copy(self.__default_path, self.__path)

        with open(self.__path) as file_values:
            self.config.read_file(file_values)

        self.__CONFIG_STRING = {}
        for section in self.config.sections():
            for property_name in list(dict(self.config.items(section)).keys()):
                self.__CONFIG_STRING[property_name] = section

        self.legacy_convert()
        return_value = self.__read_properties(return_value)
        self.__CONFIG_STRING = {}
        self.__load_sections()
        return return_value

    def __read_properties(self, return_value):
        for section in self.def_config.sections():
            for property_name in list(dict(self.def_config.items(section)).keys()):
                return_value = self.__read_property(
                    property_name, return_value, section
                )
        return return_value

    def __read_property(self, property_name, return_value, section):
        try:
            if not self.config.has_section(section):
                self.config.add_section(section)
                return_value = True
            self.config.get(section, property_name)
        except Exception:
            value = str()
            try:
                value = self.get(property_name)
            except Exception:
                pass
            self.config.set(
                section,
                property_name,
                value if value else self.def_config.get(section, property_name),
            )
            return_value = True
            pass
        return return_value

    def __load_sections(self):
        for section in self.def_config.sections():
            for property_name in list(dict(self.def_config.items(section)).keys()):
                self.__CONFIG_STRING[property_name] = section

    def get(self, name: str) -> str:
        try:
            return self.config.get(self.__CONFIG_STRING[name], name)
        except Exception:
            raise Exception(self.__ERROR_PARSE.format(name))

    def __load_default_file(self):
        self.def_config = configparser.ConfigParser()
        with open(self.__default_path) as file_data:
            self.def_config.read_file(file_data)

    def getint(self, name: str) -> int:
        try:
            return self.config.getint(self.__CONFIG_STRING[name], name)
        except Exception:
            raise Exception(self.__ERROR_PARSE.format(name))

    def set(self, name: str, value):
        self.config.set(self.__CONFIG_STRING[name], name, value)

    def save(self, path_name: str = None):
        path = self.__path if path_name is None else path_name
        filename = ""

        iterator = itertools.cycle(self.__CONFIG_STRING.keys())
        next_iterator = next(iterator)

        with open(self.__default_path) as file_lines:
            filename, next_iterator = self.__save_lines(
                file_lines, filename, iterator, next_iterator
            )

        self.__write_file(filename, path)

    def __save_lines(self, file_lines, filename, iterator, next_iterator):
        for line in file_lines:
            filename, next_iterator = self.__process_line(
                filename, iterator, line, next_iterator
            )
        return filename, next_iterator

    def __process_line(self, filename, iterator, line, next_iterator):
        if self.__check_line(line):
            filename = filename + line
        elif next_iterator in line:
            filename, next_iterator = self.__process_next(
                filename, iterator, next_iterator
            )
        else:
            raise Exception(self.__ERROR_SAVE)
        return filename, next_iterator

    def __check_line(self, line):
        return (
            line.startswith(self.__COMMENT_IND_OK)
            or line.startswith(self.__SECTION_IND)
            or line.startswith(self.__COMMENT_IND_NOK)
            or not str.strip(line)
        )

    def __process_next(self, filename, iterator, next_iterator):
        filename += "{}{}{}\n".format(
            next_iterator, self.__VALUE_IND, self.get(next_iterator)
        )
        next_iterator = next(iterator)
        return filename, next_iterator

    def __write_file(self, filename, path):
        with open(path, self.__FILE_WRITE_FLAG) as file_lines:
            file_lines.write(filename)

    def get_default(self, name: str):
        property_object = self.get_property(name)
        return (
            property_object.get_default() if str(property_object.get_default()) else ""
        )

    def get_possible_values(self, name: str):
        proper = self.get_property(name)
        return proper.get_possible()

    def get_comment(self, name: str) -> str:
        try:
            return self.__COMMENTS[name]
        except Exception:
            raise Exception(self.__ERROR_PARSE.format(name))

    def get_property(self, name: str) -> ConfigProperty:
        try:
            return_value = next(
                (
                    property_name
                    for property_name in self.SETTINGS
                    if property_name.get_name() == name
                ),
                None,
            )
            if not return_value:
                raise Exception
        except Exception:
            raise Exception(self.__ERROR_PARSE.format(name))
        return return_value

    def validate(self, name: str):
        proper = self.get_property(name)
        proper.validate()

    def get_sections(self) -> List[str]:
        return self.config.sections()

    def get_section_properties(self, section) -> list:
        return [
            property_name
            for property_name in self.__CONFIG_STRING.keys()
            if self.__CONFIG_STRING[property_name] == section
        ]

    def verify(self):
        for property_name in self.SETTINGS:
            property_name.validate()

    def verify_exceptions(self):
        for property_name in self.SETTINGS:
            try:
                property_name.validate()
            except Warning:
                pass
            except Exception as exception:
                raise exception

    def verify_warnings(self):
        for property_name in self.SETTINGS:
            try:
                property_name.validate()
            except Warning as warning:
                raise warning
            except Exception:
                pass
