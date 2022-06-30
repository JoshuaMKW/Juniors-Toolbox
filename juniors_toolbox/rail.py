from __future__ import annotations

from dataclasses import dataclass, field
import enum
from math import cos, sin, sqrt
from typing import BinaryIO, Iterable, List, Optional, Tuple, Union
from io import BytesIO

from numpy import array, ndarray
import numpy
from juniors_toolbox.objects.value import MemberValue, ValueType

from juniors_toolbox.utils.iohelper import (align_int, read_float, read_sint16, read_string, read_uint32,
                                            write_float, write_sint16, write_string, write_uint16, write_uint32)
from juniors_toolbox.utils import JSYSTEM_PADDING_TEXT, A_Clonable, A_Serializable, VariadicArgs, VariadicKwargs
from juniors_toolbox.utils.subdivision import chaikin_generate_q_point, chaikin_generate_r_point
from juniors_toolbox.utils.types import Quaternion, Vec3f


class RailNode(A_Serializable, A_Clonable):
    def __init__(self, x: int = 0, y: int = 0, z: int = 0, *, flags: int = 0) -> None:
        super().__init__()
        self.posX = MemberValue("PositionX", x, ValueType.S16)
        self.posY = MemberValue("PositionY", y, ValueType.S16)
        self.posZ = MemberValue("PositionZ", z, ValueType.S16)

        self.connectionCount = MemberValue("Connections", 0, ValueType.S16)

        self.flags = MemberValue("Flags", flags, ValueType.U32)

        self.values = MemberValue("Value{i}", -1, ValueType.S16)
        self.values.set_array_size(4)

        self.connections = MemberValue("Connection{i}", 0, ValueType.S16)
        self.connections.set_array_size(8)

        self.periods = MemberValue("Period{i}", 0, ValueType.F32)
        self.periods.set_array_size(8)

        self._rail: Optional[Rail] = None

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs):
        posX = read_sint16(data)
        posY = read_sint16(data)
        posZ = read_sint16(data)
        connectionCount = read_sint16(data)
        flags = read_uint32(data)

        node = cls(
            posX,
            posY,
            posZ,
            flags=flags
        )

        node.connectionCount.set_value(connectionCount)

        for i in range(4):
            node.values[i].set_value(read_sint16(data))

        for i in range(8):
            node.connections[i].set_value(read_sint16(data))

        for i in range(8):
            node.periods[i].set_value(read_float(data))

        return node

    def to_bytes(self) -> bytes:
        stream = BytesIO()

        connectionCount = self.connectionCount.get_value()

        write_sint16(stream, self.posX.get_value())
        write_sint16(stream, self.posY.get_value())
        write_sint16(stream, self.posZ.get_value())

        write_sint16(stream, connectionCount)
        write_uint32(stream, self.flags.get_value())

        for i in range(4):
            write_sint16(stream, self.values[i].get_value())

        for i in range(8):
            if i < connectionCount:
                write_sint16(stream, self.connections[i].get_value())
            else:
                write_sint16(stream, 0)

        for i in range(8):
            if i < connectionCount:
                write_float(stream, self.periods[i].get_value())
            else:
                write_float(stream, 0.0)

        return stream.getvalue()

    def copy(self, *, deep: bool = False) -> "RailNode":
        """
        Return a copy of this node
        """
        _copy = RailNode(
            self.posX.get_value(),
            self.posY.get_value(),
            self.posZ.get_value(),
            flags=self.flags.get_value()
        )
        _copy.connectionCount.set_value(
            self.connectionCount.get_value()
        )
        for i in range(_copy.values.get_array_size()):
            _copy.values[i].set_value(
                self.values[i].get_value()
            )
        for i in range(_copy.connections.get_array_size()):
            _copy.connections[i].set_value(
                self.connections[i].get_value()
            )
        for i in range(_copy.periods.get_array_size()):
            _copy.periods[i].set_value(
                self.periods[i].get_value()
            )
        return _copy

    def is_connected(self) -> bool:
        if self.get_rail() is None:
            return False
        return self.connectionCount.get_value() > 0

    def is_connected_to(self, node: int | "RailNode"):
        rail = self.get_rail()
        if rail is None:
            return False

        if isinstance(node, int):
            uNode = rail.get_node(node)
            if uNode is None:
                return False
            node = uNode

        if node.get_rail() != rail:
            return False

        for i in range(self.connectionCount.get_value()):
            if self.connections[i].get_value() == node.get_index():
                return True
        return False

    def get_position(self) -> Vec3f:
        return Vec3f(
            float(self.posX.get_value()),
            float(self.posY.get_value()),
            float(self.posZ.get_value())
        )

    def set_position(self, pos: Vec3f):
        self.posX.set_value(int(pos.x))
        self.posY.set_value(int(pos.y))
        self.posZ.set_value(int(pos.z))

        rail = self.get_rail()
        if rail is None:
            return

        for slot in range(self.connectionCount.get_value()):
            node = rail.get_node(
                self.connections[slot].get_value()
            )
            if node is None:
                continue
            self._set_period_from(slot, node)

        for node in rail.iter_nodes():
            if node is self:
                continue
            for slot in range(node.connectionCount.get_value()):
                if node.connections[slot].get_value() == self.get_index():
                    node._set_period_from(slot, self)

    def get_size(self) -> int:
        return 68

    def get_rail(self) -> Optional["Rail"]:
        return self._rail

    # def set_rail(self, rail: Optional["Rail"] = None):
    #     self._rail = rail
    #     if rail is None:
    #         return
    #     rail.add_node(self)

    def get_index(self) -> int:
        rail = self.get_rail()
        if rail is None:
            return -1

        for i, node in enumerate(rail.iter_nodes()):
            if node is self:
                return i

        return -1

    def get_connection_count(self) -> int:
        return self.connectionCount.get_value()

    def set_connection_count(self, count: int):
        self.connectionCount.set_value(count)

    def get_connection(self, slot: int) -> Optional["RailNode"]:
        rail = self.get_rail()
        if rail is None:
            return None

        if slot >= self.connectionCount.get_value():
            return None

        index = self.connections[slot].get_value()
        return rail.get_node(index)

    def get_connections(self) -> list["RailNode"]:
        rail = self.get_rail()
        if rail is None:
            return []

        connections = []
        for node in rail.iter_nodes():
            if node is self:
                continue
            if node.is_connected_to(self):
                connections.append(node)

        return connections

    def get_slot(self, node: "RailNode") -> int:
        for slot in range(self.connectionCount.get_value()):
            if self.connections[slot].get_value() == node.get_index():
                return slot
        return -1

    def connect(self, srcSlot: int, node: "RailNode", dstSlot: int = -1, *, reparent: bool = False) -> bool:
        targetRail = node.get_rail()
        if targetRail is None:
            return False

        currentRail = self.get_rail()
        if currentRail != targetRail:
            if reparent is False:
                return False
            self._rail = targetRail
            self._rail.insert_node(node.get_index() + 1, self)
            
        self._connect_slots(srcSlot, node, dstSlot)
        return True

    def disconnect(self, slot: int, doubly: bool = False) -> bool:
        self._disconnect_slots(slot, doubly)
        return True

    def _set_period_from(self, slot: int, connected: "RailNode"):
        if slot not in range(8):
            raise ValueError(
                f"Slot ({slot}) is beyond the array size")

        thisPos = Vec3f(
            self.posX.get_value(),
            self.posY.get_value(),
            self.posZ.get_value()
        )
        thatPos = Vec3f(
            connected.posX.get_value(),
            connected.posY.get_value(),
            connected.posZ.get_value()
        )
        diff = thisPos - thatPos
        self.periods[slot].set_value(sqrt(diff.dot(diff)))

    def connect_to_neighbors(self) -> bool:
        rail = self.get_rail()
        if rail is None:
            return False

        thisRow = self.get_index()

        if thisRow == rail.get_node_count() - 1:
            nextRow = 0
        else:
            nextRow = thisRow + 1

        if thisRow == 0:
            prevRow = rail.get_node_count() - 1
        else:
            prevRow = thisRow - 1

        nextNode = rail.get_node(nextRow)
        prevNode = rail.get_node(prevRow)
        if nextNode is None or prevNode is None:
            print(
                f"WARNING: Couldn't connect to neighbors ({prevRow}) and ({nextRow})")
            return False

        self.connectionCount.set_value(1)

        preConnectionCount = prevNode.connectionCount.get_value()
        if preConnectionCount < 1:
            prevNode.connectionCount.set_value(1)
            preConnectionCount = 1

        if nextNode.connectionCount.get_value() < 1:
            nextNode.connectionCount.set_value(1)

        self.connect(
            srcSlot=0,
            node=prevNode,
            dstSlot=preConnectionCount - 1
        )
        self.connect(
            srcSlot=1,
            node=nextNode,
            dstSlot=0
        )

        return True

    def connect_to_prev(self) -> bool:
        rail = self.get_rail()
        if rail is None:
            return False

        thisRow = self.get_index()

        if thisRow == 0:
            prevRow = rail.get_node_count() - 1
        else:
            prevRow = thisRow - 1

        prevNode = rail.get_node(prevRow)
        if prevNode is None:
            print(f"WARNING: Couldn't connect to previous node ({prevRow})")
            return False

        self.connectionCount.set_value(1)
        preConnectionCount = prevNode.connectionCount.get_value()
        if preConnectionCount < 1:
            prevNode.connectionCount.set_value(1)
            preConnectionCount = 1

        self.connect(
            srcSlot=0,
            node=prevNode
        )

        return True

    def connect_to_next(self) -> bool:
        rail = self.get_rail()
        if rail is None:
            return False

        thisRow = self.get_index()

        if thisRow == rail.get_node_count() - 1:
            nextRow = 0
        else:
            nextRow = thisRow + 1

        nextNode = rail.get_node(nextRow)
        if nextNode is None:
            print(f"WARNING: Couldn't connect to next node ({nextRow})")
            return False

        self.connectionCount.set_value(1)
        if nextNode.connectionCount.get_value() < 1:
            nextNode.connectionCount.set_value(1)

        self.connect(
            srcSlot=0,
            node=nextNode
        )

        return True

    def connect_to_referring(self) -> bool:
        rail = self.get_rail()
        if rail is None:
            return False

        connectionCount = self.connectionCount.get_value()
        connectionIndex = connectionCount

        existingConnections = []
        for i in range(connectionCount):
            existingConnections.append(self.connections[i].get_value())

        index = self.get_index()
        for row in range(rail.get_node_count()):
            if connectionIndex > 7:
                break

            if row == index or row in existingConnections:
                continue

            otherNode = rail.get_node(row)
            if otherNode is None:
                print(f"WARNING: Couldn't connect to referring node ({row})")
                continue

            for i in range(otherNode.connectionCount.get_value()):
                connection = otherNode.connections[i].get_value()
                if connection == index:
                    self.connections[connectionIndex].set_value(row)
                    self._set_period_from(connectionIndex, otherNode)
                    self.connectionCount.set_value(connectionIndex + 1)
                    connectionIndex += 1

        return True

    def _connect_slots(self, srcSlot: int, node: "RailNode", dstSlot: int) -> None:
        dstValid = dstSlot != -1

        if srcSlot not in range(8):
            raise ValueError(f"Source slot {srcSlot} exceeds capacity (8)")

        if dstSlot not in range(8) and dstValid:
            raise ValueError(
                f"Destination slot {dstSlot} exceeds capacity (8)")

        if not self.is_connected_to(node):
            self.connections[srcSlot].set_value(node.get_index())
            if srcSlot >= self.connectionCount.get_value():
                self.connectionCount.set_value(srcSlot + 1)
            self._set_period_from(srcSlot, node)

        if not node.is_connected_to(self) and dstValid:
            node.connections[dstSlot].set_value(self.get_index())
            if dstSlot >= node.connectionCount.get_value():
                node.connectionCount.set_value(dstSlot + 1)
            node._set_period_from(dstSlot, self)

    def _disconnect_slots(self, srcSlot: int, doubly: bool = False) -> None:
        if srcSlot not in range(8):
            raise ValueError(f"Source slot {srcSlot} exceeds capacity (8)")

        if doubly:
            dstIndex = self.connections[srcSlot].get_value()
            for node in self.get_connections():
                if node.get_index() == dstIndex:
                    for i in range(node.connectionCount.get_value()):
                        connection = node.connections[i]
                        if connection.get_value() == self.get_index():
                            connection.set_value(0)
        self.connections[srcSlot].set_value(0)

    def __len__(self) -> int:
        return 68


class Rail(A_Serializable, A_Clonable):
    def __init__(self, name: str, nodes: Optional[list[RailNode]] = None):
        if nodes is None:
            nodes = []

        self.name = name
        self._nodes = nodes

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["Rail"]:
        """
        Returns a Rail from the given data
        """
        size = read_uint32(data)
        if size == 0:
            return None

        namePos = read_uint32(data)
        dataPos = read_uint32(data)
        _oldPos = data.tell()  # Preserve position

        this = cls(read_string(data, offset=namePos))

        data.seek(dataPos)
        for _ in range(size):
            this.add_node(RailNode.from_bytes(data))

        data.seek(_oldPos)
        return this

    def to_bytes(self) -> bytes:
        """
        Stores the data form of this Rail
        """
        data = BytesIO()
        self.save(data, 0, 0, 0)
        return data.getvalue()

    def copy(self, *, deep: bool = False) -> "Rail":
        copy = Rail(self.name)
        for node in self._nodes:
            copy._nodes.append(node.copy(deep=deep))
        return copy

    def is_spline(self) -> bool:
        return self.name.startswith("S_")

    def get_size(self) -> int:
        return self.get_header_size() + self.get_name_size() + self.get_data_size()

    def get_centeroid(self) -> Vec3f:
        nodeCount = self.get_node_count()
        if nodeCount == 0:
            return Vec3f()

        xs, ys, zs = [], [], []
        for node in self.iter_nodes():
            xs.append(node.posX.get_value())
            ys.append(node.posY.get_value())
            zs.append(node.posZ.get_value())

        return Vec3f(
            sum(xs) / nodeCount,
            sum(ys) / nodeCount,
            sum(zs) / nodeCount,
        )

    def get_header_size(self) -> int:
        return 12

    def get_name_size(self) -> int:
        return len(self.name) + 1

    def get_data_size(self) -> int:
        return 68 * len(self._nodes)

    def get_node_count(self) -> int:
        return len(self._nodes)

    def iter_nodes(self) -> Iterable[RailNode]:
        for node in self._nodes:
            yield node

    def get_nodes(self) -> list[RailNode]:
        return self._nodes

    def get_node(self, index: int) -> Optional["RailNode"]:
        if index not in range(len(self._nodes)):
            return None
        return self._nodes[index]

    def add_node(self, node: RailNode):
        self._nodes.append(node)
        node._rail = self

    def insert_node(self, index: int, node: RailNode) -> bool:
        try:
            self._nodes.insert(index, node)
            node._rail = self
        except IndexError:
            return False
        finally:
            return True

    def remove_node(self, node: RailNode) -> bool:
        try:
            self._nodes.remove(node)
        except ValueError:
            return False
        finally:
            return True

    def swap_nodes(self, index1: int, index2: int) -> bool:
        """
        Swaps two nodes in this rail

        Returns True if successful
        """
        try:
            node1 = self._nodes[index1]
            node2 = self._nodes[index2]
            self._nodes[index1] = node2
            self._nodes[index2] = node1
            return True
        except IndexError:
            return False

    def remove_node_by_index(self, index: int) -> bool:
        """
        Removes a node at `index` from this rail
        """
        try:
            self._nodes.pop(index)
            return True
        except IndexError:
            return False

    def save(self, data: BinaryIO, headerloc: int, nameloc: int, dataloc: int):
        """
        Stores the data form of this Rail
        """
        data.seek(headerloc, 0)
        write_uint32(data, len(self._nodes))
        write_uint32(data, nameloc)
        write_uint32(data, dataloc)

        data.seek(nameloc, 0)
        write_string(data, self.name)

        data.seek(dataloc)
        for node in self._nodes:
            data.write(node.to_bytes())

    def translate(self, translation: Vec3f) -> "Rail":
        _x = int(translation.x)
        _y = int(translation.y)
        _z = int(translation.z)

        if 32767 < _x < -32768:
            raise ValueError(
                f"Translation on X axis ({_x}) not in range -32768 <> 32767")
        if 32767 < _y < -32768:
            raise ValueError(
                f"Translation on Y axis ({_y}) not in range -32768 <> 32767")
        if 32767 < _z < -32768:
            raise ValueError(
                f"Translation on Z axis ({_z}) not in range -32768 <> 32767")

        for node in self.iter_nodes():
            node.posX.set_value(node.posX.get_value() + _x)
            node.posY.set_value(node.posY.get_value() + _y)
            node.posZ.set_value(node.posZ.get_value() + _z)

        return self

    def invert(self, *, x: bool, y: bool, z: bool) -> "Rail":
        if not any([x, y, z]):
            return self

        centeroid = self.get_centeroid()
        for node in self.iter_nodes():
            if x:
                diffX = node.posX - centeroid.x
                node.posX.set_value(node.posX.get_value() + (diffX * 2))
            if y:
                diffY = node.posY - centeroid.y
                node.posY.set_value(node.posY.get_value() + (diffY * 2))
            if z:
                diffZ = node.posZ - centeroid.z
                node.posZ.set_value(node.posZ.get_value() + (diffZ * 2))

        return self

    def rotate(self, rotation: Quaternion) -> "Rail":
        euler = rotation.to_euler()

        cosa = cos(euler.x)
        sina = sin(euler.x)

        cosb = cos(euler.y)
        sinb = sin(euler.y)

        cosc = cos(euler.z)
        sinc = sin(euler.z)

        Axx = cosa*cosb
        Axy = cosa*sinb*sinc - sina*cosc
        Axz = cosa*sinb*cosc + sina*sinc

        Ayx = sina*cosb
        Ayy = sina*sinb*sinc + cosa*cosc
        Ayz = sina*sinb*cosc - cosa*sinc

        Azx = -sinb
        Azy = cosb*sinc
        Azz = cosb*cosc

        for node in self.iter_nodes():
            px = node.posX.get_value()
            py = node.posY.get_value()
            pz = node.posZ.get_value()

            node.posX.set_value(int(Axx*px) + int(Axy*py) + int(Axz*pz))
            node.posY.set_value(int(Ayx*px) + int(Ayy*py) + int(Ayz*pz))
            node.posZ.set_value(int(Azx*px) + int(Azy*py) + int(Azz*pz))

        return self

    def scale(self, scale: Vec3f) -> "Rail":
        centeroid = self.get_centeroid()

        for node in self.iter_nodes():
            px = node.posX.get_value()
            py = node.posY.get_value()
            pz = node.posZ.get_value()

            px -= centeroid.x
            py -= centeroid.y
            pz -= centeroid.z

            px *= scale.x
            py *= scale.y
            pz *= scale.z

            px += centeroid.x
            py += centeroid.y
            pz += centeroid.z

            node.posX.set_value(px)
            node.posY.set_value(py)
            node.posZ.set_value(pz)

        return self

    def subdivide(self, iterations=5) -> "Rail":
        self._chaikin_algorithm(iterations)
        return self

    def _chaikin_algorithm(self, iterations: int = 5):
        "Curve creation algoritm"
        if iterations == 0:
            return

        nodeCount = self.get_node_count()
        if nodeCount < 3:
            return

        nodeVisitedMap: dict[RailNode, bool] = {}

        newNodes: list[RailNode] = []
        oldNodes = self.get_nodes()
        startNode = oldNodes[0].copy(deep=True)
        endNode = oldNodes[-1].copy(deep=True)

        i = 0
        thisNode = oldNodes[0]
        while True:  # Continue processing until all nodes are traversed
            if nodeVisitedMap.get(thisNode, False):
                i += 1
                if i >= len(oldNodes):
                    break  # All possible nodes traversed
                thisNode = oldNodes[i]
                continue

            connectionCount = thisNode.connectionCount.get_value()

            # Single connection means this is likely an end point and thus shouldn't be curved
            if connectionCount == 1:
                nodeVisitedMap[thisNode] = True
                nextNode = thisNode.get_connection(0)
                if nextNode is None:
                    i += 1
                    if i >= len(oldNodes):
                        break  # All possible nodes traversed
                    thisNode = oldNodes[i]
                else:
                    thisNode = nextNode
                continue

            # Traverse every connected slot of this node
            qNode = thisNode
            for slot in range(connectionCount):
                otherNode = thisNode.get_connection(slot)
                if otherNode is None:
                    continue

                rNode = qNode.copy(deep=True)

                qNodePos = Vec3f(
                    float(qNode.posX.get_value()),
                    float(qNode.posY.get_value()),
                    float(qNode.posZ.get_value())
                )

                rNodePos = Vec3f(
                    float(otherNode.posX.get_value()),
                    float(otherNode.posY.get_value()),
                    float(otherNode.posZ.get_value())
                )

                qNode.set_position(
                    chaikin_generate_q_point(qNodePos, rNodePos)
                )

                rNode.set_position(
                    chaikin_generate_r_point(qNodePos, rNodePos)
                )

                rNode.set_connection_count(2)

                # Read slots before insertion to maintain data
                nextSlot = thisNode.get_slot(otherNode)
                thisSlot = otherNode.get_slot(thisNode)

                self.insert_node(qNode.get_index() + int(slot > 0), rNode)

                rNode.connect(0, thisNode, nextSlot)
                rNode.connect(1, otherNode,thisSlot)
                rNode.values[3].set_value(1111)

                nodeVisitedMap[rNode] = True
            nodeVisitedMap[qNode] = True
            
        # for i, node in enumerate(oldNodes[1:], start=1):
        #     if i + 1 >= nodeCount:
        #         endNode = oldNodes[i]
        #         break

        #     qNode = node.copy(deep=True)


        #     connectionCount = node.connectionCount.get_value()
        #     if connectionCount != 2:
        #         continue

        #     nextNode = node.get_connection(1)
        #     if nextNode is None or nodeVisitedMap.get(nextNode, False) is True:
        #         continue

        #     qNode = node
        #     rNode = RailNode(
        #         flags=qNode.flags.get_value()
        #     )

        #     nodePos = Vec3f(
        #         float(node.posX.get_value()),
        #         float(node.posY.get_value()),
        #         float(node.posZ.get_value())
        #     )

        #     nextNodePos = Vec3f(
        #         float(nextNode.posX.get_value()),
        #         float(nextNode.posY.get_value()),
        #         float(nextNode.posZ.get_value())
        #     )

        #     rNode.set_connection_count(2)
        #     rNode.connect(0, qNode, 1, reparent=True)
        #     rNode.connect(1, nextNode, nextNode.get_slot(qNode))
        #     rNode.values[3].set_value(1234)

        #     qNode.set_position(
        #         chaikin_generate_q_point(nodePos, nextNodePos)
        #     )
        #     rNode.set_position(
        #         chaikin_generate_r_point(nodePos, nextNodePos)
        #     )

        #     # newNodes.append(rNode)
        #     # if slot == 0:
        #     #     newNodes.append(qNode)
                

        #     # nodeVisitedMap[qNode] = True
        #     nodeVisitedMap[rNode] = True

        #     # for slot in range(connectionCount):
        #     #     nextNode = node.get_connection(slot)
        #     #     if nextNode is None or nodeVisitedMap.get(nextNode, False) is True:
        #     #         continue

        #     #     nodePos = Vec3f(
        #     #         float(node.posX.get_value()),
        #     #         float(node.posY.get_value()),
        #     #         float(node.posZ.get_value())
        #     #     )

        #     #     nextNodePos = Vec3f(
        #     #         float(nextNode.posX.get_value()),
        #     #         float(nextNode.posY.get_value()),
        #     #         float(nextNode.posZ.get_value())
        #     #     )

        #     #     rNode = RailNode(
        #     #         flags=qNode.flags.get_value()
        #     #     )

        #     #     rNode.set_connection_count(2)
        #     #     rNode.connect(0, qNode, slot)
        #     #     rNode.connect(1, nextNode, nextNode.get_slot(qNode))

        #     #     qNode.set_position(
        #     #         chaikin_generate_q_point(nodePos, nextNodePos)
        #     #     )
        #     #     rNode.set_position(
        #     #         chaikin_generate_r_point(nodePos, nextNodePos)
        #     #     )

        #     #     newNodes.append(rNode)

        #     #     # nodeVisitedMap[qNode] = True
        #     #     nodeVisitedMap[rNode] = True

        # self._nodes = newNodes
        self._chaikin_algorithm(iterations - 1)

    def __len__(self) -> int:
        return self.get_size()


class RalData(A_Serializable):
    def __init__(self, rails: Optional[list[Rail]] = None):
        if rails is None:
            rails = []

        self._rails = rails

    @classmethod
    def from_bytes(cls, data: BinaryIO, *args: VariadicArgs, **kwargs: VariadicKwargs) -> Optional["RalData"]:
        this = cls()
        while (rail := Rail.from_bytes(data)) is not None:
            this._rails.append(rail)
        return this

    def to_bytes(self) -> bytes:
        headerloc = self.get_header_start()
        nameloc = self.get_name_start()
        dataloc = self.get_data_start()

        data = BytesIO()
        for rail in self._rails:
            rail.save(data, headerloc, nameloc, dataloc)
            headerloc += rail.get_header_size()
            nameloc += rail.get_name_size()
            dataloc += rail.get_data_size()

        data.seek(headerloc)
        data.write(b"\x00"*12)
        return data.getvalue()

    def get_size(self) -> int:
        return align_int(sum([r.get_size() for r in self._rails]), 32)

    def get_header_start(self) -> int:
        return 0

    def get_name_start(self) -> int:
        return sum([r.get_header_size() for r in self._rails]) + 12

    def get_data_start(self) -> int:
        return align_int(sum([r.get_header_size() + r.get_name_size() for r in self._rails]), 4) + 12

    def iter_rails(self) -> Iterable[Rail]:
        for rail in self._rails:
            yield rail

    def get_rails(self) -> list[Rail]:
        return self._rails

    def get_rail(self, name: str) -> Optional[Rail]:
        for rail in self._rails:
            if rail.name == name:
                return rail
        return None

    def get_rail_by_index(self, index: int) -> Optional[Rail]:
        try:
            return self._rails[index]
        except IndexError:
            return None

    def set_rail(self, rail: Rail):
        for i, r in enumerate(self._rails):
            if r.name == rail.name:
                self._rails[i] = rail
                return
        self._rails.append(rail)

    def set_rail_by_index(self, index: int, rail: Rail) -> bool:
        try:
            self._rails[index] = rail
            return True
        except IndexError:
            return False

    def rename_rail(self, name: str, new: str) -> bool:
        for r in self._rails:
            if r.name == name:
                r.name = new
                return True
        return False

    def remove_rail(self, name: str) -> bool:
        for r in self._rails:
            if r.name == name:
                self._rails.remove(r)
                return True
        return False

    def _get_node_name(self, index: int, node: RailNode):
        connections = []
        for x in range(node.connectionCount.get_value()):
            connections.append(node.connections[x].get_value())
        name = f"Node {index} - {connections}"
        return name

    def __len__(self) -> int:
        return self.get_size()

    def __contains__(self, other: Union[str, Rail]) -> bool:
        if isinstance(other, Rail):
            return other in self._rails
        return any([r.name == other for r in self._rails])
