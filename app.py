#!/usr/bin/env python3
import os
import json

import aws_cdk as cdk

from mesh_vpccdk.mesh_vpc_cdk_stack import MeshVpcCDKStack


app = cdk.App()
MeshVpcCDKStack(app, "MeshVpcCDKStack")

app.synth()

## Post process JSON to remove CDK specific stuff, since we're vending this as a
# CloudFormation template:
with open("cdk.out/MeshVpcCDKStack.template.json", "r") as f:
    template_json = json.load(f)
    del template_json["Rules"]

    router_object = [
        obj
        for name, obj in template_json["Resources"].items()
        if name.startswith("VPNRouterInstance") and obj["Type"] == "AWS::EC2::Instance"
    ][0]

    router_object["Properties"][
        "ImageId"
    ] = "{{resolve:ssm:/aws/service/canonical/ubuntu/server/focal/stable/current/arm64/hvm/ebs-gp2/ami-id}}"

    params_to_remove = ["BootstrapVersion"]
    for parameter in template_json["Parameters"]:
        if parameter.startswith("SsmParameter"):
            params_to_remove.append(parameter)

    for parameter in params_to_remove:
        del template_json["Parameters"][parameter]

    with open("cdk.out/MeshVpcCDKStack.clean.template.json", "w") as of:
        json.dump(template_json, of, indent=2)
