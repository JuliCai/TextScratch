"""Keep comment anchors across block ID regeneration without caching code."""
import json


def block_paths(blocks, sort_roots=False):
    roots = [bid for bid, block in blocks.items() if
             (isinstance(block, dict) and block.get("topLevel")) or
             (isinstance(block, list) and len(block) >= 5)]
    if sort_roots:
        roots.sort(key=lambda bid: (blocks[bid][4], blocks[bid][3]) if isinstance(blocks[bid], list)
                   else (blocks[bid].get("y", 0), blocks[bid].get("x", 0)))
    pending = [(bid, [str(i)]) for i, bid in enumerate(roots)]
    seen = set()
    while pending:
        bid, path = pending.pop()
        if bid in seen or not isinstance(blocks.get(bid), dict):
            continue
        seen.add(bid)
        block = blocks[bid]
        yield bid, path
        if block.get("next"):
            pending.append((block["next"], path + ["next"]))
        mutation = block.get("mutation", {})
        arguments = json.loads(mutation.get("argumentids", "[]"))
        for name, value in block.get("inputs", {}).items():
            key = "arg:" + str(arguments.index(name)) if name in arguments else name
            if len(value) > 1 and isinstance(value[1], str):
                pending.append((value[1], path + [key]))


def comment_anchors(target):
    paths = dict(block_paths(target.get("blocks", {}), sort_roots=True))
    return {cid: {"path": paths[c["blockId"]],
                  "opcode": target["blocks"][c["blockId"]]["opcode"]}
            for cid, c in target.get("comments", {}).items() if c.get("blockId") in paths}


def restore_comments(misc, blocks):
    paths = {tuple(path): bid for bid, path in block_paths(blocks)}
    comments = {cid: dict(c, blockId=None) for cid, c in misc.get("comments", {}).items()}
    for cid, anchor in misc.get("commentAnchors", {}).items():
        bid = paths.get(tuple(anchor["path"]))
        if cid in comments and bid and blocks[bid]["opcode"] == anchor["opcode"]:
            comments[cid]["blockId"] = bid
            blocks[bid]["comment"] = cid
    return comments
