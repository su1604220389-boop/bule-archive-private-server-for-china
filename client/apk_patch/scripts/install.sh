#!/bin/bash
set -x
export DEBIAN_FRONTEND=noninteractive
echo "=== apt update ==="
apt-get update -qq 2>&1 | tail -5
echo "=== install candidates ==="
apt-cache policy apksigner zipalign aapt android-sdk-build-tools android-sdk-platform-tools-common zip unzip openjdk-21-jre-headless openjdk-17-jre-headless default-jre-headless 2>&1 | head -80
echo "=== install base ==="
apt-get install -y -qq --no-install-recommends \
  openjdk-21-jre-headless openjdk-21-jdk-headless \
  apktool zip unzip file curl wget ca-certificates git 2>&1 | tail -25
echo "=== versions ==="
java -version 2>&1
apktool --version 2>&1 | head -3
which java apktool unzip zip
echo "=== try android build tools ==="
apt-cache search 'apksigner|zipalign|aapt' 2>&1 | head -20
echo "=== net test ==="
curl -s -o /dev/null -w "github:%{http_code}\n" --max-time 20 https://github.com/ 2>&1
curl -s -o /dev/null -w "objects.github:%{http_code}\n" --max-time 20 https://objects.githubusercontent.com/ 2>&1
curl -s -o /dev/null -w "ghproxy:%{http_code}\n" --max-time 20 https://ghproxy.net/ 2>&1
echo "=== DONE INSTALL ==="
