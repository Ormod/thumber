from setuptools import setup, find_packages
from thumber import __version__

setup(
    name="thumber",
    version=__version__,
    zip_safe = False,
    packages = find_packages(),
    install_requires = [],
    extras_require = {},
    dependency_links = [],
    package_data = {},
    entry_points = {'console_scripts': ["thumber = thumber.thumber:main"]}
    )
