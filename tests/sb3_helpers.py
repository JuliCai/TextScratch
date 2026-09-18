"""ID-independent executable graph comparison for round-trip tests."""
import json


def scripts(target, stage=None):
    blocks = target["blocks"]
    stage = stage or target
    variables = {k: ("global", v[0]) for k, v in stage.get("variables", {}).items()}
    lists = {k: ("global", v[0]) for k, v in stage.get("lists", {}).items()}
    if not target.get("isStage"):
        variables.update({k: ("local", v[0]) for k, v in target.get("variables", {}).items()})
        lists.update({k: ("local", v[0]) for k, v in target.get("lists", {}).items()})

    def value(ref):
        if isinstance(ref, list):
            if ref[0] == 12:
                return ["variable", variables.get(ref[2], ("missing", ref[1]))]
            if ref[0] == 13:
                return ["list", lists.get(ref[2], ("missing", ref[1]))]
            if ref[0] == 11:
                return ["broadcast", ref[1]]
            return ["literal", str(ref[1])]
        if not ref:
            return None
        b = blocks[ref]
        if isinstance(b, list):
            return value(b)
        op = b["opcode"]
        if op == "data_variable":
            return value([12] + b["fields"]["VARIABLE"])
        if op == "data_listcontents":
            return value([13] + b["fields"]["LIST"])
        fields = {}
        for k, v in b.get("fields", {}).items():
            fields[k] = variables.get(v[1], ("missing", v[0])) if k == "VARIABLE" else lists.get(v[1], ("missing", v[0])) if k == "LIST" else v[0]
        mutation = b.get("mutation", {})
        inputs = b.get("inputs", {})
        if op == "procedures_call":
            inputs = {str(i): inputs.get(k, [2, None]) for i, k in enumerate(json.loads(mutation.get("argumentids", "[]")))}
        elif op == "procedures_prototype":
            inputs = {}
        return {"opcode": op, "fields": fields,
                "inputs": {k: value(v[1]) for k, v in inputs.items() if len(v) > 1 and v[1] is not None},
                "procedure": {k: json.loads(mutation[k]) if k == "argumentnames" else mutation[k] for k in ("proccode", "warp", "argumentnames") if k in mutation and (k != "argumentnames" or op == "procedures_prototype")},
                "next": value(b.get("next"))}

    return sorted((value(k) for k, b in blocks.items() if
                   (isinstance(b, dict) and b.get("topLevel")) or (isinstance(b, list) and len(b) > 3)),
                  key=lambda v: json.dumps(v, sort_keys=True))
