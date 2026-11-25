#!/bin/bash
set -u
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk
mkdir -p /root/ba_work/verify
unzip -p "$SLIM" classes.dex > /root/ba_work/verify/classes_orig.dex
echo "orig classes.dex extracted: $(stat -c%s /root/ba_work/verify/classes_orig.dex) B"
exec python3 /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/scripts/s2_verify_dex.py
