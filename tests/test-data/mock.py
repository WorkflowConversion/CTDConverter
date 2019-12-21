#!/usr/bin/env python

# little mock app to handle ouput file parameters
# i.e. to create them

import os
import re
import sys

wd=os.path.dirname(__file__)

fparam = {"input": set(), "output": set()}
ctd = sys.argv[1]
with open(os.path.join(wd, ctd)) as cf:
    for line in cf:
        m = re.search(r'type="(input|output)-file"', line)
        if m is not None:
            n = re.search(r'name="([^"]+)"', line)
            fparam[m.group(1)].add(n.group(1))
        

i = 2
while i < len(sys.argv):
    if sys.argv[i].startswith("-"):
        param = sys.argv[i][1:]
        if param in fparam["input"] or param in fparam["output"]:
            if param in fparam["input"]:
                mode = "r"
            else: 
                mode = "w"

            while i+1 < len(sys.argv):
                if sys.argv[i+1].startswith("-"):
                    break
                of = open(sys.argv[i+1], mode)
                of.close()
                i += 1
    i += 1
