# Conversion of CTD Files to Galaxy ToolConfigs
## Generating a `tool_conf.xml` File 
* Purpose: Galaxy uses a file `tool_conf.xml` in which other tools can be included. `CTDConverter` can also generate this file. Categories will be extracted from the provided input CTDs and for each category, a different `<section>` will be generated. Any input CTD lacking a category will be sorted under the provided default category.
* Short/long version: `-t` / `--tool-conf-destination`
* Required: no.
* Taken values: The destination of the file.

    $ python convert.py galaxy -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs -t /data/generated-galaxy-stubs/tool_conf.xml

## Adding Parameters to the Command-line
* Purpose: Galaxy *ToolConfig* files include a `<command>` element in which the command line to invoke the tool can be given. Sometimes it is needed to invoke your tools in a certain way (i.e., passing certain parameters). For instance, some tools offer the possibility to be invoked in a verbose or quiet way or even to be invoked in a headless way (i.e., without GUI).
* Short/long version: `-a` / `--add-to-command-line`
* Required: no.
* Taken values: The command(s) to be added to the command line.

Example:

    $ python convert.py galaxy ... -a "--quiet --no-gui"

Will generate the following `<command>` element in the generated Galaxy *ToolConfig*:

    <command>TOOL_NAME --quiet --no-gui ...</command>
    
## Providing a default Category
* Purpose: Input CTDs that lack a category will be sorted under the value given to this parameter. If this parameter is not provided, then the category `DEFAULT` will be used.
* Short/long version: `-c` / `--default-category`
* Required: no.
* Taken values: The value for the default category to use for input CTDs lacking a category.

Example:

Suppose there is a folder containing several CTD files. Some of those CTDs don't have the optional attribute `category` and the rest belong to the `Data Processing` category. The following invocation:

    $ python convert.py galaxy ... -c Other
    
will generate, for each of the categories, a different section. Additionally, CTDs lacking a category will be sorted under the given category, `Other`, as shown:

    <section id="category-id-dataprocessing" name="Data Processing">
        <tool file="some_path/tool_one.xml" />
        <tool file="some_path/tool_two.xml" />
        ...
    </section>
    
    <section id="category-id-other" name="Other">
        <tool file="some_path/tool_three.xml" />
        <tool file="some_path/tool_four.xml" />
        ...
    </section>

## Providing a Path for the Location of the *ToolConfig* Files
* Purpose: The `tool_conf.xml` file contains references to files which in turn contain Galaxy *ToolConfig* files. Using this parameter, you can provide information about the location of your wrappers on your Galaxy instance.
* Short/long version: `-g` / `--galaxy-tool-path`
* Required: no.
* Taken values: The path relative to your `$GALAXY_ROOT/tools` folder on which your tools are located.

Example:

    $ python convert.py galaxy ... -g my_tools_folder
    
Will generate `<tool>` elements in the generated `tool_conf.xml` as follows:

    <tool file="my_tools_folder/some_tool.xml" />
    
In this example, `tool_conf.xml` refers to a file located on `$GALAXY_ROOT/tools/my_tools_folder/some_tool.xml`.

## Including additional Macros Files
* Purpose: Include external macros files.
* Short/long version: `-m` / `--macros`
* Required: no.
* Default: `macros.xml`
* Taken values: List of paths of macros files to include.

*ToolConfig* supports elaborate sections such as `<stdio>`, `<requirements>`, etc., that are identical across tools of the same suite. Macros files assist in the task of including external xml sections into *ToolConfig* files. For more information about the syntax of macros files, see: https://wiki.galaxyproject.org/Admin/Tools/ToolConfigSyntax#Reusing_Repeated_Configuration_Elements

There are some macros that are required, namely `stdio`, `requirements` and `advanced_options`. A template macro file is included in [macros.xml]. It can be edited to suit your needs and you could add extra macros or leave it as it is and include additional files. Every macro found in the provided files will be expanded. 

Please note that the used macros files **must** be copied to your Galaxy installation on the same location in which you place the generated *ToolConfig* files, otherwise Galaxy will not be able to parse the generated *ToolConfig* files!

## Generating a `datatypes_conf.xml` File
* Purpose: Specify the destination of a generated `datatypes_conf.xml` file.
* Short/long version: `-d` / `--datatypes-destination`
* Required: no.
* Taken values: The path in which `datatypes_conf.xml` will be generated.

It is likely that your tools use file formats or mimetypes that have not been registered in Galaxy. The generator allows you to specify a path in which an automatically generated `datatypes_conf.xml` file will be created. Consult the next section to get information about how to register file formats and mimetypes.

## Providing Galaxy File Formats
* Purpose: Register new file formats and mimetypes.
* Short/long version: `-f` / `--formats-file`
* Required: no.
* Taken values: The path of a file describing formats.

Galaxy supports the concept of file format in order to connect compatible ports, that is, input ports of a certain data format will be able to receive data from a port from the same format. This converter allows you to provide a personalized file in which you can relate the CTD data formats with supported Galaxy data formats. The format file is a simple text file, each line containing several columns separated by whitespace. The content of each column is as follows:

* 1st column: file extension, this column is required.
* 2nd column: data type, as listed in Galaxy, this column is optional.
* 3rd column: full-named Galaxy data type, as it will appear on datatypes_conf.xml; this column is required if the second column is included.
* 4th column: mimetype, this column is optional.

The following is an example of a valid "file formats" file:

    # CTD type    # Galaxy type      # Long Galaxy data type            # Mimetype
    csv           tabular            galaxy.datatypes.data:Text
    fasta
    ini           txt                galaxy.datatypes.data:Text
    txt
    idxml         txt                galaxy.datatypes.xml:GenericXml    application/xml
    options       txt                galaxy.datatypes.data:Text
    grid          grid               galaxy.datatypes.data:Grid

Note that each line consists of either one, three or four columns. In the case of data types already registered in Galaxy (such as `fasta` and `txt` in the above example), only the first column is needed. In the case of data types that haven't been yet registered in Galaxy, the first three columns are needed (mimetype is optional).

For information about Galaxy data types and subclasses, consult the following page: https://wiki.galaxyproject.org/Admin/Datatypes/Adding%20Datatypes

## Remarks about some of the *OpenMS* Tools
* Most of the tools can be generated automatically. However, some of the tools need some extra work (for now).
* The following adapters need to be changed, such that you provide the path to the executable:
    * FidoAdapter (add `-exe fido` in the command tag, delete the `$param_exe` in the command tag, delete the parameter from the input list).
    * MSGFPlusAdapter (add `-executable msgfplus.jar` in the command tag, delete the `$param_executable` in the command tag, delete the parameter from the input list).
    * MyriMatchAdapter (add `-myrimatch_executable myrimatch` in the command tag, delete the `$param_myrimatch_executable` in the command tag, delete the parameter from the input list).
    * OMSSAAdapter (add `-omssa_executable omssa` in the command tag, delete the `$param_omssa_executable` in the command tag, delete the parameter from the input list).
    * PepNovoAdapter (add `-pepnovo_executable pepnovo` in the command tag, delete the `$param_pepnovo_executable` in the command tag, delete the parameter from the input list).
    * XTandemAdapter (add `-xtandem_executable xtandem` in the command tag, delete the $param_xtandem_executable in the command tag, delete the parameter from the input list).
    * To avoid the deletion in the inputs you can also add these parameters to the blacklist
    
    $ python convert.py galaxy -b exe executable myrimatch_excutable omssa_executable pepnovo_executable xtandem_executable

* The following tools have multiple outputs (number of inputs = number of outputs) which is not yet supported in Galaxy-stable:
    * SeedListGenerator
    * SpecLibSearcher
    * MapAlignerIdentification
    * MapAlignerPoseClustering
    * MapAlignerSpectrum
    * MapAlignerRTTransformer

[CTDopts]: https://github.com/genericworkflownodes/CTDopts
[macros.xml]: https://github.com/WorkflowConversion/CTDConverter/blob/master/galaxy/macros.xml
[CTDSchema]: https://github.com/genericworkflownodes/CTDSchema