import aws_cdk as core
import aws_cdk.assertions as assertions

from mesh_vpccdk.mesh_vpccdk_stack import MeshVpccdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in mesh_vpccdk/mesh_vpccdk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MeshVpccdkStack(app, "mesh-vpccdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
