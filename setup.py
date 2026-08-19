from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

with open("caonline/__init__.py") as f:
	version = f.read().split("__version__ = ")[1].strip().strip('"').strip("'")

setup(
	name="caonline",
	version=version,
	description="Complete CA Firm Management System on Frappe/ERPNext v16",
	author="Nabeel Munawar & Co.",
	author_email="info@nabeelmunawar.co",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
