import json
import zipfile
import os
import string

INPUT_FILE = "Filler.sprite3" 
OUTPUT_FILE = "Filler.txt"

# Mapping of opcodes to ScratchBlocks format strings
# Keys are opcodes, values are format strings using input names
OPCODE_MAP = {
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
    "looks_switchbackdropto": "switch backdrop to {BACKDROP}",
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

    # Sound
    "sound_playuntildone": "play sound {SOUND_MENU} until done",
    "sound_play": "start sound {SOUND_MENU}",
    "sound_stopallsounds": "stop all sounds",
    "sound_changeeffectby": "change [{EFFECT} v] effect by {VALUE}",
    "sound_seteffectto": "set [{EFFECT} v] effect to {VALUE}",
    "sound_changevolumeby": "change volume by {VOLUME}",
    "sound_setvolumeto": "set volume to {VOLUME} %",

    # Pen
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penup": "pen up",
    "pen_pendown": "pen down",
    "pen_setpenparamto": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_changepenparamby": "change pen ({COLOR_PARAM} v) by {VALUE}",
    "pen_setpencolortocolor": "set pen color to {COLOR}",
    "pen_changepensizeby": "change pen size by {SIZE}",
    "pen_setpensizeto": "set pen size to {SIZE}",
    
    # Pen (CamelCase variants found in some files)
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    "pen_penUp": "pen up",
    "pen_penDown": "pen down",
    "pen_setPenColorParamTo": "set pen ({COLOR_PARAM} v) to {VALUE}",
    "pen_menu_colorParam": "{colorParam}",

    # Sound Menus
    "sound_sounds_menu": "{SOUND_MENU}",
    
    # Motion Reporters
    "motion_xposition": "(x position)",
    "motion_yposition": "(y position)",
    "motion_direction": "(direction)",

    # Control
    "control_wait": "wait {DURATION} seconds",
    "control_repeat": "repeat {TIMES}", # C-block
    "control_forever": "forever", # C-block
    "control_if": "if {CONDITION} then", # C-block
    "control_if_else": "if {CONDITION} then", # C-block (special handling for else)
    "control_wait_until": "wait until {CONDITION}",
    "control_repeat_until": "repeat until {CONDITION}", # C-block
    "control_stop": "stop [{STOP_OPTION} v]",
    "control_start_as_clone": "when I start as a clone",
    "control_create_clone_of": "create clone of {CLONE_OPTION}",
    "control_delete_this_clone": "delete this clone",

    # Sensing
    "sensing_touchingobject": "<touching {TOUCHINGOBJECTMENU} ?>",
    "sensing_touchingcolor": "<touching color {COLOR} ?>",
    "sensing_coloristouchingcolor": "<color {COLOR} is touching {COLOR2} ?>",
    "sensing_distanceto": "(distance to {DISTANCETOMENU})",
    "sensing_askandwait": "ask {QUESTION} and wait",
    "sensing_answer": "(answer)",
    "sensing_keypressed": "<key [{KEY_OPTION} v] pressed?>",
    "sensing_mousedown": "<mouse down?>",
    "sensing_mousex": "(mouse x)",
    "sensing_mousey": "(mouse y)",
    "sensing_setdragmode": "set drag mode [{DRAG_MODE} v]",
    "sensing_loudness": "(loudness)",
    "sensing_timer": "(timer)",
    "sensing_resettimer": "reset timer",
    "sensing_of": "([{PROPERTY} v] of {OBJECT})",
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
    "argument_reporter_string_number": "({VALUE})",
    "argument_reporter_boolean": "<{VALUE}>",
}

def parse_input(input_data, blocks):
    # input_data is like [1, [10, "Hello!"]] or [1, "BLOCK_ID"]
    # The first element is shadow status (1=shadow, 2=no shadow, 3=shadow obscured)
    # The second element is the value.
    
    if not input_data:
        return ""
        
    val = input_data[1]
    
    if isinstance(val, str):
        # It's a block ID
        return generate_block_code(val, blocks).strip() # Strip newline for inputs
    elif isinstance(val, list):
        # It's a primitive
        # [type, value]
        # Types: 4-8 number, 9 color, 10 string, 11 broadcast, 12 variable, 13 list
        primitive_type = val[0]
        primitive_value = val[1]
        
        if primitive_type in [4, 5, 6, 7, 8]: # Numbers
            return f"[{primitive_value}]"
        elif primitive_type == 9: # Color
            return f"({primitive_value})"
        elif primitive_type == 10: # String
            return f"[{primitive_value}]" # Wrap strings in brackets
        elif primitive_type == 11: # Broadcast
            return primitive_value
        elif primitive_type == 12: # Variable
            return f"({primitive_value})"
        elif primitive_type == 13: # List
            return f"({primitive_value})"
        else:
            return str(primitive_value)
    return ""

def parse_field(field_data):
    # field_data is like ["KEY_OPTION", "space"] or ["VARIABLE", "my variable", "id"]
    if not field_data:
        return ""
    return field_data[0]

def generate_block_code(block_id, blocks, indent_level=0):
    if not block_id or block_id not in blocks:
        return ""
    
    block = blocks[block_id]
    opcode = block['opcode']
    inputs = block['inputs']
    fields = block['fields']
    
    indent = "    " * indent_level
    
    # Handle special cases or generic mapping
    format_str = OPCODE_MAP.get(opcode, f"UNKNOWN_BLOCK_{opcode}")
    
    # Prepare arguments for format string
    args = {}
    
    # Process inputs
    for input_name, input_val in inputs.items():
        args[input_name] = parse_input(input_val, blocks)
        
    # Process fields
    for field_name, field_val in fields.items():
        args[field_name] = parse_field(field_val)
        
    # Special handling for procedures_definition
    if opcode == "procedures_definition":
        custom_block_id = inputs.get('custom_block', [None, None])[1]
        if custom_block_id and custom_block_id in blocks:
            proto = blocks[custom_block_id]
            mutation = proto.get('mutation', {})
            proccode = mutation.get('proccode', '')
            argumentnames = json.loads(mutation.get('argumentnames', '[]'))
            
            parts = proccode.replace('%b', '%s').split('%s')
            def_str = "define "
            for i, part in enumerate(parts):
                def_str += part
                if i < len(argumentnames):
                    def_str += f"({argumentnames[i]})"
            
            return f"{indent}{def_str}\n"
        return f"{indent}define unknown\n"

    # Special handling for procedures_call
    if opcode == "procedures_call":
        mutation = block.get('mutation', {})
        proccode = mutation.get('proccode', '')
        argumentids = json.loads(mutation.get('argumentids', '[]'))
        
        parts = proccode.replace('%b', '%s').split('%s')
        result_str = ""
        for i, part in enumerate(parts):
            result_str += part
            if i < len(argumentids):
                arg_id = argumentids[i]
                if arg_id in inputs:
                    val = parse_input(inputs[arg_id], blocks)
                    result_str += val
                else:
                    result_str += "[]"
        
        return f"{indent}{result_str}\n"

    # Construct the code line
    try:
        # Check for missing args and fill with empty string
        required_keys = [fname for _, fname, _, _ in string.Formatter().parse(format_str) if fname]
        for key in required_keys:
            if key not in args:
                # Special handling for boolean inputs (OPERAND) to show empty boolean slot <>
                if "OPERAND" in key or "CONDITION" in key:
                     args[key] = "<>"
                else:
                     args[key] = "" # Default to empty string for missing inputs
                
        code = format_str.format(**args)
    except KeyError as e:
        code = f"{format_str} (Missing arg: {e})"
    except Exception as e:
        code = f"Error parsing {opcode}: {e}"

    result = f"{indent}{code}\n"
    
    # Handle C-blocks
    c_blocks = ["control_forever", "control_repeat", "control_repeat_until", "control_if", "control_if_else"]
    
    if opcode in c_blocks:
        # First substack
        # Check for both lowercase and uppercase SUBSTACK
        substack_input = inputs.get("substack") or inputs.get("SUBSTACK")
        if substack_input:
            substack_id = substack_input[1]
            if substack_id:
                curr_sub = substack_id
                while curr_sub:
                    result += generate_block_code(curr_sub, blocks, indent_level + 1)
                    curr_sub = blocks[curr_sub]['next']
        
        # Else part
        if opcode == "control_if_else":
            result += f"{indent}else\n"
            substack2_input = inputs.get("substack2") or inputs.get("SUBSTACK2")
            if substack2_input:
                substack2_id = substack2_input[1]
                if substack2_id:
                    curr_sub2 = substack2_id
                    while curr_sub2:
                        result += generate_block_code(curr_sub2, blocks, indent_level + 1)
                        curr_sub2 = blocks[curr_sub2]['next']
        
        result += f"{indent}end\n"

    return result

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    try:
        with zipfile.ZipFile(INPUT_FILE, 'r') as z:
            if "sprite.json" not in z.namelist():
                print("Error: sprite.json not found in the archive.")
                return
            
            with z.open("sprite.json") as f:
                data = json.load(f)
                
        blocks = data.get('blocks', {})
        
        # Find top-level blocks (hat blocks or disconnected stacks)
        top_level_blocks = []
        for bid, b in blocks.items():
            if b.get('topLevel', False):
                top_level_blocks.append(bid)
                
        # Sort by Y then X to approximate visual order
        top_level_blocks.sort(key=lambda bid: (blocks[bid].get('y', 0), blocks[bid].get('x', 0)))
        
        output_lines = []
        
        for start_id in top_level_blocks:
            curr_id = start_id
            while curr_id:
                output_lines.append(generate_block_code(curr_id, blocks))
                curr_id = blocks[curr_id]['next']
            output_lines.append("\n") # Separator between scripts
            
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.writelines(output_lines)
            
        print(f"Successfully converted to {OUTPUT_FILE}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

