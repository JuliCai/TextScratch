import hashlib
import os
import re
import shutil
import zipfile
from typing import Any, Dict, List, Optional, Tuple

try:  # Optional dependency for accurate image sizing
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Image = None

from .utils import ensure_dir, safe_name


def probe_image_size(path: str, ext: str) -> Optional[Tuple[float, float]]:
    ext = ext.lower()

    if ext in {"png", "jpg", "jpeg", "gif", "bmp", "webp"} and Image is not None:
        try:
            with Image.open(path) as img:
                w, h = img.size
                return float(w), float(h)
        except Exception:  # pragma: no cover - best effort
            return None

    if ext == "svg":
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read(2000)
            width_match = re.search(r"width=\"([0-9.]+)", content)
            height_match = re.search(r"height=\"([0-9.]+)", content)
            if width_match and height_match:
                return float(width_match.group(1)), float(height_match.group(1))
            viewbox_match = re.search(r"viewBox=\"[0-9.]+ [0-9.]+ ([0-9.]+) ([0-9.]+)\"", content)
            if viewbox_match:
                return float(viewbox_match.group(1)), float(viewbox_match.group(2))
        except Exception:  # pragma: no cover - best effort
            return None

    return None


def cleaned_asset_name(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    if "_" in base and base.split("_", 1)[0].isdigit():
        return base.split("_", 1)[1]
    return base


def prepare_costumes(asset_dir: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    costumes: List[Dict[str, Any]] = []
    files: List[Tuple[str, str]] = []

    if not os.path.exists(asset_dir):
        return costumes, files

    for fname in sorted(os.listdir(asset_dir)):
        path = os.path.join(asset_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        asset_id = hashlib.md5(data).hexdigest()
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        md5ext = f"{asset_id}.{ext}" if ext else asset_id

        size = probe_image_size(path, ext)
        center_x = size[0] / 2 if size else 0
        center_y = size[1] / 2 if size else 0

        bitmap_res = 1 if ext == "svg" else 2

        costumes.append(
            {
                "name": cleaned_asset_name(fname),
                "dataFormat": ext,
                "assetId": asset_id,
                "md5ext": md5ext,
                "bitmapResolution": bitmap_res,
                "rotationCenterX": center_x,
                "rotationCenterY": center_y,
            }
        )
        files.append((path, md5ext))
    return costumes, files


def prepare_sounds(asset_dir: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    sounds: List[Dict[str, Any]] = []
    files: List[Tuple[str, str]] = []

    if not os.path.exists(asset_dir):
        return sounds, files

    for fname in sorted(os.listdir(asset_dir)):
        path = os.path.join(asset_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        asset_id = hashlib.md5(data).hexdigest()
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        md5ext = f"{asset_id}.{ext}" if ext else asset_id
        sound_entry = {
            "name": cleaned_asset_name(fname),
            "assetId": asset_id,
            "dataFormat": ext,
            "rate": 0,
            "sampleCount": 0,
            "md5ext": md5ext,
        }
        sounds.append(sound_entry)
        files.append((path, md5ext))
    return sounds, files


def build_miscdata(target: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "position": {
            "x": target.get("x", 0),
            "y": target.get("y", 0),
        },
        "size": target.get("size", 100),
        "direction": target.get("direction", 90),
        "visible": target.get("visible", True),
        "rotationStyle": target.get("rotationStyle", "all around"),
        "currentCostume": target.get("currentCostume", 0),
        "draggable": target.get("draggable", False),
        "volume": target.get("volume", 100),
        "layer": target.get("layerOrder", 0),
    }


def copy_costumes(target: Dict[str, Any], archive: zipfile.ZipFile, assets_dir: str) -> None:
    ensure_dir(assets_dir)
    for idx, costume in enumerate(target.get("costumes", [])):
        md5ext = costume.get("md5ext")
        if not md5ext:
            continue
        if md5ext not in archive.namelist():
            print(f"Warning: costume asset {md5ext} not found in archive")
            continue

        ext = os.path.splitext(md5ext)[1] or f".{costume.get('dataFormat', '')}"
        name = safe_name(costume.get("name", "costume"), "costume")
        dest_name = f"{idx:02d}_{name}{ext}"
        dest_path = os.path.join(assets_dir, dest_name)

        with archive.open(md5ext) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)


def copy_sounds(target: Dict[str, Any], archive: zipfile.ZipFile, sounds_dir: str) -> None:
    ensure_dir(sounds_dir)

    if not target.get("sounds"):
        return

    for idx, sound in enumerate(target.get("sounds", [])):
        md5ext = sound.get("md5ext")
        if not md5ext:
            continue
        if md5ext not in archive.namelist():
            print(f"Warning: sound asset {md5ext} not found in archive")
            continue

        ext = os.path.splitext(md5ext)[1] or f".{sound.get('dataFormat', '')}"
        name = safe_name(sound.get("name", "sound"), "sound")
        dest_name = f"sound_{idx:02d}_{name}{ext}"
        dest_path = os.path.join(sounds_dir, dest_name)

        with archive.open(md5ext) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
