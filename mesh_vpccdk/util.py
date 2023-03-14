import base64
import os
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString
import io

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
)

THIS_DIRECTORY = os.path.join(os.path.dirname(__file__))
CLOUD_INIT_FILE_PATH = os.path.join(THIS_DIRECTORY, "router_instance_cloud_init.yml")
WG_TUNNEL_FILE_PATH = os.path.join(THIS_DIRECTORY, "wg_tunnel_config.yml")
OSPF_INTERFACE_CONF_FILE_PATH = os.path.join(THIS_DIRECTORY, "ospf_interface.conf")


def get_netplan_write_file_config_for_tunnel(tunnel_num: int) -> dict:
    with open(WG_TUNNEL_FILE_PATH, "r") as f:
        wg_tunnel_yaml_str = f.read()

    wg_tunnel_replaced = wg_tunnel_yaml_str.replace("%i", str(tunnel_num + 1))

    if tunnel_num == 0:
        return {
            "content": LiteralScalarString(wg_tunnel_replaced),
            "path": f"/etc/netplan/71-wireguard-tunnel.yaml",
        }

    conditional_comment_character = f"${{CommentIfWGServer{tunnel_num + 1}NotProvided}}"
    output_str = conditional_comment_character + wg_tunnel_replaced.replace(
        "\n", f"\n{conditional_comment_character}"
    )

    return {
        "content": LiteralScalarString(output_str + "\n"),
        "path": f"/etc/netplan/7{tunnel_num + 1}-wireguard-tunnel.yaml",
    }


def get_bird_write_file_config_for_interface(interface_num: int) -> str:
    with open(OSPF_INTERFACE_CONF_FILE_PATH, "r") as f:
        ospf_interface_conf = f.read()

    conf_with_numbers = ospf_interface_conf.replace("%i", str(interface_num + 1))
    if interface_num == 0:
        return conf_with_numbers

    conditional_comment_character = (
        f"${{CommentIfWGServer{interface_num + 1}NotProvided}}"
    )
    conf_with_optional_comments = (
        conditional_comment_character
        + conf_with_numbers.replace("\n", f"\n{conditional_comment_character}")
    )
    return conf_with_optional_comments


def get_static_routes_yaml(max_wg_tunnels: int) -> dict:
    static_routes_yaml = """network:
  ethernets:
    ens5:
      routes:
"""
    for i in range(0, max_wg_tunnels):
        conditional_comment_character = f"${{CommentIfWGServer{i + 1}NotProvided}}"
        static_routes_yaml += (
            conditional_comment_character if i > 0 else ""
        ) + f"      - to: ${{WireGuardServer{i + 1}PublicIP}}\n"
        static_routes_yaml += (
            conditional_comment_character if i > 0 else ""
        ) + f"        via: XXXX_VPC_ROUTER_ADDRESS_XXXX\n"

    return {
        "content": LiteralScalarString(static_routes_yaml),
        "path": "/etc/netplan/60-static-routes.yaml",
    }


def get_user_data(max_wg_tunnels):
    yaml = YAML()
    with open(CLOUD_INIT_FILE_PATH, "r") as f:
        user_data_yaml = yaml.load(f)

    ospf_interface_confs = [
        get_bird_write_file_config_for_interface(i) for i in range(max_wg_tunnels)
    ]

    user_data_yaml["write_files"][0]["content"] = user_data_yaml["write_files"][0][
        "content"
    ].replace("%INTERFACES_CONFIG_REPLACE_ME%", "\n".join(ospf_interface_confs))

    for i in range(0, max_wg_tunnels):
        user_data_yaml["write_files"].append(
            get_netplan_write_file_config_for_tunnel(i)
        )

    user_data_yaml["write_files"].append(get_static_routes_yaml(max_wg_tunnels))

    yaml_output_buffer = io.StringIO()
    yaml.dump(user_data_yaml, yaml_output_buffer)
    yaml_output_buffer.seek(0)

    multipart_user_data = ec2.MultipartUserData()
    multipart_user_data.add_part(
        ec2.MultipartBody.from_raw_body(
            content_type='text/cloud-config; charset="us-ascii"',
            body=yaml_output_buffer.read(),
        )
    )

    return multipart_user_data.render()


def name_tag(name):
    return cdk.CfnTag(key="Name", value=name)
