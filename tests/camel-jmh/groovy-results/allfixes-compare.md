# All fixes vs main (JDK 21)

## GroovyExpressionTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `arithmeticGroovy` |  | thrpt | ops/s | 3,656,819 ± 86,337 | 27,984,212 ± 1,099,819 | 7.65× | 1,336 | 184 |
| `arithmeticJactl` |  | thrpt | ops/s | 86,218,393 ± 634,674 | 69,162,969 ± 195,635 | 0.80× | 56 | 56 |
| `arithmeticJavaExpression` |  | thrpt | ops/s | 434,267,392 ± 3,237,999 | 432,651,097 ± 2,831,470 | 1.00× | 0 | 0 |
| `arithmeticJavaLanguage` |  | thrpt | ops/s | 363,446,576 ± 1,332,548 | 376,580,728 ± 703,783 | 1.04× | 0 | 0 |
| `arithmeticJs` |  | thrpt | ops/s | 3,126 ± 152 | 5,621 ± 295 | 1.80× | 851,931 | 143,100 |
| `arithmeticMvel` |  | thrpt | ops/s | 54,211,377 ± 482,690 | 58,676,232 ± 1,141,014 | 1.08× | 32 | 32 |
| `arithmeticPython3` |  | thrpt | ops/s | 106 ± 7 | 112 ± 5 | 1.05× | 5,225,907 | 5,226,737 |
| `arithmeticSimple` |  | thrpt | ops/s | 2,916,484 ± 40,484 | 3,176,100 ± 324,368 | 1.09× | 1,676 | 1,640 |
| `concatGroovy` |  | thrpt | ops/s | 3,001,362 ± 33,509 | 14,773,683 ± 349,838 | 4.92× | 1,568 | 288 |
| `concatJactl` |  | thrpt | ops/s | 35,389,546 ± 259,800 | 31,465,051 ± 161,224 | 0.89× | 136 | 136 |
| `concatJavaExpression` |  | thrpt | ops/s | 47,780,724 ± 536,770 | 47,117,559 ± 234,725 | 0.99× | 56 | 56 |
| `concatJavaLanguage` |  | thrpt | ops/s | 44,348,419 ± 317,402 | 47,852,995 ± 1,316,020 | 1.08× | 56 | 56 |
| `concatJavaProcessor` |  | thrpt | ops/s | 43,844,347 ± 231,094 | 44,402,625 ± 984,143 | 1.01× | 56 | 56 |
| `concatJs` |  | thrpt | ops/s | 3,120 ± 116 | 5,626 ± 258 | 1.80× | 862,843 | 143,657 |
| `concatMvel` |  | thrpt | ops/s | 19,034,062 ± 184,871 | 19,424,265 ± 83,733 | 1.02× | 248 | 248 |
| `concatPython3` |  | thrpt | ops/s | 115 ± 7 | 111 ± 4 | 0.96× | 5,499,461 | 5,496,206 |
| `concatSimple` |  | thrpt | ops/s | 13,086,610 ± 167,523 | 13,093,707 ± 307,700 | 1.00× | 352 | 352 |
| `predicateGroovy` |  | thrpt | ops/s | 3,623,062 ± 23,970 | 25,315,455 ± 113,089 | 6.99× | 1,344 | 160 |
| `predicateJactl` |  | thrpt | ops/s | 73,565,987 ± 421,084 | 59,613,860 ± 435,935 | 0.81× | 56 | 56 |
| `predicateJava` |  | thrpt | ops/s | 279,871,699 ± 1,714,108 | 273,374,192 ± 10,889,207 | 0.98× | 0 | 0 |
| `predicateJavaLanguage` |  | thrpt | ops/s | 247,313,303 ± 1,487,478 | 241,371,744 ± 835,454 | 0.98× | 0 | 0 |
| `predicateJs` |  | thrpt | ops/s | 3,176 ± 91 | 5,570 ± 277 | 1.75× | 859,438 | 143,324 |
| `predicateMvel` |  | thrpt | ops/s | 65,026,418 ± 889,865 | 70,717,774 ± 942,999 | 1.09× | 32 | 32 |
| `predicatePython3` |  | thrpt | ops/s | 118 ± 7 | 111 ± 5 | 0.94× | 5,494,383 | 5,496,490 |
| `predicateSimple` |  | thrpt | ops/s | 31,089,329 ± 197,310 | 30,952,680 ± 59,952 | 1.00× | 0 | 0 |

## GroovyCollectionTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `groovyCompileStatic` | size=10 | thrpt | ops/s | 1,513,159 ± 22,879 | 2,621,041 ± 12,664 | 1.73× | 3,024 | 1,360 |
| `groovyCompileStatic` | size=1000 | thrpt | ops/s | 17,196 ± 360 | 16,716 ± 162 | 0.97× | 74,305 | 72,657 |
| `groovyDynamic` | size=10 | thrpt | ops/s | 1,722,843 ± 10,232 | 2,206,871 ± 191,285 | 1.28× | 2,528 | 1,336 |
| `groovyDynamic` | size=1000 | thrpt | ops/s | 16,831 ± 535 | 16,219 ± 271 | 0.96× | 73,849 | 72,625 |
| `jactlHostAccess` | size=10 | thrpt | ops/s | 11,389,269 ± 191,643 | 9,164,012 ± 1,389,378 | 0.80× | 72 | 96 |
| `jactlHostAccess` | size=1000 | thrpt | ops/s | 158,808 ± 1,715 | 180,977 ± 141 | 1.14× | 96 | 96 |
| `javaLanguage` | size=10 | thrpt | ops/s | 12,489,977 ± 86,006 | 10,835,523 ± 724,432 | 0.87× | 112 | 112 |
| `javaLanguage` | size=1000 | thrpt | ops/s | 218,515 ± 2,716 | 178,858 ± 684 | 0.82× | 160 | 112 |
| `javaStreams` | size=10 | thrpt | ops/s | 11,709,817 ± 1,365,752 | 11,095,333 ± 98,677 | 0.95× | 112 | 112 |
| `javaStreams` | size=1000 | thrpt | ops/s | 184,777 ± 54,517 | 160,899 ± 508 | 0.87× | 160 | 136 |
| `js` | size=10 | thrpt | ops/s | 3,042 ± 96 | 5,640 ± 303 | 1.85× | 877,118 | 151,058 |
| `js` | size=1000 | thrpt | ops/s | 1,417 ± 38 | 2,012 ± 27 | 1.42× | 1,479,511 | 753,900 |
| `mvel` | size=10 | thrpt | ops/s | 6,190,678 ± 53,426 | 5,192,363 ± 18,985 | 0.84× | 376 | 376 |
| `mvel` | size=1000 | thrpt | ops/s | 85,307 ± 770 | 85,026 ± 2,289 | 1.00× | 4,336 | 4,336 |
| `precompiledDynamicBean` | size=10 | thrpt | ops/s | 2,100,661 ± 21,981 | 2,021,752 ± 17,110 | 0.96× | 2,484 | 2,488 |
| `precompiledDynamicBean` | size=1000 | thrpt | ops/s | 16,704 ± 373 | 17,138 ± 1,284 | 1.03× | 73,761 | 73,817 |
| `precompiledDynamicDirect` | size=10 | thrpt | ops/s | 1,991,767 ± 744,533 | 1,572,908 ± 44,288 | 0.79× | 1,180 | 1,176 |
| `precompiledDynamicDirect` | size=1000 | thrpt | ops/s | 16,169 ± 1,201 | 15,995 ± 152 | 0.99× | 72,465 | 72,465 |
| `precompiledStaticBean` | size=10 | thrpt | ops/s | 2,054,074 ± 12,745 | 2,060,303 ± 15,734 | 1.00× | 2,464 | 2,464 |
| `precompiledStaticBean` | size=1000 | thrpt | ops/s | 16,532 ± 2,570 | 20,918 ± 6,275 | 1.27× | 73,745 | 73,745 |
| `precompiledStaticDirect` | size=10 | thrpt | ops/s | 2,688,331 ± 299,633 | 3,042,138 ± 40,695 | 1.13× | 1,144 | 1,144 |
| `precompiledStaticDirect` | size=1000 | thrpt | ops/s | 16,580 ± 366 | 16,803 ± 400 | 1.01× | 72,449 | 72,449 |
| `python3HostAccess` | size=10 | thrpt | ops/s | 119 ± 6 | 113 ± 5 | 0.94× | 5,510,096 | 5,511,626 |
| `python3HostAccess` | size=1000 | thrpt | ops/s | 104 ± 4 | 97.23 ± 2.58 | 0.94× | 6,577,729 | 6,577,629 |

## GroovyRouteTest

raw/GroovyRouteTest-jdk21-allfixes.jmh.json is empty (JMH writes the file when the run completes)

## GroovyOverheadTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `evaluateGroovy` | extraBeans=0,shellFactory=factoryWithFileName | thrpt | ops/s | 2,552,970 ± 20,817 | 14,546,834 ± 854,709 | 5.70× | 2,000 | 288 |
| `evaluateGroovy` | extraBeans=0,shellFactory=none | thrpt | ops/s | 3,362,248 ± 19,360 | 14,481,113 ± 105,677 | 4.31× | 1,400 | 264 |
| `evaluateGroovy` | extraBeans=500,shellFactory=factoryWithFileName | thrpt | ops/s | 177,819 ± 3,344 | 14,324,696 ± 54,875 | 80.56× | 2,000 | 264 |
| `evaluateGroovy` | extraBeans=500,shellFactory=none | thrpt | ops/s | 283,929 ± 982 | 14,456,935 ± 132,990 | 50.92× | 1,480 | 264 |
| `evaluatePrototypeLazyBinding` | extraBeans=0,shellFactory=factoryWithFileName | thrpt | ops/s | 18,191,436 ± 23,890 | 17,993,940 ± 65,916 | 0.99× | 248 | 248 |
| `evaluatePrototypeLazyBinding` | extraBeans=0,shellFactory=none | thrpt | ops/s | 18,095,413 ± 334,945 | 18,004,116 ± 60,820 | 0.99× | 248 | 248 |
| `evaluatePrototypeLazyBinding` | extraBeans=500,shellFactory=factoryWithFileName | thrpt | ops/s | 18,252,341 ± 44,755 | 17,911,154 ± 86,078 | 0.98× | 248 | 248 |
| `evaluatePrototypeLazyBinding` | extraBeans=500,shellFactory=none | thrpt | ops/s | 18,240,546 ± 270,547 | 18,030,228 ± 47,712 | 0.99× | 248 | 248 |
| `evaluatePrototypeOptimized` | extraBeans=0,shellFactory=factoryWithFileName | thrpt | ops/s | 5,709,191 ± 19,891 | 5,664,128 ± 30,963 | 0.99× | 1,160 | 864 |
| `evaluatePrototypeOptimized` | extraBeans=0,shellFactory=none | thrpt | ops/s | 5,728,707 ± 12,427 | 5,676,927 ± 23,521 | 0.99× | 1,160 | 864 |
| `evaluatePrototypeOptimized` | extraBeans=500,shellFactory=factoryWithFileName | thrpt | ops/s | 5,706,718 ± 11,080 | 5,678,588 ± 17,424 | 1.00× | 1,160 | 864 |
| `evaluatePrototypeOptimized` | extraBeans=500,shellFactory=none | thrpt | ops/s | 5,718,748 ± 20,667 | 5,712,112 ± 26,781 | 1.00× | 1,160 | 864 |
| `stepCacheKeyConcatAndLookup` |  | thrpt | ops/s | 52,748,973 ± 5,645,694 | 55,046,964 ± 390,169 | 1.04× | 88 | 88 |
| `stepConvertResult` |  | thrpt | ops/s | 605,678,787 ± 3,146,929 | 603,275,757 ± 1,168,644 | 1.00× | 0 | 0 |
| `stepCreateBinding` |  | thrpt | ops/s | 6,488,445 ± 23,189 | 70,088,450 ± 247,527 | 10.80× | 1,152 | 160 |
| `stepFindShellFactory` |  | thrpt | ops/s | 48,140,236 ± 151,717 | 42,681,479 ± 6,105,860 | 0.89× | 80 | 80 |
| `stepInstantiateScript` |  | thrpt | ops/s | 14,233,254 ± 293,005 | 57,010,228 ± 202,398 | 4.01× | 240 | 48 |
| `stepNewInstanceMethodHandle` |  | thrpt | ops/s | 73,291,339 ± 2,408,601 | 76,029,205 ± 6,310,551 | 1.04× | 48 | 48 |
| `stepNewInstanceReflection` |  | thrpt | ops/s | 38,349,942 ± 2,261,797 | 36,772,272 ± 176,620 | 0.96× | 160 | 168 |
| `stepResolveLanguage` |  | thrpt | ops/s | 143,765,950 ± 235,595 | 142,615,011 ± 949,315 | 0.99× | 24 | 24 |
| `stepRunScript` |  | thrpt | ops/s | 20,761,196 ± 2,195,726 | 24,027,180 ± 2,270,816 | 1.16× | 104 | 104 |

## GroovyScriptCacheTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `compileDistinctScripts` | scripts=10 | avgt | ms/op | 8.88 ± 0.32 | 8.93 ± 0.57 | 0.99× | 5,496,392 | 5,482,882 |
| `compileDistinctScripts` | scripts=100 | avgt | ms/op | 84.60 ± 3.50 | 84.06 ± 5.16 | 1.01× | 49,140,815 | 48,991,318 |
| `compileDistinctScripts` | scripts=1000 | avgt | ms/op | 808 ± 27 | 828 ± 31 | 0.98× | 484,389,247 | 483,271,450 |
| `roundRobinDistinctScripts` | distinctScripts=100 | avgt | ns/op | 479 ± 5 | 126 ± 2 | 3.79× | 1,448 | 264 |
| `roundRobinDistinctScripts` | distinctScripts=1000 | avgt | us/op | 7.48 ± 4.89 | 8.29 ± 4.70 | 0.90× | 1,697 | 457 |
| `roundRobinDistinctScripts` | distinctScripts=1001 | avgt | us/op | 703 ± 39 | 8.28 ± 4.65 | 84.83× | 480,514 | 457 |
| `roundRobinDistinctScripts` | distinctScripts=2000 | avgt | us/op | 700 ± 42 | 3.57 ± 0.46 | 195.73× | 480,777 | 439 |

## GroovyJsonDataFormatTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `marshalGroovyCompact` | payload=1KB | avgt | us/op | 13.49 ± 0.06 | 13.57 ± 0.13 | 0.99× | 117,508 | 117,496 |
| `marshalGroovyCompact` | payload=1MB | avgt | ms/op | 5.98 ± 0.05 | 6.02 ± 0.03 | 0.99× | 17,932,381 | 17,882,029 |
| `marshalGroovyPretty` | payload=1KB | avgt | us/op | 60.79 ± 0.31 | 123 ± 1 | 0.49× | 352,482 | 1,320,292 |
| `marshalGroovyPretty` | payload=1MB | avgt | ms/op | 55.61 ± 0.18 | 131 ± 0 | 0.43× | 242,871,764 | 1,383,161,437 |
| `marshalGroovyStreaming` | payload=1KB | avgt | us/op | 13.75 ± 0.06 | 13.83 ± 0.08 | 0.99× | 120,928 | 120,928 |
| `marshalGroovyStreaming` | payload=1MB | avgt | ms/op | 5.94 ± 0.05 | 5.99 ± 0.03 | 0.99× | 20,030,699 | 19,929,996 |
| `marshalJacksonCompact` | payload=1KB | avgt | us/op | 1.87 ± 0.01 | 1.87 ± 0.01 | 1.00× | 2,936 | 2,956 |
| `marshalJacksonCompact` | payload=1MB | avgt | ms/op | 1.85 ± 0.15 | 1.81 ± 0.02 | 1.02× | 3,828,025 | 3,828,024 |
| `marshalJacksonPretty` | payload=1KB | avgt | us/op | 2.66 ± 0.04 | 2.61 ± 0.01 | 1.02× | 3,856 | 3,856 |
| `marshalJacksonPretty` | payload=1MB | avgt | ms/op | 3.15 ± 0.25 | 2.89 ± 0.14 | 1.09× | 6,316,866 | 6,316,857 |
| `marshalJsonOutputToJson` | payload=1KB | avgt | us/op | 13.39 ± 0.04 | 13.48 ± 0.10 | 0.99× | 116,152 | 116,200 |
| `marshalJsonOutputToJson` | payload=1MB | avgt | ms/op | 5.91 ± 0.02 | 5.95 ± 0.02 | 0.99× | 16,571,907 | 16,571,907 |
| `unmarshalGroovy` | payload=1KB | avgt | us/op | 3.21 ± 0.03 | 3.29 ± 0.06 | 0.98× | 26,544 | 26,544 |
| `unmarshalGroovy` | payload=1MB | avgt | ms/op | 2.95 ± 0.04 | 2.92 ± 0.03 | 1.01× | 10,919,135 | 10,919,134 |
| `unmarshalJackson` | payload=1KB | avgt | us/op | 2.95 ± 0.05 | 2.87 ± 0.04 | 1.03× | 7,956 | 8,084 |
| `unmarshalJackson` | payload=1MB | avgt | ms/op | 2.65 ± 0.02 | 2.58 ± 0.01 | 1.03× | 7,185,284 | 7,185,279 |
| `unmarshalWalkGroovy` | payload=1KB | avgt | us/op | 5.61 ± 0.05 | 5.63 ± 0.11 | 1.00× | 42,240 | 42,240 |
| `unmarshalWalkGroovy` | payload=1MB | avgt | ms/op | 5.47 ± 0.25 | 5.43 ± 0.04 | 1.01× | 27,561,253 | 27,561,251 |
| `unmarshalWalkGroovyIndexOverlay` | payload=1KB | avgt | us/op | 5.51 ± 0.02 | 5.59 ± 0.02 | 0.99× | 36,120 | 36,120 |
| `unmarshalWalkGroovyIndexOverlay` | payload=1MB | avgt | ms/op | 4.55 ± 0.35 | 4.39 ± 0.06 | 1.04× | 21,209,657 | 21,209,652 |
| `unmarshalWalkJackson` | payload=1KB | avgt | us/op | 4.20 ± 0.05 | 4.29 ± 0.02 | 0.98× | 10,476 | 10,328 |
| `unmarshalWalkJackson` | payload=1MB | avgt | ms/op | 3.89 ± 0.04 | 3.84 ± 0.05 | 1.01× | 10,037,345 | 10,037,343 |

## GroovyXmlDataFormatTest

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `marshalMapGroovyXml` | payload=1KB | avgt | us/op | 7.44 ± 0.07 | 8.81 ± 0.10 | 0.84× | 25,576 | 36,408 |
| `marshalMapGroovyXml` | payload=1MB | avgt | ms/op | 9.41 ± 0.54 | 8.16 ± 0.03 | 1.15× | 27,405,324 | 19,000,518 |
| `marshalMapGroovyXmlBufferedDevNull` | payload=1KB | avgt | us/op | 9.64 ± 0.03 | 9.37 ± 0.19 | 1.03× | 20,848 | 34,256 |
| `marshalMapGroovyXmlBufferedDevNull` | payload=1MB | avgt | ms/op | 9.89 ± 0.85 | 8.57 ± 0.30 | 1.15× | 22,035,645 | 13,790,122 |
| `marshalMapGroovyXmlDevNull` | payload=1KB | avgt | us/op | 252 ± 1 | 9.41 ± 0.07 | 26.82× | 21,928 | 34,256 |
| `marshalMapGroovyXmlDevNull` | payload=1MB | avgt | ms/op | 261 ± 2 | 8.55 ± 0.34 | 30.59× | 22,546,247 | 13,790,122 |
| `marshalMapJacksonXml` | payload=1KB | avgt | us/op | 2.98 ± 0.01 | 2.98 ± 0.00 | 1.00× | 4,856 | 4,856 |
| `marshalMapJacksonXml` | payload=1MB | avgt | ms/op | 3.09 ± 0.01 | 3.11 ± 0.01 | 0.99× | 6,431,849 | 6,431,851 |
| `marshalMapJacksonXmlDevNull` | payload=1KB | avgt | us/op | 3.67 ± 0.01 | 3.70 ± 0.05 | 0.99× | 2,872 | 2,872 |
| `marshalMapJacksonXmlDevNull` | payload=1MB | avgt | ms/op | 3.70 ± 0.02 | 3.76 ± 0.02 | 0.98× | 1,511,481 | 1,511,482 |
| `unmarshalDom` | payload=1KB | avgt | us/op | 16.43 ± 0.27 | 16.49 ± 0.29 | 1.00× | 39,416 | 39,384 |
| `unmarshalDom` | payload=1MB | avgt | ms/op | 6.61 ± 0.02 | 6.60 ± 0.05 | 1.00× | 4,938,996 | 4,938,994 |
| `unmarshalGroovyXml` | payload=1KB | avgt | us/op | 33.21 ± 0.24 | 10.80 ± 0.02 | 3.07× | 66,481 | 19,672 |
| `unmarshalGroovyXml` | payload=1MB | avgt | ms/op | 9.27 ± 0.10 | 9.57 ± 0.06 | 0.97× | 17,605,742 | 17,557,939 |
| `unmarshalGroovyXmlCachedFactory` | payload=1KB | avgt | us/op | 18.25 ± 0.19 | 18.28 ± 0.31 | 1.00× | 43,633 | 43,649 |
| `unmarshalGroovyXmlCachedFactory` | payload=1MB | avgt | ms/op | 9.30 ± 0.07 | 9.27 ± 0.21 | 1.00× | 17,582,148 | 17,582,147 |
| `unmarshalJacksonXml` | payload=1KB | avgt | us/op | 6.05 ± 0.13 | 6.05 ± 0.02 | 1.00× | 9,736 | 9,736 |
| `unmarshalJacksonXml` | payload=1MB | avgt | ms/op | 6.09 ± 0.05 | 6.13 ± 0.02 | 0.99× | 7,090,453 | 7,090,454 |
| `unmarshalStaxScan` | payload=1KB | avgt | us/op | 3.45 ± 0.11 | 3.36 ± 0.01 | 1.03× | 4,480 | 4,480 |
| `unmarshalStaxScan` | payload=1MB | avgt | ms/op | 3.31 ± 0.07 | 3.29 ± 0.01 | 1.01× | 2,517,191 | 2,517,191 |

## GroovyRouteTest sample (p99)

raw/GroovyRouteTest-jdk21-allfixes-sample.jmh.json is empty (JMH writes the file when the run completes)

## quickjs baseline vs allfixes

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `arithmeticQuickjs` |  | thrpt | ops/s | 1,707 ± 19 | 3,948 ± 55 | 2.31× | 36,897 | 28,911 |
| `concatQuickjs` |  | thrpt | ops/s | 1,665 ± 11 | 3,876 ± 62 | 2.33× | 37,802 | 29,996 |
| `predicateQuickjs` |  | thrpt | ops/s | 1,700 ± 15 | 3,923 ± 68 | 2.31× | 36,959 | 29,158 |

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `quickjs` | size=10 | thrpt | ops/s | 1,470 ± 9 | 3,232 ± 85 | 2.20× | 48,199 | 40,533 |
| `quickjs` | size=1000 | thrpt | ops/s | 203 ± 2 | 214 ± 1 | 1.06× | 1,057,515 | 1,049,641 |

raw/GroovyRouteTest-jdk21-allfixes.jmh.json is empty (JMH writes the file when the run completes)

| benchmark | params | mode | unit | before | after | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|---|---|
| `firstEvaluationQuickjs` |  | ss | ms/op | 24.81 ± 12.40 | 27.07 ± 12.87 | 0.92× |  |  |

## load (60-300 s)

| variant | msg/s | p99 µs (median/max) | bytes/msg | alloc MB/s | GC pauses/s | pause % | max pause ms | old gen after GC MB (first/max/last) | Metaspace MB (first/last) | classes loaded | classes unloaded | CPU % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| java-harness2 | 4,109,230 | 2 / 2 | 1,538 | 6,027 | 9.89 | 0.94 | 2.00 | 17.1 / 17.3 / 17.3 | 17.1 / 17.2 | 6 | 0 | 79.71 |
| java-allfixes | 4,177,417 | 2 / 2 | 1,538 | 6,127 | 10.06 | 0.95 | 2.00 | 17.0 / 17.2 / 17.2 | 17.1 / 17.2 | 6 | 0 | 79.73 |
| groovy-harness2 | 1,082,957 | 102 / 103 | 5,598 | 5,781 | 9.49 | 0.93 | 2.00 | 26.0 / 26.1 / 26.1 | 28.5 / 28.6 | 0 | 0 | 45.92 |
| groovy-allfixes | 3,804,907 | 3 / 3 | 2,799 | 10,156 | 16.67 | 1.61 | 2.00 | 26.2 / 26.4 / 26.4 | 28.4 / 28.5 | 0 | 0 | 78.83 |
| groovy-prototype | 3,737,215 | 3 / 4 | 3,002 | 10,698 | 17.56 | 1.72 | 2.00 | 26.2 / 26.4 / 26.4 | 28.4 / 28.5 | 0 | 0 | 78.81 |
| jactl | 3,731,657 | 3 / 5 | 1,626 | 5,785 | 9.49 | 0.94 | 2.00 | 14.8 / 14.8 / 14.8 | 21.2 / 21.4 | 6 | 0 | 77.69 |
| jactl-allfixes | 4,050,241 | 2 / 2 | 1,626 | 6,279 | 10.31 | 0.98 | 2.00 | 20.3 / 20.4 / 20.4 | 21.2 / 21.4 | 6 | 0 | 79.71 |
| mvel | 3,676,944 | 3 / 6 | 1,835 | 6,435 | 10.56 | 1.00 | 2.00 | 0.0 / 0.0 / 0.0 | 18.4 / 18.5 | 6 | 0 | 78.12 |
| mvel-allfixes | 3,994,026 | 3 / 3 | 1,835 | 6,990 | 11.47 | 1.08 | 2.00 | 18.0 / 18.2 / 18.2 | 18.4 / 18.5 | 6 | 0 | 79.71 |
| javaLanguage | 3,532,546 | 4 / 6 | 1,570 | 5,288 | 8.68 | 0.85 | 9.00 | 44.6 / 44.6 / 44.6 | 26.9 / 27.1 | 7 | 0 | 77.56 |
| javaLanguage-allfixes | 4,023,264 | 2 / 2 | 1,570 | 6,023 | 9.89 | 0.94 | 2.00 | 63.9 / 64.0 / 64.0 | 27.0 / 27.1 | 7 | 0 | 79.79 |
| js | 4,697 | 4300 / 5600 | 1,767,305 | 7,916 | 13.02 | 2.12 | 3.00 | 22.4 / 22.4 / 22.4 | 40.7 / 40.8 | 0 | 0 | 67.69 |
| js-allfixes | 15,006 | 1200 / 1200 | 323,482 | 4,629 | 7.59 | 1.06 | 2.00 | 23.9 / 24.2 / 24.2 | 38.9 / 39.0 | 0 | 0 | 68.48 |
| groovyManyScripts-prototype | 2,732,130 | 6 / 11 | 3,058 | 7,967 | 13.07 | 1.75 | 3.00 | 110.8 / 111.0 / 111.0 | 88.5 / 88.7 | 2 | 0 | 78.85 |
| groovyManyScripts-allfixes | 2,922,193 | 5 / 9 | 2,819 | 7,855 | 12.89 | 1.66 | 2.00 | 110.4 / 110.6 / 110.6 | 88.6 / 88.7 | 2 | 0 | 78.92 |
