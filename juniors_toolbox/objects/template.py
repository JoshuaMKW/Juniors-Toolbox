import json
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import (BinaryIO, Dict, Iterable, Iterator, List, TextIO, Tuple,
                    Union)

from juniors_toolbox.objects.value import A_Member, ValueType


class AttributeInvalidError(Exception):
    ...


class ObjectTemplate():
    """
    Class representing a whole object template
    """
    TEMPLATE_PATH = Path("Templates")

    def __init__(self):
        self.name = ""
        self._attrs: List[A_Member] = []
        self._counts: Dict[str, int] = {}

        self.__eof = 0

    @classmethod
    def from_template(cls, file: Path) -> "ObjectTemplate":
        """
        Create an instance from a template file
        """
        if not file.is_file():
            return None

        this = cls()
        with file.open("r") as f:
            this.parse(f)

        return this

    def to_template(self, file: Path):
        """
        Create a template file from this instance
        """
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w") as f:
            for attribute in self:
                f.write(f"{attribute}\n")

    def get_attribute(self, name: str) -> A_Member:
        for attr in self._attrs:
            if attr.name == name:
                return attr

    def add_attribute(self, attribute: A_Member, index: int = -1):
        """
        Add an attribute to this object template
        """
        if index == -1:
            self._attrs.append(attribute)
        else:
            self._attrs.insert(index, attribute)

    def remove_attribute(self, attribute: Union[A_Member, str]) -> bool:
        """
        Remove an attribute from this object instance

        Returns True if successful
        """
        if not attribute in self:
            return False

        if isinstance(attribute, A_Member):
            self._attrs.remove(attribute)
        else:
            for attr in self._attrs:
                if attr.name == attribute:
                    self._attrs.remove(attr)
        return True

    def iter_attributes(self, deep: bool = False) -> Iterable[A_Member]:
        """
        Iterate through this object template's attributes

        `deep`: When true, also iterate through all subattributes of structs
        """
        for attribute in self._attrs:
            yield attribute
            if deep and attribute.is_struct():
                yield from attribute.iter_attributes()

    def get_count(self, attribute: Union[A_Member, str]) -> int:
        """
        Return the instance count this template has of an attribute
        """
        if isinstance(attribute, A_Member):
            attribute = attribute.name

        try:
            return self._counts[attribute]
        except KeyError:
            return 0

    def set_count(self, attribute: Union[A_Member, str], count: int) -> bool:
        """
        Set the instance count of an attribute, returns `True` if successful
        """
        if isinstance(attribute, A_Member):
            attribute = attribute.name

        if attribute in self:
            self._counts[attribute] = count
            return True
        return False

    def copy(self) -> "ObjectTemplate":
        """
        Return a copy of this template instance
        """
        new = ObjectTemplate(self)
        new.name = self.name
        return new

    # -- TEMPLATE PARSING -- #

    def parse(self, f: TextIO):
        """
        Fills this object template with the contents of a template file stream
        """
        oldpos = f.tell()
        f.seek(0, 2)
        self.__eof = f.tell()
        f.seek(oldpos, 0)

        self.name = f.readline().strip()
        while (entry := f.readline()) != "":
            attr = self.parse_attr(f, entry)
            if attr is None:
                continue
            self._attrs.append(attr)

    def parse_attr(self, f: TextIO, entry: str) -> A_Member:
        """
        Parse an attribute entry from an object template file
        """
        entry = entry.strip()
        if entry == "" or entry.startswith(("//", "#")):
            return None

        info = entry.split()

        name = info[0]
        attrtype = ValueType(info[1])
        this = A_Member(name, attrtype)

        if len(info) >= 3:
            countRefName = info[2][1:-1]
            if countRefName.isnumeric():
                this.countRef = int(countRefName)
            elif countRefName == "*":
                this.countRef = -1
            else:
                for attribute in self._attrs:
                    if attribute.name == countRefName:
                        this.countRef = attribute
                        break
                    
        if attrtype == ValueType.COMMENT:
            this.comment = info[2]
        elif attrtype == ValueType.TEMPLATE:
            while (next := f.readline().strip()) != "}":
                if f.tell() >= self.__eof:
                    raise AttributeInvalidError(
                        "Parser found EOF during struct generation!")
                this.add_attribute(self.parse_attr(f, next))

        return this

    def __len__(self) -> int:
        return len(self._attrs)

    def __contains__(self, attr: Union[A_Member, str]) -> bool:
        if isinstance(attr, A_Member):
            return attr in self._attrs
        return any([a.name == attr for a in self._attrs])
