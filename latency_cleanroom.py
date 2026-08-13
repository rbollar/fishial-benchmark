import time, numpy as np, coremltools as ct
for pkg in ("CleanRoom-fp16.mlpackage", "CleanRoom-6bit.mlpackage"):
    for cu_name, cu in (("CPU_ONLY", ct.ComputeUnit.CPU_ONLY), ("ALL(ANE)", ct.ComputeUnit.ALL)):
        m = ct.models.MLModel(pkg, compute_units=cu)
        x = {"image": np.random.rand(1, 3, 224, 224).astype(np.float32)}
        m.predict(x)
        t0 = time.time(); N = 15
        for _ in range(N): m.predict(x)
        print(f"{pkg:26} {cu_name:9} {(time.time()-t0)/N*1000:6.1f} ms")
print("LATENCY_DONE")
