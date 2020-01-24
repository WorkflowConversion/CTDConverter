#!/usr/bin/env python
# encoding: utf-8
import os
import os.path
import re
import string

from collections import OrderedDict
import copy
from io import StringIO
from lxml import etree
from lxml.etree import CDATA, SubElement, Element, ElementTree, ParseError, parse, strip_elements

from common import utils, logger
from common.exceptions import ApplicationException, InvalidModelException

from CTDopts.CTDopts import _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, _FileFormat, ModelError, _Null, CTDTYPE_TO_TYPE, ParameterGroup


# mapping to CTD types to Galaxy types
TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'txt',
                       _OutFile: 'txt', _Choices: 'select'}
STDIO_MACRO_NAME = "stdio"
REQUIREMENTS_MACRO_NAME = "requirements"
ADVANCED_OPTIONS_NAME = "adv_opts_"

REQUIRED_MACROS = [REQUIREMENTS_MACRO_NAME, STDIO_MACRO_NAME, ADVANCED_OPTIONS_NAME + "macro"]


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
    """
    add command line arguments specific for galaxy tool generation
    @param parser an instance of ArgumentParser
    """
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
    parser.add_argument("--test-macros", dest="test_macros_files", default=[], nargs="*",
                        action="append", required=None,
                        help="Import tests from the files given file(s) as macros. "
                        "The macro names must end with the id of the tools")
    parser.add_argument("--test-macros-prefix", dest="test_macros_prefix", default=[], nargs="*",
                        action="append", required=None, help="The prefix of the macro name in the corresponding trest macros file")
    parser.add_argument("--test-test", dest="test_test", action='store_true', default=False, required=False,
                        help="Generate a simple test for the internal unit tests.")
    parser.add_argument("--test-only", dest="test_only", action='store_true', default=False, required=False,
                        help="Generate only the test section.")
    parser.add_argument("--tool-version", dest="tool_version", required=False, default=None,
                        help="Tool version to use (if not given its extracted from the CTD)")


def modify_param_for_galaxy(param):
    """
    some parameters need galaxy specific modifications
    """
    if param.type is _InFile:
        # if file default is given (happens for external applications and
        # files for which the default is taken from share/OpenMS) set the
        # parm to not required and remove the default (external applications
        # need to be taken care by hardcoded values and the other cases
        # are chosen automatically if not specified on the command line)
        if param.required and not (param.default is None or param.default is _Null):
            param.required = False
            param.default = _Null
    return param


def convert_models(args, parsed_ctds):
    """
    main conversion function

    @param args command line arguments
    @param parsed_ctds the ctds
    """
    # validate and prepare the passed arguments
    validate_and_prepare_args(args, parsed_ctds[0].ctd_model)

    # parse the given supported file-formats file
    supported_file_formats = parse_file_formats(args.formats_file)

    # extract the names of the macros and check that we have found the ones we need
    macros_to_expand = parse_macros_files(args.macros_files,
                                          tool_version=args.tool_version,
                                          supported_file_types=supported_file_formats,
                                          required_macros=REQUIRED_MACROS,
                                          dont_expand=[ADVANCED_OPTIONS_NAME + "macro", "references",
                                                       "list_string_val", "list_string_san",
                                                       "list_float_valsan", "list_integer_valsan"])

    check_test_macros(args.test_macros_files, args.test_macros_prefix, parsed_ctds)

    # parse the skip/required tools files
    skip_tools = parse_tools_list_file(args.skip_tools_file)
    required_tools = parse_tools_list_file(args.required_tools_file)
    _convert_internal(parsed_ctds,
                      supported_file_formats=supported_file_formats,
                      default_executable_path=args.default_executable_path,
                      add_to_command_line=args.add_to_command_line,
                      required_tools=required_tools,
                      skip_tools=skip_tools,
                      macros_file_names=args.macros_files,
                      macros_to_expand=macros_to_expand,
                      parameter_hardcoder=args.parameter_hardcoder,
                      test_test=args.test_test,
                      test_only=args.test_only,
                      test_macros_file_names=args.test_macros_files,
                      test_macros_prefix=args.test_macros_prefix,
                      tool_version=args.tool_version)
    # generation of galaxy stubs is ready... now, let's see if we need to generate a tool_conf.xml
    # TODO remove tool conf .. deprecated
#     if args.tool_conf_destination is not None:
#         generate_tool_conf(parsed_ctds, args.tool_conf_destination,
#                            args.galaxy_tool_path, args.default_category)

    # TODO remove datatypes_conf generation
    # generate datatypes_conf.xml
#     if args.data_types_destination is not None:
#         generate_data_type_conf(supported_file_formats, args.data_types_destination)


def parse_tools_list_file(tools_list_file):
    """
    """
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


def parse_macros_files(macros_file_names, tool_version, supported_file_types, required_macros=[], dont_expand=[]):
    """
    """
    macros_to_expand = []
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
                    continue
                logger.info("Macro %s found" % name, 1)
                macros_to_expand.append(name)
        except ParseError as e:
            raise ApplicationException("The macros file " + macros_file_name + " could not be parsed. Cause: " +
                                       str(e))

        except IOError as e:
            raise ApplicationException("The macros file " + macros_file_name + " could not be opened. Cause: " +
                                       str(e))
        else:
            macros_file.close()

    tool_ver_tk = root.find("token[@name='@TOOL_VERSION@']")
    galaxy_ver_tk = root.find("token[@name='@GALAXY_VERSION@']")
    if tool_ver_tk is None:
        tool_ver_tk = add_child_node(root, "token", OrderedDict([("name", "@TOOL_VERSION@")]))
        tool_ver_tk.text = tool_version
    if galaxy_ver_tk is None:
        galaxy_ver_tk = add_child_node(root, "token", OrderedDict([("name", "@GALAXY_VERSION@")]))
        galaxy_ver_tk.text = "0"
    if tool_version == tool_ver_tk.text:
        galaxy_ver_tk.text = str(int(galaxy_ver_tk.text))
    else:
        tool_ver_tk.text = tool_version
        galaxy_ver_tk.text = "0"

    ext_foo = root.find("token[@name='@EXT_FOO@']")
    if ext_foo is None:
        ext_foo = add_child_node(root, "token", OrderedDict([("name", "@EXT_FOO@")]))

    g2o, o2g = get_fileformat_maps(supported_file_types)

    # make sure that the backup data type is in the map
    if 'txt' not in g2o:
        g2o['txt'] = 'txt'

    ext_foo.text = CDATA("""#def oms2gxyext(o)
    #set m=%s
    #return m[o]
#end def
#def gxy2omsext(g)
    #set m=%s
    #return m[g]
#end def
""" % (str(o2g), str(g2o)))

    tree = ElementTree(root)
    tree.write(macros_file_name, encoding="UTF-8", xml_declaration=True, pretty_print=True)
#     with open(macros_file_name, "w") as macros_file:
#         tree = ElementTree(root)
#         tree.write(macros_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)

    # we depend on "stdio", "requirements" and "advanced_options" to exist on all the given macros files
    missing_needed_macros = []
    for required_macro in required_macros:
        if required_macro not in macros_to_expand:
            missing_needed_macros.append(required_macro)

    if missing_needed_macros:
        raise ApplicationException(
            "The following required macro(s) were not found in any of the given macros files: %s, "
            "see galaxy/macros.xml for an example of a valid macros file."
            % ", ".join(missing_needed_macros))

    # remove macros that should not be expanded
    for m in dont_expand:
        try:
            idx = macros_to_expand.index(m)
            del macros_to_expand[idx]
        except ValueError:
            pass

    return macros_to_expand


def check_test_macros(test_macros_files, test_macros_prefix, parsed_ctds):

    tool_ids = set()
    for parsed_ctd in parsed_ctds:
        model = parsed_ctd.ctd_model
        tool_ids.add(model.name.replace(" ", "_"))

    for mf, mp in zip(test_macros_files, test_macros_prefix):
        macro_ids = set()
        try:
            with open(mf) as macros_file:
                root = parse(macros_file).getroot()
                for xml_element in root.findall("xml"):
                    name = xml_element.attrib["name"]
                    if not name.startswith(mp):
                        logger.warning("Testmacro with invalid prefix %s." % (mp), 0)
                        continue
                    name = name[len(mp):]
                    macro_ids.add(name)

        except ParseError as e:
            raise ApplicationException("The macros file " + mf + " could not be parsed. Cause: " +
                                       str(e))
        except IOError as e:
            raise ApplicationException("The macros file " + mf + " could not be opened. Cause: " +
                                       str(e))
        for t in tool_ids - macro_ids:
            logger.error("missing %s" % t)
            add_child_node(root, "xml", OrderedDict([("name", mp + t)]))

        if len(macro_ids - tool_ids):
            logger.warning("Unnecessary macros in %s: %s" % (mf, macro_ids - tool_ids))
        with open(mf, "w") as macros_file:
            tree = ElementTree(root)
            tree.write(macros_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)


def parse_file_formats(formats_file):
    """
    """
    supported_formats = OrderedDict()
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


def get_fileformat_maps(supported_formats):
    """
    convenience functions to compute dictionaries mapping
    Galaxy data types <-> CTD formats
    """
    o2g = {}
    g2o = {}
    for s in supported_formats:
        o2g[s] = supported_formats[s].galaxy_extension
        if supported_formats[s].galaxy_extension not in g2o:
            g2o[supported_formats[s].galaxy_extension] = s
    return g2o, o2g


def validate_and_prepare_args(args, model):
    """
    check command line arguments
    @param args command line arguments
    @return None
    """
    # check that only one of skip_tools_file and required_tools_file has been provided
    if args.skip_tools_file is not None and args.required_tools_file is not None:
        raise ApplicationException(
            "You have provided both a file with tools to ignore and a file with required tools.\n"
            "Only one of -s/--skip-tools, -r/--required-tools can be provided.")

    # flatten macros_files to make sure that we have a list containing file names and not a list of lists
    utils.flatten_list_of_lists(args, "macros_files")
    utils.flatten_list_of_lists(args, "test_macros_files")
    utils.flatten_list_of_lists(args, "test_macros_prefix")

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
        args.macros_files = [os.path.dirname(os.path.abspath(__file__)) + "/macros.xml"]

    if args.tool_version is None:
        args.tool_version = model.version


def get_preferred_file_extension():
    """
    get the file extension for the output files
    @return "xml"
    """
    return "xml"


def _convert_internal(parsed_ctds, **kwargs):
    """
    parse all input files into models using CTDopts (via utils)

    @param parsed_ctds the ctds
    @param kwargs skip_tools, required_tools, and additional parameters for
        expand_macros, create_command, create_inputs, create_outputs
    @return a tuple containing the model, output destination, origin file
    """

    if "test_only" in kwargs and kwargs["test_only"]:
        for parsed_ctd in parsed_ctds:
            test = create_test_only(parsed_ctd.ctd_model)
            tree = ElementTree(test)
            output_file = parsed_ctd.suggested_output_file
            logger.info("Writing to %s" % utils.get_filename(output_file), 1)
            with open(output_file, 'w') as fh:
                tree.write(fh, encoding="UTF-8", xml_declaration=False, pretty_print=True)
        return

    parameter_hardcoder = kwargs["parameter_hardcoder"]
    for parsed_ctd in parsed_ctds:
        model = parsed_ctd.ctd_model

        if kwargs["skip_tools"] is not None and model.name in kwargs["skip_tools"]:
            logger.info("Skipping tool %s" % model.name, 0)
            continue
        elif kwargs["required_tools"] is not None and model.name not in kwargs["required_tools"]:
            logger.info("Tool %s is not required, skipping it" % model.name, 0)
            continue

        origin_file = parsed_ctd.input_file
        output_file = parsed_ctd.suggested_output_file

        # overwrite attributes of the parsed ctd parameters as specified in hardcoded parameterd json
        for param in utils.extract_and_flatten_parameters(model):
            hardcoded_attributes = parameter_hardcoder.get_hardcoded_attributes(param.name, model.name)
            if hardcoded_attributes is not None:
                for a in hardcoded_attributes:
                    if not hasattr(param, a):
                        continue
                    # logger.error("%s %s"%(param.name, type(getattr(param, a))) )
                    if type(getattr(param, a)) is _FileFormat:
                        setattr(param, a, _FileFormat(str(hardcoded_attributes[a])))
                    elif type(getattr(param, a)) is _Choices:
                        # logger.error("SET CTD %s %s %s" %(param.name, a, hardcoded_attributes[a]))
                        setattr(param, a, _Choices(str(hardcoded_attributes[a])))
                    elif type(getattr(param, a)) is _NumericRange:
                        raise Exception("Overwriting of Numeric Range not implemented")
                    else:
                        setattr(param, a, hardcoded_attributes[a])

        logger.info("Converting %s (source %s)" % (model.name, utils.get_filename(origin_file)), 0)
        tool = create_tool(model)
        write_header(tool, model)
        create_description(tool, model)
        import_macros(tool, model, **kwargs)
        expand_macros(tool, kwargs["macros_to_expand"])
#         command, inputs, outputs = create_cio(tool, model, **kwargs)
        create_command(tool, model, **kwargs)
        create_configfile(tool, model, **kwargs)
        inputs = create_inputs(tool, model, **kwargs)
        outputs = create_outputs(tool, model, **kwargs)
        if kwargs["test_test"]:
            create_tests(tool, inputs=copy.deepcopy(inputs), outputs=copy.deepcopy(outputs))
        if kwargs["test_macros_prefix"]:
            create_tests(tool, test_macros_prefix=kwargs['test_macros_prefix'], name=model.name)

        create_help(tool, model)
        # citations are required to be at the end
        expand_macro(tool, "references")

        # wrap our tool element into a tree to be able to serialize it
        tree = ElementTree(tool)
        logger.info("Writing to %s" % utils.get_filename(output_file), 1)
        tree.write(output_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)


def write_header(tool, model):
    """
    add comments to the tool header
    @param tool the tool xml
    @param model the ctd model
    """
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
    toolconf_tree.write(open(tool_conf_destination, 'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
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
    data_types_tree.write(open(data_types_destination, 'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
    logger.info("Generated Galaxy datatypes_conf.xml in %s" % data_types_destination, 0)


def create_tool(model):
    """
    initialize the tool
    @param model the ctd model
    """

    return Element("tool", OrderedDict([("id", model.name.replace(" ", "_")), ("name", model.name), ("version", "@TOOL_VERSION@+galaxy@GALAXY_VERSION@")]))


def create_description(tool, model):
    """
    add description to the tool
    @param tool the Galaxy tool
    @param model the ctd model
    """
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description = SubElement(tool, "description")
        description.text = model.opt_attribs["description"]


def get_by_path(dataDict, mapList):
    for k in mapList:
        dataDict = dataDict[k]
    return dataDict


def set_by_path(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def create_configfile(tool, model, **kwargs):

    configfiles_node = add_child_node(tool, "configfiles")
    inputs_node = add_child_node(configfiles_node, "inputs", OrderedDict([("name", "args_json"), ("data_style", "paths")]))


def create_command(tool, model, **kwargs):
    """
    @param tool the Galaxy tool
    @param model the ctd model
    @param kwargs
    """

    # main command
    final_cmd = OrderedDict([('preprocessing', []), ('command', []), ('postprocessing', [])])
    advanced_cmd = {'preprocessing': [], 'command': [], 'postprocessing': []}

    final_cmd['preprocessing'].extend(["@QUOTE_FOO@", "@EXT_FOO@", "#import re", "", "## Preprocessing"])

    # - call the executable with -write_ctd to write the ctd file (with defaults)
    # - use fill_ctd.py to overwrite the defaults in the ctd file with the
    #   Galaxy parameters in the JSON file (from inputs config file)
    #   (note the base name call is only necessary for the CTDconverter tests)
    # - feed the ctd file to the executable (with -ini)
    #   note: input and output file parameters are still given on the command line
    #   - output file parameters are not included in the JSON file
    #   - input and output files are accessed through links / files that have the correct extension
    final_cmd['command'].extend(["", "## Main program call"])
    final_cmd['command'].append("""@EXECUTABLE@ -write_ctd ./ &&
python '$__tool_directory__/fill_ctd.py' "\$(basename "@EXECUTABLE@.ctd")" '$args_json' &&
@EXECUTABLE@ -ini @EXECUTABLE@.ctd""")
    final_cmd['command'].extend(kwargs["add_to_command_line"])
    final_cmd['postprocessing'].extend(["", "## Postprocessing"])

    advanced_command_start = "#if ${aon}cond.{aon}selector=='advanced':".format(aon=ADVANCED_OPTIONS_NAME)
    advanced_command_end = "#end if"

    parameter_hardcoder = kwargs["parameter_hardcoder"]
    supported_file_formats = kwargs["supported_file_formats"]

    found_output_parameter = False
    for param in utils.extract_and_flatten_parameters(model):
        param = modify_param_for_galaxy(param)
        if param.type is _OutFile:
            found_output_parameter = True

        param_cmd = {'preprocessing': [], 'command': [], 'postprocessing': []}
        param_name = utils.extract_param_name(param)
        command_line_prefix = utils.extract_command_line_prefix(param, model)

        # TODO use utils.extract_param_name(param).replace(":", "_")? Then hardcoding ctd variables (with :) and tool variables (with _) can be distinguished
        if parameter_hardcoder.get_blacklist(utils.extract_param_name(param), model.name):
            continue

        hardcoded_value = parameter_hardcoder.get_hardcoded_value(param_name, model.name)
        if hardcoded_value is not None:
            pass  # TODO hardcoded values should go to <inputs>
            # param_cmd['command'].append("%s %s" % (command_line_prefix, hardcoded_value))
        else:
            # in the else branch the parameter is neither blacklisted nor hardcoded...

            actual_parameter = get_galaxy_parameter_path(param)
            # all but bool params need the command line argument (bools have it already in the true/false value)
            if param.type is _OutFile or param.type is _InFile:
                param_cmd['command'].append(command_line_prefix)

            # preprocessing for file inputs:
            # - create a dir with name param.name
            # - create a link to id.ext in this directory
            # rationale: in the autogenerated tests the same file was used as input to multiple parameters
            # this leads to conflicts while linking... might also be better in general
            if param.type is _InFile:
                param_cmd['preprocessing'].append("mkdir %s &&" % param.name)
                if param.is_list:
                    param_cmd['preprocessing'].append("${ ' '.join([\"ln -s '%s' '" + param.name + "/%s.%s' &&\" % (_, re.sub('[^\w\-_]', '_', _.element_identifier), $gxy2omsext(_.ext)) for _ in $" + param.name + " if _]) }")
                    param_cmd['command'].append("${' '.join([\"'" + param.name + "/%s.%s'\"%(re.sub('[^\w\-_]', '_', _.element_identifier), $gxy2omsext(_.ext)) for _ in $" + param.name + " if _])}")
                else:
                    param_cmd['preprocessing'].append("ln -s '$" + param.name + "' '" + param.name + "/${re.sub(\"[^\w\-_]\", \"_\", $" + param.name + ".element_identifier)}.$gxy2omsext($" + param.name + ".ext)' &&")
                    param_cmd['command'].append("'" + param.name + "/${re.sub(\"[^\w\-_]\", \"_\", $" + param.name + ".element_identifier)}.$gxy2omsext($" + param.name + ".ext)'")
            elif param.type is _OutFile:
                # check if there is a parameter that sets the format
                # if so we add an extension to the generated files which will be used to
                # determine the format in the output tag
                # in all other cases (corresponding input / there is only one allowed format)
                # the format will be set in the output tag
                formats = get_formats(param, supported_file_formats, TYPE_TO_GALAXY_TYPE[param.type])
                type_param = get_out_type_param(param, model, parameter_hardcoder)
                corresponding_input, fmt_from_corresponding = get_corresponding_input(param, model)
                if corresponding_input is not None:
                    actual_input_parameter = get_galaxy_parameter_path(corresponding_input)
                else:
                    actual_input_parameter = None

                if type_param is not None:
                    type_param_name = get_galaxy_parameter_path(type_param)
                elif len(formats) > 1 and (corresponding_input is None or not fmt_from_corresponding) and not param.is_list:
                    type_param_name = get_galaxy_parameter_path(param, "type")
                else:
                    type_param_name = None

                param_cmd['preprocessing'].append("mkdir " + param.name + " &&")

                # if there is only one format (the outoput node sets format using the format attribute of the data/discover node)
                # - single file: write to temp file with oms extension and move this to the actual result file
                # - lists: write to files with the oms extension and remove the extension afterwards (discovery with __name__)
                if len(formats) == 1:
                    fmt = formats.pop()
                    if param.is_list:
                        logger.info("1 fmt + list %s -> %s" % (param.name, actual_input_parameter), 1)
                        param_cmd['command'].append("${' '.join([\"'" + param.name + "/%s.%s'\"%(re.sub('[^\w\-_]', '_', _.element_identifier), $gxy2omsext(\"" + fmt + "\")) for _ in $" + actual_input_parameter + " if _])}")
                        param_cmd['postprocessing'].append("${' '.join([\"&& mv -n '" + param.name + "/%(id)s.%(gext)s' '" + param.name + "/%(id)s'\"%{\"id\": re.sub('[^\w\-_]', '_', _.element_identifier), \"gext\": $gxy2omsext(\"" + fmt + "\")} for _ in $" + actual_input_parameter + " if _])}")
                    else:
                        logger.info("1 fmt + dataset %s" % param.name, 1)
                        param_cmd['command'].append("'" + param.name + "/output.${gxy2omsext(\"" + fmt + "\")}'")
                        param_cmd['postprocessing'].append("&& mv '" + param.name + "/output.${gxy2omsext(\"" + fmt + "\")}' '$" + param.name + "'")

                # if there is a type parameter then we use the type selected by the user
                # - single: write to temp file with the oms extension and mv it to the actual file output which is treated via change_format
                # - list: let the command create output files with the oms extensions, postprocessing renames them to the galaxy extensions, output is then discover + __name_and_ext__
                elif type_param_name is not None:
                    if param.is_list:
                        logger.info("type + list %s" % param.name, 1)
                        param_cmd['command'].append("${' '.join([\"'" + param.name + "/%s.%s'\"%(re.sub('[^\w\-_]', '_', _.element_identifier), " + type_param_name + ") for _ in $" + actual_input_parameter + " if _])}")
                        param_cmd['postprocessing'].append("${' '.join([\"&& mv -n '" + param.name + "/%(id)s.%(omsext)s' '" + param.name + "/%(id)s.%(gext)s'\"%{\"id\": re.sub('[^\w\-_]', '_', _.element_identifier), \"omsext\":" + type_param_name + ", \"gext\": oms2gxyext(\"" + type_param_name + "\")} for _ in $" + actual_input_parameter + " if _])}")
                    else:
                        logger.info("type + dataset %s" % param.name, 1)
                        # 1st create file with openms extension (often required by openms)
                        # then move it to the actual place specified by the parameter
                        # the format is then set by the <data> tag using <change_format>
                        param_cmd['command'].append("'" + param.name + "/output.${" + type_param_name + "}'")
                        param_cmd['postprocessing'].append("&& mv '" + param.name + "/output.${" + type_param_name + "}' '$" + actual_parameter + "'")
                elif actual_input_parameter is not None:
                    if param.is_list:
                        logger.info("actual + list %s" % param.name, 1)
                        param_cmd['command'].append("${' '.join([\"'" + param.name + "/%s.%s'\"%(re.sub('[^\w\-_]', '_', _.element_identifier), _.ext) for _ in $" + actual_input_parameter + " if _])}")
                    else:
                        logger.info("actual + dataset %s %s %s" % (param.name, actual_input_parameter, corresponding_input.is_list), 1)
                        if corresponding_input.is_list:
                            param_cmd['command'].append("'" + param.name + "/output.${" + actual_input_parameter + "[0].ext}'")
                            param_cmd['postprocessing'].append("&& mv '" + param.name + "/output.${" + actual_input_parameter + "[0].ext}' '$" + actual_parameter + "'")
                        else:
                            param_cmd['command'].append("'" + param.name + "/output.${" + actual_input_parameter + ".ext}'")
                            param_cmd['postprocessing'].append("&& mv '" + param.name + "/output.${" + actual_input_parameter + ".ext}' '$" + actual_parameter + "'")
                else:
                    if param.is_list:
                        raise Exception("output parameter itemlist %s without corresponding input")
                    else:
                        logger.info("else + dataset %s" % param.name, 1)
                        param_cmd['command'].append("'$out_" + param.name + "'")

#             # select with multiple = true
#             elif is_selection_parameter(param) and param.is_list:
#                 param_cmd['command'].append("${' '.join(['\"%s\"'%str(_) for _ in str($" + actual_parameter + ").split(',')])}")
#             elif param.is_list:
#                 param_cmd['command'].append("$quote($%s" % actual_parameter + ")")
#                 #command += "${' '.join([\"'%s'\"%str(_) for _ in $" + actual_parameter + "])}\n"
#             elif is_boolean_parameter(param):
#                 param_cmd['command'].append("$%s" % actual_parameter + "")
#             else:
#                 param_cmd['command'].append('"$' + actual_parameter + '"')

            # add if statement for optional parameters and preprocessing
            # - for optional outputs (param_out_x) the presence of the parameter
            #   depends on the additional input (param_x) -> need no if
            # - real string parameters (i.e. ctd type string wo restrictions) also
            #   need no if (otherwise the empty string could not be provided)
            if not (param.required or is_boolean_parameter(param) or (param.type == str and param.restrictions is None)):
                # and not(param.type is _InFile and param.is_list):
                actual_parameter = get_galaxy_parameter_path(param, "FLAG")
                for stage in param_cmd:
                    if len(param_cmd[stage]) == 0:
                        continue
                    # special case for optional itemlists: for those if no option is selected only the parameter must be specified
                    if is_selection_parameter(param) and param.is_list and param.required is False:
                        param_cmd[stage] = [param_cmd[stage][0]] + ["#if $" + actual_parameter + ":"] + utils.indent(param_cmd[stage][1:]) + ["#end if"]
                    elif is_selection_parameter(param) or param.type is _OutFile or param.type is _InFile:
                        param_cmd[stage] = ["#if $" + actual_parameter + ":"] + utils.indent(param_cmd[stage]) + ["#end if"]
                    else:
                        param_cmd[stage] = ["#if str($" + actual_parameter + "):"] + utils.indent(param_cmd[stage]) + ["#end if"]

        for stage in param_cmd:
            if len(param_cmd[stage]) == 0:
                continue
            if param.advanced and hardcoded_value is None:
                advanced_cmd[stage].extend(param_cmd[stage])
            else:
                final_cmd[stage].extend(param_cmd[stage])

    for stage in advanced_cmd:
        if len(advanced_cmd[stage]) == 0:
            continue
        advanced_cmd[stage] = [advanced_command_start] + utils.indent(advanced_cmd[stage]) + [advanced_command_end]
        final_cmd[stage].extend(advanced_cmd[stage])

    if not found_output_parameter:
        final_cmd['command'].append("> $param_stdout")

    command_node = add_child_node(tool, "command")
    command_node.attrib["detect_errors"] = "exit_code"

    command_node.text = CDATA("\n".join(sum(final_cmd.values(), [])))


def import_macros(tool, model, **kwargs):
    """
    creates the xml elements needed to import the needed macros files
    @param tool the Galaxy tool
    @param model the ctd model
    @param kwargs
    """
    macros_node = add_child_node(tool, "macros")
    token_node = add_child_node(macros_node, "token")
    token_node.attrib["name"] = "@EXECUTABLE@"
    token_node.text = utils.extract_tool_executable_path(model, kwargs["default_executable_path"])

    # add <import> nodes
    for macro_file_name in kwargs["macros_file_names"] + kwargs["test_macros_file_names"]:
        macro_file = open(macro_file_name)
        import_node = add_child_node(macros_node, "import")
        # do not add the path of the file, rather, just its basename
        import_node.text = os.path.basename(macro_file.name)


def expand_macro(node, macro):
    expand_node = add_child_node(node, "expand")
    expand_node.attrib["macro"] = macro
    return expand_node


# and to "expand" the macros in a node
def expand_macros(node, macros_to_expand):
    # add <expand> nodes
    for expand_macro in macros_to_expand:
        expand_node = add_child_node(node, "expand")
        expand_node.attrib["macro"] = expand_macro


def get_galaxy_parameter_path(param, inparam=False):
    """
    get the complete cheetah path for a parameter
    """
    p = get_galaxy_parameter_name(param, inparam)
    path = utils.extract_param_path(param)
    if len(path) > 1 and (param.type is not _OutFile or inparam):
        return (".".join(["section_" + _ for _ in path[:-1]]) + "." + p).replace("-", "_")
    elif param.advanced and (param.type is not _OutFile or inparam):
        return ADVANCED_OPTIONS_NAME + "cond." + p
    else:
        return p


def get_galaxy_parameter_name(param, inparam=False):
    """
    get the name of the parameter used in the galaxy tool
    - replace : and - by _
    - add value inpram for output parameters if not False

    the idea of inparam is to be used for optional outputs (out_x) for
    which an additional boolean input (out_x_FLAG) exists

    @param param the parameter
    @param inparam get the name of the corresponding input
    @return the name used for the parameter in the tool form
    """
    p = param.name.replace("-", "_")
    if param.type is _OutFile and inparam:
        return "%s_%s" % (p, inparam)
    else:
        return "%s" % p


def get_out_type_param(out_param, model, parameter_hardcoder):
    """
    check if there is a parameter that has the same name with appended _type
    and return it if present, otherwise return None
    """
    if parameter_hardcoder.get_blacklist(out_param.name + "_type", model.name):
        return None

    for param in utils.extract_and_flatten_parameters(model):
        if param.name == out_param.name + "_type":
            return param
    return None


def is_out_type_param(param, model):
    """
    check if the parameter is output_type parameter
    - the name ends with _type and there is an output parameter without this suffix
    and return True iff this is the case
    """
    if not param.name.endswith("_type"):
        return False
    for out_param in utils.extract_and_flatten_parameters(model):
        if out_param.type is not _OutFile:
            continue
        if param.name == out_param.name + "_type":
            return True
    return False


def get_corresponding_input(out_param, model):
    """
    get the input parameter corresponding to the given output

    1st try to get the input with the type (single file/list) and same format restrictions
    if this fails get the input that has the same type
    in both cases there must be only one such input

    return the found input parameter and True iff the 1st case applied
    """
    c = get_input_with_same_restrictions(out_param, model, True)
    if c is None:
        return (get_input_with_same_restrictions(out_param, model, False), False)
    else:
        return (c, True)


def get_input_with_same_restrictions(out_param, model, check_formats):
    """
    get the input parameter that has the same restrictions (ctd file_formats)
    - input and output must both be lists of both be simple parameters
    """

    matching = []

    for allow_different_type in [False, True]:
        for param in utils.extract_and_flatten_parameters(model):
            if param.type is not _InFile:
                continue
#             logger.error("%s %s %s %s %s %s" %(out_param.name, param.name,  param.is_list, out_param.is_list, param.restrictions,  out_param.restrictions))
            if allow_different_type or param.is_list == out_param.is_list:
                if check_formats:
                    if param.restrictions is None and out_param.restrictions is None:
                        matching.append(param)
                    elif param.restrictions is not None and out_param.restrictions is not None and param.restrictions.formats == out_param.restrictions.formats:
                        matching.append(param)
                else:
                    matching.append(param)
#             logger.error("match %s "%([_.name for _ in matching]))
        if len(matching) > 0:
            break
    if len(matching) == 1:
        return matching[0]
    else:
        return None


def create_inputs(tool, model, **kwargs):
    """
    create input section of the Galaxy tool
    @param tool the Galaxy tool
    @param model the ctd model
    @param kwargs
    @return inputs node
    """
    inputs_node = SubElement(tool, "inputs")
    section_nodes = dict()
    section_params = dict()

    # some suites (such as OpenMS) need some advanced options when handling inputs
    advanced_node = None
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    # treat all non output-file/advanced/blacklisted/hardcoded parameters as inputs
    for param in utils.extract_and_flatten_parameters(model, True):
        if type(param) is ParameterGroup:
            title, help_text = generate_label_and_help(param.description)
            section_params[utils.extract_param_name(param)] = param
            section_nodes[utils.extract_param_name(param)] = Element("section", OrderedDict([("name", param.name), ("title", title), ("help", help_text), ("expanded", "false")]))
            continue

        param = modify_param_for_galaxy(param)
        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(utils.extract_param_name(param), model.name)
        if parameter_hardcoder.get_blacklist(utils.extract_param_name(param), model.name) or hardcoded_value is not None:
            continue

        if utils.extract_param_name(param.parent) in section_nodes:
            parent_node = section_nodes[utils.extract_param_name(param.parent)]
        elif param.advanced:
            if advanced_node is None:
                advanced_node = Element("expand", OrderedDict([("macro", ADVANCED_OPTIONS_NAME + "macro")]))
            parent_node = advanced_node
        else:
            parent_node = inputs_node

        # sometimes special inputs are needed for outfiles:
        add_formats = False
        if param.type is _OutFile:
            # if there are multiple possible output formats, but no parameter to choose the type or a
            # corresponding input then add a selection parameter
            formats = get_formats(param, kwargs["supported_file_formats"], TYPE_TO_GALAXY_TYPE[_OutFile])
            type_param = get_out_type_param(param, model, parameter_hardcoder)
            corresponding_input, fmt_from_corresponding = get_corresponding_input(param, model)
            if len(formats) > 1 and type_param is None and (corresponding_input is None or not fmt_from_corresponding) and not param.is_list:
                fmt_select = add_child_node(parent_node, "param", OrderedDict([("name", param.name + "_type"), ("type", "select"), ("optional", "false"), ("label", "File type of output %s (%s)" % (param.name, param.description))]))
                g2o, o2g = get_fileformat_maps(kwargs["supported_file_formats"])
                for f in formats:
                    option_node = add_child_node(fmt_select, "option", OrderedDict([("value", g2o[f])]), f)

            # create an additional bool input which is used to filter for the output
            # mandatory outpiles: no input node needed
            # inputs: create the input param
            if not param.required:
                add_child_node(parent_node, "param", OrderedDict([("type", "boolean"), ("name", param.name + "_FLAG"), ("optional", "false"), ("checked", "false"), ("label", "Generate output %s (%s)" % (param.name, param.description))]))
#             else:
#                 add_child_node(parent_node, "param", OrderedDict([("type", "hidden"), ("name", param.name)]))
            continue

        # create the actual param node and fill the attributes
        param_node = add_child_node(parent_node, "param")
        create_param_attribute_list(param_node, param, model, kwargs["supported_file_formats"])

        hardcoded_attributes = parameter_hardcoder.get_hardcoded_attributes(param.name, model.name)
        if hardcoded_attributes is not None:
            for a in hardcoded_attributes:
                param_node.attrib[a] = str(hardcoded_attributes[a])

    for sn in section_nodes:
        if utils.extract_param_name(section_params[sn].parent) in section_nodes:
            section_nodes[utils.extract_param_name(section_params[sn].parent)].append(section_nodes[sn])
        else:
            inputs_node.append(section_nodes[sn])
    # if there is an advanced section then append it at the end of the inputs
    if advanced_node is not None:
        inputs_node.append(advanced_node)

    return inputs_node


def is_default(value, param):
    """
    check if the value is the default of the param or if the value is in the defaults of param
    """
    return param.default == value or (type(param.default) is list and value in param.default)


def get_formats(param, supported_file_formats, default=None):
    """
    determine format attribute
    - check if all listed possible formats are supported in Galaxy
    - if there is a single one, then take this
    - otherwise try to determine an input with the same restrictions and use this as format source
    """
    formats = set()
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            # check if there are formats that have not been registered yet...
            output = list()
            for format_name in param.restrictions.formats:
                if format_name not in supported_file_formats.keys():
                    output.append(str(format_name))
            # warn only if there's about to complain
            if output:
                logger.warning("Parameter " + param.name + " has the following unsupported format(s):" +
                               ','.join(output), 1)

            formats = get_supported_file_types(param.restrictions.formats, supported_file_formats)
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] "
                                        "for [%(name)s]" % {"type": type(param.restrictions),
                                                            "name": param.name})

    if len(formats) == 0:
        if default is not None:
            formats.add(default)
        else:
            raise InvalidModelException("No supported formats [%(type)s] "
                                        "for [%(name)s]" % {"type": type(param.restrictions),
                                                            "name": param.name})

    return formats


def create_param_attribute_list(param_node, param, model, supported_file_formats):
    """
    get the attributes of input parameters
    @param param_node the galaxy tool param node
    @param param the ctd parameter
    @param supported_file_formats
    """

    g2o, o2g = get_fileformat_maps(supported_file_formats)

    # set the name, argument and a first guess for the type (which will be over written
    # in some cases .. see below)
    param_node.attrib["name"] = param.name
    param_node.attrib["argument"] = "-%s" % utils.extract_param_name(param)
    param_type = TYPE_TO_GALAXY_TYPE[param.type]
    if param_type is None:
        raise ModelError("Unrecognized parameter type %(type)s for parameter %(name)s"
                         % {"type": param.type, "name": param.name})

    # ITEMLIST is rendered as text field (even if its integers or floats), an
    # exception is files which are treated a bit below
    if param.is_list:
        param_type = "text"

    if is_selection_parameter(param):
        param_type = "select"
        if len(param.restrictions.choices) < 5 and not param.is_list:
            param_node.attrib["display"] = "radio"
        if param.is_list:
            param_node.attrib["multiple"] = "true"

    if is_boolean_parameter(param):
        param_type = "boolean"

    if param.type is _InFile:
        # assume it's just text unless restrictions are provided
        param_node.attrib["type"] = "data"
        param_node.attrib["format"] = ",".join(get_formats(param, supported_file_formats, TYPE_TO_GALAXY_TYPE[_InFile]))
        # in the case of multiple input set multiple flag
        if param.is_list:
            param_node.attrib["multiple"] = "true"
    else:
        param_node.attrib["type"] = param_type

    if param_type == "select" and param.default in param.restrictions.choices:
        param_node.attrib["optional"] = "false"
    else:
        param_node.attrib["optional"] = str(not param.required).lower()

    # check for parameters with restricted values (which will correspond to a "select" in galaxy)
    if param.restrictions is not None or param_type == "boolean":
        # it could be either _Choices or _NumericRange, with special case for boolean types
        if param_type == "boolean":
            create_boolean_parameter(param_node, param)
        elif type(param.restrictions) is _Choices:

            # TODO if the parameter is used to select the output file type the
            # options need to be replaced with the Galaxy data types
            # if is_out_type_param(param, model):
            #     param.restrictions.choices = get_supported_file_types(param.restrictions.choices, supported_file_formats)

            # # add a nothing selected option to mandatory options w/o default
            # if param_node.attrib["optional"] == "False" and (param.default is None or param.default is _Null):
            #     param.restrictions.choices.insert(0, "select a value")
            # create as many <option> elements as restriction values
            for choice in param.restrictions.choices:
                option_node = add_child_node(param_node, "option", OrderedDict([("value", str(choice))]))
                if is_out_type_param(param, model):
                    option_node.text = o2g[str(choice)]
                else:
                    option_node.text = str(choice)

                # preselect the default value
                if is_default(choice, param):
                    option_node.attrib["selected"] = "true"
                else:
                    option_node.attrib["selected"] = "false"
            # add validator to check that "nothing selected" is not seletcedto mandatory options w/o default
            if param_node.attrib["optional"] == "False" and (param.default is None or param.default is _Null):
                validator_node = add_child_node(param_node, "validator", OrderedDict([("type", "expression"), ("message", "A value needs to be selected")]))
                validator_node.text = 'value != "select a value"'

        # numeric ranges (which appear for int and float ITEMS and ITEMLISTS)
        # these are reflected by min and max attributes
        # since item lists become text parameters + validator these don't need these attributes
        elif type(param.restrictions) is _NumericRange and param_type == "text":
            pass
        elif type(param.restrictions) is _NumericRange and param_type != "text":
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
            # has already been handled
            pass
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]"
                                        % {"type": type(param.restrictions), "name": param.name})

    if param_type == "text":
        # for repeats (which are rendered as text field in the tool form) that are actually
        # integer/floats special validation is necessary (try to convert them and check if
        # in the min max range if a range is given)
        if TYPE_TO_GALAXY_TYPE[param.type] in ["integer", "float"]:
            valsan = expand_macro(param_node, "list_%s_valsan" % TYPE_TO_GALAXY_TYPE[param.type])

            if type(param.restrictions) is _NumericRange and not (param.restrictions.n_min is None and param.restrictions.n_max is None):
                expression = "len(value.split(' ')) == len([_ for _ in value.split(' ') if "
                message = "a space separated list of %s values " % TYPE_TO_GALAXY_TYPE[param.type]

                if param.restrictions.n_min is not None and param.restrictions.n_max is not None:
                    expression += " %s <= %s(_) <= %s" % (param.restrictions.n_min, param.type.__name__, param.restrictions.n_max)
                    message += "in the range %s:%s " % (param.restrictions.n_min, param.restrictions.n_max)
                elif param.restrictions.n_min is not None:
                    expression += " %s <= %s(_)" % (param.restrictions.n_min, param.type.__name__)
                    message += "in the range %s: " % (param.restrictions.n_min)
                elif param.restrictions.n_max is not None:
                    expression += " %s(_) <= %s" % (param.type.__name__, param.restrictions.n_max)
                    message += "in the range :%s " % (param.restrictions.n_min)
                expression += "])\n"
                message += "is required"
                validator_node = SubElement(valsan, "validator", OrderedDict([("type", "expression"), ("message", message)]))
                validator_node.text = CDATA(expression)
        else:
            # add quotes to the default values (only if they include spaces .. then the UI looks nicer)
            if not (param.default is None or param.default is _Null) and param.type is not _InFile:
                if type(param.default) is list:
                    for i, d in enumerate(param.default):
                        if " " in d:
                            param.default[i] = '"%s"' % d
#                 elif " " in param.default:
#                     param.default = '"%s"' %param.default
    # add sanitizer nodes to
    # - text (only those that are not actually integer selects which are treated above) and
    # - select params,
    # this is needed for special character like "[" which are used for example by FeatureFinderMultiplex
    if ((param_type == "text" and not TYPE_TO_GALAXY_TYPE[param.type] in ["integer", "float"]) or is_selection_parameter(param)) and param.type is not _InFile:
        if not is_selection_parameter(param):
            valsan = expand_macro(param_node, "list_string_val")
        valsan = expand_macro(param_node, "list_string_san")

    # check for default value
    if not (param.default is None or param.default is _Null):
        # defaults of selects are set via the selected attribute of the options (happens above)
        if param_type == "select":
            pass
        elif type(param.default) is list:
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
    elif param.type is int or param.type is float or param.type is str:
        if param_type == "select":
            pass
        else:
            param_node.attrib["value"] = ""

    # add label, help, and argument
    label = "%s parameter" % param.name
    help_text = ""

    if param.description is not None:
        label, help_text = generate_label_and_help(param.description)
    if param.is_list and not is_selection_parameter(param) and param.type is not _InFile:
        help_text += " (space separated list, in order to allow for spaces in list items surround them by single quotes)"
    if param.type is _InFile:
        if param.is_list:
            help_text += " select %s data sets(s)" % (",".join(get_formats(param, supported_file_formats, TYPE_TO_GALAXY_TYPE[_InFile])))
        else:
            help_text += " select a %s data set" % (",".join(get_formats(param, supported_file_formats, TYPE_TO_GALAXY_TYPE[_InFile])))

    param_node.attrib["label"] = label
    param_node.attrib["help"] = help_text


def generate_label_and_help(desc):
    help_text = ""
    # This tag is found in some descriptions
    if not isinstance(desc, str):
        desc = str(desc)
#     desc = desc.encode("utf8")
    desc = desc.replace("#br#", " <br>")
    # Get rid of dots in the end
    if desc.endswith("."):
        desc = desc.rstrip(".")
    # Check if first word is a normal word and make it uppercase
    if str(desc).find(" ") > -1:
        first_word, rest = str(desc).split(" ", 1)
        if str(first_word).islower():
            # check if label has a quotient of the form a/b
            if first_word.find("/") != 1:
                first_word.capitalize()
        desc = first_word + " " + rest
#     label = desc.decode("utf8")
    label = desc

    # split delimiters ".,?!;("
    if len(desc) > 50:
        m = re.search(r"([.?!] |e\.g\.|\(e\.g\.|i\.e\.|\(i\.e\.)", desc)
        if m is not None:
            label = desc[:m.start()].rstrip(".?!, ")
            help_text = desc[m.start():].lstrip(".?!, ")

#     # Try to split the label if it is too long
#     if len(desc) > 50:
#         # find an example and put everything before in the label and the e.g. in the help
#         if desc.find("e.g.") > 1 :
#             label, help_text = desc.split("e.g.",1)
#             help_text = "e.g." + help_text
#         else:
#             # find the end of the first sentence
#             # look for ". " because some labels contain .file or something similar
#             delimiter = ""
#             if desc.find(". ") > 1 and desc.find("? ") > 1:
#                 if desc.find(". ") < desc.find("? "):
#                     delimiter = ". "
#                 else:
#                     delimiter = "? "
#             elif desc.find(". ") > 1:
#                 delimiter = ". "
#             elif desc.find("? ") > 1:
#                 delimiter = "? "
#             if delimiter != "":
#                 label, help_text = desc.split(delimiter, 1)
#
#             # add the question mark back
#             if delimiter == "? ":
#                 label += "? "

    # remove all linebreaks
    label = label.rstrip().rstrip('<br>').rstrip()
    return label, help_text


def is_boolean_parameter(param):
    """
    determines if the given choices are boolean (basically, if the possible values are true/false)
    @param param the ctd parameter
    @return True iff a boolean parameter
    """
    # detect boolean selects of OpenMS
    if type(param.restrictions) is _Choices:
        return set(param.restrictions.choices) == set(["true", "false"])
    else:
        return param.type is bool


def is_selection_parameter(param):
    """
    determines if there are choices for the parameter and its not bool
    @param param the ctd parameter
    @return True iff a selection parameter
    """
    if type(param.restrictions) is _Choices:
        return set(param.restrictions.choices) != set(["true", "false"])


def get_lowercase_list(some_list):
    return [str(_).lower().strip() for _ in some_list]


def create_boolean_parameter(param_node, param):
    """
    creates a galaxy boolean parameter type
    this method assumes that param has restrictions, and that only two restictions are present
    (either yes/no or true/false)

    TODO: true and false values can be way more than 'true' and 'false'
        but for that we need CTD support
    """

    # in ctd (1.6.2) bools are strings with restriction true,false
    # - if the default is false then they are flags
    # - otherwise the true or false value needs to be added (where the true case is unnecessary)
    # A special case are restrictions false,true which are not treated as flags
    if param.type == str:
        choices = get_lowercase_list(param.restrictions.choices)
        if set(choices) == set(["true", "false"]):
            param_node.attrib["truevalue"] = "true"
            param_node.attrib["falsevalue"] = "false"
        else:
            param_node.attrib["truevalue"] = choices[0]
            param_node.attrib["falsevalue"] = choices[1]

        # set the checked attribute
        if param.default is not None:
            checked_value = "false"
            default = param.default.lower().strip()
            if default == "yes" or default == "true":
                checked_value = "true"
            param_node.attrib["checked"] = checked_value
    else:
        param_node.attrib["truevalue"] = "true"
        param_node.attrib["falsevalue"] = "false"
        param_node.attrib["checked"] = str(param.default).lower()


def create_outputs(parent, model, **kwargs):
    """
    create outputs section of the Galaxy tool
    @param tool the Galaxy tool
    @param model the ctd model
    @param kwargs
      - parameter_hardcoder and
      - supported_file_formats ()
    """
    outputs_node = add_child_node(parent, "outputs")
    parameter_hardcoder = kwargs["parameter_hardcoder"]

    for param in utils.extract_and_flatten_parameters(model):
        param = modify_param_for_galaxy(param)
        # no need to show hardcoded parameters
        hardcoded_value = parameter_hardcoder.get_hardcoded_value(utils.extract_param_name(param), model.name)
        if parameter_hardcoder.get_blacklist(utils.extract_param_name(param), model.name) or hardcoded_value:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is not _OutFile:
            continue
        create_output_node(outputs_node, param, model, kwargs["supported_file_formats"], parameter_hardcoder)

    # If there are no outputs defined in the ctd the node will have no children
    # and the stdout will be used as output
    if len(outputs_node) == 0:
        add_child_node(outputs_node, "data",
                       OrderedDict([("name", "param_stdout"), ("format", "txt"), ("label", "Output from stdout")]))
    return outputs_node


def create_output_node(parent, param, model, supported_file_formats, parameter_hardcoder):

    # add a data node / collection + discover_datasets
    # in the former case we just set the discover_node equal to the data node
    # then we can just use this to set the common format attribute
    if not param.is_list:
        data_node = add_child_node(parent, "data")
        discover_node = data_node
    else:
        data_node = add_child_node(parent, "collection")
        data_node.attrib["type"] = "list"
        discover_node = add_child_node(data_node, "discover_datasets",
                                       OrderedDict([("directory", get_galaxy_parameter_path(param))]))

    data_node.attrib["name"] = param.name
    data_node.attrib["label"] = "${tool.name} on ${on_string}: %s" % param.name

    formats = get_formats(param, supported_file_formats, TYPE_TO_GALAXY_TYPE[_OutFile])
    type_param = get_out_type_param(param, model, parameter_hardcoder)
    corresponding_input, fmt_from_corresponding = get_corresponding_input(param, model)

    # if there is only a single possible output format we set this
#     logger.error("%s %s %s %s %s" %(param.name, formats, type_param, fmt_from_corresponding, corresponding_input))
    if len(formats) == 1:
        discover_node.attrib["format"] = formats.pop()
        if param.is_list:
            discover_node.attrib["pattern"] = "__name__"
    # if there is another parameter where the user selects the format
    # then this format was added as file extension on the CLI, now we can discover this
    elif type_param is not None:
        if not param.is_list:
            change_node = add_child_node(data_node, "change_format")
            for r in type_param.restrictions.choices:
                f = get_supported_file_type(r, supported_file_formats)
                # TODO this should not happen for fully specified fileformats file
                if f is None:
                    f = r
                add_child_node(change_node, "when", OrderedDict([("input", get_galaxy_parameter_name(type_param)), ("value", r), ("format", f)]))
        else:
            discover_node.attrib["pattern"] = "__name_and_ext__"
    elif corresponding_input is not None:
        if param.is_list:
            discover_node.attrib["pattern"] = "__name_and_ext__"
#             data_node.attrib["structured_like"] = get_galaxy_parameter_name(corresponding_input)
            # data_node.attrib["inherit_format"] = "true"
        else:
            data_node.attrib["format_source"] = get_galaxy_parameter_path(corresponding_input)
            data_node.attrib["metadata_source"] = get_galaxy_parameter_path(corresponding_input)
    else:
        if not param.is_list:
            data_node.attrib["auto_format"] = "true"
        else:
            raise InvalidModelException("No way to know the format for"
                                        "for output [%(name)s]" % {"name": param.name})


#     # data output has fomat (except if fromat_source has been added already)
#     # note .. collection output has no format
#     if not param.is_list and not "format_source" in data_node.attrib:
#         data_node.attrib["format"] = data_format

    # add filter for optional parameters
    if not param.required:
        filter_node = add_child_node(data_node, "filter")
        filter_path = utils.extract_param_path(param)
        filter_path[-1] += "_FLAG"
        filter_node.text = filter_path[0] + "".join(['["' + _ + '"]' for _ in filter_path[1:]])
        if len(filter_path) == 1 and param.advanced:
            filter_node.text = "{aon}cond['{aon}selector'] == 'advanced' and {aon}cond['".format(aon=ADVANCED_OPTIONS_NAME) + filter_node.text + "']"
    return data_node


# Get the supported file format for one given format (w galaxy extensions)
def get_supported_file_type(format_name, supported_file_formats):
    if format_name in supported_file_formats.keys():
        return supported_file_formats[format_name].galaxy_extension
    else:
        return None


def get_supported_file_types(formats, supported_file_formats):
    r = set()
    for f in formats:
        if f in supported_file_formats:
            r.add(supported_file_formats[f].galaxy_extension)
    return r
#         print f, f in supported_file_formats, supported_file_formats[f].galaxy_extension
#     return set([supported_file_formats[_].galaxy_extension
#                for _ in formats if _ in supported_file_formats])


def create_change_format_node(parent, data_formats, input_ref):
    #  <change_format>
    #    <when input="secondary_structure" value="true" format="txt"/>
    #  </change_format>
    change_format_node = add_child_node(parent, "change_format")
    for data_format in data_formats:
        add_child_node(change_format_node, "when",
                       OrderedDict([("input", input_ref), ("value", data_format), ("format", data_format)]))


def create_tests(parent, inputs=None, outputs=None, test_macros_prefix=None, name=None):
    """
    create tests section of the Galaxy tool
    @param tool the Galaxy tool
    @param inputs a copy of the inputs
    """
    tests_node = add_child_node(parent, "tests")

    if not (inputs is None or outputs is None):
        fidx = 0
        test_node = add_child_node(tests_node, "test")
        strip_elements(inputs, "validator", "sanitizer")
        for node in inputs.iter():
            if node.tag == "expand" and node.attrib["macro"] == ADVANCED_OPTIONS_NAME + "macro":
                node.tag = "conditional"
                node.attrib["name"] = ADVANCED_OPTIONS_NAME + "cond"
                add_child_node(node, "param", OrderedDict([("name", ADVANCED_OPTIONS_NAME + "selector"), ("value", "advanced")]))
            if "type" not in node.attrib:
                continue

            if (node.attrib["type"] == "select" and "true" in set([_.attrib.get("selected", "false") for _ in node])) or\
               (node.attrib["type"] == "select" and node.attrib.get("value", "") != ""):
                node.tag = "delete_node"
                continue

            # TODO make this optional (ie add aparameter)
            if node.attrib["optional"] == "true" and node.attrib["type"] != "boolean":
                node.tag = "delete_node"
                continue

            if node.attrib["type"] == "boolean":
                if node.attrib["checked"] == "true":
                    node.attrib["value"] = "true"  # node.attrib["truevalue"]
                else:
                    node.attrib["value"] = "false"  # node.attrib["falsevalue"]
            elif node.attrib["type"] == "text" and node.attrib["value"] == "":
                node.attrib["value"] = "1 2"  # use a space separated list here to cover the repeat (int/float) case
            elif node.attrib["type"] == "integer" and node.attrib["value"] == "":
                node.attrib["value"] = "1"
            elif node.attrib["type"] == "float" and node.attrib["value"] == "":
                node.attrib["value"] = "1.0"
            elif node.attrib["type"] == "select":
                if node.attrib.get("display", None) == "radio" or node.attrib.get("multiple", "false") == "false":
                    node.attrib["value"] = node[0].attrib["value"]
                elif node.attrib.get("multiple", None) == "true":
                    print(node)
                    node.attrib["value"] = ",".join([_.attrib["value"] for _ in node if "value" in _.attrib])
            elif node.attrib["type"] == "data":
                node.attrib["ftype"] = node.attrib["format"].split(',')[0]
                if node.attrib.get("multiple", "false") == "true":
                    node.attrib["value"] = "{fidx}test.ext,{fidx}test2.ext".format(fidx=fidx)
                else:
                    node.attrib["value"] = "{fidx}test.ext".format(fidx=fidx)
                fidx += 1
        for node in inputs.iter():
            for a in set(node.attrib) - set(["name", "value", "ftype"]):
                del node.attrib[a]
        strip_elements(inputs, "delete_node", "option", "expand")
        for node in inputs:
            test_node.append(node)

        outputs_cnt = 0
        for node in outputs.iter():
            if node.tag == "data" or node.tag == "collection":
                # assuming that all filters avaluate to false
                has_filter = False
                for c in node:
                    if c.tag == "filter":
                        has_filter = True
                        break
                if not has_filter:
                    outputs_cnt += 1
                else:
                    node.tag = "delete_node"
            if node.tag == "data":
                node.tag = "output"
                try:
                    node.attrib["ftype"] = node.attrib["format"]
                except KeyError:
                    pass
                node.attrib["value"] = "outfile.txt"
            if node.tag == "collection":
                node.tag = "output_collection"
            if node.attrib.get("name", None) == "param_stdout":
                node.attrib["lines_diff"] = "2"
            for a in set(node.attrib) - set(["name", "value", "ftype", "lines_diff"]):
                del node.attrib[a]
        strip_elements(outputs, "delete_node", "discover_datasets", "filter", "change_format")

        for node in outputs:
            test_node.append(node)
        test_node.attrib["expect_num_outputs"] = str(outputs_cnt)
    elif not (test_macros_prefix is None or name is None):
        expand_macros(tests_node, [p + name for p in test_macros_prefix])


def create_test_only(model, **kwargs):

    parameter_hardcoder = kwargs["parameter_hardcoder"]

    section_nodes = dict()
    section_params = dict()

    test = Element("test")
    advanced = None

    for param in utils.extract_and_flatten_parameters(model, True):
        try:
            parent = section_nodes[utils.extract_param_name(param.parent)]
        except KeyError:
            parent = test

        if utils.extract_param_name(param.parent) in section_nodes:
            parent = section_nodes[utils.extract_param_name(param.parent)]
        elif type(param) is not ParameterGroup and param.advanced:
            if advanced is None:
                advanced = add_child_node(test, "conditional", OrderedDict([("name", "adv_opts_cond")]))
                adv_sel = add_child_node(advanced, "param", OrderedDict([("name", "adv_opts_selector"), ("value", "advanced")]))
            parent = advanced
        else:
            parent = test

        if type(param) is ParameterGroup:
            section_params[utils.extract_param_name(param)] = param
            section_nodes[utils.extract_param_name(param)] = add_child_node(parent, "section", OrderedDict([("name", param.name)]))
            continue
        if param.type is _OutFile and not param.required:
            nd = add_child_node(parent, "param", OrderedDict([("name", param.name + "_FLAG"), ("value", "false")]))

            formats = get_formats(param, kwargs["supported_file_formats"], TYPE_TO_GALAXY_TYPE[_OutFile])
            type_param = get_out_type_param(param, model, parameter_hardcoder)
            corresponding_input, fmt_from_corresponding = get_corresponding_input(param, model)
            if len(formats) > 1 and type_param is None and (corresponding_input is None or not fmt_from_corresponding) and not param.is_list:
                fmt_select = add_child_node(parent, "param", OrderedDict([("name", param.name + "_type"), ("value", "")]))

        if param.is_list and type(param.default) is not _Null:
            value = '"' + '" "'.join(map(str, param.default)) + '"'
        else:
            value = str(param.default)

        nd = add_child_node(parent, "param" if param.type is not _OutFile else "output", OrderedDict([("name", param.name), ("value", value)]))
    return test


def create_help(tool, model):
    """
    create help section of the Galaxy tool
    @param tool the Galaxy tool
    @param model the ctd model
    @param kwargs
    """
    help_node = add_child_node(tool, "help")
    help_node.text = CDATA(utils.extract_tool_help_text(model))


def add_child_node(parent_node, child_node_name, attributes=OrderedDict([]), text=None):
    """
    helper function to add a child node using the given name to the given parent node
    @param parent_node the parent
    @param child_node_name the desired name of the child
    @param attributes desired attributes of the child
    @return the created child node
    """
    child_node = SubElement(parent_node, child_node_name, attributes)
    if text is not None:
        child_node.text = text
    return child_node
