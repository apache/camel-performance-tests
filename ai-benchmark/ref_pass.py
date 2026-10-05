#!/usr/bin/env python3
"""Reference pass: runs every example of a set unchanged (the example's own files plus its seeds) through the same
scorer the model is scored with. An example the reference cannot pass is a harness bug or an example bug, to be fixed
before any model run. Usage: ref_pass.py [examples-ladder.json] [name ...]   Results: ref/<name>/, ref.log"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_local as A

REPO = os.path.expanduser(os.environ.get("BENCH_EXAMPLES_REPO", "~/workspace/camel-jbang-examples"))


def main():
    setfile = sys.argv[1] if len(sys.argv) > 1 else "examples-ladder.json"
    only = set(sys.argv[2:])
    examples = json.load(open(os.path.join(A.HERE, setfile)))
    log = open(os.path.join(A.HERE, "ref.log"), "a")
    passed = 0
    for ex in examples:
        if only and ex["name"] not in only:
            continue
        folder = os.path.join(A.HERE, "ref", ex["name"])
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(os.path.join(REPO, ex["example"]), folder, ignore=shutil.ignore_patterns("README.md", "metadata.json", "test", "parked"))
        if ex.get("seed"):
            A.seed_files(ex["name"], folder)
        A.hook(ex.get("pre"), log)
        ok, v, errs, nroutes, activity = A.run_folder(folder, ex["run_seconds"], ex.get("probe"), ex.get("probe_regex"), ex)
        A.hook(ex.get("post"), log)
        passed += ok
        line = f"{ex['name']}: ok={ok} routes={nroutes} activity={activity}" + (("\n    " + errs.replace("\n", "\n    ")) if errs else "")
        print(line, flush=True); print(line, file=log, flush=True)
    print(f"reference pass: {passed} of {len(only) if only else len(examples)} pass")


if __name__ == "__main__":
    main()
