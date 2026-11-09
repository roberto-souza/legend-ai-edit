# 01: instalar o Legend AI Edit nesta máquina

## Quando usar

Na primeira vez, num Mac que ainda não tem `~/Movies/legend-ai-edit/`. Pode rodar de novo sem problema: cada passo confere antes de criar e nunca sobrescreve.

## Prompt

Abra o Claude Code em `~/Movies` e cole:

```text
Leia https://raw.githubusercontent.com/roberto-souza/legend-ai-edit/main/prompts/01-instalar.md e execute a seção "O que o agente faz".
```

## O que o agente faz

Regras para a sessão inteira:
- Mostre o que vai fazer e espere o "sim" antes de **cada** instalação, download grande ou escrita fora de `~/Movies/legend-ai-edit/`.
- Nunca mova, renomeie nem apague vídeo, áudio ou LUT do usuário: copie.
- Prosa em pt-BR; código, nomes de script e mensagens técnicas em inglês.

1. **Confira a máquina.** Rode `sw_vers`, `uname -m` e `df -h ~/Movies`.
   - Pare se não for macOS ou se não for `arm64`.
   - Mostre o espaço livre. Bruto 4K ocupa uns 6 GB a cada 10 min.
2. **Inventário, sem instalar nada.** Mostre numa tabela o que existe e em que versão: Homebrew, git, Node.js (22 ou mais novo), Python (3.11 ou mais novo), `uv` e `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`.
   - Se o Homebrew faltar, pare e indique https://brew.sh.
   - Se o Node.js já existe por nvm, fnm ou volta, não instale por cima. Só avise se a versão for menor que 22.
3. **Clone.** Se `~/Movies/legend-ai-edit` não existir:
   ```bash
   git clone https://github.com/roberto-souza/legend-ai-edit ~/Movies/legend-ai-edit
   ```
   Se existir, mostre `git status` e `git log -1`. Não altere nada.
4. **Setup.** Leia `scripts/setup.sh` e mostre o que ele instala: `ffmpeg-full` e `uv` pelo `Brewfile`, o `.venv` pelo `pyproject.toml`, o modelo do Whisper (uns 1,5 GB em `.cache/`) e o HyperFrames em `motion/`. Com o "sim", rode:
   ```bash
   cd ~/Movies/legend-ai-edit && scripts/setup.sh
   ```
5. **Teste a transcrição** com um áudio sintético, sem usar arquivo do usuário:
   ```bash
   say -v Luciana "Olá, este é um teste de transcrição do Legend AI Edit." -o /tmp/lae-test.aiff
   ```
   Transcreva com `.venv/bin/python`, importando `lae` antes de `mlx_whisper`, com modelo `mlx-community/whisper-large-v3-turbo`, `language="pt"` e `word_timestamps=True`.
   - Pare se as palavras não vierem com `start` e `end` próprios.
   - Mostre as 5 primeiras palavras com os tempos.
6. **Câmera e LUT.** Pergunte qual câmera a pessoa usa e se grava em log.
   - Se gravar em log: peça o `.cube` de log para Rec.709, **copie** para `luts/<camera>_<log>-to-rec709.cube` e confira:
     ```bash
     /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -hide_banner -f lavfi -i testsrc2=size=1920x1080:rate=30 -t 1 -vf "lut3d=luts/<arquivo>.cube" -f null -
     ```
   - Se não gravar em log: anote que a configuração de acabamento usa `"lut": "nenhum"`.
7. **Memória pessoal.** Crie `CLAUDE.local.md` e `.memoria/MEMORIA.md` a partir de `docs/modelos/memoria.md`, os dois fora do git. Pergunte e anote:
   - nome e canal;
   - tipo de vídeo;
   - idioma;
   - pessoas que costumam aparecer;
   - gostos já conhecidos (música, legenda).
8. **Estilo.** Copie `estilos/palanque.md` para `estilos/<canal>.md` como ponto de partida. Explique que o estilo vai sendo ajustado a cada vídeo aprovado.
9. **Epidemic Sound (opcional).** O `.mcp.json` já traz o servidor. Peça à pessoa para:
   - reabrir o Claude Code dentro de `~/Movies/legend-ai-edit`;
   - aprovar o servidor;
   - autenticar por `/mcp`.

   Teste só com uma busca de efeito sonoro por "whoosh"; não baixe nada. Lembre que a licença de uso no canal depende da assinatura dela.
10. **Primeiro vídeo.** Pergunte a data da gravação e um nome curto. Crie `videos/AAAA-MM-DD_nome/` com `bruto/`, `assets/`, `trabalho/` e `final/`, e peça para a pessoa **copiar** os arquivos da câmera para `bruto/`.
11. **Entregue.** Explique em linguagem simples:
    - o que foi instalado e onde ficou;
    - como abrir o editor (`scripts/editor.sh`);
    - que o próximo passo é chamar `/editar-video` no Claude Code aberto em `~/Movies/legend-ai-edit`.
