#!/usr/bin/env python3
"""Original deterministic motion-graphics preview. No external generation service."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import sys
import wave

from PIL import Image, ImageDraw, ImageFont

W,H=1920,1080
FPS=30
INK='#10232d'; CREAM='#f7f5ee'; MINT='#83e3bf'; PURPLE='#b6b5f7'; MUTED='#a7b9bf'
SCENES=[
 (7, 'ONE CLEAR IDEA', 'Start with the story.', 'A good video starts with one clear idea. What should your audience understand, feel, or do?'),
 (8, 'THE RIGHT MATERIAL', 'Many ways to begin.', 'Bring your brief, your product, or the footage you already have. Choose the route that fits the story.'),
 (8, 'A PURPOSE FOR EVERY SHOT', 'Make the story visible.', 'Turn that story into scenes. Give every shot a purpose, then connect the visuals, voice, and captions.'),
 (8, 'SEE IT. HEAR IT. FEEL IT.', 'Preview before production.', 'Make a short preview first. Check the pace, the sound, and the details before building the full video.'),
 (8, 'KEEP WHAT WORKS', 'Change one scene.', "When something changes, revise the scene that needs it. Keep the work you've already approved."),
 (8, 'CHECK THE ACTUAL RESULT', 'Confidence comes from checks.', 'Check the actual export. Can it play? Is the text readable? Do the captions match what you hear?'),
 (8, 'READY FOR THE NEXT PERSON', 'Make it yours.', 'Deliver a clear, editable result. One workflow, many styles. Built to improve with every contribution.'),
]


def font(size,bold=False,serif=False):
    names=([
        '/System/Library/Fonts/Supplemental/Georgia.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'] if serif else [
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for p in names:
        if Path(p).is_file(): return ImageFont.truetype(p,size)
    raise RuntimeError('Install Arial/Georgia or DejaVu fonts; font binaries are not bundled.')


FONTS={}
def f(size,bold=False,serif=False):
    key=(size,bold,serif)
    if key not in FONTS:FONTS[key]=font(*key)
    return FONTS[key]


def ease(x):
    x=max(0,min(1,x)); return 1-(1-x)**3


def rounded(d,box,fill,r=24,outline=None,width=1):
    d.rounded_rectangle(tuple(int(x) for x in box),r,fill=fill,outline=outline,width=width)


def text(d,xy,value,size=32,fill=INK,bold=False,serif=False):
    d.text(tuple(int(x) for x in xy),value,font=f(size,bold,serif),fill=fill,spacing=14)


def label(d,x,y,value,dark=True):
    text(d,(x,y),value,23,MINT if dark else '#386858',True)


def checkmark(d,x,y,color=MINT,scale=1):
    d.line([(x,y+12*scale),(x+10*scale,y+23*scale),(x+30*scale,y)],fill=color,width=max(2,int(5*scale)),joint='curve')


def line(d,points,fill,width=3):
    d.line([(int(x),int(y)) for x,y in points],fill=fill,width=width,joint='curve')


def frame(scene_index,t,total_t,cues):
    dur,kicker,title,_=SCENES[scene_index]
    light=scene_index in (1,4,6)
    bg=CREAM if light else INK; fg=INK if light else CREAM; sub='#577079' if light else MUTED
    im=Image.new('RGB',(W,H),bg);d=ImageDraw.Draw(im)
    # Quiet fixed identity, chapter and measured progress.
    rounded(d,(80,56,118,94),INK if light else MINT,10)
    d.polygon([(94,66),(94,84),(108,75)],fill=CREAM if light else INK)
    text(d,(136,57),'VIDEO / PRODUCTION',25,fg,True)
    text(d,(1640,61),f'0{scene_index+1} / 07',23,sub)
    entry=ease(t/0.9); yshift=30*(1-entry)
    label(d,80,170+yshift,kicker,not light)
    text(d,(75,221+yshift),title,76,fg,serif=True)
    # Scene-specific original vector compositions.
    if scene_index==0:
        text(d,(82,360),'A brief. A direction.\nA story worth watching.',48,fg)
        text(d,(84,548),'Plan  /  Produce  /  Refine',28,sub)
        cx,cy=1370,550
        for i,(size,col) in enumerate([(520,'#1d3942'),(405,'#2b514f'),(282,MINT)]):
            s=size*(.94+.06*ease((t-i*.15)/1.4))
            rounded(d,(cx-s/2,cy-s/2,cx+s/2,cy+s/2),col,int(s*.21))
        d.polygon([(1322,468),(1322,632),(1464,550)],fill=INK)
        for i in range(10):
            hh=20+60*(.5+.5*math.sin(t*2+i*.8))
            rounded(d,(1170+i*40,870-hh,1187+i*40,870),MINT,8)
    elif scene_index==1:
        titles=['Record a workflow','Animate an idea','Edit your footage']
        for i,tt in enumerate(titles):
            p=ease((t-i*.28)/.8);x=80+i*600;y=365+(1-p)*60
            rounded(d,(x,y,x+560,y+460),'#ffffff',28,outline='#dce3dc',width=2)
            rounded(d,(x+30,y+30,x+530,y+310),['#e6f1e9','#e9e8fa','#e7eef2'][i],18)
            if i==0:
                rounded(d,(x+60,y+65,x+500,y+280),INK,13)
                rounded(d,(x+85,y+100,x+170,y+252),'#24414a',8)
                for j in range(3):rounded(d,(x+195,y+107+j*46,x+460,y+133+j*46),MINT if j==1 else '#658487',7)
                px=x+290+85*math.sin(t*.7);py=y+160+25*math.cos(t)
                d.polygon([(px,py),(px+2,py+31),(px+12,py+24),(px+23,py+24)],fill=CREAM)
            elif i==1:
                for j in range(3):
                    xx=x+110+j*140;yy=y+175+28*math.sin(t*1.3+j)
                    d.ellipse((xx-47,yy-47,xx+47,yy+47),fill=[MINT,PURPLE,INK][j])
                    if j<2:line(d,[(xx+50,yy),(xx+90,yy)],'#758980',4)
            else:
                for j in range(3):
                    rounded(d,(x+65+j*142,y+80,x+190+j*142,y+215),[INK,'#628a89',PURPLE][j],12)
                rounded(d,(x+65,y+242,x+490,y+258),'#bed4d1',6)
                marker=x+70+(t/dur)*410;line(d,[(marker,y+229),(marker,y+272)],INK,4)
            text(d,(x+30,y+345),tt,35,INK,True)
            text(d,(x+30,y+405),['Show the actual action.','Explain what matters.','Shape what you have.'][i],26,'#577079')
    elif scene_index==2:
        names=['Opening','Context','Action','Result']
        for i,n in enumerate(names):
            x=82+i*450; yy=390+24*(1-ease((t-i*.18)/.7))
            rounded(d,(x,yy,x+410,yy+245),['#22434b','#305552','#475c7d','#305552'][i],24)
            text(d,(x+24,yy+22),f'0{i+1}',24,MINT,True)
            if i in (0,3):
                d.ellipse((x+155,yy+70,x+255,yy+170),fill=MINT if i==0 else PURPLE)
                if i==3:checkmark(d,x+183,yy+103,INK,1.2)
            else:
                for j in range(3):rounded(d,(x+42,yy+74+j*43,x+365-(j%2)*75,yy+98+j*43),MINT if j==1 else '#819b9f',7)
            text(d,(x+10,yy+272),n,32,CREAM,True)
        for i,(name,col) in enumerate([('VISUAL',PURPLE),('VOICE',MINT),('CAPTIONS','#e8cda4')]):
            y=785+i*48;label(d,82,y,name)
            rounded(d,(310,y+3,1815,y+27),'#24414a',7)
            rounded(d,(310,y+3,310+1505*ease((t-.7-i*.3)/3),y+27),col,7)
    elif scene_index==3:
        rounded(d,(82,365,1220,890),'#24414a',30)
        rounded(d,(108,391,1194,810),'#edf2e8',18)
        text(d,(145,425),'Your story, in motion.',45,INK,True)
        for i in range(3):
            x=150+i*330; y=530+24*math.sin(t+i)
            rounded(d,(x,y,x+285,y+190),[INK,'#7ab39c',PURPLE][i],18)
        playx=130+(t/dur)*1030
        line(d,[(130,852),(1170,852)],'#5d7b80',7);line(d,[(130,852),(playx,852)],MINT,7)
        d.ellipse((playx-10,842,playx+10,862),fill=MINT)
        for i,word in enumerate(['PACE','VOICE','DETAIL']):
            y=420+i*135;checkmark(d,1325,y+10,MINT,1.2)
            text(d,(1390,y),word,35,CREAM,True)
            text(d,(1390,y+51),['Room to understand.','Natural and clear.','Readable at a glance.'][i],26,MUTED)
    elif scene_index==4:
        for i in range(5):
            x=82+i*356; y=405
            chosen=i==2;col=INK if chosen else '#ffffff'
            rounded(d,(x,y,x+326,y+325),col,24,outline='#d7e3da',width=2)
            text(d,(x+25,y+25),f'SCENE 0{i+1}',23, MINT if chosen else '#577079',True)
            for j in range(3):
                length=240-(j%2)*60
                rounded(d,(x+27,y+98+j*48,x+27+length,y+116+j*48),MINT if chosen and j==1 else ('#40626a' if chosen else '#d8e6df'),5)
            if chosen:
                text(d,(x+27,y+259),'Refining…',29,CREAM,True)
                line(d,[(x+23,y+322),(x+23+280*ease(t/4),y+322)],MINT,5)
            else:
                checkmark(d,x+28,y+269,'#35745e',.8);text(d,(x+70,y+257),'Keep',28,'#35745e',True)
        text(d,(84,802),'Focused revisions. Less repeated work.',38,INK,serif=True)
    elif scene_index==5:
        rows=[('PLAYBACK','Full decode'),('PICTURE','Visual review'),('SOUND','Listen and align'),('DELIVERY','Files and source')]
        for i,(name,note) in enumerate(rows):
            y=365+i*123;rounded(d,(82,y,1838,y+101),'#1c3842',17)
            text(d,(111,y+28),name,29,CREAM,True)
            text(d,(630,y+27),note,30,MUTED)
            if t>i*.55+.7:checkmark(d,1740,y+35,MINT,1.2)
        text(d,(84,862),'Technical checks + human judgment',26,MUTED)
    else:
        text(d,(84,360),'One workflow.\nMany video styles.',74,INK,serif=True)
        text(d,(85,585),'Editable. Reviewable. Open to improve.',32,'#577079')
        for i,tt in enumerate(['THE VIDEO','THE SOURCE','THE EVIDENCE']):
            x=1080+i*230;yy=405+18*math.sin(t*.8+i)
            rounded(d,(x,yy,x+204,yy+290),[INK,'#dce9df',PURPLE][i],22)
            text(d,(x+20,yy+28),['01','02','03'][i],36,MINT if i==0 else INK,True)
            for j in range(3):rounded(d,(x+22,yy+110+j*38,x+175,yy+126+j*38), '#4d7274' if i==0 else '#9fbcad',5)
            text(d,(x,yy+323),tt,21,INK,True)
        rounded(d,(84,753,722,830),INK,18);text(d,(115,773),'VIDEO PRODUCTION  /  v0.1',30,CREAM,True)
    # Readable phrase captions, kept below the meaningful composition.
    cue=next((c for c in cues if c['start']<=total_t<c['end']),None)
    if cue:
        lines=cue['text'].split('\n');cw=max(d.textlength(l,font=f(30)) for l in lines)+64
        ch=50+39*(len(lines)-1);x=(W-cw)/2;y=H-112-ch
        rounded(d,(x,y,x+cw,y+ch),'#07151d',14)
        for j,l in enumerate(lines):text(d,((W-d.textlength(l,font=f(30)))/2,y+9+j*39),l,30,'#ffffff')
    rounded(d,(80,1030,1840,1034),'#d4dfd7' if light else '#37535c',2)
    rounded(d,(80,1030,80+1760*min(1,total_t/55),1034),INK if light else MINT,2)
    return im


def timestamp(v):
    ms=round(v*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def chunks(sentence):
    return [part.strip() for part in re.split(r'(?<=[.!?])\s+',sentence) if part.strip()]


def narration_key(voice,rate):
    data={'voice':voice,'rate':rate,'speech_and_slots':[(s[0],s[3]) for s in SCENES],'audio_pipeline':4}
    if voice.startswith('piper:'):
        model=Path(voice.removeprefix('piper:'))
        data['model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
        data['config_sha256']=hashlib.sha256(Path(str(model)+'.json').read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def audio_cache_valid(out,voice,rate):
    try:
        state=json.loads((out/'timings.json').read_text())
        if not isinstance(state,dict) or not isinstance(state.get('artifacts'),dict):return False
        if state.get('input_key')!=narration_key(voice,rate):return False
        for name in ['narration.wav','mix.wav','captions.srt','script.md','music.wav']:
            p=out/name
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=state.get('artifacts',{}).get(name):return False
        return True
    except (OSError,ValueError,TypeError):return False


def clip_cache_valid(clip,marker,digest,seconds):
    try:
        if not clip.is_file() or not marker.is_file() or marker.read_text()!=digest:return False
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_streams','-of','json',str(clip)],stderr=subprocess.DEVNULL,timeout=30))
        v=next(x for x in info['streams'] if x.get('codec_type')=='video')
        if v.get('width')!=W or v.get('height')!=H or abs(float(v['duration'])-seconds)>.05:return False
        n,d=v.get('avg_frame_rate','0/1').split('/')
        if not float(d) or abs(float(n)/float(d)-FPS)>.01 or v.get('pix_fmt')!='yuv420p':return False
        subprocess.run(['ffmpeg','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',str(clip),'-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=max(60,seconds*4))
        return True
    except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError):return False


def prepare_audio(out,voice,rate):
    duration=sum(x[0] for x in SCENES);sample_rate=48000
    pcm=bytearray(int(duration*sample_rate)*2);cues=[];timings=[];cursor=0
    neural=None
    if voice.startswith('piper:'):
        from piper import PiperVoice, SynthesisConfig
        neural=PiperVoice.load(voice.removeprefix('piper:'))
        synthesis=SynthesisConfig(length_scale=.9*148/rate)
    for i,(length,_,_,speech) in enumerate(SCENES):
        scene_pcm=bytearray();scene_cues=[];parts=chunks(speech)
        for j,part in enumerate(parts):
            aiff=out/f'voice-{i+1}-{j+1}.aiff';wav=out/f'voice-{i+1}-{j+1}.wav'
            if neural:
                generated=out/f'voice-{i+1}-{j+1}-piper.wav'
                with wave.open(str(generated),'wb') as wf:neural.synthesize_wav(part,wf,syn_config=synthesis)
            else:
                if not shutil.which('say'):raise RuntimeError('Install Piper and supply --model, or explicitly select a permitted local system voice.')
                subprocess.run(['say','-v',voice,'-r',str(rate),'-o',str(aiff),part],check=True)
                generated=aiff
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(generated),'-ar','48000','-ac','1','-c:a','pcm_s16le',str(wav)],check=True)
            with wave.open(str(wav)) as w:raw=w.readframes(w.getnframes());seconds=w.getnframes()/w.getframerate()
            start=cursor+.25+len(scene_pcm)/(sample_rate*2)
            scene_cues.append({'start':start,'end':start+seconds,'text':part})
            scene_pcm.extend(raw)
            if j<len(parts)-1:scene_pcm.extend(bytes(round(.12*sample_rate)*2))
        raw=bytes(scene_pcm);seconds=len(raw)/(sample_rate*2)
        if seconds>length-.45:raise RuntimeError(f'Voice {i+1} needs {seconds:.2f}s; scene budget {length}s. Adjust rate/script rather than cutting speech.')
        start=cursor+.25;at=round(start*sample_rate)*2;pcm[at:at+len(raw)]=raw
        cues.extend(scene_cues)
        timings.append({'scene':i+1,'start':start,'spoken_seconds':seconds,'slot_seconds':length,'text':speech});cursor+=length
    audio=out/'narration.wav'
    with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sample_rate);w.writeframes(pcm)
    # Original understated ambient bed, generated mathematically; no stock-music rights.
    import array
    bed=array.array('h')
    for j in range(int(duration*sample_rate)):
        t=j/sample_rate;env=min(1,t/2,(duration-t)/3)
        value=sum(math.sin(2*math.pi*freq*t+phase)*amp for freq,amp,phase in [(130.8128,.011,0),(164.8138,.007,.4),(195.9977,.005,.8)])
        # Reduce the already quiet bed further under measured speech.
        duck=.38 if any(a['start']<=t<a['start']+a['spoken_seconds'] for a in timings) else 1
        bed.append(int(32767*value*env*duck))
    with wave.open(str(out/'music.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sample_rate);w.writeframes(bed.tobytes())
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(audio),'-i',str(out/'music.wav'),'-filter_complex',
                    '[0:a]loudnorm=I=-17:TP=-2:LRA=7[v];[v][1:a]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.92[a]',
                    '-map','[a]','-ar','48000',str(out/'mix.wav')],check=True)
    srt='\n\n'.join(f'{i+1}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n'
    (out/'captions.srt').write_text(srt)
    (out/'script.md').write_text('# Video Production — showcase narration\n\n'+'\n\n'.join(f'## Scene {i+1} · {s[0]} seconds\n\n{s[3]}' for i,s in enumerate(SCENES)))
    artifacts={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['narration.wav','mix.wav','captions.srt','script.md','music.wav']}
    (out/'timings.json').write_text(json.dumps({'input_key':narration_key(voice,rate),'artifacts':artifacts,'voice':voice,'rate':rate,'alignment':'Measured sentence audio with explicit inter-sentence gaps; not word-level alignment','scenes':timings,'cues':cues},indent=2))
    return cues


def render(out,voice,rate,stills_only=False):
    out.mkdir(parents=True,exist_ok=True)
    timings=out/'timings.json'
    cues=json.loads(timings.read_text())['cues'] if audio_cache_valid(out,voice,rate) else prepare_audio(out,voice,rate)
    cursor=0;thumbs=[]
    for i,s in enumerate(SCENES):
        im=frame(i,min(3,s[0]/2),cursor+min(3,s[0]/2),cues)
        im.save(out/f'scene-{i+1}.png');thumbs.append(im.resize((640,360)))
        cursor+=s[0]
    sheet=Image.new('RGB',(1280,4*360),CREAM)
    for i,im in enumerate(thumbs):sheet.paste(im,((i%2)*640,(i//2)*360))
    sheet.save(out/'contact-sheet.jpg',quality=90)
    if stills_only:return
    clips=[];cursor=0
    for i,s in enumerate(SCENES):
        target=out/f'scene-{i+1}.mp4';clips.append(target)
        digest=hashlib.sha256(Path(__file__).read_bytes()+json.dumps(s).encode()+json.dumps(cues).encode()).hexdigest()
        marker=out/f'scene-{i+1}.sha256'
        if clip_cache_valid(target,marker,digest,s[0]):cursor+=s[0];continue
        partial=out/f'scene-{i+1}.partial.mp4'
        args=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
              '-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(partial)]
        p=subprocess.Popen(args,stdin=subprocess.PIPE)
        try:
            for j in range(s[0]*FPS):p.stdin.write(frame(i,j/FPS,cursor+j/FPS,cues).tobytes())
            p.stdin.close()
            if p.wait()!=0:raise RuntimeError(f'FFmpeg failed at scene {i+1}')
            partial.replace(target);marker.write_text(digest)
        finally:
            if p.poll() is None:p.kill();p.wait()
            partial.unlink(missing_ok=True)
        print(f'Rendered scene {i+1}/7',flush=True);cursor+=s[0]
    listing=out/'concat.txt';listing.write_text(''.join(f"file 'scene-{i+1}.mp4'\n" for i in range(len(SCENES))))
    subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-i',str(out/'mix.wav'),
                    '-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-t','55','-movflags','+faststart',str(out/'video-production-preview.mp4')],check=True)
    print(str(out/'video-production-preview.mp4'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='artifacts/showcase');parser.add_argument('--voice',help='Explicit system voice for private preview; check its distribution terms')
    parser.add_argument('--model',default='artifacts/voices/en_US-ljspeech-high.onnx',help='Piper ONNX model path with adjacent .json config')
    parser.add_argument('--rate',type=int,default=148);parser.add_argument('--stills-only',action='store_true')
    args=parser.parse_args()
    selected=args.voice or f'piper:{Path(args.model).resolve()}'
    if not args.voice and not Path(args.model).is_file():parser.error('Piper model is missing; download it as described in README or pass --model')
    render(Path(args.output).resolve(),selected,args.rate,args.stills_only)
