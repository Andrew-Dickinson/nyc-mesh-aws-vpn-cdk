import base64
import os

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
)


def get_user_data():
    directory = os.path.join(os.path.dirname(__file__))
    file_path = os.path.join(directory, "router_instance_cloud_init.yml")

    with open(file_path, "r") as f:
        user_data_str = f.read()

    multipart_user_data = ec2.MultipartUserData()
    multipart_user_data.add_part(
        ec2.MultipartBody.from_raw_body(
            content_type='text/cloud-config; charset="us-ascii"',
            body=user_data_str,
        )
    )

    return multipart_user_data.render()


def name_tag(name):
    return cdk.CfnTag(key="Name", value=name)
