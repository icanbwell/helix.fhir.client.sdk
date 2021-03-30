# python-package-template
Cookiecutter template for creating a new Python Package

# Usage
Install cookiecutter:

`pip install -U cookiecutter`

Run cookiecutter:

`cookiecutter -f https://github.com/imranq2/python-package-template.git -o ../`

This will ask you for the parameters.

Alternatively, create a cookiecutter.json
{
    "directory_name": "Hello",
    "package_name": "Howdy",
    "author": "Julie",
    "author_email": "foo@email.com",
    "package_description": "description",
    "package_github_url": "url",

}

After generation is complete, run `make init` to set up your environment.
