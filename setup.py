from setuptools import setup, find_packages


version = '0.1.6'
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='django-form-copy',
    version=version,
    include_package_data=True,
    packages=find_packages(),
    url='https://github.com/DeNRuDi/django-form-copy',
    author='DeNRuDi',
    author_email='denisrudnitskiy0@gmail.com',
    description='Library for quickly copying django objects from one to another project.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=[
        'django',
        'clipboard==0.0.4',
        'python-dateutil==2.8.2',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
