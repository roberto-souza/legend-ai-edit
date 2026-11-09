# Etapa 3: rascunho

Entrada: o plano de corte aprovado, já resolvido (`plano_vNN.resolvido.json`).

1. Monte: `.venv/bin/python scripts/build_draft.py videos/<pasta> trabalho/plano_vNN.resolvido.json`. O script cria `final/<pasta>_rascunho_vNN.mp4` (1080p, a partir dos proxies) e `trabalho/rascunho_vNN.edl.json`, sempre com o próximo número de versão livre.
   - Corta os silêncios maiores que `--max-pause` (padrão 0,45 s) dentro de cada trecho. Trechos com `+fim` mantêm as pausas.
   - Põe as bordas de cada trecho sobre o silêncio real do áudio.
   - Corta no quadro exato, com o áudio cortado na amostra correspondente e um fade de 10 ms em cada corte.
   - Encaixa tudo em 1920×1080. Clipe vertical fica centralizado sobre uma cópia dele mesmo, ampliada e desfocada.
   - `broll` entra sem som. `efeito glitch_pb` dá 8 quadros de glitch colorido e depois preto e branco até o fim do trecho.
2. Confira antes de mostrar ao usuário:
   - a contagem de quadros do arquivo é igual ao `total_frames` do EDL;
   - o áudio tem a mesma duração do vídeo;
   - uma nova transcrição do rascunho bate com o texto do plano, sem palavra cortada e sem palavra sobrando;
   - os quadros das imagens de apoio e do fim estão certos.

Sem zoom, legenda nem música: isso é acabamento.

Um silêncio que não foi cortado pode ser fala arrastada ou "éé", e não pausa. Meça com `silencedetect` antes de mexer no limiar.
