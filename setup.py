from setuptools import setup, find_packages

setup(
    name='apcmagic',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=[
        'apcaccess',
        'Flask',
        'rumps',
        'paramiko',
    ],
    entry_points={
        'console_scripts': [
            'apcmagic=app:main',
        ],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='A Python application for monitoring APC UPS and managing shutdowns.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/ahoy-cmyk/apcmagic',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
    ],
    python_requires='>=3.7',
)
