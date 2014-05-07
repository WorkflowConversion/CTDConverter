# GalaxyConfigGenerator


Given one or more CTD files, GalaxyConfigGenerator generates the needed Galaxy wrappers.

## How to install

1. Download the source code from https://github.com/genericworkflownodes/GalaxyConfigGenerator.
2. Download CTDopts from https://github.com/genericworkflownodes/CTDopts.
3. You can install the CTDopts and GalaxyConfigGenerator modules, or just make them available through your `PYTHONPATH` environment variable. To get more information about how to install python modules, visit: https://docs.python.org/2/install/.

## How to use

The generator takes several parameters and a varying number of inputs and outputs. The following sub-sections show how to perform the most common operations.

### One input, one output

In its simplest form, GalaxyConfigGenerator takes an input CTD file and generates an output Galaxy *ToolConfig* file. The following use of GalaxyConfigGenerator:

    $ python generator.py -i /data/sample_input.ctd -o /data/sample_output.xml

will parse `/data/sample_input.ctd` and generate a Galaxy tool wrapper under `/data/sample_output.xml`; this generated file can be added to your Galaxy instance like any other tool.

### Converting several CTDs found in a folder


    $ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs
    
### Generating a tool_conf.xml file 


    $ python generator.py -i /data/ctds/*.ctd -o /data/generated-galaxy-stubs -t /data/generated-galaxy-stubs/tool_conf.xml


## Parameters in detail


### A word about parameters taking list of values

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
    
### Input file(s)

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

    $ python generator.py -i /data/input.ctd -o /data/output.xml
    
Of course, you can also use Unix wildcards, which will be automatically expanded. This is extremely useful if you want to convert several files at a time. Imagine that the folder `/data/ctds` contains three files, `input_one.ctd`, `input_two.ctd` and `input_three.ctd`. The following two invocations will produce the same output in the `/data/galaxy` folder if Unix wildcards are supported in your OS:

    $ python generator.py -i /data/input_one.ctd /data/input_two.ctd /data/input_three.ctd -o /data/galaxy
    $ python generator.py -i /data/*.ctd -o /data/galaxy

### Output destination

* Purpose: Provide output destination for the generated Galaxy *ToolConfig* files.
* Short/long version: `-o` / `--output-destination`
* Required: yes.
* Taken values: if a single input file is given, then a single output file is expected. If multiple input files are given, then an existent folder, in which all generated Galaxy *ToolConfig* will be written, is expected.

Example:

A single input is given, and the output will be generated into `/data/output.xml`:

    $ python generator.py -i /data/input.ctd -o /data/output.xml
    
Several inputs are given. The output is the already existent folder, `/data/stubs`, and at the end of the operation, the files `/data/stubs/input_one.ctd.xml` and `/data/stubs/input_two.ctd.xml` will be generated:

    $ python generator.py -i /data/ctds/input_one.ctd /data/ctds/input_two.ctd -o /data/stubs


### Adding parameters to the command line

* Purpose: Galaxy *ToolConfig* files include a `<command>` element in which the command line to invoke the tool can be given. Sometimes it is needed to invoke your tools in a certain way (i.e., passing certain parameters). For instance, some tools offer the possibility to be invoked in a verbose or quiet way or even to be invoked in a headless way (i.e., without GUI).
* Short/long version: `-a` / `--add-to-command-line`
* Required: no.
* Taken values: The command(s) to be added to the command line.

Example:

    $ python generator.py ... -a "--quiet --no-gui"

Will generate the following `<command>` element in the generated Galaxy *ToolConfig*:

    <command>TOOL_NAME --quiet --no-gui ...</command>
    

### Validating parameter values for emptiness

* Purpose: Command line invocation can be scary sometimes. Some parameters, when passed to a Galaxy tool, might contain an empty string. Use this parameter to add validation against empty strings.
* Short/long version: `-w` / `--whitespace-validation`
* Required: no.
* Taken values: None.

Example:

    $ python generator.py ... -w

For each of the parameters located in the given input CTD, the generated Galaxy *ToolConfig* will contain a similar section to the following one:

    <command>TOOL_NAME 
        #if str( $foo_value ) != ''  and str( $foo_value ) != None :
          -foo $foo_value
        #end if
    </command>

### Quoting parameters

* Purpose: Passing strings containing whitespace might be problematic for some tools to handle. You can use this parameter to quote parameters and avoid problems.
* Short/long version: `-q` / `--quote-parameters`
* Required: no.
* Taken values: None. 

Example:

    $ python generator.py ... -q
    
Will generate a similar `<command>` element to the following one:

    <command>TOOL_NAME --param_one "$param_one_value"</command>    

### Blacklisting parameters

* Purpose: Some parameters present in the CTD are not to be exposed on Galaxy. Think of parameters such as `--help`, that don't make much sense to be exposed to final users in a workflow management system such as Galaxy.
* Short/long version: `-b` / `--blacklist`
* Required: no.
* Taken values: A list of parameters to be blacklisted.

Example:

    $ python generator.py ... -b h help quiet
    
Will not process any of the parameters named `h`, `help`, or `quiet` and will not appear in the generated Galaxy *ToolConfig*.

### Providing exit code ranges

* Purpose: Galaxy reads the exit code of an invoked tool and can be configured to act depending on the exit code. This parameter allows you to include this information in a generated Galaxy *ToolConfig*.
* Short/long version: `-x` / `--exit-code`
* Required: no.
* Taken values: A list of Galaxy exit code elements given in the following format:

`range=<range>,level=<level>[,description=<description>]`

Note that `description` is optional. Both `range` and `level` are required. Thus, the following are valid values for this parameter:

    range=5:,level=fatal,description=Fatal error
    range=127:,level=warning

Example:

    $ python generator.py ... -x "range=1:5,level=fatal,description=I/O" -x "range=6:,level=warning,description=Non fatal"
    
Will produce the following `<stdio>` section in the generated Galaxy *ToolConfig*:

    <stdio>
        <exit_code range="1:5" level="fatal" description="I/O"/>
        <exit_code range="6:" level="warning" description="Non fatal"/>
    </stdio>
    
For more information about providing valid values for `range` and `level`, go to https://wiki.galaxyproject.org/Admin/Tools/ToolConfigSyntax#A.3Cexit_code.3E_tag_set

### Generating a tool_conf.xml file

* Purpose: Galaxy uses a file `tool_conf.xml` in which other tools can be included. GalaxyConfigGenerator can also generate this file. Categories will be extracted from the provided input CTDs and for each category, a different `<section>` will be generated. Any input CTD lacking a category will be sorted under the provided default category.
* Short/long version: `-t` / `--tool-conf-destination`
* Required: no.
* Taken values: The destination of the file.

### Providing a default category

* Purpose: Input CTDs that lack a category will be sorted under the value given to this parameter. If this parameter is not given, then the category `DEFAULT` will be used.
* Short/long version: `-d` / `--default-category`
* Required: no.
* Taken values: The value for the default category to use for input CTDs lacking a category.

Example:

Suppose there is a folder containing several CTD files. Some of those CTDs don't have the optional attribute `category` and the rest belong to the `Data Processing` category. The following invocation:

    $ python generator.py ... -d Other
    
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

### Providing package requirements

* Purpose: Dependency of tools is managed in Galaxy by using package requirements. This parameter allows you to provide GalaxyConfigGenerator with the required packages when a `tool_conf.xml` is generated.
* Short/long version: `-p` / `--package-requirement`
* Required: no.
* Taken values: A list of packages on which the generated tools are dependent.

Example:

    $ python generator.py ... -p apache-tools java-galaxy
    
Will generate the following requirement section in the generated `/data/tool_conf.xml`:

    <requirements>
        <requirement type="package">apache-tools</requirement>
        <requirement type="package">java-galaxy</requirement>
    </requirements>

### Providing a path for the location of the ToolConfig files

* Purpose: The `tool_conf.xml` file contains references to files which in turn contain Galaxy *ToolConfig* files. Using this parameter, you can provide information about the location of your tools.
* Short/long version: `-g` / `--galaxy-tool-path`
* Required: no.
* Taken values: The path relative to your `$GALAXY_ROOT/tools` folder on which your tools are located.

Example:

    $ python generator.py ... -g my_tools_folder
    
Will generate `<tool>` elements in the generated `tool_conf.xml` as follows:

    <tool file="my_tools_folder/some_tool.xml" />
