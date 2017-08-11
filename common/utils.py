#!/usr/bin/env python
# encoding: utf-8
import ntpath
import os

from lxml import etree
from string import strip
from logger import info, error, warning

from common.exceptions import ApplicationException
from CTDopts.CTDopts import CTDModel


MESSAGE_INDENTATION_INCREMENT = 2


# simple struct-class containing a tuple with input/output location and the in-memory CTDModel
class ParsedCTD:
    def __init__(self, ctd_model=None, input_file=None, suggested_output_file=None):
        self.ctd_model = ctd_model
        self.input_file = input_file
        self.suggested_output_file = suggested_output_file


class ParameterHardcoder:
    def __init__(self):
        # map whose keys are the composite names of tools and parameters in the following pattern:
        # [ToolName][separator][ParameterName] -> HardcodedValue
        # if the parameter applies to all tools, then the following pattern is used:
        # [ParameterName] -> HardcodedValue

        # examples (assuming separator is '#'):
        # threads -> 24
        # XtandemAdapter#adapter -> xtandem.exe
        # adapter -> adapter.exe
        self.separator = "!"
        self.parameter_map = {}

    # the most specific value will be returned in case of overlap
    def get_hardcoded_value(self, parameter_name, tool_name):
        # look for the value that would apply for all tools
        generic_value = self.parameter_map.get(parameter_name, None)
        specific_value = self.parameter_map.get(self.build_key(parameter_name, tool_name), None)
        if specific_value is not None:
            return specific_value

        return generic_value

    def register_parameter(self, parameter_name, parameter_value, tool_name=None):
        self.parameter_map[self.build_key(parameter_name, tool_name)] = parameter_value

    def build_key(self, parameter_name, tool_name):
        if tool_name is None:
            return parameter_name
        return "%s%s%s" % (parameter_name, self.separator, tool_name)


def validate_path_exists(path):
    if not os.path.isfile(path) or not os.path.exists(path):
        raise ApplicationException("The provided path (%s) does not exist or is not a valid file path." % path)


def validate_argument_is_directory(args, argument_name):
    file_name = getattr(args, argument_name)
    if file_name is not None and os.path.isdir(file_name):
        raise ApplicationException("The provided output file name (%s) points to a directory." % file_name)


def validate_argument_is_valid_path(args, argument_name):
    paths_to_check = []
    # check if we are handling a single file or a list of files
    member_value = getattr(args, argument_name)
    if member_value is not None:
        if isinstance(member_value, list):
            for file_name in member_value:
                paths_to_check.append(strip(str(file_name)))
        else:
            paths_to_check.append(strip(str(member_value)))

        for path_to_check in paths_to_check:
            validate_path_exists(path_to_check)


# taken from
# http://stackoverflow.com/questions/8384737/python-extract-file-name-from-path-no-matter-what-the-os-path-format
def get_filename(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def get_filename_without_suffix(path):
    root, ext = os.path.splitext(os.path.basename(path))
    return root


def parse_input_ctds(xsd_location, input_ctds, output_destination, output_file_extension):
    is_converting_multiple_ctds = len(input_ctds) > 1
    parsed_ctds = []
    schema = None
    if xsd_location is not None:
        try:
            info("Loading validation schema from %s" % xsd_location, 0)
            schema = etree.XMLSchema(etree.parse(xsd_location))
        except Exception, e:
            error("Could not load validation schema %s. Reason: %s" % (xsd_location, str(e)), 0)
    else:
        info("Validation against a schema has not been enabled.", 0)
    for input_ctd in input_ctds:
        try:
            if schema is not None:
                validate_against_schema(input_ctd, schema)
            output_file = output_destination
            # if multiple inputs are being converted, we need to generate a different output_file for each input
            if is_converting_multiple_ctds:
                output_file = os.path.join(output_file,
                                           get_filename_without_suffix(input_ctd) + '.' + output_file_extension)
            parsed_ctds.append(ParsedCTD(CTDModel(from_file=input_ctd), input_ctd, output_file))
        except Exception, e:
            error(str(e), 1)
            continue
    return parsed_ctds


def flatten_list_of_lists(args, list_name):
    setattr(args, list_name, [item for sub_list in getattr(args, list_name) for item in sub_list])


def validate_against_schema(ctd_file, schema):
    try:
        parser = etree.XMLParser(schema=schema)
        etree.parse(ctd_file, parser=parser)
    except etree.XMLSyntaxError, e:
        raise ApplicationException("Invalid CTD file %s. Reason: %s" % (ctd_file, str(e)))


def add_common_parameters(parser, version, last_updated):
    parser.add_argument("FORMAT", default=None, help="Output format (mandatory). Can be one of: cwl, galaxy.")
    parser.add_argument("-i", "--input", dest="input_files", default=[], required=True, nargs="+", action="append",
                        help="List of CTD files to convert.")
    parser.add_argument("-o", "--output-destination", dest="output_destination", required=True,
                        help="If multiple input files are given, then a folder in which all converted "
                             "files will be generated is expected; "
                             "if a single input file is given, then a destination file is expected.")
    parser.add_argument("-x", "--default-executable-path", dest="default_executable_path",
                        help="Use this executable path when <executablePath> is not present in the CTD",
                        default=None, required=False)
    parser.add_argument("-b", "--blacklist-parameters", dest="blacklisted_parameters", default=[], nargs="+",
                        action="append",
                        help="List of parameters that will be ignored and won't appear on the galaxy stub",
                        required=False)
    parser.add_argument("-p", "--hardcoded-parameters", dest="hardcoded_parameters", default=None, required=False,
                        help="File containing hardcoded values for the given parameters. Run with '-h' or '--help' "
                             "to see a brief example on the format of this file.")
    parser.add_argument("-V", "--validation-schema", dest="xsd_location", default=None, required=False,
                        help="Location of the schema to use to validate CTDs. If not provided, no schema validation "
                             "will take place.")

    # TODO: add verbosity, maybe?
    program_version = "v%s" % version
    program_build_date = str(last_updated)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    parser.add_argument("-v", "--version", action='version', version=program_version_message)


def parse_hardcoded_parameters(hardcoded_parameters_file):
    parameter_hardcoder = ParameterHardcoder()
    if hardcoded_parameters_file is not None:
        line_number = 0
        with open(hardcoded_parameters_file) as f:
            for line in f:
                line_number += 1
                if line is None or not line.strip() or line.strip().startswith("#"):
                    pass
                else:
                    # the third column must not be obtained as a whole, and not split
                    parsed_hardcoded_parameter = line.strip().split(None, 2)
                    # valid lines contain two or three columns
                    if len(parsed_hardcoded_parameter) != 2 and len(parsed_hardcoded_parameter) != 3:
                        warning("Invalid line at line number %d of the given hardcoded parameters file. Line will be"
                                "ignored:\n%s" % (line_number, line), 0)
                        continue

                    parameter_name = parsed_hardcoded_parameter[0]
                    hardcoded_value = parsed_hardcoded_parameter[1]
                    tool_names = None
                    if len(parsed_hardcoded_parameter) == 3:
                        tool_names = parsed_hardcoded_parameter[2].split(',')
                    if tool_names:
                        for tool_name in tool_names:
                            parameter_hardcoder.register_parameter(parameter_name, hardcoded_value, tool_name.strip())
                    else:
                        parameter_hardcoder.register_parameter(parameter_name, hardcoded_value)

    return parameter_hardcoder
