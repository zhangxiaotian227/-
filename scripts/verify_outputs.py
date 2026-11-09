from pathlib import Path
import argparse,json
from PIL import Image
p=argparse.ArgumentParser(description="Verify selected 8K transparent PNG render tasks")
p.add_argument("manifest",type=Path)
p.add_argument("--indices",nargs="*",type=int,default=None)
a=p.parse_args();tasks=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
indices=a.indices if a.indices is not None else list(range(len(tasks)))
records=[];failures=[]
for i in indices:
    if not 0<=i<len(tasks):failures.append({"index":i,"error":"Task index out of range"});continue
    path=Path(tasks[i]["output"])
    try:
        with Image.open(path) as im:
            if im.size!=(7680,4320) or im.mode!="RGBA":raise ValueError("Expected 7680x4320 RGBA")
            alpha=im.getchannel("A");limits=alpha.getextrema();bounds=alpha.getbbox()
            if limits[0]!=0 or limits[1]==0 or bounds is None:raise ValueError("Expected nonempty transparent line art")
        records.append({"index":i,"path":str(path),"size":[7680,4320],"alpha_range":limits,"bounds":bounds})
    except (OSError,ValueError,SyntaxError,EOFError) as error:failures.append({"index":i,"path":str(path),"error":str(error)})
report={"expected":len(indices),"verified":len(records),"files":records,"failures":failures}
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(1 if failures else 0)
