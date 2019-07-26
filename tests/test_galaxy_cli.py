import unittest
import os
import subprocess
import tempfile

def to_test_data(*args):
    return os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "test-data", *args))

def file2list(pth):
    with open(pth) as f:
        lines = f.readlines()
    return lines

class GalaxyCliTestCase(unittest.TestCase):

    def _compare_cli_output(self, fileprefix):
        in_pth = to_test_data('{}.ctd'.format(fileprefix))
        macro_pth = to_test_data('macros.xml')
        ftypes_pth = to_test_data('filetypes.txt')
        tmp = tempfile.mkdtemp()

        out_file = os.path.join(tmp, '{}.xml'.format(fileprefix))
        #out_file = to_test_data('{}.xml'.format(fileprefix))

        cmd = ['CTDConverter', 'galaxy', '-i', in_pth, '-o', out_file, '-f', ftypes_pth, '-m', macro_pth, '-b', 'version', '--test-test']
        print(cmd)

        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, err = popen.communicate()
        print(output)
        print(err)

        old_file_pth = to_test_data('{}.xml'.format(fileprefix))

        print(out_file)
        print(old_file_pth)

        new_l = file2list(out_file)
        old_l = file2list(old_file_pth)

        for i in range(0, len(new_l)):
            self.assertEqual(new_l[i].rstrip(), old_l[i].rstrip())
        
        cmd = ['planemo', 'l', out_file]
        print(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, err = popen.communicate()
        print(output)
        print(err)
        self.assertEqual(err, 0)

        cmd = ['planemo', 't', out_file]
        print(cmd)
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, err = popen.communicate()
        print(output)
        print(err)
        self.assertEqual(err, 0)

    def test_galaxy_cli_bool_ctd(self):
        self._compare_cli_output('bool')

    def test_galaxy_cli_empty_ctd(self):
        self._compare_cli_output('empty')

    def test_galaxy_cli_float_ctd(self):
        self._compare_cli_output('float')

    def test_galaxy_cli_integer_ctd(self):
        self._compare_cli_output('integer')

    def test_galaxy_cli_repeat_ctd(self):
        self._compare_cli_output('repeat')

    def test_galaxy_cli_select_ctd(self):
        self._compare_cli_output('select')

    def test_galaxy_cli_string_ctd(self):
        self._compare_cli_output('string')

    def test_galaxy_cli_ifile_ctd(self):
        self._compare_cli_output('ifile')

    def test_galaxy_cli_ofile_ctd(self):
        self._compare_cli_output('ofile')


if __name__ == '__main__':
    unittest.main()
