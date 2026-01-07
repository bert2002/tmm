from setuptools import setup, find_packages

setup(
    name="tmm-monitor",
    version="1.0.2",
    description="Tendermint Metrics Monitor - A TUI for monitoring blockchain metrics",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/pharos-network/tmm",
    author="",
    author_email="",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={
        "tmm": ["chains/*.json"],
    },
    python_requires=">=3.9",
    install_requires=[
        "textual==0.79.1",
        "plotext==5.2.8"
    ],
    entry_points={
        "console_scripts": [
            "tmm=tmm.main:main",
        ],
    },
)
