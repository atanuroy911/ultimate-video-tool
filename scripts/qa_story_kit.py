"""Render reusable cartoon controls through the real composition/export engine."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from vt.compose.composer import resolve_composition, write_composition
from vt.project import load_theme
from vt.schema import Word, Transcript, Beat, Beats, ScenesFile
from vt.render.hyperframes import snapshot


def main():
    out = ROOT / 'docs/evidence/story-kit'
    out.mkdir(parents=True, exist_ok=True)
    prop = Image.new('RGBA', (240, 240))
    draw = ImageDraw.Draw(prop)
    draw.rounded_rectangle((35, 65, 205, 205), 18, fill='#e6a93d', outline='#33334a', width=6)
    draw.rectangle((112, 65, 132, 205), fill='#fff0b1')
    prop.save(out / 'prop.png')
    words = [Word(id=f'w{i}', text=w, start=i*.5, end=i*.5+.45) for i,w in enumerate('One small step can change your day'.split())]
    beats = Beats(beats=[Beat(id='b1',word_ids=[w.id for w in words],start=0,end=3.5,text='One small step can change your day')])
    theme = load_theme('paper')
    frames = []
    for style, env, text, light in [('classic','market','sign','day'),('ink','classroom','chalk','sunset'),('paper','street','neon','night')]:
        for aspect in ['9:16','16:9','1:1']:
            cartoon = {'type':'cartoon','at_word':'w0','set':env,'character_style':style,'framing':'scene','world':'3d','lighting':light,'camera':'pan',
                'cast':[{'who':'teacher','name':'Sam','pose':'wave','x':.35},{'who':'robot','name':'Pip','pose':'think','x':.7}],
                'cues':[{'actor':0,'start':1.5,'end':2.5,'pose':'celebrate','expression':'happy'}],
                'labels':[{'text':'ONE SMALL STEP','treatment':text,'x':.5,'y':.16,'width':.65}],
                'artifacts':[{'media':'prop','x':.86,'y':.77,'width':.17,'height':.25,'depth':'front'}]}
            plan=ScenesFile.model_validate({'scenes':[{'id':'s1','beats':['b1'],'layout':'hero','elements':[cartoon]}]})
            media={'prop':{'kind':'image','src':'media/prop.png','_abs':str(out/'prop.png'),'w':240,'h':240}}
            data=resolve_composition(plan,Transcript(words=words),beats,theme,aspect,4,None,media=media,language='en')
            folder=out/f'{style}-{aspect.replace(":","x")}'
            page=write_composition(folder/'comp',data,theme)
            frame=snapshot(page.parent,folder/'frames',[1.8],gpu=False)[0]
            frames.append(frame)
    sheet=Image.new('RGB',(960,960),'#e7e7eb')
    for i,f in enumerate(frames):
        im=Image.open(f).convert('RGB');im.thumbnail((300,300))
        x=(i%3)*320+(320-im.width)//2;y=(i//3)*320+(320-im.height)//2
        sheet.paste(im,(x,y))
    sheet.save(out/'contact-sheet.png')
    print(out/'contact-sheet.png')


if __name__=='__main__': main()
