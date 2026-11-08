"""Render/measure animation before and after a split using the production HyperFrames path."""
from pathlib import Path
import sys, copy, json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from PIL import Image
from vt.schema import ScenesFile, Transcript, Word, Beats, Beat
from vt.project import load_theme
from vt.compose.composer import resolve_composition, write_composition
from vt.render.hyperframes import snapshot


def main():
    out=ROOT/'docs/evidence/visual-motion';out.mkdir(parents=True,exist_ok=True)
    tr=Transcript(words=[Word(id='w1',text='Move',start=0,end=4)])
    beats=Beats(beats=[Beat(id='b1',word_ids=['w1'],start=0,end=4,text='Move')])
    plan=ScenesFile(scenes=[{'id':'s1','beats':['b1'],'elements':[{'type':'shape','shape':'circle','at_word':'w1','start':0,'end':4,'color':'#ff00ff','width':.15,'keyframes':[{'time':0,'x':.2,'y':.5},{'time':4,'x':.8,'y':.5,'ease':'linear'}]}]}])
    theme=load_theme('paper');reports=[];thumbs=[]
    for aspect in ['9:16','1:1','16:9']:
        data=resolve_composition(plan,tr,beats,theme,aspect,4,None,language='en');data['captions_enabled']=False
        for variant in ['whole','split']:
            sample=copy.deepcopy(data)
            if variant=='split':
                el=sample['scenes'][0]['elements'][0];other=copy.deepcopy(el);el['until']=2;other['at']=2;sample['scenes'][0]['elements'].append(other)
            folder=out/f'{aspect.replace(":","x")}-{variant}'
            page=write_composition(folder/'comp',sample,theme)
            frames=snapshot(page.parent,folder/'frames',[1,2.5,3],gpu=False)
            for t,frame in zip([1,2.5,3],frames):
                im=Image.open(frame).convert('RGB');pixels=im.load()
                hits=[(x,y) for y in range(0,im.height,3) for x in range(0,im.width,3) if pixels[x,y][0]>210 and pixels[x,y][1]<65 and pixels[x,y][2]>210]
                assert hits,(aspect,variant,t,'missing shape')
                center=(min(x for x,y in hits)+max(x for x,y in hits))/2/im.width
                expected=.2+.6*t/4
                assert abs(center-expected)<.025,(aspect,variant,t,center,expected)
                reports.append({'aspect':aspect,'variant':variant,'time':t,'center':center,'expected':expected})
                if t==2.5: im.thumbnail((300,300));thumbs.append(im)
    sheet=Image.new('RGB',(900,600),'#e4e4e8')
    for i,im in enumerate(thumbs):sheet.paste(im,((i//2)*300+(300-im.width)//2,(i%2)*300+(300-im.height)//2))
    sheet.save(out/'contact-sheet.png');(out/'measurements.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print(f'{len(reports)} rendered positions match the video clock, including splits.')

if __name__=='__main__':main()
