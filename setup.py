# -*- coding: utf-8 -*-
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.4@@
import os
import log_offload

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def path(p):
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), p)


requirements = []
tests_requirements = requirements + []

setup(name='log_offload',
      version=log_offload.__version__,
      description='',
      classifiers=[
          'Programming Language :: Python :: 2.7',
          'Environment :: Web Environment',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries',
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
      ],
      keywords=['appengine'],
      author='GIG Technology',
      author_email='apps@greenitglobe.com',
      url='https://github.com/rogerthat-platform/log-offload',
      license='Apache 2.0',
      packages=['log_offload'],
      install_requires=requirements,
      tests_require=tests_requirements,
      )
