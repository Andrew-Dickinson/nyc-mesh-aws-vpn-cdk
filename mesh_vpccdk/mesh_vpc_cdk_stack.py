import aws_cdk as cdk

from constructs import Construct

from mesh_vpccdk.constructs import CoreVPCInfrastructure, VPNRouterInstance
from mesh_vpccdk.util import get_user_data


class MeshVpcCDKStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        params = {
            "MeshCIDR": cdk.CfnParameter(
                self,
                id="MeshCIDR",
                allowed_pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}(\/([0-9]|[1-2][0-9]|3[0-2]))?$",
                type="String",
                description="Enter the mesh IP-space CIDR to use to create the VPC. This "
                "must be a real mesh IP CIDR that is allocated exclusively for"
                " this purpose. Minimum size is /28, but using at least a /27 is recommended",
            ),
            "RouterInstanceSSHPublicKeyMaterial": cdk.CfnParameter(
                self,
                id="RouterInstanceSSHPublicKeyMaterial",
                type="String",
                description="(optional) A public key which the router EC2 instance will trust for "
                "SSH connections, must be in OpenSSH public key format. If not provided, the "
                "router will not be accessible using vanilla SSH (only AWS Systems Manger). Note: "
                "even if a key is provided here, you will still need to create a new security group"
                " which allows port 22 access and associate it with the router instance in order"
                "to actually connect over vanilla SSH from a non-mesh IP address.",
                default="",
            ),
            "WireguardServerIP": cdk.CfnParameter(
                self,
                id="WireguardServerIP",
                type="String",
                description="The public IP address of the mesh-side wireguard endpoint to connect to",
                default="199.170.132.4",
                allowed_pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
            ),
            "WireguardServerPort": cdk.CfnParameter(
                self,
                id="WireguardServerPort",
                type="String",
                description="The port that the IP specified above is listening for our connection on",
                allowed_pattern=r"^[0-9]{1,5}$",
            ),
            "WireguardServerPublicKey": cdk.CfnParameter(
                self,
                id="WireguardServerPublicKey",
                type="String",
                description="The public key of the mesh-side wireguard server",
                default="FRjRFt/XnSa1tDqnH5g3Y6CikIar/bq3uwUh5vfU/UI=",
                allowed_pattern=r"^([A-z0-9\/\+]{43}\=)$",
            ),
            "p2pIPAddressMeshSide": cdk.CfnParameter(
                self,
                id="p2pIPAddressMeshSide",
                type="String",
                description="The adjacent router IP for the router instance to use as its OSPF "
                "neighbor. This should probably be the mesh-side of the P2P CIDR for your tunnel",
                allowed_pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
            ),
            "p2pIPAddressAWSSide": cdk.CfnParameter(
                self,
                id="p2pIPAddressAWSSide",
                type="String",
                description="The IP for the router instance to use as its OSPF identity. "
                "This should probably be the AWS-side IP of the P2P CIDR for your tunnel",
                allowed_pattern=r"^([0-9]{1,3}\.){3}[0-9]{1,3}$",
            ),
        }

        self.template_options.metadata = {
            "AWS::CloudFormation::Interface": {
                "ParameterGroups": [
                    {
                        "Label": {"default": "IP Addresses"},
                        "Parameters": [
                            "MeshCIDR",
                            "p2pIPAddressMeshSide",
                            "p2pIPAddressAWSSide",
                        ],
                    },
                    {
                        "Label": {"default": "WireGuard Connection Details"},
                        "Parameters": [
                            "WireguardServerIP",
                            "WireguardServerPort",
                            "WireguardServerPublicKey",
                        ],
                    },
                    {
                        "Label": {"default": "Router Instance Config"},
                        "Parameters": [
                            "RouterInstanceSSHPublicKeyMaterial",
                        ],
                    },
                ],
                "ParameterLabels": {
                    "MeshCIDR": {"default": "Mesh CIDR range to use for VPC"},
                    "p2pIPAddressMeshSide": {
                        "default": "WG tunnel P2P Address (Mesh Side)"
                    },
                    "p2pIPAddressAWSSide": {
                        "default": "WG tunnel P2P Address (AWS Side)"
                    },
                    "WireguardServerIP": {"default": "Mesh WireGuard server Public IP"},
                    "WireguardServerPort": {"default": "Mesh WireGuard server port"},
                    "WireguardServerPublicKey": {
                        "default": "Mesh WireGuard Server Public Key"
                    },
                    "RouterInstanceSSHPublicKeyMaterial": {
                        "default": "Public Key for SSH Access to the Router Instance"
                    },
                },
            }
        }

        conditions = {
            "PublicKeyProvided": cdk.CfnCondition(
                self,
                "PublicKeyProvided",
                expression=cdk.Fn.condition_not(
                    cdk.Fn.condition_equals(
                        params["RouterInstanceSSHPublicKeyMaterial"].value_as_string, ""
                    )
                ),
            ),
        }

        core_vpc_infra = CoreVPCInfrastructure(
            self,
            "CoreVPCInfrastructure",
            vpc_cidr=params["MeshCIDR"].value_as_string,
        )

        user_data = cdk.Fn.base64(
            cdk.Fn.sub(
                get_user_data(),
                {
                    "AWSRegion": cdk.Aws.REGION,
                    "VPCCIDR": params["MeshCIDR"].value_as_string,
                    "P2P_IP_Address_AWS_Side": params[
                        "p2pIPAddressAWSSide"
                    ].value_as_string,
                    "P2P_IP_Address_Mesh_Side": params[
                        "p2pIPAddressMeshSide"
                    ].value_as_string,
                    "WireGuardServerPublicKey": params[
                        "WireguardServerPublicKey"
                    ].value_as_string,
                    "WireGuardServerPublicIP": params[
                        "WireguardServerIP"
                    ].value_as_string,
                    "WireGuardServerPort": params[
                        "WireguardServerPort"
                    ].value_as_string,
                },
            )
        )

        vpn_router_instance = VPNRouterInstance(
            self,
            "VPNRouterInstance",
            cfn_subnet=core_vpc_infra.cfn_subnet,
            cfn_security_group=core_vpc_infra.router_security_group,
            public_key_material=params[
                "RouterInstanceSSHPublicKeyMaterial"
            ].value_as_string,
            public_key_provided_condition=conditions["PublicKeyProvided"],
            user_data=user_data,
        )

        core_vpc_infra.add_mesh_routes(
            vpn_router_instance.instance.ref,
            params["WireguardServerIP"].value_as_string,
        )
