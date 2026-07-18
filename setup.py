from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="advanced_commerce",
    version="0.1.0",
    description="Advanced multi-channel headless commerce engine for Frappe, combining channel/attribute patterns from Saleor and saga-style workflow orchestration from Medusa.",
    author="Your Company",
    author_email="dev@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
