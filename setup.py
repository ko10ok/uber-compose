import os
import pathlib
import shutil

from setuptools import find_packages
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

HERE = pathlib.Path(__file__).parent


class BuildPy(_build_py):
    def run(self):
        super().run()
        docs_source = HERE / 'docs'
        docs_target = pathlib.Path(self.build_lib) / 'uber_compose' / 'docs'
        if docs_source.is_dir():
            shutil.copytree(docs_source, docs_target, dirs_exist_ok=True)


def find_required():
    with open("requirements.txt") as f:
        return f.read().splitlines()


def get_version(filename='uber_compose/version'):
    ext_version = os.environ.get('EXT_VERSION', '')
    return open(filename, "r").read().strip() + ext_version


README = open("README.md").read()
setup(
    name="uber-compose",
    version=get_version(),
    description="docker compose testing env orchestrator",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Yuriy Sagitov",
    author_email="pro100.ko10ok@gmail.com",
    python_requires=">=3.10.0",
    url="https://github.com/ko10ok/uber-compose",
    license="Apache-2.0",
    packages=find_packages(exclude=("tests",)),
    install_requires=find_required(),
    entry_points={},
    cmdclass={'build_py': BuildPy},
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    package_data={
        'uber_compose': ['version'],
    },
)
