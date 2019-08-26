from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="pymada",
    version="0.1.0",
    url="-",
    license="",

    author="Nafis Hossain",
    author_email="nafis@labs.im",

    description="flight search stuff",

    packages=find_packages(),

    install_requires=requirements,

    entry_points={
        'console_scripts': ['pymada=pymada.cli:main']
    },

    classifiers=[],
)
