from distutils.core import setup

setup(
    name='ebook-isbn',
    version='0.1 alpha',
    packages=['app', 'bookinfo'],
    url='https://github.com/EugenePig',
    license='Apache License, Version 2.0',
    author='Eugene Su',
    author_email='',
    description='An eBook tool to extract ISBN or Metadata form eBook and rename them using ISBN database and Metadata',
    install_requires=['isbnlib>=3.5.6']
)
