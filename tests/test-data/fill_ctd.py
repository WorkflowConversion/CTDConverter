import json
import sys

from CTDopts.CTDopts import CTDModel

input_ctd = sys.argv[1]
with open(sys.argv[2]) as fh:
    args = json.load(fh)

if "adv_opts_cond" in args:
    args.update(args["adv_opts_cond"])
    del args["adv_opts_cond"]

model = CTDModel(from_file=input_ctd)
# model.write_ctd(input_ctd, arg_dict = {'1':args})
model.write_ctd(input_ctd)
