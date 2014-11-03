#!/usr/bin/env python
# encoding: utf-8
'''
@author:     delagarza

'''


import sys
import os
import traceback
import ntpath
import string
from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from CTDopts.CTDopts import CTDModel, _InFile, _OutFile, ParameterGroup, _Choices, _NumericRange, _FileFormat, ModelError
 

from lxml.etree import SubElement, Element, ElementTree
from collections import OrderedDict

from string import strip
from mercurial.revset import desc

__all__ = []
__version__ = 0.11
__date__ = '2014-09-17'
__updated__ = '2014-09-17'

TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data', 
                       _OutFile: 'data', _Choices: 'select'}
COMMAND_REPLACE_PARAMS = {'threads': '\${GALAXY_SLOTS:-24} ', "processOption":"inmemory"}
SUPPORTED_FILE_TYPES = ["svg","jpg","png","fasta","HTML","mzXML","mzML","mgf","featureXML","XML","consensusXML","idXML","pepXML", "txt", "csv", "traML", "TraML", "mzq", "trafoXML", "tsv", "msp", "qcML"]
FILE_TYPES_TO_GALAXY_DATA_TYPES = {'csv': 'tabular', 'XML':'xml', 'HTML':'html', 'traML':'traml', 'TraML':'traml', 'trafoXML':'trafoxml', 'tsv':'tabulear', 'qcML':'qcml' }

class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg
    
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

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = "GalaxyConfigGenerator - A project from the GenericWorkflowNodes family (https://github.com/orgs/genericworkflownodes)"
    program_usage = '''
    USAGE:
    
    Parse a single CTD file and generate a Galaxy wrapper:
    $ python generator.py -i input.ctd -o output.xml
    
    Parse all found CTD files (files with .ctd and .xml extension) in a given folder and output converted Galaxy wrappers in a given folder:
    $ python generator.py -input-directory /home/johndoe/*.ctd -o /home/johndoe/galaxywrappers
    '''
    program_license = '''%(shortdesc)s
    Copyright 2014, Luis de la Garza

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
''' % {'shortdesc':program_shortdesc, 'usage':program_usage}

    

    try:
        # Setup argument parser
        parser = ArgumentParser(prog="GalaxyConfigGenerator", description=program_license, formatter_class=RawDescriptionHelpFormatter, add_help=True)
        parser.add_argument("-i", "--input", dest="input_files", required=True, nargs="+", action="append",
                            help="list of CTD files to convert.")
        parser.add_argument("-o", "--output-destination", dest="output_dest", required=True, 
                            help="if multiple input files are given, then a folder in which all generated XMLs will generated is expected;"\
                            "if a single input file is given, then a destination file is expected.")
        parser.add_argument("-a", "--add-to-command-line", dest="add_to_command_line", help="adds content to the command line", default="", required=False)
        parser.add_argument("-w", "--whitespace-validation", dest="whitespace_validation", action="store_true", default=False,
                            help="if true, each parameter in the generated command line will be "+ 
                                 "validated against emptiness or being equal to 'None'", required=False)
        parser.add_argument("-q", "--quote-parameters", dest="quote_parameters", action="store_true", default=False,
                            help="if true, each parameter in the generated command line will be quoted", required=False)
        parser.add_argument("-b", "--blacklist", dest="blacklisted_parameters", default=[], nargs="+", action="append",
                             help="list of parameters that will be ignored and won't appear on the galaxy stub", required=False)
        parser.add_argument("-p", "--package-requirement", dest="package_requirements", default=[], nargs="+", action="append", 
                            help="list of required galaxy packages", required=False)
        parser.add_argument("-d", "--default-category", dest="default_category", default="DEFAULT", required=False, 
                            help="default category to use for tools lacking a category when generating tool_conf.xml")
        parser.add_argument("-x", "--exit-code", dest="exit_codes", default=[], nargs="+", action="append",
                            help="list of <stdio> galaxy exit codes, in the following format: range=<range>,level=<level>,description=<description>,\n" +
                                 "example: --exit-codes \"range=3:4,level=fatal,description=Out of memory\"")
        parser.add_argument("-t", "--tool-conf-destination", dest="tool_conf_dest", default=None, required=False,
                            help="specify the destination file of a generated tool_conf.xml for all given input files; each category will be written in its own section.")
        parser.add_argument("-g", "--galaxy-tool-path", dest="galaxy_tool_path", default=None, required=False,
                            help="the path that will be prepended to the file names when generating tool_conf.xml")
        parser.add_argument("-l", "--tools-list-file", dest="tools_list_file", default=None, required=False,
                            help="list of tools that need to be translated.")
        parser.add_argument("-s", "--skip", dest="skip_tools", default=[], nargs="+", action="append",
                             help="list of that don't need to be generated", required=False)
        # verbosity will be added later on, will not waste time on this now
        # parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument("-V", "--version", action='version', version=program_version_message)
        
        # Process arguments
        args = parser.parse_args()
        
        # validate and prepare the passed arguments
        validate_and_prepare_args(args)
        
        #if verbose > 0:
        #    print("Verbose mode on")
        convert(args.input_files, 
                args.output_dest, 
                add_to_command_line=args.add_to_command_line, 
                whitespace_validation=args.whitespace_validation,
                quote_parameters=args.quote_parameters,
                blacklisted_parameters=args.blacklisted_parameters,
                tools_list_file=args.tools_list_file,
                skip_tools=args.skip_tools,
                package_requirements=args.package_requirements,
                exit_codes=args.exit_codes,
                galaxy_tool_path=args.galaxy_tool_path,
                tool_conf_dest=args.tool_conf_dest,
                default_category=args.default_category)
        return 0

    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except ApplicationException, e:
        sys.stderr.write("GalaxyConfigGenerator could not complete the requested operation.\n")
        sys.stderr.write("Reason: " + e.msg)
        return 1
    except ModelError, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "There seems to be a problem with one your input CTD.\n")
        sys.stderr.write(indent + "For help use --help\n")
        return 1
    except Exception, e:
        traceback.print_exc()
        return 2
    
def validate_and_prepare_args(args):
    # first, we convert all list of lists to flat lists
    args.input_files = [item for sublist in args.input_files for item in sublist]
    args.blacklisted_parameters=[item for sublist in args.blacklisted_parameters for item in sublist]
    args.skip_tools=[item for sublist in args.skip_tools for item in sublist]
    args.package_requirements=[item for sublist in args.package_requirements for item in sublist]
    args.exit_codes=convert_exit_codes([item for sublist in args.exit_codes for item in sublist])
    
    # if input is a single file, we expect output to be a file (and not a dir that already exists)
    if len(args.input_files) == 1:
        if os.path.isdir(args.output_dest):
            raise ApplicationException("If a single input file is provided, output (%s) is expected to be a file and not a folder." % args.output_dest)
        
    # if input is a list of files, we expect output to be a folder
    if len(args.input_files) > 1:
        if not os.path.isdir(args.output_dest):
            raise ApplicationException("If several input files are provided, output (%s) is expected to be an existing directory." % args.output_dest)
        
            
    
def convert_exit_codes(exit_codes_raw):
    # input is in the format:
    # range=3:4,level=fatal,description=Out of memory
    exit_codes = []
    errors_so_far = ""
    for exit_code_raw in exit_codes_raw:
        exit_code = ExitCode()
        required_keys = ["range", "level"]
        valid_keys = required_keys[:]
        valid_keys.append("description")
        obtained_values = dict()
        
        for key_value in exit_code_raw.split(","):
            # each key_value contains something like range=3 or description=whatever
            # so we can split again by using "="
            key_value_split = key_value.split("=")
            if len(key_value_split) == 2:
                obtained_values[key_value_split[0]] = key_value_split[1].strip()
            else:
                errors_so_far += "Unrecognized format [%s] found in exit-code parameter. Allowed format is [key=value]\n" % key_value
            
        # do some sanity check and report non-recognized keys
        for (key, value) in obtained_values.iteritems():
            # check if the key is in the valid keys
            if not key in valid_keys:
                errors_so_far += "Unrecognized property [%(key)s] found in exit-code parameter [%(exit_code)s]\n" % {"key":key, "exit_code":exit_code_raw}
            else:
                # we know it's a valid key, so let's use it
                setattr(exit_code, key, value)
                
        # now, let's check that all required keys were given
        for key in required_keys:
            if key not in obtained_values:
                errors_so_far += "Required property [%(key)s] was not found in exit-code parameter [%(exit_code)s]\n" % {"key":key, "exit_code":exit_code_raw}
        exit_codes.append(exit_code)        
    
    # stop processing if errors were found
    if len(errors_so_far) > 0:
        raise ApplicationException(errors_so_far)    
         
    return exit_codes
    
def convert(input_files, output_dest, **kwargs):
    # if a file with a list of needed tools is given they are put in the tools list
    needed_tools = []
    if kwargs["tools_list_file"] is not None:
        try:
            with open(kwargs["tools_list_file"]) as f:
                for line in f:
                    needed_tools.append(line.rstrip())
        except IOError, e:
            print "The provided input file " + str(kwargs["tools_list_file"]) + " could not be accessed. Detailed information: " + str(e) + "\n"
    # first, generate a model
    is_converting_multiple_ctds = len(input_files) > 1 
    parsed_models = []
    try:
        for input_file in input_files:
            toolname = os.path.splitext(os.path.basename(input_file))[0]
            if toolname in kwargs["skip_tools"] or (kwargs["tools_list_file"] is not None and toolname not in needed_tools):
                print("Skipping %s" % toolname)
                continue
            else:
                print("Parsing CTD from [%s]" % input_file)
                try:
                    model = CTDModel(from_file=input_file)
                except Exception, e:
                    print str(e)
                    continue
                tool = create_tool(model)
    
                tree = ElementTree(tool)
    
                create_description(tool, model)
                create_macros(tool, model)
                create_command(tool, model, **kwargs)
                #create_configfiles(tool, model, kwargs["blacklisted_parameters"])
                create_inputs(tool, model, kwargs["blacklisted_parameters"])
                create_outputs(tool, model, kwargs["blacklisted_parameters"])
                create_help(tool, model)
                
                # finally, serialize the tool
                output_file = output_dest
                # if multiple inputs are being converted, then we need to generate a different output_file for each input
                if is_converting_multiple_ctds:
                    #if not output_file.endswith('/'):
                    #    output_file += "/"
                    #output_file += get_filename(input_file) + ".xml"
                    output_file = os.path.join( output_file, get_filename_without_suffix(input_file) + ".xml" )
                tree.write(open(output_file,'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)
                # let's use model to hold the name of the outputfile
                parsed_models.append([model, get_filename(output_file)])
                #print("Generated Galaxy wrapper in [%s]\n" % output_file)
    
                macro_file = os.path.join( os.path.dirname( output_file ), 'macros.xml' )
                if not os.path.exists( macro_file ):
                    macro_node = Element("macros")
                    macro_tree = ElementTree(macro_node)
                    create_requirements_macro(macro_node, kwargs["package_requirements"])
                    create_exit_codes_macro(macro_node, kwargs["exit_codes"])
                    create_reference_macro(macro_node)
                    create_advanced_selector_macro(macro_node )
                    macro_tree.write(open(macro_file,'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)

        # generation of galaxy stubs is ready... now, let's see if we need to generate a tool_conf.xml
        if kwargs["tool_conf_dest"] is not None:
            generate_tool_conf(parsed_models, kwargs["tool_conf_dest"], kwargs["galaxy_tool_path"], kwargs["default_category"])
                
    except IOError, e:
        raise ApplicationException("One of the provided input files or the destination file could not be accessed. Detailed information: " + str(e) + "\n")
    
def generate_tool_conf(parsed_models, tool_conf_dest, galaxy_tool_path, default_category):
    # for each category, we keep a list of models corresponding to it
    categories_to_tools = dict()
    for model in parsed_models:
        category = strip(model[0].opt_attribs.get("category", default_category))
        if category not in categories_to_tools:
            categories_to_tools[category] = []
        categories_to_tools[category].append(model[1])
                
    # at this point, we should have a map for all categories->tools
    toolbox_node = Element("toolbox")
    toolconf_tree = ElementTree(toolbox_node)

    
    if galaxy_tool_path is not None and not galaxy_tool_path.strip().endswith("/"):
        galaxy_tool_path = galaxy_tool_path.strip() + "/"
    if galaxy_tool_path is None:
        galaxy_tool_path = ""
    
    for category, filenames in categories_to_tools.iteritems():
        section_node = SubElement(toolbox_node, "section")
        section_node.attrib["id"] = "section-id-" + "".join(category.split())
        section_node.attrib["name"] = category
    
        for filename in filenames:
            tool_node = SubElement(section_node, "tool")
            tool_node.attrib["file"] = galaxy_tool_path + filename

    toolconf_tree.write(open(tool_conf_dest,'w'), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    print("Generated Galaxy tool_conf.xml in [%s]\n" % tool_conf_dest)
    
# taken from
# http://stackoverflow.com/questions/8384737/python-extract-file-name-from-path-no-matter-what-the-os-path-format
def get_filename(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def get_filename_without_suffix(path):
    root, ext = os.path.splitext(os.path.basename(path))
    return root 

def create_tool(model):
    
    tool = Element("tool", OrderedDict([("id",model.name),("name",model.name),("version",model.version)]))
    # use the same name of the tool... maybe a future version would contain a way to add a specific ID?  tool.setAttribute("id", model.name)
    return tool

def create_description(tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description = SubElement(tool,"description")
        description.text = model.opt_attribs["description"]


def get_param_name( param ):
    if type(param.parent) == ParameterGroup and param.parent.name != '1':
        return get_param_name(param.parent) + ":" + param.name
    else:
        return param.name

def create_command(tool, model, **kwargs):
    final_command = get_tool_executable_path(model) + '\n'
    final_command += kwargs["add_to_command_line"] + '\n'
    whitespace_validation = kwargs["whitespace_validation"]
    quote_parameters = kwargs["quote_parameters"]

    advanced_command_start = "#if $adv_opts.adv_opts_selector=='advanced':\n"
    advanced_command_end = '#end if'
    advanced_command = ''

    for param in extract_parameters(model):
        command = ''
        param_name = get_param_name( param )

        if param.name in kwargs["blacklisted_parameters"]:
            if param.name in COMMAND_REPLACE_PARAMS:
                # replace the param value with a hardcoded value, for example the GALAXY_SLOTS ENV
                command += '-%s %s\n' %  ( param_name, COMMAND_REPLACE_PARAMS[param.name])
            else:
                # let's not use an extra level of indentation and use NOP
                continue
        else:
            galaxy_parameter_name = get_galaxy_parameter_name(param.name)
            repeat_galaxy_parameter_name = get_repeat_galaxy_parameter_name(param.name)

            # logic for ITEMLISTs
            if param.is_list:
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
                if param.advanced:
                    actual_parameter = "$adv_opts.%s" % galaxy_parameter_name
                else:
                    actual_parameter = "$%s" % galaxy_parameter_name
                ## if whitespace_validation has been set, we need to generate, for each parameter:
                ## #if str( $t ).split() != '':
                ## -t "$t"
                ## #end if
                ## TODO only useful for text fields, integers or floats
                ## not useful for choices, input fields ...
                ##if whitespace_validation:
                    #command += "\n#if str($%(param_name)s).strip() != '':\n    "  % {"param_name": galaxy_parameter_name}
                # This has been taken out and replaced with a check for None


                if not is_boolean_parameter( param ):
                    command += "#if " + actual_parameter + ":\n"
                    command += '  -%s\n' %  ( param_name ) 
                    command += "  #if \" \" in str("+ actual_parameter +"):\n"
                    command += "    \"" + actual_parameter + "\"\n"
                    command += "  #else\n"
                    command += "    " + actual_parameter + "\n"
                    command += "  #end if\n"
                    command += "#end if\n" 
                else:
                    command += "#if " + actual_parameter + ":\n"
                    command += '  -%s\n' %  ( param_name )
                    command += "#end if\n" 


                # for boolean types, we only need the placeholder
                    # add the parameter name
                    #command += '-%s ' %  ( param_name )
                # we need to add the placeholder
                #if quote_parameters:
                    #actual_parameter = '"%s"' % actual_parameter
                #if whitespace_validation:
                    #command += "#end if\n"

        if param.advanced and param.name not in kwargs["blacklisted_parameters"]:
            advanced_command += "    %s" % command
        else:
            final_command += command

    if advanced_command:
            final_command += "%s%s%s\n" % (advanced_command_start, advanced_command, advanced_command_end)

    command_node = SubElement(tool,"command")
    command_node.text = final_command


def create_macros(tool, model):
    """
        <macros>
            <token name="@EXECUTABLE@">IDFilter</token>
            <import>macros.xml</import>
        </macros>
        <expand macro="stdio" />
        <expand macro="requirements" />
        <expand macro="command" /> -> was used with configfiles
    """
    macros = SubElement(tool,"macros")
    executable = SubElement(macros, "token", OrderedDict([("name","@EXECUTABLE@")]))
    executable.text = get_tool_executable_path(model)
    imports = SubElement(macros, "import")
    imports.text = "macros.xml"
    stdio = SubElement(tool, "expand")
    stdio.attrib["macro"] = "stdio"
    requirements = SubElement(tool, "expand")
    requirements.attrib["macro"] = "requirements"

def get_tool_executable_path(model):
    # rules to build the galaxy executable path:
    # if executablePath is null and executableName is null, then the name of the tool will be used
    # if executablePath is null and executableName is not null, then executableName will be used
    # if executablePath is not null and executableName is null, then executablePaht and the name of the tool will be used
    # if executablePath is not null and executableName is not null, then both will be used
    command = None
    # first, check if the model has executablePath / executableName defined
    executablePath = model.opt_attribs.get("executablePath", None)
    executableName = model.opt_attribs.get("executableName", None)
    # fix the executablePath to make sure that there is a '/' in the end
    if executablePath is not None:
        executablePath = executablePath.strip()
        if not executablePath.endswith('/'):
            executablePath += '/'
        
    if executablePath is None:
        if executableName is None:
            command = model.name
        else:
            command = executableName
    else: 
        if executableName is None:
            command = executablePath + model.name
        else:
            command = executablePath + executableName
    return command
    
def get_galaxy_parameter_name(param_name):
    return "param_%s" % param_name

##
## historical reasons, can be removed later
##
def create_configfiles(tool, model, blacklisted_parameters):
    cf = "[simple_options]\n"
    for param in extract_parameters(model):
        if type(param.parent) == ParameterGroup and param.parent.name != '1':
            prefix = param.parent.name + ":"
        else:
            prefix = ''

        if param.name in blacklisted_parameters:
            if param.name in COMMAND_REPLACE_PARAMS:

                # add the parameter name
                cf += '%s%s=' % ( prefix, param.name )

                # replace the param value with a hardcoded value, for example the GALAXY_SLOTS ENV
                cf += COMMAND_REPLACE_PARAMS[param.name]
            else:
                continue
        else:


            # add the parameter name
            cf += '%s%s=' % ( prefix, param.name )

            # we need to add the placeholder
            cf += "$" + get_galaxy_parameter_name(param.name) + ' '
        cf += '\n'
    configfiles_node = SubElement(tool, "configfiles")
    configfile_node = SubElement(configfiles_node, "configfile")
    configfile_node.text = cf

def create_inputs(tool, model, blacklisted_parameters):
    inputs_node = SubElement(tool, "inputs")

    """
        <expand macro="advanced_options">
        </expand>
    """
    # has to be generated here so other parameters can be appended to it
    expand_advanced_node = Element("expand", OrderedDict([("macro","advanced_options")]))

    collect_inputs = list()

    # treat all non output-file parameters as inputs
    for param in extract_parameters(model):
        if param.name in blacklisted_parameters:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is not _OutFile:
            if param.advanced :
                parent_node = expand_advanced_node
            else:
                parent_node = inputs_node

            # for lists we need a repeat tag
            if param.is_list: 
                rep_node = SubElement ( parent_node, "repeat")
                create_repeat_attribute_list(rep_node, param)
                parent_node = rep_node
                
            param_node = SubElement( parent_node, "param" )
            create_param_attribute_list(param_node, param)

    # advanced paramter selection should be at the end
    # and only available if an advanced parameter exists
    if len(expand_advanced_node) > 0 :
        inputs_node.append(expand_advanced_node)

def get_repeat_galaxy_parameter_name(paramname):
    return "rep_" + get_galaxy_parameter_name(paramname)

def create_repeat_attribute_list(rep_node, param):
    rep_node.attrib["name"] = get_repeat_galaxy_parameter_name(param.name)
    if param.required:
        rep_node.attrib["min"] = "1"
    else:
        rep_node.attrib["min"] = "0"
    # for the ITEMLISTs which have LISTITEM children we only
    # need one parameter as it is given as a string
    if param.default is not None: 
        rep_node.attrib["max"] = "1"
    rep_node.attrib["title"] = get_galaxy_parameter_name(param.name)

    


def get_supported_file_types( file_types ):
    return [ FILE_TYPES_TO_GALAXY_DATA_TYPES.get(file_type, file_type) for file_type in file_types if file_type in SUPPORTED_FILE_TYPES]


def create_param_attribute_list(param_node, param):
    
    #attribute_list["name"] = get_galaxy_parameter_name(param.name)
    param_node.attrib["name"] = get_galaxy_parameter_name(param.name)

    
    param_type = TYPE_TO_GALAXY_TYPE[param.type]
    if param_type is None:
        raise ModelError("Unrecognized parameter type '%(type)' for parameter '%(name)'" % {"type":param.type, "name":param.name})
    # galaxy handles ITEMLIST from CTDs as strings
    if param.is_list:
        param_type = "text"

    if is_selection_parameter(param):
        param_type = "select"
        
    if is_boolean_parameter(param):
        param_type = "boolean"
        
    if param.type is _InFile:
        # assume it's just data unless restrictions are provided
        param_format = "data"
        if param.restrictions is not None:
            # join all supported_formats for the file... this MUST be a _FileFormat
            if type(param.restrictions) is _FileFormat: 
                param_format = ','.join( get_supported_file_types(param.restrictions.formats) )
            else:
                raise InvalidModelException("Expected 'file type' restrictions for input file [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)}) 
        #attribute_list["format"] = str(param_format)
        param_node.attrib["type"] = "data"
        param_node.attrib["format"] = param_format
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
                #print str(choice)
                option_attribute_list = OrderedDict()
                option_attribute_list["value"] = str(choice)
                option_node = SubElement(param_node,"option", option_attribute_list)
                option_node.text = str(choice)

        elif type(param.restrictions) is _NumericRange:
            if param.type is not int and param.type is not float:
                raise InvalidModelException("Expected either 'int' or 'float' in the numeric range restriction for parameter [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)})
            # extract the min and max values and add them as attributes
            # validate the provided min and max values
            if param.restrictions.n_min is not None:
                param_node.attrib["min"] = str(param.restrictions.n_min)
            if param.restrictions.n_max is not None:
                param_node.attrib["max"] = str(param.restrictions.n_max)
        elif type(param.restrictions) is _FileFormat:
            param_node.attrib["format"] = ",".join( get_supported_file_types(param.restrictions.formats) )
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]" % {"type":type(param.restrictions), "name":param.name}) 

        param_node.attrib["optional"] = str(not param.required)

    if param_type == "text":
        # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
        param_node.attrib["size"] = "20"


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
            warning("Generating default value for parameter [%s]. Galaxy requires the attribute 'value' to be set for integer/floats. "\
                    "Edit the CTD file and provide a suitable default value." % param.name)
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
                    # should never be here, since we have validated this anyway... this code is here just for documentation purposes
                    # however, better safe than sorry! (it could be that the code changes and then we have an ugly scenario)
                    raise InvalidModelException("Expected either a numeric range for parameter [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)})
            else:
                # no restrictions and no default value provided...
                # make up something
                default_value = 0
            param_node.attrib["value"] = str(default_value)

    label = ""
    helptext = ""

    if param.description is not None:
        label, helptext = generate_label_and_help(param.description)
    else:
        label = "%s parameter" % param.name
    param_node.attrib["label"] = label
    param_node.attrib["help"] = "(-%s)" % param.name + " "+ helptext

def generate_label_and_help(desc):
    label=""
    helptext=""
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
            label, helptext = desc.split("e.g.",1) 
            helptext = "e.g." + helptext
        else:
            # find the end of the first sentence
            # look for ". " because some labels contain .file or something similar
            delim = ""
            if desc.find(". ") > 1 and desc.find("? ") > 1:
                if desc.find(". ") < desc.find("? "):
                    delim = ". "
                else:
                    delim = "? "
            elif desc.find(". ") > 1:
                delim = ". "
            elif desc.find("? ") > 1:
                delim = "? "
            if delim != "":
                label, helptext = desc.split(delim,1) 

            # add the question mark back
            if delim == "? ":
                label += "? "
    
    label=label.rstrip()

    return (label, helptext)

def warning(text):
    sys.stderr.write("WARNING: " + text + '\n')

# determines if the given choices are boolean (basically, if the possible values are yes/no, true/false)
def is_boolean_parameter(param):
    is_choices = False
    if type(param.restrictions) is _Choices:
        # for a true boolean experience, we need 2 values
        # and also that those two values are either yes/no or true/false
        if len(param.restrictions.choices) == 2:
            choices = get_lowercase_list(param.restrictions.choices)
            if ('yes' in choices and 'no' in choices) or ('true' in choices and 'false' in choices):
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
# this method assumes that param has restrictions, and that only two restictions are present (either yes/no or true/false)
def create_boolean_parameter(param_node, param):
    # first, determine the 'truevalue' and the 'falsevalue'
    """TODO: true and false values can be way more than 'true' and 'false'
        but for that we need CTD support
    """
    truevalue = None
    falsevalue = None
    choices = get_lowercase_list(param.restrictions.choices)
    if "yes" in choices:
        truevalue = "yes"
        falsevalue = "no"
    else:
        #truevalue = "-%s true"   % get_param_name(param)
        #falsevalue = "-%s false" % get_param_name(param)
        truevalue = "-%s"   % get_param_name(param)
        falsevalue = ""
    param_node.attrib["truevalue"] = truevalue
    param_node.attrib["falsevalue"] = falsevalue

    # set the checked attribute
    if param.default is not None:
        checked_value = "false"
        default = strip(string.lower(param.default))
        if default == "yes" or default == "true":
            checked_value = "true"
        #attribute_list["checked"] = checked_value
        param_node.attrib["checked"] = checked_value

def create_outputs(parent, model, blacklisted_parameters):
    outputs_node = SubElement(parent, "outputs")

    for param in extract_parameters(model):
       
        if param.name in blacklisted_parameters:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            create_data_node(outputs_node, param)

def create_data_node(parent, param):
    data_node = SubElement(parent, "data")
    data_node.attrib["name"] = get_galaxy_parameter_name(param.name)

        
    data_format = "data"
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            # set the first data output node to the first fileformat
            formats = get_supported_file_types( param.restrictions.formats )
            try:
                data_format = formats.pop()
            except:
                output = "Parameter: "+ param.name + " has unsupported formats: " 
                for form in param.restrictions.formats:
                    output += str(form)
                print output
            # if there are more than one output file formats from which the
            # user can choose, create "change_format" nodes for all but the first
            if formats:
                #param_out_type is hardcoded for the moment
                create_change_format_node(data_node, formats, 'param_out_type')
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for output [%(name)s]" % {"type":type(param.restrictions), "name":param.name})
    data_node.attrib["format"] = data_format

    if param.description is not None:
        data_node.attrib["label"] = param.description
    
        
    return data_node

def create_filter_node(data_format):
    """
        <filter>'bam' in outputs</filter>
    """
    filter_node = Element("filter")
    # param_out_type is hardcoded for the moment
    filter_node.text = "'%s' in param_out_type" % (data_format)
    return filter_node

def create_change_format_node(parent, data_formats, input_ref):
    """
        <change_format>
            <when input="secondary_structure" value="true" format="text"/>
        </change_format>
    """
    change_format_node = SubElement(parent, "change_format")
    for data_format in data_formats:
        when_node = SubElement(change_format_node, "when")
        when_node.attrib["input"] = input_ref
        when_node.attrib["value"] = data_format
        when_node.attrib["format"] = data_format


def create_requirements_macro(macro, package_requirements):
    # create xml node to define a macro: <xml name="requirements">
    xml_node = SubElement(macro, "xml")
    xml_node.attrib["name"] = "requirements"
    
    if len(package_requirements) > 0:
        requirements_node = SubElement(xml_node, "requirements")
        for package_requirement in package_requirements:
            requirement_node = SubElement(requirements_node, "requirement")
            requirement_node.attrib["type"] = "package"
            requirement_node.text = package_requirement
    else:
        # Add a template
        """
        <requirements>
            <requirement type="binary">@EXECUTABLE@</requirement>
            <requirement type="package" version="1.1.1">TODO</requirement>
        </requirements>
        """
        requirements_node = SubElement(xml_node, "requirements")
        requirement_node = SubElement(requirements_node, "requirement")
        requirement_node.attrib["type"] = "binary"
        requirement_node.text = "@EXECUTABLE@"

        requirement_node = SubElement(requirements_node, "requirement")
        requirement_node.attrib["type"] = "package"
        requirement_node.attrib["version"] = "1.1.1"
        requirement_node.text = "TODO"



    """
        Add a version_command to the macro file.
        <version_command>@EXECUTABLE@ -version</version_command>
    """
    #version_command = SubElement(xml_node, "version_command")
    #version_command.text = "@EXECUTABLE@ -version"



def create_reference_macro(macro):
    # create xml node to define a macro: <token name="@REFERENCES@">
    macro_xml_node = SubElement(macro, "token")
    macro_xml_node.attrib["name"] = "@REFERENCES@"
    macro_xml_node.text = """

-------

**References**

If you use this Galaxy tool in work leading to a scientific publication please
cite the following papers:

"""


def create_exit_codes_macro(macro, exit_codes):
    # create xml node to define a macro: <xml name="stdio">
    macro_xml_node = SubElement(macro, "xml")
    macro_xml_node.attrib["name"] = "stdio"

    if len(exit_codes) > 0:
        stdio_node = SubElement(macro_xml_node, "stdio")
        
        for exit_code in exit_codes:
            exit_code_node = SubElement(stdio_node, "exit_code")
            exit_code_node.attrib["range"] = exit_code.range
            exit_code_node.attrib["level"] = exit_code.level
            # description is optional
            if exit_code.description is not None:
                exit_code_node.attrib["description"] = exit_code.description
    else:
        # fill in a template with a meaningful defaul
        """
            <!-- Anything other than zero is an error -->
            <exit_code range="1:" />
            <exit_code range=":-1" />
            <!-- In case the return code has not been set propery check stderr too -->
            <regex match="Error:" />
            <regex match="Exception:" />
        """
        stdio_node = SubElement(macro_xml_node, "stdio")
        exit_code_node = SubElement(stdio_node, "exit_code")
        exit_code_node.attrib["range"] = "1:"
        exit_code_node = SubElement(stdio_node, "exit_code")
        exit_code_node.attrib["range"] = ":-1"
        exit_code_node = SubElement(stdio_node, "regex")
        exit_code_node.attrib["match"] = "Error:"
        exit_code_node = SubElement(stdio_node, "regex")
        exit_code_node.attrib["match"] = "Exception:"


def create_advanced_selector_macro(macro):
    """
    Append one macro to the macro file:
    <xml name="advanced_options">
       <conditional name="adv_opts">
            <param name="adv_opts_selector" type="select" label="Advanced Options">
              <option value="basic" selected="True">Hide Advanced Options</option>
              <option value="advanced">Show Advanced Options</option>
            </param>
            <when value="basic" />
            <when value="advanced">
                <yield />
            </when>
        </conditional>
    </xml>
    """

    # create xml node to define a macro: <xml name="stdio">
    macro_xml_node = SubElement(macro, "xml")
    macro_xml_node.attrib["name"] = "advanced_options"

    conditional_node = SubElement(macro_xml_node, "conditional")
    conditional_node.attrib['name'] = 'adv_opts'

    param_node = SubElement(conditional_node, "param")
    param_node.attrib['name'] = 'adv_opts_selector'
    param_node.attrib['type'] = 'select'
    param_node.attrib['label'] = 'Advanced Options'

    option_node = SubElement(param_node, "option")
    option_node.attrib['value'] = 'basic'
    option_node.attrib['selected'] = 'True'
    option_node.text = 'Hide Advanced Options'

    option_node = SubElement(param_node, "option")
    option_node.attrib['value'] = 'advanced'
    option_node.text = 'Show Advanced Options'

    when_node = SubElement(conditional_node, "when")
    when_node.attrib['value'] = 'basic'

    when_node = SubElement(conditional_node, "when")
    when_node.attrib['value'] = 'advanced'
    yield_node = SubElement(when_node, 'yield')


def create_help(tool, model):
    """
**What it does**

Shows basic information about the file, such as data ranges and file type.

    """
    manual = '**What it does**\n\n'
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
    help_text += "\n\n@REFERENCES@\n"
    help_node = SubElement(tool, "help")
    help_node.text = help_text
    # TODO: do we need CDATA Section here?
    
# since a model might contain several ParameterGroup elements, we want to simply 'flatten' the parameters to generate the Galaxy wrapper    
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
    # returned the reversed list of parameters (as it is now, we have the last parameter in the CTD as first in the list)
    return reversed(parameters)
    
class InvalidModelException(ModelError):
    def __init__(self, message):
        super(InvalidModelException, self).__init__()
        self.message = message

    def __str__(self):
        return self.message
    
    def __repr__(self):
        return self.message
        
if __name__ == "__main__":
    sys.exit(main())
