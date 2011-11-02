import os
from setuptools import setup, find_packages

from django_table_export_import import VERSION


f = open(os.path.join(os.path.dirname(__file__), 'README'))
readme = f.read()
f.close()

setup(
    name='django-table-export-import ',
    version=".".join(map(str, VERSION)),
    description='django-table-export-import is a reusable Django application for export and import model data.',
    long_description=readme,
    author='Sergey Klimov',
    author_email='sergey.v.klimov@gmail.com',
    url='http://github.com/darvin/django-table-export-import',
    packages=find_packages(),
    install_requires = [
        'django',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
)
