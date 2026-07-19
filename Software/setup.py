from setuptools import setup, find_packages

setup(
    name="fieldzero",
    version="0.2.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.11",
    install_requires=[
        "numpy>=1.26",
        "scipy>=1.11",
        "matplotlib>=3.8",        # fieldzero.scope, the fallback viewer
        "fastapi>=0.110",         # fieldzero.viewer, the browser viewer
        "uvicorn[standard]>=0.27",
    ],
    extras_require={
        # The NI-DAQmx driver must be installed separately from National Instruments.
        "daq": ["nidaqmx>=1.0"],
        "dev": ["pytest>=8.0", "websockets>=12.0"],
    },
    # The viewer serves these at runtime; without them an installed package
    # starts and then 404s on its own front end.
    package_data={"fieldzero.viewer": ["static/*", "static/vendor/*"]},
    include_package_data=True,
)
