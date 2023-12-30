import pytest
from misc.configproperty import ConfigProperty
from modules.base.configbase import ConfigBase
from tests.helpers.helpers import remove_file, not_raises, set_file

filename = "config_test.cfg"


def test_getters():
    test_property = "test_property"
    test_value = "test_value"

    set_file(
        "\n".join(
            [
                "[test_section]",
                f"{test_property}={test_value}",
                f"{test_property}2=1",
            ]
        ),
        filename,
    )

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    test_property,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    not_empty=True,
                    dependency=[f"{test_property}2", 1],
                    minvalue=1,
                    maxvalue=100,
                    possible=[test_value],
                    reset_needed=True,
                ),
                ConfigProperty(
                    f"{test_property}2",
                    self,
                    prop_type=ConfigProperty.BOOLEAN_TYPE,
                ),
            ]

    config = ConfigTest(filename, filename)
    property_object = config.get_property(test_property)
    assert property_object.get_default() == test_value
    assert property_object.get_type() == ConfigProperty.STRING_TYPE
    assert property_object.get_dependency() == f"{test_property}2"
    assert property_object.get_dependency_value() == 1
    assert property_object.get_min() == 1
    assert property_object.get_max() == 100
    assert property_object.get_possible() == [test_value]
    assert property_object.get_name() == test_property
    assert property_object.get_reset_needed() is True
    remove_file(filename)


def test_convert():
    test_property = "test_property"
    test_value = "test_value"
    set_properties(test_property, test_value)

    def convert_test(value: str = None):
        return test_property

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    test_property,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    convert=convert_test,
                ),
            ]

    config = ConfigTest(filename, filename)
    property_object = config.get_property(test_property)
    property_object.convert()
    assert config.get(test_property) == test_property
    remove_file(filename)


@pytest.mark.parametrize(
    "value, property_type",
    [
        ("value", ConfigProperty.INTEGER_TYPE),
        ("value", ConfigProperty.FLOAT_TYPE),
        ("", ConfigProperty.STRING_TYPE),
        ("value", ConfigProperty.BOOLEAN_TYPE),
        ("non_existing_file.file", ConfigProperty.FILE_TYPE),
        ("", ConfigProperty.STRING_LIST_TYPE),
        ("value", ConfigProperty.INT_LIST_TYPE),
        ("", ConfigProperty.PASSWORD_TYPE),
    ],
)
def test_verify_property_nok(value, property_type):
    config = get_config("property", value, property_type)
    verify_nok(config)


@pytest.mark.parametrize(
    "value, property_type",
    [
        (8, ConfigProperty.INTEGER_TYPE),
        (2.1, ConfigProperty.FLOAT_TYPE),
        ("value", ConfigProperty.STRING_TYPE),
        (1, ConfigProperty.BOOLEAN_TYPE),
        (filename, ConfigProperty.FILE_TYPE),
        ("one two", ConfigProperty.STRING_LIST_TYPE),
        ("1 2 3", ConfigProperty.INT_LIST_TYPE),
        ("password", ConfigProperty.PASSWORD_TYPE),
    ],
)
def test_verify_property_ok(value, property_type):
    config = get_config("property", value, property_type)
    verify_ok(config)


def test_verify_property_empty_nok():
    config = get_config("property", "", ConfigProperty.STRING_TYPE)
    verify_nok(config)


def test_verify_property_empty_ok():
    config = get_config("property", "not_empty", ConfigProperty.STRING_TYPE)
    verify_ok(config)


def test_verify_property_min_nok():
    config = get_config_min("property", 0, 1, ConfigProperty.INTEGER_TYPE)
    verify_nok(config)


def test_verify_property_min_ok():
    config = get_config_min("property", 1, 1, ConfigProperty.INTEGER_TYPE)
    verify_ok(config)


def test_verify_property_max_nok():
    config = get_config_max("property", 100, 99, ConfigProperty.INTEGER_TYPE)
    verify_nok(config)


def test_verify_property_max_ok():
    config = get_config_max("property", 99, 99, ConfigProperty.INTEGER_TYPE)
    verify_ok(config)


def test_verify_property_float_min_nok():
    config = get_config_min("property", 0.1, 1.1, ConfigProperty.FLOAT_TYPE)
    verify_nok(config)


def test_verify_property_float_min_ok():
    config = get_config_min("property", 1.1, 1.1, ConfigProperty.FLOAT_TYPE)
    verify_ok(config)


def test_verify_property_float_max_nok():
    config = get_config_max("property", 100.1, 99.1, ConfigProperty.FLOAT_TYPE)
    verify_nok(config)


def test_verify_property_float_max_ok():
    config = get_config_max("property", 99.1, 99.1, ConfigProperty.FLOAT_TYPE)
    verify_ok(config)


def test_verify_property_delimiter_nok():
    config = get_config_delimiter(
        "property", "value1;value2", ConfigProperty.STRING_LIST_TYPE, ","
    )
    verify_nok(config)


def test_verify_property_delimiter_ok():
    config = get_config_delimiter(
        "property", "value1,value2", ConfigProperty.STRING_LIST_TYPE, ","
    )
    verify_ok(config)


def test_verify_property_delimiter_integer_nok():
    config = get_config_delimiter("property", "1;2", ConfigProperty.INT_LIST_TYPE, ",")
    verify_nok(config)


def test_verify_property_delimiter_integer_ok():
    config = get_config_delimiter("property", "1,2", ConfigProperty.INT_LIST_TYPE, ",")
    verify_ok(config)


def test_verify_property_length_nok():
    config = get_config_delimiter(
        "property", "value1,value2,value3", ConfigProperty.STRING_LIST_TYPE, ","
    )
    verify_nok(config)


def test_verify_property_length_ok():
    config = get_config_delimiter(
        "property", "value1,value2", ConfigProperty.STRING_LIST_TYPE, ","
    )
    verify_ok(config)


def test_verify_property_length_integer_nok():
    config = get_config_delimiter(
        "property", "1,2,3", ConfigProperty.INT_LIST_TYPE, ","
    )
    verify_nok(config)


def test_verify_property_length_integer_ok():
    config = get_config_delimiter("property", "1,2", ConfigProperty.INT_LIST_TYPE, ",")
    verify_ok(config)


def test_dependency_nok():
    config = get_config_dependency("property", "", 0, "property2")
    verify_ok(config)


def test_dependency_ok():
    config = get_config_dependency("property", "", 1, "property2")
    verify_nok(config)


def test_dependency_list_nok():
    config = get_config_dependency("property", "", 0, ["property2", "1"])
    verify_ok(config)


def test_dependency_list_ok():
    config = get_config_dependency("property", "", 1, ["property2", "1"])
    verify_nok(config)


def test_possible_nok():
    config = get_config_possible("property", "not_exists", ["value1", "value2"])
    verify_nok(config)


def test_possible_ok():
    config = get_config_possible("property", "value1", ["value1", "value2"])
    verify_ok(config)


def test_check_function_nok():
    def check_function(value):
        raise Exception("Check failed!")

    config = get_config_check_function("property", "value", check_function)
    verify_nok(config)


def test_check_function_warning_nok():
    def check_function(value):
        raise Warning("Check failed!")

    config = get_config_check_function("property", "value", check_function)
    with pytest.raises(Warning):
        config.verify()
    remove_file(filename)


def test_check_function_ok():
    def check_function(value):
        print("Check successful!")

    config = get_config_check_function("property", "value", check_function)
    verify_ok(config)


def test_convert_function():
    property_name = "property"
    value = "value"
    new_value = "new_value"

    set_properties(property_name, value)

    def convert(property_value):
        return new_value

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    convert=convert,
                ),
            ]

    config = ConfigTest(filename, filename)
    assert config.get(property_name) != value
    assert config.get(property_name) == new_value


def test_special_nok():
    def special_function(values):
        raise Exception("Special function failed!")

    special = ConfigProperty.Special(special_function, ["property2", "property3"])
    config = get_config_special("property", "value", special)
    verify_nok(config)


def test_special_ok():
    def special_function(values):
        print("Special function successful!")

    special = ConfigProperty.Special(special_function, ["property2", "property3"])
    config = get_config_special("property", "value", special)
    verify_ok(config)


def test_special_warning():
    def special_function(values):
        raise Exception("Special function failed!")

    special = ConfigProperty.Special(
        special_function,
        ["property2", "property3"],
        exception_type=ConfigProperty.Special.WARNING_TYPE,
    )
    config = get_config_special("property", "value", special)
    with pytest.raises(Warning):
        config.verify()
    remove_file(filename)


def verify_ok(config):
    with not_raises(Exception):
        config.verify()
    remove_file(filename)


def verify_nok(config):
    with pytest.raises(Exception):
        config.verify()
    remove_file(filename)


def get_config(property_name, value, property_type):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name, self, prop_type=property_type, not_empty=True
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_min(property_name, value, min_value, property_type):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=property_type,
                    minvalue=min_value,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_max(property_name, value, max_value, property_type):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=property_type,
                    maxvalue=max_value,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_delimiter(property_name, value, property_type, delimiter):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=property_type,
                    delimiter=delimiter,
                    length=2,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_dependency(property_name, value, dependency_value, dependency):
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"{property_name}={value}",
                f"{property_name}2={dependency_value}",
            ]
        ),
        filename,
    )

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    not_empty=True,
                    dependency=dependency,
                ),
                ConfigProperty(
                    f"{property_name}2",
                    self,
                    prop_type=ConfigProperty.BOOLEAN_TYPE,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_possible(property_name, value, possible_values):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    possible=possible_values,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_check_function(property_name, value, check_function):
    set_properties(property_name, value)

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    check_function=check_function,
                ),
            ]

    return ConfigTest(filename, filename)


def get_config_special(property_name, value, special):
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"{property_name}={value}",
                f"{property_name}2={value}2",
                f"{property_name}3={value}3",
            ]
        ),
        filename,
    )

    class ConfigTest(ConfigBase):
        def load_settings(self):
            self.SETTINGS = [
                ConfigProperty(
                    property_name,
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                    special=special,
                ),
                ConfigProperty(
                    f"{property_name}2",
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                ),
                ConfigProperty(
                    f"{property_name}3",
                    self,
                    prop_type=ConfigProperty.STRING_TYPE,
                ),
            ]

    return ConfigTest(filename, filename)


def set_properties(property_name, value):
    set_file(
        "\n".join(
            [
                "[test_section]",
                f"{property_name}={value}",
            ]
        ),
        filename,
    )
