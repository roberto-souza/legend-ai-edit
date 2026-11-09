# Etapa 2: plano de corte

Entrada: a preparação aprovada, com `projeto.yml` dizendo quais clipes ficaram fora.

1. Leia as transcrições dos clipes aprovados, as palavras com os tempos, e o `estilos/<projeto>.md`.
2. Escreva `trabalho/plano_vNN.md` com:
   - um roteiro em blocos;
   - os trechos na ordem de montagem, no formato `- <clipe> "<texto exato da transcrição>"`;
   - o que ficou de fora e por quê;
   - os pontos para o usuário conferir.
3. Resolva o plano: `.venv/bin/python scripts/resolve_plan.py videos/<pasta> trabalho/plano_vNN.md` cria `plano_vNN.resolvido.json` com os tempos, os quadros e as palavras de baixa confiança. Um erro de "matches" quer dizer que a citação não bate com a transcrição ou aparece mais de uma vez: corrija o texto no plano. Nunca escreva tempos à mão.

O Claude decide o texto; o script calcula o tempo. As pausas longas ficam para o rascunho.

Extras do formato do plano (a referência completa está no topo de `scripts/resolve_plan.py`):
- `<clipe>@N "…"` escolhe a N-ésima vez que a frase foi dita, útil quando há vários takes.
- `+fim` depois da citação mantém a imagem e as pausas até o fim do clipe, por exemplo quando uma reação ou uma tela vem depois da fala.
- `- apoio <clipe>` põe o clipe inteiro, só a imagem, por cima do trecho anterior; o som continua sendo o do trecho anterior.
- `- efeito glitch_pb desde "<palavras>"` aplica um glitch e deixa em preto e branco desde essas palavras até o fim do trecho anterior.
- `- broll <clipe> <N>s` é um plano sem som, tirado do meio do clipe; a música entra no acabamento.

Quando chegarem clipes novos, rode de novo a preparação com `inventory.py --version vNN`. Os outros scripts usam sempre o inventário mais recente.
