#!/bin/bash
# read-only: is ll_container_login referenced by any code? (it must NOT be,
# otherwise the paddingTop I add could be clobbered)
D=/root/ba_work/dec0/smali
echo "== ll_container_login in smali =="
grep -rn "ll_container_login" "$D" | head -20 || true
echo "== R\$id;->ll_container_login count =="
grep -rn "R\$id;->ll_container_login" "$D" | wc -l
echo "== setPadding / paddingTop writes in LoginFragment =="
grep -n "setPadding" "$D/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali" || true
