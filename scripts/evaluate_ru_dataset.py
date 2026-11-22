"""Evaluate published RU OCR crops without downloading the entire 1.5GB ZIP.

Only standard ZIP metadata and selected test members are fetched via HTTPS
Range requests. No dataset code runs, no archive paths are extracted.
"""
from __future__ import annotations
import argparse
import io
import json
import random
import urllib.request
import zipfile
from pathlib import Path

URL = "https://nomeroff.net.ua/datasets/autoriaNumberplateOcrRu-2021-09-01.zip"
ROOT = Path(__file__).resolve().parents[1]

class RemoteZip(io.RawIOBase):
    def __init__(self, url):
        self.url, self.position = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=40) as response:
            self.size = int(response.headers["Content-Length"])
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position
    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.position + size)
        if end <= self.position: return b""
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={self.position}-{end-1}"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206: raise RuntimeError("Dataset server must support byte ranges")
            data = response.read(end-self.position)
        self.position += len(data)
        return data

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--evaluate',action='store_true')
    args=parser.parse_args()
    cache=ROOT/'models/datasets/ru-evaluation'
    cache.mkdir(parents=True,exist_ok=True)
    if args.evaluate:
        import sys
        sys.path.insert(0,str(ROOT))
        import cv2
        import numpy as np
        from backend.cv import engine,normalize_plate,RU_PATTERN
        manifest=json.loads((cache/'manifest.json').read_text(encoding='utf-8'))
        engine.load()
        counts={'direct_ocr':0,'detector_only_pipeline':0,'closeup_pipeline':0}
        errors=[]
        for sample in manifest:
            expected=normalize_plate(sample['annotation']['description'])
            image=cv2.imdecode(np.frombuffer((ROOT/sample['path']).read_bytes(),dtype=np.uint8),cv2.IMREAD_COLOR)
            direct=engine.alpr.ocr.predict(image)
            detected,_=engine._read_plate(image,'plate')
            # Scene path uses the same detector/reader without the close-up
            # fallback and reproduces the old detector-only behavior on crops.
            baseline,_=engine._read_plate(image,'scene')
            values={'direct_ocr':normalize_plate(direct.text) if direct else '', 'detector_only_pipeline':baseline['value'],'closeup_pipeline':detected['value']}
            for key,value in values.items(): counts[key]+=value==expected
            if values['closeup_pipeline']!=expected:
                # Diagnostic indices only; no dataset photos or plate identifiers
                # are included in the distributable aggregate report.
                errors.append({'index':len(errors),'direct_correct':values['direct_ocr']==expected,'format_valid':bool(RU_PATTERN.fullmatch(values['closeup_pipeline']))})
        report={'source':URL,'attribution':'AUTO.RIA Numberplate OCR RU Dataset; data provided by Habr.com community; CC BY 4.0','split':'test','seed':20261122,'samples':len(manifest),'exact_matches':counts,'accuracy':{key:round(value/len(manifest),4) for key,value in counts.items()},'pipeline_errors':errors,'limits':'Published model and its upstream test crops, used to diagnose and verify the crop fallback; not an independent street-scene or detector benchmark. No training or test-label corrections were used.'}
        output=ROOT/'docs/ru-dataset-evaluation.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return
    with zipfile.ZipFile(RemoteZip(URL)) as archive:
        names=archive.namelist()
        if args.list:
            print(json.dumps({'members':len(names),'examples':names[:20],'test_examples':[name for name in names if '/test/' in name][:20]},ensure_ascii=False,indent=2))
            return
        annotation_names=sorted(name for name in names if '/test/ann/' in name and name.endswith('.json'))
        if not annotation_names: raise RuntimeError('No explicit test/ann split found; inspect --list before evaluating')
        selected=random.Random(20261122).sample(annotation_names,min(args.limit,len(annotation_names)))
        samples=[]
        for index,name in enumerate(selected):
            annotation=json.loads(archive.read(name))
            image_name=name.replace('/ann/','/img/').rsplit('.',1)[0]
            image_name=next((image_name+extension for extension in ['.png','.jpg','.jpeg'] if image_name+extension in names),None)
            if not image_name: continue
            target=cache/f'{index:04d}{Path(image_name).suffix}'
            if not target.exists(): target.write_bytes(archive.read(image_name))
            samples.append({'path':str(target.relative_to(ROOT)),'annotation':annotation,'member':name})
            if (index+1)%10==0: print(f'Fetched {index+1}/{len(selected)}',flush=True)
    (cache/'manifest.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'samples':len(samples),'annotation_example':samples[0]['annotation'] if samples else None},ensure_ascii=False))

if __name__=='__main__': main()
