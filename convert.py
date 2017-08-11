import os
import sys
import traceback
import common.utils as utils

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from common.exceptions import ApplicationException, ModelError


__all__ = []
__version__ = 2.0
__date__ = '2014-09-17'
__updated__ = '2017-08-09'

program_version = "v%s" % __version__
program_build_date = str(__updated__)
program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
program_short_description = "CTDConverter - A project from the WorkflowConversion family " \
                                "(https://github.com/WorkflowConversion/CTDConverter)"
program_usage = '''
USAGE:

  $ python convert.py [FORMAT] [ARGUMENTS ...]

FORMAT can be either one of the supported output formats: cwl, galaxy.

There is one converter for each supported FORMAT, each taking a different set of arguments. Please consult the detailed
documentation for each of the converters. Nevertheless, all converters have the following common parameters/options:


I - Parsing a single CTD file and convert it:

  $ python convert.py [FORMAT] -i [INPUT_FILE] -o [OUTPUT_FILE]


II - Parsing several CTD files, output converted wrappers in a given folder:

  $ python converter.py [FORMAT] -i [INPUT_FILES] -o [OUTPUT_DIRECTORY]


III - Hardcoding parameters

  It is possible to hardcode parameters. This makes sense if you want to set a tool in 'quiet' mode or if your tools
  support multi-threading and accept the number of threads via a parameter, without giving end users the chance to
  change the values for these parameters.

  In order to generate hardcoded parameters, you need to provide a simple file. Each line of this file contains
  two or three columns separated by whitespace. Any line starting with a '#' will be ignored. The first column contains
  the name of the parameter, the second column contains the value that will always be set for this parameter. Only the
  first two columns are mandatory.

  If the parameter is to be hardcoded only for a set of tools, then a third column can be added. This column contains
  a comma-separated list of tool names for which the parameter will be hardcoded. If a third column is not present,
  then all processed tools containing the given parameter will get a hardcoded value for it.

  The following is an example of a valid file:

  ##################################### HARDCODED PARAMETERS example #####################################
  # Every line starting with a # will be handled as a comment and will not be parsed.
  # The first column is the name of the parameter and the second column is the value that will be used.

  # Parameter name            # Value                     # Tool(s)
  threads                     8
  mode                        quiet
  xtandem_executable          xtandem                     XTandemAdapter
  verbosity                   high                        Foo, Bar

  #########################################################################################################

  Using the above file will produce a command-line similar to:

    [TOOL] ... -threads 8 -mode quiet ...

  for all tools. For XTandemAdapter, however, the command-line will look like:

    XtandemAdapter ... -threads 8 -mode quiet -xtandem_executable xtandem ...

  And for tools Foo and Bar, the command-line will be similar to:

    Foo -threads 8 -mode quiet -verbosity high ...


  IV - Engine-specific parameters

    i - Galaxy

      a. Providing file formats, mimetypes

        Galaxy supports the concept of file format in order to connect compatible ports, that is, input ports of a
        certain data format will be able to receive data from a port from the same format. This converter allows you
        to provide a personalized file in which you can relate the CTD data formats with supported Galaxy data formats.
        The layout of this file consists of lines, each of either one or four columns separated by any amount of
        whitespace. The content of each column is as follows:

          * 1st column: file extension
          * 2nd column: data type, as listed in Galaxy
          * 3rd column: full-named Galaxy data type, as it will appear on datatypes_conf.xml
          * 4th column: mimetype (optional)

        The following is an example of a valid "file formats" file:

        ########################################## FILE FORMATS example ##########################################
        # Every line starting with a # will be handled as a comment and will not be parsed.
        # The first column is the file format as given in the CTD and second column is the Galaxy data format. The
        # second, third, fourth and fifth columns can be left empty if the data type has already been registered
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
        registered in Galaxy (such as fasta and txt in the above example), only the first column is needed. In the
        case of data types that haven't been yet registered in Galaxy, the first three columns are needed
        (mimetype is optional).

        For information about Galaxy data types and subclasses, see the following page:
        https://wiki.galaxyproject.org/Admin/Datatypes/Adding%20Datatypes


      b. Finer control over which tools will be converted

        Sometimes only a subset of CTDs needs to be converted. It is possible to either explicitly specify which tools
        will be converted or which tools will not be converted.

        The value of the -s/--skip-tools parameter is a file in which each line will be interpreted as the name of a
        tool that will not be converted. Conversely, the value of the -r/--required-tools is a file in which each line
        will be interpreted as a tool that is required. Only one of these parameters can be specified at a given time.

        The format of both files is exactly the same. As stated before, each line will be interpreted as the name of a
        tool. Any line starting with a '#' will be ignored.


    ii - CWL

      There are, for now, no CWL-specific parameters or options.

'''

program_license = '''%(short_description)s

Copyright 2017, WorklfowConversion

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


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    # check that we have, at least, one argument provided
    # at this point we cannot parse the arguments, because each converter takes different arguments, meaning each
    # converter will register its own parameters after we've registered the basic ones... we have to do it old school
    if len(argv) < 2:
        utils.error('Not enough arguments provided')
        print('\nUsage: $ python convert.py [TARGET] [ARGUMENTS]\n\n' +
          'Where:\n' +
          '  target: one of \'cwl\' or \'galaxy\'\n\n' +
          'Run again using the -h/--help option to print more detailed help.\n')
        return 1

    # TODO: at some point this should look like real software engineering and use a map containing converter instances
    # whose keys would be the name of the converter (e.g., cwl, galaxy), but for the time being, only two formats
    # are supported
    target = str.lower(argv[1])
    if target == 'cwl':
        from cwl import converter
    elif target == 'galaxy':
        from galaxy import converter
    elif target == '-h' or target == '--help' or target == '--h' or target == 'help':
        print(program_license)
        return 0
    else:
        utils.error('Unrecognized target engine. Supported targets are \'cwl\' and \'galaxy\'.')
        return 1

    try:
        # Setup argument parser
        parser = ArgumentParser(prog="CTDConverter", description=program_license,
                                formatter_class=RawDescriptionHelpFormatter, add_help=True)
        utils.add_common_parameters(parser, program_version_message, program_build_date)

        # add tool-specific arguments
        converter.add_specific_args(parser)

        # parse arguments and perform some basic, common validation
        args = parser.parse_args()
        validate_and_prepare_common_arguments(args)

        # parse the input CTD files into CTDModels
        parsed_ctds = utils.parse_input_ctds(args.xsd_location, args.input_files, args.output_destination,
                                             converter.get_preferred_file_extension())

        # let the converter do its own thing
        return converter.convert_models(args, parsed_ctds)

    except KeyboardInterrupt:
        # handle keyboard interrupt
        return 0

    except ApplicationException, e:
        utils.error("CTDConverter could not complete the requested operation.", 0)
        utils.error("Reason: " + e.msg, 0)
        return 1

    except ModelError, e:
        utils.error("There seems to be a problem with one of your input CTDs.", 0)
        utils.error("Reason: " + e.msg, 0)
        return 1

    except Exception, e:
        traceback.print_exc()
        return 2

    return 0


def validate_and_prepare_common_arguments(args):
    # flatten lists of lists to a list containing elements
    lists_to_flatten = ["input_files", "blacklisted_parameters"]
    for list_to_flatten in lists_to_flatten:
        utils.flatten_list_of_lists(args, list_to_flatten)

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
    input_arguments_to_check = ["xsd_location", "input_files", "hardcoded_parameters"]
    for argument_name in input_arguments_to_check:
        utils.validate_argument_is_valid_path(args, argument_name)


if __name__ == "__main__":
    sys.exit(main())