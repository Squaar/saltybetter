from setuptools import setup

setup(
    name='saltybetter',
    version='0.1',
    packages=['saltybetter'],
    # package_dir={'': 'saltybetter'},
    url='https://github.com/Squaar/saltybetter/',
    license='MIT',
    author='Matt Dumford',
    author_email='mdumford99@gmail.com',
    description='',
    entry_points={
        'console_scripts': [
            'saltybetter = saltybetter.__main__:main'
        ]
    }
)
