import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ssm as ssm,
)
from constructs import Construct

from mesh_vpccdk.constants import MESH_CIDRS
from mesh_vpccdk.util import name_tag, get_user_data


class CoreVPCInfrastructure(Construct):
    def __init__(self, scope, id, vpc_cidr):
        super().__init__(scope, id)

        self.cfn_vpc = ec2.CfnVPC(
            self,
            "MeshVPC",
            cidr_block=vpc_cidr,
            tags=[name_tag("MeshVPC")],
        )

        self.cfn_subnet = ec2.CfnSubnet(
            self,
            "MeshSubnet",
            vpc_id=self.cfn_vpc.attr_vpc_id,
            cidr_block=vpc_cidr,
            availability_zone_id="use1-az1",
            map_public_ip_on_launch=True,
            tags=[name_tag("MeshSubnet")],
        )

        self.cfn_route_table = ec2.CfnRouteTable(
            self,
            "MeshRouteTable",
            vpc_id=self.cfn_vpc.attr_vpc_id,
            tags=[name_tag("MeshVPCRouteTable")],
        )
        ec2.CfnSubnetRouteTableAssociation(
            self,
            "MeshRouteTableAttachment",
            route_table_id=self.cfn_route_table.attr_route_table_id,
            subnet_id=self.cfn_subnet.attr_subnet_id,
        )

        self.igw = ec2.CfnInternetGateway(self, "MeshIGW", tags=[name_tag("MeshIGW")])
        ec2.CfnVPCGatewayAttachment(
            self,
            "MeshIGWAttachment",
            vpc_id=self.cfn_vpc.attr_vpc_id,
            internet_gateway_id=self.igw.attr_internet_gateway_id,
        )
        internet_route = ec2.CfnRoute(
            self,
            "InternetRoute",
            route_table_id=self.cfn_route_table.attr_route_table_id,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=self.igw.attr_internet_gateway_id,
        )

        self.router_security_group = ec2.CfnSecurityGroup(
            self,
            "AllowFromMeshAndToInternet",
            vpc_id=self.cfn_vpc.attr_vpc_id,
            group_name="AllowFromMeshAndToInternet",
            group_description="Allow all connections from 10.0.0.0/8 (plus other mesh CIDRS) "
            "and all outbound to 0.0.0.0/0",
            security_group_egress=[
                ec2.CfnSecurityGroup.EgressProperty(
                    description="Allow any outbound traffic flows",
                    ip_protocol="-1",  # All traffic
                    cidr_ip="0.0.0.0/0",
                )
            ],
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    cidr_ip=cidr,
                    ip_protocol="-1",
                    description="Allow all traffic from mesh",
                )
                for cidr in MESH_CIDRS
            ],
        )

    def add_mesh_routes(self, router_instance_id, vpn_endpoint_addr):
        # Add routes to the mesh
        for i, cidr in enumerate(MESH_CIDRS):
            ec2.CfnRoute(
                self,
                f"Mesh CIDR {i}",
                route_table_id=self.cfn_route_table.attr_route_table_id,
                destination_cidr_block=cidr,
                instance_id=router_instance_id,
            )

        # Make sure we have a more specific route to the VPN server so its
        # traffic goes directly out via the IGW
        ec2.CfnRoute(
            self,
            "Mesh VPN Endpoint Goes via IGW",
            route_table_id=self.cfn_route_table.attr_route_table_id,
            destination_cidr_block=cdk.Fn.join("", [vpn_endpoint_addr, "/32"]),
            gateway_id=self.igw.attr_internet_gateway_id,
        )


class VPNRouterInstance(Construct):
    def __init__(
        self,
        scope,
        id,
        public_key_material,
        public_key_provided_condition,
        cfn_subnet,
        cfn_security_group,
        user_data,
    ):
        super().__init__(scope, id)

        router_iam_role = iam.Role(
            self,
            "EC2-SSM-Only",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Role for EC2 instances to call AWS Systems Manager in order to allow "
            "keyless SSH access",
            role_name="EC2-SSM-Only-Role",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
            inline_policies={
                "InlineAccessToPutOutputInSSMParameterStore": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["ssm:PutParameter"],
                            resources=[
                                cdk.Fn.join(
                                    ":",
                                    [
                                        "arn:aws:ssm",
                                        cdk.Aws.REGION,
                                        cdk.Aws.ACCOUNT_ID,
                                        "parameter/MeshVPC/*",
                                    ],
                                )
                            ],
                        )
                    ],
                )
            },
        )

        key_pair = ec2.CfnKeyPair(
            self,
            "MeshVPNRouterKey",
            key_name="MeshVPNRouterKey",
            public_key_material=public_key_material,
        )
        key_pair.cfn_options.condition = public_key_provided_condition

        self.instance = ec2.CfnInstance(
            self,
            "RouterInstance",
            tags=[name_tag("Mesh Router")],
            instance_type="t4g.nano",
            image_id=ssm.StringParameter.value_for_string_parameter(
                self,
                "/aws/service/canonical/ubuntu/server/focal/stable/current/arm64/hvm/ebs-gp2/ami-id",
            ),
            iam_instance_profile=iam.CfnInstanceProfile(
                self,
                "RouterRoleInstanceProfile",
                roles=[router_iam_role.role_name],
            ).ref,
            source_dest_check=False,
            security_group_ids=[cfn_security_group.attr_group_id],
            disable_api_termination=True,
            subnet_id=cfn_subnet.attr_subnet_id,
            user_data=user_data,
        )

        # Set keypair
        self.instance.add_property_override(
            "KeyName",
            cdk.Fn.condition_if(
                public_key_provided_condition.logical_id,
                key_pair.ref,
                "AWS::NoValue",
            ),
        )
