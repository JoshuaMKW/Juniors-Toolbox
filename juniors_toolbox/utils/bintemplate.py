

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

from juniors_toolbox.objects.value import ValueType


_TYPE_DEFAULT_LUT = {
    ValueType.BOOL: False,
    ValueType.BYTE: 0,
    ValueType.CHAR: 0,
    ValueType.S8: 0,
    ValueType.U8: 0,
    ValueType.SHORT: 0,
    ValueType.S16: 0,
    ValueType.U16: 0,
    ValueType.S32: 0,
    ValueType.INT: 0,
    ValueType.U32: 0,
    ValueType.F32: 0,
    ValueType.FLOAT: 0,
    ValueType.F64: 0,
    ValueType.DOUBLE: 0,
    ValueType.STR: "Generated from Bin Editor Template by Junior's Toolbox",
    ValueType.STRING: "Generated from Bin Editor Template by Junior's Toolbox",
    ValueType.C_RGB8: [255, 255, 255],
    ValueType.C_RGBA8: [255, 255, 255, 255],
    ValueType.C_RGB32: [255, 255, 255],
    ValueType.C_RGBA: [255, 255, 255, 255],
    ValueType.VECTOR3: [0, 0, 0],
    ValueType.TRANSFORM: [
        [0, 0, 0],
        [0, 0, 0],
        [1, 1, 1]
    ],
    ValueType.COMMENT: "Generated from Bin Editor Template by Junior's Toolbox",
    ValueType.STRUCT: {}
}


@dataclass
class _BinEditorEntry:
    name: str
    kind: str
    comment: Optional[str] = None


def convert_bin_to_toolbox(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False

    toolboxPath = (dst / src.name).with_suffix(".json")

    entries: list[_BinEditorEntry] = []
    template = src.read_text()
    objName, templateData = template.split("\n", 1)
    for line in templateData.splitlines():
        name, *info = line.split(" ")
        if len(info) > 2:
            entries.append(_BinEditorEntry(name, "STRUCT"))
        else:
            entries.append(_BinEditorEntry(name, *info))

    objDict: dict[str, dict[str, dict]] = {
        objName: {
            "Structs": {},
            "Members": {},
            "Wizard": {
                "Default": {}
            }
        }
    }
    membersDict = objDict[objName]["Members"]
    wizardDict = objDict[objName]["Wizard"]["Default"]

    for entry in entries:
        membersDict[entry.name] = {
            "Type": entry.kind,
            "ArraySize": 1,
        }
        wizardDict[entry.name] = _TYPE_DEFAULT_LUT[ValueType(entry.kind)]
        

    toolboxPath.parent.mkdir(parents=True, exist_ok=True)
    with toolboxPath.open("w") as f:
        json.dump(objDict, f, indent=4)

    return True
