"""Gera as tres musicas e resume os resultados dos experimentos."""
import argparse
from collections import Counter
import json
from pathlib import Path
import matplotlib.pyplot as plt
from gerador import compose, MOTIFS
from sanfona_amostrada import render_sampled

EXPERIMENTS = [('xote_01_base', 65, .20), ('xote_02_semente', 137, .20),
               ('xote_03_variacao', 137, .80)]


def analyze(data):
    counts = Counter(data['motivos_gerados'])
    notes = data['melodia_notas']
    return {'musica': data['nome'], 'semente': data['semente'], 'variacao': data['variacao'],
            'duracao_segundos': data['duracao_segundos'], 'motivos': len(data['motivos_gerados']),
            'motivos_distintos': len(counts), 'notas_melodia': len(notes),
            'alturas_distintas': len({n['nota'] for n in notes}),
            'distribuicao_motivos': dict(sorted(counts.items())),
            'sequencia_motivos': data['motivos_gerados']}


def plot_results(results, root):
    plt.figure(figsize=(8, 3.7))
    names = list(MOTIFS)
    for i, result in enumerate(results):
        x = [j+(i-1)*.24 for j in range(len(names))]
        y = [result['distribuicao_motivos'].get(name, 0) for name in names]
        plt.bar(x, y, width=.24, label=result['musica'].replace('xote_', ''))
    plt.xticks(range(len(names)), names, rotation=45, ha='right')
    plt.xlabel('Terminais da gramatica'); plt.ylabel('Contagem de motivos')
    plt.title('Diversidade das regras utilizadas nas tres musicas')
    plt.legend(fontsize=8); plt.tight_layout()
    plt.savefig(root/'relatorio'/'distribuicao_motivos.png', dpi=170)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--ciclos', type=int, default=2)
    parser.add_argument('--sem-audio', action='store_true')
    args = parser.parse_args()
    root = args.saida
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for name, seed, variation in EXPERIMENTS:
        data = compose(seed, variation, args.ciclos, name, root)
        results.append(analyze(data))
        if not args.sem_audio:
            samples = root/'instrumentos'/'amostras'
            render_sampled(root/'midis'/f'{name}.mid', samples/'sanfona_01.wav',
                           samples/'triangulo_A_final.wav', samples/'zabumba_aproximacao_01.wav',
                           root/'audios'/f'{name}.wav')
        print(name, 'motivos:', data['motivos_gerados'])
    report = root/'relatorio'
    report.mkdir(exist_ok=True)
    (report/'medidas.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n',
                                      encoding='utf-8')
    plot_results(results, root)
    print('Resultados salvos em relatorio/')


if __name__ == '__main__': main()
