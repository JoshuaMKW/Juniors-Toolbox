import glm
from dataclasses import dataclass, field

class BMD():
    @dataclass
    class INF1():
        vertexCount: int = 0
        #sceneGraph: List[SceneGraphNode] = field(default_factory=lambda: [])

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
        self.boundingBox = glm.AABB()
