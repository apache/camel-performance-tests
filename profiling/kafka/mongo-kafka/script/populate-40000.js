use test
db.createCollection("log", { capped : true, size : 5242880, max : 50000 } )
for (var i = 1; i <= 40000; i++) {
   db.log.insert({ item: "canvas", qty: 100, tags: ["cotton"], size: { h: 28, w: i, uom: "cm" } })
}
