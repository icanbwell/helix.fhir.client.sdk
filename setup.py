# noinspection Mypy

from os import getcwd, path

from setuptools import find_packages, setup

# from https://packaging.python.org/tutorials/packaging-projects/

# noinspection SpellCheckingInspection
package_name = "helix.fhir.client.sdk"

with open("README.md") as fh:
    long_description = fh.read()

try:
    with open(path.join(getcwd(), "VERSION")) as version_file:
        version = version_file.read().strip()
except OSError:
    raise


# classifiers list is here: https://pypi.org/classifiers/

# create the package setup
setup(
    name=package_name,
    version=version,
    author="Imran Qureshi",
    author_email="imran@icanbwell.com",
    description="helix.fhir.client.sdk",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/icanbwell/helix.fhir.client.sdk",
    packages=find_packages(exclude=["**/test", "**/test/**"]),
    install_requires=[
        "furl",
        "requests",
        "urllib3",
        "chardet",
        "aiohttp",
        "async-timeout>=4.0.3",
        "python-dateutil",
        "compressedfhir>=1.0.3",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    dependency_links=[],
    include_package_data=True,
    zip_safe=False,
    package_data={"helix_fhir_client_sdk": ["py.typed"]},
)
