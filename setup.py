from setuptools import setup, find_packages


def readme():
  with open('README.md', 'r') as f:
    return f.read()
  

setup(
  name='tehzor',
  version='0.0.1',
  author='Igor Gritsyuk',
  author_email='gritsyuk.igor@gmail.com',
  description='A Python API wrapper for Tehzor API',
  download_url='https://github.com/gritsyuk/tehzor_api/archive/refs/heads/develop.zip',
  long_description=readme(),
  long_description_content_type='text/markdown',
  url='https://github.com/gritsyuk/tehzor_api',
  packages=find_packages(),
  install_requires=['requests>=2.25.1'],
  classifiers=[
    'Programming Language :: Python :: 3.11',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent'
  ],
  keywords='tehzor api tehzorapi construction supervision operation inspections constarctionsite building management',
  project_urls={
    'GitHub': 'https://github.com/gritsyuk/tehzor_api'
  },
  python_requires='>=3.6'
)
