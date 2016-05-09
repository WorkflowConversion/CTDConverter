#!/usr/bin/env python
# encoding: utf-8

"""
@author:     delagarza
"""


import sys
import os
import traceback
import ntpath
import string

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from CTDopts.CTDopts import CTDModel, _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, \
    _FileFormat, ModelError
from collections import OrderedDict
from string import strip
from lxml import etree
from lxml.etree import SubElement, Element, ElementTree, ParseError, parse

__all__ = []
__version__ = 1.0
__date__ = '2014-09-17'
__updated__ = '2016-05-09'

MESSAGE_INDENTATION_INCREMENT = 2

TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data', 
                       _OutFile: 'data', _Choices: 'select'}

STDIO_MACRO_NAME = "stdio"
REQUIREMENTS_MACRO_NAME = "requirements"
ADVANCED_OPTIONS_MACRO_NAME = "advanced_options"

REQUIRED_MACROS = [STDIO_MACRO_NAME, REQUIREMENTS_MACRO_NAME, ADVANCED_OPTIONS_MACRO_NAME]


class CLIError(Exception):
    # Generic exception to raise and log different fatal errors.
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg


class InvalidModelException(ModelError):
    def __init__(self, message):
        super(InvalidModelException, self).__init__()
        self.message = message

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message


class ApplicationException(Exception):
    def __init__(self, msg):
        super(ApplicationException).__init__(type(self))
        self.msg = msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg


class ExitCode:
    def __init__(self, code_range="", level="", description=None):
        self.range = code_range
        self.level = level
        self.description = description    


class DataType:
    def __init__(self, extension, galaxy_extension=None, galaxy_type=None, mimetype=None):
        self.extension = extension
        self.galaxy_extension = galaxy_extension
        self.galaxy_type = galaxy_type
        self.mimetype = mimetype


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


def main(argv=None):  # IGNORE:C0111
    # Command line options.
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_short_description = "CTD2Galaxy - A project from the GenericWorkflowNodes family " \
                                "(https://github.com/orgs/genericworkflownodes)"
    program_usage = '''
    USAGE:
    
    I - Parsing a single CTD file and generate a Galaxy wrapper:

    $ python generator.py -i input.ctd -o output.xml
    

    II - Parsing all found CTD files (files with .ctd and .xml extension) in a given folder and
         output converted Galaxy wrappers in a given folder:

    $ python generator.py -i /home/user/*.ctd -o /home/user/galaxywrappers


    III - Providing file formats, mimetypes

    Galaxy supports the concept of file format in order to connect compatible ports, that is, input ports of a certain
    data format will be able to receive data from a port from the same format. This converter allows you to provide
    a personalized file in which you can relate the CTD data formats with supported Galaxy data formats. The layout of
    this file consists of lines, each of either one or four columns separated by any amount of whitespace. The content
    of each column is as follows:

    * 1st column: file extension
    * 2nd column: data type, as listed in Galaxy
    * 3rd column: full-named Galaxy data type, as it will appear on datatypes_conf.xml
    * 4th column: mimetype (optional)

    The following is an example of a valid "file formats" file:

    ########################################## FILE FORMATS example ##########################################
    # Every line starting with a # will be handled as a comment and will not be parsed.
    # The first column is the file format as given in the CTD and second column is the Galaxy data format.
    # The second, third, fourth and fifth column can be left empty if the data type has already been registered
    # in Galaxy, otherwise, all but the mimetype must be provided.

    # CTD type    # Galaxy type      # Long Galaxy data type            # Mimetype
    csv           tabular            galaxy.datatypes.data:Text
    fasta
    ini           txt                galaxy.datatypes.data:Text
    txt
    idxml         txt                galaxy.datatypes.xml:GenericXml    application/xml
    options       txt                galaxy.datatypes.data:Text
    grid          grid               galaxy.datatypes.data:Grid

    ##########################################################################################################

    Note that each line consists precisely of either one, three or four columns. In the case of data types already
    registered in Galaxy (such as fasta and txt in the above example), only the first column is needed. In the case of
    data types that haven't been yet registered in Galaxy, the first three columns are needed (mimetype is optional).

    For information about Galaxy data types and subclasses, see the following page:
    https://wiki.galaxyproject.org/Admin/Datatypes/Adding%20Datatypes


    IV - Hardcoding parameters

    It is possible to hardcode parameters. This makes sense if you want to set a tool in Galaxy in 'quiet' mode or if
    your tools support multi-threading and accept the number of threads via a parameter, without giving the end user the
    chance to change the values for these parameters.

    In order to generate hardcoded parameters, you need to provide a simple file. Each line of this file contains two
    or three columns separated by whitespace. Any line starting with a '#' will be ignored. The first column contains
    the name of the parameter, the second column contains the value that will always be set for this parameter. The
    first two columns are mandatory.

    If the parameter is to be hardcoded only for a set of tools, then a third column can be added. This column includes
    a comma-separated list of tool names for which the parameter will be hardcoded. If a third column is not included,
    then all processed tools containing the given parameter will get a hardcoded value for it.

    The following is an example of a valid file:

    ##################################### HARDCODED PARAMETERS example #####################################
    # Every line starting with a # will be handled as a comment and will not be parsed.
    # The first column is the name of the parameter and the second column is the value that will be used.

    # Parameter name            # Value                     # Tool(s)
    threads                     \${GALAXY_SLOTS:-24}
    mode                        quiet
    xtandem_executable          xtandem                     XTandemAdapter
    verbosity                   high                        Foo, Bar

    #########################################################################################################

    Using the above file will produce a <command> similar to:

    [tool_name] ... -threads \${GALAXY_SLOTS:-24} -mode quiet ...

    For all tools. For XTandemAdapter, the <command> will be similar to:

    XtandemAdapter ... -threads \${GALAXY_SLOTS:-24} -mode quiet -xtandem_executable xtandem ...

    And for tools Foo and Bar, the <command> will be similar to:

    Foo ... ... -threads \${GALAXY_SLOTS:-24} -mode quiet -verbosity high ...


    V - Control which tools will be converted

    Sometimes only a subset of CTDs needs to be converted. It is possible to either explicitly specify which tools will
    be converted or which tools will not be converted.

    The value of the -s/--skip-tools parameter is a file in which each line will be interpreted as the name of a tool
    that will not be converted. Conversely, the value of the -r/--required-tools is a file in which each line will be
    interpreted as a tool that is required. Only one of these parameters can be specified at a given time.

    The format of both files is exactly the same. As stated before, each line will be interpreted as the name of a tool;
    any line starting with a '#' will be ignored.

    '''
    program_license = '''%(short_description)s
    Copyright 2015, Luis de la Garza

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
    
    %(usage)s
''' % {'short_description': program_short_description, 'usage': program_usage}

    try:
        # Setup argument parser
        parser = ArgumentParser(prog="CTD2Galaxy", description=program_license,
                                formatter_class=RawDescriptionHelpFormatter, add_help=True)
        parser.add_argument("-i", "--input", dest="input_files", default=[], required=True, nargs="+", action="append",
                            help="List of CTD files to convert.")
        parser.add_argument("-o", "--output-destination", dest="output_destination", required=True,
                            help="If multiple input files are given, then a folder in which all generated "
                                 "XMLs will be generated is expected;"
                                 "if a single input file is given, then a destination file is expected.")
        parser.add_argument("-f", "--formats-file", dest="formats_file",
                            help="File containing the supported file formats. Run with '-h' or '--help' to see a "
                                 "brief example on the layout of this file.", default=None, required=False)
        parser.add_argument("-a", "--add-to-command-line", dest="add_to_command_line",
                            help="Adds content to the command line", default="", required=False)
        parser.add_argument("-d", "--datatypes-destination", dest="data_types_destination",
                            help="Specify the location of a datatypes_conf.xml to modify and add the registered "
                                 "data types. If the provided destination does not exist, a new file will be created.",
                            default=None, required=False)
        parser.add_argument("-x", "--default-executable-path", dest="default_executable_path",
                            help="Use this executable path when <executablePath> is not present in the CTD",
                            default=None, required=False)
        parser.add_argument("-b", "--blacklist-parameters", dest="blacklisted_parameters", default=[], nargs="+", action="append",
                            help="List of parameters that will be ignored and won't appear on the galaxy stub",
                            required=False)
        parser.add_argument("-c", "--default-category", dest="default_category", default="DEFAULT", required=False,
                            help="Default category to use for tools lacking a category when generating tool_conf.xml")
        parser.add_argument("-t", "--tool-conf-destination", dest="tool_conf_destination", default=None, required=False,
                            help="Specify the location of an existing tool_conf.xml that will be modified to include "
                                 "the converted tools. If the provided destination does not exist, a new file will"
                                 "be created.")
        parser.add_argument("-g", "--galaxy-tool-path", dest="galaxy_tool_path", default=None, required=False,
                            help="The path that will be prepended to the file names when generating tool_conf.xml")
        parser.add_argument("-r", "--required-tools", dest="required_tools_file", default=None, required=False,
                            help="Each line of the file will be interpreted as a tool name that needs translation. "
                                 "Run with '-h' or '--help' to see a brief example on the format of this file.")
        parser.add_argument("-s", "--skip-tools", dest="skip_tools_file", default=None, required=False,
                            help="File containing a list of tools for which a Galaxy stub will not be generated. "
                                 "Run with '-h' or '--help' to see a brief example on the format of this file.")
        parser.add_argument("-m", "--macros", dest="macros_files", default=[], nargs="+", action="append",
                            help="Import the additional given file(s) as macros. The macros stdio, requirements and"
                                 "advanced_options are required. Please see sample_files/macros.xml for an example"
                                 "of a valid macros file. All defined macros will be imported.",
                            required=True)
        parser.add_argument("-p", "--hardcoded-parameters", dest="hardcoded_parameters", default=None, required=False,
                            help="File containing hardcoded values for the given parameters. Run with '-h' or '--help' "
                                 "to see a brief example on the format of this file.")
        # TODO: add verbosity, maybe?
        parser.add_argument("-V", "--version", action='version', version=program_version_message)

        # Process arguments
        args = parser.parse_args()
        
        # validate and prepare the passed arguments
        validate_and_prepare_args(args)

        # extract the names of the macros and check that we have found the ones we need
        macros_file_names = args.macros_files
        macros_to_expand = parse_macros_files(macros_file_names)

        # parse the given supported file-formats file
        supported_file_formats = parse_file_formats(args.formats_file)

        # parse the hardcoded parameters file¬
        parameter_hardcoder = parse_hardcoded_parameters(args.hardcoded_parameters)

        # parse the skip/required tools files
        skip_tools = parse_tools_list_file(args.skip_tools_file)
        required_tools = parse_tools_list_file(args.required_tools_file)
        
        #if verbose > 0:
        #    print("Verbose mode on")
        parsed_models = convert(args.input_files,
                                args.output_destination,
                                supported_file_formats=supported_file_formats,
                                default_executable_path=args.default_executable_path,
                                add_to_command_line=args.add_to_command_line,
                                blacklisted_parameters=args.blacklisted_parameters,
                                required_tools=required_tools,
                                skip_tools=skip_tools,
                                macros_file_names=macros_file_names,
                                macros_to_expand=macros_to_expand,
                                parameter_hardcoder=parameter_hardcoder)

        #TODO: add some sort of warning if a macro that doesn't exist is to be expanded

        # it is not needed to copy the macros files, since the user has provided them

        # generation of galaxy stubs is ready... now, let's see if we need to generate a tool_conf.xml
        if args.tool_conf_destination is not None:
            generate_tool_conf(parsed_models, args.tool_conf_destination,
                               args.galaxy_tool_path, args.default_category)

        # now datatypes_conf.xml
        if args.data_types_destination is not None:
            generate_data_type_conf(supported_file_formats, args.data_types_destination)

        return 0

    except KeyboardInterrupt:
        # handle keyboard interrupt
        return 0
    except ApplicationException, e:
        error("CTD2Galaxy could not complete the requested operation.", 0)
        error("Reason: " + e.msg, 0)
        return 1
    except ModelError, e:
        error("There seems to be a problem with one of your input CTDs.", 0)
        error("Reason: " + e.msg, 0)
        return 1
    except Exception, e:
        traceback.print_exc()
        return 2


def parse_tools_list_file(tools_list_file):
    tools_list = None
    if tools_list_file is not None:
        tools_list = []
        with open(tools_list_file) as f:
            for line in f:
                if line is None or not line.strip() or line.strip().startswith("#"):
                    continue
                else:
                    tools_list.append(line.strip())

    return tools_list


def parse_macros_files(macros_file_names):
    macros_to_expand = set()

    for macros_file_name in macros_file_names:
        try:
            macros_file = open(macros_file_name)
            root = parse(macros_file).getroot()
            for xml_element in root.findall("xml"):
                name = xml_element.attrib["name"]
                if name in macros_to_expand:
                    warning("Macro %s has already been found. Duplicate found in file %s." %
                            (name, macros_file_name), 0)
                else:
                    macros_to_expand.add(name)
        except ParseError, e:
            raise ApplicationException("The macros file " + macros_file_name + " could not be parsed. Cause: " +
                                       str(e))
        except IOError, e:
            raise ApplicationException("The macros file " + macros_file_name + " could not be opened. Cause: " +
                                       str(e))

    # we depend on "stdio", "requirements" and "advanced_options" to exist on all the given macros files
    missing_needed_macros = []
    for required_macro in REQUIRED_MACROS:
        if required_macro not in macros_to_expand:
            missing_needed_macros.append(required_macro)

    if missing_needed_macros:
        raise ApplicationException(
            "The following required macro(s) were not found in any of the given macros files: %s, "
            "see sample_files/macros.xml for an example of a valid macros file."
            % ", ".join(missing_needed_macros))

    # we do not need to "expand" the advanced_options macro
    macros_to_expand.remove(ADVANCED_OPTIONS_MACRO_NAME)
    return macros_to_expand

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


def parse_file_formats(formats_file):
    supported_formats = {}
    if formats_file is not None:
        line_number = 0
        with open(formats_file) as f:
            for line in f:
                line_number += 1
                if line is None or not line.strip() or line.strip().startswith("#"):
                    # ignore (it'd be weird to have something like:
                    # if line is not None and not (not line.strip()) ...
                    pass
                else:
                    # not an empty line, no comment
                    # strip the line and split by whitespace
                    parsed_formats = line.strip().split()
                    # valid lines contain either one or four columns
                    if not (len(parsed_formats) == 1 or len(parsed_formats) == 3 or len(parsed_formats) == 4):
                        warning("Invalid line at line number %d of the given formats file. Line will be ignored:\n%s" %
                                (line_number, line), 0)
                        # ignore the line
                        continue
                    elif len(parsed_formats) == 1:
                        supported_formats[parsed_formats[0]] = DataType(parsed_formats[0], parsed_formats[0])
                    else:
                        mimetype = None
                        # check if mimetype was provided
                        if len(parsed_formats) == 4:
                            mimetype = parsed_formats[3]
                        supported_formats[parsed_formats[0]] = DataType(parsed_formats[0], parsed_formats[1],
                                                                        parsed_formats[2], mimetype)
    return supported_formats


def validate_and_prepare_args(args):
    # check that only one of skip_tools_file and required_tools_file has been provided
    if args.skip_tools_file is not None and args.required_tools_file is not None:
        raise ApplicationException(
            "You have provided both a file with tools to ignore and a file with required tools.\n"
            "Only one of -s/--skip-tools, -r/--required-tools can be provided.")

    # first, we convert all list of lists in args to flat lists
    lists_to_flatten = ["input_files", "blacklisted_parameters", "macros_files"]
    for list_to_flatten in lists_to_flatten:
        setattr(args, list_to_flatten, [item for sub_list in getattr(args, list_to_flatten) for item in sub_list])

    # if input is a single file, we expect output to be a file (and not a dir that already exists)
    if len(args.input_files) == 1:
        if os.path.isdir(args.output_destination):
            raise ApplicationException("If a single input file is provided, output (%s) is expected to be a file "
                                       "and not a folder.\n" % args.output_destination)
        
    # if input is a list of files, we expect output to be a folder
    if len(args.input_files) > 1:
        if not os.path.isdir(args.output_destination):
            raise ApplicationException("If several input files are provided, output (%s) is expected to be an "
                                       "existing directory.\n" % args.output_destination)

    # check that the provided input files, if provided, contain a valid file path
    input_variables_to_check = ["skip_tools_file", "required_tools_file", "macros_files",
                                "input_files", "formats_file", "hardcoded_parameters"]

    for variable_name in input_variables_to_check:
        paths_to_check = []
        # check if we are handling a single file or a list of files
        member_value = getattr(args, variable_name)
        if member_value is not None:
            if isinstance(member_value, list):
                for file_name in member_value:
                    paths_to_check.append(strip(str(file_name)))
            else:
                paths_to_check.append(strip(str(member_value)))

            for path_to_check in paths_to_check:
                if not os.path.isfile(path_to_check) or not os.path.exists(path_to_check):
                    raise ApplicationException(
                        "The provided input file (%s) does not exist or is not a valid file path."
                        % path_to_check)

    # check that the provided output files, if provided, contain a valid file path (i.e., not a folder)
    output_variables_to_check = ["data_types_destination", "tool_conf_destination"]

    for variable_name in output_variables_to_check:
        file_name = getattr(args, variable_name)
        if file_name is not None and os.path.isdir(file_name):
            raise ApplicationException("The provided output file name (%s) points to a directory." % file_name)


def convert(input_files, output_destination, **kwargs):
    # first, generate a model
    is_converting_multiple_ctds = len(input_files) > 1 
    parsed_models = []
    for input_file in input_files:
        try:
            model = CTDModel(from_file=input_file)
        except Exception, e:
            error(str(e), 1)
            continue

        if kwargs["skip_tools"] is not None and model.name in kwargs["skip_tools"]:
            info("Skipping tool %s" % model.name, 0)
            continue
        elif kwargs["required_tools"] is not None and model.name not in kwargs["required_tools"]:
            info("Tool %s is not required, skipping it" % model.name, 0)
            continue
        else:
            info("Converting from %s " % input_file, 0)
            tool = create_tool(model)
            write_header(tool, model)
            create_description(tool, model)
            expand_macros(tool, model, **kwargs)
            create_command(tool, model, **kwargs)
            create_inputs(tool, model, **kwargs)
            create_outputs(tool, model, **kwargs)
            create_help(tool, model)

            # finally, serialize the tool
            output_file = output_destination
            # if multiple inputs are being converted,
            # then we need to generate a different output_file for each input
            if is_converting_multiple_ctds:
                output_file = os.path.join(output_file, get_filename_without_suffix(input_file) + ".xml")
            # wrap our tool element into a tree to be able to serialize it
            tree = ElementTree(tool)
            tree.write(open(output_file, 'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
            # let's use model to hold the name of the output file
            parsed_models.append([model, get_filename(output_file)])

    return parsed_models


def write_header(tool, model):
    tool.addprevious(etree.Comment(
        "This is a configuration file for the integration of a tools into Galaxy (https://galaxyproject.org/). "
        "This file was automatically generated using CTD2Galaxy."))
    tool.addprevious(etree.Comment('Proposed Tool Section: [%s]' % model.opt_attribs.get("category", "")))


def generate_tool_conf(parsed_models, tool_conf_destination, galaxy_tool_path, default_category):
    # for each category, we keep a list of models corresponding to it
    categories_to_tools = dict()
    for model in parsed_models:
        category = strip(model[0].opt_attribs.get("category", ""))
        if not category.strip():
            category = default_category
        if category not in categories_to_tools:
            categories_to_tools[category] = []
        categories_to_tools[category].append(model[1])
                
    # at this point, we should have a map for all categories->tools
    toolbox_node = Element("toolbox")
    
    if galaxy_tool_path is not None and not galaxy_tool_path.strip().endswith("/"):
        galaxy_tool_path = galaxy_tool_path.strip() + "/"
    if galaxy_tool_path is None:
        galaxy_tool_path = ""
    
    for category, file_names in categories_to_tools.iteritems():
        section_node = add_child_node(toolbox_node, "section")
        section_node.attrib["id"] = "section-id-" + "".join(category.split())
        section_node.attrib["name"] = category
    
        for filename in file_names:
            tool_node = add_child_node(section_node, "tool")
            tool_node.attrib["file"] = galaxy_tool_path + filename

    toolconf_tree = ElementTree(toolbox_node)
    toolconf_tree.write(open(tool_conf_destination,'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    info("Generated Galaxy tool_conf.xml in %s" % tool_conf_destination, 0)


def generate_data_type_conf(supported_file_formats, data_types_destination):
    data_types_node = Element("datatypes")
    registration_node = add_child_node(data_types_node, "registration")
    registration_node.attrib["converters_path"] = "lib/galaxy/datatypes/converters"
    registration_node.attrib["display_path"] = "display_applications"

    for format_name in supported_file_formats:
        data_type = supported_file_formats[format_name]
        # add only if it's a data type that does not exist in Galaxy
        if data_type.galaxy_type is not None:
            data_type_node = add_child_node(registration_node, "datatype")
            # we know galaxy_extension is not None
            data_type_node.attrib["extension"] = data_type.galaxy_extension
            data_type_node.attrib["type"] = data_type.galaxy_type
            if data_type.mimetype is not None:
                data_type_node.attrib["mimetype"] = data_type.mimetype

    data_types_tree = ElementTree(data_types_node)
    data_types_tree.write(open(data_types_destination,'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    info("Generated Galaxy datatypes_conf.xml in %s" % data_types_destination, 0)


# taken from
# http://stackoverflow.com/questions/8384737/python-extract-file-name-from-path-no-matter-what-the-os-path-format
def get_filename(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def get_filename_without_suffix(path):
    root, ext = os.path.splitext(os.path.basename(path))
    return root 


def create_tool(model):
    return Element("tool", OrderedDict([("id", model.name), ("name", model.name), ("version", model.version)]))


def create_description(tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description = SubElement(tool,"description")
        description.text = model.opt_attribs["description"]


def get_param_name(param):
    if type(param.parent) == ParameterGroup and param.parent.name != '1':
        return get_param_name(param.parent) + ":" + param.name
    else:
        return param.name


def create_command(tool, model, **kwargs):
    final_command = get_tool_executable_path(model, kwargs["default_executable_path"]) + '\n'
    final_command += kwargs["add_to_command_line"] + '\n'
    advanced_command_start = "#if $adv_opts.adv_opts_selector=='advanced':\n"
    advanced_command_end = '#end if'
    advanced_command = ''
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    found_output_parameter = False
    for param in extract_parameters(model):
        if param.type is _OutFile:
            found_output_parameter = True
        command = ''
        param_name = get_param_name(param)

        if param.name in kwargs["blacklisted_parameters"]:
            continue

        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param_name, model.name)
        if hardcoded_value:
            command += '-%s %s\n' % (param_name, hardcoded_value)
        else:
            # parameter is neither blacklisted nor hardcoded...
            galaxy_parameter_name = get_galaxy_parameter_name(param)
            repeat_galaxy_parameter_name = get_repeat_galaxy_parameter_name(param)

            # logic for ITEMLISTs
            if param.is_list:
                if param.type is _InFile:
                    command += "-" + str(param_name) + "\n"
                    command += "  #for token in $" + galaxy_parameter_name + ":\n" 
                    command += "    $token\n"
                    command += "  #end for\n" 
                else:
                    command += "\n#if $" + repeat_galaxy_parameter_name + ":\n"
                    command += "-" + str(param_name) + "\n"
                    command += "  #for token in $" + repeat_galaxy_parameter_name + ":\n" 
                    command += "    #if \" \" in str(token):\n"
                    command += "      \"$token." + galaxy_parameter_name + "\"\n"
                    command += "    #else\n"
                    command += "      $token." + galaxy_parameter_name + "\n"
                    command += "    #end if\n"
                    command += "  #end for\n" 
                    command += "#end if\n" 
            # logic for other ITEMs 
            else:
                if param.advanced and param.type is not _OutFile:
                    actual_parameter = "$adv_opts.%s" % galaxy_parameter_name
                else:
                    actual_parameter = "$%s" % galaxy_parameter_name
                ## if whitespace_validation has been set, we need to generate, for each parameter:
                ## #if str( $t ).split() != '':
                ## -t "$t"
                ## #end if
                ## TODO only useful for text fields, integers or floats
                ## not useful for choices, input fields ...

                if not is_boolean_parameter(param) and type(param.restrictions) is _Choices :
                    command += "#if " + actual_parameter + ":\n"
                    command += '  -%s\n' % param_name
                    command += "  #if \" \" in str(" + actual_parameter + "):\n"
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "  #else\n"
                    command += "    " + actual_parameter + "\n"
                    command += "  #end if\n"
                    command += "#end if\n" 
                elif is_boolean_parameter(param):
                    command += "#if " + actual_parameter + ":\n"
                    command += '  -%s\n' % param_name
                    command += "#end if\n" 
                elif TYPE_TO_GALAXY_TYPE[param.type] is 'text':
                    command += "#if " + actual_parameter + ":\n"
                    command += "  -%s " % param_name
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "#end if\n" 
                else:
                    command += "#if " + actual_parameter + ":\n"
                    command += '  -%s ' % param_name
                    command += actual_parameter + "\n"
                    command += "#end if\n" 

        if param.advanced and param.type is not _OutFile:
            advanced_command += "    %s" % command
        else:
            final_command += command

    if advanced_command:
        final_command += "%s%s%s\n" % (advanced_command_start, advanced_command, advanced_command_end)

    if not found_output_parameter:
        final_command += "> $param_stdout\n" 

    command_node = add_child_node(tool, "command")
    command_node.text = final_command


# creates the xml elements needed to import the needed macros files
# and to "expand" the macros
def expand_macros(tool, model, **kwargs):
    macros_node = add_child_node(tool, "macros")
    token_node = add_child_node(macros_node, "token")
    token_node.attrib["name"] = "@EXECUTABLE@"
    token_node.text = get_tool_executable_path(model, kwargs["default_executable_path"])

    # add <import> nodes
    for macro_file_name in kwargs["macros_file_names"]:
        macro_file = open(macro_file_name)
        import_node = add_child_node(macros_node, "import")
        # do not add the path of the file, rather, just its basename
        import_node.text = os.path.basename(macro_file.name)

    # add <expand> nodes
    for expand_macro in kwargs["macros_to_expand"]:
        expand_node = add_child_node(tool, "expand")
        expand_node.attrib["macro"] = expand_macro


def get_tool_executable_path(model, default_executable_path):
    # rules to build the galaxy executable path:
    # if executablePath is null, then use default_executable_path and store it in executablePath
    # if executablePath is null and executableName is null, then the name of the tool will be used
    # if executablePath is null and executableName is not null, then executableName will be used
    # if executablePath is not null and executableName is null,
    #   then executablePath and the name of the tool will be used
    # if executablePath is not null and executableName is not null, then both will be used

    # first, check if the model has executablePath / executableName defined
    executable_path = model.opt_attribs.get("executablePath", None)
    executable_name = model.opt_attribs.get("executableName", None)

    # check if we need to use the default_executable_path
    if executable_path is None:
        executable_path = default_executable_path

    # fix the executablePath to make sure that there is a '/' in the end
    if executable_path is not None:
        executable_path = executable_path.strip()
        if not executable_path.endswith('/'):
            executable_path += '/'

    # assume that we have all information present
    command = str(executable_path) + str(executable_name)
    if executable_path is None:
        if executable_name is None:
            command = model.name
        else:
            command = executable_name
    else:
        if executable_name is None:
            command = executable_path + model.name
    return command


def get_galaxy_parameter_name(param):
    return "param_%s" % get_param_name(param).replace(':', '_').replace('-', '_')


def get_input_with_same_restrictions(out_param, model, supported_file_formats):
    for param in extract_parameters(model):
        if param.type is _InFile:
            if param.restrictions is not None:
                in_param_formats = get_supported_file_types(param.restrictions.formats, supported_file_formats)
                out_param_formats = get_supported_file_types(out_param.restrictions.formats, supported_file_formats)
                if in_param_formats == out_param_formats:
                    return param
                    

def create_inputs(tool, model, **kwargs):
    inputs_node = SubElement(tool, "inputs")

    # some suites (such as OpenMS) need some advanced options when handling inputs
    expand_advanced_node = add_child_node(tool, "expand", OrderedDict([("macro", ADVANCED_OPTIONS_MACRO_NAME)]))
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    # treat all non output-file parameters as inputs
    for param in extract_parameters(model):
        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param.name, model.name)
        if param.name in kwargs["blacklisted_parameters"] or hardcoded_value:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is not _OutFile:
            if param.advanced:
                if expand_advanced_node is not None:
                    parent_node = expand_advanced_node
                else:
                    # something went wrong... we are handling an advanced parameter and the
                    # advanced input macro was not set... inform the user about it
                    info("The parameter %s has been set as advanced, but advanced_input_macro has "
                         "not been set." % param.name, 1)
                    # there is not much we can do, other than use the inputs_node as a parent node!
                    parent_node = inputs_node
            else:
                parent_node = inputs_node

            # for lists we need a repeat tag
            if param.is_list and param.type is not _InFile:
                rep_node = add_child_node(parent_node, "repeat")
                create_repeat_attribute_list(rep_node, param)
                parent_node = rep_node

            param_node = add_child_node(parent_node, "param")
            create_param_attribute_list(param_node, param, kwargs["supported_file_formats"])

    # advanced parameter selection should be at the end
    # and only available if an advanced parameter exists
    if expand_advanced_node is not None and len(expand_advanced_node) > 0:
        inputs_node.append(expand_advanced_node)


def get_repeat_galaxy_parameter_name(param):
    return "rep_" + get_galaxy_parameter_name(param)


def create_repeat_attribute_list(rep_node, param):
    rep_node.attrib["name"] = get_repeat_galaxy_parameter_name(param)
    if param.required:
        rep_node.attrib["min"] = "1"
    else:
        rep_node.attrib["min"] = "0"
    # for the ITEMLISTs which have LISTITEM children we only
    # need one parameter as it is given as a string
    if param.default is not None: 
        rep_node.attrib["max"] = "1"
    rep_node.attrib["title"] = get_galaxy_parameter_name(param)


def create_param_attribute_list(param_node, param, supported_file_formats):
    param_node.attrib["name"] = get_galaxy_parameter_name(param)

    param_type = TYPE_TO_GALAXY_TYPE[param.type]
    if param_type is None:
        raise ModelError("Unrecognized parameter type %(type)s for parameter %(name)s"
                         % {"type": param.type, "name": param.name})

    if param.is_list:
        param_type = "text"

    if is_selection_parameter(param):
        param_type = "select"
        
    if is_boolean_parameter(param):
        param_type = "boolean"
        
    if param.type is _InFile:
        # assume it's just text unless restrictions are provided
        param_format = "text"
        if param.restrictions is not None:
            # join all supported_formats for the file... this MUST be a _FileFormat
            if type(param.restrictions) is _FileFormat: 
                param_format = ','.join(get_supported_file_types(param.restrictions.formats, supported_file_formats))
            else:
                raise InvalidModelException("Expected 'file type' restrictions for input file [%(name)s], "
                                            "but instead got [%(type)s]"
                                            % {"name": param.name, "type": type(param.restrictions)})
        param_node.attrib["type"] = "data"
        param_node.attrib["format"] = param_format
        # in the case of multiple input set multiple flag
        if param.is_list:
            param_node.attrib["multiple"] = "true"

    else:
        param_node.attrib["type"] = param_type

    # check for parameters with restricted values (which will correspond to a "select" in galaxy)
    if param.restrictions is not None:
        # it could be either _Choices or _NumericRange, with special case for boolean types
        if param_type == "boolean":
            create_boolean_parameter(param_node, param)
        elif type(param.restrictions) is _Choices:
            # create as many <option> elements as restriction values
            for choice in param.restrictions.choices:
                option_node = add_child_node(param_node, "option", OrderedDict([("value", str(choice))]))
                option_node.text = str(choice)

        elif type(param.restrictions) is _NumericRange:
            if param.type is not int and param.type is not float:
                raise InvalidModelException("Expected either 'int' or 'float' in the numeric range restriction for "
                                            "parameter [%(name)s], but instead got [%(type)s]" %
                                            {"name": param.name, "type": type(param.restrictions)})
            # extract the min and max values and add them as attributes
            # validate the provided min and max values
            if param.restrictions.n_min is not None:
                param_node.attrib["min"] = str(param.restrictions.n_min)
            if param.restrictions.n_max is not None:
                param_node.attrib["max"] = str(param.restrictions.n_max)
        elif type(param.restrictions) is _FileFormat:
            param_node.attrib["format"] = ",".join(
                get_supported_file_types(param.restrictions.formats, supported_file_formats))
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]"
                                        % {"type": type(param.restrictions), "name": param.name})

        param_node.attrib["optional"] = str(not param.required)

    if param_type == "text":
        # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
        param_node.attrib["size"] = "30"
        # add sanitizer nodes, this is needed for special character like "["
        # which are used for example by FeatureFinderMultiplex
        sanitizer_node = SubElement(param_node, "sanitizer")

        valid_node = SubElement(sanitizer_node, "valid", OrderedDict([("initial", "string.printable")]))
        add_child_node(valid_node, "remove", OrderedDict([("value", '\'')]))
        add_child_node(valid_node, "remove", OrderedDict([("value", '"')]))

    # check for default value
    if param.default is not None:
        if type(param.default) is list:
            # we ASSUME that a list of parameters looks like:
            # $ tool -ignore He Ar Xe
            # meaning, that, for example, Helium, Argon and Xenon will be ignored
            param_node.attrib["value"] = ' '.join(map(str, param.default))

        elif param_type != "boolean":
            # boolean parameters handle default values by using the "checked" attribute
            # there isn't much we can do... just stringify the value
            param_node.attrib["value"] = str(param.default)
    else:
        if param.type is int or param.type is float:
            # galaxy requires "value" to be included for int/float
            # since no default was included, we need to figure out one in a clever way... but let the user know
            # that we are "thinking" for him/her
            warning("Generating default value for parameter [%s]. "
                    "Galaxy requires the attribute 'value' to be set for integer/floats. "
                    "Edit the CTD file and provide a suitable default value." % param.name, 1)
            # check if there's a min/max and try to use them
            default_value = None
            if param.restrictions is not None:
                if type(param.restrictions) is _NumericRange:
                    default_value = param.restrictions.n_min
                    if default_value is None:
                        default_value = param.restrictions.n_max
                    if default_value is None:
                        # no min/max provided... just use 0 and see what happens
                        default_value = 0
                else:
                    # should never be here, since we have validated this anyway...
                    # this code is here just for documentation purposes
                    # however, better safe than sorry!
                    # (it could be that the code changes and then we have an ugly scenario)
                    raise InvalidModelException("Expected either a numeric range for parameter [%(name)s], "
                                                "but instead got [%(type)s]"
                                                % {"name": param.name, "type": type(param.restrictions)})
            else:
                # no restrictions and no default value provided...
                # make up something
                default_value = 0
            param_node.attrib["value"] = str(default_value)

    label = "%s parameter" % param.name
    help_text = ""

    if param.description is not None:
        label, help_text = generate_label_and_help(param.description)

    param_node.attrib["label"] = label
    param_node.attrib["help"] = "(-%s)" % param.name + " " + help_text


def generate_label_and_help(desc):
    label = ""
    help_text = ""
    # This tag is found in some descriptions 
    desc = str(desc).replace("#br#", " <br>")
    # Get rid of dots in the end
    if desc.endswith("."):
        desc = desc.rstrip(".")
    # Check if first word is a normal word and make it uppercase
    if str(desc).find(" ") > -1:
        first_word, rest = str(desc).split(" ", 1)
        if str(first_word).islower():
            # check if label has a quotient of the form a/b 
            if first_word.find("/") != 1 :
                first_word.capitalize()
        desc = first_word + " " + rest
    label = desc
    
    # Try to split the label if it is too long    
    if len(desc) > 50:
        # find an example and put everything before in the label and the e.g. in the help
        if desc.find("e.g.") > 1 :
            label, help_text = desc.split("e.g.",1)
            help_text = "e.g." + help_text
        else:
            # find the end of the first sentence
            # look for ". " because some labels contain .file or something similar
            delimiter = ""
            if desc.find(". ") > 1 and desc.find("? ") > 1:
                if desc.find(". ") < desc.find("? "):
                    delimiter = ". "
                else:
                    delimiter = "? "
            elif desc.find(". ") > 1:
                delimiter = ". "
            elif desc.find("? ") > 1:
                delimiter = "? "
            if delimiter != "":
                label, help_text = desc.split(delimiter, 1)

            # add the question mark back
            if delimiter == "? ":
                label += "? "
    
    # remove all linebreaks
    label = label.rstrip().rstrip('<br>').rstrip()
    return label, help_text


def get_indented_text(text, indentation_level):
    return ("%(indentation)s%(text)s" %
            {"indentation": "  " * (MESSAGE_INDENTATION_INCREMENT * indentation_level),
             "text": text})


def warning(warning_text, indentation_level):
    sys.stdout.write(get_indented_text("WARNING: %s\n" % warning_text, indentation_level))


def error(error_text, indentation_level):
    sys.stderr.write(get_indented_text("ERROR: %s\n" % error_text, indentation_level))


def info(info_text, indentation_level):
    sys.stdout.write(get_indented_text("INFO: %s\n" % info_text, indentation_level))


# determines if the given choices are boolean (basically, if the possible values are yes/no, true/false)
def is_boolean_parameter(param):
    is_choices = False
    if type(param.restrictions) is _Choices:
        # for a true boolean experience, we need 2 values
        # and also that those two values are either yes/no or true/false
        if len(param.restrictions.choices) == 2:
            choices = get_lowercase_list(param.restrictions.choices)
            if ("yes" in choices and "no" in choices) or ("true" in choices and "false" in choices):
                is_choices = True
    return is_choices


# determines if there are choices for the parameter
def is_selection_parameter(param):
    return type(param.restrictions) is _Choices


def get_lowercase_list(some_list):
    lowercase_list = map(str, some_list)
    lowercase_list = map(string.lower, lowercase_list)
    lowercase_list = map(strip, lowercase_list)
    return lowercase_list


# creates a galaxy boolean parameter type
# this method assumes that param has restrictions, and that only two restictions are present
# (either yes/no or true/false)
def create_boolean_parameter(param_node, param):
    # first, determine the 'truevalue' and the 'falsevalue'
    """TODO: true and false values can be way more than 'true' and 'false'
        but for that we need CTD support
    """
    # by default, 'true' and 'false' are handled as flags, like the verbose flag (i.e., -v)
    true_value = "-%s" % get_param_name(param)
    false_value = ""
    choices = get_lowercase_list(param.restrictions.choices)
    if "yes" in choices:
        true_value = "yes"
        false_value = "no"
    param_node.attrib["truevalue"] = true_value
    param_node.attrib["falsevalue"] = false_value

    # set the checked attribute
    if param.default is not None:
        checked_value = "false"
        default = strip(string.lower(param.default))
        if default == "yes" or default == "true":
            checked_value = "true"
        #attribute_list["checked"] = checked_value
        param_node.attrib["checked"] = checked_value


def create_outputs(parent, model, **kwargs):
    outputs_node = add_child_node(parent, "outputs")
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    for param in extract_parameters(model):

        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param.name, model.name)
        if param.name in kwargs["blacklisted_parameters"] or hardcoded_value:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            create_output_node(outputs_node, param, model, kwargs["supported_file_formats"])

    # If there are no outputs defined in the ctd the node will have no children
    # and the stdout will be used as output
    if len(outputs_node) == 0:
        add_child_node(outputs_node, "data",
                       OrderedDict([("name", "param_stdout"), ("format", "text"), ("label", "Output from stdout")]))


def create_output_node(parent, param, model, supported_file_formats):
    data_node = add_child_node(parent, "data")
    data_node.attrib["name"] = get_galaxy_parameter_name(param)

    data_format = "data"
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            # set the first data output node to the first file format

            # check if there are formats that have not been registered yet...
            output = ""
            for format_name in param.restrictions.formats:
                if not format_name in supported_file_formats.keys():
                    output += " " + str(format_name)

            # warn only if there's about to complain
            if output:
                warning("Parameter " + param.name + " has the following unsupported format(s):" + output, 1)

            formats = get_supported_file_types(param.restrictions.formats, supported_file_formats)
            try:
                data_format = formats.pop()
            except KeyError:
                # there is not much we can do, other than catching the exception
                pass
            # if there are more than one output file formats try to take the format from the input parameter
            if formats:
                corresponding_input = get_input_with_same_restrictions(param, model, supported_file_formats)
                if corresponding_input is not None:
                    data_format = "input"
                    data_node.attrib["metadata_source"] = get_galaxy_parameter_name(corresponding_input)
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] "
                                        "for output [%(name)s]" % {"type": type(param.restrictions),
                                                                   "name": param.name})
    data_node.attrib["format"] = data_format

    #TODO: find a smarter label ?
    #if param.description is not None:
    #    data_node.setAttribute("label", param.description)
    return data_node


def get_supported_file_types(formats, supported_file_formats):
    return set([supported_file_formats.get(format_name, DataType(format_name, format_name)).galaxy_extension
               for format_name in formats if format_name in supported_file_formats.keys()])


def create_change_format_node(parent, data_formats, input_ref):
    #  <change_format>
    #    <when input="secondary_structure" value="true" format="text"/>
    #  </change_format>
    change_format_node = add_child_node(parent, "change_format")
    for data_format in data_formats:
        add_child_node(change_format_node, "when",
                       OrderedDict([("input", input_ref), ("value", data_format), ("format", data_format)]))


# Shows basic information about the file, such as data ranges and file type.
def create_help(tool, model):
    manual = ''
    doc_url = None
    if 'manual' in model.opt_attribs.keys(): 
        manual += '%s\n\n' % model.opt_attribs["manual"]
    if 'docurl' in model.opt_attribs.keys():
        doc_url = model.opt_attribs["docurl"]

    help_text = "No help available"
    if manual is not None:
        help_text = manual
    if doc_url is not None:
        help_text = ("" if manual is None else manual) + "\nFor more information, visit %s" % doc_url
    help_node = add_child_node(tool, "help")
    # TODO: do we need CDATA Section here?
    help_node.text = help_text


# since a model might contain several ParameterGroup elements,
# we want to simply 'flatten' the parameters to generate the Galaxy wrapper
def extract_parameters(model):
    parameters = []
    if len(model.parameters.parameters) > 0:
        # use this to put parameters that are to be processed
        # we know that CTDModel has one parent ParameterGroup
        pending = [model.parameters]
        while len(pending) > 0:
            # take one element from 'pending'
            parameter = pending.pop()
            if type(parameter) is not ParameterGroup:
                parameters.append(parameter)
            else:
                # append the first-level children of this ParameterGroup
                pending.extend(parameter.parameters.values()) 
    # returned the reversed list of parameters (as it is now,
    # we have the last parameter in the CTD as first in the list)
    return reversed(parameters)


# adds and returns a child node using the given name to the given parent node
def add_child_node(parent_node, child_node_name, attributes=OrderedDict([])):
    child_node = SubElement(parent_node, child_node_name, attributes)
    return child_node


if __name__ == "__main__":
    sys.exit(main())
