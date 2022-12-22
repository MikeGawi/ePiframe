import os
import numbers


class ConfigProperty:
    STRING_TYPE = "STRING"
    FILE_TYPE = "FILE"
    INTEGER_TYPE = "INTEGER"
    FLOAT_TYPE = "FLOAT"
    BOOLEAN_TYPE = "BOOLEAN"
    STRING_LIST_TYPE = "STRING_LIST"
    INT_LIST_TYPE = "INT_LIST"
    PASSWORD_TYPE = "PASSWORD"

    STRING_ERROR_MSG = "{} configuration entry is missing!"
    FILE_ERROR_MSG = "{} configuration entry path does not exist!"
    INT_ERROR_MSG = "{} configuration entry in not an integer value!"
    FLOAT_ERROR_MSG = "{} configuration entry in not an float value!"
    BOOL_ERROR_MSG = "{} configuration entry in not a boolean (0 or 1) value!"
    MIN_ERROR_MSG = "{} configuration entry should be >= than {}!"
    MAX_ERROR_MSG = "{} configuration entry should be <= than {}!"
    LENGTH_ERROR_MSG = "{} configuration entry is missing all values!"
    INT_LIST_ERROR_MSG = "{} configuration entry not all values are integer!"
    CHECK_ERROR_MSG = "{} configuration entry error: {}"
    CHECK_WARN_MSG = "{} configuration entry warning: {}"
    POSSIBLE_ERROR_MSG = "{} configuration entry value should be one of the {}"

    class Special:
        WARNING_TYPE = "WARNING"
        EXCEPTION_TYPE = "EXCEPTION"

        def __init__(self, function, arguments, exception_type=EXCEPTION_TYPE):
            self.function = function
            self.arguments = arguments
            self.exception_type = exception_type

    def __init__(
        self,
        name,
        config_manager,
        prop_type=STRING_TYPE,
        not_empty: bool = True,
        dependency=None,
        minvalue=None,
        maxvalue=None,
        check_function=None,
        special=None,
        length=None,
        delimiter=None,
        possible=None,
        reset_needed: bool = False,
        convert=None,
    ):
        self.__type = prop_type
        self.__name = name
        self.__dependency = dependency
        self.__minvalue = minvalue
        self.__maxvalue = maxvalue
        self.__check_function = check_function
        self.__special = special
        self.__length = length
        self.__delimiter = delimiter
        self.__not_empty = not_empty
        self.__config_manager = config_manager
        self.__possible = possible
        self.__reset_needed = reset_needed
        self.__convert = convert

        is_break = False
        for section in self.__config_manager.def_config.sections():
            if is_break:
                break
            for property_name in list(
                dict(self.__config_manager.def_config.items(section)).keys()
            ):
                if property_name == name:
                    if (
                        self.__type == self.BOOLEAN_TYPE
                        or self.__type == self.INTEGER_TYPE
                    ):
                        value = self.__config_manager.def_config.get(
                            section, property_name
                        )
                        if value:
                            self.__default = int(value)
                        else:
                            self.__default = value
                        is_break = True
                        break
                    else:
                        self.__default = self.__config_manager.def_config.get(
                            section, property_name
                        )
                        is_break = True
                        break

    def get_name(self) -> str:
        return self.__name

    def get_type(self) -> str:
        return self.__type

    def get_dependency(self):
        return (
            self.__dependency
            if not isinstance(self.__dependency, list)
            else self.__dependency[0]
        )

    def get_dependency_value(self):
        return (
            str() if not isinstance(self.__dependency, list) else self.__dependency[1]
        )

    def get_reset_needed(self) -> bool:
        return self.__reset_needed

    def get_default(self):
        return self.__default

    def get_possible(self):
        return list(range(2)) if self.__type == self.BOOLEAN_TYPE else self.__possible

    def get_min(self):
        return self.__minvalue

    def get_max(self):
        return self.__maxvalue

    def convert(self):
        if self.__convert:
            self.__config_manager.set(
                self.__name, self.__convert(self.__config_manager.get(self.__name))
            )

    def validate(self):
        if (
            (
                self.__dependency
                and not isinstance(self.__dependency, list)
                and bool(self.__config_manager.getint(self.__dependency))
            )
            or (
                self.__dependency
                and isinstance(self.__dependency, list)
                and self.__config_manager.get(self.__dependency[0])
                == self.__dependency[1]
            )
            or not self.__dependency
        ):
            if self.__not_empty and not self.__config_manager.get(self.__name):
                raise Exception(self.STRING_ERROR_MSG.format(self.__name))

            if self.__config_manager.get(self.__name):
                if self.__type == self.FILE_TYPE:
                    if not os.path.exists(self.__config_manager.get(self.__name)):
                        raise Exception(self.FILE_ERROR_MSG.format(self.__name))
                elif self.__type == self.INTEGER_TYPE:
                    try:
                        self.__config_manager.getint(self.__name)
                    except Exception:
                        raise Exception(self.INT_ERROR_MSG.format(self.__name))

                    if self.__minvalue is not None:
                        if self.__config_manager.getint(self.__name) < self.__minvalue:
                            raise Exception(
                                self.MIN_ERROR_MSG.format(self.__name, self.__minvalue)
                            )

                    if self.__maxvalue is not None:
                        if self.__config_manager.getint(self.__name) > self.__maxvalue:
                            raise Exception(
                                self.MAX_ERROR_MSG.format(self.__name, self.__maxvalue)
                            )
                elif self.__type == self.FLOAT_TYPE:
                    try:
                        if not isinstance(
                            float(self.__config_manager.get(self.__name)), numbers.Real
                        ):
                            raise Exception()
                    except Exception:
                        raise Exception(self.FLOAT_ERROR_MSG.format(self.__name))

                    if self.__minvalue is not None:
                        if float(self.__config_manager.get(self.__name)) < float(
                            self.__minvalue
                        ):
                            raise Exception(
                                self.MIN_ERROR_MSG.format(self.__name, self.__minvalue)
                            )

                    if self.__maxvalue is not None:
                        if float(self.__config_manager.getint(self.__name)) > float(
                            self.__maxvalue
                        ):
                            raise Exception(
                                self.MAX_ERROR_MSG.format(self.__name, self.__maxvalue)
                            )
                elif self.__type == self.BOOLEAN_TYPE:
                    try:
                        bool(self.__config_manager.getint(self.__name))
                    except Exception:
                        raise Exception(self.BOOL_ERROR_MSG.format(self.__name))
                elif self.__type == self.STRING_LIST_TYPE:
                    if (
                        self.__length
                        and not len(
                            self.__config_manager.get(self.__name).split(
                                self.__delimiter
                            )
                        )
                        == self.__length
                    ):
                        raise Exception(self.LENGTH_ERROR_MSG.format(self.__name))
                elif self.__type == self.INT_LIST_TYPE:
                    if (
                        self.__length
                        and not len(
                            self.__config_manager.get(self.__name).split(
                                self.__delimiter
                            )
                        )
                        == self.__length
                    ):
                        raise Exception(self.LENGTH_ERROR_MSG.format(self.__name))
                    try:
                        [
                            int(x)
                            for x in self.__config_manager.get(self.__name).split(
                                self.__delimiter
                            )
                        ]
                    except Exception:
                        raise Exception(self.INT_LIST_ERROR_MSG.format(self.__name))

                if self.__possible:
                    if not self.__config_manager.get(self.__name) in [
                        str(value) for value in self.__possible
                    ]:
                        raise Exception(
                            self.POSSIBLE_ERROR_MSG.format(self.__name, self.__possible)
                        )

                if self.__check_function:
                    try:
                        self.__check_function(self.__config_manager.get(self.__name))
                    except Exception as exception:
                        raise Exception(
                            self.CHECK_ERROR_MSG.format(self.__name, exception)
                        )

                if self.__special:
                    try:
                        self.__special.function(
                            [
                                self.__config_manager.get(function)
                                for function in self.__special.arguments
                            ]
                        )
                    except Exception as exception:
                        if self.__special.exception_type == self.Special.EXCEPTION_TYPE:
                            raise Exception(
                                self.CHECK_ERROR_MSG.format(self.__name, exception)
                            )
                        else:
                            raise Warning(
                                self.CHECK_WARN_MSG.format(self.__name, exception)
                            )
