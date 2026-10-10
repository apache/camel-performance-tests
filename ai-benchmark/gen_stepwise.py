#!/usr/bin/env python3
"""Builds the round-2 stepwise set from the examples' "Build it step by step" README sections: steps-ladder/<name>.json
and stepwise-ladder/<name>/ (the project as it is after the README's step 1, plus the seeds).

Each steps file has the shape agent_mcp_stepwise.py reads (project, route_file, props_file, wait_seconds, steps with
request/check/reference) plus "initial": the files of the starting project. The README's step 1 is the starting state;
steps 2..N are the requests. Checks: log_regex (a regex or a list, all must match an INFO record), log_not_regex,
file_regex (the route file), props_regex, files {name: regex}, errors_ok, min_errors.

Usage: gen_stepwise.py            writes every steps file and project
       gen_stepwise.py <name>     rewrites one example's steps file and resets its project (the runner does this per pass)
"""
import datetime, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS_DIR = os.path.join(HERE, "steps-ladder")
PROJECTS = os.path.join(HERE, "stepwise-ladder")
SEEDS = os.path.join(HERE, "seed")

def route(rid, frm, steps, extra=""):
    return "- route:\n    id: " + rid + "\n    from:\n" + frm + "      steps:\n" + steps + extra

TIMER5 = "      uri: timer\n      parameters:\n        timerName: orders\n        period: 5000\n"
FILE_ORDERS = "      uri: file\n      parameters:\n        directoryName: orders\n        noop: true\n        sortBy: \"file:name\"\n"
FILE_INBOX = "      uri: file\n      parameters:\n        directoryName: inbox\n        noop: true\n        include: \".*\\\\.xml\"\n"
UNMARSHAL = "        - unmarshal:\n            json:\n              library: Jackson\n"

def log(msg, indent="        "):
    return indent + "- log:\n" + indent + "    message: \"" + msg + "\"\n"

EXAMPLES = []

# ---------------------------------------------------------------- run/order-generator
ON_JAVA_V1 = """package camel.example;

import java.util.concurrent.atomic.AtomicInteger;

public class OrderNumber {

    private final AtomicInteger counter = new AtomicInteger(1000);

    public String next() {
        return "ORD-" + counter.incrementAndGet();
    }
}
"""
ON_JAVA_V2 = """package camel.example;

import java.util.concurrent.atomic.AtomicInteger;

public class OrderNumber {

    private final AtomicInteger counter = new AtomicInteger();

    public void setStart(int start) {
        counter.set(start - 1);
    }

    public String next() {
        return "ORD-" + counter.incrementAndGet();
    }
}
"""
BEANS_V1 = "- beans:\n    - name: orderNumber\n      type: \"camel.example.OrderNumber\"\n"
BEANS_V2 = BEANS_V1 + "      properties:\n        start: \"{{order.first-number}}\"\n"
OG = "order-generator.camel.yaml"
og_s2 = route("order-generator", TIMER5,
              "        - setHeader:\n            name: orderId\n            expression:\n              constant:\n                expression: ORD-1001\n"
              + log("New order ${header.orderId}"))
og_s3 = route("order-generator", TIMER5,
              "        - setHeader:\n            name: orderId\n            expression:\n              method:\n                ref: orderNumber\n                method: next\n"
              + log("New order ${header.orderId}"))
OG_BODY = ("        - setBody:\n            expression:\n              simple:\n                expression: |-\n"
           "                  {\"orderId\": \"${header.orderId}\", \"customer\": \"C-${random(100,999)}\", \"country\": \"DK\",\n"
           "                   \"lines\": [{\"sku\": \"CAMEL-TSHIRT\", \"qty\": ${random(1,3)}, \"price\": 19.95}], \"status\": \"paid\"}\n")
og_s4 = route("order-generator", TIMER5,
              "        - setHeader:\n            name: orderId\n            expression:\n              method:\n                ref: orderNumber\n                method: next\n"
              + OG_BODY + log("New order ${header.orderId}: ${body}"))
og_s5 = og_s4.replace("period: 5000", "period: \"{{order.period}}\"")
EXAMPLES.append({
    "name": "run-order-generator", "route_file": OG, "props_file": "application.properties", "wait_seconds": 13,
    "initial": {OG: route("order-generator", TIMER5, log("New order")), "application.properties": ""},
    "steps": [
        {"request": "Set a header orderId to a constant ORD-1001 and log \"New order ${header.orderId}\".",
         "check": {"file_regex": "setHeader", "log_regex": "New order ORD-1001"},
         "reference": {OG: og_s2}},
        {"request": "Add a Java class OrderNumber (package camel.example) with a method next() that returns \"ORD-\" and a counter starting at 1001, declare it as the bean orderNumber in beans.yaml, and set the orderId header from the bean's method instead of the constant. A new Java class needs a restart of the integration to be compiled; it is restarted after your change.",
         "restart": True,
         "check": {"file_regex": "method|bean:orderNumber", "files": {"OrderNumber.java": "next\\(\\)", "beans.yaml": "orderNumber"}, "log_regex": "New order ORD-1002"},
         "reference": {"OrderNumber.java": ON_JAVA_V1, "beans.yaml": BEANS_V1, OG: og_s3}},
        {"request": "Set the body to a JSON order with the order id, a random customer (C- and a random number) and one line with sku CAMEL-TSHIRT and a random qty, and log \"New order <id>: <body>\".",
         "check": {"file_regex": "random", "log_regex": "New order ORD-\\d+.*\"orderId\"\\s*:\\s*\"ORD-\\d+\".*\"customer\"\\s*:\\s*\"C-\\d+\""},
         "reference": {OG: og_s4}},
        {"request": "Move the timer period (order.period=5000) and the first order number (order.first-number=1001) to application.properties, and use them as {{order.period}} in the route and as a start property of the bean in beans.yaml (the class gets a setStart(int) that the counter starts from). The changed class needs a restart; it is restarted after your change.",
         "restart": True,
         "check": {"props_regex": "order\\.period\\s*=\\s*5000", "file_regex": "\\{\\{order\\.period\\}\\}", "files": {"beans.yaml": "order\\.first-number", "OrderNumber.java": "setStart"}, "log_regex": "New order ORD-100[1-9]"},
         "reference": {"application.properties": "order.period=5000\norder.first-number=1001\n", "OrderNumber.java": ON_JAVA_V2, "beans.yaml": BEANS_V2, OG: og_s5}},
    ]})

# ---------------------------------------------------------------- run/nightly-report
NR = "nightly-report.camel.yaml"
TIMER10 = "      uri: timer\n      parameters:\n        timerName: report\n        period: 10000\n"
CRON = "      uri: cron\n      parameters:\n        name: report\n        schedule: \"0/10 * * * * ?\"\n"
CRON_P = "      uri: cron\n      parameters:\n        name: report\n        schedule: \"{{report.schedule}}\"\n"
MSG1 = "Inventory report: 120 T-shirts and 45 mugs in stock"
MSG2 = "Inventory report ${date:now:yyyy-MM-dd HH:mm:ss}: 120 T-shirts and 45 mugs in stock"
MSG3 = "Inventory report ${date:now:yyyy-MM-dd HH:mm:ss}: {{inventory.tshirt}} T-shirts and {{inventory.mug}} mugs in stock"
EXAMPLES.append({
    "name": "run-nightly-report", "route_file": NR, "props_file": "application.properties", "wait_seconds": 20,
    "initial": {NR: route("nightly-report", TIMER10, log(MSG1)), "application.properties": ""},
    "steps": [
        {"request": "Replace the timer with the cron component and the schedule 0/10 * * * * ? so the report keeps coming every ten seconds.",
         "check": {"file_regex": "cron", "log_regex": "Inventory report"}, "reference": {NR: route("nightly-report", CRON, log(MSG1))}},
        {"request": "Add the current time to the message with ${date:now:yyyy-MM-dd HH:mm:ss}.",
         "check": {"log_regex": "(?s)(?=.*Inventory report)(?=.*\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})"}, "reference": {NR: route("nightly-report", CRON, log(MSG2))}},
        {"request": "Move the schedule and the two stock counts to application.properties (report.schedule, inventory.tshirt=120, inventory.mug=45) and use them as {{...}} placeholders in the route.",
         "check": {"props_regex": "report\\.schedule\\s*=", "file_regex": "\\{\\{report\\.schedule\\}\\}", "log_regex": "120 T-shirts and 45 mugs"},
         "reference": {NR: route("nightly-report", CRON_P, log(MSG3)), "application.properties": "report.schedule=0/10 * * * * ?\ninventory.tshirt=120\ninventory.mug=45\n"}},
        {"request": "Change the schedule to 0 0 2 * * ? so the report runs at two in the morning every night.",
         "check": {"props_regex": "report\\.schedule\\s*=\\s*0 0 2 \\* \\* \\?"},
         "reference": {"application.properties": "report.schedule=0 0 2 * * ?\ninventory.tshirt=120\ninventory.mug=45\n"}},
    ]})

# ---------------------------------------------------------------- run/properties-and-profiles
PP = "properties-and-profiles.camel.yaml"
TIMER3 = "      uri: timer\n      parameters:\n        timerName: welcome\n        period: 3000\n"
TIMER3_P = TIMER3.replace("period: 3000", "period: \"{{welcome.period}}\"")
EXAMPLES.append({
    "name": "run-properties-and-profiles", "route_file": PP, "props_file": "application.properties", "wait_seconds": 8,
    "initial": {PP: route("welcome", TIMER3, log("Welcome to Camel Shop")), "application.properties": ""},
    "steps": [
        {"request": "Move the shop name to application.properties as shop.name=Camel Shop and use {{shop.name}} in the message.",
         "check": {"props_regex": "shop\\.name\\s*=", "file_regex": "\\{\\{shop\\.name\\}\\}", "log_regex": "Welcome to Camel Shop"},
         "reference": {PP: route("welcome", TIMER3, log("Welcome to {{shop.name}}")), "application.properties": "shop.name=Camel Shop\n"}},
        {"request": "Add shop.currency=EUR the same way and mention it in the message: \"Welcome to <name>, prices in <currency>\".",
         "check": {"props_regex": "shop\\.currency\\s*=\\s*EUR", "log_regex": "Welcome to Camel Shop, prices in EUR"},
         "reference": {PP: route("welcome", TIMER3, log("Welcome to {{shop.name}}, prices in {{shop.currency}}")), "application.properties": "shop.name=Camel Shop\nshop.currency=EUR\n"}},
        {"request": "Create application-prod.properties with shop.name=Camel Shop and shop.currency=USD, and change application.properties to the development values shop.name=Camel Shop (development) and shop.currency=EUR, so that running with --profile=prod changes the message.",
         "check": {"files": {"application-prod.properties": "shop\\.currency\\s*=\\s*USD"}, "props_regex": "development", "log_regex": "Welcome to Camel Shop \\(development\\), prices in EUR"},
         "reference": {"application.properties": "shop.name=Camel Shop (development)\nshop.currency=EUR\n", "application-prod.properties": "shop.name=Camel Shop\nshop.currency=USD\n"}},
        {"request": "Move the timer period to a property welcome.period=3000 that only application.properties has, and use it in the route.",
         "check": {"props_regex": "welcome\\.period\\s*=\\s*3000", "file_regex": "\\{\\{welcome\\.period\\}\\}", "log_regex": "Welcome to Camel Shop"},
         "reference": {PP: route("welcome", TIMER3_P, log("Welcome to {{shop.name}}, prices in {{shop.currency}}")), "application.properties": "shop.name=Camel Shop (development)\nshop.currency=EUR\nwelcome.period=3000\n"}},
    ]})

# ---------------------------------------------------------------- transform/json-transform
JT = "json-transform.camel.yaml"
TIMER1 = "      uri: timer\n      parameters:\n        timerName: order\n        repeatCount: 1\n"
BODY_FILE = "        - setBody:\n            expression:\n              constant:\n                expression: \"resource:file:order.json\"\n"
H_ID = "        - setHeader:\n            name: orderId\n            expression:\n              jsonpath:\n                expression: \"$.orderId\"\n"
H_COUNT = "        - setHeader:\n            name: itemCount\n            expression:\n              jsonpath:\n                expression: \"$.lines.length()\"\n"
def jq(expr):
    return ("        - transform:\n            expression:\n              jq:\n                expression: \"" + expr + "\"\n                resultType: java.lang.String\n")
JQ_FULL = "{order: .orderId, country: .country, pick: [.lines[] | {sku: .sku, qty: .qty}]}"
EXAMPLES.append({
    "name": "transform-json-transform", "route_file": JT, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-json-transform",
    "initial": {JT: route("json-transform", TIMER1, BODY_FILE + log("Order: ${body}")), "application.properties": ""},
    "steps": [
        {"request": "Read the order id into a header orderId with a jsonpath expression $.orderId and log the message \"Order ${header.orderId}: ${body}\" (it reads Order ORD-1001: followed by the order JSON).",
         "check": {"file_regex": "jsonpath", "log_regex": "Order ORD-1001: \\{"},
         "reference": {JT: route("json-transform", TIMER1, BODY_FILE + H_ID + log("Order ${header.orderId}: ${body}"))}},
        {"request": "Add the number of lines as a header itemCount with jsonpath $.lines.length() and log \"Order <id> with <count> lines: <body>\".",
         "check": {"log_regex": "Order ORD-1001 with 2 lines"},
         "reference": {JT: route("json-transform", TIMER1, BODY_FILE + H_ID + H_COUNT + log("Order ${header.orderId} with ${header.itemCount} lines: ${body}"))}},
        {"request": "Add a transform step with a jq expression that keeps only the order id as {order: .orderId} (result type java.lang.String), and log the result as \"Pick list for the warehouse: <body>\".",
         "check": {"file_regex": "jq", "log_regex": "Pick list for the warehouse: \\{\\s*\"order\"\\s*:\\s*\"ORD-1001\"\\s*\\}"},
         "reference": {JT: route("json-transform", TIMER1, BODY_FILE + H_ID + H_COUNT + log("Order ${header.orderId} with ${header.itemCount} lines: ${body}") + jq("{order: .orderId}") + log("Pick list for the warehouse: ${body}"))}},
        {"request": "Extend the jq expression with the country and a pick list of sku and qty per line: {order: .orderId, country: .country, pick: [.lines[] | {sku: .sku, qty: .qty}]}.",
         "check": {"log_regex": ["\"country\"\\s*:\\s*\"DK\"", "\"sku\"\\s*:\\s*\"CAMEL-TSHIRT\""]},
         "reference": {JT: route("json-transform", TIMER1, BODY_FILE + H_ID + H_COUNT + log("Order ${header.orderId} with ${header.itemCount} lines: ${body}") + jq(JQ_FULL) + log("Pick list for the warehouse: ${body}"))}},
    ]})

# ---------------------------------------------------------------- transform/xml-to-json
XJ = "xml-to-json.camel.yaml"
XML2 = """<?xml version="1.0" encoding="UTF-8"?>
<order id="ORD-1002" country="DE">
  <customer>C-207</customer>
  <line sku="CAMEL-MUG" qty="3" price="9.50"/>
  <status>paid</status>
</order>
"""
EXAMPLES.append({
    "name": "transform-xml-to-json", "route_file": XJ, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-xml-to-json",
    "initial": {XJ: route("xml-to-json", FILE_INBOX, log("Supplier order as XML: ${body}")), "application.properties": ""},
    "steps": [
        {"request": "Add an unmarshal step with jacksonXml and log the body after it as \"Supplier order as a map: <body>\" (it is a map now).",
         "check": {"file_regex": "jacksonXml", "log_regex": "Supplier order as a map: \\{.*(\\bid|orderId)=ORD-1001"},
         "reference": {XJ: route("xml-to-json", FILE_INBOX, log("Supplier order as XML: ${body}") + "        - unmarshal:\n            jacksonXml: {}\n" + log("Supplier order as a map: ${body}"))}},
        {"request": "Add a marshal step with the json data format (library Jackson) after the unmarshal and log again: \"The same order as JSON: <body>\".",
         "check": {"file_regex": "marshal:\\s*\\n\\s*json", "log_regex": "The same order as JSON: \\{.*\"(id|orderId)\"\\s*:\\s*\"ORD-1001\""},
         "reference": {XJ: route("xml-to-json", FILE_INBOX, log("Supplier order as XML: ${body}") + "        - unmarshal:\n            jacksonXml: {}\n" + "        - marshal:\n            json:\n              library: Jackson\n" + log("The same order as JSON: ${body}"))}},
        {"request": "Drop a second supplier order into inbox as supplier-order-2.xml: order ORD-1002 from DE, customer C-207, one line of 3 CAMEL-MUG at 9.50, status paid. The running route converts it too.",
         "check": {"files": {"inbox/supplier-order-2.xml": "ORD-1002"}, "log_regex": "The same order as JSON: \\{.*ORD-1002"},
         "reference": {"inbox/supplier-order-2.xml": XML2}},
    ]})

# ---------------------------------------------------------------- transform/xslt
XS = "xslt.camel.yaml"
XSL_HEAD = "<?xml version=\"1.0\"?>\n<xsl:stylesheet version=\"1.0\" xmlns:xsl=\"http://www.w3.org/1999/XSL/Transform\">\n  <xsl:output method=\"xml\" indent=\"yes\"/>\n  <xsl:template match=\"/order\">\n"
XSL_TAIL = "  </xsl:template>\n</xsl:stylesheet>\n"
XSL_V1 = XSL_HEAD + "    <packingSlip order=\"{@id}\" customer=\"{customer}\" country=\"{@country}\"/>\n" + XSL_TAIL
XSL_V2 = XSL_HEAD + "    <packingSlip order=\"{@id}\" customer=\"{customer}\" country=\"{@country}\">\n      <xsl:for-each select=\"line\">\n        <item sku=\"{@sku}\" pieces=\"{@qty}\"/>\n      </xsl:for-each>\n    </packingSlip>\n" + XSL_TAIL
XSL_V3 = XSL_HEAD + "    <packingSlip order=\"{@id}\" customer=\"{customer}\" country=\"{@country}\">\n      <xsl:for-each select=\"line\">\n        <item sku=\"{@sku}\" pieces=\"{@qty}\"/>\n      </xsl:for-each>\n      <pieces><xsl:value-of select=\"sum(line/@qty)\"/></pieces>\n    </packingSlip>\n" + XSL_TAIL
XSLT_STEP = "        - to:\n            uri: xslt\n            parameters:\n              resourceUri: packing-slip.xsl\n"
xs_route = route("xslt", FILE_INBOX, XSLT_STEP + log("Packing slip: ${body}"))
EXAMPLES.append({
    "name": "transform-xslt", "route_file": XS, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-xslt", "exclude_seeds": ["packing-slip.xsl"],
    "initial": {XS: route("xslt", FILE_INBOX, log("Supplier order: ${body}")), "application.properties": ""},
    "steps": [
        {"request": "Add a to: xslt step with a stylesheet packing-slip.xsl (next to the route) that turns the order into a packingSlip root element carrying the order id, the customer and the country as attributes, and log \"Packing slip: <body>\".",
         "check": {"file_regex": "xslt", "files": {"packing-slip.xsl": "packingSlip"}, "log_regex": "<packingSlip[^>]*ORD-1001"},
         "reference": {XS: xs_route, "packing-slip.xsl": XSL_V1}},
        {"request": "In the stylesheet, add a for-each over the order's line elements writing one item element each, with the sku and the qty as pieces.",
         "check": {"files": {"packing-slip.xsl": "for-each"}, "log_regex": "(?s)<item.{0,120}CAMEL-TSHIRT"},
         "reference": {"packing-slip.xsl": XSL_V2}},
        {"request": "Add an element named pieces with the total number of pieces, using sum() over the lines' qty.",
         "check": {"files": {"packing-slip.xsl": "sum\\("}, "log_regex": "(?s)<pieces.{0,20}3"},
         "reference": {"packing-slip.xsl": XSL_V3}},
    ]})

# ---------------------------------------------------------------- route/content-based-router
CB = "content-based-router.camel.yaml"
def when(expr, msg):
    return ("              - expression:\n                  simple:\n                    expression: \"" + expr + "\"\n                steps:\n" + log(msg, "                  "))
CB_OTHER = "            otherwise:\n              steps:\n" + log("Order ${body[orderId]} from ${body[country]}: export, customs declaration needed", "                ")
CB_DK = when("${body[country]} == 'DK'", "Order ${body[orderId]} from ${body[country]}: local delivery from the Copenhagen warehouse")
CB_EU = when("${body[country]} in 'DE,SE,NL,FR'", "Order ${body[orderId]} from ${body[country]}: EU shipping, no customs")
cb_s2 = route("content-based-router", FILE_ORDERS, UNMARSHAL + "        - choice:\n            when:\n" + CB_DK + CB_OTHER)
cb_s3 = route("content-based-router", FILE_ORDERS, UNMARSHAL + "        - choice:\n            when:\n" + CB_DK + CB_EU + CB_OTHER)
ORDER_1004 = "{\"orderId\": \"ORD-1004\", \"customer\": \"C-318\", \"country\": \"SE\", \"status\": \"paid\", \"lines\": [{\"sku\": \"CAMEL-CAP\", \"qty\": 2, \"price\": 14.00}]}\n"
EXAMPLES.append({
    "name": "route-content-based-router", "route_file": CB, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "route-content-based-router",
    "initial": {CB: route("content-based-router", FILE_ORDERS, UNMARSHAL + log("Order ${body[orderId]} from ${body[country]}")), "application.properties": ""},
    "steps": [
        {"request": "Add a choice with one when for the country DK (local delivery from the Copenhagen warehouse) and an otherwise (export, customs declaration needed), each logging a different line with the order id and the country.",
         "check": {"file_regex": "otherwise", "log_regex": ["(?is)(?=.*ORD-1001)(?=.*(local|copenhagen))", "(?is)(?=.*ORD-1003)(?=.*(export|customs))"]},
         "reference": {CB: cb_s2}},
        {"request": "Add a second when for the EU countries with the simple operator in 'DE,SE,NL,FR', logging EU shipping with no customs.",
         "check": {"file_regex": "in 'DE,SE,NL,FR'|in \\\\\"DE,SE,NL,FR\\\\\"", "log_regex": "(?is)(?=.*ORD-1002)(?=.*(EU|no customs))"},
         "reference": {CB: cb_s3}},
        {"request": "Add a fourth order file orders/order-1004.json for a Swedish customer (ORD-1004, customer C-318, country SE, status paid, one line) and check the log shows it taking the EU branch.",
         "check": {"files": {"orders/order-1004.json": "\"SE\""}, "log_regex": "(?is)(?=.*ORD-1004)(?=.*(EU|no customs))"},
         "reference": {"orders/order-1004.json": ORDER_1004}},
    ]})

# ---------------------------------------------------------------- route/order-lines
OL = "order-lines.camel.yaml"
OL_HDR = "        - setHeader:\n            name: orderId\n            expression:\n              simple:\n                expression: \"${body[orderId]}\"\n"
def split(inner):
    return "        - split:\n            expression:\n              simple:\n                expression: \"${body[lines]}\"\n            steps:\n" + inner
ol_s2 = route("order-lines", FILE_ORDERS, UNMARSHAL + log("Order ${body[orderId]} with ${body[lines].size()} line(s)") + split(log("  pick ${body[qty]} x ${body[sku]}", "              ")))
ol_s3 = route("order-lines", FILE_ORDERS, UNMARSHAL + OL_HDR + log("Order ${header.orderId} with ${body[lines].size()} line(s)") + split(log("  pick ${body[qty]} x ${body[sku]} for ${header.orderId}", "              ")))
ol_s4 = ol_s3 + log("Order ${header.orderId}: all ${body[lines].size()} line(s) sent to picking")
EXAMPLES.append({
    "name": "route-order-lines", "route_file": OL, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "route-order-lines",
    "initial": {OL: route("order-lines", FILE_ORDERS, UNMARSHAL + log("Order ${body[orderId]} with ${body[lines].size()} line(s)")), "application.properties": ""},
    "steps": [
        {"request": "Add a split over the order's lines (${body[lines]}) and inside it log the message \"  pick ${body[qty]} x ${body[sku]}\" for each line (it reads   pick 2 x CAMEL-TSHIRT).",
         "check": {"file_regex": "split", "log_regex": "pick 2 x CAMEL-TSHIRT"},
         "reference": {OL: ol_s2}},
        {"request": "Keep the order id in a header orderId before the split and use it in the pick line: \"  pick <qty> x <sku> for <orderId>\".",
         "check": {"file_regex": "setHeader", "log_regex": "pick 2 x CAMEL-TSHIRT for ORD-1001"},
         "reference": {OL: ol_s3}},
        {"request": "After the split, log a confirmation \"Order <orderId>: all <n> line(s) sent to picking\"; the body is the whole order again there.",
         "check": {"log_regex": "Order ORD-1001: all 2 line\\(s\\) sent to picking"},
         "reference": {OL: ol_s4}},
    ]})

# ---------------------------------------------------------------- route/filter-and-multicast
FM = "filter-and-multicast.camel.yaml"
FM_LOG = log("Order ${body[orderId]} received, status ${body[status]}")
def filt(inner):
    return "        - filter:\n            expression:\n              simple:\n                expression: \"${body[status]} == 'paid'\"\n            steps:\n" + inner
def multicast(parallel):
    return ("              - multicast:\n" + ("                  parallelProcessing: true\n" if parallel else "")
            + "                  steps:\n                    - to:\n                        uri: direct\n                        parameters:\n                          name: warehouse\n"
            + "                    - to:\n                        uri: direct\n                        parameters:\n                          name: invoicing\n")
DIRECTS = ("- route:\n    id: warehouse\n    from:\n      uri: direct\n      parameters:\n        name: warehouse\n      steps:\n" + log("Warehouse: pick ${body[lines].size()} line(s) for ${body[orderId]}")
           + "- route:\n    id: invoicing\n    from:\n      uri: direct\n      parameters:\n        name: invoicing\n      steps:\n" + log("Invoicing: bill customer ${body[customer]} for ${body[orderId]}"))
fm_s2 = route("filter-and-multicast", FILE_ORDERS, UNMARSHAL + FM_LOG + filt(log("Order ${body[orderId]} is paid: forwarding to the departments", "              ")))
fm_s3 = route("filter-and-multicast", FILE_ORDERS, UNMARSHAL + FM_LOG + filt(multicast(False)), DIRECTS)
fm_s4 = route("filter-and-multicast", FILE_ORDERS, UNMARSHAL + FM_LOG + filt(multicast(True)), DIRECTS)
EXAMPLES.append({
    "name": "route-filter-and-multicast", "route_file": FM, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "route-filter-and-multicast",
    "initial": {FM: route("filter-and-multicast", FILE_ORDERS, UNMARSHAL + FM_LOG), "application.properties": ""},
    "steps": [
        {"request": "Add a filter that only lets paid orders through (status == 'paid') and log inside it \"Order <id> is paid: forwarding to the departments\"; the pending order must not appear in that inner log.",
         "check": {"file_regex": "filter", "log_regex": ["ORD-1001 is paid", "ORD-1003 received, status pending"], "log_not_regex": "ORD-1003 is paid"},
         "reference": {FM: fm_s2}},
        {"request": "Add two routes, direct:warehouse (logs \"Warehouse: pick <n> line(s) for <id>\") and direct:invoicing (logs \"Invoicing: bill customer <customer> for <id>\"), and inside the filter replace the log with a multicast to both.",
         "check": {"file_regex": "multicast", "log_regex": ["Warehouse: pick 2 line\\(s\\) for ORD-1001", "Invoicing: bill customer C-482 for ORD-1001"], "log_not_regex": "(Warehouse|Invoicing).*ORD-1003"},
         "reference": {FM: fm_s3}},
        {"request": "Add parallelProcessing: true to the multicast so both departments get the order at the same moment.",
         "check": {"file_regex": "parallelProcessing:\\s*true", "log_regex": ["Warehouse: pick 2 line\\(s\\) for ORD-1001", "Invoicing: bill customer C-482 for ORD-1001"]},
         "reference": {FM: fm_s4}},
    ]})

# ---------------------------------------------------------------- fail-well/circuit-breaker
CBR = "circuit-breaker.camel.yaml"
TIMER_STOCK = "      uri: timer\n      parameters:\n        timerName: stock\n        period: 1000\n        includeMetadata: true\n"
SUPPLIER_OK = ("- route:\n    id: supplier\n    errorHandler:\n      noErrorHandler: {}\n    from:\n      uri: direct:supplier\n      steps:\n"
               "        - setBody:\n            expression:\n              simple:\n                expression: \"CAMEL-MUG: ${random(20,60)} in stock at the supplier\"\n")
SUPPLIER_FAIL = ("- route:\n    id: supplier\n    errorHandler:\n      noErrorHandler: {}\n    from:\n      uri: direct:supplier\n      steps:\n"
                 "        - choice:\n            when:\n              - expression:\n                  simple:\n                    expression: \"${header.CamelTimerCounter} > 3 && ${header.CamelTimerCounter} <= 12\"\n"
                 "                steps:\n                  - throwException:\n                      exceptionType: java.net.ConnectException\n                      message: \"supplier unreachable\"\n"
                 "            otherwise:\n              steps:\n                - setBody:\n                    expression:\n                      simple:\n                        expression: \"CAMEL-MUG: ${random(20,60)} in stock at the supplier\"\n")
CALL = "        - to:\n            uri: direct:supplier\n"
def breaker(config):
    return ("        - circuitBreaker:\n" + config + "            steps:\n              - to:\n                  uri: direct:supplier\n"
            "            onFallback:\n              steps:\n                - setBody:\n                    expression:\n                      simple:\n                        expression: \"no answer, using last known stock\"\n")
R4J = ("            resilience4jConfiguration:\n              slidingWindowSize: 4\n              minimumNumberOfCalls: 4\n              failureRateThreshold: 50\n"
       "              waitDurationInOpenState: 5000\n              automaticTransitionFromOpenToHalfOpenEnabled: true\n              permittedNumberOfCallsInHalfOpenState: 1\n")
cbr_s1 = route("stock-check", TIMER_STOCK, CALL + log("Stock check ${header.CamelTimerCounter}: ${body}"), SUPPLIER_OK)
cbr_s2 = route("stock-check", TIMER_STOCK, CALL + log("Stock check ${header.CamelTimerCounter}: ${body}"), SUPPLIER_FAIL)
cbr_s3 = route("stock-check", TIMER_STOCK, breaker("") + log("Stock check ${header.CamelTimerCounter}: ${body}"), SUPPLIER_FAIL)
cbr_s4 = route("stock-check", TIMER_STOCK, breaker(R4J) + log("Stock check ${header.CamelTimerCounter} (breaker ${exchangeProperty.CamelCircuitBreakerState}): ${body}"), SUPPLIER_FAIL)
EXAMPLES.append({
    "name": "fail-well-circuit-breaker", "route_file": CBR, "props_file": "application.properties", "wait_seconds": 14,
    "initial": {CBR: cbr_s1, "application.properties": ""},
    "steps": [
        {"request": "Make the supplier route throw a java.net.ConnectException \"supplier unreachable\" when the timer counter (header CamelTimerCounter) is 4 to 12, and answer with the stock otherwise; expect nine stack traces in the log.",
         "check": {"file_regex": "throwException", "log_regex": "Stock check [1-3]: CAMEL-MUG", "errors_ok": True, "min_errors": 1},
         "reference": {CBR: cbr_s2}},
        {"request": "Wrap the call to direct:supplier in a circuitBreaker with an onFallback that sets the body to \"no answer, using last known stock\", so there are no more stack traces (the supplier is still called every time, the default window is 100 calls).",
         "check": {"file_regex": "circuitBreaker", "file_regex2": "onFallback", "log_regex": "no answer, using last known stock", "log_not_regex": "Failed delivery|ConnectException", "errors_ok": True},
         "reference": {CBR: cbr_s3}},
        {"request": "Add a resilience4jConfiguration with slidingWindowSize 4, minimumNumberOfCalls 4, failureRateThreshold 50, waitDurationInOpenState 5000, automaticTransitionFromOpenToHalfOpenEnabled true and permittedNumberOfCallsInHalfOpenState 1, and log the exchange property CamelCircuitBreakerState in the stock check line to watch the breaker open and close.",
         "check": {"file_regex": "resilience4jConfiguration", "log_regex": "Stock check \\d+.*(OPEN|HALF_OPEN)", "log_not_regex": "Failed delivery|ConnectException", "errors_ok": True},
         "reference": {CBR: cbr_s4}},
    ]})

# ---------------------------------------------------------------- connect-service/sql (Postgres as the example ships it, started with camel infra)
SQL = "sql.camel.yaml"
# the example's own datasource: what `camel infra run postgres` prints
SQL_PROPS = ("spring.datasource.url=jdbc:postgresql://localhost:5432/test\nspring.datasource.username=test\n"
             "spring.datasource.password=test\nspring.datasource.driverClassName=org.postgresql.Driver\n")
TIMER_SETUP = "      uri: timer\n      parameters:\n        timerName: setup\n        repeatCount: 1\n        delay: 0\n"
TIMER_REPORT = "      uri: timer\n      parameters:\n        timerName: report\n        delay: 5000\n        period: 10000\n"
FILE_ORDERS_SQL = FILE_ORDERS + "        initialDelay: 2000\n"
def sql_to(query, noop=False):
    return ("        - to:\n            uri: sql\n            parameters:\n              query: \"" + query + "\"\n" + ("              noop: true\n" if noop else ""))
# exactly as the example has it: no reset in the route. A reset here runs on every reload too, and then an UPDATE
# that fires before the file route's inserts is wiped -- which cost step 3 six of ten passes. The database is made
# fresh between passes instead, by recycling the infra service.
CREATE = sql_to("CREATE TABLE IF NOT EXISTS customers (id varchar(10) PRIMARY KEY, country varchar(2), orders integer)")
# the example's own insert, verbatim
MERGE = sql_to("INSERT INTO customers (id, country, orders) VALUES (:#${body[customer]}, :#${body[country]}, 1) "
               "ON CONFLICT (id) DO UPDATE SET orders = customers.orders + 1", noop=True)
REGISTERED = log("Customer ${body[customer]} from ${body[country]} registered with order ${body[orderId]}")
REPORT = (sql_to("SELECT id, country, orders FROM customers ORDER BY id") + log("${body.size()} customer(s) in the table")
          + "        - split:\n            expression:\n              simple:\n                expression: \"${body}\"\n            steps:\n"
          + log("  ${body[id]} (${body[country]}): ${body[orders]} order(s)", indent="              "))
sql_s1 = route("create-table", TIMER_SETUP, CREATE + log("Table customers is ready"))
sql_s3 = sql_s1 + "\n" + route("register-customers", FILE_ORDERS_SQL, UNMARSHAL + MERGE + REGISTERED)
sql_s4 = sql_s3 + "\n" + route("customer-report", TIMER_REPORT, REPORT)
FIX_COUNTRY = route("fix-country", "      uri: timer\n      parameters:\n        timerName: fix\n        repeatCount: 1\n        delay: 4000\n",
                    sql_to("UPDATE customers SET country = 'NL' WHERE id = 'C-207'") + log("Fixed country of C-207"))
EXAMPLES.append({
    "name": "connect-service-sql", "route_file": SQL, "props_file": "application.properties", "wait_seconds": 16,
    "seed": "connect-service-sql", "infra": ["postgres"],
    "initial": {SQL: sql_s1, "application.properties": SQL_PROPS},
    "steps": [
        {"request": "Add a route register-customers that reads the JSON files in the orders directory (file endpoint with noop true, sortBy file:name and initialDelay 2000), unmarshals each with Jackson, and registers the customer in the customers table with the sql component using named parameters from the body: a new customer gets a row (id from body[customer], country from body[country], orders 1), a customer that already has a row gets orders + 1; the orders directory is read again every time the routes reload, so this must not fail on a duplicate key. Keep the order as the body (noop true) and log \"Customer ${body[customer]} from ${body[country]} registered with order ${body[orderId]}\".",
         "check": {"file_regex": "CONFLICT|MERGE", "log_regex": ["Customer C-482 from DK registered with order ORD-1001", "Customer C-134 from US registered with order ORD-1003"], "log_not_regex": "Syntax error|duplicate key value"},
         "reference": {SQL: sql_s3}},
        {"request": "Add a route customer-report from a timer (delay 5000, period 10000) that selects id, country and orders from customers ordered by id, logs \"${body.size()} customer(s) in the table\", and splits the list to log \"  ${body[id]} (${body[country]}): ${body[orders]} order(s)\" per row.",
         "check": {"file_regex": "split", "log_regex": ["3 customer\\(s\\) in the table", "C-482 \\(DK\\): \\d+ order\\(s\\)"]},
         "reference": {SQL: sql_s4}},
        {"request": "Customer C-207 lives in NL, not DE: correct that customer's row in the customers table so the next report line reads \"C-207 (NL)\". Leave the order file as it is.",
         "check": {"log_regex": "C-207 \\(NL\\): \\d+ order\\(s\\)", "files": {"orders/order-1002.json": "\"country\": \"DE\""}},
         "reference": {"fix-country.camel.yaml": FIX_COUNTRY}},
    ]})

# ================================================================ the six one-shot zero-pass examples, stepwise (2026-09-21)
# ---------------------------------------------------------------- transform/csv-to-json
CSV = "csv-to-json.camel.yaml"
FILE_INBOX_CSV = "      uri: file\n      parameters:\n        directoryName: inbox\n        noop: true\n        include: \".*\\\\.csv\"\n"
UNMARSHAL_CSV = "        - unmarshal:\n            csv:\n              useMaps: true\n              captureHeaderRecord: true\n"
def split_body(inner):
    return "        - split:\n            expression:\n              simple:\n                expression: \"${body}\"\n            steps:\n" + inner
I = "              "
CSV_HDR = I + "- setHeader:\n" + I + "    name: invoiceId\n" + I + "    expression:\n" + I + "      simple:\n" + I + "        expression: \"${body[invoiceId]}\"\n"
MARSHAL_JSON_IN = I + "- marshal:\n" + I + "    json:\n" + I + "      library: Jackson\n"
TO_OUTBOX = I + "- to:\n" + I + "    uri: file\n" + I + "    parameters:\n" + I + "      directoryName: outbox\n" + I + "      fileName: \"${header.invoiceId}.json\"\n"
csv_s1 = route("csv-to-json", FILE_INBOX_CSV, log("Invoices as text:\\n${body}"))
csv_s2 = route("csv-to-json", FILE_INBOX_CSV, UNMARSHAL_CSV + log("Invoices as a list of maps: ${body}"))
csv_s3 = route("csv-to-json", FILE_INBOX_CSV, UNMARSHAL_CSV + split_body(log("Invoice ${body[invoiceId]}: ${body}", I)))
csv_s4 = route("csv-to-json", FILE_INBOX_CSV, UNMARSHAL_CSV + split_body(CSV_HDR + MARSHAL_JSON_IN + log("Invoice ${header.invoiceId}: ${body}", I)))
csv_s5 = route("csv-to-json", FILE_INBOX_CSV, UNMARSHAL_CSV + split_body(CSV_HDR + MARSHAL_JSON_IN + log("Invoice ${header.invoiceId}: ${body}", I) + TO_OUTBOX))
EXAMPLES.append({
    "name": "transform-csv-to-json", "route_file": CSV, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-csv-to-json",
    "initial": {CSV: csv_s1, "application.properties": ""},
    "steps": [
        {"request": "Unmarshal the CSV with the csv data format so the body becomes a list of maps keyed by the header row (useMaps and captureHeaderRecord), and log \"Invoices as a list of maps: ${body}\".",
         "check": {"file_regex": "csv", "log_regex": "Invoices as a list of maps: \\[\\{invoiceId=INV-2001"},
         "reference": {CSV: csv_s2}},
        {"request": "Split the list over ${body} and inside the split log \"Invoice ${body[invoiceId]}: ${body}\" for each invoice.",
         "check": {"file_regex": "split", "log_regex": ["Invoice INV-2001: \\{invoiceId=INV-2001", "Invoice INV-2003: \\{invoiceId=INV-2003"]},
         "reference": {CSV: csv_s3}},
        {"request": "Inside the split, keep the invoice id in a header invoiceId, then marshal the invoice to JSON with Jackson and log \"Invoice ${header.invoiceId}: ${body}\" so each line shows the JSON.",
         "check": {"file_regex": "marshal", "log_regex": "Invoice INV-2002: \\{\"invoiceId\":\"INV-2002\",\"orderId\":\"ORD-1002\""},
         "reference": {CSV: csv_s4}},
        {"request": "Write each JSON invoice to the outbox directory as a file named after the invoice id, INV-2001.json and so on.",
         "check": {"file_regex": "outbox", "files": {"outbox/INV-2001.json": "\"invoiceId\":\"INV-2001\"", "outbox/INV-2003.json": "INV-2003"}, "log_regex": "Invoice INV-2003"},
         "reference": {CSV: csv_s5}},
    ]})

# ---------------------------------------------------------------- transform/data-mapping
DM = "data-mapping.camel.yaml"
TIMER_ONCE = "      uri: timer\n      parameters:\n        timerName: order\n        repeatCount: 1\n"
def set_body(kind, expr):
    return "        - setBody:\n            expression:\n              " + kind + ":\n                expression: " + expr + "\n"
BODY_ORDER = set_body("constant", "\"resource:file:order.json\"")
MARSHAL_JSON = "        - marshal:\n            json:\n              library: Jackson\n"
GROOVY_INLINE = "        - setBody:\n            expression:\n              groovy:\n                expression: \"[shipmentRef: body.orderId]\"\n"
GROOVY_FILE = set_body("groovy", "\"resource:file:shipment-mapping.groovy\"")
MAPPING_V1 = "def order = body\n[shipmentRef: order.orderId]\n"
MAPPING_V2 = """def order = body
[
    shipmentRef : order.orderId,
    recipient   : [customerNo: order.customer, countryCode: order.country],
    parcels     : order.lines.collect { line -> [article: line.sku, pieces: line.qty] },
    totalPieces : order.lines.sum { line -> line.qty }
]
"""
dm_s1 = route("data-mapping", TIMER_ONCE, BODY_ORDER + UNMARSHAL + log("Order ${body[orderId]} read"))
dm_s2 = route("data-mapping", TIMER_ONCE, BODY_ORDER + UNMARSHAL + GROOVY_INLINE + log("Shipment: ${body}"))
dm_s3 = route("data-mapping", TIMER_ONCE, BODY_ORDER + UNMARSHAL + GROOVY_FILE + log("Shipment: ${body}"))
dm_s5 = route("data-mapping", TIMER_ONCE, BODY_ORDER + UNMARSHAL + GROOVY_FILE + MARSHAL_JSON + log("Shipment for the courier: ${body}"))
EXAMPLES.append({
    "name": "transform-data-mapping", "route_file": DM, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-data-mapping",
    "initial": {DM: dm_s1, "application.properties": ""},
    "steps": [
        {"request": "After the unmarshal, set the body with an inline groovy expression that returns the map [shipmentRef: body.orderId], and log \"Shipment: ${body}\".",
         "check": {"file_regex": "groovy", "log_regex": "Shipment: \\{shipmentRef=ORD-1001\\}"},
         "reference": {DM: dm_s2}},
        {"request": "Move the groovy expression into a script file shipment-mapping.groovy next to the route (the last expression of the script is the new body) and load it from the route with resource:file:shipment-mapping.groovy.",
         "check": {"file_regex": "resource:(file|classpath):shipment-mapping\\.groovy", "files": {"shipment-mapping.groovy": "shipmentRef"}, "log_regex": "Shipment: \\{shipmentRef=ORD-1001\\}"},
         "reference": {DM: dm_s3, "shipment-mapping.groovy": MAPPING_V1}},
        {"request": "Grow the shipment map in the script: a recipient map with customerNo from the customer and countryCode from the country, parcels built from the lines with collect as maps of article (the sku) and pieces (the qty), and totalPieces as the sum of the qty over the lines.",
         "check": {"files": {"shipment-mapping.groovy": "collect"}, "log_regex": ["recipient=\\{customerNo=C-482, countryCode=DK\\}", "parcels=\\[\\{article=CAMEL-TSHIRT, pieces=2\\}, \\{article=CAMEL-MUG, pieces=1\\}\\]", "totalPieces=3"]},
         "reference": {"shipment-mapping.groovy": MAPPING_V2}},
        {"request": "Marshal the shipment map to JSON with Jackson and log it as \"Shipment for the courier: ${body}\".",
         "check": {"file_regex": "marshal", "log_regex": ["Shipment for the courier: \\{\"shipmentRef\":\"ORD-1001\"", "\"totalPieces\":3", "\"parcels\":\\[\\{\"article\":\"CAMEL-TSHIRT\",\"pieces\":2\\}"]},
         "reference": {DM: dm_s5}},
    ]})

# ---------------------------------------------------------------- transform/groovy
GR = "groovy.camel.yaml"
TIMER_ORDERS_ONCE = "      uri: timer\n      parameters:\n        timerName: orders\n        repeatCount: 1\n"
TIMER_ORDERS_TWICE = "      uri: timer\n      parameters:\n        timerName: orders\n        repeatCount: 2\n        includeMetadata: true\n"
BODY_ORDER_JSON = set_body("constant", "\"resource:file:order.json\"")
BODY_ORDER_PICK = set_body("simple", "\"resource:file:${exchangeProperty.CamelTimerCounter == 1 ? 'order.json' : 'order-bad-email.json'}\"")
def choice_groovy(expr_lines):
    return ("        - choice:\n            when:\n              - expression:\n                  groovy:\n                    expression: " + expr_lines + "\n"
            "                steps:\n                  - log:\n                      message: \"Order ${body[orderId]} accepted: ${body[email]} is a valid address\"\n"
            "            otherwise:\n              steps:\n                - log:\n                    message: \"Order ${body[orderId]} rejected: ${body[email]} is not an email address\"\n")
CHOICE_CONTAINS = choice_groovy("\"body.email.contains('@')\"")
CHOICE_VALIDATOR = choice_groovy("|-\n                      import org.apache.commons.validator.routines.EmailValidator\n                      EmailValidator.getInstance().isValid(body.email)")
GR_PROPS = "camel.jbang.dependencies=commons-validator:commons-validator:1.10.1\n"
gr_s1 = route("groovy", TIMER_ORDERS_ONCE, BODY_ORDER_JSON + UNMARSHAL + log("Order ${body[orderId]} from ${body[email]}"))
gr_s2 = route("groovy", TIMER_ORDERS_ONCE, BODY_ORDER_JSON + UNMARSHAL + CHOICE_CONTAINS)
gr_s3 = route("groovy", TIMER_ORDERS_ONCE, BODY_ORDER_JSON + UNMARSHAL + CHOICE_VALIDATOR)
gr_s4 = route("groovy", TIMER_ORDERS_TWICE, BODY_ORDER_PICK + UNMARSHAL + CHOICE_VALIDATOR)
EXAMPLES.append({
    "name": "transform-groovy", "route_file": GR, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "transform-groovy",
    "initial": {GR: gr_s1, "application.properties": ""},
    "steps": [
        {"request": "Replace the log by a choice: when a groovy expression body.email.contains('@') is true log \"Order ${body[orderId]} accepted: ${body[email]} is a valid address\", otherwise log \"Order ${body[orderId]} rejected: ${body[email]} is not an email address\".",
         "check": {"file_regex": "choice", "file_regex2": "groovy", "log_regex": "Order ORD-1001 accepted: anna@example.com is a valid address"},
         "reference": {GR: gr_s2}},
        {"request": "Check the address with Apache Commons Validator instead: the groovy expression imports org.apache.commons.validator.routines.EmailValidator and returns EmailValidator.getInstance().isValid(body.email); declare the library commons-validator:commons-validator:1.10.1 in application.properties with the camel.jbang.dependencies key so the Camel CLI downloads it. A new dependency needs a restart of the integration; it is restarted after your change.",
         "check": {"file_regex": "EmailValidator", "props_regex": "camel\\.jbang\\.dependencies\\s*=.*commons-validator:commons-validator:1\\.10\\.1", "log_regex": "Order ORD-1001 accepted: anna@example.com is a valid address"},
         "restart": True,
         "reference": {GR: gr_s3, "application.properties": GR_PROPS}},
        {"request": "Let the timer fire twice with includeMetadata true, and pick the file by the counter: order.json on the first fire and order-bad-email.json on the second (the exchange property CamelTimerCounter in a simple expression), so the second order is rejected.",
         "check": {"file_regex": "CamelTimerCounter", "log_regex": ["Order ORD-1001 accepted: anna@example.com is a valid address", "Order ORD-1002 rejected: not-an-address is not an email address"]},
         "reference": {GR: gr_s4}},
    ]})

# ---------------------------------------------------------------- route/aggregator
AG = "aggregator.camel.yaml"
AG_HDR = "        - setHeader:\n            name: orderId\n            expression:\n              simple:\n                expression: \"${body[orderId]}\"\n"
TO_SHIPMENT = I + "- to:\n" + I + "    uri: direct\n" + I + "    parameters:\n" + I + "      name: shipment\n"
DIRECT_SHIPMENT = "      uri: direct\n      parameters:\n        name: shipment\n"
def aggregate(completion, inner):
    return ("        - aggregate:\n            aggregationStrategy: \"#class:org.apache.camel.processor.aggregate.GroupedBodyAggregationStrategy\"\n"
            "            correlationExpression:\n              simple:\n                expression: \"${header.orderId}\"\n" + completion + "            steps:\n" + inner)
COMPLETION_SIZE = "            completionSize: 2\n"
COMPLETION_EXPR = "            completionSizeExpression:\n              simple:\n                expression: \"${header.CamelSplitSize}\"\n"
picked = route("picked-lines", FILE_ORDERS, UNMARSHAL + AG_HDR + split(log("Picked ${body[qty]} x ${body[sku]} for ${header.orderId}", I) + TO_SHIPMENT))
ag_s1 = route("picked-lines", FILE_ORDERS, UNMARSHAL + AG_HDR + split(log("Picked ${body[qty]} x ${body[sku]} for ${header.orderId}", I)))
ag_s2 = picked + route("aggregator", DIRECT_SHIPMENT, aggregate(COMPLETION_SIZE, log("Shipment for ${header.orderId} complete: ${body}", I)))
ag_s3 = picked + route("aggregator", DIRECT_SHIPMENT, aggregate(COMPLETION_EXPR, log("Shipment for ${header.orderId} complete: ${body}", I)))
ag_s4 = picked + route("aggregator", DIRECT_SHIPMENT, aggregate(COMPLETION_EXPR, MARSHAL_JSON_IN + log("Shipment for ${header.orderId} complete: ${body}", I)))
EXAMPLES.append({
    "name": "route-aggregator", "route_file": AG, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "route-aggregator",
    "initial": {AG: ag_s1, "application.properties": ""},
    "steps": [
        {"request": "After the log inside the split, send each picked line to direct:shipment, and add a route aggregator from direct:shipment with an aggregate that correlates on ${header.orderId}, completes at a fixed completionSize of 2, uses the aggregation strategy #class:org.apache.camel.processor.aggregate.GroupedBodyAggregationStrategy, and logs \"Shipment for ${header.orderId} complete: ${body}\" when a shipment completes.",
         "check": {"file_regex": "aggregate", "file_regex2": "GroupedBodyAggregationStrategy", "log_regex": "Shipment for ORD-1001 complete", "log_not_regex": "Shipment for ORD-1002 complete"},
         "reference": {AG: ag_s2}},
        {"request": "Replace the fixed completionSize by a completionSizeExpression that takes the number of lines of the order from the header CamelSplitSize, so every order completes with all its lines.",
         "check": {"file_regex": "completionSizeExpression", "log_regex": ["Shipment for ORD-1002 complete", "Shipment for ORD-1003 complete"]},
         "reference": {AG: ag_s3}},
        {"request": "Marshal the completed shipment to JSON with Jackson before the log so the log line shows the lines as JSON.",
         "check": {"file_regex": "marshal", "log_regex": "Shipment for ORD-1002 complete: \\[\\{\"sku\":\"CAMEL-MUG\",\"qty\":3"},
         "reference": {AG: ag_s4}},
    ]})

# ---------------------------------------------------------------- fail-well/error-handling
EH = "error-handling.camel.yaml"
CHECKOUT = route("checkout", FILE_ORDERS, UNMARSHAL + "        - to:\n            uri: direct:charge\n" + log("Payment for ${body[orderId]} charged, ${body[lines].size()} line(s) to the warehouse"))
def when_throw(cond, exc, msg):
    return ("              - expression:\n                  simple:\n                    expression: \"" + cond + "\"\n                steps:\n"
            "                  - throwException:\n                      exceptionType: " + exc + "\n                      message: \"" + msg + "\"\n")
DECLINED = when_throw("${body[orderId]} == 'ORD-1003'", "java.lang.IllegalStateException", "card declined")
FLAKY = when_throw("${body[orderId]} == 'ORD-1002' && ${header.CamelRedeliveryCounter} != 2", "java.net.ConnectException", "payment provider did not answer")
def provider(extra_when, no_eh):
    return ("- route:\n    id: payment-provider\n" + ("    errorHandler:\n      noErrorHandler: {}\n" if no_eh else "")
            + "    from:\n      uri: direct:charge\n      steps:\n        - choice:\n            when:\n" + extra_when)
DLC = ("- errorHandler:\n    deadLetterChannel:\n      deadLetterUri: direct:parked\n      redeliveryPolicy:\n        maximumRedeliveries: 2\n"
       "        redeliveryDelay: 1000\n        retryAttemptedLogLevel: WARN\n\n")
PARKED = route("parked", "      uri: direct:parked\n", log("Order ${body[orderId]} parked for manual review: ${exception.message}"))
ON_DECLINED = ("- onException:\n    exception:\n      - java.lang.IllegalStateException\n    redeliveryPolicy:\n      maximumRedeliveries: 0\n"
               "    handled:\n      constant:\n        expression: \"true\"\n    steps:\n      - log:\n          message: \"Payment for ${body[orderId]} declined: ${exception.message}\"\n"
               "      - to:\n          uri: direct:parked\n\n")
eh_s1 = CHECKOUT + "\n" + provider(DECLINED, False)
eh_s2 = DLC + CHECKOUT + "\n" + provider(DECLINED, False) + "\n" + PARKED
eh_s3 = DLC + CHECKOUT + "\n" + provider(FLAKY + DECLINED, True) + "\n" + PARKED
eh_s4 = DLC + ON_DECLINED + CHECKOUT + "\n" + provider(FLAKY + DECLINED, True) + "\n" + PARKED
EXAMPLES.append({
    "name": "fail-well-error-handling", "route_file": EH, "props_file": "application.properties", "wait_seconds": 12,
    "seed": "fail-well-error-handling",
    "initial": {EH: eh_s1, "application.properties": ""},
    "steps": [
        {"request": "Add a top-level errorHandler with a deadLetterChannel to direct:parked (maximumRedeliveries 2, redeliveryDelay 1000, retryAttemptedLogLevel WARN) and a route parked from direct:parked that logs \"Order ${body[orderId]} parked for manual review: ${exception.message}\", so the declined order is parked after the retries instead of dropped with a stack trace.",
         "check": {"file_regex": "deadLetterChannel", "log_regex": ["Order ORD-1003 parked for manual review: card declined", "Payment for ORD-1001 charged, 2 line\\(s\\)"], "errors_ok": True},
         "reference": {EH: eh_s2}},
        {"request": "Give the payment-provider route a noErrorHandler so its failures reach the caller, and make it throw a java.net.ConnectException \"payment provider did not answer\" for ORD-1002 unless the header CamelRedeliveryCounter is 2: the caller retries twice with a warning each time, then the order is charged.",
         "check": {"file_regex": "noErrorHandler", "file_regex2": "ConnectException", "log_regex": ["Payment for ORD-1002 charged, 1 line\\(s\\)", "Order ORD-1003 parked for manual review: card declined"], "errors_ok": True},
         "reference": {EH: eh_s3}},
        {"request": "A declined card is final: add a top-level onException for java.lang.IllegalStateException with maximumRedeliveries 0 and handled true that logs \"Payment for ${body[orderId]} declined: ${exception.message}\" and sends the order to direct:parked at once.",
         "check": {"file_regex": "onException", "log_regex": ["Payment for ORD-1003 declined: card declined", "Order ORD-1003 parked for manual review: card declined", "Payment for ORD-1002 charged"], "errors_ok": True},
         "reference": {EH: eh_s4}},
    ]})

# ---------------------------------------------------------------- connect/file-processing
FP = "file-processing.camel.yaml"
MONTH = datetime.date.today().strftime("%Y-%m")
COURIER = route("courier", "      uri: file\n      parameters:\n        directoryName: samples\n        noop: true\n        sortBy: \"file:name\"\n", "        - to:\n            uri: file\n            parameters:\n              directoryName: inbox\n")
def inbox(extra):
    return "      uri: file\n      parameters:\n        directoryName: inbox\n" + extra + "        sortBy: \"file:name\"\n"
INBOX_ALL = inbox("")
INBOX_JSON = inbox("        include: \".*\\\\.json\"\n        move: done\n")
INBOX_JSON_FAILED = inbox("        include: \".*\\\\.json\"\n        move: done\n        moveFailed: failed\n")
VALIDATE = "        - validate:\n            expression:\n              simple:\n                expression: \"${body[amount]} > 0\"\n"
INVOICE_LOG = log("Invoice ${body[invoiceId]} for ${body[orderId]}: ${body[amount]} EUR")
ARCHIVE_LOG = log("Invoice ${body[invoiceId]} for ${body[orderId]}: ${body[amount]} EUR, archived as ${date:now:yyyy-MM}/${file:name}")
TO_ARCHIVE = "        - to:\n            uri: file\n            parameters:\n              directoryName: archive\n              fileName: \"${date:now:yyyy-MM}/${file:name}\"\n"
ON_INVALID = ("- onException:\n    exception:\n      - org.apache.camel.support.processor.PredicateValidationException\n    redeliveryPolicy:\n      logStackTrace: false\n"
              "      logExhaustedMessageHistory: false\n    steps:\n      - log:\n          loggingLevel: WARN\n          message: \"Invoice ${file:name} rejected: ${exception.message}\"\n\n")
fp_s1 = COURIER + "\n" + route("invoices", INBOX_ALL, log("Received ${file:name}"))
fp_s2 = COURIER + "\n" + route("invoices", INBOX_JSON, log("Received ${file:name}"))
fp_s3 = COURIER + "\n" + route("invoices", INBOX_JSON, UNMARSHAL + INVOICE_LOG)
fp_s4 = ON_INVALID + COURIER + "\n" + route("invoices", INBOX_JSON_FAILED, UNMARSHAL + VALIDATE + INVOICE_LOG)
fp_s5 = ON_INVALID + COURIER + "\n" + route("invoices", INBOX_JSON_FAILED, UNMARSHAL + VALIDATE + ARCHIVE_LOG + MARSHAL_JSON + TO_ARCHIVE)
EXAMPLES.append({
    "name": "connect-file-processing", "route_file": FP, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "connect-file-processing",
    "initial": {FP: fp_s1, "application.properties": ""},
    "steps": [
        {"request": "The invoices route must only take the JSON files: include .*\\.json, and move each processed file to the done directory instead of the default .camel directory. The driver's note note-2005.txt must stay untouched in inbox.",
         "check": {"file_regex": "move: done", "file_regex2": "include", "log_regex": "Received invoice-2004.json", "log_not_regex": "Received note-2005", "files": {"inbox/note-2005.txt": "Handwritten note", "done/invoice-2001.json": "INV-2001"}},
         "reference": {FP: fp_s2}},
        {"request": "Unmarshal each invoice from JSON with Jackson and log \"Invoice ${body[invoiceId]} for ${body[orderId]}: ${body[amount]} EUR\" instead of the file name.",
         "check": {"file_regex": "unmarshal", "log_regex": ["Invoice INV-2001 for ORD-1001: 49.4 EUR", "Invoice INV-2003 for ORD-1003: -5.0 EUR"]},
         "reference": {FP: fp_s3}},
        {"request": "Reject a bad invoice: add a validate step with the simple predicate ${body[amount]} > 0 before the log, moveFailed failed so a rejected file goes to the failed directory, and a top-level onException for org.apache.camel.support.processor.PredicateValidationException whose redelivery policy has logStackTrace false and logExhaustedMessageHistory false and that logs at WARN \"Invoice ${file:name} rejected: ${exception.message}\".",
         "check": {"file_regex": "validate", "file_regex2": "moveFailed", "log_regex": "Invoice INV-2004 for ORD-1003: 53.45 EUR", "log_not_regex": "Invoice INV-2003 for", "files": {"failed/invoice-2003.json": "INV-2003"}, "errors_ok": True},
         "reference": {FP: fp_s4}},
        {"request": "Archive each valid invoice: after the validate, extend the log line with \", archived as ${date:now:yyyy-MM}/${file:name}\", marshal the invoice back to JSON with Jackson, and write it to the archive directory under a subdirectory of the current month with the original file name (fileName ${date:now:yyyy-MM}/${file:name}).",
         "check": {"file_regex": "archive", "log_regex": "Invoice INV-2001 for ORD-1001: 49.4 EUR, archived as \\d{4}-\\d{2}/invoice-2001.json", "files": {"archive/" + MONTH + "/invoice-2002.json": "INV-2002"}, "errors_ok": True},
         "reference": {FP: fp_s5}},
    ]})

# ================================================================ the HTTP rungs (CAMEL-24886), stepwise
PORT_PROPS = "camel.server.port=8080\n"
def const(expr):
    return "        - setBody:\n            expression:\n              constant:\n                expression: " + expr + "\n"
def set_header(name, kind, expr, ind="        "):
    return (ind + "- setHeader:\n" + ind + "    name: " + name + "\n" + ind + "    expression:\n" + ind + "      " + kind + ":\n"
            + ind + "        expression: " + expr + "\n")
CT_JSON = set_header("Content-Type", "constant", "application/json")
DIRECT = lambda n: "      uri: direct\n      parameters:\n        name: " + n + "\n"
GROOVY_SKU = ("        - unmarshal:\n            json:\n              library: Jackson\n"
              "        - setBody:\n            expression:\n              groovy:\n                expression: \"body.find { it.sku == headers.sku }\"\n")
NOT_FOUND = ("        - choice:\n            when:\n              - expression:\n                  simple:\n                    expression: \"${body} == null\"\n"
             "                steps:\n" + set_header("CamelHttpResponseCode", "constant", "\"404\"", "                  ")
             + "                  - setBody:\n                      expression:\n                        simple:\n                          expression: '{\"error\": \"unknown sku ${header.sku}\"}'\n"
             "            otherwise:\n              steps:\n"
             "                - marshal:\n                    json:\n                      library: Jackson\n")
FIRST_ITEM = ("        - marshal:\n            json:\n              library: Jackson\n")

# ---------------------------------------------------------------- connect/stock-api (a server: the checks are the README's curl)
SA = "stock-api.camel.yaml"
REST_ALL = "- rest:\n    path: /stock\n    get:\n      - to:\n          uri: direct:all-stock\n"
REST_BOTH = "- rest:\n    path: /stock\n    get:\n      - to:\n          uri: direct:all-stock\n      - path: \"/{sku}\"\n        to:\n          uri: direct:one-sku\n"
ALL_STOCK = route("all-stock", DIRECT("all-stock"), const("resource:file:stock.json") + CT_JSON)
sa_s1 = REST_ALL + "\n" + ALL_STOCK
sa_s2 = REST_BOTH + "\n" + ALL_STOCK + "\n" + route("one-sku", DIRECT("one-sku"), log("Stock asked for ${header.sku}") + const("resource:file:stock.json") + CT_JSON)
sa_s3 = REST_BOTH + "\n" + ALL_STOCK + "\n" + route("one-sku", DIRECT("one-sku"), log("Stock asked for ${header.sku}") + const("resource:file:stock.json") + GROOVY_SKU + FIRST_ITEM + CT_JSON)
sa_s4 = REST_BOTH + "\n" + ALL_STOCK + "\n" + route("one-sku", DIRECT("one-sku"), log("Stock asked for ${header.sku}") + const("resource:file:stock.json") + GROOVY_SKU + NOT_FOUND + CT_JSON)
GET = lambda path, status=200, rx=None: {"method": "GET", "url": "http://localhost:8080" + path, "expect_status": status, **({"body_regex": rx} if rx else {})}
EXAMPLES.append({
    "name": "connect-stock-api", "route_file": SA, "props_file": "application.properties", "wait_seconds": 4,
    "seed": "connect-stock-api",
    "initial": {SA: sa_s1, "application.properties": PORT_PROPS},
    "steps": [
        {"request": "Add a second operation to the rest: GET /stock/{sku}, routed to direct:one-sku, and a route one-sku that logs \"Stock asked for ${header.sku}\" (the path parameter arrives as a header) and for now answers with the whole stock file like all-stock does.",
         "check": {"file_regex": "\\{sku\\}", "log_regex": "Stock asked for CAMEL-MUG", "probes": [GET("/stock/CAMEL-MUG", 200, "CAMEL-MUG")]},
         "reference": {SA: sa_s2}},
        {"request": "In one-sku, keep loading the stock file into the body as now, then unmarshal the body with Jackson and pick the SKU with the Groovy expression body.find { it.sku == headers.sku } (the item as a map, or null), answer with the item marshalled to JSON with Jackson, Content-Type application/json.",
         "check": {"file_regex": "groovy", "probes": [GET("/stock/CAMEL-MUG", 200, "\"sku\":\"CAMEL-MUG\",\"qty\":42")]},
         "reference": {SA: sa_s3}},
        {"request": "When the SKU is unknown (the Groovy expression gives null) answer with HTTP status 404 (the header CamelHttpResponseCode) and the body {\"error\": \"unknown sku ${header.sku}\"}; a known SKU still answers as before.",
         "check": {"file_regex": "404", "probes": [GET("/stock/CAMEL-SOCKS", 404, "unknown sku CAMEL-SOCKS"), GET("/stock/CAMEL-MUG", 200, "\"qty\":42")]},
         "reference": {SA: sa_s4}},
    ]})

# ---------------------------------------------------------------- connect/http-client (the stock service is in the same app)
HC = "http-client.camel.yaml"
REST_ONE = "- rest:\n    path: /stock\n    get:\n      - path: \"/{sku}\"\n        to:\n          uri: direct:one-sku\n"
STOCK_SERVICE = route("stock-service", DIRECT("one-sku"), const("resource:file:stock.json") + GROOVY_SKU + NOT_FOUND + CT_JSON)
SERVER = REST_ONE + "\n" + STOCK_SERVICE + "\n"
def set_var(name, expr, ind="        "):
    return ind + "- setVariable:\n" + ind + "    name: " + name + "\n" + ind + "    expression:\n" + ind + "      simple:\n" + ind + "        expression: \"" + expr + "\"\n"
NULL_BODY = I + "- setBody:\n" + I + "    expression:\n" + I + "      simple:\n" + I + "        expression: \"${null}\"\n"
UNMARSHAL_IN = I + "- unmarshal:\n" + I + "    json:\n" + I + "      library: Jackson\n"
TO_FIXED = I + "- to:\n" + I + "    uri: \"http://localhost:8080/stock/CAMEL-MUG\"\n"
TOD_SKU = I + "- toD:\n" + I + "    uri: \"http://localhost:8080/stock/${variable.sku}\"\n"
TOD_SKU_NOFAIL = I + "- toD:\n" + I + "    uri: \"http://localhost:8080/stock/${variable.sku}?throwExceptionOnFailure=false\"\n"
PROPS_LINE = set_var("sku", "${body[sku]}", I) + set_var("needed", "${body[qty]}", I)
STOCK_CHOICE = (I + "- choice:\n" + I + "    when:\n" + I + "      - expression:\n" + I + "          simple:\n" + I + "            expression: \"${header.CamelHttpResponseCode} != 200\"\n"
                + I + "        steps:\n" + log("${variable.orderId}: ${body[error]} (HTTP ${header.CamelHttpResponseCode})", I + "          ")
                + I + "      - expression:\n" + I + "          simple:\n" + I + "            expression: \"${body[qty]} >= ${variable.needed}\"\n"
                + I + "        steps:\n" + log("${variable.orderId}: ${variable.sku} x ${variable.needed}, ${body[qty]} in stock, ok", I + "          ")
                + I + "    otherwise:\n" + I + "      steps:\n" + log("${variable.orderId}: ${variable.sku} x ${variable.needed}, only ${body[qty]} in stock, back-order", I + "        "))
hc_s1 = SERVER + route("check-stock", FILE_ORDERS, UNMARSHAL + log("Order ${body[orderId]} with ${body[lines].size()} line(s)"))
hc_s2 = SERVER + route("check-stock", FILE_ORDERS, UNMARSHAL + split(NULL_BODY + TO_FIXED + log("Stock answer: ${body}", I)))
hc_s3 = SERVER + route("check-stock", FILE_ORDERS, UNMARSHAL + set_var("orderId", "${body[orderId]}") + split(PROPS_LINE + NULL_BODY + TOD_SKU + UNMARSHAL_IN + log("${variable.orderId}: ${variable.sku} x ${variable.needed}, ${body[qty]} in stock", I)))
hc_s4 = SERVER + route("check-stock", FILE_ORDERS, UNMARSHAL + set_var("orderId", "${body[orderId]}") + split(PROPS_LINE + NULL_BODY + TOD_SKU_NOFAIL + UNMARSHAL_IN + STOCK_CHOICE))
EXAMPLES.append({
    "name": "connect-http-client", "route_file": HC, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "connect-http-client",
    "initial": {HC: hc_s1, "application.properties": PORT_PROPS},
    "steps": [
        {"request": "Split the order over its lines (${body[lines]}) and for each line call the stock service over HTTP with a GET on http://localhost:8080/stock/CAMEL-MUG (a fixed SKU for now; set the body to null first, a GET sends no body) and log the response as \"Stock answer: ${body}\".",
         "check": {"file_regex": "http://localhost:8080/stock", "log_regex": "Stock answer: \\{\"sku\":\"CAMEL-MUG\",\"qty\":42\\}"},
         "reference": {HC: hc_s2}},
        {"request": "Call the stock service for the line's own SKU: keep the order id, the line's sku and its qty in variables orderId, sku and needed before the call (headers would travel on the HTTP request), build the URI per line with toD as http://localhost:8080/stock/${variable.sku}, unmarshal the JSON answer and log \"${variable.orderId}: ${variable.sku} x ${variable.needed}, ${body[qty]} in stock\".",
         "check": {"file_regex": "toD", "log_regex": ["ORD-1001: CAMEL-TSHIRT x 2, 120 in stock", "ORD-1003: CAMEL-CAP x 1, 0 in stock"]},
         "reference": {HC: hc_s3}},
        {"request": "Decide per line: add throwExceptionOnFailure=false to the HTTP call so a 404 does not throw, then a choice: when the header CamelHttpResponseCode is not 200 log \"${variable.orderId}: ${body[error]} (HTTP ${header.CamelHttpResponseCode})\", when ${body[qty]} >= ${variable.needed} log \"${variable.orderId}: ${variable.sku} x ${variable.needed}, ${body[qty]} in stock, ok\", otherwise log \"${variable.orderId}: ${variable.sku} x ${variable.needed}, only ${body[qty]} in stock, back-order\".",
         "check": {"file_regex": "throwExceptionOnFailure[=:] *false", "log_regex": ["ORD-1001: CAMEL-TSHIRT x 2, 120 in stock, ok", "ORD-1003: CAMEL-CAP x 1, only 0 in stock, back-order"]},
         "reference": {HC: hc_s4}},
    ]})

# ---------------------------------------------------------------- contracts/openapi-server (contract first; the checks are the README's curl)
OS = "openapi-server.camel.yaml"
import copy
FULL_CONTRACT = json.load(open(os.path.join(SEEDS, "_peer-openapi-server", "stock-api.json")))
def contract(paths):
    c = copy.deepcopy(FULL_CONTRACT)
    c["paths"] = {k: v for k, v in c["paths"].items() if k in paths}
    return json.dumps(c, indent=2) + "\n"
CONTRACT_V1 = contract(["/stock"])
CONTRACT_V2 = contract(["/stock", "/stock/{sku}"])
CONTRACT_V3 = contract(["/stock", "/stock/{sku}", "/stock/{sku}/reserve"])
REST_OPENAPI = "- restConfiguration:\n    apiContextPath: openapi\n\n- rest:\n    openApi:\n      specification: stock-api.json\n\n"
REST_OPENAPI_VALIDATED = "- restConfiguration:\n    clientRequestValidation: true\n    apiContextPath: openapi\n\n- rest:\n    openApi:\n      specification: stock-api.json\n\n"
LIST_STOCK = route("listStock", DIRECT("listStock"), const("resource:file:stock.json"))
LOOKUP = route("lookup", DIRECT("lookup"), const("resource:file:stock.json") + GROOVY_SKU)
NULL_404 = ("        - choice:\n            when:\n              - expression:\n                  simple:\n                    expression: \"${body} == null\"\n"
            "                steps:\n" + set_header("CamelHttpResponseCode", "constant", "\"404\"", "                  ")
            + "                  - setBody:\n                      expression:\n                        simple:\n                          expression: '{\"error\": \"unknown sku ${header.sku}\"}'\n"
            "            otherwise:\n              steps:\n                - marshal:\n                    json:\n                      library: Jackson\n")
GET_STOCK = route("getStock", DIRECT("getStock"), "        - to:\n            uri: direct:lookup\n" + NULL_404)
RESERVE_BODY = ("        - setBody:\n            expression:\n              simple:\n                expression: '{\"sku\": \"${header.sku}\", \"reserved\": ${variable.reservation[qty]}, \"remaining\": ${body[qty]}}'\n")
def reserve_route(validate, conflict):
    steps = UNMARSHAL
    if validate:
        steps += "        - validate:\n            expression:\n              simple:\n                expression: \"${body[orderId]} != null && ${body[qty]} > 0\"\n"
    steps += set_var("reservation", "${body}") + "        - to:\n            uri: direct:lookup\n"
    steps += ("        - choice:\n            when:\n              - expression:\n                  simple:\n                    expression: \"${body} == null\"\n"
              "                steps:\n" + set_header("CamelHttpResponseCode", "constant", "\"404\"", "                  ")
              + "                  - setBody:\n                      expression:\n                        simple:\n                          expression: '{\"error\": \"unknown sku ${header.sku}\"}'\n")
    if conflict:
        steps += ("              - expression:\n                  simple:\n                    expression: \"${body[qty]} < ${variable.reservation[qty]}\"\n"
                  "                steps:\n" + set_header("CamelHttpResponseCode", "constant", "\"409\"", "                  ")
                  + "                  - setBody:\n                      expression:\n                        simple:\n                          expression: '{\"error\": \"only ${body[qty]} ${header.sku} in stock, ${variable.reservation[qty]} wanted for ${variable.reservation[orderId]}\"}'\n")
    steps += ("            otherwise:\n              steps:\n" + log("Reserved ${variable.reservation[qty]} x ${header.sku} for ${variable.reservation[orderId]}", "                ")
              + "                - setBody:\n                    expression:\n                      simple:\n                        expression: '{\"sku\": \"${header.sku}\", \"reserved\": ${variable.reservation[qty]}, \"remaining\": ${body[qty]}}'\n")
    return route("reserveStock", DIRECT("reserveStock"), steps)
ON_INVALID_400 = ("- onException:\n    exception:\n      - org.apache.camel.support.processor.PredicateValidationException\n    handled:\n      constant:\n        expression: \"true\"\n"
                  "    steps:\n" + set_header("CamelHttpResponseCode", "constant", "\"400\"", "      ")
                  + "      - setBody:\n          expression:\n            simple:\n              expression: '{\"error\": \"orderId and a positive qty are required\"}'\n\n")
os_s1 = REST_OPENAPI + LIST_STOCK
os_s2 = REST_OPENAPI + LIST_STOCK + "\n" + GET_STOCK + "\n" + LOOKUP
os_s3 = REST_OPENAPI + LIST_STOCK + "\n" + GET_STOCK + "\n" + reserve_route(False, False) + "\n" + LOOKUP
os_s4 = REST_OPENAPI_VALIDATED + ON_INVALID_400 + LIST_STOCK + "\n" + GET_STOCK + "\n" + reserve_route(True, False) + "\n" + LOOKUP
os_s5 = REST_OPENAPI_VALIDATED + ON_INVALID_400 + LIST_STOCK + "\n" + GET_STOCK + "\n" + reserve_route(True, True) + "\n" + LOOKUP
JSON_HDR = {"Content-Type": "application/json"}
POST = lambda path, body, status, rx=None: {"method": "POST", "url": "http://localhost:8080" + path, "headers": JSON_HDR, "expect_status": status, **({"body": body} if body is not None else {}), **({"body_regex": rx} if rx else {})}
EXAMPLES.append({
    "name": "contracts-openapi-server", "route_file": OS, "props_file": "application.properties", "wait_seconds": 4,
    "seed": "contracts-openapi-server",
    "initial": {OS: os_s1, "stock-api.json": CONTRACT_V1, "application.properties": PORT_PROPS},
    "steps": [
        {"request": "Add the operation getStock to the contract stock-api.json: GET /stock/{sku} with the path parameter sku, a 200 answering a StockItem and a 404 answering an Error. Then the route getStock (rest-openapi routes each operation to direct:<operationId>): it calls a helper route lookup that sets the body to the stock file (resource:file:stock.json, as listStock does), unmarshals the body with Jackson and picks the SKU with the Groovy expression body.find { it.sku == headers.sku }, which leaves the item as the body, or null; getStock answers the item marshalled to JSON, or a 404 (header CamelHttpResponseCode) with {\"error\": \"unknown sku ${header.sku}\"}.",
         "check": {"file_regex": "getStock", "files": {"stock-api.json": "\"operationId\": \"getStock\""}, "probes": [GET("/api/stock/CAMEL-MUG", 200, "\"sku\":\"CAMEL-MUG\",\"qty\":42"), GET("/api/stock/CAMEL-SOCKS", 404, "unknown sku CAMEL-SOCKS")]},
         "reference": {OS: os_s2, "stock-api.json": CONTRACT_V2}},
        {"request": "Add the operation reserveStock to the contract: POST /stock/{sku}/reserve with a JSON request body Reservation (orderId string, qty integer, both required), a 200 answering a ReservationResult (sku, reserved, remaining), and a 404. Then the route reserveStock: unmarshal the body with Jackson, keep it in a variable reservation, call direct:lookup, answer 404 for an unknown SKU as getStock does, otherwise log \"Reserved ${variable.reservation[qty]} x ${header.sku} for ${variable.reservation[orderId]}\" and answer the JSON {\"sku\": \"${header.sku}\", \"reserved\": ${variable.reservation[qty]}, \"remaining\": ${body[qty]}}.",
         "check": {"file_regex": "reserveStock", "files": {"stock-api.json": "\"operationId\": \"reserveStock\""}, "log_regex": "Reserved 2 x CAMEL-MUG for ORD-1001", "probes": [POST("/api/stock/CAMEL-MUG/reserve", '{"orderId": "ORD-1001", "qty": 2}', 200, "\"reserved\": 2")]},
         "reference": {OS: os_s3, "stock-api.json": CONTRACT_V3}},
        {"request": "Turn on the contract check: clientRequestValidation true in the restConfiguration, so a POST without a body or with the wrong content type gets a 400 from the contract. In reserveStock add a validate step with the simple predicate ${body[orderId]} != null && ${body[qty]} > 0 right after the unmarshal, and a top-level onException for org.apache.camel.support.processor.PredicateValidationException, handled, that answers 400 (CamelHttpResponseCode) with {\"error\": \"orderId and a positive qty are required\"}.",
         "check": {"file_regex": "clientRequestValidation", "file_regex2": "PredicateValidationException", "probes": [POST("/api/stock/CAMEL-MUG/reserve", None, 400), POST("/api/stock/CAMEL-MUG/reserve", '{"orderId": "ORD-1001", "qty": 0}', 400, "positive qty"), POST("/api/stock/CAMEL-MUG/reserve", '{"orderId": "ORD-1001", "qty": 2}', 200, "\"reserved\": 2")], "errors_ok": True},
         "reference": {OS: os_s4}},
        {"request": "Short stock is a conflict: in reserveStock, when the stock's ${body[qty]} is less than ${variable.reservation[qty]} answer 409 with {\"error\": \"only ${body[qty]} ${header.sku} in stock, ${variable.reservation[qty]} wanted for ${variable.reservation[orderId]}\"}.",
         "check": {"file_regex": "409", "probes": [POST("/api/stock/CAMEL-CAP/reserve", '{"orderId": "ORD-1003", "qty": 1}', 409, "only 0 CAMEL-CAP in stock, 1 wanted for ORD-1003"), POST("/api/stock/CAMEL-MUG/reserve", '{"orderId": "ORD-1001", "qty": 2}', 200)], "errors_ok": True},
         "reference": {OS: os_s5}},
    ]})

# ---------------------------------------------------------------- contracts/openapi-client (the openapi-server reference runs next to it as the peer)
OC = "openapi-client.camel.yaml"
OC_PROPS = "stock.api.url=http://localhost:8080\n"
TIMER_ONE = "      uri: timer\n      parameters:\n        timerName: stock\n        repeatCount: 1\n"
def rest_openapi(op, ind="        "):
    return (ind + "- to:\n" + ind + "    uri: rest-openapi\n" + ind + "    parameters:\n" + ind + "      specificationUri: stock-api.json\n"
            + ind + "      operationId: " + op + "\n" + ind + "      host: \"{{stock.api.url}}\"\n" + ind + "      componentName: http\n")
oc_s1 = route("stock-check", TIMER_ONE, set_header("sku", "constant", "CAMEL-MUG") + rest_openapi("getStock") + log("Stock of CAMEL-MUG: ${body}"))
SKU_HDR_LINE = set_header("sku", "simple", "\"${body[sku]}\"", I)
RESERVE_BODY_LINE = I + "- setBody:\n" + I + "    expression:\n" + I + "      simple:\n" + I + "        expression: '{\"orderId\": \"${variable.orderId}\", \"qty\": ${body[qty]}}'\n"
oc_s2 = route("reserve-order-lines", FILE_ORDERS, UNMARSHAL + set_var("orderId", "${body[orderId]}") + split(SKU_HDR_LINE + RESERVE_BODY_LINE + rest_openapi("reserveStock", I) + log("Reservation answer: ${body}", I)))
oc_s3 = route("reserve-order-lines", FILE_ORDERS, UNMARSHAL + set_var("orderId", "${body[orderId]}") + split(set_var("sku", "${body[sku]}", I) + SKU_HDR_LINE + RESERVE_BODY_LINE + rest_openapi("reserveStock", I) + UNMARSHAL_IN + log("${variable.orderId}: reserved ${body[reserved]} x ${body[sku]}, ${body[remaining]} left on the shelf", I)))
ON_409 = ("- onException:\n    exception:\n      - org.apache.camel.http.base.HttpOperationFailedException\n    handled:\n      constant:\n        expression: \"true\"\n"
          "    steps:\n      - log:\n          loggingLevel: WARN\n          message: \"${variable.orderId}: ${variable.sku} not reserved, the stock API answered ${exception.statusCode}: ${exception.responseBody}\"\n\n")
oc_s4 = ON_409 + oc_s3
EXAMPLES.append({
    "name": "contracts-openapi-client", "route_file": OC, "props_file": "application.properties", "wait_seconds": 8,
    "seed": "contracts-openapi-client",
    "peer": {"seed": "_peer-openapi-server", "project": "stepwise-ladder/_peer-openapi-server", "name": "stock-api-peer"},
    "initial": {OC: oc_s1, "application.properties": OC_PROPS},
    "steps": [
        {"request": "Replace the timer route by a route reserve-order-lines that reads the orders directory (file, noop true, sortBy file:name), unmarshals each order with Jackson, keeps the order id in a variable orderId, splits the lines and for each line calls the operation reserveStock of the contract (rest-openapi, specificationUri stock-api.json, host {{stock.api.url}}, componentName http) with the header sku from the line (the path parameter) and the body {\"orderId\": \"${variable.orderId}\", \"qty\": ${body[qty]}}; log the answer as \"Reservation answer: ${body}\". The cap is out of stock, so one call fails with a 409 for now.",
         "check": {"file_regex": "reserveStock", "file_regex2": "orders", "log_regex": "Reservation answer: \\{\"sku\": \"CAMEL-TSHIRT\", \"reserved\": 2, \"remaining\": 120\\}", "errors_ok": True},
         "reference": {OC: oc_s2}},
        {"request": "Keep the line's sku in a variable sku as well, unmarshal the JSON answer and log \"${variable.orderId}: reserved ${body[reserved]} x ${body[sku]}, ${body[remaining]} left on the shelf\".",
         "check": {"log_regex": ["ORD-1001: reserved 2 x CAMEL-TSHIRT, 120 left on the shelf", "ORD-1002: reserved 3 x CAMEL-MUG, 42 left on the shelf"], "errors_ok": True},
         "reference": {OC: oc_s3}},
        {"request": "Handle the conflict: add a top-level onException for org.apache.camel.http.base.HttpOperationFailedException, handled true, that logs at WARN \"${variable.orderId}: ${variable.sku} not reserved, the stock API answered ${exception.statusCode}: ${exception.responseBody}\", so the cap's 409 is a warning and the rest of the order goes on.",
         "check": {"file_regex": "HttpOperationFailedException", "log_regex": ["ORD-1003: CAMEL-CAP not reserved, the stock API answered 409", "ORD-1003: reserved 2 x CAMEL-MUG, 42 left on the shelf"], "errors_ok": True},
         "reference": {OC: oc_s4}},
    ]})


def write_project(ex):
    d = os.path.join(PROJECTS, ex["name"])
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if ex.get("seed"):
        src = os.path.join(SEEDS, ex["seed"])
        for item in os.listdir(src):
            if item in ex.get("exclude_seeds", []):
                continue
            s = os.path.join(src, item)
            (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, os.path.join(d, item))
    for name, content in ex["initial"].items():
        os.makedirs(os.path.dirname(os.path.join(d, name)) or d, exist_ok=True)
        with open(os.path.join(d, name), "w") as f:
            f.write(content)


def main():
    os.makedirs(STEPS_DIR, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for ex in EXAMPLES:
        if only and ex["name"] != only:
            continue
        steps = []
        for i, s in enumerate(ex["steps"], 1):
            steps.append({"id": i, "request": s["request"], "check": s["check"], "reference": s["reference"], **({"restart": True} if s.get("restart") else {})})
        cfg = {"project": "stepwise-ladder/" + ex["name"], "route_file": ex["route_file"], "props_file": ex["props_file"],
               "wait_seconds": ex["wait_seconds"], "source_dir": True, "seed": ex.get("seed"), "exclude_seeds": ex.get("exclude_seeds", []),
               "initial": ex["initial"], "steps": steps}
        if ex.get("infra"):
            # services the example needs, started with `camel infra run` before the app (the sql example's postgres)
            cfg["infra"] = ex["infra"]
        if ex.get("peer"):
            cfg["peer"] = {"project": ex["peer"]["project"], "name": ex["peer"]["name"]}
            pd = os.path.join(HERE, ex["peer"]["project"])
            shutil.rmtree(pd, ignore_errors=True)
            shutil.copytree(os.path.join(SEEDS, ex["peer"]["seed"]), pd)
        with open(os.path.join(STEPS_DIR, ex["name"] + ".json"), "w") as f:
            json.dump(cfg, f, indent=1)
        write_project(ex)
        print(f"{ex['name']}: {len(steps)} steps, project stepwise-ladder/{ex['name']}")


if __name__ == "__main__":
    main()
