import json
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QObject
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.objects.template import Template


class ToolboxTemplates(QObject):
    __singleton: Optional["ToolboxTemplates"] = None
    __singleton_ready = False

    def __new__(cls, *args: VariadicArgs, **kwargs: VariadicKwargs) -> "ToolboxTemplates":
        if cls.__singleton is None:
            cls.__singleton = super().__new__(cls, *args, **kwargs)
        return cls.__singleton

    def __init__(self):
        if self.__singleton_ready:
            return

        super().__init__()
        self.__singleton_ready = True

        self.__templatePath = Path("Templates")
        self.__templates: dict[str, Template] = {}
        self.reload()

    @staticmethod
    def get_instance() -> "ToolboxTemplates":
        if ToolboxTemplates.__singleton is None:
            return ToolboxTemplates()
        return ToolboxTemplates.__singleton

    def add_template(self, template: Template):
        self.__templates[template.get_name()] = template

    def remove_template(self, template: Template):
        self.__templates.pop(template.get_name())

    def get_template(self, objname: str) -> Optional[Template]:
        if objname in self.__templates:
            return self.__templates[objname]
        return None

    def iter_templates(self) -> Iterable[Template]:
        for template in self.__templates.values():
            yield template

    def reload(self):
        from juniors_toolbox.gui.tabs import TabWidgetManager
        from juniors_toolbox.gui.tabs.console import ConsoleLogWidget

        console = TabWidgetManager.get_tab(ConsoleLogWidget)

        self.__templates.clear()
        for templateFile in self.__templatePath.iterdir():
            template = Template(templateFile.stem)
            successful = template.load(self.__templatePath)
            if not successful:
                console.error(
                    f"Error loading template {template.get_name()}"
                )
                continue
            self.__templates[template.get_name()] = template

            console.info(
                f"Successfully loaded \"{template.get_name()}\""
            )

    def load(self, template: Template):
        template.load(self.__templatePath)

    def save(self, template: Template):
        template.save(self.__templatePath)
