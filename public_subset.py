import csv, pathlib, re
from collections import defaultdict
import numpy as np, torch, timm
from PIL import Image
MEAN = np.array([0.485,0.456,0.406],dtype=np.float32); STD = np.array([0.229,0.224,0.225],dtype=np.float32)
def tensor_for(p):
    img = Image.open(p).convert("RGB").resize((224,224), Image.BILINEAR)
    a = (np.asarray(img,dtype=np.float32)/255.0 - MEAN)/STD
    return torch.from_numpy(a.transpose(2,0,1)[None])
model = timm.create_model("vit_base_patch14_dinov2.lvd142m", pretrained=True, num_classes=0, img_size=224).eval()
def embed(p):
    with torch.no_grad(): e = model(tensor_for(p))
    return torch.nn.functional.normalize(e,p=2,dim=1)[0]
man = list(csv.DictReader(open("manifest_inat_full_public.csv")))
by_sp = defaultdict(list)
for path in sorted(pathlib.Path("images_inat").iterdir()):
    m = re.match(r"(.+)__(\d+)\.", path.name)
    if not m: continue
    by_sp[man[int(m.group(2))]["species"]].append(path)
centroids, labels = [], []
for sp, paths in sorted(by_sp.items()):
    if len(paths) < 3: continue
    vecs = [embed(p) for p in paths]
    centroids.append(torch.nn.functional.normalize(torch.stack(vecs).mean(0),p=2,dim=0))
    labels.append(sp)
    print(f"store {sp}: {len(vecs)}")
C = torch.stack(centroids)
print(f"public store: {len(labels)} classes")
t1=t5=n=0
for man_path, img_dir in [("manifest_covered61.csv","images_cropped"),("manifest_uncovered79.csv","images_uncovered_cropped")]:
    m2 = list(csv.DictReader(open(man_path)))
    for path in sorted(pathlib.Path(img_dir).iterdir()):
        mm = re.match(r"(.+)__(\d+)\.", path.name)
        if not mm: continue
        true_sp = m2[int(mm.group(2))]["species"]
        if true_sp not in labels: continue
        try: e = embed(path)
        except Exception: continue
        sims = C @ e
        top = torch.topk(sims, k=5).indices.tolist()
        names = [labels[i] for i in top]
        t1 += int(names[0]==true_sp); t5 += int(true_sp in names); n += 1
        if n % 200 == 0: print(f"eval {n}")
import json as _json
out = pathlib.Path("results_public"); out.mkdir(exist_ok=True)
np.save(out/"centroids.npy", C.numpy())
(out/"labels.json").write_text(_json.dumps(labels, indent=0))
(out/"summary.md").write_text(f"# Public-subset benchmark\n\ntop-1 {t1/n*100:.0f}% / top-5 {t5/n*100:.0f}% (n={n}, {len(labels)} classes)\n")
print(f"PUBLIC-SUBSET: top-1 {t1/n*100:.0f}% / top-5 {t5/n*100:.0f}% (n={n})")
print("PUBLIC_SUBSET_DONE")
