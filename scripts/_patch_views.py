# -*- coding: utf-8 -*-
from pathlib import Path
import re

p = Path(__file__).with_name("_build_effluent.py")
t = p.read_text(encoding="utf-8")
names = [
    "plantsViewTemplate",
    "outfallsViewTemplate",
    "samplesViewTemplate",
    "exceedViewTemplate",
    "releaseViewTemplate",
    "sealViewTemplate",
    "permitsViewTemplate",
    "lineageViewTemplate",
    "reconcileViewTemplate",
    "stubsViewTemplate",
]
for n in names:
    old = f"export function {n}() {{\n  return `"
    new = f"export const {n} = `"
    if old in t:
        t = t.replace(old, new)
        print("fixed start", n)
    else:
        print("miss start", n)

# Remove leftover function-closing braces after view template strings
pat = re.compile(r"(</div>`;)\n\}\n('''[,}])")
t, n = pat.subn(r"\1\n\2", t)
print("removed closers", n)
p.write_text(t, encoding="utf-8")
