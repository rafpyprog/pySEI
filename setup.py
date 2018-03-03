import os
import re
from setuptools import setup


def get_version(pkg_name, version_file='__version__.py'):
    here = os.path.abspath(os.path.dirname(__file__))
    version_file = os.path.join(here, pkg_name, version_file)
    version = open(version_file).read()
    version = re.search('[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}', version).group()
    return version


def get_dependencies():
    with open('requirements.txt') as f:
        dependencies = f.readlines()
    return dependencies


pkg_name = 'pysei'
pkg_version = get_version(pkg_name)
pkgs = ['pysei']
install_requires = get_dependencies()

config = dict(
    name=pkg_name,
    version=pkg_version,
    author='Rafael Alves Ribeiro',
    author_email='rafael.alves.ribeiro@gmail.com',
    url='https://github.com/rafpyprog/pySEI.git',
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=pkgs,
    license='License :: OSI Approved :: MIT License',
    install_requires=install_requires,
    setup_requires=['pytest-runner'],
    tests_require=[
        'pytest', 'pytest-cov', 'requests',
    ],
)

setup(**config)
