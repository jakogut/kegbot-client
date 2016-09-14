from setuptools import setup, find_packages

setup(
    name='kegbot-client',
    version='0.1',
    url='https://github.com/nrssystems/kegbot-client',
    author='Joseph Kogut',
    author_email='joseph.kogut@gmail.com',
    install_requires=[
        'kegboard >= v1.2.0',
        'kegbot-api >= v1.2.0',
        'kegbot-pycore >= 1.3.0',
        'kegbot-pyutil >= v0.2',
        'kivy >= 1.10.1',
    ],
    packages=find_packages(),
)
