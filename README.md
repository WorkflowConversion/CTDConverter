# CTDConverter
Given one or more CTD files, `CTDConverter` generates the needed wrappers to include them in workflow engines, such as Galaxy and CWL.

## Dependencies
`CTDConverter` has the following python dependencies:

- [CTDopts] 
- `lxml`
- `ruamel.yaml`
- Python 3.6+

Python 2.x is no longer supported as of release 3.0.0

### Installing Dependencies
We recommend the use of `conda` to manage all dependencies. If you're not sure what `conda` is, make sure to read about the [conda project](https://conda.io/docs/index.html).

The easiest way to get you started with CTD conversion is to create a `conda` environment on which you'll install all dependencies.  Using environments in `conda` allows you to have parallel, independent python environments, thus avoiding conflicts between libraries. 

If you haven't installed `conda`, check [conda-install](conda's installation guide). See [this guide](https://conda.io/docs/user-guide/tasks/manage-environments.html) if you need help creating a `conda` environment.

Once you've installed `conda`, create an environment named `ctd-converter`, like so:

```sh
$ conda create --name ctd-converter
```

You will now need to *activate* the environment by executing the following command:

```sh
$ source activate ctd-converter
```

Install the required dependencies as follows (the order of execution **is actually important**, due to transitive dependencies):

```sh
$ conda install --channel workflowconversion ctdopts
$ conda install lxml
$ conda install --channel conda-forge ruamel.yaml
$ conda install libxml2=2.9.2
```

`lxml` depends on `libxml2`. When you install `lxml` you'll get the latest version of `libxml2` (2.9.4) by default. You would usually want the latest version, but there is, however, a bug in validating XML files against a schema in this version of `libxml2`.

If you require validation of input CTDs against a schema (which we recommend), you will need to downgrade to the latest known version of `libxml2` that works, namely, 2.9.2.

You could just download dependencies manually and make them available through your `PYTHONPATH` environment variable, if you're into that. To get more information about how to install python modules without using `conda`, visit: https://docs.python.org/2/install/.

## How to install `CTDConverter`
`CTDConverter` is not a python module, rather, a series of scripts, so installing it is as easy as downloading the source code from https://github.com/genericworkflownodes/CTDConverter. Once you've installed all dependencies, downloaded `CTDConverter` and activated your `conda` environment, you're good to go.

## Usage
The first thing that you need to tell `CTDConverter` is the output format of the converted wrappers. `CTDConverter` supports conversion of CTDs into Galaxy and CWL. Invoking it is as simple as follows:

    $ python convert.py [FORMAT] [ADDITIONAL_PARAMETERS ...]   
    
Here `[FORMAT]` can be any of the supported formats (i.e., `cwl`, `galaxy`). `CTDConverter` offers a series of format-specific scripts and we've designed these scripts to behave *somewhat* similarly. All converter scripts have the same core functionality, that is, read CTD files, parse them using [CTDopts], validate against a schema, etc. Of course, each converter script might add extra functionality that is not present in other engines. Only the Galaxy converter script supports generation of a `tool_conf.xml` file, for instance.

The following sections in this file describe the parameters that all converter scripts share.

Please refer to the detailed documentation for each of the converters for more information:

- [Generation of Galaxy ToolConfig files](galaxy/README.md)
- [Generation of CWL CommandLineTool descriptions](ctdconverter/cwl/README.md)

## Fail Policy while processing several Files
`CTDConverter` can parse several CTDs and convert them. However, the process will be interrupted and an error code will be returned at the first encountered error (e.g., a CTD is not valid, there are missing support files, etc.).

## Converting a single CTD
In its simplest form, the converter takes an input CTD file and generates an output file. The following usage of `CTDConverter`:

    $ python convert.py [FORMAT] -i /data/sample_input.ctd -o /data/sample_output.xml

will parse `/data/sample_input.ctd` and generate an appropriate converted file under `/data/sample_output.xml`. The generated file can be added to your workflow engine as usual.

## Converting several CTDs
When converting several CTDs, the expected value for the `-o`/`--output` parameter is a folder. For example:

    $ python convert.py [FORMAT] -i /data/ctds/one.ctd /data/ctds/two.ctd -o /data/converted-files
    
Will convert `/data/ctds/one.ctd` into `/data/converted-files/one.[EXT]` and `/data/ctds/two.ctd` into `/data/converted-files/two.[EXT]`. Each converter has a preferred extension, here shown as a variable (`[EXT]`). Galaxy prefers `xml`, while CWL prefers `cwl`.
    
You can use wildcard expansion, as supported by most modern operating systems:
	
    $ python convert.py [FORMAT] -i /data/ctds/*.ctd -o /data/converted-files
    
## Common Parameters	
### Input File(s)
* Purpose: Provide input CTD file(s) to convert.
* Short/long version: `-i` / `--input`
* Required: yes.
* Taken values: a list of input CTD files.

Examples:

Any of the following invocations will convert `/data/input_one.ctd` and `/data/input_two.ctd`:

    $ python convert.py [FORMAT] -i /data/input_one.ctd -i /data/input_two.ctd -o /data/generated
    $ python convert.py [FORMAT] -i /data/input_one.ctd /data/input_two.ctd -o /data/generated
    $ python convert.py [FORMAT] --input /data/input_one.ctd /data/input_two.ctd -o /data/generated
    $ python convert.py [FORMAT] --input /data/input_one.ctd --input /data/input_two.ctd -o /data/generated 
    
The following invocation will convert `/data/input.ctd` into `/data/output.xml`:

    $ python convert.py [FORMAT] -i /data/input.ctd -o /data/output.xml 
    
Of course, you can also use wildcards, which will be automatically expanded by any modern operating system. This is extremely useful if you want to convert several files at a time. Let's assume that the folder `/data/ctds` contains three files: `input_one.ctd`, `input_two.ctd` and `input_three.ctd`. The following two invocations will produce the same output in the `/data/wrappers` folder:

    $ python convert.py [FORMAT] -i /data/input_one.ctd /data/input_two.ctd /data/input_three.ctd -o /data/wrappers
    $ python convert.py [FORMAT] -i /data/*.ctd -o /data/wrappers

### Output Destination
* Purpose: Provide output destination for the converted wrapper files.
* Short/long version: `-o` / `--output-destination`
* Required: yes.
* Taken values: if a single input file is given, then a single output file is expected. If multiple input files are given, then an existent folder in which all converted CTDs will be written is expected.

Examples:

A single input is given, and the output will be generated into `/data/output.xml`:

    $ python convert.py [FORMAT] -i /data/input.ctd -o /data/output.xml
    
Several inputs are given. The output is the already existent folder, `/data/wrappers`, and at the end of the operation, the files `/data/wrappers/input_one.[EXT]` and `/data/wrappers/input_two.[EXT]` will be generated:

    $ python convert.py [FORMAT] -i /data/ctds/input_one.ctd /data/ctds/input_two.ctd -o /data/stubs
    
Please note that the output file name is **not** taken from the name of the input file, rather from the name of the tool, that is, from the `name` attribute in the `<tool>` element in its corresponding CTD. By convention, the name of the CTD file and the name of the tool match.

### Exclusion, hardcoding, and modification of Parameters
* Purpose: Some parameters present in the CTD are not to be exposed on the output files (e.g. parameters such as `--help`, `--debug` that might won't make much sense to be exposed to users in a workflow management system), other parameters should be hardcoded (i.e. parameters that should not be exposed to the user but still set to a fixed value on the generated command line), and for other parameters it might be necessary to modify attributes of the input CTD or the generated output.
* Short/long version: `-p` / `--hardcoded-parameters`
* Required: no.
* Taken values: A json file defining: exclusion, hardcoded, and modifications of parameters

Example:

    $ pythonconvert.py [FORMAT] ... -p JSON_FILE

The json defines a mapping from parameter names to a list of modifications:

```
{
    "parameter1": [MODIFICATION1, ...], 
    "parameter2": [MODIFICATION1, ...]
    ...
}
```

where each modification is a mapping as defined below.


#### Hardcoding parameters

If a parameter should always be set on the command line using a fixed value, 
i.e. the user can to choose the value, this can be done as follows: 

`"parameter": [{"value":"HARDCODED_VALUE"}]`

#### Excluding parameters

In order to exclude a parameter, it will not appear in the generated tool or
the generated command line, the same syntax as for hardcoding is used but a
special reserved value is used:

`"parameter": [{"value": "@"}]`

#### Modifying parameters

It's possible to modify attributes of the input CTD definition of a parameter
as well as attributes of the generated Galaxy XML tags. 

```
	"test": [{
		"CTD:type": "text",
		"XML:type": "hidden"
	}],
```

### Restricting modifications to a subset of the tools

Its possible to specify modifications to a parameter for only a subset of the tools
by specifying a list of tools as follows:

```
    "output_files": [{
		"CTD:required": true,
		"tools": ["OpenSwathDIAPreScoring"]
	}, {
		"CTD:restrictions": "txt,tsv,pep.xml,pepXML,html",
		"tools": ["SpectraSTSearchAdapter"]
	
	}]
```

### Schema Validation
* Purpose: Provide validation of input CTDs against a schema file (i.e, a XSD file).
* Short/long version: `-V` / `--validation-schema`
* Required: no.
* Taken values: location of the schema file (e.g., CTD.xsd).

CTDs can be validated against a schema. The master version of the schema can be found on [CTDSchema].

If a schema is provided, all input CTDs will be validated against it. 

**NOTE:** Please make sure to read the [section on issues with schema validation](#issues-with-libxml2-and-schema-validation) if you require validation of CTDs against a schema.

### Providing a default executable Path
* Purpose: Help workflow engines locate tools by providing a path.
* Short/long version: `-x` / `--default-executable-path`
* Required: no.
* Taken values: The default executable path of the tools in the target workflow engine.

CTDs can contain an `<executablePath>` element that will be used when executing the tool binary. If this element is missing, the value provided by this parameter will be used as a prefix when building the appropriate sections in the output files. 

The following invocation of the converter will use `/opt/suite/bin` as a prefix when providing the executable path in the output files for any input CTD that lacks the `<executablePath>` section:

    $ python convert.py [FORMAT] -x /opt/suite/bin ...

### Bump wrapper versions

There are two ways to bump tool versions.  

- Definition of a `@GALAXY_VERSION@` token in the macros file. This can be used to bump all tools at once. Tool versions will be `@TOOL_VERSION@+galaxy@GALAXY_VERSION@`.
- Use the `--bump-file` parameter to specify the wrapper version of a subset of the tools in a json file that maps tool names/ids to a wrapper version. Tool version will be set to `@TOOL_VERSION@+galaxyX`, where `X` is the version found in the json file or `0` if not found.

In case of an update of the tool version, i.e. `@TOOL_VERSION@`, in the first case `@GALAXY_VERSION@` should be reset to 0 and the dictionary in the bump file should be emptied otherwise.

Rationale: the auto-generation of the tool xml files would overwrite the
wrapper version when regenerated. Hence it needs to be specified externally,
e.g. in the macros.xml or in the bump file.

### Tests

Tests for Galaxy tools are generated with:

```
PATH=$(pwd)/tests/test-data/:$PATH
for i in tests/test-data/*ctd
do
b=$(basename $i .ctd)
python convert.py galaxy -i tests/test-data/$b.ctd -o tests/test-data/$b.xml -m tests/test-data/macros.xml -f tests/test-data/filetypes.txt --test-test -p tests/test-data/hardcoded_params.json  --tool-version 5.0.011
done
```


[CTDopts]: https://github.com/genericworkflownodes/CTDopts
[CTDSchema]: https://github.com/WorkflowConversion/CTDSchema
[conda-install]: https://conda.io/docs/install/quick.html
[using-conda]: https://conda.io/docs/using/envs.html
