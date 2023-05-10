from __future__ import annotations

import os
import importlib
from glob import glob
from typing import List
from misc.logs import Logs
from modules.base.pluginbase import PluginBase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.configmanager import ConfigManager
    from modules.pidmanager import PIDManager


class PluginsManager:

    __PLUGINS_DIR = "plugins/"
    __PLUGIN_NAME = "_plugin.py"
    __PLUGIN_CLASS = "_plugin"
    __PLUGINS = []
    __ORDER_FILE = __PLUGINS_DIR + "order.cfg"

    def __init__(
        self, path: str, pid_manager: PIDManager, logging: Logs, config: ConfigManager
    ):
        self.__config = config
        self.__pid_manager = pid_manager
        self.__logging = logging
        self.__global_path = path

        self.discover()

    def read_order(self) -> List[str]:
        orders = []
        if os.path.exists(self.__ORDER_FILE):
            with open(self.__ORDER_FILE) as file:
                orders = file.readlines()
        return [order.strip() for order in orders]

    def save_order(self, orders: List[str]):
        with open(self.__ORDER_FILE, "w") as file:
            for order in orders:
                file.write(order + "\n")

    def discover(self):
        self.__PLUGINS = []
        lists = glob(self.__PLUGINS_DIR + "**/" + self.__PLUGIN_NAME)
        modules = []
        elements = {}
        if lists and len(lists) > 0:
            for element in lists:
                path = os.path.dirname(element).replace("/", ".")
                modules.append(path)
                elements[path] = element
            modules.sort()
            orders = self.read_order()

            zipped = self.__get_locations(modules, orders)
            sorted_elements = [
                module for zipped_module, module in sorted(zip(zipped, modules))
            ]
            self.save_order(sorted_elements)
            self.__set_order(elements, sorted_elements)

    @staticmethod
    def __get_locations(modules: list, orders: list[str]) -> list[int]:
        zipped = []
        location = len(modules) + 1
        for plugin in modules:
            if plugin in orders:
                position = 0
                for order in orders:
                    if plugin == order:
                        zipped.append(position)
                        break
                    position += 1
            else:
                zipped.append(location)
                location += 1
        return zipped

    def __set_order(self, elements: dict, sorted_elements: list):
        for modules in sorted_elements:
            module = importlib.import_module(modules + "." + self.__PLUGIN_CLASS)
            self.__PLUGINS.append(
                module.Plugin(
                    os.path.join(
                        os.path.realpath(self.__global_path),
                        os.path.dirname(elements[modules]),
                    ),
                    self.__pid_manager,
                    self.__logging,
                    self.__config,
                )
            )

    def get_plugins(self) -> List[PluginBase]:
        return self.__PLUGINS

    def get_enabled(self) -> List[PluginBase]:
        return [plugin for plugin in self.__PLUGINS if plugin.is_enabled()]

    def plugin_source(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("add_photo_source")
        ]

    def get_plugin_source(self) -> List[PluginBase]:
        return [plugin for plugin in self.get_enabled() if plugin.SOURCE]

    @staticmethod
    def plugin_source_get_file(plugin: PluginBase) -> bool:
        return plugin.is_function_used("add_photo_source_get_file")

    def plugin_photos_list(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("change_photos_list")
        ]

    def plugin_preprocess(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("preprocess_photo")
        ]

    def plugin_postprocess(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("postprocess_photo")
        ]

    def plugin_api(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("extend_api")
        ]

    def plugin_website(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("add_website")
        ]

    def plugin_action(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("add_action")
        ]

    def plugin_service_thread(self) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.get_enabled()
            if plugin.is_function_used("add_service_thread")
        ]
