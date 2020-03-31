from setuptools import setup, find_packages

setup(
    name="pymada",
    version="0.1.0",
    url="https://github.com/nhoss2/pymada",
    license="",

    author="Nafis Hossain",
    author_email="nafis@labs.im",

    description="pymada",

    packages=find_packages(),

    install_requires=[
        'apache-libcloud',
        'django',
        'djangorestframework',
        'requests',
        'gunicorn',
        'flask',
        'kubernetes',
        'cryptography',
        'click',
        'pyyaml',
        'tabulate',
        'pillow'
    ],

    entry_points={
        'console_scripts': ['pymada=pymada.cli:cli']
    },

    classifiers=[],
)
