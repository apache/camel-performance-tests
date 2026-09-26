#!/usr/bin/env python3
"""Builds the round-2 ladder set from the examples catalog: examples-ladder.json and seed/<name>/.

    gen_ladder.py [path to camel-jbang-examples]      default ~/workspace/camel-jbang-examples

The prompt is the catalog description (written as observable behaviour), the seeds are the data files the description
names (orders, inbox, order.json, stock.json, the contract, the stylesheet, the Groovy mapping): the model writes the
routes, the beans and the properties. CHECKS below is the hand-written part: what the log and the folder must show for
the description to count as met; the reference example must pass every check (ref_pass.py) before a model sees the set.
Docker-free rungs only (run, transform, route, fail-well, connect, contracts); quick-start was round 1, showcase, ai
and cloud are out.
"""
import json, os, shutil, sys

REPO = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/workspace/camel-jbang-examples")
HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = ["run", "transform", "route", "fail-well", "connect", "contracts"]
# files never seeded: the model writes routes, properties and beans; README/metadata/tests are not part of the app
NO_SEED = {"README.md", "metadata.json", "test", "parked"}
NO_SEED_EXT = (".yaml", ".properties", ".java")
ORD = r"ORD-\d{4}"
NL = r"[^\n]*"


def L(*terms):
    """regex for one log line that carries every term, in any order (case-insensitive)"""
    return "(?im)^" + "".join(f"(?=.*{t})" for t in terms) + ".*$"

CHECKS = {
    "run/order-generator": dict(run_seconds=12, require_files=["*.java"],
        log_regex=[['(?s)\\{[^\\n]*"[^\\n]*\\}.*\\n.*\\{[^\\n]*"[^\\n]*\\}', 'two orders logged as JSON']]),   # two JSON orders logged
    "run/nightly-report": dict(run_seconds=25,
        log_regex=[['(?s)\\.yaml:\\d+\\s*:[^\\n]*\\d{4}-\\d{2}-\\d{2}[^\\n]*\\d+.*\\n.*\\.yaml:\\d+\\s*:[^\\n]*\\d{4}-\\d{2}-\\d{2}', 'two report runs logged, each with a timestamp and the stock counts']]),
    "run/properties-and-profiles": dict(run_seconds=8, require_files=["application-prod.properties"],
        log_regex=[['\\.yaml:\\d+\\s*:[^\\n]*\\b(EUR|USD|DKK|GBP)\\b', 'the welcome logged with the currency from application.properties']]),
    "transform/json-transform": dict(run_seconds=10,
        log_regex=[['ORD-1001', 'the order ORD-1001 logged'], ['"sku"\\s*:\\s*"CAMEL-TSHIRT"', 'the pick list logged as JSON with the sku CAMEL-TSHIRT']]),
    "transform/xml-to-json": dict(run_seconds=10,
        log_regex=[['<order', 'the XML order logged as it was read (the <order element)'], ['"CAMEL-TSHIRT"', 'the same order logged as JSON (CAMEL-TSHIRT as a JSON string)']]),
    "transform/csv-to-json": dict(run_seconds=10, output_files=[["outbox/*.json", 3]],
        log_regex=[['INV-2001', 'invoice INV-2001 logged'], ['INV-2003', 'invoice INV-2003 logged'], ['"[a-zA-Z]+"\\s*:\\s*"INV-200\\d"', 'an invoice logged as JSON (a quoted field with the value INV-200x)']]),
    "transform/data-mapping": dict(run_seconds=10,
        log_regex=[['SHIP-1001', 'the shipment SHIP-1001 logged'], ['"totalPieces"\\s*:\\s*3', 'totalPieces 3 in the logged shipment JSON'], ['domestic', 'the domestic service in the logged shipment']]),
    "transform/groovy": dict(run_seconds=10, require_text={"application.properties": "commons-validator"},
        log_regex=[['anna@example\\.com', 'anna@example.com logged as accepted'], ['not-an-address', 'not-an-address logged as rejected']]),
    "transform/xslt": dict(run_seconds=10,
        log_regex=[['<packingSlip', 'the packing slip logged (a <packingSlip element)'], ['<pieces>3</pieces>', '<pieces>3</pieces> in the logged slip'], ['CAMEL-TSHIRT', 'CAMEL-TSHIRT in the logged slip']]),
    "route/content-based-router": dict(run_seconds=10,
        log_regex=[['(?im)^(?=.*ORD-1001)(?=.*(local|copenhagen)).*$', 'ORD-1001 logged as local delivery'], ['(?im)^(?=.*ORD-1002)(?=.*\\bEU\\b).*$', 'ORD-1002 logged as EU shipping'], ['(?im)^(?=.*ORD-1003)(?=.*(export|customs)).*$', 'ORD-1003 logged as export with customs']]),
    "route/order-lines": dict(run_seconds=10,
        log_regex=[['(?im)^(?=.*ORD-1001)(?=.*CAMEL-TSHIRT).*$', 'a pick line for CAMEL-TSHIRT of ORD-1001'], ['(?im)^(?=.*ORD-1001)(?=.*CAMEL-MUG).*$', 'a pick line for CAMEL-MUG of ORD-1001'], ['ORD-1002', 'order ORD-1002 logged'], ['(?im)^(?=.*ORD-1001)(?=.*(all|\\b2\\b))(?=.*(line|pick)).*$', 'the confirmation that all lines of ORD-1001 went to picking']]),
    "route/aggregator": dict(run_seconds=15,
        log_regex=[['(?im)^(?=.*ORD-1001)(?=.*CAMEL-TSHIRT)(?=.*CAMEL-MUG).*$', 'the shipment of ORD-1001 logged with both lines (CAMEL-TSHIRT and CAMEL-MUG)'], ['(?im)^(?=.*ORD-1002)(?=.*CAMEL-MUG)(?=.*\\b3\\b).*$', 'the shipment of ORD-1002 logged with 3 x CAMEL-MUG']]),
    "route/filter-and-multicast": dict(run_seconds=10,
        log_regex=[['(?im)^(?=.*ORD-1001)(?=.*(warehouse|pick)).*$', 'ORD-1001 logged by the warehouse route'], ['(?im)^(?=.*ORD-1001)(?=.*(invoic|bill)).*$', 'ORD-1001 logged by the invoicing route'], ['ORD-1003', 'ORD-1003 logged as received']],
        log_not_regex=[L("ORD-1003", "(warehouse|invoic|pick|bill)")]),
    "fail-well/error-handling": dict(run_seconds=20, expected_errors=r"(?i)payment|did not answer|declined|ConnectException|Failed delivery",
        log_regex=[['(?im)^(?=.*ORD-1001)(?=.*charged).*$', 'ORD-1001 logged as charged'], ['(?im)^(?=.*ORD-1002)(?=.*charged).*$', 'ORD-1002 logged as charged'], ['(?im)^(?=.*ORD-1003)(?=.*(declin|park|manual|review)).*$', 'ORD-1003 logged as declined and parked'], ['(?s)(WARN|retr|redeliver|attempt).*(WARN|retr|redeliver|attempt)', 'two retries logged (as warnings)']]),
    "fail-well/circuit-breaker": dict(run_seconds=25, expected_errors=r"(?i)supplier|simulat|down",
        log_regex=[['(?i)\\bOPEN\\b', 'the breaker logged as OPEN'], ['(?i)\\bCLOSED\\b', 'the breaker logged as CLOSED'], ['(?i)(fallback|last known|no answer)', 'the fallback answer logged while open']]),
    "connect/file-processing": dict(run_seconds=12, expected_errors=r"(?i)Validation|Predicate|Rollback|negative|2003",
        require_files=["inbox/note-2005.txt"], output_files=[["**/done/*.json", 3], ["**/failed/*", 1]],
        log_regex=[['INV-2001', 'INV-2001 logged as archived'], ['INV-2002', 'INV-2002 logged as archived'], ['INV-2004', 'INV-2004 logged as archived'], ['(?im)^(?=.*(2003|negative))(?=.*(reject|fail|warn|invalid)).*$', 'invoice 2003 (the negative amount) logged as rejected']]),
    "connect/stock-api": dict(run_seconds=15,
        probe="curl -s localhost:8080/stock/CAMEL-MUG; echo; curl -s -o /dev/null -w '%{http_code}' localhost:8080/stock/CAMEL-SOCKS; echo; curl -s localhost:8080/stock | head -c 400",
        probe_regex=r"(?s)CAMEL-MUG" + NL + r"42.*\n404\n.*CAMEL-TSHIRT"),
    "connect/http-client": dict(run_seconds=15,
        log_regex=[['(?im)^(?=.*ORD-1003)(?=.*CAMEL-CAP)(?=.*(back|short|\\b0\\b)).*$', 'ORD-1003 CAMEL-CAP logged as back-order with the stock level'], ['(?im)^(?=.*ORD-1001)(?=.*CAMEL-TSHIRT)(?=.*\\b120\\b).*$', 'ORD-1001 CAMEL-TSHIRT logged as ok with 120 in stock']]),
    "contracts/openapi-server": dict(run_seconds=15,
        probe="curl -s localhost:8080/api/stock/CAMEL-MUG; echo; "
              "curl -s -o /dev/null -w '%{http_code}\\n' -X POST -H 'Content-Type: application/json' -d '{\"orderId\": \"ORD-1001\", \"qty\": 2}' localhost:8080/api/stock/CAMEL-MUG/reserve; "
              "curl -s -o /dev/null -w '%{http_code}\\n' -X POST -H 'Content-Type: application/json' -d '{\"orderId\": \"ORD-1003\", \"qty\": 1}' localhost:8080/api/stock/CAMEL-CAP/reserve; "
              "curl -s -o /dev/null -w '%{http_code}\\n' -X POST -H 'Content-Type: application/json' localhost:8080/api/stock/CAMEL-MUG/reserve; "
              "curl -s localhost:8080/openapi localhost:8080/api/openapi | head -c 300",
        probe_regex=r"(?s)CAMEL-MUG" + NL + r"42.*\n200\n409\n400\n.*openapi"),
    "contracts/openapi-client": dict(run_seconds=20, expected_errors=r"409|CAMEL-CAP|HttpOperationFailed",
        hint="The stock API server (the openapi-server example) is already running at http://localhost:8080/api and its contract is the file stock-api.json.",
        pre="./ref-server.sh start", post="./ref-server.sh stop",
        log_regex=[['(?im)^(?=.*CAMEL-CAP)(?=.*409).*$', 'the 409 for CAMEL-CAP logged'], ['(?im)^(?=.*ORD-1001)(?=.*CAMEL-TSHIRT)(?=.*reserv).*$', 'the reservation of CAMEL-TSHIRT for ORD-1001 logged']]),
}


def seed_dir(src, dst):
    """copies the data files of an example (not routes, properties, beans, docs, tests, outputs); returns the list"""
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in NO_SEED and not d.startswith(".")]
        for f in files:
            if f in NO_SEED or f.endswith(NO_SEED_EXT) or f.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(root, f), src)
            os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
            shutil.copy2(os.path.join(root, f), os.path.join(dst, rel))
            out.append(rel)
    return sorted(out)


def main():
    cat = json.load(open(os.path.join(REPO, "camel-jbang-example-catalog.json")))
    examples = cat["examples"] if isinstance(cat, dict) else cat
    keep = [e for e in examples if e["level"] in LEVELS and not e.get("requiresDocker")]
    keep.sort(key=lambda e: (LEVELS.index(e["level"]), e.get("order", 99)))
    missing = [e["name"] for e in keep if e["name"] not in CHECKS]
    if missing:
        sys.exit("no checks for: " + ", ".join(missing))
    seeds = os.path.join(HERE, "seed")
    out = []
    for e in keep:
        name = e["name"].replace("/", "-")
        c = dict(CHECKS[e["name"]])
        entry = {"name": name, "example": e["name"], "level": e["level"],
                 "prompt": e["description"].rstrip(". "),
                 "expect": e["description"]}
        shutil.rmtree(os.path.join(seeds, name), ignore_errors=True)
        seeded = seed_dir(os.path.join(REPO, e["name"]), os.path.join(seeds, name))
        if seeded:
            entry["seed"] = True
            entry["seed_files"] = seeded
        entry.update(c)
        out.append(entry)
    # the reference stock API server the openapi-client example calls (started by ref-server.sh, port 8080)
    ref = os.path.join(seeds, "openapi-server-ref")
    shutil.rmtree(ref, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "contracts/openapi-server"), ref, ignore=shutil.ignore_patterns("README.md", "metadata.json", "test"))
    json.dump(out, open(os.path.join(HERE, "examples-ladder.json"), "w"), indent=1)
    print(f"{len(out)} examples -> examples-ladder.json; seeds under seed/")
    for e in out:
        print(f"  {e['name']:<34} {e['run_seconds']:>3}s seed={len(e.get('seed_files', []))} checks={[k for k in e if k in ('log_regex','log_not_regex','probe','require_files','require_text','output_files','expected_errors')]}")


if __name__ == "__main__":
    main()
