"""Run: python -m tests.compare_projects original.sb3 rebuilt.sb3"""
import json
import sys
import zipfile
from .sb3_helpers import scripts


def first_difference(a, b, path=""):
    if type(a) is not type(b):
        return path, a, b
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return path + "/keys", list(a), list(b)
        for k in a:
            diff = first_difference(a[k], b[k], path + "/" + k)
            if diff:
                return diff
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return path + "/length", len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            diff = first_difference(x, y, path + "/" + str(i))
            if diff:
                return diff
    elif a != b:
        return path, a, b


if __name__ == "__main__":
    projects = [json.loads(zipfile.ZipFile(p).read("project.json")) for p in sys.argv[1:]]
    a, b = projects
    failures = 0
    if [t["name"] for t in a["targets"]] != [t["name"] for t in b["targets"]]:
        print("Target names/order differ")
        failures += 1
    for old in a["targets"]:
        new = next((t for t in b["targets"] if t["name"] == old["name"]), None)
        if new is None:
            print(old["name"], "MISSING")
            failures += 1
            continue
        x, y = scripts(old, a["targets"][0]), scripts(new, b["targets"][0])
        diff = first_difference(x, y)
        print(old["name"], "MATCH" if not diff else str(diff)[:1200])
        failures += bool(diff)
    sys.exit(1 if failures else 0)
