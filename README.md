GalaxyConfigGenerator
=====================

Given a CTD file, GalaxyConfigGenerator generates a Galaxy wrapper.

How to install
==============
1. Download the source code from https://github.com/genericworkflownodes/GalaxyConfigGenerator
2. Download CTDopts from https://github.com/genericworkflownodes/CTDopts
3. You can install the CTDopts and GalaxyConfigGenerator modules, or just make them available through your PYTHONPATH environment variable. To get more information about how to install python modules, visit: https://docs.python.org/2/install/

How to use
==========
The generator takes two parameters: 1) an input file to convert and 2) the output destination. Example:

$ python generator.py -i /data/sample_input.ctd -o /data/sample_output.xml

Will parse /data/sample_input.ctd and generate a Galaxy tool wrapper under /data/sample_output.xml; this generated file can be added to your Galaxy instance like any other tool.
