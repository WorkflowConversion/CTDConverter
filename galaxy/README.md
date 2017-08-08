# Conversion of CTD Files to Galaxy ToolConfigs

## How to use: most common Tasks

The Galaxy ToolConfig generator takes several parameters and a varying number of inputs and outputs. The following sub-sections show how to perform the most common operations.

Running the generator with the `-h/--help` parameter will print extended information about each of the parameters.

### Macros

Galaxy supports the use of macros via a `macros.xml` file (we provide a sample macros file in [macros.xml]). Instead of repeating sections, macros can be used and expanded. If you want fine control over the macros, you can use the `-m` / `--macros` parameter to provide your own macros file.

Please note that the used macros file **must** be copied to your Galaxy installation on the same location in which you place the generated *ToolConfig* files, otherwise Galaxy will not be able to parse the generated *ToolConfig* files!

### One input, one Output

In its simplest form, the converter takes an input CTD file and generates an output Galaxy *ToolConfig* file. The following usage of `generator.py`:

    $ python generator.py -i /data/sample_input.ctd -o /data/sample_output.xml

will parse `/data/sample_input.ctd` and generate a Galaxy tool wrapper under `/data/sample_output.xml`. The generated file can be added to your Galaxy instance like any other tool.

### Converting several CTDs at once

When converting several CTDs, the expected value for the `-o`/`--output` parameter is a folder. For example:

    $ python generator.py -i /data/ctds/one.ctd /data/ctds/two.ctd -o /data/generated-galaxy-stubs
    
Will convert `/data/ctds/one.ctd` into `/data/generated-galaxy-stubs/one.xml` and `/data/ctds/two.ctd` into `/data/generated-galaxy-stubs/two.xml`.
    
You can use wildcard expansion, as supported by most modern operating systems:
	
	$ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs

### Generating a tool_conf.xml File 

The generator supports generation of a `tool_conf.xml` file which you can later use in your local Galaxy installation. The parameter `-t`/`--tool-conf-destination` contains the path of a file in which a `tool_conf.xml` file will be generated.

    $ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs -t /data/generated-galaxy-stubs/tool_conf.xml


## How to use: Parameters in Detail

### A Word about Parameters taking Lists of Values

All parameters have a short and a long option and some parameters take list of values. Using either the long or the short option of the parameter will produce the same output. The following examples show how to pass values using the `-f` / `--foo` parameter:

The following uses of the parameter will pass the list of values containing `bar`, `blah` and `blu`:

    -f bar blah blu
    --foo bar blah blu
    -f bar -f blah -f blu
    --foo bar --foo blah --foo blu
    -f bar --foo blah blu
    
The following uses of the parameter will pass a single value `bar`:

    -f bar
    --foo bar
    
### Schema Validation

* Purpose: Provide validation of input CTDs against a schema file (i.e, a XSD file).
* Short/long version: `v` / `--validation-schema`
* Required: no.
* Taken values: location of the schema file (e.g., CTD.xsd).

CTDs can be validated against a schema. The master version of the schema can be found under [CTDSchema].

If a schema is provided, all input CTDs will be validated against it.
    
### Input File(s)

* Purpose: Provide input CTD file(s) to convert.
* Short/long version: `-i` / `--input`
* Required: yes.
* Taken values: a list of input CTD files.

Example:

Any of the following invocations will convert `/data/input_one.ctd` and `/data/input_two.ctd`:

    $ python generator.py -i /data/input_one.ctd -i /data/input_two.ctd -o /data/generated
    $ python generator.py -i /data/input_one.ctd /data/input_two.ctd -o /data/generated
    $ python generator.py --input /data/input_one.ctd /data/input_two.ctd -o /data/generated
    $ python generator.py --input /data/input_one.ctd --input /data/input_two.ctd -o /data/generated 
    
The following invocation will convert `/data/input.ctd` into `/data/output.xml`:

    $ python generator.py -i /data/input.ctd -o /data/output.xml -m sample_files/macros.xml
    
Of course, you can also use wildcards, which will be automatically expanded by any modern operating system. This is extremely useful if you want to convert several files at a time. Imagine that the folder `/data/ctds` contains three files, `input_one.ctd`, `input_two.ctd` and `input_three.ctd`. The following two invocations will produce the same output in the `/data/galaxy`:

    $ python generator.py -i /data/input_one.ctd /data/input_two.ctd /data/input_three.ctd -o /data/galaxy
    $ python generator.py -i /data/*.ctd -o /data/galaxy

### Finer Control over the Tools to be converted

Sometimes only a set of CTDs in a folder need to be converted. The parameter `-r`/`--required-tools` takes the path a file containing the names of tools that will be converted.

    $ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs -r required_tools.txt
    
On the other hand, if you want the generator to skip conversion of some CTDs, the parameter `-s`/`--skip-tools` will take the path of a file containing the names of tools that will not be converted.

	$ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs -s skipped_tools.txt
	
The format of these files (`required_tools.txt`, `skipped_tools.txt` in the examples above) is straightforward. Each line contains the name of a tool and any line starting with `#` will be ignored.

### Output Destination

* Purpose: Provide output destination for the generated Galaxy *ToolConfig* files.
* Short/long version: `-o` / `--output-destination`
* Required: yes.
* Taken values: if a single input file is given, then a single output file is expected. If multiple input files are given, then an existent folder, in which all generated Galaxy *ToolConfig* will be written, is expected.

Example:

A single input is given, and the output will be generated into `/data/output.xml`:

    $ python generator.py -i /data/input.ctd -o /data/output.xml
    
Several inputs are given. The output is the already existent folder, `/data/stubs`, and at the end of the operation, the files `/data/stubs/input_one.ctd.xml` and `/data/stubs/input_two.ctd.xml` will be generated:

    $ python generator.py -i /data/ctds/input_one.ctd /data/ctds/input_two.ctd -o /data/stubs


### Adding Parameters to the Command-line

* Purpose: Galaxy *ToolConfig* files include a `<command>` element in which the command line to invoke the tool can be given. Sometimes it is needed to invoke your tools in a certain way (i.e., passing certain parameters). For instance, some tools offer the possibility to be invoked in a verbose or quiet way or even to be invoked in a headless way (i.e., without GUI).
* Short/long version: `-a` / `--add-to-command-line`
* Required: no.
* Taken values: The command(s) to be added to the command line.

Example:

    $ python generator.py ... -a "--quiet --no-gui"

Will generate the following `<command>` element in the generated Galaxy *ToolConfig*:

    <command>TOOL_NAME --quiet --no-gui ...</command>
    

### Blacklisting Parameters

* Purpose: Some parameters present in the CTD are not to be exposed on Galaxy. Think of parameters such as `--help`, `--debug`, that might won't make much sense to be exposed to final users in a workflow management system such as Galaxy.
* Short/long version: `-b` / `--blacklist-parameters`
* Required: no.
* Taken values: A list of parameters to be blacklisted.

Example:

    $ python generator.py ... -b h help quiet
    
Will not process any of the parameters named `h`, `help`, or `quiet` and will not appear in the generated Galaxy *ToolConfig*.

### Generating a tool_conf.xml file

* Purpose: Galaxy uses a file `tool_conf.xml` in which other tools can be included. `generator.py` can also generate this file. Categories will be extracted from the provided input CTDs and for each category, a different `<section>` will be generated. Any input CTD lacking a category will be sorted under the provided default category.
* Short/long version: `-t` / `--tool-conf-destination`
* Required: no.
* Taken values: The destination of the file.

### Providing a default Category

* Purpose: Input CTDs that lack a category will be sorted under the value given to this parameter. If this parameter is not given, then the category `DEFAULT` will be used.
* Short/long version: `-c` / `--default-category`
* Required: no.
* Taken values: The value for the default category to use for input CTDs lacking a category.

Example:

Suppose there is a folder containing several CTD files. Some of those CTDs don't have the optional attribute `category` and the rest belong to the `Data Processing` category. The following invocation:

    $ python generator.py ... -c Other
    
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

### Providing a Path for the Location of the ToolConfig Files

* Purpose: The `tool_conf.xml` file contains references to files which in turn contain Galaxy *ToolConfig* files. Using this parameter, you can provide information about the location of your tools.
* Short/long version: `-g` / `--galaxy-tool-path`
* Required: no.
* Taken values: The path relative to your `$GALAXY_ROOT/tools` folder on which your tools are located.

Example:

    $ python generator.py ... -g my_tools_folder
    
Will generate `<tool>` elements in the generated `tool_conf.xml` as follows:

    <tool file="my_tools_folder/some_tool.xml" />
    
In this example, `tool_conf.xml` refers to a file located on `$GALAXY_ROOT/tools/my_tools_folder/some_tool.xml`.


### Hardcoding Parameters

* Purpose: Fixing the value of a parameter and hide it from the end user.
* Short/long version: `-p` / `--hardcoded-parameters`
* Required: no.
* Taken values: The path of a file containing the mapping between parameter names and hardcoded values to use in the `<command>` section.

It is sometimes required that parameters are hidden from the end user in workflow systems such as Galaxy and that they take a predetermined value. Allowing end users to control parameters similar to `--verbosity`, `--threads`, etc., might create more problems than solving them. For this purpose, the parameter `p`/`--hardcoded-parameters` takes the path of a file that contains up to three columns separated by whitespace that map parameter names to the hardcoded value. The first column contains the name of the parameter and the second one the hardcoded value. The first two columns are mandatory.

If the parameter is to be hardcoded only for certain tools, a third column containing a comma separated list of tool names for which the hardcoding will apply can be added.

Lines starting with `#` will be ignored. The following is an example of a valid file:

    # Parameter name            # Value							# Tool(s)
    threads                     \${GALAXY_SLOTS:-24}
    mode                        quiet
    xtandem_executable          xtandem                     	XTandemAdapter
    verbosity                   high                        	Foo, Bar
    
This will produce a `<command>` section similar to the following one for all tools but `XTandemAdapter`, `Foo` and `Bar`:

    <command>TOOL_NAME -threads \${GALAXY_SLOTS:-24} -mode quiet  ...</command>
    
For `XTandemAdapter`, the `<command>` will be similar to:

    <command>XtandemAdapter ... -threads \${GALAXY_SLOTS:-24} -mode quiet -xtandem_executable xtandem ...</command>

And for tools `Foo` and `Bar`, the `<command>` will be similar to:

    <command>Foo ... ... -threads \${GALAXY_SLOTS:-24} -mode quiet -verbosity high ...</command>


### Including additional Macros Files

* Purpose: Include external macros files.
* Short/long version: `-m` / `--macros`
* Required: no.
* Default: `macros.xml`
* Taken values: List of paths of macros files to include.

*ToolConfig* supports elaborate sections such as `<stdio>`, `<requirements>`, etc., that are identical across tools of the same suite. Macros files assist in the task of including external xml sections into *ToolConfig* files. For more information about the syntax of macros files, see: https://wiki.galaxyproject.org/Admin/Tools/ToolConfigSyntax#Reusing_Repeated_Configuration_Elements

There are some macros that are required, namely `stdio`, `requirements` and `advanced_options`. A template macro file is included in [macros.xml]. It can be edited to suit your needs and you could add extra macros or leave it as it is and include additional files. 

Every macro found in the included files and in `support_files/macros.xml` will be expanded. Users are responsible for copying the given macros files in their corresponding galaxy folders.

### Providing a default executable Path

* Purpose: Help Galaxy locate tools by providing a path.
* Short/long version: `-x` / `--default-executable-path`
* Required: no.
* Taken values: The default executable path of the tools in the Galaxy installation.

CTDs can contain an `<executablePath>` element that will be used when executing the tool binary. If this element is missing, the value provided by this parameter will be used as a prefix when building the `<command>` section. Suppose that you have installed a tool suite in your local Galaxy instance under `/opt/suite/bin`. The following invocation of the converter:

    $ python generator.py -x /opt/suite/bin ...
    
Will produce a `<command>` section similar to:

	<command>/opt/suite/bin/Foo ...</command>
	
For those CTDs in which no `<executablePath>` could be found.


### Generating a `datatypes_conf.xml` File

* Purpose: Specify the destination of a generated `datatypes_conf.xml` file.
* Short/long version: `-d` / `--datatypes-destination`
* Required: no.
* Taken values: The path in which `datatypes_conf.xml` will be generated.

It is likely that your tools use file formats or mimetypes that have not been registered in Galaxy. The generator allows you to specify a path in which an automatically generated `datatypes_conf.xml` file will be created. Consult the next section to get information about how to register file formats and mimetypes.


### Providing Galaxy File Formats

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


## Notes about some of the *OpenMS* Tools

* Most of the tools can be generated automatically. Some of the tools need some extra work (for now).
* These adapters need to be changed, such that you provide the path to the executable:
    * FidoAdapter (add `-exe fido` in the command tag, delete the `$param_exe` in the command tag, delete the parameter from the input list).
    * MSGFPlusAdapter (add `-executable msgfplus.jar` in the command tag, delete the `$param_executable` in the command tag, delete the parameter from the input list).
    * MyriMatchAdapter (add `-myrimatch_executable myrimatch` in the command tag, delete the `$param_myrimatch_executable` in the command tag, delete the parameter from the input list).
    * OMSSAAdapter (add `-omssa_executable omssa` in the command tag, delete the `$param_omssa_executable` in the command tag, delete the parameter from the input list).
    * PepNovoAdapter (add `-pepnovo_executable pepnovo` in the command tag, delete the `$param_pepnovo_executable` in the command tag, delete the parameter from the input list).
    * XTandemAdapter (add `-xtandem_executable xtandem` in the command tag, delete the $param_xtandem_executable in the command tag, delete the parameter from the input list).
    * To avoid the deletion in the inputs you can also add these parameters to the blacklist
    
        $ python generator.py -b exe executable myrimatch_excutable omssa_executable pepnovo_executable xtandem_executable

* These tools have multiple outputs (number of inputs = number of outputs) which is not yet supported in Galaxy-stable:
    * SeedListGenerator
    * SpecLibSearcher
    * MapAlignerIdentification
    * MapAlignerPoseClustering
    * MapAlignerSpectrum
    * MapAlignerRTTransformer

[CTDopts]: https://github.com/genericworkflownodes/CTDopts
[macros.xml]: https://github.com/WorkflowConversion/CTDConverter/blob/master/galaxy/macros.xml
[CTDSchema]: https://github.com/genericworkflownodes/CTDSchema