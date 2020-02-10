from functools import reduce  # forward compatibility for Python 3
import json
import operator
import sys

from CTDopts.CTDopts import CTDModel, _Null, _InFile, _NumericRange


def getFromDict(dataDict, mapList):
    return reduce(operator.getitem, mapList, dataDict)


def setInDict(dataDict, mapList, value):
    getFromDict(dataDict, mapList[:-1])[mapList[-1]] = value


def _json_object_hook(d):
    """
    wee helper to transform the json written by galaxy
    while loading
    - sections are dicts -> recurse
    - True/False (bool objects) -> "true"/"false" (lowercase string)
    - None -> "" (empty string)
    """
    for k in d:
        if type(d[k]) is bool:
            d[k] = str(d[k]).lower()
        elif type(d[k]) is list and len(d[k]) == 1 and d[k][0] is None:
            d[k] = []
        elif d[k] is None:
            d[k] = ""
    return d


def qstring2list(qs):
    """
    transform a space separated string that is quoted by " into a list
    """
    lst = list()
    qs = qs.split(" ")
    for p in qs:
        if p == "":
            continue

        if p.startswith('"') and p.endswith('"'):
            lst.append(p[1:-1])
        elif p.startswith('"'):
            lst.append( p[1:]+" ")
        elif p.endswith('"'):
            lst[-1] += p[:-1]
        else:
            lst.append(p)
    return lst

input_ctd = sys.argv[1]
with open(sys.argv[2]) as fh:
    args = json.load(fh, object_hook=_json_object_hook)

if "adv_opts_cond" in args:
    args.update(args["adv_opts_cond"])
    del args["adv_opts_cond"]

model = CTDModel(from_file=input_ctd)

# transform values from json that 
# - correspond to unrestricted ITEMLIST which are represented as strings 
#   ("=quoted and space separated) in Galaxy to lists
# - optional data input parameters that have defaults and for which no
#   value is given are overwritten with the default
for p in model.get_parameters():
    if p.is_list and (p.restrictions is None or type(p.restrictions) is _NumericRange):
        v = getFromDict(args, p.get_lineage(name_only=True))
        if type(v) is str:
            setInDict(args, p.get_lineage(name_only=True), qstring2list(v))
    if p.type is _InFile and p.default not in [None, _Null]:
        v = getFromDict(args, p.get_lineage(name_only=True))
        if v in [[], ""]:
            setInDict(args, p.get_lineage(name_only=True), p.default)

model.write_ctd(input_ctd, arg_dict=args)
