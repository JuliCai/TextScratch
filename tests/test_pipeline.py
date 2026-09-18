import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from textscratch.blocks_to_text import generate_target_code
from textscratch.diagnostics import DiagnosticContext
from textscratch.project_io import convert_folder_to_sb3, convert_project
from textscratch.text_to_blocks import code_to_blocks
from .sb3_helpers import scripts


class CompilerTests(unittest.TestCase):
    def compile(self, text, variables=None, lists=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "code.scratchblocks"
            path.write_text(text, encoding="utf-8")
            context = DiagnosticContext("Sprite")
            blocks = code_to_blocks(str(path), variables or {}, {}, lists or {}, {}, {}, context)
            self.assertFalse(context.has_errors(), str(context.diagnostics))
            self.check_links(blocks)
            return blocks

    def check_links(self, blocks):
        incoming = {}
        for bid, block in blocks.items():
            refs = [block.get("next")]
            for inp in block["inputs"].values():
                self.assertIn(inp[0], (1, 2, 3))
                self.assertEqual(len(inp), 3 if inp[0] == 3 else 2)
                refs.extend(v for v in inp[1:] if isinstance(v, str))
            for ref in refs:
                if ref:
                    self.assertIn(ref, blocks)
                    self.assertEqual(blocks[ref]["parent"], bid)
                    self.assertNotIn(ref, incoming)
                    incoming[ref] = bid
        for bid, block in blocks.items():
            self.assertEqual(block["topLevel"], bid not in incoming)

    def one(self, blocks, opcode):
        return next(b for b in blocks.values() if b["opcode"] == opcode)

    def test_literal_collisions_and_numeric_spelling(self):
        values = ["score", "001", " 42 ", "1e3", "900719925474099312345", "Infinity", "NaN", "(x position)"]
        for value in values:
            with self.subTest(value=value):
                block = self.one(self.compile(f"say [{value}]", {"score": "v"}), "looks_say")
                self.assertEqual(block["inputs"]["MESSAGE"], [1, [10, value]])
                json.dumps(block, allow_nan=False)

    def test_numeric_input_keeps_literal_spelling(self):
        b = self.one(self.compile("move [0001] steps"), "motion_movesteps")
        self.assertEqual(b["inputs"]["STEPS"], [1, [4, "0001"]])

    def test_nested_separators_do_not_split_outer_inputs(self):
        b = self.compile("say (join [ for ] (join [seconds] [hi])) for (pick random [1] to [3]) seconds")
        say = self.one(b, "looks_sayforsecs")
        self.assertEqual(b[say["inputs"]["MESSAGE"][1]]["opcode"], "operator_join")
        self.assertEqual(b[say["inputs"]["SECS"][1]]["opcode"], "operator_random")

    def test_nested_less_than_boolean(self):
        b = self.compile("if <<[1] < [2]> and <[3] > [2]>> then\n  say [yes]\nend")
        self.assertEqual(self.one(b, "operator_and")["inputs"]["OPERAND1"][0], 2)
        self.one(b, "operator_lt")
        self.one(b, "operator_gt")

    def test_two_space_unindented_and_blank_control_bodies(self):
        for indent in ("", "  ", "    ", "\t"):
            b = self.compile(f"when green flag clicked\nrepeat [2]\n\n{indent}if <> then\n{indent}say [yes]\nelse\n{indent}say [no]\nend\nend\nsay [after]")
            repeat = self.one(b, "control_repeat")
            branch = b[repeat["inputs"]["SUBSTACK"][1]]
            self.assertEqual(branch["opcode"], "control_if_else")
            self.assertEqual(b[repeat["next"]]["inputs"]["MESSAGE"][1][1], "after")

    def test_comments_and_adjacent_hats(self):
        b = self.compile("// note\nwhen green flag clicked\nsay [https://example.test] // note\nwhen [space v] key pressed\nsay [other]")
        self.assertEqual(sum(x["topLevel"] for x in b.values()), 2)
        self.assertEqual(self.one(b, "looks_say")["inputs"]["MESSAGE"][1][1], "https://example.test")

    def test_boolean_procedure_forward_call(self):
        b = self.compile("check <[1] < [2]> [okay]\n\ndefine check <enabled> (text) #norefresh\nif {<enabled>} then\nsay {text}\nend")
        proto = self.one(b, "procedures_prototype")
        self.assertEqual(proto["mutation"]["proccode"], "check %b %s")
        self.assertEqual(json.loads(proto["mutation"]["argumentdefaults"]), [False, ""])
        arg = next(iter(proto["inputs"].values()))[1]
        self.assertEqual(b[arg]["opcode"], "argument_reporter_boolean")
        call = self.one(b, "procedures_call")
        self.assertEqual(call["mutation"]["argumentids"], proto["mutation"]["argumentids"])
        self.assertEqual(next(iter(call["inputs"].values()))[0], 2)

    def test_escaped_procedure_labels_and_argument_names(self):
        text = r"define process \(raw\)\: (arg\)name) <flag\>name> #norefresh" + "\nsay {arg\\)name}\n\n" + r"process \(raw\)\: [hello] <mouse down?>"
        b = self.compile(text)
        proto = self.one(b, "procedures_prototype")
        self.assertEqual(proto["mutation"]["proccode"], "process (raw): %s %b")
        self.assertEqual(json.loads(proto["mutation"]["argumentnames"]), ["arg)name", "flag>name"])
        rebuilt = self.compile(generate_target_code({"blocks": b}))
        self.assertEqual(scripts({"blocks": b}), scripts({"blocks": rebuilt}))

    def test_inline_comments_on_definition_and_terminators(self):
        b = self.compile("define greet (name) #norefresh // note\nif <> then\nsay {name}\nelse // note\nsay [no]\nend // done\n\ngreet [hi]")
        self.assertEqual(self.one(b, "procedures_prototype")["mutation"]["proccode"], "greet %s")
        self.one(b, "control_if_else")

    def test_unclosed_control_reports_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "code.scratchblocks"
            path.write_text("repeat [3]\nsay [hello]")
            context = DiagnosticContext("Sprite")
            code_to_blocks(str(path), {}, {}, {}, {}, {}, context)
        self.assertTrue(context.has_errors())
        self.assertIn("Missing end", context.get_errors()[0].message)

    def test_procedure_literals_are_required(self):
        b = self.compile("define put (first) beside (second)\n\nput [beside] beside (join [x] [y])")
        call = self.one(b, "procedures_call")
        inputs = list(call["inputs"].values())
        self.assertEqual(inputs[0], [1, [10, "beside"]])
        self.assertEqual(b[inputs[1][1]]["opcode"], "operator_join")

    def test_dynamic_menus(self):
        for code, opcode, name in [
            ("create clone of (choice)", "control_create_clone_of", "CLONE_OPTION"),
            ("say (distance to (choice))", "sensing_distanceto", "DISTANCETOMENU"),
            ("if <touching (choice) ?> then\nend", "sensing_touchingobject", "TOUCHINGOBJECTMENU"),
            ("say ([x position v] of (choice))", "sensing_of", "OBJECT"),
            ("if <key (choice) pressed?> then\nend", "sensing_keypressed", "KEY_OPTION"),
            ("switch costume to (choice)", "looks_switchcostumeto", "COSTUME"),
            ("go to (choice)", "motion_goto", "TO"),
            ("glide [1] secs to (choice)", "motion_glideto", "TO"),
            ("set pen (choice) to [50]", "pen_setPenColorParamTo", "COLOR_PARAM"),
        ]:
            with self.subTest(code=code):
                b = self.compile(code, {"choice": "v"})
                inp = self.one(b, opcode)["inputs"][name]
                self.assertEqual(inp[:2], [3, [12, "choice", "v"]])
                self.assertTrue(b[inp[2]]["shadow"])

    def test_boolean_reporter_in_text_slot_has_shadow(self):
        b = self.compile("say <mouse down?>")
        self.assertEqual(self.one(b, "looks_say")["inputs"]["MESSAGE"][0], 3)

    def test_stop_mutation_and_pen_opcodes(self):
        b = self.compile("stop [other scripts in sprite v]\nchange pen size by [1]\nchange pen (color v) by [10]")
        self.assertEqual(self.one(b, "control_stop")["mutation"]["hasnext"], "true")
        self.one(b, "pen_changePenSizeBy")
        self.one(b, "pen_changePenColorParamBy")

    def test_escaped_literal_round_trip(self):
        value = "a ] [ ( < > } \\n\n\t emoji: 🐈"
        target = {"blocks": {"say": {"opcode": "looks_say", "inputs": {"MESSAGE": [1, [10, value]]}, "fields": {}, "topLevel": True, "next": None}}}
        b = self.compile(generate_target_code(target))
        self.assertEqual(self.one(b, "looks_say")["inputs"]["MESSAGE"][1][1], value)

    def test_loose_variable_and_list_reporters_survive(self):
        target = {"variables": {"v": ["score", 0]}, "lists": {"l": ["items", []]},
                  "blocks": {"v-block": [12, "score", "v", 0, 0], "l-block": [13, "items", "l", 0, 80]}}
        b = self.compile(generate_target_code(target), {"score": "v"}, {"items": "l"})
        self.one(b, "data_variable")
        self.one(b, "data_listcontents")
        self.assertEqual(sum(x["topLevel"] for x in b.values()), 2)

    def test_variable_names_colliding_with_reporters(self):
        for name in ("123", "answer", "x position", "a + b", "volume", "score :: variables"):
            target = {"variables": {"v": [name, 0]}, "blocks": {
                "say": {"opcode": "looks_say", "fields": {}, "inputs": {"MESSAGE": [3, [12, name, "v"], [10, ""]]}, "topLevel": True}}}
            b = self.compile(generate_target_code(target), {name: "v"})
            self.assertEqual(self.one(b, "looks_say")["inputs"]["MESSAGE"][1], [12, name, "v"])

    def test_global_local_and_list_name_collisions(self):
        code = "set [same :: global v] to (same :: variables global)\nadd (same :: list) to [same :: global v]"
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "code.scratchblocks"
            path.write_text(code)
            b = code_to_blocks(str(path), {"same": "lv"}, {"same": "gv"}, {"same": "ll"}, {"same": "gl"}, {})
        self.assertEqual(self.one(b, "data_setvariableto")["fields"]["VARIABLE"], ["same", "gv"])
        self.assertEqual(self.one(b, "data_setvariableto")["inputs"]["VALUE"][1], [12, "same", "gv"])
        self.assertEqual(self.one(b, "data_addtolist")["fields"]["LIST"], ["same", "gl"])
        self.assertEqual(self.one(b, "data_addtolist")["inputs"]["ITEM"][1], [13, "same", "ll"])

    def test_additional_control_substacks_round_trip(self):
        for head in ("while <mouse down?>", "for each [i v] in [10]", "all at once"):
            b = self.compile(head + "\nsay [inside]\nend", {"i": "v"})
            text = generate_target_code({"blocks": b})
            self.assertIn("say [inside]", text)
            self.assertEqual(scripts({"blocks": b}), scripts({"blocks": self.compile(text, {"i": "v"})}))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value, encoding="utf-8")

    def pack(self):
        output = self.root / "out.sb3"
        with contextlib.redirect_stdout(io.StringIO()):
            convert_folder_to_sb3(str(self.root), str(output))
        with zipfile.ZipFile(output) as z:
            return json.loads(z.read("project.json"))

    def test_sprite_discovered_broadcasts_are_on_stage(self):
        self.write("Sprites/A/code.scratchblocks", "when I receive [hello v]\nbroadcast [world v]")
        p = self.pack()
        self.assertEqual(set(p["targets"][0]["broadcasts"].values()), {"hello", "world"})

    def test_auto_created_variable_and_list_have_declarations(self):
        self.write("Sprites/A/code.scratchblocks", "set [score v] to [2]\nadd [x] to [items v]")
        sprite = self.pack()["targets"][1]
        self.assertEqual(list(sprite["variables"].values()), [["score", 0]])
        self.assertEqual(list(sprite["lists"].values()), [["items", []]])

    def test_invalid_code_does_not_overwrite_output(self):
        self.write("Stage/code.scratchblocks", "unsupported command")
        self.write("out.sb3", "keep me")
        with self.assertRaises(ValueError):
            self.pack()
        self.assertEqual((self.root / "out.sb3").read_text(), "keep me")

    def test_names_stage_settings_order_and_comments(self):
        self.write("Stage/code.scratchblocks", "when stage clicked\nswitch backdrop to [x v] and wait")
        self.write("Sprites/B/code.scratchblocks", "say [b]")
        self.write("Sprites/A/code.scratchblocks", "say [a]")
        p = self.pack()
        stage = p["targets"][0]
        stage.update(tempo=123, volume=37, videoState="off", videoTransparency=72, textToSpeechLanguage="de")
        p["targets"][1]["name"] = "a:b"
        p["targets"][2]["name"] = "a?b"
        p["targets"][1:] = p["targets"][1:][::-1]
        sprite = p["targets"][1]
        anchor = next(iter(sprite["blocks"]))
        sprite["comments"] = {"note": {"blockId": anchor, "text": "keep this", "x": 10, "y": 20, "width": 100, "height": 50, "minimized": False}}
        sprite["blocks"][anchor]["comment"] = "note"
        original = self.root / "original.sb3"
        with zipfile.ZipFile(original, "w") as z:
            z.writestr("project.json", json.dumps(p))
            for target in p["targets"]:
                for costume in target["costumes"]:
                    if costume["md5ext"] not in z.namelist():
                        z.write(Path(__file__).parents[1] / "textscratch/assets/blank.svg", costume["md5ext"])
        extracted = self.root / "extracted"
        with contextlib.redirect_stdout(io.StringIO()):
            convert_project(str(original), str(extracted))
            convert_folder_to_sb3(str(extracted), str(self.root / "roundtrip.sb3"))
        with zipfile.ZipFile(self.root / "roundtrip.sb3") as z:
            rebuilt = json.loads(z.read("project.json"))
        self.assertEqual([t["name"] for t in rebuilt["targets"]], [t["name"] for t in p["targets"]])
        for key in ("tempo", "volume", "videoState", "videoTransparency", "textToSpeechLanguage"):
            self.assertEqual(rebuilt["targets"][0][key], stage[key])
        for old, new in zip(p["targets"], rebuilt["targets"]):
            self.assertEqual(scripts(old, stage), scripts(new, rebuilt["targets"][0]))
        note = rebuilt["targets"][1]["comments"]["note"]
        self.assertEqual(note["text"], "keep this")
        self.assertEqual(rebuilt["targets"][1]["blocks"][note["blockId"]]["comment"], "note")

    def test_dynamic_broadcast_has_registered_menu_shadow(self):
        self.write("Sprites/A/code.scratchblocks", "broadcast (join [hello] [world])")
        p = self.pack()
        blocks = p["targets"][1]["blocks"]
        broadcast = next(b for b in blocks.values() if b["opcode"] == "event_broadcast")
        inp = broadcast["inputs"]["BROADCAST_INPUT"]
        self.assertEqual(inp[0], 3)
        self.assertEqual(blocks[inp[1]]["opcode"], "operator_join")
        self.assertIn(inp[2][2], p["targets"][0]["broadcasts"])

    def test_empty_targets_get_packaged_costume(self):
        p = self.pack()
        self.assertEqual(len(p["targets"][0]["costumes"]), 1)
        with zipfile.ZipFile(self.root / "out.sb3") as z:
            self.assertIn(p["targets"][0]["costumes"][0]["md5ext"], z.namelist())

    def test_manager_can_edit_imported_monitor_and_duplicate_ids(self):
        from manager import Manager
        self.write("variables.json", {"variables": [{"id": "gv", "name": "score", "value": 0, "monitor": None}], "lists": []})
        self.write("Stage/code.scratchblocks", "")
        self.write("Sprites/A/code.scratchblocks", "say (local)")
        self.write("Sprites/A/variables.json", {"variables": [{"id": "lv", "name": "local", "value": 1}], "lists": []})
        manager = Manager(str(self.root))
        manager.edit_variable("score", monitor_x=25)
        manager.duplicate_sprite("A", "B")
        p = self.pack()
        self.assertNotEqual(set(p["targets"][1]["variables"]), set(p["targets"][2]["variables"]))
        self.assertEqual(next(m for m in p["monitors"] if m["id"] == "gv")["x"], 25)


if __name__ == "__main__":
    unittest.main()
