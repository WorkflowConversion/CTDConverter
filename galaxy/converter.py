#!/usr/bin/env python
# encoding: utf-8
import os
import string

from collections import OrderedDict
from string import strip
from lxml import etree
from lxml.etree import SubElement, Element, ElementTree, ParseError, parse

from common import utils, logger
from common.exceptions import ApplicationException, InvalidModelException

from CTDopts.CTDopts import _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, _FileFormat, ModelError, _Null


TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data',
                       _OutFile: 'data', _Choices: 'select'}
STDIO_MACRO_NAME = "stdio"
REQUIREMENTS_MACRO_NAME = "requirements"
ADVANCED_OPTIONS_MACRO_NAME = "advanced_options"

REQUIRED_MACROS = [REQUIREMENTS_MACRO_NAME, STDIO_MACRO_NAME, ADVANCED_OPTIONS_MACRO_NAME]


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


def add_specific_args(parser):
    parser.add_argument("-f", "--formats-file", dest="formats_file",
                        help="File containing the supported file formats. Run with '-h' or '--help' to see a "
                             "brief example on the layout of this file.", default=None, required=False)
    parser.add_argument("-a", "--add-to-command-line", dest="add_to_command_line",
                    help="Adds content to the command line", default="", required=False)
    parser.add_argument("-d", "--datatypes-destination", dest="data_types_destination",
                    help="Specify the location of a datatypes_conf.xml to modify and add the registered "
                         "data types. If the provided destination does not exist, a new file will be created.",
                    default=None, required=False)
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
    parser.add_argument("-m", "--macros", dest="macros_files", default=[], nargs="*",
                    action="append", required=None, help="Import the additional given file(s) as macros. "
                                                         "The macros stdio, requirements and advanced_options are "
                                                         "required. Please see galaxy/macros.xml for an example of a "
                                                         "valid macros file. All defined macros will be imported.")


def convert_models(args, parsed_ctds):
        # validate and prepare the passed arguments
        validate_and_prepare_args(args)

        # extract the names of the macros and check that we have found the ones we need
        macros_to_expand = parse_macros_files(args.macros_files)

        # parse the given supported file-formats file
        supported_file_formats = parse_file_formats(args.formats_file)

        # parse the skip/required tools files
        skip_tools = parse_tools_list_file(args.skip_tools_file)
        required_tools = parse_tools_list_file(args.required_tools_file)
        
        _convert_internal(parsed_ctds,
                          supported_file_formats=supported_file_formats,
                          default_executable_path=args.default_executable_path,
                          add_to_command_line=args.add_to_command_line,
                          blacklisted_parameters=args.blacklisted_parameters,
                          required_tools=required_tools,
                          skip_tools=skip_tools,
                          macros_file_names=args.macros_files,
                          macros_to_expand=macros_to_expand,
                          parameter_hardcoder=args.parameter_hardcoder)

        # generation of galaxy stubs is ready... now, let's see if we need to generate a tool_conf.xml
        if args.tool_conf_destination is not None:
            generate_tool_conf(parsed_ctds, args.tool_conf_destination,
                               args.galaxy_tool_path, args.default_category)

        # generate datatypes_conf.xml
        if args.data_types_destination is not None:
            generate_data_type_conf(supported_file_formats, args.data_types_destination)


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
    macros_to_expand = list()

    for macros_file_name in macros_file_names:
        try:
            macros_file = open(macros_file_name)
            logger.info("Loading macros from %s" % macros_file_name, 0)
            root = parse(macros_file).getroot()
            for xml_element in root.findall("xml"):
                name = xml_element.attrib["name"]
                if name in macros_to_expand:
                    logger.warning("Macro %s has already been found. Duplicate found in file %s." %
                            (name, macros_file_name), 0)
                else:
                    logger.info("Macro %s found" % name, 1)
                    macros_to_expand.append(name)
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
            "see galaxy/macros.xml for an example of a valid macros file."
            % ", ".join(missing_needed_macros))

    # we do not need to "expand" the advanced_options macro
    macros_to_expand.remove(ADVANCED_OPTIONS_MACRO_NAME)
    return macros_to_expand


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
                        logger.warning(
                            "Invalid line at line number %d of the given formats file. Line will be ignored:\n%s" %
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

    # flatten macros_files to make sure that we have a list containing file names and not a list of lists
    utils.flatten_list_of_lists(args, "macros_files")

    # check that the arguments point to a valid, existing path
    input_variables_to_check = ["skip_tools_file", "required_tools_file", "macros_files", "formats_file"]
    for variable_name in input_variables_to_check:
        utils.validate_argument_is_valid_path(args, variable_name)

    # check that the provided output files, if provided, contain a valid file path (i.e., not a folder)
    output_variables_to_check = ["data_types_destination", "tool_conf_destination"]
    for variable_name in output_variables_to_check:
        file_name = getattr(args, variable_name)
        if file_name is not None and os.path.isdir(file_name):
            raise ApplicationException("The provided output file name (%s) points to a directory." % file_name)

    if not args.macros_files:
        # list is empty, provide the default value
        logger.warning("Using default macros from galaxy/macros.xml", 0)
        args.macros_files = ["galaxy/macros.xml"]


def get_preferred_file_extension():
    return "xml"


def _convert_internal(parsed_ctds, **kwargs):
    # parse all input files into models using CTDopts (via utils)
    # the output is a tuple containing the model, output destination, origin file
    for parsed_ctd in parsed_ctds:
        model = parsed_ctd.ctd_model
        origin_file = parsed_ctd.input_file
        output_file = parsed_ctd.suggested_output_file

        if kwargs["skip_tools"] is not None and model.name in kwargs["skip_tools"]:
            logger.info("Skipping tool %s" % model.name, 0)
            continue
        elif kwargs["required_tools"] is not None and model.name not in kwargs["required_tools"]:
            logger.info("Tool %s is not required, skipping it" % model.name, 0)
            continue
        else:
            logger.info("Converting %s (source %s)" % (model.name, utils.get_filename(origin_file)), 0)
            tool = create_tool(model)
            write_header(tool, model)
            create_description(tool, model)
            expand_macros(tool, model, **kwargs)
            create_command(tool, model, **kwargs)
            create_inputs(tool, model, **kwargs)
            create_outputs(tool, model, **kwargs)
            create_help(tool, model)

            # wrap our tool element into a tree to be able to serialize it
            tree = ElementTree(tool)
            logger.info("Writing to %s" % utils.get_filename(output_file), 1)
            tree.write(open(output_file, 'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)


def write_header(tool, model):
    tool.addprevious(etree.Comment(
        "This is a configuration file for the integration of a tools into Galaxy (https://galaxyproject.org/). "
        "This file was automatically generated using CTDConverter."))
    tool.addprevious(etree.Comment('Proposed Tool Section: [%s]' % model.opt_attribs.get("category", "")))


def generate_tool_conf(parsed_ctds, tool_conf_destination, galaxy_tool_path, default_category):
    # for each category, we keep a list of models corresponding to it
    categories_to_tools = dict()
    for parsed_ctd in parsed_ctds:
        category = strip(parsed_ctd.ctd_model.opt_attribs.get("category", ""))
        if not category.strip():
            category = default_category
        if category not in categories_to_tools:
            categories_to_tools[category] = []
        categories_to_tools[category].append(utils.get_filename(parsed_ctd.suggested_output_file))
                
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
    logger.info("Generated Galaxy tool_conf.xml in %s" % tool_conf_destination, 0)


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
    logger.info("Generated Galaxy datatypes_conf.xml in %s" % data_types_destination, 0)


def create_tool(model):
    return Element("tool", OrderedDict([("id", model.name), ("name", model.name), ("version", model.version)]))


def create_description(tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description = SubElement(tool,"description")
        description.text = model.opt_attribs["description"]


def create_command(tool, model, **kwargs):
    final_command = utils.extract_tool_executable_path(model, kwargs["default_executable_path"]) + '\n'
    final_command += kwargs["add_to_command_line"] + '\n'
    advanced_command_start = "#if $adv_opts.adv_opts_selector=='advanced':\n"
    advanced_command_end = "#end if"
    advanced_command = ""
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    found_output_parameter = False
    for param in utils.extract_and_flatten_parameters(model):
        if param.type is _OutFile:
            found_output_parameter = True
        command = ""
        param_name = utils.extract_param_name(param)
        command_line_prefix = utils.extract_command_line_prefix(param, model)

        if param.name in kwargs["blacklisted_parameters"]:
            continue

        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param_name, model.name)
        if hardcoded_value:
            command += "%s %s\n" % (command_line_prefix, hardcoded_value)
        else:
            # parameter is neither blacklisted nor hardcoded...
            galaxy_parameter_name = get_galaxy_parameter_name(param)
            repeat_galaxy_parameter_name = get_repeat_galaxy_parameter_name(param)

            # logic for ITEMLISTs
            if param.is_list:
                if param.type is _InFile:
                    command += command_line_prefix + "\n"
                    command += "  #for token in $" + galaxy_parameter_name + ":\n" 
                    command += "    $token\n"
                    command += "  #end for\n" 
                else:
                    command += "\n#if $" + repeat_galaxy_parameter_name + ":\n"
                    command += command_line_prefix + "\n"
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
                # TODO only useful for text fields, integers or floats
                # not useful for choices, input fields ...

                if not is_boolean_parameter(param) and type(param.restrictions) is _Choices :
                    command += "#if " + actual_parameter + ":\n"
                    command += "  %s\n" % command_line_prefix
                    command += "  #if \" \" in str(" + actual_parameter + "):\n"
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "  #else\n"
                    command += "    " + actual_parameter + "\n"
                    command += "  #end if\n"
                    command += "#end if\n" 
                elif is_boolean_parameter(param):
                    command += "#if " + actual_parameter + ":\n"
                    command += "  %s\n" % command_line_prefix
                    command += "#end if\n" 
                elif TYPE_TO_GALAXY_TYPE[param.type] in ['text', 'integer', 'float']:
                    command += "#if str(" + actual_parameter + ") != \"\":\n"
                    command += "  %s " % command_line_prefix
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "#end if\n" 
                elif TYPE_TO_GALAXY_TYPE[param.type] is 'data':
                    command += "#if str(" + actual_parameter + ") != \"None\":\n"
                    command += "  %s " % command_line_prefix
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "#end if\n" 
                else:
                    command += "#if str(" + actual_parameter + "):\n"
                    command += "  %s " % command_line_prefix
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
    token_node.text = utils.extract_tool_executable_path(model, kwargs["default_executable_path"])

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


def get_galaxy_parameter_name(param):
    return "param_%s" % utils.extract_param_name(param).replace(":", "_").replace("-", "_")


def get_input_with_same_restrictions(out_param, model, supported_file_formats):
    for param in utils.extract_and_flatten_parameters(model):
        if param.type is _InFile:
            if param.restrictions is not None:
                in_param_formats = get_supported_file_types(param.restrictions.formats, supported_file_formats)
                out_param_formats = get_supported_file_types(out_param.restrictions.formats, supported_file_formats)
                if in_param_formats == out_param_formats:
                    return param
                    

def create_inputs(tool, model, **kwargs):
    inputs_node = SubElement(tool, "inputs")

    # some suites (such as OpenMS) need some advanced options when handling inputs
    expand_advanced_node = None
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    # treat all non output-file parameters as inputs
    for param in utils.extract_and_flatten_parameters(model):
        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param.name, model.name)
        if param.name in kwargs["blacklisted_parameters"] or hardcoded_value:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            continue
        if param.advanced:
            continue

        parent_node = inputs_node

        # for lists we need a repeat tag
        if param.is_list and param.type is not _InFile:
            rep_node = add_child_node(parent_node, "repeat")
            create_repeat_attribute_list(rep_node, param)
            parent_node = rep_node

        param_node = add_child_node(parent_node, "param")
        create_param_attribute_list(param_node, param, kwargs["supported_file_formats"])

    for param in utils.extract_and_flatten_parameters(model):
        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param.name, model.name)
        if param.name in kwargs["blacklisted_parameters"] or hardcoded_value:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            continue
        if not param.advanced:
            continue
        if expand_advanced_node is None:
            expand_advanced_node = add_child_node(inputs_node, "expand", OrderedDict([("macro", ADVANCED_OPTIONS_MACRO_NAME)]))
        parent_node = expand_advanced_node

        # for lists we need a repeat tag
        if param.is_list and param.type is not _InFile:
            rep_node = add_child_node(parent_node, "repeat")
            create_repeat_attribute_list(rep_node, param)
            parent_node = rep_node

        param_node = add_child_node(parent_node, "param")
        create_param_attribute_list(param_node, param, kwargs["supported_file_formats"])


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
    if param.default is not None and param.default is not _Null:  
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
        if len(param.restrictions.choices) < 5:
            param_node.attrib["display"] = "radio"
        
    if is_boolean_parameter(param):
        param_type = "boolean"
        
    if param.type is _InFile:
        # assume it's just text unless restrictions are provided
        param_format = "txt"
        if param.restrictions is not None:
            # join all formats of the file, take mapping from supported_file if available for an entry
            if type(param.restrictions) is _FileFormat:
                param_format = ",".join([get_supported_file_type(i, supported_file_formats) if
                                        get_supported_file_type(i, supported_file_formats)
                                        else i for i in param.restrictions.formats])
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

                # preselect the default value
                if param.default == choice:
                    option_node.attrib["selected"] = "true"

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
            param_node.attrib["format"] = ','.join([get_supported_file_type(i, supported_file_formats) if
                                            get_supported_file_type(i, supported_file_formats)
                                            else i for i in param.restrictions.formats])
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]"
                                        % {"type": type(param.restrictions), "name": param.name})

        if param_type == "select" and param.default in param.restrictions.choices:
            param_node.attrib["optional"] = "False"
        else:
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
    if param.default is not None and param.default is not _Null:
        if type(param.default) is list:
            # we ASSUME that a list of parameters looks like:
            # $ tool -ignore He Ar Xe
            # meaning, that, for example, Helium, Argon and Xenon will be ignored
            param_node.attrib["value"] = ' '.join(map(str, param.default))

        elif param_type != "boolean":
            param_node.attrib["value"] = str(param.default)

        else:
            # simple boolean with a default
            if param.default is True:
                param_node.attrib["checked"] = "true"
    else:
        if param.type is int or param.type is float:
            # galaxy requires "value" to be included for int/float
            # since no default was included, we need to figure out one in a clever way... but let the user know
            # that we are "thinking" for him/her
            logger.warning("Generating default value for parameter [%s]. "
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
    help_text = ""
    # This tag is found in some descriptions 
    if not isinstance(desc, basestring):
        desc = str(desc)
    desc = desc.encode("utf8").replace("#br#", " <br>")
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
    label = desc.decode("utf8")
    
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


# determines if the given choices are boolean (basically, if the possible values are yes/no, true/false)
def is_boolean_parameter(param):
    # detect boolean selects of OpenMS
    if is_selection_parameter(param):
        if len(param.restrictions.choices) == 2:
            # check that default value is false to make sure it is an actual flag
            if "false" in param.restrictions.choices and \
                            "true" in param.restrictions.choices and \
                            param.default == "false":
                return True
    else:
        return param.type is bool


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
    true_value = "-%s" % utils.extract_param_name(param)
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
        param_node.attrib["checked"] = checked_value


def create_outputs(parent, model, **kwargs):
    outputs_node = add_child_node(parent, "outputs")
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    for param in utils.extract_and_flatten_parameters(model):

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
                       OrderedDict([("name", "param_stdout"), ("format", "txt"), ("label", "Output from stdout")]))


def create_output_node(parent, param, model, supported_file_formats):
    data_node = add_child_node(parent, "data")
    data_node.attrib["name"] = get_galaxy_parameter_name(param)
    if data_node.attrib["name"].startswith('param_out_'):
        data_node.attrib["label"] = "${tool.name} on ${on_string}: %s" % data_node.attrib["name"][10:]

    data_format = "data"
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            # set the first data output node to the first file format

            # check if there are formats that have not been registered yet...
            output = list()
            for format_name in param.restrictions.formats:
                if not format_name in supported_file_formats.keys():
                    output.append(str(format_name))

            # warn only if there's about to complain
            if output:
                logger.warning("Parameter " + param.name + " has the following unsupported format(s):"
                              + ','.join(output), 1)
                data_format = ','.join(output)

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
                    
                    data_node.attrib["format_source"] = get_galaxy_parameter_name(corresponding_input)
                    data_node.attrib["metadata_source"] = get_galaxy_parameter_name(corresponding_input)
                    return data_node
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] "
                                        "for output [%(name)s]" % {"type": type(param.restrictions),
                                                                   "name": param.name})
    data_node.attrib["format"] = data_format

    return data_node


# Get the supported file format for one given format
def get_supported_file_type(format_name, supported_file_formats):
    if format_name in supported_file_formats.keys():
        return supported_file_formats.get(format_name, DataType(format_name, format_name)).galaxy_extension
    else:
        return None


def get_supported_file_types(formats, supported_file_formats):
    return set([supported_file_formats.get(format_name, DataType(format_name, format_name)).galaxy_extension
               for format_name in formats if format_name in supported_file_formats.keys()])


def create_change_format_node(parent, data_formats, input_ref):
    #  <change_format>
    #    <when input="secondary_structure" value="true" format="txt"/>
    #  </change_format>
    change_format_node = add_child_node(parent, "change_format")
    for data_format in data_formats:
        add_child_node(change_format_node, "when",
                       OrderedDict([("input", input_ref), ("value", data_format), ("format", data_format)]))


# Shows basic information about the file, such as data ranges and file type.
def create_help(tool, model):
    help_node = add_child_node(tool, "help")
    # TODO: do we need CDATA Section here?
    help_node.text = utils.extract_tool_help_text(model)


# adds and returns a child node using the given name to the given parent node
def add_child_node(parent_node, child_node_name, attributes=OrderedDict([])):
    child_node = SubElement(parent_node, child_node_name, attributes)
    return child_node
