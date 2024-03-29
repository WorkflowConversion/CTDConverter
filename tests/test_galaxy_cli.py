import os
import subprocess
import tempfile
import unittest


def to_test_data(*args):
    return os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "test-data", *args))


def file2list(pth):
    with open(pth) as f:
        lines = f.readlines()
    return lines


class GalaxyCliTestCase(unittest.TestCase):

    def _compare_cli_output(self, fileprefix):
        in_pth = to_test_data(f'{fileprefix}.ctd')
        macro_pth = to_test_data('macros.xml')
        ftypes_pth = to_test_data('filetypes.txt')
        hcparam_pth = to_test_data('hardcoded_params.json')
        tmp = tempfile.mkdtemp()

        out_file = os.path.join(tmp, f'{fileprefix}.xml')
        # out_file = to_test_data('{}.xml'.format(fileprefix))
        my_env = os.environ.copy()
        my_env["PATH"] = fileprefix + ":" + my_env["PATH"]
        cmd = ['CTDConverter', 'galaxy', '-i', in_pth, '-o', out_file, '-f', ftypes_pth, '-m', macro_pth, '--test-test', '-p', hcparam_pth, "--tool-version", "3.8"]
#         print("cmd %s" % cmd)

        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=my_env)
        stdout, stderr = popen.communicate()
        assert popen.returncode == 0, f"could not convert {fileprefix} with: " + " ".join(cmd) + f"\n{stdout}\n{stderr}"
#         print("out %s" % output)
#         print("err %s" % err)

        old_file_pth = to_test_data(f'{fileprefix}.xml')

#         print("out_file %s" % out_file)
#         print("old_file_path %s" % old_file_pth)

        new_l = file2list(out_file)
        old_l = file2list(old_file_pth)

        for i in range(0, len(new_l)):
            self.assertEqual(new_l[i].rstrip(), old_l[i].rstrip()), f"xml files differed for {fileprefix}"

    def test_galaxy_cli_bool_ctd(self):
        self._compare_cli_output('bool')

    def test_galaxy_cli_empty_ctd(self):
        self._compare_cli_output('empty')

    def test_galaxy_cli_float_ctd(self):
        self._compare_cli_output('float')

    def test_galaxy_cli_integer_ctd(self):
        self._compare_cli_output('integer')

    def test_galaxy_cli_repeat_ctd(self):
        self._compare_cli_output('repeat_test')

    def test_galaxy_cli_select_ctd(self):
        self._compare_cli_output('select_test')

    def test_galaxy_cli_string_ctd(self):
        self._compare_cli_output('string')

    def test_galaxy_cli_ifile_ctd(self):
        self._compare_cli_output('ifile')

    def test_galaxy_cli_ofile_ctd(self):
        self._compare_cli_output('ofile')

    def test_galaxy_cli_ofile_corresponding_input_ctd(self):
        self._compare_cli_output('ofile-corresponding-input')

    def test_galaxy_cli_ofile_typeparam(self):
        self._compare_cli_output('ofile-typeparam')

    def test_galaxy_cli_ofile_mult_ctd(self):
        self._compare_cli_output('ofile-mult')

    def test_galaxy_cli_ofile_mult_typeparam_ctd(self):
        self._compare_cli_output('ofile-mult-typeparam')


if __name__ == '__main__':
    unittest.main()
