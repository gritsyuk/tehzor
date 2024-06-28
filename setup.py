from setuptools import setup, find_packages


with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()
  

setup(
  name='tehzor',
  version='0.0.10',
  author='Igor Gritsyuk',
  author_email='gritsyuk.igor@gmail.com',
  description='A Python API wrapper for Tehzor API',
  download_url='https://github.com/gritsyuk/tehzor/archive/refs/heads/develop.zip',
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='https://github.com/gritsyuk/tehzor',
  packages=find_packages(include=['tehzor', 'tehzor.*']),
  install_requires=['aiohttp>=3.9.3', 'pydantic[email]>=2.6.4'],
  classifiers=[
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent'
  ],
  keywords='tehzor api tehzorapi construction supervision operation inspections constarctionsite building management',
  project_urls={
    'GitHub': 'https://github.com/gritsyuk/tehzor'
  },
  python_requires='>=3.6'
)
