#!/usr/bin/env bash
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Builds camel-groovy from an apache/camel checkout (e.g. a prototype branch) and installs it into the local Maven
# repository under a separate version, so the main 4.23.0-SNAPSHOT jar is left untouched:
#
#   CAMEL_DIR=/path/to/camel ./groovy-results/install-prototype.sh
#   mvn test -P jmh -Dtest=GroovyRouteTest -Dcamel-groovy-bench-version=4.23.0-perf-SNAPSHOT
set -euo pipefail

CAMEL_DIR=${CAMEL_DIR:?set CAMEL_DIR to the apache/camel checkout with the prototype}
VERSION=${PROTOTYPE_VERSION:-4.23.0-perf-SNAPSHOT}
TMP=$(mktemp -d)

cd "$CAMEL_DIR"
mvn -o -q package -pl components/camel-groovy -Dquickly
jar=$(ls components/camel-groovy/target/camel-groovy-*-SNAPSHOT.jar | grep -v -E 'sources|javadoc|tests' | head -1)
# same pom (same dependencies), only the project version differs
perl -0pe "s#(<artifactId>camel-groovy</artifactId>)#\$1\n    <version>$VERSION</version>#" \
  components/camel-groovy/pom.xml > "$TMP/pom.xml"
mvn -o -q install:install-file -Dfile="$jar" -DpomFile="$TMP/pom.xml"
echo "installed $jar as org.apache.camel:camel-groovy:$VERSION ($(git rev-parse --short HEAD) $(git branch --show-current), dirty files: $(git status --short | wc -l | tr -d ' '))"
