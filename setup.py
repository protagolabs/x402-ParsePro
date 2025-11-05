from setuptools import setup, find_packages

setup(
    name="x402-netmind-parsepro",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastmcp",
        "x402",
        "cdp-sdk"
    ],
    entry_points={
        "console_scripts": [
            "x402-parsepro=x402_parsepro.app:main",
        ],
    },
    python_requires=">=3.12",
)
