#!/usr/bin/env python3
"""Builds the Kamelet side check: steps-kamelet/<name>.json and stepwise-kamelet/<name>/.

Do models know Kamelets as well as components? Each task is written twice with the same requests: once with Kamelets
(kamelet-*) and once with plain components (component-*), so a gap between the two is about Kamelets, not the task.
Run it with tools (the Camel MCP server, as the ladder) and bare (BENCH_BARE=1: file tools only, no catalog, no
runtime feedback). Not part of the ladder or its baselines.

Usage: gen_kamelet.py [<name>]     writes every steps file and project, or one example's
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS_DIR = os.path.join(HERE, "steps-kamelet")
PROJECTS = os.path.join(HERE, "stepwise-kamelet")

ROUTE = "orders.camel.yaml"
INITIAL = {ROUTE: """- route:
    id: orders
    from:
      uri: timer
      parameters:
        timerName: tick
        period: 5000
      steps:
        - log:
            message: "Waiting for orders"
""", "application.properties": ""}

PAID = '{"orderId":"ORD-1","status":"paid","amount":42}'
PENDING = '{"orderId":"ORD-2","status":"pending","amount":42}'

# ---------------------------------------------------------------- orders pipeline: source, extract a field, filter
K_SOURCE = """      uri: kamelet:timer-source
      parameters:
        period: 2000
        message: '%s'
        contentType: application/json
"""
K_LOG = """        - to:
            uri: kamelet:log-sink
"""
K_EXTRACT = """        - to:
            uri: kamelet:extract-field-action
            parameters:
              field: orderId
"""
K_FILTER = """        - to:
            uri: kamelet:predicate-filter-action
            parameters:
              expression: "@.status == 'paid'"
"""
C_SOURCE = """      uri: timer
      parameters:
        timerName: orders
        period: 2000
"""
C_BODY = """        - setBody:
            constant: '%s'
"""
C_LOG = """        - to:
            uri: log:orders
"""
C_EXTRACT = """        - setBody:
            jsonpath: "$.orderId"
"""
C_FILTER_OPEN = """        - filter:
            jsonpath: "$[?(@.status == 'paid')]"
            steps:
"""


def orders(src, steps):
    return "- route:\n    id: orders\n    from:\n" + src + "      steps:\n" + steps


def indent(s, n):
    return "".join(" " * n + l + "\n" if l else "\n" for l in s.splitlines())


PIPE_STEPS = [
    {"k": "Replace the route's source with the timer-source Kamelet: every 2 seconds it emits the message %s as JSON "
          "(content type application/json). Send each message to the log-sink Kamelet." % PAID,
     "c": "Replace the route's source with the timer component: every 2 seconds set the body to the message %s. "
          "Send each message to the log component (logger name orders)." % PAID,
     "check": {"log_regex": "ORD-1"}},
    {"k": "Before the log-sink, use the extract-field-action Kamelet so only the orderId value is logged, not the whole "
          "order.",
     "c": "Before the log, set the body to only the orderId value of the JSON message, so only that is logged, not the "
          "whole order.",
     "check": {"log_regex": "ORD-1", "log_not_regex": "status"}},
    {"k": "Change the message to %s and add the predicate-filter-action Kamelet first, so only orders with status paid "
          "go on to the extract and the log." % PENDING,
     "c": "Change the message to %s and add a filter first, so only orders with status paid go on to the extract and "
          "the log." % PENDING,
     "check": {"log_not_regex": "ORD-2"}},
]
PIPE_K = [
    orders(K_SOURCE % PAID, K_LOG),
    orders(K_SOURCE % PAID, K_EXTRACT + K_LOG),
    orders(K_SOURCE % PENDING, K_FILTER + K_EXTRACT + K_LOG),
]
PIPE_C = [
    orders(C_SOURCE, C_BODY % PAID + C_LOG),
    orders(C_SOURCE, C_BODY % PAID + C_EXTRACT + C_LOG),
    orders(C_SOURCE, C_BODY % PENDING + C_FILTER_OPEN + indent(C_EXTRACT + C_LOG, 6)),
]
PIPE_FILE = [{"k": "timer-source", "c": r"uri: timer\b"},
             {"k": "extract-field-action", "c": r'orderId(?!":)'},
             {"k": "predicate-filter-action", "c": "filter"}]

# ---------------------------------------------------------------- kafka round trip
MSG = "Order ORD-7 placed"
K_KAFKA_OUT = """- route:
    id: orders
    from:
      uri: kamelet:timer-source
      parameters:
        period: 3000
        message: "%s"
      steps:
        - to:
            uri: kamelet:kafka-sink
            parameters:
              topic: orders
              bootstrapServers: localhost:9092
""" % MSG
K_KAFKA_IN = """- route:
    id: received
    from:
      uri: kamelet:kafka-source
      parameters:
        topic: orders
        bootstrapServers: localhost:9092
      steps:
        - to:
            uri: kamelet:log-sink
"""
C_KAFKA_OUT = """- route:
    id: orders
    from:
      uri: timer
      parameters:
        timerName: orders
        period: 3000
      steps:
        - setBody:
            constant: "%s"
        - to:
            uri: kafka
            parameters:
              topic: orders
              brokers: localhost:9092
""" % MSG
C_KAFKA_IN = """- route:
    id: received
    from:
      uri: kafka
      parameters:
        topic: orders
        brokers: localhost:9092
      steps:
        - to:
            uri: log:received
"""
KAFKA_STEPS = [
    {"k": "Change the route so it sends the message \"%s\" every 3 seconds to the Kafka topic orders on localhost:9092 "
          "(the broker has no authentication), using the timer-source and kafka-sink Kamelets." % MSG,
     "c": "Change the route so it sends the message \"%s\" every 3 seconds to the Kafka topic orders on localhost:9092 "
          "(the broker has no authentication), using the timer and kafka components." % MSG,
     "check": {}},
    {"k": "Add a second route that consumes the topic orders with the kafka-source Kamelet and sends each message to the "
          "log-sink Kamelet.",
     "c": "Add a second route that consumes the topic orders with the kafka component and sends each message to the log "
          "component (logger name received).",
     "check": {"log_regex": MSG}},
]
KAFKA_K = [K_KAFKA_OUT, K_KAFKA_OUT + K_KAFKA_IN]
KAFKA_C = [C_KAFKA_OUT, C_KAFKA_OUT + C_KAFKA_IN]
KAFKA_FILE = [{"k": "kafka-sink", "c": r"uri: kafka\b|kafka:"},
              {"k": "kafka-source", "c": r"(?s)kafka.*kafka"}]


# ---------------------------------------------------------------- a custom Kamelet: a business building block
# Not a twin: the model writes the Kamelet itself (the definition with its properties, and the template), then uses
# it and changes it. What custom Kamelets are for: a block of the business, not a general purpose one like kafka.
TAG_FILE = "tag-order-action.kamelet.yaml"


def tag_kamelet(prefix):
    props = """      tag:
        title: Tag
        description: The tag to append to the order
        type: string
"""
    expr = "${body} [{{tag}}]"
    if prefix:
        props += """      prefix:
        title: Prefix
        description: Goes before the tag
        type: string
        default: "#"
"""
        expr = "${body} [{{prefix}}{{tag}}]"
    return """apiVersion: camel.apache.org/v1
kind: Kamelet
metadata:
  name: tag-order-action
  labels:
    camel.apache.org/kamelet.type: action
spec:
  definition:
    title: Tag Order
    description: Appends a tag to the order in the message body
    required:
      - tag
    type: object
    properties:
""" + props + """  template:
    from:
      uri: kamelet:source
      steps:
        - setBody:
            expression:
              simple:
                expression: "%s"
""" % expr


TAG_ROUTE = """- route:
    id: orders
    from:
      uri: timer
      parameters:
        timerName: orders
        period: 2000
      steps:
        - setBody:
            expression:
              constant:
                expression: Order ORD-5
        - to:
            uri: kamelet:tag-order-action
            parameters:
              tag: priority
        - log:
            message: "Tagged: ${body}"
"""
CUSTOM = {"name": "kamelet-custom", "steps": [
    {"id": 1,
     "request": "Write a custom action Kamelet named tag-order-action in the file %s in the project. It has one "
                "required property tag and appends a space and the tag in square brackets to the message body (with tag "
                "priority the body Order ORD-5 becomes Order ORD-5 [priority]). Then change the route: every 2 "
                "seconds set the body to \"Order ORD-5\", send it through tag-order-action with tag priority, and log "
                "\"Tagged: <body>\"." % TAG_FILE,
     "check": {"file_regex": "tag-order-action", "files": {TAG_FILE: "kind:\\s*Kamelet"},
               "log_regex": "Tagged: Order ORD-5 \\[priority\\]"},
     "reference": {TAG_FILE: tag_kamelet(False), ROUTE: TAG_ROUTE}},
    {"id": 2,
     "request": "Give tag-order-action a second, optional property prefix with the default value #, which goes before "
                "the tag, so the route logs \"Tagged: Order ORD-5 [#priority]\" without changing the route.",
     "check": {"files": {TAG_FILE: "prefix"}, "log_regex": "Tagged: Order ORD-5 \\[#priority\\]"},
     "reference": {TAG_FILE: tag_kamelet(True)}},
]}


def example(name, kind, steps, refs, files, infra=None):
    out = []
    for i, (s, ref, f) in enumerate(zip(steps, refs, files), 1):
        chk = dict(s["check"]); chk["file_regex"] = f[kind]
        out.append({"id": i, "request": s[kind], "check": chk, "reference": {ROUTE: ref}})
    ex = {"name": name, "steps": out}
    if infra:
        ex["infra"] = infra
    return ex


EXAMPLES = [
    example("kamelet-orders", "k", PIPE_STEPS, PIPE_K, PIPE_FILE),
    example("component-orders", "c", PIPE_STEPS, PIPE_C, PIPE_FILE),
    example("kamelet-kafka", "k", KAFKA_STEPS, KAFKA_K, KAFKA_FILE, ["kafka"]),
    example("component-kafka", "c", KAFKA_STEPS, KAFKA_C, KAFKA_FILE, ["kafka"]),
    CUSTOM,
]


def main():
    os.makedirs(STEPS_DIR, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for ex in EXAMPLES:
        if only and ex["name"] != only:
            continue
        cfg = {"project": "stepwise-kamelet/" + ex["name"], "route_file": ROUTE, "props_file": "application.properties",
               "wait_seconds": 8, "source_dir": True, "initial": INITIAL, "steps": ex["steps"]}
        if ex.get("infra"):
            cfg["infra"] = ex["infra"]
        with open(os.path.join(STEPS_DIR, ex["name"] + ".json"), "w") as f:
            json.dump(cfg, f, indent=1)
        d = os.path.join(PROJECTS, ex["name"])
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        for fname, content in INITIAL.items():
            with open(os.path.join(d, fname), "w") as f:
                f.write(content)
        print(f"{ex['name']}: {len(ex['steps'])} steps, project stepwise-kamelet/{ex['name']}")


if __name__ == "__main__":
    main()
