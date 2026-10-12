## Executar no macOS

No Terminal, dentro da pasta extraída (Python 3.10+):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python experimentos.py
```

**Não precisa de SoundFont, FluidSynth nem scripts `.command`.** O comando `experimentos.py` regenera os três `.mid`, `.wav`, `.json` e as estatísticas/figura usadas no artigo. O tempo pode variar conforme o computador. Para apenas gerar MIDI e estatísticas, use `python experimentos.py --sem-audio`.

Para criar mais uma composição (saídas nas mesmas pastas):

```bash
python gerador.py --semente 2026 --variacao 0.5 --ciclos 2 --nome xote_novo
python sanfona_amostrada.py --midi midis/xote_novo.mid --saida audios/xote_novo.wav
```
## Sobre os instrumentos e a reprodutibilidade

As **três amostras WAV estão incluídas e são realmente usadas** pelo renderizador de áudio. Isso permite reproduzir o som sem instalar um instrumento adicional. Porém, o arquivo de sanfona contém apenas algumas notas originais: as demais são produzidas por **transposição/re-amostragem**, não por execução nativa de toda a SoundFont. Essa limitação pode introduzir artefatos perceptíveis (timbre semelhante a música eletrônica). A zabumba é uma aproximação construída com samples de bumbo e side stick, e não uma gravação acústica. O MIDI sozinho, aberto em outro programa, pode soar diferente do WAV, porque a biblioteca de sons de reprodução será diferente.

https://chatgpt.com/c/6acc44e1-50fc-83e9-aeb4-0a3006ddaa8c
