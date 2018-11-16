#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, distutils, Command
from setuptools.command.build_py import build_py

try:
    from cx_Freeze import setup, Executable
except ImportError:
    Executable = lambda x, **kw: x


# Awesome hack to Load `__version__`
exec(open("parsec/_version.py", encoding="utf-8").read())


class GeneratePyQtResourcesBundle(Command):
    description = "Generates `parsec.core.gui._resource_rc` bundle module"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            from PyQt5.pyrcc_main import processResourceFile

            self.announce("Generating `parsec.core.gui._resources_rc`", level=distutils.log.INFO)
            processResourceFile(
                [f"parsec/core/gui/rc/resources.qrc"], f"parsec/core/gui/_resources_rc.py", False
            )
        except ImportError:
            print("PyQt5 not installed, skipping `parsec.core.gui._resources_rc` generation.")


class GeneratePyQtForms(Command):
    description = "Generates `parsec.core.ui.*` forms module"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import os
        import pathlib
        from collections import namedtuple

        try:
            from PyQt5.uic.driver import Driver
        except ImportError:
            print("PyQt5 not installed, skipping `parsec.core.gui.ui` generation.")
            return

        self.announce("Generating `parsec.core.gui.ui`", level=distutils.log.INFO)
        Options = namedtuple(
            "Options",
            ["output", "import_from", "debug", "preview", "execute", "indent", "resource_suffix"],
        )
        ui_dir = pathlib.Path("parsec/core/gui/forms")
        ui_path = "parsec/core/gui/ui"
        os.makedirs(ui_path, exist_ok=True)
        for f in ui_dir.iterdir():
            o = Options(
                output=os.path.join(ui_path, "{}.py".format(f.stem)),
                import_from="parsec.core.gui",
                debug=False,
                preview=False,
                execute=False,
                indent=4,
                resource_suffix="_rc",
            )
            d = Driver(o, str(f))
            d.invoke()


class GeneratePyQtTranslations(Command):
    description = "Generates ui translation files"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import os
        import pathlib
        import subprocess
        from unittest.mock import patch

        try:
            from PyQt5.pylupdate_main import main as pylupdate_main
        except ImportError:
            print("PyQt5 not installed, skipping `parsec.core.gui.ui` generation.")
            return

        self.announce("Generating ui translation files", level=distutils.log.INFO)
        rc_dir = "parsec/core/gui/rc/translations"
        os.makedirs(rc_dir, exist_ok=True)
        new_args = ["pylupdate", "parsec/core/gui/parsec-gui.pro"]
        with patch("sys.argv", new_args):
            pylupdate_main()
        tr_dir = pathlib.Path("parsec/core/gui/tr")
        for f in tr_dir.iterdir():
            subprocess.call(
                [
                    "lrelease",
                    "-compress",
                    str(f),
                    "-qm",
                    os.path.join(rc_dir, "{}.qm".format(f.stem)),
                ],
                stdout=subprocess.DEVNULL,
            )


class build_py_with_pyqt(build_py):
    def run(self):
        self.run_command("generate_pyqt_forms")
        self.run_command("generate_pyqt_resources_bundle")
        return super().run()


class build_py_with_pyqt_resource_bundle_generation(build_py):
    def run(self):
        self.run_command("generate_pyqt_resources_bundle")
        return super().run()


def _extract_libs_cffi_backend():
    try:
        import nacl
    except ImportError:
        return []

    import pathlib

    cffi_backend_dir = pathlib.Path(nacl.__file__).parent / "../.libs_cffi_backend"
    return [(lib.as_posix(), lib.name) for lib in cffi_backend_dir.glob("*")]


def _ui_files():
    import pathlib

    ui_dir = pathlib.Path("parsec/core/gui/ui")
    return [(file.as_posix(), file.name) for file in ui_dir.glob("*")]


build_exe_options = {
    "packages": [
        "idna",
        "trio._core",
        "nacl._sodium",
        "html.parser",
        "pkg_resources._vendor",
        "swiftclient",
        "setuptools.msvc",
        "unittest.mock",
    ],
    # nacl store it cffi shared lib in a very strange place...
    "include_files": _extract_libs_cffi_backend() + _ui_files(),
}


with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "attrs==18.1.0",
    "click==6.7",
    "huepy==0.9.6",
    # Can use marshmallow or the toasted flavour as you like ;-)
    # "marshmallow==2.14.0",
    "toastedmarshmallow==0.2.6",
    "pendulum==1.3.1",
    "PyNaCl==1.2.0",
    "simplejson==3.10.0",
    "python-decouple==3.1",
    "trio==0.9.0",
    "python-interface==1.4.0",
    "async_generator>=1.9",
    'contextvars==2.1;python_version<"3.7"',
    "raven==6.8.0",  # Sentry support
    "structlog==18.2.0",
    "colorama==0.4.0",  # structlog colored output
]


test_requirements = [
    "pytest>=3.8.1",
    "pytest-cov",
    "pytest-trio>=0.5.1",
    "tox",
    "wheel",
    "Sphinx",
    "flake8",
    "hypothesis",
    "hypothesis-trio>=0.2.1",
    "black==18.6b1",  # Pin black to avoid flaky style check
]


PYQT_DEP = "PyQt5==5.11.2"
extra_requirements = {
    "pkcs11": ["python-pkcs11==0.5.0", "pycrypto==2.6.1"],
    "core": [PYQT_DEP, "fusepy==3.0.1"],
    "backend": [
        # PostgreSQL
        "triopg==0.3.0",
        "trio-asyncio==0.9.1",
        # S3
        "boto3==1.4.4",
        "botocore==1.5.46",
        # Swift
        "python-swiftclient==3.5.0",
        "pbr==4.0.2",
        "futures==3.1.1",
    ],
    "dev": test_requirements,
}
extra_requirements["all"] = sum(extra_requirements.values(), [])
extra_requirements["oeuf-jambon-fromage"] = extra_requirements["all"]

setup(
    name="parsec-cloud",
    version=__version__,
    description="Secure cloud framework",
    long_description=readme + "\n\n" + history,
    author="Scille SAS",
    author_email="contact@scille.fr",
    url="https://github.com/Scille/parsec-cloud",
    packages=find_packages(),
    package_dir={"parsec": "parsec"},
    setup_requires=[PYQT_DEP],  # To generate resources bundle
    install_requires=requirements,
    extras_require=extra_requirements,
    cmdclass={
        "generate_pyqt_resources_bundle": GeneratePyQtResourcesBundle,
        "generate_pyqt_forms": GeneratePyQtForms,
        "generate_pyqt_translations": GeneratePyQtTranslations,
        "generate_pyqt": build_py_with_pyqt,
        "build_py": build_py_with_pyqt,
    },
    entry_points={"console_scripts": ["parsec = parsec.cli:cli"]},
    options={"build_exe": build_exe_options},
    executables=[Executable("parsec/cli.py", targetName="parsec")],
    license="AGPLv3",
    zip_safe=False,
    keywords="parsec",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
    ],
    test_suite="tests",
    tests_require=test_requirements,
)
