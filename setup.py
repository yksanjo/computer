from setuptools import setup, find_packages

setup(
    name="computer",
    version="0.1.0",
    description="GPU Cost Intelligence Platform - See, analyze, and optimize your GPU spend",
    author="Yoshi Kondo",
    author_email="yoshi@example.com",
    url="https://github.com/yksanjo/computer",
    packages=find_packages(),
    install_requires=[
        "boto3>=1.34.0",
        "requests>=2.31.0",
        "httpx>=0.26.0",
        "pandas>=2.1.0",
        "numpy>=1.26.0",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "pydantic>=2.5.0",
        "typer>=0.9.0",
        "rich>=13.7.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "computer=computer.cli:app",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
