import json
import struct
import sys
from pathlib import Path


def main(path_string: str) -> None:
    path = Path(path_string)
    with path.open("rb") as handle:
        magic, version, length = struct.unpack("<4sII", handle.read(12))
        if magic != b"glTF":
            raise ValueError("Not a binary glTF file")
        chunk_length, chunk_type = struct.unpack("<II", handle.read(8))
        if chunk_type != 0x4E4F534A:
            raise ValueError("The first GLB chunk is not JSON")
        document = json.loads(handle.read(chunk_length).decode("utf-8"))

    print(f"file={path.name}")
    print(f"version={version} bytes={length}")
    print(f"scenes={len(document.get('scenes', []))}")
    print(f"nodes={len(document.get('nodes', []))}")
    print(f"meshes={len(document.get('meshes', []))}")
    print(f"materials={len(document.get('materials', []))}")
    print(f"textures={len(document.get('textures', []))}")
    print(f"images={len(document.get('images', []))}")
    print(f"animations={len(document.get('animations', []))}")
    print("extensionsUsed=" + ",".join(document.get("extensionsUsed", [])))
    print("extensionsRequired=" + ",".join(document.get("extensionsRequired", [])))

    mins = []
    maxs = []
    accessors = document.get("accessors", [])
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            position_index = primitive.get("attributes", {}).get("POSITION")
            if position_index is None:
                continue
            accessor = accessors[position_index]
            if "min" in accessor and "max" in accessor:
                mins.append(accessor["min"])
                maxs.append(accessor["max"])
    if mins:
        overall_min = [min(value[i] for value in mins) for i in range(3)]
        overall_max = [max(value[i] for value in maxs) for i in range(3)]
        print(f"meshAccessorMin={overall_min}")
        print(f"meshAccessorMax={overall_max}")


if __name__ == "__main__":
    main(sys.argv[1])
