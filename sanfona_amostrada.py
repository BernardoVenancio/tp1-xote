"""Renderiza WAVs a partir das notas MIDI e das tres amostras de instrumentos."""
from __future__ import annotations
import argparse
from pathlib import Path
from scipy.signal import resample
import soundfile as sf
import numpy as np
import mido
SAMPLE_RATE=44100

def extract_hit(audio, sr, start:float, duration:float=.38):
    """Isola trecho da batida sem carregar ataque seguinte."""
    i=round(start*sr)
    segment=np.array(audio[i:i+round(duration*sr)],dtype=np.float32,copy=True)
    fade=min(round(.07*sr),len(segment))
    segment[-fade:]*=np.linspace(1,0,fade,dtype=np.float32)
    return segment


def add_triangle_A(wav:np.ndarray,reference:Path,bpm=80,gain=.27):
    tri,sr=sf.read(reference,dtype='float32')
    if sr!=SAMPLE_RATE:raise ValueError('Referencia do triangulo precisa ter 44100 Hz')
    if tri.ndim==2:tri=tri.mean(axis=1)
    # Instantes dos tres ataques na amostra do triangulo.
    clips=[extract_hit(tri,sr,start) for start in (.17,1.07,1.97)]
    beat_duration=60/bpm
    total_beats=int((wav.shape[0]/sr-.8)/beat_duration)
    for i in range(total_beats):
        start=round((i*beat_duration+.17)*sr)
        clip=clips[i%3]
        n=min(len(clip),len(wav)-start)
        if n>0:wav[start:start+n] += gain*clip[:n,None]
    return wav




ROOT=Path(__file__).resolve().parent
# Notas MIDI e trechos [inicio, duracao] da gravacao de referencia
SOURCES={60:(5.4,.45),62:(5.9,.44),64:(2.60,2.12),65:(7.15,.44),67:(7.65,.9)}

class AccordionSampleBank:
    def __init__(self, original:Path):
        wav,sr=sf.read(original,dtype='float32',always_2d=True)
        if sr!=SAMPLE_RATE:raise ValueError('WAV deve ter 44.1kHz')
        self.samples={}
        for pitch,(onset,duration) in SOURCES.items():
            a=round(onset*sr);b=round((onset+duration)*sr)
            self.samples[pitch]=wav[a:b].copy()
        self.cache={}

    def pitched(self,pitch):
        if pitch in self.cache:return self.cache[pitch]
        ref_pitch=min(SOURCES, key=lambda p:abs(p-pitch))
        wav=self.samples[ref_pitch]
        ratio=2**((pitch-ref_pitch)/12)
        # A reamostragem altera altura e duração, mantendo os harmônicos do WAV original.
        out=resample(wav,max(3,round(len(wav)/ratio)),axis=0).astype(np.float32)
        self.cache[pitch]=out
        return out

    def note(self,pitch,duration,velocity):
        source=self.pitched(pitch)
        samples=max(1,round(duration*SAMPLE_RATE))
        out=np.zeros((samples,2),np.float32)
        initial=min(samples,len(source))
        out[:initial]=source[:initial]
        if initial<samples:
            # Inicia o loop antes do release natural da amostra.
            loop_a=max(0,int(.13*SAMPLE_RATE))
            loop_b=min(len(source)-1,int(.42*SAMPLE_RATE))
            if loop_b-loop_a<1000:
                loop_a=round(len(source)*.22)
                loop_b=round(len(source)*.83)
            loop=source[loop_a:loop_b]
            overlap=min(round(.024*SAMPLE_RATE),len(loop)//5)
            cur=initial
            while cur<samples:
                n=min(len(loop),samples-cur+overlap)
                k=min(overlap,cur,n)
                if k>0:
                    mix=np.linspace(0,1,k,dtype=np.float32)[:,None]
                    out[cur-k:cur]=out[cur-k:cur]*(1-mix)+loop[:k]*mix
                z=min(samples-cur,n-k)
                if z>0:
                    out[cur:cur+z]=loop[k:k+z]
                    cur+=z
                else: break
        # Release curto elimina cliques nos finais das notas.
        f=min(samples,round(.065*SAMPLE_RATE))
        out[-f:]*=np.linspace(1,0,f,dtype=np.float32)[:,None]
        return out*(velocity/80.0)


def parse_notes(mid:Path):
    midi=mido.MidiFile(mid)
    tempo=500000;seconds=0.0
    pending={};result=[]
    for msg in mido.merge_tracks(midi.tracks):
        seconds+=mido.tick2second(msg.time,midi.ticks_per_beat,tempo)
        if msg.type=='set_tempo':tempo=msg.tempo
        if msg.type=='note_on' and msg.velocity>0:
            pending.setdefault((msg.channel,msg.note),[]).append((seconds,msg.velocity))
        elif msg.type=='note_off' or (msg.type=='note_on' and msg.velocity==0):
            q=pending.get((msg.channel,msg.note),[])
            if q:
                start,velocity=q.pop(0)
                result.append((msg.channel,msg.note,start,max(.04,seconds-start),velocity))
    return result,seconds

def percussion_samples(wav:np.ndarray,reference:Path,notes):
    """Recorta o bumbo (36) e o toque seco (37) da amostra."""
    raw,sr=sf.read(reference,dtype='float32',always_2d=True)
    if sr!=SAMPLE_RATE:
        raise ValueError('WAV de zabumba precisa ter 44100 Hz')
    clips={}
    for note,onset in ((36,.25),(37,2.5)):
        start=round(onset*sr)
        clip=raw[start:start+round(.48*sr)].copy()
        f=min(round(.075*sr),len(clip))
        clip[-f:]*=np.linspace(1,0,f,dtype=np.float32)[:,None]
        clips[note]=clip
    for channel,pitch,onset,duration,velocity in notes:
        if channel!=9 or pitch not in clips:continue
        start=round(onset*sr)
        if start>=len(wav):continue
        clip=clips[pitch]
        n=min(len(clip),len(wav)-start)
        original_velocity = 88 if pitch==36 else 72
        wav[start:start+n]+=clip[:n] * (.70*velocity/original_velocity)
    return wav


def render_sampled(midi:Path,reference:Path,triangle:Path,zabumba:Path,output:Path,
                   octave_melody:int=0,seconds_max:float|None=None):
    """Combina as amostras para renderizar as pistas MIDI."""
    notes,duration=parse_notes(midi)
    limit=duration+.8 if seconds_max is None else min(seconds_max,duration+.8)
    size=round(limit*SAMPLE_RATE)
    bank=AccordionSampleBank(reference)
    wav=np.zeros((size,2),dtype=np.float32)
    percussion_samples(wav,zabumba,notes)
    for channel,pitch,onset,duration,velocity in notes:
        if channel not in (0,1) or onset>=limit:continue
        new_pitch=pitch+(octave_melody if channel==0 else 0)
        gain=.85 if channel==0 else .15
        note=bank.note(new_pitch,duration,velocity)*gain
        start=round(onset*SAMPLE_RATE)
        n=min(len(note),len(wav)-start)
        if n>0:wav[start:start+n]+=note[:n]
    wav=add_triangle_A(wav,triangle,gain=.22)
    peak=np.max(np.abs(wav))
    if peak>.93:wav*=.93/peak
    output.parent.mkdir(exist_ok=True,parents=True)
    sf.write(output,wav,SAMPLE_RATE,subtype='PCM_16')
    return {'arquivo':str(output),'segundos':size/SAMPLE_RATE,
            'notas_sanfona':sum(ch==0 for ch,*_ in notes),'pico':float(np.abs(wav).max())}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--midi',type=Path,default=ROOT/'midis/xote_01_base.mid')
    p.add_argument('--referencia',type=Path,default=ROOT/'instrumentos/amostras/sanfona_01.wav')
    p.add_argument('--triangulo',type=Path,default=ROOT/'instrumentos/amostras/triangulo_A_final.wav')
    p.add_argument('--zabumba',type=Path,default=ROOT/'instrumentos/amostras/zabumba_aproximacao_01.wav')
    p.add_argument('--oitava-melodia',type=int,default=0,
                   help='Transposicao extra em semitons para a melodia')
    p.add_argument('--segundos',type=float,default=None)
    p.add_argument('--saida',type=Path,required=True)
    a=p.parse_args()
    print(render_sampled(a.midi,a.referencia,a.triangulo,a.zabumba,a.saida,
                         a.oitava_melodia,a.segundos))
