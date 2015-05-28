import sys, os, py
import subprocess
import cffi
from testing.udir import udir


def chdir_to_tmp(f):
    f.chdir_to_tmp = True
    return f

def from_outside(f):
    f.chdir_to_tmp = False
    return f


class TestDist(object):

    def setup_method(self, meth):
        self.executable = os.path.abspath(sys.executable)
        self.rootdir = os.path.abspath(os.path.dirname(os.path.dirname(
            cffi.__file__)))
        self.udir = udir.join(meth.__name__)
        os.mkdir(str(self.udir))
        if meth.chdir_to_tmp:
            self.saved_cwd = os.getcwd()
            os.chdir(str(self.udir))

    def teardown_method(self, meth):
        if hasattr(self, 'saved_cwd'):
            os.chdir(self.saved_cwd)

    def run(self, args):
        env = os.environ.copy()
        env['PYTHONPATH'] = self.rootdir
        subprocess.check_call([self.executable] + args, env=env)

    def _prepare_setuptools(self):
        if hasattr(TestDist, '_setuptools_ready'):
            return
        try:
            import setuptools
        except ImportError:
            py.test.skip("setuptools not found")
        subprocess.check_call([self.executable, 'setup.py', 'egg_info'],
                              cwd=self.rootdir)
        TestDist._setuptools_ready = True

    def check_produced_files(self, content, curdir=None):
        if curdir is None:
            curdir = str(self.udir)
        found_so = None
        for name in os.listdir(curdir):
            if (name.endswith('.so') or name.endswith('.pyd') or
                name.endswith('.dylib')):
                found_so = os.path.join(curdir, name)
                name = name.split('.')[0] + '.SO' # foo.cpython-34m.so => foo.SO
            assert name in content, "found unexpected file %r" % (
                os.path.join(curdir, name),)
            value = content.pop(name)
            if value is None:
                assert name.endswith('.SO') or (
                    os.path.isfile(os.path.join(curdir, name)))
            else:
                subdir = os.path.join(curdir, name)
                assert os.path.isdir(subdir)
                if value == '?':
                    continue
                found_so = self.check_produced_files(value, subdir) or found_so
        assert content == {}, "files or dirs not produced in %r: %r" % (
            curdir, content.keys())
        return found_so

    @chdir_to_tmp
    def test_empty(self):
        self.check_produced_files({})

    @chdir_to_tmp
    def test_abi_emit_python_code_1(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", None)
        ffi.emit_python_code('xyz.py')
        self.check_produced_files({'xyz.py': None})

    @chdir_to_tmp
    def test_abi_emit_python_code_2(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", None)
        py.test.raises(IOError, ffi.emit_python_code, 'unexisting/xyz.py')

    @from_outside
    def test_abi_emit_python_code_3(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", None)
        ffi.emit_python_code(str(self.udir.join('xyt.py')))
        self.check_produced_files({'xyt.py': None})

    @chdir_to_tmp
    def test_abi_compile_1(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", None)
        x = ffi.compile()
        self.check_produced_files({'mod_name_in_package': {'mymod.py': None}})
        assert x == os.path.join('.', 'mod_name_in_package', 'mymod.py')

    @chdir_to_tmp
    def test_abi_compile_2(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", None)
        x = ffi.compile('build2')
        self.check_produced_files({'build2': {
            'mod_name_in_package': {'mymod.py': None}}})
        assert x == os.path.join('build2', 'mod_name_in_package', 'mymod.py')

    @from_outside
    def test_abi_compile_3(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", None)
        tmpdir = str(self.udir.join('build3'))
        x = ffi.compile(tmpdir)
        self.check_produced_files({'build3': {
            'mod_name_in_package': {'mymod.py': None}}})
        assert x == os.path.join(tmpdir, 'mod_name_in_package', 'mymod.py')

    @chdir_to_tmp
    def test_api_emit_c_code_1(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", "/*code would be here*/")
        ffi.emit_c_code('xyz.c')
        self.check_produced_files({'xyz.c': None})

    @chdir_to_tmp
    def test_api_emit_c_code_2(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", "/*code would be here*/")
        py.test.raises(IOError, ffi.emit_c_code, 'unexisting/xyz.c')

    @from_outside
    def test_api_emit_c_code_3(self):
        ffi = cffi.FFI()
        ffi.set_source("package_name_1.mymod", "/*code would be here*/")
        ffi.emit_c_code(str(self.udir.join('xyu.c')))
        self.check_produced_files({'xyu.c': None})

    @chdir_to_tmp
    def test_api_compile_1(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", "/*code would be here*/")
        x = ffi.compile()
        if sys.platform != 'win32':
            sofile = self.check_produced_files({
                'mod_name_in_package': {'mymod.SO': None,
                                        'mymod.c': None,
                                        'mymod.o': None}})
            assert os.path.isabs(x) and os.path.samefile(x, sofile)
        else:
            self.check_produced_files({
                'mod_name_in_package': {'mymod.SO': None,
                                        'mymod.c': None},
                'Release': '?'})

    @chdir_to_tmp
    def test_api_compile_2(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", "/*code would be here*/")
        x = ffi.compile('output')
        if sys.platform != 'win32':
            sofile = self.check_produced_files({
                'output': {'mod_name_in_package': {'mymod.SO': None,
                                                   'mymod.c': None,
                                                   'mymod.o': None}}})
            assert os.path.isabs(x) and os.path.samefile(x, sofile)
        else:
            self.check_produced_files({
                'output': {'mod_name_in_package': {'mymod.SO': None,
                                                   'mymod.c': None},
                           'Release': '?'}})

    @from_outside
    def test_api_compile_3(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", "/*code would be here*/")
        x = ffi.compile(str(self.udir.join('foo')))
        if sys.platform != 'win32':
            sofile = self.check_produced_files({
                'foo': {'mod_name_in_package': {'mymod.SO': None,
                                                'mymod.c': None,
                                                'mymod.o': None}}})
            assert os.path.isabs(x) and os.path.samefile(x, sofile)
        else:
            self.check_produced_files({
                'foo': {'mod_name_in_package': {'mymod.SO': None,
                                                'mymod.c': None},
                        'Release': '?'}})

    @chdir_to_tmp
    def test_api_distutils_extension_1(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", "/*code would be here*/")
        ext = ffi.distutils_extension()
        self.check_produced_files({'build': {
            'mod_name_in_package': {'mymod.c': None}}})
        if hasattr(os.path, 'samefile'):
            assert os.path.samefile(ext.sources[0],
                                    'build/mod_name_in_package/mymod.c')

    @from_outside
    def test_api_distutils_extension_2(self):
        ffi = cffi.FFI()
        ffi.set_source("mod_name_in_package.mymod", "/*code would be here*/")
        ext = ffi.distutils_extension(str(self.udir.join('foo')))
        self.check_produced_files({'foo': {
            'mod_name_in_package': {'mymod.c': None}}})
        if hasattr(os.path, 'samefile'):
            assert os.path.samefile(ext.sources[0],
                str(self.udir.join('foo/mod_name_in_package/mymod.c')))


    def _make_distutils_api(self):
        os.mkdir("src")
        os.mkdir(os.path.join("src", "pack1"))
        with open(os.path.join("src", "pack1", "__init__.py"), "w") as f:
            pass
        with open("setup.py", "w") as f:
            f.write("""if 1:
                import cffi
                ffi = cffi.FFI()
                ffi.set_source("pack1.mymod", "/*code would be here*/")

                from distutils.core import setup
                setup(name='example1',
                      version='0.1',
                      packages=['pack1'],
                      package_dir={'': 'src'},
                      ext_modules=[ffi.distutils_extension()])
            """)

    @chdir_to_tmp
    def test_distutils_api_1(self):
        self._make_distutils_api()
        self.run(["setup.py", "build"])
        self.check_produced_files({'setup.py': None,
                                   'build': '?',
                                   'src': {'pack1': {'__init__.py': None}}})

    @chdir_to_tmp
    def test_distutils_api_2(self):
        self._make_distutils_api()
        self.run(["setup.py", "build_ext", "-i"])
        self.check_produced_files({'setup.py': None,
                                   'build': '?',
                                   'src': {'pack1': {'__init__.py': None,
                                                     'mymod.SO': None}}})

    def _make_setuptools_abi(self):
        self._prepare_setuptools()
        os.mkdir("src0")
        os.mkdir(os.path.join("src0", "pack2"))
        with open(os.path.join("src0", "pack2", "__init__.py"), "w") as f:
            pass
        with open(os.path.join("src0", "pack2", "_build.py"), "w") as f:
            f.write("""if 1:
                import cffi
                ffi = cffi.FFI()
                ffi.set_source("pack2.mymod", None)
            """)
        with open("setup.py", "w") as f:
            f.write("""if 1:
                from setuptools import setup
                setup(name='example1',
                      version='0.1',
                      packages=['pack2'],
                      package_dir={'': 'src0'},
                      cffi_modules=["src0/pack2/_build.py:ffi"])
            """)

    @chdir_to_tmp
    def test_setuptools_abi_1(self):
        self._make_setuptools_abi()
        self.run(["setup.py", "build"])
        self.check_produced_files({'setup.py': None,
                                   'build': '?',
                                   'src0': {'pack2': {'__init__.py': None,
                                                      '_build.py': None}}})

    @chdir_to_tmp
    def test_setuptools_abi_2(self):
        self._make_setuptools_abi()
        self.run(["setup.py", "build_ext", "-i"])
        self.check_produced_files({'setup.py': None,
                                   'src0': {'pack2': {'__init__.py': None,
                                                      '_build.py': None,
                                                      'mymod.py': None}}})

    def _make_setuptools_api(self):
        self._prepare_setuptools()
        os.mkdir("src1")
        os.mkdir(os.path.join("src1", "pack3"))
        with open(os.path.join("src1", "pack3", "__init__.py"), "w") as f:
            pass
        with open(os.path.join("src1", "pack3", "_build.py"), "w") as f:
            f.write("""if 1:
                import cffi
                ffi = cffi.FFI()
                ffi.set_source("pack3.mymod", "/*code would be here*/")
            """)
        with open("setup.py", "w") as f:
            f.write("""if 1:
                from setuptools import setup
                setup(name='example1',
                      version='0.1',
                      packages=['pack3'],
                      package_dir={'': 'src1'},
                      cffi_modules=["src1/pack3/_build.py:ffi"])
            """)

    @chdir_to_tmp
    def test_setuptools_api_1(self):
        self._make_setuptools_api()
        self.run(["setup.py", "build"])
        self.check_produced_files({'setup.py': None,
                                   'build': '?',
                                   'src1': {'pack3': {'__init__.py': None,
                                                      '_build.py': None}}})

    @chdir_to_tmp
    def test_setuptools_api_2(self):
        self._make_setuptools_api()
        self.run(["setup.py", "build_ext", "-i"])
        self.check_produced_files({'setup.py': None,
                                   'build': '?',
                                   'src1': {'pack3': {'__init__.py': None,
                                                      '_build.py': None,
                                                      'mymod.SO': None}}})