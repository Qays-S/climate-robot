import os
from glob import glob

from setuptools import find_packages, setup

package_name = "climate_robot"

setup(
    name=package_name,
    version="0.3.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "rviz"), glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Qays",
    maintainer_email="qshashaa@gmail.com",
    description="Climate-aware patrol robot",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "robot_sim = climate_robot.robot_sim_node:main",
            "navigation = climate_robot.navigation_node:main",
            "mission_manager = climate_robot.mission_manager_node:main",
            "weather = climate_robot.weather_node:main",
            "prediction = climate_robot.prediction_node:main",
        ],
    },
)
