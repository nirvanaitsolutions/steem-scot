from setuptools import setup

setup(
    name='steem-scot',
    version='0.2.0',
    packages=["scot",],
    url='http://github.com/holgern/steem-scot',
    license='MIT',
    author='Holger Nahrstaedt',
    author_email='holgernahrstaedt@gmx.de',
    description='Distrubtion of Smart Contract Organizational Token steem-engine',
    entry_points={
        'console_scripts': [
            'scot_by_votes=scot.scot:main',
            'scot_by_comment=scot.scot_by_comment:main'
        ],
    },
    install_requires=["beem", "steemengine"]
)
