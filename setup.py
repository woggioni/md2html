from os.path import join, dirname
from setuptools import setup, find_packages


def read(fname):
    return open(join(dirname(__file__), fname)).read()


config = {
    'name': "md2html",
    'version': "0.2",
    'author': "Walter Oggioni",
    'author_email': "oggioni.walter@gmail.com",
    'description': ("Various development utility scripts"),
    'long_description': '',
    'license': "MIT",
    'keywords': "build",
    'url': "https://github.com/oggio88/md2html",
    'packages': ['md2html'],
    'package_data': {
        'md2html': ['static/*.html', 'static/*.css', 'static/*.js'],
    },
    'include_package_data': True,
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    'install_requires': [
      'markdown'
    ],
    "entry_points": {
        'console_scripts': [
            'md2html=md2html.md2html:main',
        ],
    }
}
setup(**config)
