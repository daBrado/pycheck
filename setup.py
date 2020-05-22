from distutils.core import setup

setup(
    name="pycheck",
    version="0.0.1",
    description="Check Python code",
    packages=["pycheck"],
    install_requires=[
        "black",
        "flake8",
        "flake8-bugbear",
        "inotify_simple",
        "isort",
        "mypy",
        "pytest",
    ],
)
