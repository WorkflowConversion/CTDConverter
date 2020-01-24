#!/usr/bin/env python

# little mock app to handle ouput file parameters
# i.e. to create them

import os
import re
import shutil
import sys


# from argparse import ArgumentParser
# parser = ArgumentParser(prog="mock.py", description="MOCK", add_help=True)
# parser.add_argument("-w", "-write_ctd", dest="write_ctd", metavar='PATH', default=None, required=False,
#                     help="Write CTD to given path")
# parser.add_argument("-i", "-ini", dest="ini", metavar='CTDFILE', default=None, required=False,
#                     help="Process CTDFILE")
# parser.add_argument('moreargs', metavar='ARGS', type=str, nargs='*', help='more arguments')
# args = parser.parse_args()
print(sys.argv)

wd = os.path.dirname(__file__)
bn = os.path.splitext(os.path.basename(__file__))[0]

if sys.argv[1] == "-write_ctd":
    shutil.copyfile(os.path.join(wd, bn + ".ctd"), os.path.join(sys.argv[2], bn + ".ctd"))
elif sys.argv[1] == "-ini":
    fparam = {"input": set(), "output": set()}
    with open(sys.argv[2]) as cf:
        for line in cf:
            m = re.search(r'type="(input|output)-file"', line)
            if m is not None:
                n = re.search(r'name="([^"]+)"', line)
                fparam[m.group(1)].add(n.group(1))

    i = 3
    while i < len(sys.argv):
        if sys.argv[i].startswith("-"):
            param = sys.argv[i][1:]
            if param in fparam["input"] or param in fparam["output"]:
                if param in fparam["input"]:
                    mode = "r"
                else:
                    mode = "w"

                while i + 1 < len(sys.argv):
                    if sys.argv[i + 1].startswith("-"):
                        break
                    of = open(sys.argv[i + 1], mode)
                    of.close()
                    i += 1
        i += 1
else:
    sys.stderr.write("Either -write_ctd or -ini must be given")
    sys.exit(1)
