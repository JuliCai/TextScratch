import argparse
import hashlib
import json
import os
import re
import shutil
import string
import zipfile
from itertools import count
from typing import Any, Dict, List, Optional, Tuple

try:  # Optional dependency for accurate image sizing
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Image = None


# Mapping of opcodes to ScratchBlocks format strings
# Keys are opcodes, values are format strings using input names
OPCODE_MAP: Dict[str, str] = {
    # Events
    "event_whenflagclicked": "when green flag clicked",
    "event_whenkeypressed": "when [{KEY_OPTION} v] key pressed",
    "event_whenthisspriteclicked": "when this sprite clicked",
    "event_whenbackdropswitchesto": "when backdrop switches to [{BACKDROP} v]",
    "event_whengreaterthan": "when [{WHENGREATERTHANMENU} v] > {VALUE}",
    "event_whenbroadcastreceived": "when I receive [{BROADCAST_OPTION} v]",
    "event_broadcast": "broadcast {BROADCAST_INPUT}",
    "event_broadcastandwait": "broadcast {BROADCAST_INPUT} and wait",

    # Motion
    "motion_movesteps": "move {STEPS} steps",
    "motion_turnright": "turn right {DEGREES} degrees",
    "motion_turnleft": "turn left {DEGREES} degrees",
    "motion_goto": "go to {TO}",
    "motion_gotoxy": "go to x: {X} y: {Y}",
    "motion_glideto": "glide {SECS} secs to {TO}",
    "motion_glidesecstoxy": "glide {SECS} secs to x: {X} y: {Y}",
    "motion_pointindirection": "point in direction {DIRECTION}",
    "motion_pointtowards": "point towards {TOWARDS}",
    "motion_changexby": "change x by {DX}",
    "motion_setx": "set x to {X}",
    "motion_changeyby": "change y by {DY}",
    "motion_sety": "set y to {Y}",
    "motion_ifonedgebounce": "if on edge, bounce",
    "motion_setrotationstyle": "set rotation style [{STYLE} v]",

    # Looks
    "looks_sayforsecs": "say {MESSAGE} for {SECS} seconds",
    "looks_say": "say {MESSAGE}",
    "looks_thinkforsecs": "think {MESSAGE} for {SECS} seconds",
    "looks_think": "think {MESSAGE}",
    "looks_switchcostumeto": "switch costume to {COSTUME}",
    "looks_nextcostume": "next costume",
    import argparse

    from textscratch.project_io import convert_folder_to_sb3, convert_project


    def parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description="Convert between Scratch .sb3 archives and scratchblocks folders."
        )
        parser.add_argument("input", help="Path to the .sb3 project file or project folder")
        parser.add_argument("--output-dir", default="Project", help="Output directory for the converted project")
        parser.add_argument("--no-clean", action="store_true", help="Do not remove the output directory before writing")
        parser.add_argument("--to-sb3", action="store_true", help="Convert from a project folder back to a .sb3 archive")
        parser.add_argument("--sb3-output", default="output.sb3", help="Output .sb3 path when using --to-sb3")
        return parser.parse_args()


    def main() -> None:
        args = parse_args()
        if args.to_sb3:
            convert_folder_to_sb3(args.input, args.sb3_output)
        else:
            convert_project(args.input, args.output_dir, clean=not args.no_clean)


    if __name__ == "__main__":
        main()
    "pen_changepenparamby": "change pen ({COLOR_PARAM} v) by {VALUE}",

    "pen_setpencolortocolor": "set pen color to {COLOR}",
