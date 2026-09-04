import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'camera_streaming'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Miguel Angel Gonzalez Rodriguez',
    maintainer_email='miguel_gonzalezr@ieee.org',
    description='Launches surface and underwater USB camera feeds as ROS 2 image topics and republishes them over HTTP via web_video_server on port 8000.',
    license='BSD 3-Clause',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'camera_node = camera_streaming.camera_node:main',
            'http_video_server = camera_streaming.http_video_server:main',
        ],
    },
)
