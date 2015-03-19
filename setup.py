#!/usr/bin/env python

# Imports
import os
from setuptools import setup


# Read function
def safe_read(fname):
    try:
        return open(os.path.join(os.path.dirname(__file__), fname)).read()
    except IOError:
        return ""


# Setup
setup(name="python-rohdescope",
      version="0.4.2",
      description="Library for remote communication with the R&S oscilloscopes.",
      author="Vincent Michel; Paul Bell",
      author_email="vincent.michel@maxlab.lu.se; paul.bell@maxlab.lu.se",
      license="GPLv3",
      url="http://www.maxlab.lu.se",
      long_description=safe_read("README.md"),
      packages=["rohdescope"],
      )
