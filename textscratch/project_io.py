import json
import os
import shutil
import zipfile
from typing import Any, Dict, List, Set, Tuple

from .assets import (
    build_miscdata,
    copy_costumes,
    copy_sounds,
    prepare_costumes,
    prepare_sounds,
)
from .blocks_to_text import generate_target_code
from .diagnostics import DiagnosticCollector, DiagnosticContext
from .layout import auto_arrange_top_blocks
from .text_to_blocks import code_to_blocks
from .utils import ensure_dir, gen_id, load_json_file, safe_name, write_json_file


# Known extension opcode prefixes to emit in project.json
EXTENSION_PREFIXES: Dict[str, str] = {
    "pen": "pen",
    "music": "music",
    "text2speech": "text2speech",
    "translate": "translate",
    "videoSensing": "videoSensing",
    "ev3": "ev3",
    "microbit": "microbit",
    "wedo2": "wedo2",
    "makeymakey": "makeymakey",
    "boost": "boost",
    "gdxfor": "gdxfor",
}


def build_variables_payload(
    entries: List[Dict[str, Any]], sprite_name: str | None
) -> Tuple[Dict[str, List[Any]], Dict[str, str], List[Dict[str, Any]]]:
    var_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    monitors: List[Dict[str, Any]] = []
    for entry in entries:
        name = entry.get("name", "variable")
        value = entry.get("value", 0)
        vid = gen_id("var")
        name_to_id[name] = vid
        payload: List[Any] = [name, value]
        if entry.get("cloud"):
            payload.append(True)
        var_dict[vid] = payload
        # Build monitor entry
        mon_data = entry.get("monitor", {})
        monitors.append({
            "id": vid,
            "mode": mon_data.get("mode", "default"),
            "opcode": "data_variable",
            "params": {"VARIABLE": name},
            "spriteName": sprite_name,
            "value": value,
            "width": 0,
            "height": 0,
            "x": mon_data.get("x", 0),
            "y": mon_data.get("y", 0),
            "visible": mon_data.get("visible", False),
            "sliderMin": mon_data.get("sliderMin", 0),
            "sliderMax": mon_data.get("sliderMax", 100),
            "isDiscrete": mon_data.get("isDiscrete", True),
        })
    return var_dict, name_to_id, monitors


def build_lists_payload(
    entries: List[Dict[str, Any]], sprite_name: str | None
) -> Tuple[Dict[str, List[Any]], Dict[str, str], List[Dict[str, Any]]]:
    list_dict: Dict[str, List[Any]] = {}
    name_to_id: Dict[str, str] = {}
    monitors: List[Dict[str, Any]] = []
    for entry in entries:
        name = entry.get("name", "list")
        value = entry.get("value", [])
        lid = gen_id("list")
        name_to_id[name] = lid
        list_dict[lid] = [name, value]
        # Build monitor entry
        mon_data = entry.get("monitor", {})
        monitors.append({
            "id": lid,
            "mode": "list",
            "opcode": "data_listcontents",
            "params": {"LIST": name},
            "spriteName": sprite_name,
            "value": value,
            "width": mon_data.get("width", 0),
            "height": mon_data.get("height", 0),
            "x": mon_data.get("x", 0),
            "y": mon_data.get("y", 0),
            "visible": mon_data.get("visible", False),
        })
    return list_dict, name_to_id, monitors


def convert_variables_dict(
    variables: Dict[str, Any], monitors: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for var_id, payload in variables.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            entry: Dict[str, Any] = {"name": name, "value": value}
            if len(payload) >= 3 and payload[2] is True:
                entry["cloud"] = True
            # Find monitor metadata for this variable
            for mon in monitors:
                if mon.get("id") == var_id and mon.get("opcode") == "data_variable":
                    entry["monitor"] = {
                        "visible": mon.get("visible", False),
                        "mode": mon.get("mode", "default"),
                        "x": mon.get("x", 0),
                        "y": mon.get("y", 0),
                        "sliderMin": mon.get("sliderMin", 0),
                        "sliderMax": mon.get("sliderMax", 100),
                        "isDiscrete": mon.get("isDiscrete", True),
                    }
                    break
            result.append(entry)
    return result


def convert_lists_dict(
    lists: Dict[str, Any], monitors: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for list_id, payload in lists.items():
        if isinstance(payload, list) and len(payload) >= 2:
            name, value = payload[0], payload[1]
            entry: Dict[str, Any] = {"name": name, "value": value}
            # Find monitor metadata for this list
            for mon in monitors:
                if mon.get("id") == list_id and mon.get("opcode") == "data_listcontents":
                    entry["monitor"] = {
                        "visible": mon.get("visible", False),
                        "x": mon.get("x", 0),
                        "y": mon.get("y", 0),
                        "width": mon.get("width", 0),
                        "height": mon.get("height", 0),
                    }
                    break
            result.append(entry)
    return result


def write_variables_file(
    path: str, target: Dict[str, Any], monitors: List[Dict[str, Any]]
) -> None:
    # Filter monitors for this target
    target_name = target.get("name") if not target.get("isStage") else None
    target_monitors = [
        m for m in monitors
        if m.get("spriteName") == target_name
    ]
    payload = {
        "variables": convert_variables_dict(target.get("variables", {}), target_monitors),
        "lists": convert_lists_dict(target.get("lists", {}), target_monitors),
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


def collect_extensions_from_blocks(blocks: Dict[str, Any], extensions: Set[str]) -> None:
    for block in blocks.values():
        opcode = block.get("opcode", "")
        prefix = opcode.split("_", 1)[0] if "_" in opcode else ""
        ext = EXTENSION_PREFIXES.get(prefix)
        if ext:
            extensions.add(ext)


def write_target(
    target: Dict[str, Any],
    archive: zipfile.ZipFile,
    output_root: str,
    monitors: List[Dict[str, Any]],
) -> None:
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
        write_variables_file(os.path.join(target_dir, "variables.json"), target, monitors)
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
        monitors = project.get("monitors", [])

        stage_target = next((t for t in targets if t.get("isStage")), None)
        if stage_target:
            write_variables_file(os.path.join(output_dir, "variables.json"), stage_target, monitors)
        else:
            write_json_file(os.path.join(output_dir, "variables.json"), {"variables": [], "lists": []})

        write_events_file(os.path.join(output_dir, "events.json"), collect_broadcasts(targets))

        for target in targets:
            write_target(target, archive, output_dir, monitors)

    print(f"Successfully converted {sb3_path} to {output_dir}")


def convert_folder_to_sb3(input_dir: str, output_path: str) -> None:
    if not os.path.isdir(input_dir):
        print(f"Error: {input_dir} not found or not a directory")
        return

    # Create diagnostic collector for all sprites
    diag_collector = DiagnosticCollector()

    events_path = os.path.join(input_dir, "events.json")
    variables_path = os.path.join(input_dir, "variables.json")

    events_payload = load_json_file(events_path, {"broadcasts": []})
    broadcast_ids: Dict[str, str] = {name: gen_id("broadcast") for name in events_payload.get("broadcasts", [])}

    extensions: Set[str] = set()
    all_monitors: List[Dict[str, Any]] = []

    root_vars_payload = load_json_file(variables_path, {"variables": [], "lists": []})
    stage_vars, stage_var_ids, stage_var_monitors = build_variables_payload(
        root_vars_payload.get("variables", []), None
    )
    stage_lists, stage_list_ids, stage_list_monitors = build_lists_payload(
        root_vars_payload.get("lists", []), None
    )
    all_monitors.extend(stage_var_monitors)
    all_monitors.extend(stage_list_monitors)

    assets_to_pack: List[Tuple[str, str]] = []

    # Create diagnostic context for Stage
    stage_diag = DiagnosticContext(sprite_name="Stage")

    stage_dir = os.path.join(input_dir, "Stage")
    stage_blocks = code_to_blocks(
        os.path.join(stage_dir, "code.scratchblocks"),
        stage_var_ids,
        {},
        stage_list_ids,
        {},
        broadcast_ids,
        stage_diag,
    )
    diag_collector.add_context_diagnostics(stage_diag)
    collect_extensions_from_blocks(stage_blocks, extensions)
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
            sprite_vars, sprite_var_ids, sprite_var_monitors = build_variables_payload(
                sprite_vars_payload.get("variables", []), sprite_name
            )
            sprite_lists, sprite_list_ids, sprite_list_monitors = build_lists_payload(
                sprite_vars_payload.get("lists", []), sprite_name
            )
            all_monitors.extend(sprite_var_monitors)
            all_monitors.extend(sprite_list_monitors)

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

            # Create diagnostic context for this sprite
            sprite_diag = DiagnosticContext(sprite_name=sprite_name)

            sprite_blocks = code_to_blocks(
                os.path.join(sprite_dir, "code.scratchblocks"),
                sprite_var_ids,
                stage_var_ids,
                sprite_list_ids,
                stage_list_ids,
                broadcast_ids,
                sprite_diag,
            )
            diag_collector.add_context_diagnostics(sprite_diag)
            auto_arrange_top_blocks(sprite_blocks)
            collect_extensions_from_blocks(sprite_blocks, extensions)

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
        "monitors": all_monitors,
        "extensions": sorted(extensions),
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

    # Print diagnostics if any
    if diag_collector.all_diagnostics:
        print()  # Blank line before diagnostics
        diag_collector.print_all()
        print()  # Blank line after diagnostics
        print(f"Conversion completed with {diag_collector.summary()}")
    else:
        print(f"Successfully converted {input_dir} to {output_path}")
