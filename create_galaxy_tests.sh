conda create -y --quiet --override-channels --channel iuc --channel conda-forge --channel bioconda --channel defaults --name ctdopts-1.4 ctdopts=1.4 lxml

python convert.py galaxy -i tests/test-data/*.ctd -o tests/test-data/ -m tests/test-data/macros.xml -f tests/test-data/filetypes.txt --test-test -p tests/test-data/hardcoded_params.json --tool-version 3.8
