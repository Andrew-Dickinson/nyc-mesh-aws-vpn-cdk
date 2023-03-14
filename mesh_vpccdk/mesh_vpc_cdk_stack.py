from collections import ChainMap

import aws_cdk as cdk

from constructs import Construct

from mesh_vpccdk.constructs import CoreVPCInfrastructure, VPNRouterInstance
from mesh_vpccdk.util import get_user_data

SN3_VPN_SERVER_IP = "199.170.132.4"
SN3_VPN_SERVER_PUBLIC_KEY = "FRjRFt/XnSa1tDqnH5g3Y6CikIar/bq3uwUh5vfU/UI="

CIDR_REGEX = r"^([0-9]{1,3}\.){3}[0-9]{1,3}(\/([0-9]|[1-2][0-9]|3[0-2]))?$"
IPV4_ADDR_REGEX = r"^([0-9]{1,3}\.){3}[0-9]{1,3}$"
PORT_NUMBER_REGEX = r"^[0-9]{1,5}$"
WG_KEY_REGEX = r"^([A-z0-9\/\+]{43}\=)$"
SUFFIX_TO_INDICATE_OPTIONAL = r"|^$"

MAX_WG_TUNNELS = 3


class MeshVpcCDKStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        params = {
            "MeshCIDR": cdk.CfnParameter(
                self,
                id="MeshCIDR",
                allowed_pattern=CIDR_REGEX,
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
        }

        wireguard_params = [
            {
                "ServerIP": cdk.CfnParameter(
                    self,
                    id=f"WireguardServer{i + 1}IP",
                    type="String",
                    description="The public IP address of the mesh-side wireguard endpoint to connect to",
                    default=SN3_VPN_SERVER_IP if i == 0 else None,
                    allowed_pattern=IPV4_ADDR_REGEX
                    if i == 0
                    else IPV4_ADDR_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                ),
                "ServerPort": cdk.CfnParameter(
                    self,
                    id=f"WireguardServer{i + 1}Port",
                    type="String",
                    description="The port that the IP specified above is listening for our connection on",
                    allowed_pattern=PORT_NUMBER_REGEX
                    if i == 0
                    else PORT_NUMBER_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                ),
                "ServerPublicKey": cdk.CfnParameter(
                    self,
                    id=f"WireguardServer{i + 1}PublicKey",
                    type="String",
                    description="The public key of the mesh-side wireguard server",
                    default=SN3_VPN_SERVER_PUBLIC_KEY if i == 0 else None,
                    allowed_pattern=WG_KEY_REGEX
                    if i == 0
                    else WG_KEY_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                ),
                "p2pIPAddressMeshSide": cdk.CfnParameter(
                    self,
                    id=f"p2pIPAddress{i + 1}MeshSide",
                    type="String",
                    description="The adjacent router IP for the router instance to use as its OSPF "
                    "neighbor. This should probably be the mesh-side of the P2P CIDR for your tunnel",
                    allowed_pattern=IPV4_ADDR_REGEX
                    if i == 0
                    else IPV4_ADDR_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                ),
                "p2pIPAddressAWSSide": cdk.CfnParameter(
                    self,
                    id=f"p2pIPAddress{i + 1}AWSSide",
                    type="String",
                    description="The AWS-side IP of the P2P CIDR for your tunnel "
                    "(also used as the router's OSPF identity)"
                    if i == 0
                    else "The AWS-side IP of the P2P CIDR for your tunnel",
                    allowed_pattern=IPV4_ADDR_REGEX
                    if i == 0
                    else IPV4_ADDR_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                ),
                "LinkOSPFCost": cdk.CfnParameter(
                    self,
                    id=f"LinkOSFPCost{i+1}",
                    type="String",
                    default="10" if i == 0 else None,
                    allowed_pattern=PORT_NUMBER_REGEX
                    if i == 0
                    else PORT_NUMBER_REGEX + SUFFIX_TO_INDICATE_OPTIONAL,
                    description="The OSPF cost to use for this WG tunnel",
                ),
            }
            for i in range(MAX_WG_TUNNELS)
        ]

        wg_parameter_groups = [
            {
                "Label": {
                    "default": f"WireGuard Connection {i + 1} Details{' (Optional)' if i > 0 else ''}"
                },
                "Parameters": [
                    f"WireguardServer{i + 1}IP",
                    f"WireguardServer{i + 1}Port",
                    f"WireguardServer{i + 1}PublicKey",
                    f"p2pIPAddress{i + 1}MeshSide",
                    f"p2pIPAddress{i + 1}AWSSide",
                    f"LinkOSFPCost{i + 1}",
                ],
            }
            for i in range(MAX_WG_TUNNELS)
        ]

        wg_parameter_labels = dict(
            ChainMap(
                *[
                    {
                        f"p2pIPAddress{i + 1}MeshSide": {
                            "default": f"WG tunnel {i + 1} P2P Address (Mesh Side)"
                        },
                        f"p2pIPAddress{i + 1}AWSSide": {
                            "default": f"WG tunnel {i + 1} P2P Address (AWS Side)"
                        },
                        f"WireguardServer{i + 1}IP": {
                            "default": f"Mesh WireGuard server {i + 1} Public IP"
                        },
                        f"WireguardServer{i + 1}Port": {
                            "default": f"Mesh WireGuard server {i + 1} port"
                        },
                        f"WireguardServer{i + 1}PublicKey": {
                            "default": f"Mesh WireGuard Server {i + 1} Public Key"
                        },
                        f"LinkOSFPCost{i + 1}": {
                            "default": f"WG Tunnel {i + 1} OSPF Cost"
                        },
                    }
                    for i in range(MAX_WG_TUNNELS)
                ]
            )
        )

        self.template_options.metadata = {
            "AWS::CloudFormation::Interface": {
                "ParameterGroups": [
                    {
                        "Label": {"default": "IP Addresses"},
                        "Parameters": [
                            "MeshCIDR",
                        ],
                    },
                    *wg_parameter_groups,
                    {
                        "Label": {"default": "Router Instance Config"},
                        "Parameters": [
                            "RouterInstanceSSHPublicKeyMaterial",
                        ],
                    },
                ],
                "ParameterLabels": {
                    "MeshCIDR": {"default": "Mesh CIDR range to use for VPC"},
                    **wg_parameter_labels,
                    "RouterInstanceSSHPublicKeyMaterial": {
                        "default": "Public Key for SSH Access to the Router Instance"
                    },
                },
            }
        }
        wg_tunnel_conditions = [
            cdk.CfnCondition(
                self,
                f"WGServer{i + 1}Provided",
                expression=cdk.Fn.condition_and(
                    *[
                        cdk.Fn.condition_not(
                            cdk.Fn.condition_equals(
                                wireguard_params[i][param].value_as_string,
                                "",
                            )
                        )
                        for param in wireguard_params[i].keys()
                    ]
                ),
            )
            for i in range(MAX_WG_TUNNELS)
        ]

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

        wg_param_substitutions = dict(
            ChainMap(
                *[
                    {
                        f"P2P_IP_Address_{i + 1}_AWS_Side": wireguard_params[i][
                            "p2pIPAddressAWSSide"
                        ].value_as_string,
                        f"P2P_IP_Address_{i + 1}_Mesh_Side": wireguard_params[i][
                            "p2pIPAddressMeshSide"
                        ].value_as_string,
                        f"WireGuardServer{i + 1}PublicKey": wireguard_params[i][
                            "ServerPublicKey"
                        ].value_as_string,
                        f"WireGuardServer{i + 1}PublicIP": wireguard_params[i][
                            "ServerIP"
                        ].value_as_string,
                        f"WireGuardServer{i + 1}Port": wireguard_params[i][
                            "ServerPort"
                        ].value_as_string,
                        f"LinkOSPFCost{i + 1}": wireguard_params[i][
                            "LinkOSPFCost"
                        ].value_as_string,
                    }
                    for i in range(MAX_WG_TUNNELS)
                ]
            )
        )

        wg_condition_substitutions = {
            f"CommentIfWGServer{i + 1}NotProvided": cdk.Fn.condition_if(
                wg_tunnel_conditions[i].logical_id, "", "#"
            ).to_string()
            for i in range(1, MAX_WG_TUNNELS)
        }

        user_data = cdk.Fn.base64(
            cdk.Fn.sub(
                get_user_data(MAX_WG_TUNNELS),
                {
                    "AWSRegion": cdk.Aws.REGION,
                    "VPCCIDR": params["MeshCIDR"].value_as_string,
                    **wg_param_substitutions,
                    **wg_condition_substitutions,
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
            [
                wireguard_params[i]["ServerIP"].value_as_string
                for i in range(MAX_WG_TUNNELS)
            ],
            [wg_tunnel_conditions[i] for i in range(MAX_WG_TUNNELS)],
        )
