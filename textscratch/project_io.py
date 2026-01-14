import json
import os
import shutil
import zipfile
from typing import Any, Dict, List, Tuple

from .assets import (
    build_miscdata,
    copy_costumes,
    copy_sounds,
    prepare_costumes,
    prepare_sounds,
)
from .blocks_to_text import generate_target_code
from .layout import auto_arrange_top_blocks
from .text_to_blocks import code_to_blocks
from .utils import ensure_dir, gen_id, load_json_file, safe_name, write_json_file


def build_variables_payload(entries: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Any]], Dict[str, str]]:
    var_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    for entry in entries:
        name = entry.get("name", "variable")
        value = entry.get("value", 0)
        vid = gen_id("var")
        name_to_id[name] = vid
        payload: List[Any] = [name, value]
        if entry.get("cloud"):
            payload.append(True)
        var_dict[vid] = payload
    return var_dict, name_to_id


def build_lists_payload(entries: List[Dict[str, Any]]) -> Tuple[Dict[str, List[Any]], Dict[str, str]]:
    list_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    for entry in entries:
        name = entry.get("name", "list")
        value = entry.get("value", [])
        lid = gen_id("list")
        name_to_id[name] = lid
        list_dict[lid] = [name, value]
    return list_dict, name_to_id


def convert_variables_dict(variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for _, payload in variables.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            entry: Dict[str, Any] = {"name": name, "value": value}
            if len(payload) >= 3 and payload[2] is True:
                entry["cloud"] = True
            result.append(entry)
    return result


def convert_lists_dict(lists: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for _, payload in lists.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            result.append({"name": name, "value": value})
    return result


def write_variables_file(path: str, target: Dict[str, Any]) -> None:
    payload = {
        "variables": convert_variables_dict(target.get("variables", {})),
        "lists": convert_lists_dict(target.get("lists", {})),
    }
    write_json_file(path, payload)


def collect_broadcasts(targets: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for target in targets:
        for _, name in target.get("broadcasts", {}).items():
            if name not in names:
                names.append(name)
    return names


def write_events_file(path: str, broadcasts: List[str]) -> None:
    write_json_file(path, {"broadcasts": broadcasts})


def write_target(target: Dict[str, Any], archive: zipfile.ZipFile, output_root: str) -> None:
    is_stage = target.get("isStage", False)
    target_name = target.get("name", "Sprite")

    if is_stage:
        target_dir = os.path.join(output_root, "Stage")
    else:
        sprites_root = os.path.join(output_root, "Sprites")
        ensure_dir(sprites_root)
        target_dir = os.path.join(sprites_root, safe_name(target_name, "Sprite"))

    ensure_dir(target_dir)

    code_path = os.path.join(target_dir, "code.scratchblocks")
    code_text = generate_target_code(target)
    with open(code_path, "w", encoding="utf-8") as handle:
        handle.write(code_text)

    if not is_stage:
        write_variables_file(os.path.join(target_dir, "variables.json"), target)
        write_json_file(os.path.join(target_dir, "miscdata.json"), build_miscdata(target))

    assets_dir = os.path.join(target_dir, "Assets")
    sounds_dir = os.path.join(target_dir, "Sounds")
    copy_costumes(target, archive, assets_dir)
    copy_sounds(target, archive, sounds_dir)


def convert_project(sb3_path: str, output_dir: str, clean: bool = True) -> None:
    if not os.path.exists(sb3_path):
        print(f"Error: {sb3_path} not found")
        return

    with zipfile.ZipFile(sb3_path, "r") as archive:
        if "project.json" not in archive.namelist():
            print("Error: project.json not found in the archive.")
            return

        with archive.open("project.json") as handle:
            project = json.load(handle)

        if clean and os.path.exists(output_dir):
            shutil.rmtree(output_dir)

        ensure_dir(output_dir)
        ensure_dir(os.path.join(output_dir, "Sprites"))
        ensure_dir(os.path.join(output_dir, "Stage"))

        targets = project.get("targets", [])

        stage_target = next((t for t in targets if t.get("isStage")), None)
        if stage_target:
            write_variables_file(os.path.join(output_dir, "variables.json"), stage_target)
        else:
            write_json_file(os.path.join(output_dir, "variables.json"), {"variables": [], "lists": []})

        write_events_file(os.path.join(output_dir, "events.json"), collect_broadcasts(targets))

        for target in targets:
            write_target(target, archive, output_dir)

    print(f"Successfully converted {sb3_path} to {output_dir}")


def convert_folder_to_sb3(input_dir: str, output_path: str) -> None:
    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} not found or not a directory")
        return

    events_path = os.path.join(input_dir, "events.json")
    variables_path = os.path.join(input_dir, "variables.json")

    events_payload = load_json_file(events_path, {"broadcasts": []})
    broadcast_ids: Dict[str, str] = {name: gen_id("broadcast") for name in events_payload.get("broadcasts", [])}

    root_vars_payload = load_json_file(variables_path, {"variables": [], "lists": []})
    stage_vars, stage_var_ids = build_variables_payload(root_vars_payload.get("variables", []))
    stage_lists, stage_list_ids = build_lists_payload(root_vars_payload.get("lists", []))

    assets_to_pack: List[Tuple[str, str]] = []

    stage_dir = os.path.join(input_dir, "Stage")
    stage_blocks = code_to_blocks(
        os.path.join(stage_dir, "code.scratchblocks"),
        stage_var_ids,
        {},
        stage_list_ids,
        {},
        broadcast_ids,
    )
    auto_arrange_top_blocks(stage_blocks)
    stage_costumes, stage_assets = prepare_costumes(os.path.join(stage_dir, "Assets"))
    stage_sounds, stage_sound_assets = prepare_sounds(os.path.join(stage_dir, "Sounds"))
    assets_to_pack.extend(stage_assets)
    assets_to_pack.extend(stage_sound_assets)

    stage_target = {
        "isStage": True,
        "name": "Stage",
        "variables": stage_vars,
        "lists": stage_lists,
        "broadcasts": {bid: name for name, bid in broadcast_ids.items()},
        "blocks": stage_blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": stage_costumes,
        "sounds": stage_sounds,
        "volume": 100,
        "layerOrder": 0,
        "tempo": 60,
        "videoTransparency": 50,
        "videoState": "on",
        "textToSpeechLanguage": None,
    }

    targets: List[Dict[str, Any]] = [stage_target]

    sprites_root = os.path.join(input_dir, "Sprites")
    if os.path.exists(sprites_root):
        for idx, sprite_name in enumerate(sorted(os.listdir(sprites_root)), start=1):
            sprite_dir = os.path.join(sprites_root, sprite_name)
            if not os.path.isdir(sprite_dir):
                continue

            sprite_vars_payload = load_json_file(os.path.join(sprite_dir, "variables.json"), {"variables": [], "lists": []})
            sprite_vars, sprite_var_ids = build_variables_payload(sprite_vars_payload.get("variables", []))
            sprite_lists, sprite_list_ids = build_lists_payload(sprite_vars_payload.get("lists", []))

            misc = load_json_file(
                os.path.join(sprite_dir, "miscdata.json"),
                {
                    "position": {"x": 0, "y": 0},
                    "size": 100,
                    "direction": 90,
                    "visible": True,
                    "rotationStyle": "all around",
                    "currentCostume": 0,
                    "draggable": False,
                    "volume": 100,
                    "layer": idx,
                },
            )

            sprite_blocks = code_to_blocks(
                os.path.join(sprite_dir, "code.scratchblocks"),
                sprite_var_ids,
                stage_var_ids,
                sprite_list_ids,
                stage_list_ids,
                broadcast_ids,
            )
            auto_arrange_top_blocks(sprite_blocks)

            sprite_costumes, sprite_assets = prepare_costumes(os.path.join(sprite_dir, "Assets"))
            sprite_sounds, sprite_sound_assets = prepare_sounds(os.path.join(sprite_dir, "Sounds"))
            assets_to_pack.extend(sprite_assets)
            assets_to_pack.extend(sprite_sound_assets)

            current_costume = misc.get("currentCostume", 0)
            if current_costume >= len(sprite_costumes):
                current_costume = 0

            layer_order = misc.get("layer", idx)

            targets.append(
                {
                    "isStage": False,
                    "name": sprite_name,
                    "variables": sprite_vars,
                    "lists": sprite_lists,
                    "broadcasts": {},
                    "blocks": sprite_blocks,
                    "comments": {},
                    "currentCostume": current_costume,
                    "costumes": sprite_costumes,
                    "sounds": sprite_sounds,
                    "volume": misc.get("volume", 100),
                    "layerOrder": layer_order,
                    "visible": misc.get("visible", True),
                    "x": misc.get("position", {}).get("x", 0),
                    "y": misc.get("position", {}).get("y", 0),
                    "size": misc.get("size", 100),
                    "direction": misc.get("direction", 90),
                    "draggable": misc.get("draggable", False),
                    "rotationStyle": misc.get("rotationStyle", "all around"),
                }
            )

    project = {
        "targets": targets,
        "monitors": [],
        "extensions": [],
        "meta": {
            "semver": "3.0.0",
            "vm": "0.2.0",
            "agent": "",
            "platform": {"name": "TurboWarp", "url": "https://turbowarp.org/"},
        },
    }

    ensure_dir(os.path.dirname(output_path) or ".")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(project, indent=4))
        seen_assets = set()
        for src, dest in assets_to_pack:
            if dest in seen_assets:
                continue
            seen_assets.add(dest)
            archive.write(src, dest)

    print(f"Successfully converted {input_dir} to {output_path}")
