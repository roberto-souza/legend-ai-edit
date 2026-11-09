# Etapa 4: acabamento

Entrada: o EDL do rascunho aprovado (`trabalho/rascunho_vNN.edl.json`). Os cortes não mudam aqui.

1. Escolha a música e os efeitos sonoros no Epidemic Sound. Mostre as prévias (`lqmp3Url`) e baixe só com o "sim" do usuário:
   - música do vídeo em `videos/<pasta>/assets/` (fora do git);
   - efeitos sonoros reutilizáveis em `sfx/<tipo>/`, com uma linha em `sfx/INDEX.md`.
2. Escreva `trabalho/acabamento_vNN.json`. O formato está no topo de `scripts/finish.py`. Use âncoras (`broll`, `efeito`, `trecho:<texto>`), nunca tempos escritos à mão.
3. Gere a prévia: `.venv/bin/python scripts/finish.py videos/<pasta> trabalho/rascunho_vNN.edl.json trabalho/acabamento_vNN.json`. Ela sai em 1080p, a partir dos proxies, em `final/<pasta>_acabamento_vNN.mp4`. O script:
   - dá zoom alternado em `zoom_max` nos cortes secos;
   - nivela a voz de cada trecho em -16 LUFS;
   - mixa música e efeitos sonoros;
   - aplica um ganho fixo até -14 LUFS, com limitador em -1 dBTP;
   - queima a legenda (`.ass` em `trabalho/`).
4. Confira:
   - a contagem de quadros é igual à do rascunho;
   - o total fica em -14 LUFS (±1), a voz por trecho entre -13 e -16, e a música só com b-roll uns 4 dB abaixo da voz;
   - nenhuma legenda termina em palavra solta ("do", "de", "que").
5. Correções de legenda (palavra que o Whisper errou) ficam em `trabalho/correcoes_legenda.json` (`clip`, `de`, `para`). A transcrição original não muda. O `finish.py` e o editor aplicam as correções.
6. A legenda usa só as palavras do trecho do plano, sem vazamento de palavras do take vizinho. A primeira palavra de cada take vai em maiúscula. A maiúscula que o Whisper põe no começo de cada segmento, no meio da frase, vira minúscula, exceto em nomes próprios (`CANON` no `finish.py`).
7. Texto na tela: o campo `rotulo` de um corte, na linha do tempo, aparece em amarelo no canto de cima, por exemplo um contador de tentativas.
8. Motions, todos opcionais:
   - **Na configuração** (`acabamento_vNN.json`):
     - `zoom_suave`: avanço lento em cortes de fala com mais de 2,5 s;
     - `legenda_destaque`: cor da palavra que está sendo dita;
     - `sfx_transicao`: whoosh automático em cada transição;
     - `sfx_rotulo`: som a cada número novo do contador;
     - `sfx_titulo`: som leve na entrada de cada título;
     - `titulo_selo`: texto pequeno acima do título;
     - `nomes_proprios`: grafia fixa na legenda (ex.: `["Palanque", "CTG"]`).
   - **Por corte, na linha do tempo:**
     - `zoom_fim`: avanço suave até esse zoom;
     - `velocidade`: só em b-roll; acelera o trecho em timelapse (ex.: 40), e a duração na linha do tempo vira a duração acelerada;
     - `transicao`: `flash`, `punch` ou `fade`;
     - `titulo`: título animado do HyperFrames no alto (`docs/etapas/motion.md`);
     - `nome`: nome na tela, animado no HyperFrames (`motion/nome`), no formato "Nome | função";
   - Tudo isso aparece no inspetor do editor.
9. Depois da aprovação, o render final sai do mesmo EDL e da mesma configuração, com `--source bruto`: 4K com o LUT, gerando `final/<pasta>_vNN.mp4`.

## Depois do final aprovado: liberar espaço

`.venv/bin/python scripts/limpar.py videos/<pasta> --versoes --proxies --motion` mostra o que pode sair e quanto ocupa. Com `--aplicar`, manda para a Lixeira do macOS, de onde dá para recuperar até ela ser esvaziada.

- Sai: as versões antigas (rascunhos, prévias e finais anteriores), os proxies e o cache de motion.
- Fica sempre: `bruto/`, `assets/`, os textos de `trabalho/` e o final mais recente.
- Sempre pergunte antes quais categorias limpar. Os brutos são mídia da pessoa: só ela decide se apaga, depois de ter cópia em outro lugar.
