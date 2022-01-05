from dataclasses import dataclass
from typing import Dict


@dataclass
class VertexDescriptor:
    attributes: Dict[VertexAttribute, VertexAttributeType] = 0