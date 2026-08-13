"""Clean-room backbone → Core ML (spec I10). Embedding head only."""
import subprocess
import torch
import coremltools as ct

# Same guard as convert.py — harmless if the traced graph never hits it.
from coremltools.converters.mil.frontend.torch.torch_op_registry import register_torch_op
from coremltools.converters.mil.frontend.torch.ops import upsample_bilinear2d


@register_torch_op(torch_alias=["_upsample_bicubic2d_aa"], override=True)
def _upsample_bicubic2d_aa(context, node):
    upsample_bilinear2d(context, node)


@register_torch_op(torch_alias=["upsample_bicubic2d"], override=True)
def upsample_bicubic2d(context, node):
    upsample_bilinear2d(context, node)


import timm
m = timm.create_model("vit_base_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, img_size=224).eval()
ex = torch.rand(1, 3, 224, 224)
traced = torch.jit.trace(m, ex)
# freeze folds the shape-arithmetic constants that otherwise surface as
# aten::Int casts on >0-dim arrays, which coremltools cannot convert.
traced = torch.jit.freeze(traced.eval())
with torch.no_grad():
    e = traced(ex)
print("traced OK:", tuple(e.shape))

mlm = ct.convert(
    traced,
    inputs=[ct.TensorType(name="image", shape=(1, 3, 224, 224))],
    outputs=[ct.TensorType(name="embedding")],
    convert_to="mlprogram",
    compute_precision=ct.precision.FLOAT16,
    minimum_deployment_target=ct.target.iOS17,
)
mlm.save("CleanRoom-fp16.mlpackage")

import coremltools.optimize as cto
cfg = cto.coreml.OptimizationConfig(
    global_config=cto.coreml.OpPalettizerConfig(mode="kmeans", nbits=6))
cto.coreml.palettize_weights(mlm, cfg).save("CleanRoom-6bit.mlpackage")
for p in ("CleanRoom-fp16.mlpackage", "CleanRoom-6bit.mlpackage"):
    print(subprocess.run(["du", "-sh", p], capture_output=True, text=True).stdout.strip())
print("DINOV2_CONVERT_DONE")
