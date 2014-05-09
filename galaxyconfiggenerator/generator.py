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

from xml.dom.minidom import Document
from string import strip

__all__ = []
__version__ = 0.1
__date__ = '2014-03-26'
__updated__ = '2014-03-26'

TYPE_TO_GALAXY_TYPE = {int: 'integer', float: 'float', str: 'text', bool: 'boolean', _InFile: 'data', 
                       _OutFile: 'data', _Choices: 'select'}
COMMAND_REPLACE_PARAMS = {'threads': '\${GALAXY_SLOTS:-24} ', "in_type": "${param_in.ext}"}
SUPPORTED_FILE_TYPES = ["mzXML","mzML","mgf","featureXML","consensusXML","idXML","pepXML", "txt", "csv"]
FILE_TYPES_TO_GALAXY_DATA_TYPES = {'csv': 'tabular'}

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
    # first, generate a model
    is_converting_multiple_ctds = len(input_files) > 1
    parsed_models = []
    try:
        for input_file in input_files:
            print("Parsing CTD from [%s]" % input_file)
            model = CTDModel(from_file=input_file)
        
            doc = Document()
            tool = create_tool(doc, model)
            doc.appendChild(tool)
            create_description(doc, tool, model)
            create_macros(doc, tool, model)
            create_command(doc, tool, model, **kwargs)
            #create_configfiles(doc, tool, model, kwargs["blacklisted_parameters"])
            create_inputs(doc, tool, model, kwargs["blacklisted_parameters"])
            create_outputs(doc, tool, model, kwargs["blacklisted_parameters"])
            create_help(doc, tool, model)
            
            # finally, serialize the tool
            output_file = output_dest
            # if multiple inputs are being converted, then we need to generate a different output_file for each input
            if is_converting_multiple_ctds:
                #if not output_file.endswith('/'):
                #    output_file += "/"
                #output_file += get_filename(input_file) + ".xml"
                output_file = os.path.join( output_file, get_filename(input_file) + ".xml" )
            doc.writexml(open(output_file, 'w'), indent="    ", addindent="    ", newl='\n', encoding="UTF-8")
            # let's use model to hold the name of the outputfile
            parsed_models.append([model, get_filename(output_file)])
            print("Generated Galaxy wrapper in [%s]\n" % output_file)

            macro_file = os.path.join( os.path.dirname( output_file ), 'macros.xml' )
            if not os.path.exists( macro_file ):
                doc = Document()
                macro_node = doc.createElement("macros")
                doc.appendChild( macro_node )
                create_requirements_macro(doc, macro_node, kwargs["package_requirements"])
                create_exit_codes_macro(doc, macro_node, kwargs["exit_codes"])
                create_reference_macro(doc, macro_node)
                create_advanced_selector_macro( doc, macro_node )
                doc.writexml(open(macro_file, 'w+'), indent="    ", addindent="    ", newl='\n', encoding="UTF-8")

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
    doc = Document()
    toolbox_node = doc.createElement("toolbox")
    
    if galaxy_tool_path is not None and not galaxy_tool_path.strip().endswith("/"):
        galaxy_tool_path = galaxy_tool_path.strip() + "/"
    if galaxy_tool_path is None:
        galaxy_tool_path = ""
    
    for category, filenames in categories_to_tools.iteritems():
        section_node = doc.createElement("section")
        section_node.setAttribute("id", "section-id-" + "".join(category.split()))
        section_node.setAttribute("name", category)
    
        for filename in filenames:
            tool_node = doc.createElement("tool")
            tool_node.setAttribute("file", galaxy_tool_path + filename)
            toolbox_node.appendChild(section_node)
            section_node.appendChild(tool_node)
        toolbox_node.appendChild(section_node)

    doc.appendChild(toolbox_node)
    doc.writexml(open(tool_conf_dest, 'w'), indent="    ", addindent="    ", newl='\n', encoding="UTF-8")
    print("Generated Galaxy tool_conf.xml in [%s]\n" % tool_conf_dest)
    
# taken from
# http://stackoverflow.com/questions/8384737/python-extract-file-name-from-path-no-matter-what-the-os-path-format
def get_filename(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def create_tool(doc, model):
    tool = doc.createElement("tool")
    # use the same name of the tool... maybe a future version would contain a way to add a specific ID?
    tool.setAttribute("id", model.name)
    tool.setAttribute("version", model.version)
    tool.setAttribute("name", model.name)
    return tool

def create_description(doc, tool, model):
    if "description" in model.opt_attribs.keys() and model.opt_attribs["description"] is not None:
        description_node = doc.createElement("description")
        description = doc.createTextNode(model.opt_attribs["description"])
        description_node.appendChild(description)
        tool.appendChild(description_node)

def get_param_name( param ):
    if type(param.parent) == ParameterGroup and param.parent.name != '1':
        return get_param_name(param.parent) + ":" + param.name
    else:
        return param.name

def create_command(doc, tool, model, **kwargs):
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
            # if whitespace_validation has been set, we need to generate, for each parameter:
            # #if str( $t ).split() != '':
            # -t "$t"
            # #end if
            # TODO only useful for text fields, integers or floats
            # not useful for choices, input fields ...

            if whitespace_validation:
                command += "\n#if str($%(param_name)s).strip() != '':\n    "  % {"param_name": galaxy_parameter_name}
            # for boolean types, we only need the placeholder
            if param.type is not bool:
                # add the parameter name
                command += '-%s ' %  ( param_name )
            # we need to add the placeholder
            actual_parameter = "${%s}" % galaxy_parameter_name
            if quote_parameters:
                actual_parameter = '"%s"' % actual_parameter
            command += actual_parameter + '\n'
            if whitespace_validation:
                command += "#end if\n"

        if param.advanced:
            advanced_command += "    %s" % command
        else:
            final_command += command

    if advanced_command:
        final_command += "%s%s%s\n" % (advanced_command_start, advanced_command, advanced_command_end)

    command_node = doc.createElement("command")
    #command_text_node = doc.createCDATASection(command.strip())
    command_text_node = doc.createTextNode(final_command)
    command_node.appendChild(command_text_node)
    tool.appendChild(command_node)

def create_macros(doc, tool, model):
    """
        <macros>
            <token name="@EXECUTABLE@">IDFilter</token>
            <import>macros.xml</import>
        </macros>
        <expand macro="stdio" />
        <expand macro="requirements" />
        <expand macro="command" /> -> was used with configfiles
    """
    macros_node = doc.createElement( "macros" )
    token_node = doc.createElement( "token" )
    token_node.setAttribute( "name", "@EXECUTABLE@" )
    token_node.appendChild( doc.createTextNode( get_tool_executable_path(model) ) )
    macros_node.appendChild( token_node )
    import_node = doc.createElement( "import" )
    import_node.appendChild( doc.createTextNode( "macros.xml" ) )
    macros_node.appendChild( import_node )
    tool.appendChild( macros_node )
    expand_node = doc.createElement( "expand" )
    expand_node.setAttribute( "macro", "stdio" )
    tool.appendChild( expand_node )
    expand_node = doc.createElement( "expand" )
    expand_node.setAttribute( "macro", "requirements" )
    tool.appendChild( expand_node )
    #expand_node = doc.createElement( "expand" )
    #expand_node.setAttribute( "macro", "command" )
    #tool.appendChild( expand_node )

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
def create_configfiles(doc, tool, model, blacklisted_parameters):
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
    configfiles_node = doc.createElement("configfiles")
    configfile_node = doc.createElement("configfile")
    configfile_text_node = doc.createTextNode( cf )
    configfile_node.appendChild( configfile_text_node )
    configfiles_node.appendChild( configfile_node )
    tool.appendChild( configfiles_node )

def create_inputs(doc, tool, model, blacklisted_parameters):
    inputs_node = doc.createElement("inputs")

    """
        <expand macro="advanced_options">
        </expand>
    """
    expand_advanced_node = doc.createElement('expand')
    expand_advanced_node.setAttribute('macro', 'advanced_options')

    collect_inputs = list()

    # treat all non output-file parameters as inputs
    for param in extract_parameters(model):
        if param.name in blacklisted_parameters:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is not _OutFile:
            if not param.advanced:
                if param.type is _InFile:
                    inputs_node.appendChild( create_param_node(doc, param) )
                else:
                    collect_inputs.append( create_param_node(doc, param) )
            else:
                expand_advanced_node.appendChild(create_param_node(doc, param))

    for inputs in collect_inputs:
        inputs_node.appendChild( inputs )

    if expand_advanced_node.hasChildNodes():
        inputs_node.appendChild(expand_advanced_node)
    tool.appendChild(inputs_node)


def get_supported_file_types( file_types ):
    print file_types
    return [ FILE_TYPES_TO_GALAXY_DATA_TYPES.get(file_type, file_type) for file_type in file_types if file_type in SUPPORTED_FILE_TYPES]


def create_param_node(doc, param):
    param_node = doc.createElement("param")
    param_node.setAttribute("name", get_galaxy_parameter_name(param.name))
    label = ""
    if param.description is not None:
        label = param.description
    else:
        label = "%s parameter" % param.name
    param_node.setAttribute("label", label)
    param_node.setAttribute("help", "(-%s)" % param.name)
    
    param_type = TYPE_TO_GALAXY_TYPE[param.type]
    if param_type is None:
        raise ModelError("Unrecognized parameter type '%(type)' for parameter '%(name)'" % {"type":param.type, "name":param.name})
    # galaxy handles ITEMLIST from CTDs as strings
    if param.is_list:
        param_type = "text"
        
    if is_boolean_parameter(param):
        param_type = "boolean"
        
    param_node.setAttribute("type", param_type)

    if param.type is _InFile:
        # assume it's just data unless restrictions are provided
        param_format = "data"
        if param.restrictions is not None:
            # join all supported_formats for the file... this MUST be a _FileFormat
            if type(param.restrictions) is _FileFormat: 
                param_format = ','.join( get_supported_file_types(param.restrictions.formats) )
            else:
                raise InvalidModelException("Expected 'file type' restrictions for input file [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)}) 
        param_node.setAttribute("format", param_format)
        param_type = "data"

    # check for parameters with restricted values (which will correspond to a "select" in galaxy)
    if param.restrictions is not None:
        # it could be either _Choices or _NumericRange, with special case for boolean types
        if param_type == "boolean":
            create_boolean_parameter(param, param_node)
        elif type(param.restrictions) is _Choices:
            # create as many <option> elements as restriction values
            for choice in param.restrictions.choices:
                option_node = doc.createElement("option")
                option_node.setAttribute("value", str(choice))
                option_label = doc.createTextNode(str(choice))
                option_node.appendChild(option_label)
                param_node.appendChild(option_node)
        elif type(param.restrictions) is _NumericRange:
            if param.type is not int and param.type is not float:
                raise InvalidModelException("Expected either 'int' or 'float' in the numeric range restriction for parameter [%(name)s], but instead got [%(type)s]" % {"name":param.name, "type":type(param.restrictions)})
            # extract the min and max values and add them as attributes
            # validate the provided min and max values
            if param.restrictions.n_min is not None:
                param_node.setAttribute("min", str(param.restrictions.n_min))
            if param.restrictions.n_max is not None:
                param_node.setAttribute("max", str(param.restrictions.n_max))
        elif type(param.restrictions) is _FileFormat:
            param_node.setAttribute("format", ",".join( get_supported_file_types(param.restrictions.formats) ))
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for parameter [%(name)s]" % {"type":type(param.restrictions), "name":param.name}) 

        param_node.setAttribute("optional", str(not param.required))

    if param_type == "text":
        # add size attribute... this is the length of a textbox field in Galaxy (it could also be 15x2, for instance)
        param_node.setAttribute("size", "20")

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
            param_node.setAttribute("value", str(default_value))
    
    return param_node

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

def get_lowercase_list(some_list):
    lowercase_list = map(str, some_list)
    lowercase_list = map(string.lower, lowercase_list)
    lowercase_list = map(strip, lowercase_list)
    return lowercase_list

# creates a galaxy boolean parameter type
# this method assumes that param has restrictions, and that only two restictions are present (either yes/no or true/false)
def create_boolean_parameter(param, param_node):
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
        truevalue = "true"
        falsevalue = "false"
    param_node.setAttribute("truevalue", truevalue)
    param_node.setAttribute("falsevalue", falsevalue)
    
    # set the checked attribute    
    if param.default is not None:
        checked_value = "false"
        default = strip(string.lower(param.default))
        if default == "yes" or default == "true":
            checked_value = "true"
        param_node.setAttribute("checked", checked_value)

def create_outputs(doc, tool, model, blacklisted_parameters):
    outputs_node = doc.createElement("outputs")
    for param in extract_parameters(model):
        if param.name in blacklisted_parameters:
            # let's not use an extra level of indentation and use NOP
            continue
        if param.type is _OutFile:
            outputs_node.appendChild(create_data_node(doc, param))
    tool.appendChild(outputs_node) 

def create_data_node(doc, param):
    data_node = doc.createElement("data")
    data_node.setAttribute("name", get_galaxy_parameter_name(param.name))
    data_format = "data"
    if param.restrictions is not None:
        if type(param.restrictions) is _FileFormat:
            # set the first data output node to the first fileformat
            formats = get_supported_file_types( param.restrictions.formats )
            data_format = formats.pop()
            # if there are more than one output file formats from which the
            # user can choose, create "change_format" nodes for all but the first
            if formats:
                #param_out_type is hardcoded for the moment
                data_node.appendChild( create_change_format_node(doc, formats, 'param_out_type') )
        else:
            raise InvalidModelException("Unrecognized restriction type [%(type)s] for output [%(name)s]" % {"type":type(param.restrictions), "name":param.name})
    data_node.setAttribute("format", data_format)
    
    if param.description is not None:
        data_node.setAttribute("label", param.description)
        
    return data_node

def create_filter_node(doc, data_format):
    """
        <filter>'bam' in outputs</filter>
    """
    filter_node = doc.createElement("filter")
    # param_out_type is hardcoded for the moment
    option_label = doc.createTextNode("'%s' in param_out_type" % (data_format))
    filter_node.appendChild(option_label)
    return filter_node

def create_change_format_node(doc, data_formats, input_ref):
    """
        <change_format>
            <when input="secondary_structure" value="true" format="text"/>
        </change_format>
    """
    change_format_node = doc.createElement("change_format")
    for data_format in data_formats:
        when_node = doc.createElement("when")
        when_node.setAttribute('input', input_ref)
        when_node.setAttribute('value', data_format)
        when_node.setAttribute('format', data_format)
        change_format_node.appendChild( when_node )
    return change_format_node


def create_requirements_macro(doc, macro, package_requirements):
    # create xml node to define a macro: <xml name="requirements">
    macro_xml_node = doc.createElement("xml")
    macro_xml_node.setAttribute("name", "requirements")
    macro.appendChild( macro_xml_node )

    if len(package_requirements) > 0:
        requirements_node = doc.createElement("requirements")
        for package_requirement in package_requirements:
            requirement_node = doc.createElement("requirement")
            requirement_node.setAttribute("type", "package")
            requirement_text_node = doc.createTextNode(package_requirement)
            requirement_node.appendChild(requirement_text_node)
            requirements_node.appendChild(requirement_node)
        macro_xml_node.appendChild(requirements_node)
    else:
        # Add a template
        """
        <requirements>
            <requirement type="binary">@EXECUTABLE@</requirement>
            <requirement type="package" version="1.1.1">TODO</requirement>
        </requirements>
        """
        requirements_node = doc.createElement("requirements")

        requirement_node = doc.createElement("requirement")
        requirement_node.setAttribute("type", "binary")
        requirement_text_node = doc.createTextNode('@EXECUTABLE@')
        requirement_node.appendChild(requirement_text_node)
        requirements_node.appendChild(requirement_node)

        requirement_node = doc.createElement("requirement")
        requirement_node.setAttribute("type", "package")
        requirement_node.setAttribute("version", "1.1.1")
        requirement_text_node = doc.createTextNode('TODO')
        requirement_node.appendChild(requirement_text_node)
        requirements_node.appendChild(requirement_node)

        macro_xml_node.appendChild(requirements_node)

    """
        Add a version_command to the macro file.
        <version_command>@EXECUTABLE@ -version</version_command>
    """
    #version_command = doc.createElement("version_command")
    #version_command_text_node = doc.createTextNode('@EXECUTABLE@ -version')
    #version_command.appendChild(version_command_text_node)
    #macro_xml_node.appendChild(version_command)



def create_reference_macro(doc, macro):
    # create xml node to define a macro: <token name="@REFERENCES@">
    macro_xml_node = doc.createElement("token")
    macro_xml_node.setAttribute("name", "@REFERENCES@")
    references_text_node = doc.createTextNode("""

-------

**References**

If you use this Galaxy tool in work leading to a scientific publication please
cite the following papers:

""")
    macro_xml_node.appendChild( references_text_node )
    macro.appendChild( macro_xml_node )


def create_exit_codes_macro(doc, macro, exit_codes):
    # create xml node to define a macro: <xml name="stdio">
    macro_xml_node = doc.createElement("xml")
    macro_xml_node.setAttribute("name", "stdio")
    macro.appendChild( macro_xml_node )

    if len(exit_codes) > 0:
        stdio_node = doc.createElement("stdio")
        for exit_code in exit_codes:
            exit_code_node = doc.createElement("exit_code")
            exit_code_node.setAttribute("range", exit_code.range)
            exit_code_node.setAttribute("level", exit_code.level)
            # description is optional
            if exit_code.description is not None:
                exit_code_node.setAttribute("description", exit_code.description)
            stdio_node.appendChild(exit_code_node)
        macro_xml_node.appendChild(stdio_node)
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
        stdio_node = doc.createElement("stdio")
        exit_code_node = doc.createElement("exit_code")
        exit_code_node.setAttribute("range", "1:")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = doc.createElement("exit_code")
        exit_code_node.setAttribute("range", ":-1")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = doc.createElement("regex")
        exit_code_node.setAttribute("match", "Error:")
        stdio_node.appendChild(exit_code_node)
        exit_code_node = doc.createElement("regex")
        exit_code_node.setAttribute("match", "Exception:")
        stdio_node.appendChild(exit_code_node)

        macro_xml_node.appendChild(stdio_node)

def create_advanced_selector_macro(doc, macro):
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
    macro_xml_node = doc.createElement("xml")
    macro_xml_node.setAttribute("name", "advanced_options")
    macro.appendChild( macro_xml_node )

    conditional_node = doc.createElement("conditional")
    conditional_node.setAttribute('name', 'adv_opts')
    macro_xml_node.appendChild(conditional_node)

    param_node = doc.createElement("param")
    param_node.setAttribute('name', 'adv_opts_selector')
    param_node.setAttribute('type', 'select')
    param_node.setAttribute('label', 'Advanced Options')
    conditional_node.appendChild(param_node)

    option_node = doc.createElement("option")
    option_node.setAttribute('value', 'basic')
    option_node.setAttribute('selected', 'True')
    option_node.appendChild( doc.createTextNode('Hide Advanced Options') )
    param_node.appendChild(option_node)

    option_node = doc.createElement("option")
    option_node.setAttribute('value', 'advanced')
    option_node.appendChild( doc.createTextNode('Show Advanced Options') )
    param_node.appendChild(option_node)

    when_node = doc.createElement("when")
    param_node.setAttribute('value', 'basic')
    conditional_node.appendChild(when_node)

    when_node = doc.createElement("when")
    when_node.setAttribute('value', 'advanced')
    yield_node = doc.createElement('yield')
    when_node.appendChild( yield_node )
    conditional_node.appendChild(when_node)

    macro_xml_node.appendChild(conditional_node)


def create_help(doc, tool, model):
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
    help_node = doc.createElement("help")
    # TODO: do we need CDATA Section here?
    help_node.appendChild(doc.createTextNode(help_text))
    tool.appendChild(help_node)
    
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
