import setuptools
import versioneer

setup(
    name='anaconda-project',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    keywords=["conda anaconda project reproducible data science"],
    url='http://github.com/Anaconda-Server/anaconda-project',
    license='BSD 3-Clause',
    author="Anaconda, Inc",
    author_email='info@anaconda.com',
    maintainer='Anaconda, Inc',
    maintainer_email='info@anaconda.com',
    description='Tool for encapsulating, running, and reproducing data science projects',
    long_description=open("README.md").read(),
    zip_safe=False,
    install_requires=[
        'anaconda-client',
        'requests',
        'ruamel_yaml',
        'tornado>=4.2'
    ],
    entry_points={'console_scripts': [
        'anaconda-project = anaconda_project.cli:main',
    ]},
    packages=setuptools.find_packages(exclude=['contrib', 'docs', 'tests*']),
    include_package_data=True,
    classifiers=[
        'Development Status :: 5 - Production/Stable', 'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent', 'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5', 'Programming Language :: Python :: 3.6'
    ])
