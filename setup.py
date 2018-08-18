from setuptools import setup, find_packages


VERSION = "0.0.0.dev0"

REQUIRES = [
    "evdev>=1.0.0,<2.0.0",
    "click>=6.7,<7",
    "PyYAML>=3.13,<4",
]

CLASSIFIERS = [
    "Development Status :: 2 - Pre-Alpha",
    "Environment :: Console",
    # TODO "Environment :: X11 Applications"
    # TODO "Environment :: X11 Applications :: Qt"
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Natural Language :: English",
    "Operating System :: POSIX :: Linux",  # relies on uinput
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3 :: Only",
    "Topic :: Utilities",
]


setup(
    name="frankengamepad",
    version=VERSION,
    python_requires='>=3.6',
    url="https://github.com/danielkinsman/frankengamepad",
    author="Daniel Kinsman",
    author_email="danielkinsman@riseup.net",
    description="Combines several joysticks / gamepads into one",
    license="GPLv3+",
    packages=find_packages(),
    entry_points={"console_scripts": [
        "frankengamepad=frankengamepad.main:main",
    ]},
    install_requires=REQUIRES,
)
