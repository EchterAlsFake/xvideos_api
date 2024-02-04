from setuptools import setup, find_packages

setup(
    name="xvideos_api",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "requests", "bs4", "lxml", "ffmpeg-progress-yield"
    ],
    entry_points={
        'console_scripts': [
            # If you want to create any executable scripts
        ],
    },
    author="Johannes Habel",
    author_email="EchterAlsFake@proton.me",
    description="A Python API for the Porn Site xvideos.com",
    long_description=open('/home/asuna/PycharmProjects/xvideos_api/README.md').read(),
    long_description_content_type='text/markdown',
    license="LGPLv3",
    url="https://github.com/EchterAlsFake/xvideos_api",
    classifiers=[
        # Classifiers help users find your project on PyPI
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Programming Language :: Python",
    ],
)
