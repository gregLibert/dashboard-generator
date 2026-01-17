from setuptools import setup, find_packages

setup(
    name="dashboard_engine",
    version="0.0.1",
    description="Moteur de génération de dashboards statiques D3.js",
    packages=find_packages(),
    # C'est ici que la magie opère pour embarquer assets/
    include_package_data=True, 
    # Dépendances minimales
    install_requires=[
        "jinja2"
    ],
    zip_safe=False
)