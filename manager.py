#!/usr/bin/env python3
"""
TextScratch Project Manager

A module and CLI tool for managing TextScratch projects, sprites, variables, and assets.
For detailed documentation, see README.md.

Usage as CLI:
    python manager.py <command> <subcommand> [options]

Usage as Python module:
    from manager import Manager
    mgr = Manager("MyProject")
    mgr.create_sprite(name="Player")
    sprites = mgr.list_sprites()

Commands:
    project     Create or delete projects
    sprite      Manage sprites (create, rename, delete, duplicate, list, edit)
    var         Manage variables and lists
    asset       Manage costumes and sounds
"""

import argparse
import hashlib
import json as json_module
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from textscratch.utils import ensure_dir, load_json_file, safe_name, write_json_file
from textscratch.assets import (
    NAME_MAP_COSTUMES,
    NAME_MAP_SOUNDS,
    META_COSTUMES,
    probe_image_size,
    load_name_map,
    load_costume_meta,
)


# ============================================================================
# Exceptions
# ============================================================================

class ManagerError(Exception):
    """Exception raised by Manager operations."""
    
    def __init__(self, message: str, detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.detail:
            return f"{self.message} ({self.detail})"
        return self.message

# ============================================================================
# Constants
# ============================================================================

CLOUD_PREFIX = "☁"
DEFAULT_PROJECT_PATH = "Project"
LOGO_SVG_PATH = os.path.join(os.path.dirname(__file__), "textscratch", "assets", "logo.svg")

# Blank white backdrop SVG (480x360 standard Scratch stage size)
BLANK_BACKDROP_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">
  <rect fill="#ffffff" width="480" height="360"/>
</svg>'''

DEFAULT_MISCDATA = {
    "position": {"x": 0, "y": 0},
    "size": 100,
    "direction": 90,
    "visible": True,
    "rotationStyle": "all around",
    "currentCostume": 0,
    "draggable": False,
    "volume": 100,
    "layer": 1,
}

# ============================================================================
# Utility Functions
# ============================================================================

verbose_mode = False


def error(msg: str, detail: str = "") -> None:
    """Print an error message and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    if verbose_mode and detail:
        print(f"  Detail: {detail}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    """Print a warning message."""
    print(f"Warning: {msg}", file=sys.stderr)


def info(msg: str) -> None:
    """Print an info message."""
    print(msg)


def confirm(prompt: str, skip: bool = False) -> bool:
    """Ask for user confirmation. Returns True if confirmed or skip=True."""
    if skip:
        return True
    response = input(f"{prompt} [y/N]: ").strip().lower()
    return response in ("y", "yes")


def truncate_value(value: Any, limit: int = 10) -> str:
    """Truncate a value for display."""
    if isinstance(value, list):
        items = [str(v)[:limit] for v in value[:5]]
        result = ", ".join(items)
        if len(value) > 5:
            result += f", ... ({len(value)} items)"
        return f"[{result}]"
    s = str(value)
    if len(s) > limit:
        return s[:limit] + "..."
    return s


def get_project_path(args: argparse.Namespace) -> str:
    """Get the project path from args or default."""
    return getattr(args, "project", None) or DEFAULT_PROJECT_PATH


def validate_project_exists(project_path: str) -> None:
    """Validate that a project exists at the given path."""
    if not os.path.isdir(project_path):
        error(f"Project not found: {project_path}", "Make sure the path points to a valid TextScratch project folder.")
    
    # Check for required structure
    stage_path = os.path.join(project_path, "Stage")
    sprites_path = os.path.join(project_path, "Sprites")
    if not os.path.isdir(stage_path):
        error(f"Invalid project: missing Stage folder", f"Expected: {stage_path}")
    if not os.path.isdir(sprites_path):
        error(f"Invalid project: missing Sprites folder", f"Expected: {sprites_path}")


def get_sprite_path(project_path: str, sprite_name: str) -> str:
    """Get the path to a sprite folder."""
    return os.path.join(project_path, "Sprites", sprite_name)


def validate_sprite_exists(project_path: str, sprite_name: str) -> str:
    """Validate a sprite exists and return its path."""
    sprite_path = get_sprite_path(project_path, sprite_name)
    if not os.path.isdir(sprite_path):
        sprites = list_sprite_names(project_path)
        available = ", ".join(sprites) if sprites else "(none)"
        error(f"Sprite not found: {sprite_name}", f"Available sprites: {available}")
    return sprite_path


def list_sprite_names(project_path: str) -> List[str]:
    """List all sprite names in a project."""
    sprites_dir = os.path.join(project_path, "Sprites")
    if not os.path.isdir(sprites_dir):
        return []
    return [d for d in os.listdir(sprites_dir) if os.path.isdir(os.path.join(sprites_dir, d))]


def find_next_sprite_number(project_path: str) -> int:
    """Find the next available SpriteN number."""
    sprites = list_sprite_names(project_path)
    used_numbers = set()
    for name in sprites:
        match = re.match(r"^Sprite(\d+)$", name)
        if match:
            used_numbers.add(int(match.group(1)))
    
    n = 1
    while n in used_numbers:
        n += 1
    return n


def compute_md5(filepath: str) -> str:
    """Compute MD5 hash of a file."""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def get_next_asset_index(asset_dir: str) -> int:
    """Get the next asset index number for a directory."""
    if not os.path.isdir(asset_dir):
        return 0
    
    max_idx = -1
    for fname in os.listdir(asset_dir):
        if fname.startswith("__"):
            continue
        match = re.match(r"^(\d+)__", fname)
        if match:
            max_idx = max(max_idx, int(match.group(1)))
    return max_idx + 1


def load_variables_file(path: str) -> Dict[str, Any]:
    """Load a variables.json file."""
    return load_json_file(path, {"variables": [], "lists": []})


def save_variables_file(path: str, data: Dict[str, Any]) -> None:
    """Save a variables.json file."""
    write_json_file(path, data)


def _get_asset_dir(project_path: str, sprite_name: str, asset_type: str) -> str:
    """Get the asset directory path."""
    if sprite_name.lower() == "stage":
        base = os.path.join(project_path, "Stage")
    else:
        base = get_sprite_path(project_path, sprite_name)
    
    return os.path.join(base, "Assets" if asset_type == "costume" else "Sounds")


def _find_asset_file(asset_dir: str, name: str, name_map_file: str) -> Optional[str]:
    """Find an asset file by display name."""
    name_map = load_name_map(asset_dir, name_map_file)
    
    # Search by display name
    for fname, display_name in name_map.items():
        if display_name == name:
            return fname
    
    # Search by filename
    for fname in os.listdir(asset_dir):
        if fname.startswith("__"):
            continue
        if fname == name:
            return fname
    
    return None


def _get_var_file_path(project_path: str, sprite_name: Optional[str]) -> str:
    """Get the path to the variables.json file for a scope."""
    if sprite_name:
        return os.path.join(get_sprite_path(project_path, sprite_name), "variables.json")
    return os.path.join(project_path, "variables.json")


# ============================================================================
# Manager Class
# ============================================================================

class Manager:
    """
    TextScratch Project Manager class.
    
    Provides programmatic access to all project management features including
    sprites, variables, lists, and assets.
    
    Example:
        >>> mgr = Manager("MyProject")
        >>> mgr.create_sprite(name="Player")
        'Player'
        >>> sprites = mgr.list_sprites()
        >>> mgr.create_variable("score", value=0)
    """
    
    def __init__(self, project_path: str = DEFAULT_PROJECT_PATH):
        """
        Initialize the Manager with a project path.
        
        Args:
            project_path: Path to the TextScratch project folder.
        """
        self.project_path = project_path
    
    def _validate_project(self) -> None:
        """Validate that the project exists and has required structure."""
        if not os.path.isdir(self.project_path):
            raise ManagerError(
                f"Project not found: {self.project_path}",
                "Make sure the path points to a valid TextScratch project folder."
            )
        
        stage_path = os.path.join(self.project_path, "Stage")
        sprites_path = os.path.join(self.project_path, "Sprites")
        if not os.path.isdir(stage_path):
            raise ManagerError(f"Invalid project: missing Stage folder", f"Expected: {stage_path}")
        if not os.path.isdir(sprites_path):
            raise ManagerError(f"Invalid project: missing Sprites folder", f"Expected: {sprites_path}")
    
    def _validate_sprite(self, sprite_name: str) -> str:
        """Validate a sprite exists and return its path."""
        sprite_path = get_sprite_path(self.project_path, sprite_name)
        if not os.path.isdir(sprite_path):
            sprites = list_sprite_names(self.project_path)
            available = ", ".join(sprites) if sprites else "(none)"
            raise ManagerError(f"Sprite not found: {sprite_name}", f"Available sprites: {available}")
        return sprite_path
    
    # ========== Project Methods ==========
    
    @staticmethod
    def create_project(path: str, replace: bool = False) -> None:
        """
        Create a new project with template contents.
        
        Args:
            path: Path for the new project.
            replace: If True, replace existing project.
        
        Raises:
            ManagerError: If path exists and replace is False.
        """
        if os.path.exists(path):
            if not replace:
                raise ManagerError(
                    f"Path already exists: {path}",
                    "Set replace=True to overwrite the existing project."
                )
            shutil.rmtree(path)
        
        # Create project structure
        ensure_dir(path)
        
        # Create Stage
        stage_dir = os.path.join(path, "Stage")
        stage_assets = os.path.join(stage_dir, "Assets")
        stage_sounds = os.path.join(stage_dir, "Sounds")
        ensure_dir(stage_assets)
        ensure_dir(stage_sounds)
        
        # Write blank backdrop
        backdrop_content = BLANK_BACKDROP_SVG.encode("utf-8")
        backdrop_md5 = hashlib.md5(backdrop_content).hexdigest()
        backdrop_filename = f"000__{backdrop_md5}.svg"
        backdrop_path = os.path.join(stage_assets, backdrop_filename)
        with open(backdrop_path, "wb") as f:
            f.write(backdrop_content)
        
        # Write Stage asset metadata
        write_json_file(os.path.join(stage_assets, NAME_MAP_COSTUMES), {backdrop_filename: "backdrop1"})
        write_json_file(os.path.join(stage_assets, META_COSTUMES), {
            backdrop_filename: {"rotationCenterX": 240, "rotationCenterY": 180, "bitmapResolution": 1}
        })
        
        # Write empty Stage code
        with open(os.path.join(stage_dir, "code.scratchblocks"), "w") as f:
            f.write("")
        
        # Create Sprites folder
        sprites_dir = os.path.join(path, "Sprites")
        ensure_dir(sprites_dir)
        
        # Create Sprite1
        sprite1_dir = os.path.join(sprites_dir, "Sprite1")
        sprite1_assets = os.path.join(sprite1_dir, "Assets")
        sprite1_sounds = os.path.join(sprite1_dir, "Sounds")
        ensure_dir(sprite1_assets)
        ensure_dir(sprite1_sounds)
        
        # Copy logo.svg as costume1
        if os.path.exists(LOGO_SVG_PATH):
            logo_md5 = compute_md5(LOGO_SVG_PATH)
            logo_filename = f"000__{logo_md5}.svg"
            shutil.copy2(LOGO_SVG_PATH, os.path.join(sprite1_assets, logo_filename))
            
            size = probe_image_size(LOGO_SVG_PATH, "svg")
            center_x = size[0] / 2 if size else 0
            center_y = size[1] / 2 if size else 0
            
            write_json_file(os.path.join(sprite1_assets, NAME_MAP_COSTUMES), {logo_filename: "costume1"})
            write_json_file(os.path.join(sprite1_assets, META_COSTUMES), {
                logo_filename: {"rotationCenterX": center_x, "rotationCenterY": center_y, "bitmapResolution": 1}
            })
        
        # Write Sprite1 files
        with open(os.path.join(sprite1_dir, "code.scratchblocks"), "w") as f:
            f.write("")
        write_json_file(os.path.join(sprite1_dir, "miscdata.json"), DEFAULT_MISCDATA.copy())
        write_json_file(os.path.join(sprite1_dir, "variables.json"), {"variables": [], "lists": []})
        
        # Create root project files
        write_json_file(os.path.join(path, "events.json"), {"broadcasts": []})
        write_json_file(os.path.join(path, "variables.json"), {"variables": [], "lists": []})
    
    @staticmethod
    def delete_project(path: str) -> None:
        """
        Delete a project.
        
        Args:
            path: Path to the project to delete.
        
        Raises:
            ManagerError: If project does not exist.
        """
        if not os.path.exists(path):
            raise ManagerError(f"Project not found: {path}")
        shutil.rmtree(path)
    
    # ========== Sprite Methods ==========
    
    def create_sprite(self, name: Optional[str] = None) -> str:
        """
        Create a new sprite.
        
        Args:
            name: Sprite name. If None, auto-generates SpriteN.
        
        Returns:
            The name of the created sprite.
        
        Raises:
            ManagerError: If sprite already exists or project invalid.
        """
        self._validate_project()
        
        if name:
            sprite_name = safe_name(name, "Sprite")
        else:
            num = find_next_sprite_number(self.project_path)
            sprite_name = f"Sprite{num}"
        
        sprite_path = get_sprite_path(self.project_path, sprite_name)
        
        if os.path.exists(sprite_path):
            raise ManagerError(f"Sprite already exists: {sprite_name}")
        
        # Create sprite structure
        assets_dir = os.path.join(sprite_path, "Assets")
        sounds_dir = os.path.join(sprite_path, "Sounds")
        ensure_dir(assets_dir)
        ensure_dir(sounds_dir)
        
        # Copy logo.svg as costume1
        if os.path.exists(LOGO_SVG_PATH):
            logo_md5 = compute_md5(LOGO_SVG_PATH)
            logo_filename = f"000__{logo_md5}.svg"
            shutil.copy2(LOGO_SVG_PATH, os.path.join(assets_dir, logo_filename))
            
            size = probe_image_size(LOGO_SVG_PATH, "svg")
            center_x = size[0] / 2 if size else 0
            center_y = size[1] / 2 if size else 0
            
            write_json_file(os.path.join(assets_dir, NAME_MAP_COSTUMES), {logo_filename: "costume1"})
            write_json_file(os.path.join(assets_dir, META_COSTUMES), {
                logo_filename: {"rotationCenterX": center_x, "rotationCenterY": center_y, "bitmapResolution": 1}
            })
        
        # Write sprite files
        with open(os.path.join(sprite_path, "code.scratchblocks"), "w") as f:
            f.write("")
        
        # Set layer based on existing sprites
        existing_sprites = list_sprite_names(self.project_path)
        max_layer = 0
        for s in existing_sprites:
            misc_path = os.path.join(get_sprite_path(self.project_path, s), "miscdata.json")
            misc = load_json_file(misc_path, {})
            max_layer = max(max_layer, misc.get("layer", 0))
        
        miscdata = DEFAULT_MISCDATA.copy()
        miscdata["layer"] = max_layer + 1
        write_json_file(os.path.join(sprite_path, "miscdata.json"), miscdata)
        write_json_file(os.path.join(sprite_path, "variables.json"), {"variables": [], "lists": []})
        
        return sprite_name
    
    def rename_sprite(self, old_name: str, new_name: str) -> str:
        """
        Rename a sprite.
        
        Args:
            old_name: Current sprite name.
            new_name: New sprite name.
        
        Returns:
            The new sanitized sprite name.
        
        Raises:
            ManagerError: If sprite not found or new name already exists.
        """
        self._validate_project()
        
        old_path = self._validate_sprite(old_name)
        new_name_safe = safe_name(new_name, "Sprite")
        new_path = get_sprite_path(self.project_path, new_name_safe)
        
        if os.path.exists(new_path):
            raise ManagerError(f"Sprite already exists: {new_name_safe}")
        
        os.rename(old_path, new_path)
        return new_name_safe
    
    def delete_sprite(self, name: str) -> None:
        """
        Delete a sprite.
        
        Args:
            name: Sprite name to delete.
        
        Raises:
            ManagerError: If sprite not found.
        """
        self._validate_project()
        sprite_path = self._validate_sprite(name)
        shutil.rmtree(sprite_path)
    
    def duplicate_sprite(self, source: str, dest: Optional[str] = None) -> str:
        """
        Duplicate a sprite.
        
        Args:
            source: Source sprite name.
            dest: Destination sprite name. If None, auto-generates.
        
        Returns:
            The name of the duplicated sprite.
        
        Raises:
            ManagerError: If source not found or dest already exists.
        """
        self._validate_project()
        src_path = self._validate_sprite(source)
        
        if dest:
            dest_name = safe_name(dest, "Sprite")
        else:
            base_name = source
            n = 2
            dest_name = f"{base_name}{n}"
            while os.path.exists(get_sprite_path(self.project_path, dest_name)):
                n += 1
                dest_name = f"{base_name}{n}"
        
        dest_path = get_sprite_path(self.project_path, dest_name)
        
        if os.path.exists(dest_path):
            raise ManagerError(f"Sprite already exists: {dest_name}")
        
        shutil.copytree(src_path, dest_path)
        
        # Update layer in the copy
        existing_sprites = list_sprite_names(self.project_path)
        max_layer = 0
        for s in existing_sprites:
            if s == dest_name:
                continue
            misc_path = os.path.join(get_sprite_path(self.project_path, s), "miscdata.json")
            misc = load_json_file(misc_path, {})
            max_layer = max(max_layer, misc.get("layer", 0))
        
        misc_path = os.path.join(dest_path, "miscdata.json")
        miscdata = load_json_file(misc_path, DEFAULT_MISCDATA.copy())
        miscdata["layer"] = max_layer + 1
        write_json_file(misc_path, miscdata)
        
        return dest_name
    
    def list_sprites(self) -> List[Dict[str, Any]]:
        """
        List all sprites with their properties.
        
        Returns:
            List of sprite dictionaries with name, position, size, visible, layer.
        
        Raises:
            ManagerError: If project invalid.
        """
        self._validate_project()
        
        sprites = list_sprite_names(self.project_path)
        sprite_info = []
        
        for name in sorted(sprites):
            misc_path = os.path.join(get_sprite_path(self.project_path, name), "miscdata.json")
            misc = load_json_file(misc_path, {})
            sprite_info.append({
                "name": name,
                "x": misc.get("position", {}).get("x", 0),
                "y": misc.get("position", {}).get("y", 0),
                "size": misc.get("size", 100),
                "direction": misc.get("direction", 90),
                "visible": misc.get("visible", True),
                "layer": misc.get("layer", 0),
                "rotationStyle": misc.get("rotationStyle", "all around"),
                "draggable": misc.get("draggable", False),
                "currentCostume": misc.get("currentCostume", 0),
            })
        
        sprite_info.sort(key=lambda s: s["layer"])
        return sprite_info
    
    def get_sprite(self, name: str) -> Dict[str, Any]:
        """
        Get a sprite's properties.
        
        Args:
            name: Sprite name.
        
        Returns:
            Dictionary with sprite properties.
        
        Raises:
            ManagerError: If sprite not found.
        """
        self._validate_project()
        sprite_path = self._validate_sprite(name)
        
        misc_path = os.path.join(sprite_path, "miscdata.json")
        misc = load_json_file(misc_path, DEFAULT_MISCDATA.copy())
        
        return {
            "name": name,
            "x": misc.get("position", {}).get("x", 0),
            "y": misc.get("position", {}).get("y", 0),
            "size": misc.get("size", 100),
            "direction": misc.get("direction", 90),
            "visible": misc.get("visible", True),
            "layer": misc.get("layer", 0),
            "rotationStyle": misc.get("rotationStyle", "all around"),
            "draggable": misc.get("draggable", False),
            "currentCostume": misc.get("currentCostume", 0),
            "volume": misc.get("volume", 100),
        }
    
    def edit_sprite(
        self,
        name: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        size: Optional[float] = None,
        direction: Optional[float] = None,
        visible: Optional[bool] = None,
        layer: Optional[int] = None,
        costume: Optional[int] = None,
        rotation_style: Optional[str] = None,
        draggable: Optional[bool] = None,
    ) -> None:
        """
        Edit sprite properties.
        
        Args:
            name: Sprite name.
            x: X position.
            y: Y position.
            size: Size percentage.
            direction: Direction in degrees.
            visible: Visibility flag.
            layer: Layer order.
            costume: Current costume index.
            rotation_style: One of "all around", "left-right", "don't rotate".
            draggable: Draggable flag.
        
        Raises:
            ManagerError: If sprite not found or invalid rotation_style.
        """
        self._validate_project()
        sprite_path = self._validate_sprite(name)
        
        misc_path = os.path.join(sprite_path, "miscdata.json")
        miscdata = load_json_file(misc_path, DEFAULT_MISCDATA.copy())
        
        changed = False
        
        if x is not None:
            if "position" not in miscdata:
                miscdata["position"] = {"x": 0, "y": 0}
            miscdata["position"]["x"] = x
            changed = True
        
        if y is not None:
            if "position" not in miscdata:
                miscdata["position"] = {"x": 0, "y": 0}
            miscdata["position"]["y"] = y
            changed = True
        
        if size is not None:
            miscdata["size"] = size
            changed = True
        
        if direction is not None:
            miscdata["direction"] = direction
            changed = True
        
        if visible is not None:
            miscdata["visible"] = visible
            changed = True
        
        if layer is not None:
            miscdata["layer"] = layer
            changed = True
        
        if costume is not None:
            miscdata["currentCostume"] = costume
            changed = True
        
        if rotation_style is not None:
            valid_styles = ["all around", "left-right", "don't rotate"]
            if rotation_style not in valid_styles:
                raise ManagerError(
                    f"Invalid rotation style: {rotation_style}",
                    f"Valid styles: {', '.join(valid_styles)}"
                )
            miscdata["rotationStyle"] = rotation_style
            changed = True
        
        if draggable is not None:
            miscdata["draggable"] = draggable
            changed = True
        
        if not changed:
            raise ManagerError("No properties specified to edit")
        
        write_json_file(misc_path, miscdata)
    
    # ========== Variable/List Methods ==========
    
    def list_variables(
        self,
        list_only: bool = False,
        var_only: bool = False,
        sprite: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all variables and/or lists.
        
        Args:
            list_only: If True, show only lists.
            var_only: If True, show only variables.
            sprite: If specified, only show vars/lists for this sprite (or None for global only).
        
        Returns:
            List of dictionaries with name, type, scope, value.
        
        Raises:
            ManagerError: If project or sprite invalid.
        """
        self._validate_project()
        
        all_entries = []
        
        def process_scope(scope_name: str, var_path: str) -> None:
            data = load_variables_file(var_path)
            
            if not list_only:
                for var in data.get("variables", []):
                    all_entries.append({
                        "name": var["name"],
                        "type": "variable",
                        "scope": scope_name,
                        "value": var.get("value", 0),
                        "cloud": var.get("cloud", False),
                        "monitor": var.get("monitor", {}),
                    })
            
            if not var_only:
                for lst in data.get("lists", []):
                    all_entries.append({
                        "name": lst["name"],
                        "type": "list",
                        "scope": scope_name,
                        "value": lst.get("value", []),
                        "monitor": lst.get("monitor", {}),
                    })
        
        if sprite is None:
            # Global scope
            global_path = os.path.join(self.project_path, "variables.json")
            process_scope("global", global_path)
            
            # All sprite scopes
            for sprite_name in list_sprite_names(self.project_path):
                sprite_var_path = os.path.join(get_sprite_path(self.project_path, sprite_name), "variables.json")
                process_scope(sprite_name, sprite_var_path)
        elif sprite == "global":
            global_path = os.path.join(self.project_path, "variables.json")
            process_scope("global", global_path)
        else:
            self._validate_sprite(sprite)
            sprite_var_path = os.path.join(get_sprite_path(self.project_path, sprite), "variables.json")
            process_scope(sprite, sprite_var_path)
        
        return all_entries
    
    def get_variable(
        self,
        name: str,
        sprite: Optional[str] = None,
        is_list: bool = False,
    ) -> Dict[str, Any]:
        """
        Get the full value of a variable or list.
        
        Args:
            name: Variable or list name.
            sprite: Sprite name (None for global).
            is_list: If True, look for a list.
        
        Returns:
            Dictionary with name, type, scope, value.
        
        Raises:
            ManagerError: If not found.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        key = "lists" if is_list else "variables"
        for item in data.get(key, []):
            if item["name"] == name:
                return {
                    "name": item["name"],
                    "type": "list" if is_list else "variable",
                    "scope": sprite or "global",
                    "value": item.get("value", [] if is_list else 0),
                    "cloud": item.get("cloud", False),
                    "monitor": item.get("monitor", {}),
                }
        
        scope_str = f"sprite '{sprite}'" if sprite else "global scope"
        item_type = "List" if is_list else "Variable"
        raise ManagerError(f"{item_type} not found: {name}", f"Not found in {scope_str}")
    
    def create_variable(
        self,
        name: str,
        sprite: Optional[str] = None,
        value: Any = 0,
        cloud: bool = False,
        monitor_mode: Optional[str] = None,
        monitor_visible: bool = False,
    ) -> None:
        """
        Create a new variable.
        
        Args:
            name: Variable name.
            sprite: Sprite name for local scope (None for global).
            value: Initial value (default: 0).
            cloud: If True, make it a cloud variable.
            monitor_mode: One of "default", "slider", "large".
            monitor_visible: If True, make monitor visible.
        
        Raises:
            ManagerError: If variable already exists.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        var_name = name
        if cloud and not var_name.startswith(CLOUD_PREFIX):
            var_name = CLOUD_PREFIX + " " + var_name
        
        existing = [v["name"] for v in data.get("variables", [])]
        if var_name in existing:
            raise ManagerError(f"Variable already exists: {var_name}")
        
        # Convert value to number if possible
        try:
            if isinstance(value, str) and "." in value:
                value = float(value)
            elif isinstance(value, str):
                value = int(value)
        except (ValueError, TypeError):
            pass
        
        entry: Dict[str, Any] = {"name": var_name, "value": value}
        if cloud:
            entry["cloud"] = True
        
        monitor: Dict[str, Any] = {"visible": monitor_visible, "mode": monitor_mode or "default", "x": 0, "y": 0}
        if monitor_mode == "slider":
            monitor["sliderMin"] = 0
            monitor["sliderMax"] = 100
            monitor["isDiscrete"] = True
        entry["monitor"] = monitor
        
        if "variables" not in data:
            data["variables"] = []
        data["variables"].append(entry)
        
        save_variables_file(var_path, data)
    
    def create_list(
        self,
        name: str,
        sprite: Optional[str] = None,
        value: Optional[List[Any]] = None,
        monitor_visible: bool = False,
    ) -> None:
        """
        Create a new list.
        
        Args:
            name: List name.
            sprite: Sprite name for local scope (None for global).
            value: Initial value (default: []).
            monitor_visible: If True, make monitor visible.
        
        Raises:
            ManagerError: If list already exists.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        existing = [l["name"] for l in data.get("lists", [])]
        if name in existing:
            raise ManagerError(f"List already exists: {name}")
        
        list_value = value if value is not None else []
        
        entry: Dict[str, Any] = {"name": name, "value": list_value}
        if monitor_visible:
            entry["monitor"] = {"visible": True, "x": 0, "y": 0, "width": 100, "height": 200}
        
        if "lists" not in data:
            data["lists"] = []
        data["lists"].append(entry)
        
        save_variables_file(var_path, data)
    
    def bulk_create_variables(
        self,
        names: List[str],
        sprite: Optional[str] = None,
        is_list: bool = False,
    ) -> Dict[str, int]:
        """
        Bulk create variables or lists.
        
        Args:
            names: List of names to create.
            sprite: Sprite name for local scope (None for global).
            is_list: If True, create lists instead of variables.
        
        Returns:
            Dictionary with 'created' and 'skipped' counts.
        
        Raises:
            ManagerError: If project or sprite invalid.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        created = 0
        skipped = 0
        
        for name in names:
            if is_list:
                existing = [l["name"] for l in data.get("lists", [])]
                if name in existing:
                    skipped += 1
                    continue
                if "lists" not in data:
                    data["lists"] = []
                data["lists"].append({"name": name, "value": []})
                created += 1
            else:
                existing = [v["name"] for v in data.get("variables", [])]
                if name in existing:
                    skipped += 1
                    continue
                if "variables" not in data:
                    data["variables"] = []
                data["variables"].append({"name": name, "value": 0})
                created += 1
        
        save_variables_file(var_path, data)
        
        return {"created": created, "skipped": skipped}
    
    def edit_variable(
        self,
        name: str,
        sprite: Optional[str] = None,
        is_list: bool = False,
        rename: Optional[str] = None,
        value: Any = None,
        scope: Optional[str] = None,
        cloud: Optional[bool] = None,
        monitor_x: Optional[int] = None,
        monitor_y: Optional[int] = None,
    ) -> None:
        """
        Edit a variable or list.
        
        Args:
            name: Variable or list name.
            sprite: Current sprite scope (None for global).
            is_list: If True, edit a list.
            rename: New name.
            value: New value.
            scope: New scope ('global' or sprite name).
            cloud: Cloud variable flag (variables only).
            monitor_x: Monitor X position.
            monitor_y: Monitor Y position.
        
        Raises:
            ManagerError: If not found or no changes specified.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        # Find the variable or list
        target = None
        target_list = None
        target_idx = None
        key = "lists" if is_list else "variables"
        
        for i, item in enumerate(data.get(key, [])):
            if item["name"] == name:
                target = item
                target_list = data[key]
                target_idx = i
                break
        
        if target is None:
            item_type = "List" if is_list else "Variable"
            raise ManagerError(f"{item_type} not found: {name}")
        
        changed = False
        
        # Handle scope change
        if scope is not None:
            new_sprite = None if scope.lower() == "global" else scope
            if new_sprite and new_sprite != sprite:
                self._validate_sprite(new_sprite)
            
            new_var_path = _get_var_file_path(self.project_path, new_sprite)
            
            if new_var_path != var_path:
                # Remove from current location
                target_list.pop(target_idx)
                save_variables_file(var_path, data)
                
                # Add to new location
                new_data = load_variables_file(new_var_path)
                if key not in new_data:
                    new_data[key] = []
                new_data[key].append(target)
                save_variables_file(new_var_path, new_data)
                
                # Reload for further edits
                var_path = new_var_path
                data = new_data
                target_list = data[key]
                target_idx = len(target_list) - 1
                target = target_list[target_idx]
                changed = True
        
        # Handle rename
        if rename:
            new_name = rename
            if cloud and not is_list:
                if not new_name.startswith(CLOUD_PREFIX):
                    new_name = CLOUD_PREFIX + " " + new_name
            target["name"] = new_name
            changed = True
        
        # Handle value change
        if value is not None:
            if is_list:
                if isinstance(value, str):
                    try:
                        parsed_value = json_module.loads(value)
                        if isinstance(parsed_value, list):
                            value = parsed_value
                        else:
                            value = [value]
                    except (json_module.JSONDecodeError, ValueError):
                        value = [value]
                target["value"] = value
            else:
                # Try to convert to number
                try:
                    if isinstance(value, str) and "." in value:
                        value = float(value)
                    elif isinstance(value, str):
                        value = int(value)
                except (ValueError, TypeError):
                    pass
                target["value"] = value
            changed = True
        
        # Handle cloud flag
        if cloud is not None and not is_list:
            if cloud:
                target["cloud"] = True
                if not target["name"].startswith(CLOUD_PREFIX):
                    target["name"] = CLOUD_PREFIX + " " + target["name"]
            else:
                target.pop("cloud", None)
                if target["name"].startswith(CLOUD_PREFIX):
                    target["name"] = target["name"].lstrip(CLOUD_PREFIX).strip()
            changed = True
        
        # Handle monitor position
        if monitor_x is not None or monitor_y is not None:
            if "monitor" not in target:
                target["monitor"] = {}
            if monitor_x is not None:
                target["monitor"]["x"] = monitor_x
            if monitor_y is not None:
                target["monitor"]["y"] = monitor_y
            changed = True
        
        if not changed:
            raise ManagerError("No changes specified")
        
        save_variables_file(var_path, data)
    
    def delete_variable(
        self,
        name: str,
        sprite: Optional[str] = None,
        is_list: bool = False,
    ) -> None:
        """
        Delete a variable or list.
        
        Args:
            name: Variable or list name.
            sprite: Sprite scope (None for global).
            is_list: If True, delete a list.
        
        Raises:
            ManagerError: If not found.
        """
        self._validate_project()
        
        if sprite:
            self._validate_sprite(sprite)
        
        var_path = _get_var_file_path(self.project_path, sprite)
        data = load_variables_file(var_path)
        
        key = "lists" if is_list else "variables"
        items = data.get(key, [])
        
        for i, item in enumerate(items):
            if item["name"] == name:
                items.pop(i)
                save_variables_file(var_path, data)
                return
        
        item_type = "List" if is_list else "Variable"
        raise ManagerError(f"{item_type} not found: {name}")
    
    # ========== Asset Methods ==========
    
    def create_asset(
        self,
        source: str,
        sprite: str,
        name: str,
        asset_type: str,
    ) -> None:
        """
        Create a new asset from a source file.
        
        Args:
            source: Source file path.
            sprite: Sprite name (or 'Stage').
            name: Asset display name.
            asset_type: One of 'costume' or 'sound'.
        
        Raises:
            ManagerError: If source not found or sprite invalid.
        """
        self._validate_project()
        
        if not os.path.exists(source):
            raise ManagerError(f"Source file not found: {source}")
        
        if sprite.lower() != "stage":
            self._validate_sprite(sprite)
        
        asset_dir = _get_asset_dir(self.project_path, sprite, asset_type)
        ensure_dir(asset_dir)
        
        # Compute MD5 and create filename
        md5_hash = compute_md5(source)
        ext = os.path.splitext(source)[1].lower().lstrip(".")
        idx = get_next_asset_index(asset_dir)
        dest_filename = f"{idx:03d}__{md5_hash}.{ext}"
        dest_path = os.path.join(asset_dir, dest_filename)
        
        # Copy file
        shutil.copy2(source, dest_path)
        
        # Update name map
        if asset_type == "costume":
            name_map_file = NAME_MAP_COSTUMES
            meta_file = META_COSTUMES
        else:
            name_map_file = NAME_MAP_SOUNDS
            meta_file = None
        
        name_map = load_name_map(asset_dir, name_map_file)
        name_map[dest_filename] = name
        write_json_file(os.path.join(asset_dir, name_map_file), name_map)
        
        # Update costume meta if applicable
        if asset_type == "costume" and meta_file:
            meta_map = load_costume_meta(asset_dir)
            
            size = probe_image_size(dest_path, ext)
            center_x = size[0] / 2 if size else 0
            center_y = size[1] / 2 if size else 0
            
            meta_map[dest_filename] = {
                "rotationCenterX": center_x,
                "rotationCenterY": center_y,
                "bitmapResolution": 1 if ext == "svg" else 2,
            }
            write_json_file(os.path.join(asset_dir, meta_file), meta_map)
    
    def list_assets(
        self,
        sprite: str,
        asset_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List assets for a sprite.
        
        Args:
            sprite: Sprite name (or 'Stage').
            asset_type: Filter by 'costume' or 'sound' (None for both).
        
        Returns:
            List of asset dictionaries with name, type, format, size.
        
        Raises:
            ManagerError: If sprite invalid.
        """
        self._validate_project()
        
        if sprite.lower() != "stage":
            self._validate_sprite(sprite)
        
        assets = []
        
        # List costumes
        if asset_type in (None, "costume"):
            costume_dir = _get_asset_dir(self.project_path, sprite, "costume")
            if os.path.isdir(costume_dir):
                name_map = load_name_map(costume_dir, NAME_MAP_COSTUMES)
                for fname in sorted(os.listdir(costume_dir)):
                    if fname.startswith("__"):
                        continue
                    fpath = os.path.join(costume_dir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    
                    display_name = name_map.get(fname, fname)
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    size = probe_image_size(fpath, ext)
                    
                    assets.append({
                        "name": display_name,
                        "filename": fname,
                        "type": "costume",
                        "format": ext,
                        "width": int(size[0]) if size else None,
                        "height": int(size[1]) if size else None,
                    })
        
        # List sounds
        if asset_type in (None, "sound"):
            sound_dir = _get_asset_dir(self.project_path, sprite, "sound")
            if os.path.isdir(sound_dir):
                name_map = load_name_map(sound_dir, NAME_MAP_SOUNDS)
                for fname in sorted(os.listdir(sound_dir)):
                    if fname.startswith("__"):
                        continue
                    fpath = os.path.join(sound_dir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    
                    display_name = name_map.get(fname, fname)
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    file_size = os.path.getsize(fpath)
                    
                    assets.append({
                        "name": display_name,
                        "filename": fname,
                        "type": "sound",
                        "format": ext,
                        "file_size": file_size,
                    })
        
        return assets
    
    def delete_asset(
        self,
        sprite: str,
        name: str,
        asset_type: str,
    ) -> None:
        """
        Delete an asset.
        
        Args:
            sprite: Sprite name (or 'Stage').
            name: Asset display name.
            asset_type: One of 'costume' or 'sound'.
        
        Raises:
            ManagerError: If asset not found.
        """
        self._validate_project()
        
        if sprite.lower() != "stage":
            self._validate_sprite(sprite)
        
        asset_dir = _get_asset_dir(self.project_path, sprite, asset_type)
        name_map_file = NAME_MAP_COSTUMES if asset_type == "costume" else NAME_MAP_SOUNDS
        
        fname = _find_asset_file(asset_dir, name, name_map_file)
        if not fname:
            raise ManagerError(f"Asset not found: {name}")
        
        # Remove file
        fpath = os.path.join(asset_dir, fname)
        os.remove(fpath)
        
        # Update name map
        name_map = load_name_map(asset_dir, name_map_file)
        name_map.pop(fname, None)
        write_json_file(os.path.join(asset_dir, name_map_file), name_map)
        
        # Update costume meta if applicable
        if asset_type == "costume":
            meta_map = load_costume_meta(asset_dir)
            meta_map.pop(fname, None)
            write_json_file(os.path.join(asset_dir, META_COSTUMES), meta_map)
    
    def duplicate_asset(
        self,
        src_sprite: str,
        src_name: str,
        dst_sprite: str,
        dst_name: str,
        asset_type: str,
    ) -> None:
        """
        Duplicate an asset.
        
        Args:
            src_sprite: Source sprite name (or 'Stage').
            src_name: Source asset name.
            dst_sprite: Destination sprite name (or 'Stage').
            dst_name: Destination asset name.
            asset_type: One of 'costume' or 'sound'.
        
        Raises:
            ManagerError: If source not found or destination exists.
        """
        self._validate_project()
        
        if src_sprite.lower() != "stage":
            self._validate_sprite(src_sprite)
        if dst_sprite.lower() != "stage":
            self._validate_sprite(dst_sprite)
        
        src_dir = _get_asset_dir(self.project_path, src_sprite, asset_type)
        dst_dir = _get_asset_dir(self.project_path, dst_sprite, asset_type)
        name_map_file = NAME_MAP_COSTUMES if asset_type == "costume" else NAME_MAP_SOUNDS
        
        # Find source file
        src_fname = _find_asset_file(src_dir, src_name, name_map_file)
        if not src_fname:
            raise ManagerError(f"Source asset not found: {src_name}")
        
        src_path = os.path.join(src_dir, src_fname)
        
        # Check if destination already exists
        dst_fname = _find_asset_file(dst_dir, dst_name, name_map_file)
        if dst_fname:
            raise ManagerError(f"Destination asset already exists: {dst_name}")
        
        ensure_dir(dst_dir)
        
        # Create new filename for destination
        md5_hash = compute_md5(src_path)
        ext = os.path.splitext(src_fname)[1].lower().lstrip(".")
        idx = get_next_asset_index(dst_dir)
        new_fname = f"{idx:03d}__{md5_hash}.{ext}"
        dst_path = os.path.join(dst_dir, new_fname)
        
        # Copy file
        shutil.copy2(src_path, dst_path)
        
        # Update destination name map
        dst_name_map = load_name_map(dst_dir, name_map_file)
        dst_name_map[new_fname] = dst_name
        write_json_file(os.path.join(dst_dir, name_map_file), dst_name_map)
        
        # Copy costume meta if applicable
        if asset_type == "costume":
            src_meta = load_costume_meta(src_dir)
            dst_meta = load_costume_meta(dst_dir)
            
            if src_fname in src_meta:
                dst_meta[new_fname] = src_meta[src_fname].copy()
            else:
                size = probe_image_size(dst_path, ext)
                dst_meta[new_fname] = {
                    "rotationCenterX": size[0] / 2 if size else 0,
                    "rotationCenterY": size[1] / 2 if size else 0,
                    "bitmapResolution": 1 if ext == "svg" else 2,
                }
            write_json_file(os.path.join(dst_dir, META_COSTUMES), dst_meta)


# ============================================================================
# CLI Command Functions (wrap Manager class for CLI usage)
# ============================================================================

def cmd_project_create(args: argparse.Namespace) -> None:
    """Create a new project with template contents."""
    project_path = args.path
    
    if os.path.exists(project_path):
        if not args.replace:
            error(f"Path already exists: {project_path}", "Use --replace to overwrite the existing project.")
        if not confirm(f"Replace existing project at '{project_path}'?", args.yes):
            info("Cancelled.")
            return
    
    try:
        Manager.create_project(project_path, replace=args.replace)
        info(f"Created new project at: {project_path}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_project_delete(args: argparse.Namespace) -> None:
    """Delete a project."""
    project_path = args.path
    
    if not os.path.exists(project_path):
        error(f"Project not found: {project_path}")
    
    if not confirm(f"Delete project at '{project_path}'? This cannot be undone!", args.yes):
        info("Cancelled.")
        return
    
    try:
        Manager.delete_project(project_path)
        info(f"Deleted project: {project_path}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_create(args: argparse.Namespace) -> None:
    """Create a new sprite."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        sprite_name = mgr.create_sprite(name=args.name)
        info(f"Created sprite: {sprite_name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_rename(args: argparse.Namespace) -> None:
    """Rename a sprite."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        new_name = mgr.rename_sprite(args.old_name, args.new_name)
        info(f"Renamed sprite: {args.old_name} -> {new_name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_delete(args: argparse.Namespace) -> None:
    """Delete a sprite."""
    project_path = get_project_path(args)
    
    if not confirm(f"Delete sprite '{args.name}'?", args.yes):
        info("Cancelled.")
        return
    
    try:
        mgr = Manager(project_path)
        mgr.delete_sprite(args.name)
        info(f"Deleted sprite: {args.name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_duplicate(args: argparse.Namespace) -> None:
    """Duplicate a sprite."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        dest_name = mgr.duplicate_sprite(args.source, dest=args.dest)
        info(f"Duplicated sprite: {args.source} -> {dest_name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_list(args: argparse.Namespace) -> None:
    """List all sprites."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        sprites = mgr.list_sprites()
        
        if not sprites:
            info("No sprites found.")
            return
        
        print(f"{'Name':<20} {'Position':<15} {'Size':<8} {'Visible':<8} {'Layer':<6}")
        print("-" * 60)
        for s in sprites:
            pos = f"({s['x']:.0f}, {s['y']:.0f})"
            visible = "Yes" if s["visible"] else "No"
            print(f"{s['name']:<20} {pos:<15} {s['size']:<8} {visible:<8} {s['layer']:<6}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_sprite_edit(args: argparse.Namespace) -> None:
    """Edit sprite properties."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        
        # Parse string booleans
        visible = None
        if args.visible is not None:
            visible = args.visible.lower() in ("true", "yes", "1")
        
        draggable = None
        if args.draggable is not None:
            draggable = args.draggable.lower() in ("true", "yes", "1")
        
        mgr.edit_sprite(
            name=args.name,
            x=args.x,
            y=args.y,
            size=args.size,
            direction=args.direction,
            visible=visible,
            layer=args.layer,
            costume=args.costume,
            rotation_style=args.rotation_style,
            draggable=draggable,
        )
        info(f"Updated sprite: {args.name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_var_list(args: argparse.Namespace) -> None:
    """List all variables and/or lists."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        entries = mgr.list_variables(list_only=args.list_only, var_only=args.var_only)
        
        if not entries:
            info("No variables or lists found.")
            return
        
        print(f"{'Name':<25} {'Type':<10} {'Scope':<15} {'Value':<30}")
        print("-" * 80)
        for entry in entries:
            truncated = truncate_value(entry["value"], 10)
            print(f"{entry['name']:<25} {entry['type']:<10} {entry['scope']:<15} {truncated:<30}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_var_show(args: argparse.Namespace) -> None:
    """Show the full value of a variable or list."""
    project_path = get_project_path(args)
    limit = min(args.limit or 250, 4000)
    
    try:
        mgr = Manager(project_path)
        
        # Try as variable first (unless --list specified)
        if not args.list:
            try:
                var = mgr.get_variable(args.name, sprite=args.sprite, is_list=False)
                value = str(var["value"])
                if len(value) > limit:
                    value = value[:limit] + f"... (truncated, {len(str(var['value']))} chars total)"
                print(f"Variable: {args.name}")
                print(f"Value: {value}")
                return
            except ManagerError:
                if args.var_only_flag:
                    raise
        
        # Try as list
        if not args.var_only_flag:
            lst = mgr.get_variable(args.name, sprite=args.sprite, is_list=True)
            items = lst["value"]
            print(f"List: {args.name}")
            print(f"Length: {len(items)} items")
            
            shown = 0
            for i, item in enumerate(items):
                item_str = str(item)
                if shown + len(item_str) > limit:
                    print(f"... (truncated at item {i}, {len(items)} items total)")
                    break
                print(f"  [{i}]: {item_str}")
                shown += len(item_str) + 10
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_var_create(args: argparse.Namespace) -> None:
    """Create a new variable or list."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        
        if args.list:
            # Parse value as list
            value = None
            if args.value:
                try:
                    value = json_module.loads(args.value)
                    if not isinstance(value, list):
                        value = [args.value]
                except (json_module.JSONDecodeError, ValueError):
                    value = [args.value]
            
            mgr.create_list(
                name=args.name,
                sprite=args.sprite,
                value=value,
                monitor_visible=args.monitor_visible,
            )
            info(f"Created list: {args.name}")
        else:
            value = args.value if args.value is not None else 0
            mgr.create_variable(
                name=args.name,
                sprite=args.sprite,
                value=value,
                cloud=args.cloud,
                monitor_mode=args.monitor_mode,
                monitor_visible=args.monitor_visible,
            )
            name = args.name
            if args.cloud and not name.startswith(CLOUD_PREFIX):
                name = CLOUD_PREFIX + " " + name
            info(f"Created variable: {name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_var_bulk_create(args: argparse.Namespace) -> None:
    """Bulk create variables or lists."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        result = mgr.bulk_create_variables(args.names, sprite=args.sprite, is_list=args.list)
        
        item_type = "lists" if args.list else "variables"
        msg = f"Created {result['created']} {item_type}"
        if result['skipped']:
            msg += f", skipped {result['skipped']} (already exist)"
        info(msg)
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_var_edit(args: argparse.Namespace) -> None:
    """Edit a variable or list."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        mgr.edit_variable(
            name=args.name,
            sprite=args.sprite,
            is_list=args.list,
            rename=args.rename,
            value=args.value,
            scope=args.scope,
            cloud=args.cloud,
            monitor_x=args.monitor_x,
            monitor_y=args.monitor_y,
        )
        info(f"Updated {'list' if args.list else 'variable'}: {args.name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_asset_create(args: argparse.Namespace) -> None:
    """Create a new asset from a source file."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        mgr.create_asset(
            source=args.source,
            sprite=args.sprite,
            name=args.name,
            asset_type=args.type,
        )
        info(f"Created {args.type}: {args.name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_asset_list(args: argparse.Namespace) -> None:
    """List assets for a sprite."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        assets = mgr.list_assets(sprite=args.sprite, asset_type=args.type)
        
        if not assets:
            info(f"No assets found for {args.sprite}.")
            return
        
        print(f"{'Name':<25} {'Type':<10} {'Format':<8} {'Size':<15}")
        print("-" * 60)
        for asset in assets:
            if asset['type'] == 'costume':
                size_str = f"{asset['width']}x{asset['height']}" if asset.get('width') else "?"
            else:
                file_size = asset.get('file_size', 0)
                size_str = f"{file_size // 1024}KB" if file_size >= 1024 else f"{file_size}B"
            print(f"{asset['name']:<25} {asset['type']:<10} {asset['format']:<8} {size_str:<15}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_asset_delete(args: argparse.Namespace) -> None:
    """Delete an asset."""
    project_path = get_project_path(args)
    
    if not confirm(f"Delete {args.type} '{args.name}'?", args.yes):
        info("Cancelled.")
        return
    
    try:
        mgr = Manager(project_path)
        mgr.delete_asset(sprite=args.sprite, name=args.name, asset_type=args.type)
        info(f"Deleted {args.type}: {args.name}")
    except ManagerError as e:
        error(e.message, e.detail)


def cmd_asset_duplicate(args: argparse.Namespace) -> None:
    """Duplicate an asset."""
    project_path = get_project_path(args)
    
    try:
        mgr = Manager(project_path)
        mgr.duplicate_asset(
            src_sprite=args.src_sprite,
            src_name=args.src_name,
            dst_sprite=args.dst_sprite,
            dst_name=args.dst_name,
            asset_type=args.type,
        )
        info(f"Duplicated {args.type}: {args.src_name} -> {args.dst_name}")
    except ManagerError as e:
        error(e.message, e.detail)


# ============================================================================
# Argument Parser Setup
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="manager.py",
        description="TextScratch Project Manager CLI. See README.md for detailed documentation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manager.py project create MyProject
  python manager.py sprite create --name Player
  python manager.py var list
  python manager.py asset create image.png Sprite1 my_costume --type costume

For more information, see README.md
""",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed error messages")
    parser.add_argument("--project", "-p", default=DEFAULT_PROJECT_PATH, help=f"Project path (default: {DEFAULT_PROJECT_PATH})")
    
    subparsers = parser.add_subparsers(dest="command", help="Command category")
    
    # ========== Project Commands ==========
    project_parser = subparsers.add_parser("project", help="Project management commands")
    project_sub = project_parser.add_subparsers(dest="subcommand", help="Project subcommand")
    
    # project create
    p_create = project_sub.add_parser("create", help="Create a new project")
    p_create.add_argument("path", help="Path for the new project")
    p_create.add_argument("--replace", action="store_true", help="Replace existing project if it exists")
    p_create.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    p_create.set_defaults(func=cmd_project_create)
    
    # project delete
    p_delete = project_sub.add_parser("delete", help="Delete a project")
    p_delete.add_argument("path", help="Path to the project to delete")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    p_delete.set_defaults(func=cmd_project_delete)
    
    # ========== Sprite Commands ==========
    sprite_parser = subparsers.add_parser("sprite", help="Sprite management commands")
    sprite_sub = sprite_parser.add_subparsers(dest="subcommand", help="Sprite subcommand")
    
    # sprite create
    s_create = sprite_sub.add_parser("create", help="Create a new sprite")
    s_create.add_argument("--name", "-n", help="Sprite name (default: SpriteN)")
    s_create.set_defaults(func=cmd_sprite_create)
    
    # sprite rename
    s_rename = sprite_sub.add_parser("rename", help="Rename a sprite")
    s_rename.add_argument("old_name", help="Current sprite name")
    s_rename.add_argument("new_name", help="New sprite name")
    s_rename.set_defaults(func=cmd_sprite_rename)
    
    # sprite delete
    s_delete = sprite_sub.add_parser("delete", help="Delete a sprite")
    s_delete.add_argument("name", help="Sprite name to delete")
    s_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    s_delete.set_defaults(func=cmd_sprite_delete)
    
    # sprite duplicate
    s_dup = sprite_sub.add_parser("duplicate", help="Duplicate a sprite")
    s_dup.add_argument("source", help="Source sprite name")
    s_dup.add_argument("--dest", "-d", help="Destination sprite name (default: auto-generated)")
    s_dup.set_defaults(func=cmd_sprite_duplicate)
    
    # sprite list
    s_list = sprite_sub.add_parser("list", help="List all sprites")
    s_list.set_defaults(func=cmd_sprite_list)
    
    # sprite edit
    s_edit = sprite_sub.add_parser("edit", help="Edit sprite properties")
    s_edit.add_argument("name", help="Sprite name")
    s_edit.add_argument("--x", type=float, help="X position")
    s_edit.add_argument("--y", type=float, help="Y position")
    s_edit.add_argument("--size", type=float, help="Size (percentage)")
    s_edit.add_argument("--direction", type=float, help="Direction (degrees)")
    s_edit.add_argument("--visible", help="Visible (true/false)")
    s_edit.add_argument("--layer", type=int, help="Layer order")
    s_edit.add_argument("--costume", type=int, help="Current costume index")
    s_edit.add_argument("--rotation-style", choices=["all around", "left-right", "don't rotate"], help="Rotation style")
    s_edit.add_argument("--draggable", help="Draggable (true/false)")
    s_edit.set_defaults(func=cmd_sprite_edit)
    
    # ========== Variable/List Commands ==========
    var_parser = subparsers.add_parser("var", help="Variable and list management commands")
    var_sub = var_parser.add_subparsers(dest="subcommand", help="Variable subcommand")
    
    # var list
    v_list = var_sub.add_parser("list", help="List all variables and lists")
    v_list.add_argument("--list", "-l", dest="list_only", action="store_true", help="Show only lists")
    v_list.add_argument("--var", dest="var_only", action="store_true", help="Show only variables")
    v_list.set_defaults(func=cmd_var_list)
    
    # var show
    v_show = var_sub.add_parser("show", help="Show full value of a variable or list")
    v_show.add_argument("name", help="Variable or list name")
    v_show.add_argument("--sprite", "-s", help="Sprite name (omit for global)")
    v_show.add_argument("--list", "-l", action="store_true", help="Target is a list")
    v_show.add_argument("--limit", type=int, default=250, help="Truncation limit (default: 250, max: 4000)")
    v_show.add_argument("--var", dest="var_only_flag", action="store_true", help="Target is a variable (default)")
    v_show.set_defaults(func=cmd_var_show)
    
    # var create
    v_create = var_sub.add_parser("create", help="Create a new variable or list")
    v_create.add_argument("name", help="Variable or list name")
    v_create.add_argument("--sprite", "-s", help="Sprite name for local scope (omit for global)")
    v_create.add_argument("--list", "-l", action="store_true", help="Create a list instead of variable")
    v_create.add_argument("--value", "-v", help="Initial value (default: 0 for vars, [] for lists)")
    v_create.add_argument("--cloud", "-c", action="store_true", help="Make it a cloud variable (adds ☁ prefix)")
    v_create.add_argument("--monitor-mode", choices=["default", "slider", "large"], help="Monitor display mode")
    v_create.add_argument("--monitor-visible", action="store_true", help="Make monitor visible")
    v_create.set_defaults(func=cmd_var_create)
    
    # var bulk-create
    v_bulk = var_sub.add_parser("bulk-create", help="Bulk create variables or lists")
    v_bulk.add_argument("names", nargs="+", help="Names of variables or lists to create")
    v_bulk.add_argument("--sprite", "-s", help="Sprite name for local scope (omit for global)")
    v_bulk.add_argument("--list", "-l", action="store_true", help="Create lists instead of variables")
    v_bulk.set_defaults(func=cmd_var_bulk_create)
    
    # var edit
    v_edit = var_sub.add_parser("edit", help="Edit a variable or list")
    v_edit.add_argument("name", help="Variable or list name")
    v_edit.add_argument("--sprite", "-s", help="Sprite name (omit for global)")
    v_edit.add_argument("--list", "-l", action="store_true", help="Target is a list")
    v_edit.add_argument("--rename", help="New name")
    v_edit.add_argument("--value", "-v", help="New value")
    v_edit.add_argument("--scope", help="New scope ('global' or sprite name)")
    v_edit.add_argument("--cloud", type=lambda x: x.lower() in ('true', '1', 'yes'), nargs="?", const=True, help="Cloud variable flag (true/false)")
    v_edit.add_argument("--monitor-x", type=int, help="Monitor X position")
    v_edit.add_argument("--monitor-y", type=int, help="Monitor Y position")
    v_edit.set_defaults(func=cmd_var_edit)
    
    # ========== Asset Commands ==========
    asset_parser = subparsers.add_parser("asset", help="Asset management commands")
    asset_sub = asset_parser.add_subparsers(dest="subcommand", help="Asset subcommand")
    
    # asset create
    a_create = asset_sub.add_parser("create", help="Create a new asset from a source file")
    a_create.add_argument("source", help="Source file path")
    a_create.add_argument("sprite", help="Sprite name (or 'Stage')")
    a_create.add_argument("name", help="Asset display name")
    a_create.add_argument("--type", "-t", required=True, choices=["costume", "sound"], help="Asset type")
    a_create.set_defaults(func=cmd_asset_create)
    
    # asset list
    a_list = asset_sub.add_parser("list", help="List assets for a sprite")
    a_list.add_argument("sprite", help="Sprite name (or 'Stage')")
    a_list.add_argument("--type", "-t", choices=["costume", "sound"], help="Filter by asset type")
    a_list.set_defaults(func=cmd_asset_list)
    
    # asset delete
    a_delete = asset_sub.add_parser("delete", help="Delete an asset")
    a_delete.add_argument("sprite", help="Sprite name (or 'Stage')")
    a_delete.add_argument("name", help="Asset display name")
    a_delete.add_argument("--type", "-t", required=True, choices=["costume", "sound"], help="Asset type")
    a_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    a_delete.set_defaults(func=cmd_asset_delete)
    
    # asset duplicate
    a_dup = asset_sub.add_parser("duplicate", help="Duplicate an asset")
    a_dup.add_argument("src_sprite", help="Source sprite name (or 'Stage')")
    a_dup.add_argument("src_name", help="Source asset name")
    a_dup.add_argument("dst_sprite", help="Destination sprite name (or 'Stage')")
    a_dup.add_argument("dst_name", help="Destination asset name")
    a_dup.add_argument("--type", "-t", required=True, choices=["costume", "sound"], help="Asset type")
    a_dup.set_defaults(func=cmd_asset_duplicate)
    
    return parser


# ============================================================================
# Main Entry Point
# ============================================================================

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    
    global verbose_mode
    verbose_mode = args.verbose
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if not hasattr(args, "func") or not args.func:
        # No subcommand specified
        subparser_map = {
            "project": "project",
            "sprite": "sprite",
            "var": "var",
            "asset": "asset",
        }
        if args.command in subparser_map:
            parser.parse_args([args.command, "--help"])
        sys.exit(0)
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        if verbose_mode:
            import traceback
            traceback.print_exc()
        else:
            error(str(e))


if __name__ == "__main__":
    main()
