import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
import mido

TICKS = 480
BPM = 80
# Melodia transposta uma oitava para baixo.
MELODY_OCTAVE_SHIFT = -12
# Escala de Sol maior em MIDI.
G_MAJOR = (67, 69, 71, 72, 74, 76, 78)
CHORDS = {
    'G': (0, (55, 59, 62), 'Sol maior'),
    'C': (3, (52, 55, 60), 'Do maior'),
    'D': (4, (54, 57, 62), 'Re maior'),
    'Em': (5, (52, 55, 59), 'Mi menor'),
    'Am': (1, (57, 60, 64), 'La menor'),
}
PROGRESSION = ('G', 'C', 'D', 'G', 'G', 'C', 'D', 'G',
               'Em', 'Am', 'D', 'D', 'G', 'C', 'D', 'G')
# Cada motivo tem quatro tempos: (grau da escala, duracao).
MOTIFS = {
    'subida':        ((0,.5), (1,.5), (2,1), (3,.5), (2,.5), (0,1)),
    'arco':          ((0,1), (2,.5), (4,.5), (2,1), (0,1)),
    'vizinhanca':    ((0,.5), (1,.5), (0,1), (2,.5), (1,.5), (0,1)),
    'salto':         ((0,1), (4,.5), (2,.5), (1,1), (0,1)),
    'cadencia':      ((2,.5), (1,.5), (0,1), (0,2)),
    'sustentado':    ((0,2), (1,.5), (2,.5), (0,1)),
    'virada':        ((4,.5), (3,.5), (2,.5), (1,.5), (0,2)),
    'contraste':     ((0,1), (4,1), (2,.5), (3,.5), (0,1)),
    'descida':       ((4,.5), (3,.5), (2,1), (1,1), (0,1)),
    'resposta':      ((2,1), (0,.5), (2,.5), (1,1), (0,1)),
}


def rules(v):
    ##Pesos das producoes. O sorteio normaliza automaticamente cada grupo
    return {
        'A': [('P Q', .9-.4*v), ('Q P', .1+.4*v)],
        'B': [('R Q', .9-.4*v), ('R P', .1+.4*v)],
        'P': [('subida', 1-v), ('arco', .75), ('vizinhanca', .8), ('salto', .2+1.8*v)],
        'Q': [('cadencia', 1.5-v), ('sustentado', 1-v/2), ('virada', .2+1.6*v)],
        'R': [('contraste', 1-v), ('descida', 1), ('resposta', .3+1.5*v)],
    }


@dataclass
class Note:
    beat: float
    duration: float
    pitch: int
    velocity: int
    channel: int


def choose(options, rng):
    names, weights = zip(*options)
    return rng.choices(names, weights=weights)[0]


def grammar(seed, variation, cycles):
    rng = random.Random(seed)
    table = rules(variation)
    motifs, derivations = [], []
    for cycle in range(cycles):
        for phrase in ('A', 'A', 'B', 'A'):  # S -> A A B A
            production = choose(table[phrase], rng)
            derivations.append({'ciclo': cycle+1, 'nao_terminal': phrase, 'producao': production})
            for symbol in production.split():
                motif = choose(table[symbol], rng)
                derivations.append({'ciclo': cycle+1, 'nao_terminal': symbol, 'producao': motif})
                motifs.append(motif)
    return motifs, derivations, table, rng


def melody(motifs, rng, variation):
    notes, records = [], []
    for index, name in enumerate(motifs):
        beat = float(index*4)
        for degree, duration in MOTIFS[name]:
            bar = int(beat//2)
            root = CHORDS[PROGRESSION[bar % 16]][0]
            octave, degree_index = divmod(root+degree, 7)
            pitch = G_MAJOR[degree_index] + 12*octave + MELODY_OCTAVE_SHIFT
            if variation > .5 and rng.random() < .025: pitch -= 12
            velocity = max(55, min(110, 88+rng.randrange(-7, 8)))
            notes.append(Note(beat, duration+.065, pitch, velocity, 0))
            records.append({'motivo': name, 'compasso': bar+1, 'tempo': beat, 'nota': pitch})
            beat += duration
    return notes, records


def accompaniment(bars):
    harmony, zabumba, triangle = [], [], []
    for bar in range(bars):
        beat = bar*2
        for pitch in CHORDS[PROGRESSION[bar % 16]][1]:
            harmony.append(Note(beat, 1.96, pitch, 52, 1))
        zabumba.extend([Note(beat, .16, 36, 88, 9), Note(beat+1, .16, 36, 76, 9),
                        Note(beat+1.5, .14, 37, 72, 9)])
    for i in range(bars*2):
        beat = i+.17*(BPM/60)
        position = i % 3
        if position == 1:
            triangle.extend([Note(beat, .24*(BPM/60), 80, 122, 9),
                             Note(beat, .32*(BPM/60), 81, 36, 9)])
        else:
            triangle.append(Note(beat, .23*(BPM/60), 80, 105 if position == 0 else 96, 9))
    return harmony, zabumba, triangle


def save_midi(path, notes, bars):
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    meta = mido.MidiTrack(); midi.tracks.append(meta)
    meta.extend([mido.MetaMessage('track_name', name='TP1 Xote - Gramatica Probabilistica'),
                 mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(BPM)),
                 mido.MetaMessage('time_signature', numerator=2, denominator=4)])
    tracks = [(0, 'Sanfona - melodia gerada', 105),
              (1, 'Sanfona - fole e harmonia', 76), (9, 'Zabumba e triangulo A', 94)]
    for channel, label, volume in tracks:
        track = mido.MidiTrack(); midi.tracks.append(track)
        track.append(mido.MetaMessage('track_name', name=label))
        if channel != 9: track.append(mido.Message('program_change', program=21, channel=channel))
        track.append(mido.Message('control_change', channel=channel, control=7, value=volume))
        events = []
        for note in notes:
            if note.channel != channel: continue
            start = round(note.beat*TICKS)
            end = round((note.beat+note.duration)*TICKS)
            events.extend([(start, 1, mido.Message('note_on', channel=channel, note=note.pitch,
                                                    velocity=note.velocity)),
                           (end, 0, mido.Message('note_off', channel=channel, note=note.pitch, velocity=0))])
        previous = 0
        for tick, _, message in sorted(events, key=lambda item: item[:2]):
            track.append(message.copy(time=tick-previous))
            previous = tick
        track.append(mido.MetaMessage('end_of_track', time=max(0, bars*2*TICKS-previous)))
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)


def compose(seed, variation, cycles, name, root):
    if not 0 <= variation <= 1: raise ValueError('variacao deve estar entre 0 e 1')
    if cycles < 1: raise ValueError('ciclos deve ser >= 1')
    motifs, derivations, table, rng = grammar(seed, variation, cycles)
    melodic_notes, records = melody(motifs, rng, variation)
    bars = cycles*16
    harmony, zabumba, triangle = accompaniment(bars)
    instruments = {'sanfona_melodia': melodic_notes, 'sanfona_harmonia': harmony,
                   'zabumba': zabumba, 'triangulo': triangle}
    midi_file = root/'midis'/f'{name}.mid'
    save_midi(midi_file, [note for group in instruments.values() for note in group], bars)
    data = {
        'nome': name, 'metodo': 'gramatica generativa probabilistica',
        'semente': seed, 'variacao': variation, 'ciclos': cycles,
        'bpm': BPM, 'compasso': '2/4', 'tonalidade': 'Sol maior',
        'transposicao_melodia_semitons': MELODY_OCTAVE_SHIFT,
        'estrutura': 'S -> A A B A (repetida por ciclo)',
        'barras': bars, 'duracao_segundos': bars*2*60/BPM,
        'regras_com_pesos': table, 'motivos_gerados': motifs, 'derivacoes': derivations,
        'melodia_notas': records, 'contagem_eventos': {k: len(v) for k,v in instruments.items()},
        'arquivo_midi': str(midi_file.relative_to(root)),
    }
    path = root/'metadados'/f'{name}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerador de xote com gramatica probabilistica')
    parser.add_argument('--semente', type=int, default=42)
    parser.add_argument('--variacao', type=float, default=.2)
    parser.add_argument('--ciclos', type=int, default=2)
    parser.add_argument('--nome', default='xote_personalizado')
    parser.add_argument('--saida', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = compose(args.semente, args.variacao, args.ciclos, args.nome, args.saida)
    print(f"Criado: {result['arquivo_midi']} ({result['barras']} compassos)")
