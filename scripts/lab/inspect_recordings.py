"""Local contact sheets and audio copies for the owner's two supplied recordings."""
from pathlib import Path
import json
import subprocess
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parents[2]
out=root/'dist/recording-acceptance';out.mkdir(parents=True,exist_ok=True)
for index,item in enumerate(json.loads((out/'sources.json').read_text()),1):
    source=root/item['file'];duration=float(item['probe']['format']['duration'])
    folder=out/f'source-{index}';folder.mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1440,3*295),'#151a23');draw=ImageDraw.Draw(sheet)
    for number,frac in enumerate([.025,.18,.36,.54,.72,.9]):
        seconds=duration*frac;frame=folder/f'{number}.jpg'
        subprocess.run(['ffmpeg','-y','-v','error','-ss',str(seconds),'-i',str(source),'-frames:v','1','-vf','scale=720:-2',str(frame)],check=True)
        image=Image.open(frame).convert('RGB');image.thumbnail((720,265))
        x=(number%2)*720;y=(number//2)*295
        sheet.paste(image,(x,y+28));draw.text((x+12,y+7),f'{source.name}   {seconds:.1f}s',fill='white')
    sheet.save(folder/'contact-sheet.jpg',quality=90)
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-vn','-ac','1','-ar','16000',str(folder/'speech.wav')],check=True)
    print(source.name,'inspected',flush=True)
