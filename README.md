<p align="center">
  <img src="textscratch/assets/logo.svg" alt="TextScratch Logo" width="200"/>
</p>

<h1 align="center">TextScratch</h1>

<p align="center">
  <strong>Convert Scratch projects to text-based code and back again</strong>
</p>

<p align="center">
  Write Scratch projects using the <a href="https://en.scratch-wiki.info/wiki/Block_Plugin/Syntax">scratchblocks syntax</a> in your favorite text editor, then compile them into working .sb3 files!
</p>

---

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Scratchblocks Syntax](#scratchblocks-syntax)
- [Using convert.py (CLI)](#using-convertpy-cli)
- [Using manager.py](#using-managerpy)
  - [CLI Usage](#cli-usage)
  - [Python Module Usage](#python-module-usage)
- [Complete Block Reference](#complete-block-reference)

---

## Introduction

**TextScratch** is a Python toolkit that bridges the gap between text-based programming and Scratch's visual block-based environment. It allows you to:

- ✏️ **Write Scratch code in text** using the familiar scratchblocks syntax
- 📦 **Convert .sb3 files to text** for version control and text editing
- 🔧 **Pack text projects back to .sb3** for use in Scratch
- ⚙️ **Manage sprites, variables, and assets** programmatically

This is perfect for:
- Developers who prefer text editors over visual block manipulation
- Version controlling Scratch projects with Git
- Batch editing multiple Scratch projects
- Teaching programming concepts with readable code

---

## Installation

### Requirements

TextScratch requires **Python 3.8+** and the following packages:

```bash
pip install Pillow
```

That's it! No other dependencies needed.

### Clone the Repository

```bash
git clone https://github.com/your-username/TextScratch.git
cd TextScratch
```

---

## Quick Start

> **Note:** On macOS or Linux, you may need to use `python3` instead of `python` for all commands.

### 1. Create a New Project

```bash
python manager.py project create MyProject
```

This creates a project folder with the following structure:

```
MyProject/
├── events.json          # Broadcast messages
├── variables.json       # Global variables and lists
├── Stage/
│   ├── code.scratchblocks
│   ├── Assets/          # Backdrops
│   └── Sounds/
└── Sprites/
    └── Sprite1/
        ├── code.scratchblocks
        ├── miscdata.json
        ├── variables.json
        ├── Assets/      # Costumes
        └── Sounds/
```

### 2. Write Your Code

Edit `MyProject/Sprites/Sprite1/code.scratchblocks`:

```
when green flag clicked
say [Hello, World!] for [2] seconds
repeat [10]
  move [10] steps
  turn right [15] degrees
end
```

### 3. Build to .sb3

```bash
python convert.py MyProject --to-sb3 --sb3-output hello_world.sb3
```

### 4. Open in Scratch

Open `hello_world.sb3` in [Scratch](https://scratch.mit.edu/) and run your project!

---

## Scratchblocks Syntax

TextScratch uses the standard **scratchblocks** syntax. Here's a quick overview:

### Basic Rules

| Element | Syntax | Example |
|---------|--------|---------|
| Number input | `[value]` | `move [10] steps` |
| String input | `[text]` | `say [Hello!]` |
| Dropdown menu | `[option v]` | `go to [random position v]` |
| Boolean slot | `<>` | `if <> then` |
| Reporter block | `()` | `say (x position)` |
| Color input | `(#hexcode)` | `set pen color to (#ff0000)` |
| Block end | `end` | Closes C-blocks |

### Variables and Lists

```
set [my variable v] to [0]
change [my variable v] by [1]
say (my variable)

add [item] to [my list v]
say (item [1] of [my list v])
```

### Custom Blocks (Procedures)

```
define jump (height)
change y by {height}

jump [50]
```

> ⚠️ **TextScratch Syntax Modifications**
>
> We made slight modifications to the standard scratchblocks syntax to support all Scratch features:
>
> **1. Run Without Screen Refresh**
>
> Add `#norefresh` to the end of a `define` line to enable "run without screen refresh":
> ```
> define my fast block #norefresh
> ```
>
> **2. Argument References Use Curly Brackets**
>
> When using arguments *inside* a custom block, use curly brackets `{}` instead of parentheses `()`:
> ```
> define greet (name)
> say (join [Hello, ] {name})
> ```
>
> This differs from standard scratchblocks syntax, but was necessary to avoid conflicts when variables share the same name as arguments (which happens frequently). Note that the `define` line itself still uses parentheses for declaring parameters.

### Comments

```
// This is a comment
say [Hello!] // Inline comment
```

---

## Using convert.py (CLI)

The `convert.py` script handles conversion between `.sb3` archives and TextScratch project folders.

### Extract .sb3 to Project Folder

```bash
python convert.py project.sb3
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir DIR` | Output directory for extracted files | `Project` |
| `--no-clean` | Don't remove output directory before extracting | (cleans by default) |

**Examples:**

```bash
# Extract to default "Project" folder
python convert.py my_game.sb3

# Extract to custom folder
python convert.py my_game.sb3 --output-dir MyGame

# Extract without cleaning existing folder
python convert.py my_game.sb3 --output-dir MyGame --no-clean
```

### Pack Project Folder to .sb3

```bash
python convert.py ProjectFolder --to-sb3
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--to-sb3` | Pack folder to .sb3 instead of extracting | (required for packing) |
| `--sb3-output FILE` | Output .sb3 file path | `output.sb3` |

**Examples:**

```bash
# Pack to default "output.sb3"
python convert.py MyProject --to-sb3

# Pack to custom filename
python convert.py MyProject --to-sb3 --sb3-output my_game.sb3
```

---

## Using manager.py

The `manager.py` script provides comprehensive project management capabilities both as a CLI tool and as a Python module.

### CLI Usage

```bash
python manager.py [--project PATH] <command> <subcommand> [options]
```

**Global Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--project, -p` | Project path | `Project` |
| `--verbose, -v` | Show detailed error messages | (off) |

---

#### Project Commands

##### Create a Project

```bash
python manager.py project create <path> [--replace] [--yes]
```

| Option | Description |
|--------|-------------|
| `--replace` | Overwrite existing project |
| `--yes, -y` | Skip confirmation prompts |

```bash
python manager.py project create MyGame
python manager.py project create MyGame --replace --yes
```

##### Delete a Project

```bash
python manager.py project delete <path> [--yes]
```

```bash
python manager.py project delete MyGame --yes
```

---

#### Sprite Commands

##### Create a Sprite

```bash
python manager.py sprite create [--name NAME]
```

```bash
python manager.py sprite create                    # Creates "Sprite2", "Sprite3", etc.
python manager.py sprite create --name Player      # Creates "Player"
python manager.py -p MyGame sprite create --name Enemy
```

##### List Sprites

```bash
python manager.py sprite list
```

Output:
```
Name                 Position        Size     Visible  Layer
------------------------------------------------------------
Sprite1              (0, 0)          100      Yes      1
Player               (100, -50)      75       Yes      2
```

##### Rename a Sprite

```bash
python manager.py sprite rename <old_name> <new_name>
```

```bash
python manager.py sprite rename Sprite1 MainCharacter
```

##### Delete a Sprite

```bash
python manager.py sprite delete <name> [--yes]
```

```bash
python manager.py sprite delete Enemy --yes
```

##### Duplicate a Sprite

```bash
python manager.py sprite duplicate <source> [--dest NAME]
```

```bash
python manager.py sprite duplicate Player              # Creates "Player2"
python manager.py sprite duplicate Player --dest Boss  # Creates "Boss"
```

##### Edit Sprite Properties

```bash
python manager.py sprite edit <name> [options]
```

| Option | Description |
|--------|-------------|
| `--x FLOAT` | X position |
| `--y FLOAT` | Y position |
| `--size FLOAT` | Size percentage |
| `--direction FLOAT` | Direction in degrees |
| `--visible BOOL` | Visibility (true/false) |
| `--layer INT` | Layer order |
| `--costume INT` | Current costume index |
| `--rotation-style` | `all around`, `left-right`, or `don't rotate` |
| `--draggable BOOL` | Draggable flag (true/false) |

```bash
python manager.py sprite edit Player --x 100 --y -50 --size 75
python manager.py sprite edit Player --visible false --layer 5
python manager.py sprite edit Player --rotation-style "left-right"
```

---

#### Variable Commands

##### List Variables

```bash
python manager.py var list [--list] [--var]
```

| Option | Description |
|--------|-------------|
| `--list, -l` | Show only lists |
| `--var` | Show only variables |

```bash
python manager.py var list
python manager.py var list --var     # Variables only
python manager.py var list --list    # Lists only
```

##### Show Variable/List Value

```bash
python manager.py var show <name> [--sprite NAME] [--list] [--limit INT]
```

```bash
python manager.py var show score
python manager.py var show inventory --list
python manager.py var show health --sprite Player
```

##### Create Variable

```bash
python manager.py var create <name> [options]
```

| Option | Description |
|--------|-------------|
| `--sprite, -s` | Sprite name for local scope |
| `--list, -l` | Create a list instead |
| `--value, -v` | Initial value |
| `--cloud, -c` | Make it a cloud variable |
| `--monitor-mode` | `default`, `slider`, or `large` |
| `--monitor-visible` | Make monitor visible |

```bash
python manager.py var create score
python manager.py var create health --value 100 --monitor-visible
python manager.py var create "high score" --cloud
python manager.py var create inventory --list --value '["sword", "shield"]'
python manager.py var create localVar --sprite Player
```

##### Bulk Create Variables

```bash
python manager.py var bulk-create <name1> <name2> ... [--sprite NAME] [--list]
```

```bash
python manager.py var bulk-create x y z speed health
python manager.py var bulk-create enemies items --list
```

##### Edit Variable

```bash
python manager.py var edit <name> [options]
```

| Option | Description |
|--------|-------------|
| `--sprite, -s` | Current sprite scope |
| `--list, -l` | Target is a list |
| `--rename` | New name |
| `--value, -v` | New value |
| `--scope` | New scope (`global` or sprite name) |
| `--cloud` | Cloud variable flag |
| `--monitor-x` | Monitor X position |
| `--monitor-y` | Monitor Y position |

```bash
python manager.py var edit score --value 0
python manager.py var edit oldName --rename newName
python manager.py var edit localVar --sprite Player --scope global
```

---

#### Asset Commands

##### Create Asset

```bash
python manager.py asset create <source> <sprite> <name> --type <costume|sound>
```

```bash
python manager.py asset create player.png Player costume1 --type costume
python manager.py asset create jump.wav Player jump_sound --type sound
python manager.py asset create background.svg Stage backdrop2 --type costume
```

##### List Assets

```bash
python manager.py asset list <sprite> [--type <costume|sound>]
```

```bash
python manager.py asset list Player
python manager.py asset list Player --type costume
python manager.py asset list Stage --type sound
```

##### Delete Asset

```bash
python manager.py asset delete <sprite> <name> --type <costume|sound> [--yes]
```

```bash
python manager.py asset delete Player old_costume --type costume --yes
```

##### Duplicate Asset

```bash
python manager.py asset duplicate <src_sprite> <src_name> <dst_sprite> <dst_name> --type <costume|sound>
```

```bash
python manager.py asset duplicate Player costume1 Enemy costume1 --type costume
```

---

### Python Module Usage

You can also use `manager.py` as a Python module for programmatic project management.

```python
from manager import Manager, ManagerError
```

#### Project Management

```python
# Create a new project
Manager.create_project("MyProject")
Manager.create_project("MyProject", replace=True)  # Overwrite existing

# Delete a project
Manager.delete_project("MyProject")
```

#### Sprite Management

```python
mgr = Manager("MyProject")

# Create sprites
mgr.create_sprite()                    # Auto-named: Sprite1, Sprite2, etc.
mgr.create_sprite(name="Player")       # Named sprite

# List sprites
sprites = mgr.list_sprites()
for sprite in sprites:
    print(f"{sprite['name']}: pos=({sprite['x']}, {sprite['y']})")

# Get sprite details
player = mgr.get_sprite("Player")
print(player['size'], player['direction'])

# Edit sprite properties
mgr.edit_sprite("Player", x=100, y=-50, size=75, visible=True)
mgr.edit_sprite("Player", rotation_style="left-right", draggable=True)

# Rename and duplicate
mgr.rename_sprite("Sprite1", "MainCharacter")
mgr.duplicate_sprite("Player", dest="PlayerCopy")

# Delete sprite
mgr.delete_sprite("Enemy")
```

#### Variable and List Management

```python
mgr = Manager("MyProject")

# Create variables
mgr.create_variable("score", value=0)
mgr.create_variable("health", value=100, monitor_visible=True)
mgr.create_variable("high_score", cloud=True)
mgr.create_variable("localVar", sprite="Player")  # Local to sprite

# Create lists
mgr.create_list("inventory")
mgr.create_list("enemies", value=["goblin", "skeleton"])

# Bulk create
mgr.bulk_create_variables(["x", "y", "z", "speed"])
mgr.bulk_create_variables(["items", "scores"], is_list=True)

# List all variables
variables = mgr.list_variables()
variables = mgr.list_variables(var_only=True)   # Variables only
variables = mgr.list_variables(list_only=True)  # Lists only

# Get variable value
var = mgr.get_variable("score")
print(var['value'])

lst = mgr.get_variable("inventory", is_list=True)
print(lst['value'])

# Edit variables
mgr.edit_variable("score", value=100)
mgr.edit_variable("oldName", rename="newName")
mgr.edit_variable("localVar", sprite="Player", scope="global")

# Delete
mgr.delete_variable("unused")
mgr.delete_variable("old_list", is_list=True)
```

#### Asset Management

```python
mgr = Manager("MyProject")

# Add assets
mgr.create_asset("player.png", "Player", "costume1", "costume")
mgr.create_asset("jump.wav", "Player", "jump_sound", "sound")
mgr.create_asset("bg.svg", "Stage", "backdrop1", "costume")

# List assets
costumes = mgr.list_assets("Player", asset_type="costume")
sounds = mgr.list_assets("Player", asset_type="sound")
all_assets = mgr.list_assets("Player")

# Duplicate assets
mgr.duplicate_asset("Player", "costume1", "Enemy", "costume1", "costume")

# Delete assets
mgr.delete_asset("Player", "old_costume", "costume")
```

#### Error Handling

```python
from manager import Manager, ManagerError

mgr = Manager("MyProject")

try:
    mgr.create_sprite(name="Player")
except ManagerError as e:
    print(f"Error: {e.message}")
    print(f"Detail: {e.detail}")
```

---

## Complete Block Reference

Below is a comprehensive list of all Scratch blocks organized by category.

### Motion Blocks

```
move [10] steps
turn right [15] degrees
turn left [15] degrees
go to [random position v]
go to [mouse-pointer v]
go to x: [0] y: [0]
glide [1] secs to [random position v]
glide [1] secs to [mouse-pointer v]
glide [1] secs to x: [0] y: [0]
point in direction [90]
point towards [mouse-pointer v]
point towards [Sprite v]
change x by [10]
set x to [0]
change y by [10]
set y to [0]
if on edge, bounce
set rotation style [left-right v]
set rotation style [don't rotate v]
set rotation style [all around v]
```

**Reporters:**
```
(x position)
(y position)
(direction)
```

---

### Looks Blocks

```
say [Hello!] for [2] seconds
say [Hello!]
think [Hmm...] for [2] seconds
think [Hmm...]
switch costume to [costume1 v]
next costume
switch backdrop to [backdrop1 v]
next backdrop
change size by [10]
set size to [100] %
change [COLOR v] effect by [25]
set [COLOR v] effect to [0]
clear graphic effects
show
hide
go to [front v] layer
go to [back v] layer
go [forward v] [1] layers
go [backward v] [1] layers
```

**Reporters:**
```
(costume [number v])
(costume [name v])
(backdrop [number v])
(backdrop [name v])
(size)
```

---

### Sound Blocks

```
play sound [Sound v] until done
start sound [Sound v]
stop all sounds
change [PITCH v] effect by [10]
set [PITCH v] effect to [100]
clear sound effects
change volume by [-10]
set volume to [100] %
```

**Reporters:**
```
(volume)
```

---

### Events Blocks

```
when green flag clicked
when [space v] key pressed
when this sprite clicked
when backdrop switches to [backdrop1 v]
when [LOUDNESS v] > [10]
when I receive [message1 v]
broadcast [message1 v]
broadcast [message1 v] and wait
```

---

### Control Blocks

```
wait [1] seconds

repeat [10]
  // blocks here
end

forever
  // blocks here
end

if <> then
  // blocks here
end

if <> then
  // blocks here
else
  // blocks here
end

wait until <>

repeat until <>
  // blocks here
end

stop [all v]
stop [this script v]
stop [other scripts in sprite v]

when I start as a clone
create clone of [_myself_ v]
delete this clone
```

---

### Sensing Blocks

```
ask [What's your name?] and wait
set drag mode [draggable v]
reset timer
```

**Reporters:**
```
(answer)
(mouse x)
(mouse y)
(loudness)
(timer)
(current [YEAR v])
(username)
(distance to [mouse-pointer v])
(distance to [Sprite v])
([backdrop # v] of [_stage_ v])
([x position v] of [Sprite v])
([Local variable v] of [Sprite v])
```

**Booleans:**
```
<touching [mouse-pointer v] ?>
<touching color (#bbe899) ?>
<color (#132fca) is touching (#7d8b32) ?>
<key [space v] pressed?>
<mouse down?>
```

---

### Operators Blocks

**Reporters:**
```
([] + [])
([] - [])
([] * [])
([] / [])
(pick random [1] to [10])
(join [apple ] [banana])
(letter [1] of [apple])
(length of [apple])
([] mod [])
(round [])
([abs v] of [])
```

**Booleans:**
```
<[] > [50]>
<[] < [50]>
<[] = [50]>
<<> and <>>
<<> or <>>
<not <>>
<[apple] contains [a] ?>
```

---

### Variables Blocks

```
set [my variable v] to [0]
change [my variable v] by [1]
show variable [my variable v]
hide variable [my variable v]
```

**Reporters:**
```
(my variable)
```

---

### List Blocks

```
add [thing] to [my list v]
delete [1] of [my list v]
delete all of [my list v]
insert [thing] at [1] of [my list v]
replace item [1] of [my list v] with [thing]
show list [my list v]
hide list [my list v]
```

**Reporters:**
```
(item [1] of [my list v])
(item # of [thing] in [my list v])
(length of [my list v])
```

**Booleans:**
```
<[my list v] contains [thing] ?>
```

---

### Pen Extension Blocks

```
erase all
stamp
pen down
pen up
set pen color to (#26ccbc)
change pen (color v) by [10]
set pen (color v) to [50]
change pen size by [1]
set pen size to [1]
```

---

### Custom Blocks (My Blocks)

```
define my block (parameter1) (parameter2) <boolean param>
my block [value1] [value2] <condition>
```

**Using arguments inside the block:**
```
define greet (name) (times)
repeat {times}
  say (join [Hello, ] {name})
end
```

**Run without screen refresh:**
```
define fast calculation (n) #norefresh
```

---

## How to Contribute

Only pull requests that fix actual issues will be accepted. Before submitting a pull request, please fill out the form in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

---

## License

This project is open source. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ❤️ for the Scratch community
</p>
