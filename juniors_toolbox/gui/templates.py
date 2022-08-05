
import json
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Tuple, Type, TypeAlias

from PySide6.QtCore import QObject
from juniors_toolbox.utils import VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.filesystem import resource_path
from juniors_toolbox.gui.tabs import TabWidgetManager
from juniors_toolbox.gui.tabs.console import ConsoleLogWidget


TemplateEnumType: TypeAlias = dict[str, Any]
TemplateStructType: TypeAlias = dict[str, Any]
TemplateMemberType: TypeAlias = dict[str, Any]
TemplateWizardType: TypeAlias = dict[str, Any]


class Template():
    def __init__(self, objName: str):
        self._objName = objName
        self._objLongName = ""
        self._enums: dict[str, TemplateEnumType] = {}
        self._structs: dict[str, TemplateStructType] = {}
        self._members: dict[str, TemplateMemberType] = {}
        self._wizards: dict[str, TemplateWizardType] = {}

    def get_name(self) -> str:
        return self._objName

    def set_name(self, objname: str):
        self._objName = objname

    def get_long_name(self) -> str:
        return self._objLongName

    def set_long_name(self, objname: str):
        self._objLongName = objname

    def get_enum(self, name: str) -> Optional[TemplateEnumType]:
        if name in self._enums:
            return self._enums[name]
        return None

    def set_enum(self, name: str, info: TemplateEnumType):
        self._enums[name] = info

    def iter_enums(self) -> Iterator[Tuple[str, TemplateEnumType]]:
        for _enum in self._enums.items():
            yield _enum

    def get_struct(self, name: str) -> Optional[TemplateStructType]:
        if name in self._structs:
            return self._structs[name]
        return None

    def set_struct(self, name: str, info: TemplateStructType):
        self._structs[name] = info

    def iter_structs(self) -> Iterator[Tuple[str, TemplateStructType]]:
        for _struct in self._structs.items():
            yield _struct

    def get_member(self, name: str) -> Optional[TemplateMemberType]:
        if name in self._members:
            return self._members[name]
        return None

    def set_member(self, name: str, info: TemplateMemberType):
        self._members[name] = info

    def iter_members(self) -> Iterator[Tuple[str, TemplateMemberType]]:
        for _member in self._members.items():
            yield _member

    def get_wizard(self, name: str) -> Optional[TemplateWizardType]:
        if name in self._wizards:
            return self._wizards[name]
        return None

    def set_wizard(self, name: str, info: TemplateWizardType):
        self._wizards[name] = info

    def iter_wizards(self) -> Iterator[Tuple[str, TemplateWizardType]]:
        for _wizard in self._wizards.items():
            yield _wizard

    def load(self, _dir: Path, /) -> bool:
        filePath = _dir / (self._objName + ".json")
        if not filePath.exists():
            return False

        try:
            with filePath.open("r", encoding="utf-8") as f:
                templateData: dict[
                    str, dict[
                        str, Any
                    ]
                ] = json.load(f)
        except Exception:
            return False

        longname, objdata = templateData.popitem()
        self.set_long_name(longname)

        enumInfo: dict[str, TemplateEnumType] = objdata["Enums"]
        structInfo: dict[str, TemplateStructType] = objdata["Structs"]
        memberInfo: dict[str, TemplateMemberType] = objdata["Members"]
        wizardInfo: dict[str, TemplateWizardType] = objdata["Wizard"]

        for name, _enum in enumInfo.items():
            for flag in _enum["Flags"]:
                _enum["Flags"][flag] = int(_enum["Flags"][flag], 0)
            self.set_enum(name, _enum)

        for name, _struct in structInfo.items():
            self.set_struct(name, _struct)

        for name, _member in memberInfo.items():
            self.set_member(name, _member)

        for name, _wizard in wizardInfo.items():
            self.set_wizard(name, _wizard)

        return True

    def save(self, _dir: Path, /):
        _enumInfo = self._enums.copy()
        for name, _enum in _enumInfo.items():
            for flag in _enum["Flags"]:
                _enum["Flags"][flag] = f"0x{_enum['Flags'][flag]}"

        templateData = {
            self.get_long_name(): {
                {"Enums": _enumInfo},
                {"Structs": self._structs},
                {"Members": self._members},
                {"Wizard": self._wizards}
            }
        }

        filePath = _dir / (self._objName + ".json")
        with filePath.open("w", encoding="utf-8") as f:
            json.dump(templateData, f, indent=4)


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
        console = TabWidgetManager.get_tab(ConsoleLogWidget)

        self.__templates.clear()
        for templateFile in self.__templatePath.iterdir():
            template = Template(templateFile.stem)
            successful = template.load(self.__templatePath)
            if not successful:
                console.error(
                    __name__,
                    f"Error loading template {template.get_name()}"
                )
                continue
            self.__templates[template.get_name()] = template

        console.info(
            __name__,
            f"Successfully loaded \"{template.get_name()}\""
        )

    def load(self, template: Template):
        template.load(self.__templatePath)

    def save(self, template: Template):
        template.save(self.__templatePath)
