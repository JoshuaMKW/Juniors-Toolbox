from pyrr.aabb import create_from_bounds
from dataclasses import dataclass, field

class BMD():
    @dataclass
    class INF1():
        vertexCount: int = 0
        #sceneGraph: list[SceneGraphNode] = field(default_factory=lambda: [])

    class VTX1():
        ...

    class EVP1():
        ...

    class DRW1():
        ...

    class JNT1():
        ...

    class SHP1():
        ...

    class MAT3():
        ...

    class MDL3():
        ...

    class TEX1():
        ...
    
    def __init__(self):
        self.sectionCount = 0
        self.boundingBox = create_from_bounds(-1000, 1000)
