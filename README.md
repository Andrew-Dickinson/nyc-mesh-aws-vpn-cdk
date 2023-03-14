
# Mesh VPC CDK Template

This repository uses AWS CDK code to generate a CloudFormation template which
can be used to create an AWS VPC which connects to [NYC Mesh](https://nycmesh.net) via a WireGuard
VPN connection.

## Cost

This template itself, which includes a small `t4g.nano` instance costs approximately $3.76 per month 
to run idle in the `us-east-1` (N. Virginia) region. This can be reduced to around $2.47 per month
by making a 1-year commitment and paying upfront. These costs will be higher (potentially much 
higher) if you launch additional resources into this VPC. These numbers also don't include data 
transfer costs ($0/GB sent from the mesh to AWS, $0.09/GB sent from AWS to the mesh).

More pricing information is available on the [AWS website](https://aws.amazon.com/ec2/pricing/on-demand/)

## Usage Instructions

Open the pre-built CloudFormation template by using this [magic link](https://nycmesh-cloudformation-templates.s3.amazonaws.com/MeshVpcCDKStack/cdk.out/MeshVpcCDKStack.clean.template.json).

Fill in the parameters as requested, this will require setting up a new wireguard connection on the 
NYCMesh WireGuard Server, and allocating static IP ranges for the VPC itself and the VPN tunnel.

Once the stack finishes deploying, look for a new parameter in the 
[systems manager paramter store](https://console.aws.amazon.com/systems-manager/parameters) called
`/MeshVPC/RouterInstancePublicKey`. Use the value of this parameter as the public key on the Mesh
Wireguard server.

Finally, you should be able to launch EC2 instances into the new VPC and directly connect to the mesh
with no special configuration. Launch a new instance in the VPC and try to ping the core router at
SN3
```sh
ping 10.69.7.13
```
to confirm the connection.

## De-provisioning

The stack enables termination protection on the Router EC2 instance. To de-provision the resources
created by this template, first disable termination protection on the router instance according to
[AWS's instructions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html#Using_ChangingDisableAPITermination), 
then [delete the stack from the CloudFormation console](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-delete-stack.html).

If you create additional resources in the VPC, such as EC2 instances, those resources will also 
need to be terminated before the stack can be succesfully deleted.

## Building the CloudFormation Template from Source

Clone the repo with:
```bash
git clone https://github.com/Andrew-Dickinson/nycmesh-vpc-cdk
```

Setup and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.
```
cdk synth
```

The `app.py` script does some cleanup to make the stack nicer for direct deployment outside the CDK 
CLI. This means end users can just directly use the generated template and don't have to 
`cdk bootstrap`, etc. The cleaned template is written to 
`cdk.out/MeshVpcCDKStack.clean.template.json`. You can examine it with:
```sh
less cdk.out/MeshVpcCDKStack.clean.template.json
```

