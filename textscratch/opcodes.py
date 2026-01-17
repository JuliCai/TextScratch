import re
import string
from typing import Dict, List, Tuple

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
    "motion_goto_menu": "[{TO} v]",
    "motion_gotoxy": "go to x: {X} y: {Y}",
    "motion_glideto": "glide {SECS} secs to {TO}",
    "motion_glideto_menu": "[{TO} v]",
    "motion_glidesecstoxy": "glide {SECS} secs to x: {X} y: {Y}",
    "motion_pointindirection": "point in direction {DIRECTION}",
    "motion_pointtowards": "point towards {TOWARDS}",
    "motion_pointtowards_menu": "[{TOWARDS} v]",
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
    "looks_switchbackdropto": "switch backdrop to {BACKDROP}",
    "looks_backdrops": "[{BACKDROP} v]",
    "looks_costumenumbername": "(costume [{NUMBER_NAME} v])",
    "looks_backdropnumbername": "(backdrop [{NUMBER_NAME} v])",
    "looks_costume": "[{COSTUME} v]",
    "looks_nextbackdrop": "next backdrop",
    "looks_changesizeby": "change size by {CHANGE}",
    "looks_setsizeto": "set size to {SIZE} %",
    "looks_changeeffectby": "change [{EFFECT} v] effect by {CHANGE}",
    "looks_seteffectto": "set [{EFFECT} v] effect to {VALUE}",
    "looks_cleargraphiceffects": "clear graphic effects",
    "looks_show": "show",
    "looks_hide": "hide",
    "looks_gotofrontback": "go to [{FRONT_BACK} v] layer",
    "looks_goforwardbackwardlayers": "go [{FORWARD_BACKWARD} v] {NUM} layers",
    "looks_size": "(size)",

    # Sound
    "sound_playuntildone": "play sound {SOUND_MENU} until done",
    "sound_play": "start sound {SOUND_MENU}",
    "sound_stopallsounds": "stop all sounds",
    "sound_changeeffectby": "change [{EFFECT} v] effect by {VALUE}",
    "sound_seteffectto": "set [{EFFECT} v] effect to {VALUE}",
    "sound_changevolumeby": "change volume by {VOLUME}",
    "sound_setvolumeto": "set volume to {VOLUME} %",
    "sound_cleareffects": "clear sound effects",
    "sound_volume": "(volume)",

    # Pen
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penup": "pen up",
    "pen_pendown": "pen down",
    "pen_setpenparamto": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_changepenparamby": "change pen ({COLOR_PARAM} v) by {VALUE}",
    "pen_changePenColorParamBy": "change pen ({COLOR_PARAM} v) by {VALUE}",
    "pen_setpencolortocolor": "set pen color to {COLOR}",
    "pen_changepensizeby": "change pen size by {SIZE}",
    "pen_changePenSizeBy": "change pen size by {SIZE}",
    "pen_setpensizeto": "set pen size to {SIZE}",

    # Pen (CamelCase variants found in some files)
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    "pen_penUp": "pen up",
    "pen_penDown": "pen down",
    "pen_setPenColorParamTo": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_menu_colorParam": "{colorParam}",

    # Sound Menus
    "sound_sounds_menu": "[{SOUND_MENU} v]",

    # Motion Reporters
    "motion_xposition": "(x position)",
    "motion_yposition": "(y position)",
    "motion_direction": "(direction)",

    # Control
    "control_wait": "wait {DURATION} seconds",
    "control_repeat": "repeat {TIMES}",
    "control_forever": "forever",
    "control_if": "if {CONDITION} then",
    "control_if_else": "if {CONDITION} then",
    "control_wait_until": "wait until {CONDITION}",
    "control_repeat_until": "repeat until {CONDITION}",
    "control_while": "while {CONDITION}",
    "control_stop": "stop [{STOP_OPTION} v]",
    "control_start_as_clone": "when I start as a clone",
    "control_create_clone_of": "create clone of {CLONE_OPTION}",
    "control_create_clone_of_menu": "[{CLONE_OPTION} v]",
    "control_delete_this_clone": "delete this clone",

    # Sensing
    "sensing_touchingobject": "<touching {TOUCHINGOBJECTMENU} ?>",
    "sensing_touchingobjectmenu": "[{TOUCHINGOBJECTMENU} v]",
    "sensing_touchingcolor": "<touching color {COLOR} ?>",
    "sensing_coloristouchingcolor": "<color {COLOR} is touching {COLOR2} ?>",
    "sensing_distanceto": "(distance to {DISTANCETOMENU})",
    "sensing_distancetomenu": "[{DISTANCETOMENU} v]",
    "sensing_askandwait": "ask {QUESTION} and wait",
    "sensing_answer": "(answer)",
    "sensing_keypressed": "<key [{KEY_OPTION} v] pressed?>",
    "sensing_keyoptions": "{KEY_OPTION}",
    "sensing_mousedown": "<mouse down?>",
    "sensing_mousex": "(mouse x)",
    "sensing_mousey": "(mouse y)",
    "sensing_setdragmode": "set drag mode [{DRAG_MODE} v]",
    "sensing_loudness": "(loudness)",
    "sensing_timer": "(timer)",
    "sensing_resettimer": "reset timer",
    "sensing_of": "([{PROPERTY} v] of {OBJECT})",
    "sensing_of_object_menu": "[{OBJECT} v]",
    "sensing_current": "(current [{CURRENTMENU} v])",
    "sensing_dayssince2000": "(days since 2000)",
    "sensing_username": "(username)",

    # Operators
    "operator_add": "({NUM1} + {NUM2})",
    "operator_subtract": "({NUM1} - {NUM2})",
    "operator_multiply": "({NUM1} * {NUM2})",
    "operator_divide": "({NUM1} / {NUM2})",
    "operator_random": "(pick random {FROM} to {TO})",
    "operator_gt": "<{OPERAND1} > {OPERAND2}>",
    "operator_lt": "<{OPERAND1} < {OPERAND2}>",
    "operator_equals": "<{OPERAND1} = {OPERAND2}>",
    "operator_and": "<{OPERAND1} and {OPERAND2}>",
    "operator_or": "<{OPERAND1} or {OPERAND2}>",
    "operator_not": "<not {OPERAND}>",
    "operator_join": "(join {STRING1} {STRING2})",
    "operator_letter_of": "(letter {LETTER} of {STRING})",
    "operator_length": "(length of {STRING})",
    "operator_contains": "<{STRING1} contains {STRING2} ?>",
    "operator_mod": "({NUM1} mod {NUM2})",
    "operator_round": "(round {NUM})",
    "operator_mathop": "([{OPERATOR} v] of {NUM})",

    # Variables
    "data_variable": "({VARIABLE})",
    "data_setvariableto": "set [{VARIABLE} v] to {VALUE}",
    "data_changevariableby": "change [{VARIABLE} v] by {VALUE}",
    "data_showvariable": "show variable [{VARIABLE} v]",
    "data_hidevariable": "hide variable [{VARIABLE} v]",
    "data_listcontents": "({LIST})",
    "data_addtolist": "add {ITEM} to [{LIST} v]",
    "data_deleteoflist": "delete {INDEX} of [{LIST} v]",
    "data_deletealloflist": "delete all of [{LIST} v]",
    "data_insertatlist": "insert {ITEM} at {INDEX} of [{LIST} v]",
    "data_replaceitemoflist": "replace item {INDEX} of [{LIST} v] with {ITEM}",
    "data_itemoflist": "(item {INDEX} of [{LIST} v])",
    "data_itemnumoflist": "(item # of {ITEM} in [{LIST} v])",
    "data_lengthoflist": "(length of [{LIST} v])",
    "data_listcontainsitem": "<[{LIST} v] contains {ITEM} ?>",
    "data_showlist": "show list [{LIST} v]",
    "data_hidelist": "hide list [{LIST} v]",

    # Custom Blocks (Procedures)
    "argument_reporter_string_number": "{{{VALUE}}}",
    "argument_reporter_boolean": "{{<{VALUE}>}}",
}

# Normalize legacy/variant opcodes to canonical Scratch 3 names when rebuilding blocks
OPCODE_NORMALIZATION: Dict[str, str] = {
    "pen_setpensizeto": "pen_setPenSizeTo",
    "pen_setpencolortocolor": "pen_setPenColorToColor",
    "pen_penup": "pen_penUp",
    "pen_pendown": "pen_penDown",
    "pen_setpenparamto": "pen_setPenColorParamTo",
    "pen_changePenSizeBy": "pen_changepensizeby",
}

# Placeholders that should be treated as fields (instead of inputs) when rebuilding blocks
OPCODE_FIELDS: Dict[str, set] = {
    "event_whenkeypressed": {"KEY_OPTION"},
    "sensing_keyoptions": {"KEY_OPTION"},
    "event_whenbackdropswitchesto": {"BACKDROP"},
    "event_whengreaterthan": {"WHENGREATERTHANMENU"},
    "event_whenbroadcastreceived": {"BROADCAST_OPTION"},
    "control_stop": {"STOP_OPTION"},
    "looks_backdropnumbername": {"NUMBER_NAME"},
    "looks_costumenumbername": {"NUMBER_NAME"},
    "looks_costume": {"COSTUME"},
    "looks_backdrops": {"BACKDROP"},
    "looks_seteffectto": {"EFFECT"},
    "looks_changeeffectby": {"EFFECT"},
    "looks_gotofrontback": {"FRONT_BACK"},
    "looks_goforwardbackwardlayers": {"FORWARD_BACKWARD"},
    "motion_setrotationstyle": {"STYLE"},
    "motion_goto_menu": {"TO"},
    "motion_glideto_menu": {"TO"},
    "motion_pointtowards_menu": {"TOWARDS"},
    "sound_changeeffectby": {"EFFECT"},
    "sound_seteffectto": {"EFFECT"},
    "sensing_setdragmode": {"DRAG_MODE"},
    "sensing_distancetomenu": {"DISTANCETOMENU"},
    "sensing_of_object_menu": {"OBJECT"},
    "sensing_of": {"PROPERTY"},
    "sensing_current": {"CURRENTMENU"},
    # Pen color parameter is handled via a menu shadow, not a plain field.
    "data_setvariableto": {"VARIABLE"},
    "data_changevariableby": {"VARIABLE"},
    "data_showvariable": {"VARIABLE"},
    "data_hidevariable": {"VARIABLE"},
    "data_addtolist": {"LIST"},
    "data_deleteoflist": {"LIST"},
    "data_deletealloflist": {"LIST"},
    "data_insertatlist": {"LIST"},
    "data_replaceitemoflist": {"LIST"},
    "data_itemoflist": {"LIST"},
    "data_itemnumoflist": {"LIST"},
    "data_lengthoflist": {"LIST"},
    "data_listcontainsitem": {"LIST"},
    "data_showlist": {"LIST"},
    "data_hidelist": {"LIST"},
    "data_variable": {"VARIABLE"},
    "data_listcontents": {"LIST"},
    "operator_mathop": {"OPERATOR"},
    "argument_reporter_string_number": {"VALUE"},
    "argument_reporter_boolean": {"VALUE"},
}

CONTROL_BLOCKS = {"control_forever", "control_repeat", "control_repeat_until", "control_if", "control_if_else"}

MATH_OPERATORS = {
    "abs",
    "floor",
    "ceiling",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "ln",
    "log",
    "e ^",
    "10 ^",
}


def build_opcode_patterns() -> List[Tuple[re.Pattern[str], str, List[str]]]:
    patterns_with_score: List[Tuple[int, int, re.Pattern[str], str, List[str]]] = []
    formatter = string.Formatter()
    for opcode, fmt in OPCODE_MAP.items():
        regex_parts: List[str] = []
        placeholders: List[str] = []
        literal_len = 0
        for literal, field_name, _, _ in formatter.parse(fmt):
            regex_parts.append(re.escape(literal))
            literal_len += len(literal)
            if field_name:
                placeholders.append(field_name)
                # Greedy capture so nested literals (e.g., " of [" inside math/list expressions)
                # don't prematurely terminate the placeholder match.
                regex_parts.append(r"(?P<%s>.+)" % field_name)
        pattern = re.compile("^" + "".join(regex_parts) + "$")
        patterns_with_score.append((literal_len, len(placeholders), pattern, opcode, placeholders))

    # Sort patterns to prefer those with more literal text (more specific) first, then fewer placeholders
    patterns_with_score.sort(key=lambda item: (-item[0], item[1]))
    return [(pat, op, ph) for _, _, pat, op, ph in patterns_with_score]


OPCODE_PATTERNS = build_opcode_patterns()
