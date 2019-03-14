from setuptools import setup

setup(
    name='steem-scot',
    version='0.1.0',
    packages=["steem-scot",],
    url='http://github.com/holgern/steem-scot',
    license='MIT',
    author='Holger Nahrstaedt',
    author_email='holgernahrstaedt@gmx.de',
    description='Distrubtion of Smart Contract Organizational Token steem-engine',
    entry_points={
        'console_scripts': [
            'steem-scot = steem-scot.scot:main',
        ],
    },
    install_requires=["beem", "steemengine"]
)