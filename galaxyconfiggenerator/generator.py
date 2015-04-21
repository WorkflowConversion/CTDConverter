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
from CTDopts.CTDopts import CTDModel, _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, _FileFormat, ModelError, \
    ModelParsingError
from collections import OrderedDict
from string import strip
from xml.dom.minidom import Document

__all__ = []
__version__ = 0.11
__date__ = '2014-09-17'
__updated__ = '2015-01-23'

MESSAGE_INDENTATION_INCREMENT = 2

TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data', 
                       _OutFile: 'data', _Choices: 'select'}
COMMAND_REPLACE_PARAMS = {'threads': '\${GALAXY_SLOTS:-24} ', "processOption": "inmemory"}


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
    def __init__(self, extension, galaxy_extension=None, galaxy_type=None, subclass=None):
        self.extension = extension
        self.galaxy_extension = galaxy_extension
        self.galaxy_type = galaxy_type
        self.subclass = subclass

    #TODO: do we need these after all?
    def __hash__(self):
        return self.extension.__hash__()

    def __cmp__(self, other):
        return self.extension.__cmp__(other.extension)

    def __eq__(self, other):
        return self.extension.__eq__(other.extesion)


def main(argv=None):  # IGNORE:C0111
    # Command line options.
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_short_description = "GalaxyConfigGenerator - A project from the GenericWorkflowNodes family " \
                                "(https://github.com/orgs/genericworkflownodes)"
    program_usage = '''
    USAGE:
    
    Parsing a single CTD file and generate a Galaxy wrapper:

    $ python generator.py -i input.ctd -o output.xml
    

    Parsing all found CTD files (files with .ctd and .xml extension) in a given folder and
    output converted Galaxy wrappers in a given folder:

    $ python generator.py -i /home/user/*.ctd -o /home/user/galaxywrappers

    Galaxy supports the concept of file format in order to connect compatible ports, that is, input ports of a certain
    data format will be able to receive data from a port from the same format. This converter allows you to provide
    a personalized file in which you can relate the CTD data formats with supported Galaxy data formats. The layout of
    this file consists of lines, each of either one or four columns separated by any amount of whitespace. The content
    of each column is as follows:

    * 1st column: file extension
    * 2nd column: data type, as listed in Galaxy
    * 3rd column: full-named Galaxy data type, as it will appear on datatypes_conf.xml
    * 4th column: whether the given data type is a subclass of other Galaxy data types

    The following is an example of a valid "file formats" file:

    ########################################## FILE FORMATS example ##########################################
    # Every line starting with a # will be handled as a comment and will not be parsed.
    # The first column is the file format as given in the CTD and second column is the Galaxy data format.
    # The second, third and fourth column can be left empty if the data type has already been registered in Galaxy,
    # otherwise, they all must be provided.

    # CTD data type       # Short Galaxy data type      # Long Galaxy data type             # Sublcass
    csv                   tabular                       galaxy.datatypes.data:Text          true
    fasta
    ini                   txt                           galaxy.datatypes.data:Text          true
    txt
    xds                   txt                           galaxy.datatypes.data:Text          true
    options               txt                           galaxy.datatypes.data:Text          true
    grid                  grid                          galaxy.datatypes.data:Grid          false

    ##########################################################################################################

    Note that each line consists precisely of either one column or four. In the case of data types already registered
    in Galaxy (such as fasta and txt in the above example), only the first column is needed. In the case of data types
    that haven't been yet registered in Galaxy, all four columns are needed.

    For information about Galaxy data types and subclasses, see the following page:
    https://wiki.galaxyproject.org/Admin/Datatypes/Adding%20Datatypes

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
        parser = ArgumentParser(prog="GalaxyConfigGenerator", description=program_license,
                                formatter_class=RawDescriptionHelpFormatter, add_help=True)
        parser.add_argument("-i", "--input", dest="input_files", default=[], required=True, nargs="+", action="append",
                            help="List of CTD files to convert.")
        parser.add_argument("-o", "--output-destination", dest="output_destination", required=True,
                            help="If multiple input files are given, then a folder in which all generated "
                                 "XMLs will be generated is expected;"
                                 "if a single input file is given, then a destination file is expected.")
        parser.add_argument("-f", "--formats-file", dest="formats_file",
                            help="File containing the supported file formats. Run with '-h' or '--help' to to see a "
                                 "brief example on the layout of this file.", default=None, required=False)
        parser.add_argument("-a", "--add-to-command-line", dest="add_to_command_line",
                            help="Adds content to the command line", default="", required=False)
        parser.add_argument("-y", "--data-types-destination", dest="data_types_destination",
                            help="Specify the destination file of a generated datatypes_conf.xml",
                            default=None, required=False)
        parser.add_argument("-x", "--default-executable-path", dest="default_executable_path",
                            help="Use this executable path when <executablePath> is not present in the CTD",
                            default=None, required=False)
        parser.add_argument("-w", "--whitespace-validation", dest="whitespace_validation", action="store_true",
                            default=False, required=False,
                            help="If true, each parameter in the generated command line will be " +
                                 "validated against emptiness or being equal to 'None'")
        parser.add_argument("-q", "--quote-parameters", dest="quote_parameters", action="store_true", default=False,
                            help="If true, each parameter in the generated command line will be quoted", required=False)
        parser.add_argument("-b", "--blacklist", dest="blacklisted_parameters", default=[], nargs="+", action="append",
                            help="List of parameters that will be ignored and won't appear on the galaxy stub",
                            required=False)
        parser.add_argument("-c", "--default-category", dest="default_category", default="DEFAULT", required=False,
                            help="Default category to use for tools lacking a category when generating tool_conf.xml")
        parser.add_argument("-t", "--tool-conf-destination", dest="tool_conf_destination", default=None, required=False,
                            help="Specify the destination file of a generated tool_conf.xml for all given input files; "
                                 "each category will be written in its own section.")
        parser.add_argument("-g", "--galaxy-tool-path", dest="galaxy_tool_path", default=None, required=False,
                            help="The path that will be prepended to the file names when generating tool_conf.xml")
        parser.add_argument("-l", "--tools-list-file", dest="tools_list_file", default=None, required=False,
                            help="Each line of the file will be interpreted as a tool name that needs translation.")
        parser.add_argument("-s", "--skip", dest="skip_tools", default=[], nargs="+", action="append",
                            help="List of tools for which a Galaxy stub will not be generated", required=False)
        parser.add_argument("-m", "--macros", dest="macros_files", default=[], nargs="+", action="append",
                            help="Import the given file(s) as macros.", required=False)
        parser.add_argument("-e", "--expand-macros", dest="expand_macros", default=[], nargs="+", action="append",
                            help="Expand the given macros.", required=False)
        parser.add_argument("-d", "--advanced-input-macro", dest="advanced_input_macro", default="",
                            help="Use the provided macro name to expand in the <input> section.", required=False)

        # verbosity will be added later on, will not waste time on this now
        # parser.add_argument("-v", "--verbose", dest="verbose", action="count",
        # help="set verbosity level [default: %(default)s]")
        parser.add_argument("-V", "--version", action='version', version=program_version_message)
        
        # Process arguments
        args = parser.parse_args()
        
        # validate and prepare the passed arguments
        validate_and_prepare_args(args)

        # parse the given supported file-formats file
        supported_file_formats = parse_file_formats(args.formats_file)
        
        #if verbose > 0:
        #    print("Verbose mode on")
        convert(args.input_files, 
                args.output_destination,
                supported_file_formats=supported_file_formats,
                default_executable_path=args.default_executable_path,
                data_types_destination=args.data_types_destination,
                add_to_command_line=args.add_to_command_line, 
                whitespace_validation=args.whitespace_validation,
                quote_parameters=args.quote_parameters,
                blacklisted_parameters=args.blacklisted_parameters,
                default_category=args.default_category,
                tool_conf_destination=args.tool_conf_destination,
                galaxy_tool_path=args.galaxy_tool_path,
                tools_list_file=args.tools_list_file,
                skip_tools=args.skip_tools,
                macros_files=args.macros_files,
                expand_macros=args.expand_macros,
                advanced_input_macro=args.advanced_input_macro)
        return 0

    except KeyboardInterrupt:
        # handle keyboard interrupt
        return 0
    except ApplicationException, e:
        error("GalaxyConfigGenerator could not complete the requested operation.", 0)
        error("Reason: " + e.msg, 0)
        return 1
    except ModelError, e:
        error("There seems to be a problem with one of your input CTDs.", 0)
        error("Reason: " + e.msg, 0)
        return 1
    except Exception, e:
        traceback.print_exc()
        return 2


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
                    parsed_formats = line.split()
                    # valid lines contain either one or four columns
                    if not (len(parsed_formats) == 1 or len(parsed_formats) == 4):
                        warning("Invalid line at line number %d of the given formats_file. Line will be ignored:" %
                                line_number, 0)
                        warning(line, 1)
                        # ignore the line
                        continue
                    elif len(parsed_formats) == 1:
                        supported_formats[parsed_formats[0]] = DataType(parsed_formats[0])
                    else:
                        supported_formats[parsed_formats[0]] = \
                            DataType(parsed_formats[0], parsed_formats[1], parsed_formats[2], parsed_formats[3])
    return supported_formats


def validate_and_prepare_args(args):
    # first, we convert all list of lists in args to flat lists
    lists_to_flatten = ["input_files", "blacklisted_parameters", "skip_tools", "expand_macros", "macros_files"]
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
    input_variables_to_check = ["tools_list_file", "macros_files", "input_files", "formats_file"]

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
    # if a file with a list of needed tools is given they are put in the tools list
    needed_tools = []
    if kwargs["tools_list_file"] is not None:
        try:
            with open(kwargs["tools_list_file"]) as f:
                for line in f:
                    needed_tools.append(line.rstrip())
        except IOError, e:
            error("The provided input file " + str(kwargs["tools_list_file"]) + " could not be accessed. "
                  "Detailed information: " + str(e), 0)
    # first, generate a model
    is_converting_multiple_ctds = len(input_files) > 1 
    parsed_models = []
    try:
        for input_file in input_files:
            tool_name = os.path.splitext(os.path.basename(input_file))[0]
            if tool_name in kwargs["skip_tools"] or \
                    (kwargs["tools_list_file"] is not None and tool_name not in needed_tools):
                info("Skipping tool %s" % tool_name, 0)
                continue
            else:
                info("Parsing CTD from file %s" % input_file, 0)
                try:
                    model = CTDModel(from_file=input_file)
                except Exception, e:
                    error(str(e), 1)
                    continue

                main_doc = Document()
                tool = create_tool(main_doc, model)
                create_description(main_doc, tool, model)
                create_macros(main_doc, tool, model, **kwargs)
                create_command(main_doc, tool, model, **kwargs)
                create_inputs(main_doc, tool, model, **kwargs)
                create_outputs(main_doc, tool, model, **kwargs)
                create_help(main_doc, tool, model)

                # finally, serialize the tool
                output_file = output_destination
                # if multiple inputs are being converted,
                # then we need to generate a different output_file for each input
                if is_converting_multiple_ctds:
                    #if not output_file.endswith('/'):
                    #    output_file += "/"
                    #output_file += get_filename(input_file) + ".xml"
                    output_file = os.path.join(output_file, get_filename_without_suffix(input_file) + ".xml")
                main_doc.writexml(open(output_file, 'w'), encoding="UTF-8", indent="  ", addindent="  ", newl="\n")
                # let's use model to hold the name of the output file
                parsed_models.append([model, get_filename(output_file)])

        # generation of galaxy stubs is ready... now, let's see if we need to generate a tool_conf.xml
        if kwargs["tool_conf_destination"] is not None:
            generate_tool_conf(parsed_models, kwargs["tool_conf_destination"],
                               kwargs["galaxy_tool_path"], kwargs["default_category"])
                
    except IOError, e:
        raise ApplicationException("One of the provided input files or the destination file could not be accessed. "
                                   "Detailed information: " + str(e) + "\n")


def generate_tool_conf(parsed_models, tool_conf_destination, galaxy_tool_path, default_category):
    # for each category, we keep a list of models corresponding to it
    categories_to_tools = dict()
    for model in parsed_models:
        category = strip(model[0].opt_attribs.get("category", default_category))
        if category not in categories_to_tools:
            categories_to_tools[category] = []
        categories_to_tools[category].append(model[1])
                
    # at this point, we should have a map for all categories->tools
    doc = Document()
    toolbox_node = add_child_node(doc, doc, "toolbox")
    
    if galaxy_tool_path is not None and not galaxy_tool_path.strip().endswith("/"):
        galaxy_tool_path = galaxy_tool_path.strip() + "/"
    if galaxy_tool_path is None:
        galaxy_tool_path = ""
    
    for category, file_names in categories_to_tools.iteritems():
        section_node = add_child_node(doc, toolbox_node, "section")
        section_node.setAttribute("id", "section-id-" + "".join(category.split()))
        section_node.setAttribute("name", category)
    
        for filename in file_names:
            tool_node = add_child_node(doc, section_node, "tool")
            tool_node.setAttribute("file", galaxy_tool_path + filename)

    doc.writexml(open(tool_conf_destination, 'w'), encoding="UTF-8", indent="  ", addindent="  ", newl="\n")

    info("Generated Galaxy tool_conf.xml in %s" % tool_conf_destination, 0)


#def generate_data_type_conf(data_types_destination):


# taken from
# http://stackoverflow.com/questions/8384737/python-extract-file-name-from-path-no-matter-what-the-os-path-format
def get_filename(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def get_filename_without_suffix(path):
    root, ext = os.path.splitext(os.path.basename(path))
    return root 


def create_tool(doc, model):
    tool = doc.createElement("tool")
    tool.setAttribute("name", model.name)
    tool.setAttribute("version", model.version)
    # use the same name of the tool... maybe a future version would contain a way to add a
    # specific ID?
    tool.setAttribute("id", model.name)
    doc.appendChild(tool)
    return tool


def create_description(doc, tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description = doc.createElement("description")
        description.appendChild(doc.createTextNode(model.opt_attribs["description"]))
        tool.appendChild(description)


def get_param_name(param):
    if type(param.parent) == ParameterGroup and param.parent.name != '1':
        return get_param_name(param.parent) + ":" + param.name
    else:
        return param.name


def create_command(doc, tool, model, **kwargs):
    final_command = get_tool_executable_path(model, kwargs["default_executable_path"]) + '\n'
    final_command += kwargs["add_to_command_line"] + '\n'
    whitespace_validation = kwargs["whitespace_validation"]
    quote_parameters = kwargs["quote_parameters"]

    advanced_command_start = "#if $adv_opts.adv_opts_selector=='advanced':\n"
    advanced_command_end = '#end if'
    advanced_command = ''

    found_output_parameter = False
    for param in extract_parameters(model):
        if param.type is _OutFile:
            found_output_parameter = True
        command = ''
        param_name = get_param_name(param)

        if param.name in kwargs["blacklisted_parameters"]:
            if param.name in COMMAND_REPLACE_PARAMS:
                # replace the param value with a hardcoded value, for example the GALAXY_SLOTS ENV
                command += '-%s %s\n' % (param_name, COMMAND_REPLACE_PARAMS[param.name])
            else:
                # let's not use an extra level of indentation and use NOP
                continue
        else:
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

        if param.advanced and param.name not in kwargs["blacklisted_parameters"] and param.type is not _OutFile:
            advanced_command += "    %s" % command
        else:
            final_command += command

    if advanced_command:
        final_command += "%s%s%s\n" % (advanced_command_start, advanced_command, advanced_command_end)

    if not found_output_parameter:
        final_command += "> $param_stdout\n" 

    command_node = add_child_node(doc, tool, "command")
    add_text_node(doc, command_node, final_command)


# creates the xml elements needed to import the needed macros files
# and to "expand" the macros
def create_macros(doc, tool, model, **kwargs):
    """
        <macros>
            <token name="@EXECUTABLE@">AppName</token>
            <import>macros.xml</import>
        </macros>
        <expand macro="stdio" />
        <expand macro="requirements" />
    """
    if len(kwargs["macros_files"]) > 0:
        macros_node = add_child_node(doc, tool, "macros")
        token_node = add_child_node(doc, macros_node, "token")
        token_node.setAttribute("name", "@EXECUTABLE@")
        add_text_node(doc, token_node, get_tool_executable_path(model, kwargs["default_executable_path"]))

        # add <import> nodes
        for macro_file in kwargs["macros_files"]:
            import_node = add_child_node(doc, macros_node, "import")
            # do not add the path of the file, rather, just its basename
            add_text_node(doc, import_node, os.path.basename(macro_file.name))

        # add <expand> nodes
        for expand_macro in kwargs["expand_macros"]:
            expand_node = add_child_node(doc, tool, "expand")
            expand_node.setAttribute("macro", expand_macro)


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

    command = None
    if executable_path is None:
        if executable_name is None:
            command = model.name
        else:
            command = executable_name
    else:
        if executable_name is None:
            command = executable_path + model.name
        else:
            command = executable_path + executable_name
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
                    

def create_inputs(doc, tool, model, **kwargs):
    inputs_node = doc.createElement("inputs")

    # some suites (such as OpenMS) need some advanced options when handling inputs
    advanced_input_macro = kwargs["advanced_input_macro"]
    expand_advanced_node = None
    if advanced_input_macro is not None and len(strip(advanced_input_macro)) > 0:
        expand_advanced_node = add_child_node(doc, tool, "expand")
        expand_advanced_node.setAttribute("macro", strip(advanced_input_macro))

    # treat all non output-file parameters as inputs
    for param in extract_parameters(model):
        if param.name in kwargs["blacklisted_parameters"]:
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
                rep_node = add_child_node(doc, parent_node, "repeat")
                create_repeat_attribute_list(rep_node, param)
                parent_node = rep_node

            param_node = add_child_node(doc, parent_node, "param")
            create_param_attribute_list(doc, param_node, param, kwargs["supported_file_formats"])

    # advanced parameter selection should be at the end
    # and only available if an advanced parameter exists
    if expand_advanced_node is not None and expand_advanced_node.hasChildNodes():
        inputs_node.appendChild(expand_advanced_node)

    tool.appendChild(inputs_node)


def get_repeat_galaxy_parameter_name(param):
    return "rep_" + get_galaxy_parameter_name(param)


def create_repeat_attribute_list(rep_node, param):
    rep_node.setAttribute("name", get_repeat_galaxy_parameter_name(param))
    if param.required:
        rep_node.setAttribute("min", "1")
    else:
        rep_node.setAttribute("min", "0")
    # for the ITEMLISTs which have LISTITEM children we only
    # need one parameter as it is given as a string
    if param.default is not None: 
        rep_node.setAttribute("max", "1")
    rep_node.setAttribute("title", get_galaxy_parameter_name(param))


def create_param_attribute_list(doc, param_node, param, supported_file_formats):
    param_node.setAttribute("name", get_galaxy_parameter_name(param))

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
        param_node.setAttribute("type", "data")
        param_node.setAttribute("format", param_format)
        # in the case of multiple input set multiple flag
        if param.is_list:
            param_node.setAttribute("multiple", "true")

    else:
        param_node.setAttribute("type", param_type)

    # check for parameters with restricted values (which will correspond to a "select" in galaxy)
    if param.restrictions is not None:
        # it could be either _Choices or _NumericRange, with special case for boolean types
        if param_type == "boolean":
            create_boolean_parameter(param_node, param)
        elif type(param.restrictions) is _Choices:
            # create as many <option> elements as restriction values
            for choice in param.restrictions.choices:
                #print str(choice)
                option_attribute_list = OrderedDict()
                option_attribute_list["value"] = str(choice)
                option_node = add_child_node(doc, param_node, "option")
                option_node.setAttribute("value", str(choice))
                add_text_node(doc, option_node, str(choice))

        elif type(param.restrictions) is _NumericRange:
            if param.type is not int and param.type is not float:
                raise InvalidModelException("Expected either 'int' or 'float' in the numeric range restriction for "
                                            "parameter [%(name)s], but instead got [%(type)s]" %
                                            {"name": param.name, "type": type(param.restrictions)})
            # extract the min and max values and add them as attributes
            # validate the provided min and max values
            if param.restrictions.n_min is not None:
                param_node.setAttribute("min", str(param.restrictions.n_min))
            if param.restrictions.n_max is not None:
                param_node.setAttribute("max", str(param.restrictions.n_max))
        elif type(param.restrictions) is _FileFormat:
            param_node.setAttribute("format", ",".join(
                get_supported_file_types(param.restrictions.formats, supported_file_formats)))
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]"
                                        % {"type": type(param.restrictions), "name": param.name})

        param_node.setAttribute("optional", str(not param.required))

    if param_type == "text":
        # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
        param_node.setAttribute("size", "30")
        # add sanitizer nodes, this is needed for special character like "["
        # which are used for example by FeatureFinderMultiplex
        sanitizer_node = doc.createElement("sanitizer")
        param_node.appendChild(sanitizer_node)

        valid_node = doc.createElement("valid")
        sanitizer_node.appendChild(valid_node)
        valid_node.setAttribute("initial", "string.printable")

        remove_node = doc.createElement("remove")
        valid_node.appendChild(remove_node)
        remove_node.setAttribute("value", "'")

        remove_node = doc.createElement("remove")
        valid_node.appendChild(remove_node)
        remove_node.setAttribute("value", "\"")

    # check for default value
    if param.default is not None:
        if type(param.default) is list:
            # we ASSUME that a list of parameters looks like:
            # $ tool -ignore He Ar Xe
            # meaning, that, for example, Helium, Argon and Xenon will be ignored
            param_node.setAttribute("value", ' '.join(map(str, param.default)))

        elif param_type != "boolean":
            # boolean parameters handle default values by using the "checked" attribute
            # there isn't much we can do... just stringify the value
            param_node.setAttribute("value", str(param.default))
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
            param_node.setAttribute("value", str(default_value))

    label = ""
    help_text = ""

    if param.description is not None:
        label, help_text = generate_label_and_help(param.description)
    else:
        label = "%s parameter" % param.name
    param_node.setAttribute("label", label)
    param_node.setAttribute("help", "(-%s)" % param.name + " " + help_text)


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
        first_word, rest = str(desc).split(" ",1)
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
    true_value = None
    false_value = None
    choices = get_lowercase_list(param.restrictions.choices)
    if "yes" in choices:
        true_value = "yes"
        false_value = "no"
    else:
        #truevalue = "-%s true"   % get_param_name(param)
        #falsevalue = "-%s false" % get_param_name(param)
        true_value = "-%s" % get_param_name(param)
        false_value = ""
    param_node.setAttribute("truevalue", true_value)
    param_node.setAttribute("falsevalue", false_value)

    # set the checked attribute
    if param.default is not None:
        checked_value = "false"
        default = strip(string.lower(param.default))
        if default == "yes" or default == "true":
            checked_value = "true"
        #attribute_list["checked"] = checked_value
        param_node.setAttribute("checked", checked_value)


def create_outputs(doc, parent, model, **kwargs):
    outputs_node = doc.createElement("outputs")
    parent.appendChild(outputs_node)

    for param in extract_parameters(model):
       
        if param.name in kwargs["blacklisted_parameters"]:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            create_output_node(doc, outputs_node, param, model, kwargs["supported_file_formats"])

    # If there are no outputs defined in the ctd the node will have no children
    # and the stdout will be used as output
    if not outputs_node.hasChildNodes():
        out_node = doc.createElement("data")
        outputs_node.appendChild(out_node)
        out_node.setAttribute("name", "param_stdout")
        out_node.setAttribute("format", "text")
        out_node.setAttribute("label", "Output from stdout")


def create_output_node(doc, parent, param, model, supported_file_formats):
    data_node = add_child_node(doc, parent, "data")
    data_node.setAttribute("name", get_galaxy_parameter_name(param))

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
                    data_node.setAttribute("metadata_source", get_galaxy_parameter_name(corresponding_input))
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] "
                                        "for output [%(name)s]" % {"type": type(param.restrictions),
                                                                   "name": param.name})
    data_node.setAttribute("format", data_format)

    #TODO: find a smarter label ?
    #if param.description is not None:
    #    data_node.setAttribute("label", param.description)
    return data_node


def get_supported_file_types(formats, supported_file_formats):
    #return {format_name: supported_file_formats}
    return set([supported_file_formats.get(format_name, DataType(format_name)).extension
               for format_name in formats if format_name in supported_file_formats.keys()])


def create_filter_node(doc, data_format):
    # <filter>'bam' in outputs</filter>
    filter_node = doc.createElement("filter")
    # param_out_type is hardcoded for the moment
    add_text_node(doc, filter_node, "'%s' in param_out_type" % data_format)
    return filter_node


def create_change_format_node(doc, parent, data_formats, input_ref):
    #  <change_format>
    #    <when input="secondary_structure" value="true" format="text"/>
    #  </change_format>
    change_format_node = doc.createElement("change_format")
    parent.appendChild(change_format_node)
    for data_format in data_formats:
        when_node = doc.createElement("when")
        change_format_node.appendChild(when_node)
        when_node.setAttribute("input", input_ref)
        when_node.setAttribute("value", data_format)
        when_node.setAttribute("format", data_format)


# Shows basic information about the file, such as data ranges and file type.
def create_help(doc, tool, model):
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
    help_node = add_child_node(doc, tool, "help")
    # TODO: do we need CDATA Section here?
    add_text_node(doc, help_node, help_text)


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
def add_child_node(doc, parent_node, child_node_name):
    child_node = doc.createElement(child_node_name)
    parent_node.appendChild(child_node)
    return child_node


# adds a text node to the given parent node
def add_text_node(doc, parent_node, text):
    # cannot be sure if the parameter is already a string or not
    text_node = doc.createTextNode(str(text))
    parent_node.appendChild(text_node)


if __name__ == "__main__":
    sys.exit(main())