"""Constants used throughout the text-to-blocks conversion."""

from typing import Any, Dict, List, Tuple

# Binary operators with their opcodes and input names
BINARY_OPERATOR_TOKENS: List[Tuple[str, str, str, str]] = [
    (" + ", "operator_add", "NUM1", "NUM2"),
    (" - ", "operator_subtract", "NUM1", "NUM2"),
    (" * ", "operator_multiply", "NUM1", "NUM2"),
    (" / ", "operator_divide", "NUM1", "NUM2"),
    (" mod ", "operator_mod", "NUM1", "NUM2"),
]

# Opcodes that represent menu shadow blocks
MENU_SHADOW_OPCODES = {
    "looks_costume",
    "looks_backdrops",
    "sound_sounds_menu",
    "pen_menu_colorParam",
    "sensing_keyoptions",
    "sensing_distancetomenu",
    "sensing_of_object_menu",
    "motion_goto_menu",
    "motion_glideto_menu",
    "motion_pointtowards_menu",
    "control_create_clone_of_menu",
    "sensing_touchingobjectmenu",
}

# Map input names to their shadow menu opcodes and field names
MENU_SHADOW_FOR_INPUT: Dict[str, Tuple[str, str]] = {
    "KEY_OPTION": ("sensing_keyoptions", "KEY_OPTION"),
    "DISTANCETOMENU": ("sensing_distancetomenu", "DISTANCETOMENU"),
    "TOUCHINGOBJECTMENU": ("sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU"),
    "CLONE_OPTION": ("control_create_clone_of_menu", "CLONE_OPTION"),
    "COLOR_PARAM": ("pen_menu_colorParam", "colorParam"),
    "COSTUME": ("looks_costume", "COSTUME"),
    "BACKDROP": ("looks_backdrops", "BACKDROP"),
    "SOUND_MENU": ("sound_sounds_menu", "SOUND_MENU"),
    "OBJECT": ("sensing_of_object_menu", "OBJECT"),
}

# Input shadow kinds follow scratch-vm's SB3 primitive IDs (4 through 10).
NUMERIC_INPUTS = {
    "motion_movesteps": {"STEPS": 4}, "motion_turnright": {"DEGREES": 4},
    "motion_turnleft": {"DEGREES": 4}, "motion_gotoxy": {"X": 4, "Y": 4},
    "motion_glideto": {"SECS": 5}, "motion_glidesecstoxy": {"SECS": 5, "X": 4, "Y": 4},
    "motion_pointindirection": {"DIRECTION": 8}, "motion_changexby": {"DX": 4},
    "motion_setx": {"X": 4}, "motion_changeyby": {"DY": 4}, "motion_sety": {"Y": 4},
    "looks_sayforsecs": {"SECS": 4}, "looks_thinkforsecs": {"SECS": 4},
    "looks_changesizeby": {"CHANGE": 4}, "looks_setsizeto": {"SIZE": 4},
    "looks_changeeffectby": {"CHANGE": 4}, "looks_seteffectto": {"VALUE": 4},
    "looks_goforwardbackwardlayers": {"NUM": 7}, "sound_changeeffectby": {"VALUE": 4},
    "sound_seteffectto": {"VALUE": 4}, "sound_changevolumeby": {"VOLUME": 4},
    "sound_setvolumeto": {"VOLUME": 4}, "event_whengreaterthan": {"VALUE": 4},
    "control_wait": {"DURATION": 5}, "control_repeat": {"TIMES": 6},
    "control_for_each": {"VALUE": 6}, "data_changevariableby": {"VALUE": 4},
    "data_deleteoflist": {"INDEX": 7}, "data_insertatlist": {"INDEX": 7},
    "data_replaceitemoflist": {"INDEX": 7}, "data_itemoflist": {"INDEX": 7},
    "operator_add": {"NUM1": 4, "NUM2": 4}, "operator_subtract": {"NUM1": 4, "NUM2": 4},
    "operator_multiply": {"NUM1": 4, "NUM2": 4}, "operator_divide": {"NUM1": 4, "NUM2": 4},
    "operator_mod": {"NUM1": 4, "NUM2": 4}, "operator_random": {"FROM": 4, "TO": 4},
    "operator_round": {"NUM": 4}, "operator_mathop": {"NUM": 4},
    "operator_letter_of": {"LETTER": 6}, "pen_setPenSizeTo": {"SIZE": 4},
    "pen_changePenSizeBy": {"SIZE": 4}, "pen_setPenColorParamTo": {"VALUE": 4},
    "pen_changePenColorParamBy": {"VALUE": 4},
}
