#!/usr/bin/env python

# little mock app to handle ouput file parameters
# i.e. to create them

import os
import re
import sys

wd=os.path.dirname(__file__)

oparam=set()
ctd = sys.argv[1]
with open(os.path.join(wd, ctd)) as cf:
    for line in cf:
        m = re.search(r'type="output-file"', line)
        if m is None:
            continue
        m = re.search(r'name="([^"]+)"', line)
        oparam.add(m.group(1))

i = 2
while i < len(sys.argv):
    if sys.argv[i].startswith("-"):
        param = sys.argv[i][1:]
        if param in oparam:
            of = open(sys.argv[i+1], "w")
            of.close()
    i += 1
